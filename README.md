# Telegrab

**Telegrab** is a cross-platform desktop app that turns your Telegram account into unlimited, private cloud storage.

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)

## Features

- **Unlimited storage** — powered by Telegram's cloud, no caps
- **File explorer UI** — drag & drop, folders, grid/list views
- **Media streaming** — seekable video/audio playback with HTTP range requests
- **Built-in viewers** — PDF viewer, image previews, inline thumbnails
- **Privacy-first** — no third-party servers; everything stays on your machine
- **REST API** — optional local API with key auth for automations & AI integrations
- **Cross-platform** — Windows, macOS, and Linux

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React · Vite · TypeScript · Tailwind CSS |
| Backend | Python 3.11+ · Telethon (MTProto) · FastAPI |
| Desktop | pywebview (WebView2 / WebKit) |

## Quick Start

### Download

Grab the latest installer from the [Releases](https://github.com/jithin-jz/telegrab/releases) page:

| Platform | File |
|---|---|
| Windows 10/11 | `TelegramDrive.exe` |
| macOS 10.15+ | `TelegramDrive.dmg` |

You'll need **Telegram API credentials** on first launch — get them from [my.telegram.org](https://my.telegram.org) → *API development tools*.

### Run from Source

**Requirements:** Python 3.11+, Node.js 18+, Telegram API credentials

```bash
git clone https://github.com/jithin-jz/telegrab.git
cd telegrab

# Production
python run.py

# Development (Vite HMR + Python)
python run.py --dev
```

The launcher creates a virtualenv, installs dependencies, builds the frontend, and opens the app automatically.

## Data Storage

| Platform | Location |
|---|---|
| Windows | `%APPDATA%\TelegramDrive\` |
| macOS | `~/Library/Application Support/TelegramDrive/` |
| Linux | `~/.local/share/TelegramDrive/` |

## Build Installers

```bash
python installer/build.py
```

Or tag a release to trigger the CI pipeline:

```bash
git tag v1.5.0 && git push --tags
```

GitHub Actions builds Windows and macOS installers automatically.

## Credits

This project is inspired by and rewritten in Python from [**Telegram-Drive**](https://github.com/caamer20/Telegram-Drive) by [@caamer20](https://github.com/caamer20). The original project provided the core concept; Telegrab rebuilds the implementation with a Python backend (Telethon + FastAPI) and a modernised React frontend.

## License

MIT License — see [LICENSE](LICENSE) for details.

---

*Disclaimer: This application is not affiliated with Telegram FZ-LLC. Use responsibly and in accordance with Telegram's Terms of Service.*
