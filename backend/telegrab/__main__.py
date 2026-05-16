"""Telegram Drive entry point.

Works in two execution modes:
  * `python -m telegrab` — Python loads us as part of the `telegrab` package
  * PyInstaller bundle — this file is the bootloader's start script, with
    `telegrab/` on sys.path

Using an absolute import keeps both modes happy. A relative `from .app`
would fail under PyInstaller because the bundle has no package context.
"""

from telegrab.app import main

if __name__ == "__main__":
    main()
