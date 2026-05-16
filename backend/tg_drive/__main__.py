"""Telegram Drive entry point.

Works in two execution modes:
  * `python -m tg_drive` — Python loads us as part of the `tg_drive` package
  * PyInstaller bundle — this file is the bootloader's start script, with
    `tg_drive/` on sys.path

Using an absolute import keeps both modes happy. A relative `from .app`
would fail under PyInstaller because the bundle has no package context.
"""

from tg_drive.app import main

if __name__ == "__main__":
    main()
