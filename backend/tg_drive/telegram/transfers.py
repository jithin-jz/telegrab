"""Transfer cancellation registry.

Upload/download progress callbacks check `is_cancelled(transfer_id)` and
raise `asyncio.CancelledError` when the user has asked to abort. This keeps
the cancellation cooperative and side-effect-free.
"""

from __future__ import annotations


def cancel_transfer(state, transfer_id: str) -> None:
    """Record a request to cancel `transfer_id`."""
    if transfer_id:
        state.cancelled_transfers.add(transfer_id)


def is_cancelled(state, transfer_id: str) -> bool:
    return bool(transfer_id) and transfer_id in state.cancelled_transfers


def clear_cancellation(state, transfer_id: str) -> None:
    state.cancelled_transfers.discard(transfer_id)
