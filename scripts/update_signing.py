"""Ed25519 signing for release checksums (used by the auto-updater).

Usage:
    # One-time: create a key pair.
    python scripts/update_signing.py keygen
    #   -> prints the private key (store it as the UPDATE_SIGNING_KEY
    #      repository secret) and the public key (paste it into
    #      UPDATE_PUBLIC_KEY in backend/telegrab/services/updater.py).

    # In CI: write SHA256SUMS for the release files and sign it.
    python scripts/update_signing.py sums <dir> <file> [<file> ...]
    UPDATE_SIGNING_KEY=... python scripts/update_signing.py sign <dir>/SHA256SUMS

Requires the `cryptography` package (a backend dependency).
"""

from __future__ import annotations

import base64
import hashlib
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def keygen() -> None:
    private = Ed25519PrivateKey.generate()
    raw_private = private.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    raw_public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    print("UPDATE_SIGNING_KEY (secret):", base64.b64encode(raw_private).decode())
    print("UPDATE_PUBLIC_KEY (updater.py):", base64.b64encode(raw_public).decode())


def write_sums(out_dir: Path, files: list[Path]) -> Path:
    lines = []
    for f in sorted(files, key=lambda p: p.name):
        digest = hashlib.sha256(f.read_bytes()).hexdigest()
        lines.append(f"{digest}  {f.name}\n")
    sums = out_dir / "SHA256SUMS"
    sums.write_text("".join(lines), encoding="utf-8", newline="\n")
    print(sums.read_text(encoding="utf-8"), end="")
    return sums


def sign(sums: Path) -> Path:
    key_b64 = os.environ.get("UPDATE_SIGNING_KEY", "").strip()
    if not key_b64:
        sys.exit("UPDATE_SIGNING_KEY is not set")
    private = Ed25519PrivateKey.from_private_bytes(base64.b64decode(key_b64))
    signature = private.sign(sums.read_bytes())
    sig_path = sums.with_name(sums.name + ".sig")
    sig_path.write_text(base64.b64encode(signature).decode() + "\n", encoding="ascii")
    print(f"Signed {sums} -> {sig_path}")
    return sig_path


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "keygen":
        keygen()
    elif cmd == "sums" and len(sys.argv) >= 4:
        write_sums(Path(sys.argv[2]), [Path(p) for p in sys.argv[3:]])
    elif cmd == "sign" and len(sys.argv) == 3:
        sign(Path(sys.argv[2]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
