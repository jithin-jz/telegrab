"""Simulated-network benchmark for the transfer engine.

Compares the previous engine's strategy (a fresh set of connections per
file, one request in flight per connection) with the pooled, pipelined
engine — against a model of a real link, without touching Telegram:

  * round-trip latency per request
  * a bandwidth cap per connection (Telegram throttles per socket)
  * a cost for opening + authorizing each connection

Usage (from the repo root):
    backend/.venv/Scripts/python scripts/bench_transfers.py      # Windows
    backend/.venv/bin/python scripts/bench_transfers.py          # macOS/Linux

Real-world speed also depends on your line and on Telegram's account-level
limits; this measures only what the client controls.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from telethon.tl.functions.upload import GetFileRequest  # noqa: E402
from telethon.tl.types import Document  # noqa: E402

from telegrab.telegram import fast_transfer as ft  # noqa: E402

MB = 1024 * 1024
RUNS = 3


class SimLink:
    """Latency + per-socket bandwidth model; returns zero-filled parts."""

    def __init__(self, rtt: float, conn_mbps: float, connect_cost: float, speedup: float):
        self.rtt = rtt / speedup
        self.bytes_per_sec = conn_mbps * MB * speedup
        self.connect_cost = connect_cost / speedup
        self.sockets = 0

    async def open_sender(self):
        await asyncio.sleep(self.connect_cost)
        self.sockets += 1
        lock = asyncio.Lock()

        class Sender:
            wire = lock  # one socket transmits one response at a time

            def disconnect(self):
                return None

        return Sender()

    async def call(self, sender, request):
        assert isinstance(request, GetFileRequest)
        await asyncio.sleep(self.rtt)  # request out + first byte back
        async with sender.wire:  # responses on one socket are serialized
            await asyncio.sleep(request.limit / self.bytes_per_sec)

        class R:
            bytes = b"\0" * request.limit

        return R()


def Loc(size: int) -> Document:  # noqa: N802
    return Document(
        id=1, access_hash=1, file_reference=b"", date=None, mime_type="", size=size,
        dc_id=2, attributes=[],
    )


def _legacy_part_size(size: int, max_part: int) -> int:
    """Part size rule of the previous engine (1 MB / 512 KB above 1 MB)."""
    from telethon import utils

    if size > MB:
        return max_part
    return int(utils.get_appropriated_part_size(size) * 1024)


def _legacy_connection_count(size: int) -> int:
    """Connection count the previous engine opened for every single file."""
    if size > 10 * MB:
        return 20
    if size > MB:
        return 16
    if size > 256 * 1024:
        return 8
    return 4


async def _download(link: SimLink, pool: ft.DcPool, size: int, out: Path) -> None:
    await ft.download_file(None, Loc(size), out, pool=pool)


async def run_scenario(name: str, sizes: list[int], concurrency: int, link_args: dict) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="tg-bench-"))
    total = sum(sizes)
    samples: dict[str, list[tuple[float, int]]] = {"before": [], "after": []}
    for _ in range(RUNS):
        for mode, result in (await _run_modes(sizes, concurrency, link_args, tmp)).items():
            samples[mode].append(result)
    results = {m: sorted(v)[len(v) // 2] for m, v in samples.items()}
    _report(name, sizes, concurrency, total, results)


async def _run_modes(sizes, concurrency, link_args, tmp):
    results = {}
    adaptive_part_size = ft._part_size_for
    for mode in ("before", "after"):
        ft._part_size_for = _legacy_part_size if mode == "before" else adaptive_part_size
        link = SimLink(**link_args)
        shared = ft.DcPool(
            None,
            2,
            sender_factory=link.open_sender,
            call=link.call,
            max_connections=ft.MAX_CONNECTIONS_PER_DC,
            requests_per_connection=ft.REQUESTS_PER_CONNECTION,
        )
        sem = asyncio.Semaphore(concurrency)

        async def one(i: int, size: int, link=link, shared=shared, mode=mode, sem=sem) -> None:
            async with sem:
                if mode == "before":
                    pool = ft.DcPool(
                        None,
                        2,
                        sender_factory=link.open_sender,
                        call=link.call,
                        max_connections=_legacy_connection_count(size),
                        requests_per_connection=1,
                    )
                    try:
                        await _download(link, pool, size, tmp / f"{mode}{i}")
                    finally:
                        await pool.close()
                else:
                    await _download(link, shared, size, tmp / f"{mode}{i}")

        t0 = time.perf_counter()
        await asyncio.gather(*(one(i, s) for i, s in enumerate(sizes)))
        elapsed = (time.perf_counter() - t0) * link_args["speedup"]
        await shared.close()
        results[mode] = (elapsed, link.sockets)
    ft._part_size_for = adaptive_part_size
    return results


def _report(name, sizes, concurrency, total, results):
    before, after = results["before"], results["after"]
    print(f"\n{name}  ({len(sizes)} file(s), {total / MB:.0f} MB, {concurrency} at a time)")
    for label, (elapsed, sockets) in (("before", before), ("after ", after)):
        print(
            f"  {label}: {total / MB / elapsed:7.1f} MB/s   {elapsed:6.1f} s   "
            f"{sockets:4d} connections opened"
        )
    print(f"  speed-up: {before[0] / after[0]:.1f}x")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--rtt", type=float, default=0.15, help="round trip, seconds")
    parser.add_argument("--conn-mbps", type=float, default=1.5, help="MB/s per socket")
    parser.add_argument("--connect", type=float, default=0.4, help="socket setup, seconds")
    parser.add_argument("--speedup", type=float, default=5.0, help="simulate N x faster")
    parser.add_argument("--runs", type=int, default=3, help="repeat and keep the median")
    parser.add_argument(
        "--disk", action="store_true", help="also write to disk (default: discard data)"
    )
    args = parser.parse_args()
    if not args.disk:
        # Measure the network engine only: at N-x time compression the disk
        # would otherwise need N-x real write speed and dominate the result.
        ft._SequentialWriter._write_all = lambda self, chunks: None
    global RUNS
    RUNS = args.runs
    link = {
        "rtt": args.rtt,
        "conn_mbps": args.conn_mbps,
        "connect_cost": args.connect,
        "speedup": args.speedup,
    }
    print(
        f"Simulated link: RTT {args.rtt * 1000:.0f} ms, {args.conn_mbps} MB/s per "
        f"connection, {args.connect * 1000:.0f} ms to open a connection"
    )
    await run_scenario("One large file", [200 * MB], 1, link)
    await run_scenario("Many photos", [3 * MB] * 60, 3, link)
    await run_scenario("Mixed batch", [40 * MB, 8 * MB, 2 * MB] * 8, 3, link)


if __name__ == "__main__":
    asyncio.run(main())
