# Telegrab

Desktop cloud storage built on Telegram. Store, stream and manage files of any type in your own Telegram account, with no storage quota and no subscription.

[![CI](https://github.com/jithin-jz/telegrab/actions/workflows/ci.yml/badge.svg)](https://github.com/jithin-jz/telegrab/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/jithin-jz/telegrab)](https://github.com/jithin-jz/telegrab/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Features

- **Fast transfers.** Parallel, pipelined uploads and downloads over a shared connection pool, with per-part retries.
- **Media streaming.** Play video and audio, and view PDFs, without downloading the whole file.
- **Encrypted vaults.** AES-256-GCM encryption on your device before upload. Vaults work across reinstalls and devices.
- **Folders and search.** Organise files into folders and search across all of them.
- **Resilient queue.** Transfers pause when the network drops and resume when it returns.
- **Proxy support.** SOCKS5, SOCKS4, HTTP and MTProxy.
- **Updates.** Verified automatic installs on Windows; macOS and Linux link to the new release.

Available for Windows, macOS and Linux.

## Installation

1. Download the latest build from [Releases](https://github.com/jithin-jz/telegrab/releases/latest).
2. Create an API ID and hash at [my.telegram.org](https://my.telegram.org) under **API development tools**.
3. Start Telegrab, enter the API credentials, and sign in with your phone number or a QR code.

Release builds are not yet code-signed, so Windows SmartScreen and macOS Gatekeeper may show a warning on first launch.

## Development

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20.11+.

```bash
git clone https://github.com/jithin-jz/telegrab.git
cd telegrab
(cd backend && uv sync)
(cd frontend && npm ci)

python run.py --dev   # Vite dev server with hot reload
python run.py         # production bundle
```

The backend is Python (Telethon, pywebview); the frontend is React and TypeScript. Logs are written to `telegrab.log` in the app data directory.

### Checks

```bash
cd backend  && uv run ruff check telegrab/ tests/ && uv run pytest tests/
cd frontend && npm run lint && npm run typecheck && npm test
```

The same checks run in CI on every push and pull request.

### Releasing

1. Run `python scripts/bump_version.py X.Y.Z` and commit.
2. Push a `vX.Y.Z` tag. The release workflow builds and smoke-tests all platforms and publishes the installers with a `SHA256SUMS` file.

Code signing and signed updates are enabled through repository secrets. See the header of [`release.yml`](.github/workflows/release.yml).

## License

[MIT](LICENSE). Telegrab is an unofficial client and is not affiliated with or endorsed by Telegram.
