"""Transfer cancellation registry.

Upload/download progress callbacks check `is_cancelled(transfer_id)` and
raise :class:`TransferCancelledError` when the user has asked to abort. This keeps
the cancellation cooperative and side-effect-free.

A dedicated exception (rather than `asyncio.CancelledError`) is used because
the callbacks run inside worker tasks: raising `CancelledError` there marks
the *task* as cancelled and confuses asyncio's own cancellation bookkeeping.
"""

from __future__ import annotations


class TransferCancelledError(Exception):
    """The user cancelled an in-flight transfer."""


def cancel_transfer(state, transfer_id: str) -> None:
    """Record a request to cancel `transfer_id`."""
    if transfer_id:
        state.cancelled_transfers.add(transfer_id)


def is_cancelled(state, transfer_id: str) -> bool:
    return bool(transfer_id) and transfer_id in state.cancelled_transfers


def clear_cancellation(state, transfer_id: str) -> None:
    state.cancelled_transfers.discard(transfer_id)
