# Telegram Drive

**Telegram Drive** is an open-source, cross-platform desktop application that turns your Telegram account into an unlimited, secure cloud storage drive. Built with **React + Python (Telethon + FastAPI + pywebview)**.

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)

## What is Telegram Drive?

Telegram Drive uses the Telegram API to upload, organise, and manage files directly on Telegram's servers. It treats your "Saved Messages" and private channels as folders, giving you a familiar file-explorer interface for your Telegram cloud.

### Key features

* **Unlimited cloud storage** via Telegram's cloud
* **High-performance grid** with virtual scrolling (thousands of files)
* **Media streaming** with HTTP range requests (seekable video / audio)
* **Built-in PDF viewer** with infinite scroll
* **Drag & drop** uploads and file management
* **Inline thumbnails** for images and media
* **Folder management** via private Telegram channels
* **Optional REST API** with key auth for AI/LLM integrations (OpenAPI spec at `/api/v1/openapi.json`)
* **Privacy-focused** — no third-party servers; everything stays local

## Tech stack

| Layer    | Technology                                                |
|----------|-----------------------------------------------------------|
| Frontend | React + Vite + TypeScript + TailwindCSS                   |
| Backend  | Python 3.11+ + Telethon (Telegram MTProto)                |
| Webview  | pywebview (WebView2 on Windows, WebKit on macOS/Linux)    |
| HTTP     | FastAPI + uvicorn (media streaming + optional REST API)   |

## Getting started

### Download (recommended)

