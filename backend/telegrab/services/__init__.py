"""Application services — use-case layer.

Each module exposes async (or sync, where appropriate) functions matching
the Tauri command surface. The bridge in `telegrab.api.bridge` wraps each
one as a sync method that schedules the coroutine on the runtime thread.
"""