Pre-built installers are published on the [Releases page](https://github.com/caamer20/Telegram-Drive/releases):

| Platform | File | Notes |
|---|---|---|
| Windows 10 / 11 | `TelegramDrive.exe` | Single-file. Double-click to run. SmartScreen may warn on first launch — click "More info" → "Run anyway". |
| macOS 10.15+    | `TelegramDrive.dmg` | Drag `TelegramDrive.app` to Applications. Right-click → Open the first time (the build is unsigned). |

You'll need **Telegram API credentials** (`api_id` + `api_hash`) on first launch — get them from <https://my.telegram.org> → "API development tools".

### Run from source

If you'd rather run from source (or build your own installer), you need:

* **Python 3.11+**
* **Node.js 18+** (for bundling the frontend)
* **Telegram API credentials** — get from <https://my.telegram.org> → "API development tools"

Platform-specific:

* **Windows:** WebView2 runtime (already installed on recent Windows 10/11)
* **macOS:** Xcode Command Line Tools (`xcode-select --install`)
* **Linux:** GTK + WebKit2 (e.g. `sudo apt install gir1.2-webkit2-4.1 python3-gi`)

### Run

The `run.py` launcher creates a Python virtualenv on first run, installs the dependencies, builds the React bundle, and opens the desktop window:

```bash
git clone https://github.com/caamer20/Telegram-Drive.git
cd Telegram-Drive

# Production: build React, open the window
python run.py

# Development: Vite + HMR + Python window
python run.py --dev

# Open the webview devtools
python run.py --dev --debug
```

First launch installs ~120 MB of Python dependencies — subsequent launches are fast.

### Manual control (without `run.py`)

```bash
# 1. Install Python deps (one time)
cd backend
python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # macOS / Linux
pip install -r requirements.txt
cd ..

# 2. Build the frontend (once, or whenever the React code changes)
cd frontend
npm install
npm run build                    # produces frontend/dist/

# 3. Run the desktop app
cd ../backend
python -m tg_drive
```

For an HMR dev loop run `npm run dev` from `frontend/` in one shell, then in another:

```bash
# Windows
set TG_DRIVE_DEV_URL=http://localhost:5173
python -m tg_drive

# macOS / Linux
export TG_DRIVE_DEV_URL=http://localhost:5173
python -m tg_drive
```

### Where is data stored?

| Platform | Location                                                  |
|----------|------------------------------------------------------------|
| Windows  | `%APPDATA%\TelegramDrive\`                                |
| macOS    | `~/Library/Application Support/TelegramDrive/`            |
| Linux    | `~/.local/share/TelegramDrive/`                           |

Files there: `telegram.session` (Telethon SQLite), `bandwidth.json`, `api_settings.json`, `store.json`, `thumbnails/`. Preview cache lives in the OS cache directory.

## Project layout

```
Telegram-Drive/
├── run.py                      # launcher (creates venv, builds frontend, opens window)
├── README.md
├── landing.html                # marketing landing page (open directly in a browser)
│
├── frontend/                   # React + Vite + TypeScript
│   ├── package.json
│   ├── vite.config.ts          # aliases @tauri-apps/* → src/lib/platform/ shims
│   ├── tsconfig.json
│   ├── index.html
│   ├── public/
│   └── src/
│       ├── App.tsx, main.tsx
│       ├── components/         # AuthWizard, Dashboard, …
│       ├── contexts/           # Theme, Settings, Confirm, DropZone
│       ├── hooks/              # useFileUpload, useFileDownload, …
│       ├── lib/
│       │   ├── platform/       # JS shims that route Tauri-style invoke()/listen()
│       │   │                   # through pywebview (window.pywebview.api.*)
│       │   └── utils.ts
│       ├── styles/globals.css
│       └── types/index.ts
│
└── backend/                    # Python (Telethon + FastAPI + pywebview)
    ├── pyproject.toml
    ├── requirements.txt
    └── tg_drive/
        ├── app.py              # entry point (creates the pywebview window)
        ├── __main__.py         # `python -m tg_drive`
        │
        ├── config/             # paths, stream config, api settings (data only)
        ├── infra/              # runtime, event bus, JSON store, bandwidth
        ├── telegram/           # Telethon client, peer cache, transfers, media
        ├── services/           # use cases: auth, files, folders, preview, …
        └── api/                # bridge (pywebview), host commands, streaming, REST
```

## REST API

The REST API server is **off by default**. Enable it via *Settings → API*; it listens on `127.0.0.1:<port>` (default 8550). All endpoints except `/api/v1/health` require an `X-API-Key` header.

| Method | Path                                              | Description                  |
|--------|---------------------------------------------------|------------------------------|
| GET    | `/api/v1/health`                                  | unauthenticated health check |
| GET    | `/api/v1/files?folder_id=&page=&limit=&search=`   | list files                   |
| GET    | `/api/v1/files/{message_id}?folder_id=`           | one file's metadata          |
| GET    | `/api/v1/files/{message_id}/download?folder_id=`  | binary download              |
| GET    | `/api/v1/openapi.json`                            | OpenAPI spec                 |
| GET    | `/api/v1/docs`                                    | Swagger UI                   |

## Build installers

If you want to produce your own `.exe` / `.app` (e.g. to ship a fork), run:

```bash
python installer/build.py
```

This installs PyInstaller into the backend venv, builds the React bundle if missing, and runs PyInstaller against `installer/tg_drive.spec`. Output goes to `dist-installer/`:

* **Windows:** `dist-installer/TelegramDrive.exe` (single-file, ~80–100 MB)
* **macOS:** `dist-installer/TelegramDrive.app` (Cocoa bundle)
* **Linux:** `dist-installer/TelegramDrive/` (onedir layout)

PyInstaller doesn't cross-compile — build each platform on its native OS. The repo also ships `.github/workflows/release.yml`: tag a commit with `git tag v1.4.1 && git push --tags` and GitHub Actions will build both platforms in parallel and upload them as a draft release.

The Windows build is unsigned by default (SmartScreen warning on first run). To remove the warning, sign the binary with a code-signing certificate before distributing — `installer/tg_drive.spec` exposes `codesign_identity` for this.

## Open source & license

This project is **Free and Open Source Software** licensed under the **MIT License**.

---

*Disclaimer: This application is not affiliated with Telegram FZ-LLC. Use responsibly and in accordance with Telegram's Terms of Service.*
