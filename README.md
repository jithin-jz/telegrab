# Telegrab

<p align="center">
  <img src="https://res.cloudinary.com/dykc4e2yl/image/upload/v1778307719/image_au8drq.png" width="120" height="120" alt="Telegrab Logo">
</p>

<h3 align="center">Your Files, Reimagined.</h3>

<p align="center">
  <b>Telegrab</b> is a high-performance, privacy-centric desktop application that transforms your Telegram account into an encrypted, unlimited, and free cloud storage solution.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-emerald.svg?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/React-2024-cyan.svg?style=flat-square&logo=react" alt="React">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-blueviolet.svg?style=flat-square" alt="Platform">
</p>

---

## 🚀 Overview

Telegrab bridges the gap between Telegram's massive cloud infrastructure and a traditional file explorer experience. By leveraging the **MTProto** protocol, it allows you to store, manage, and stream files directly from Telegram's servers without any third-party intermediaries.

### Why Telegrab?

- **Zero Costs**: No subscription fees or storage caps—ever.
- **Privacy First**: Files are handled directly between your machine and Telegram. No middleware servers involved.
- **Modern Experience**: A sleek, GPU-accelerated interface built with React and Framer Motion.

---

## 🏗️ Architecture

Telegrab uses a hybrid architecture combining a high-concurrency Python backend with a reactive TypeScript frontend.

```mermaid
graph TD
    subgraph "Frontend (React + Vite)"
        UI[User Interface]
        SC[Settings Context]
        TC[TanStack Query]
    end

    subgraph "Backend (Python + Telethon)"
        BR[Bridge Layer]
        API[FastAPI REST Server]
        TG[Telethon Client]
    end

    UI <-->|JSON Bridge| BR
    BR <--> TG
    TG <-->|MTProto| TELEGRAM((Telegram Cloud))
    API <--> TG
```

---

## ✨ Key Features

### 📁 Advanced File Management
A fully-featured explorer supporting drag-and-drop, custom folders, and bulk operations.
- **Infinite Hierarchy**: Organize your cloud with nested folders.
- **Smart Selection**: Multi-select with Shift/Ctrl, bulk download, and bulk move.

### 🎥 Seamless Media Streaming
High-performance streaming engine with HTTP Range request support.
- **Instant Playback**: Watch 4K videos or listen to lossless audio without waiting for the full download.
- **Deep Seeking**: Jump to any timestamp instantly.

### 🛠️ Automation & API
Telegrab exposes an optional, authenticated REST API for developers.
- **Headless Integration**: Programmatically upload/download files.
- **AI-Ready**: Feed your Telegram data into LLM pipelines or other local tools.

---

## 🛠️ Technical Stack

| Layer | Technology |
| :--- | :--- |
| **Interface** | React 18, TypeScript, Tailwind CSS, Framer Motion |
| **State** | TanStack Query (React Query), Context API |
| **Engine** | Python 3.11+, Telethon (MTProto), FastAPI |
| **Runtime** | pywebview (WebView2 on Windows, WebKit on macOS) |
| **Build System** | Vite, PyInstaller, GitHub Actions |

---

## 📥 Installation

### 1. Download
Visit the [Releases](https://github.com/jithin-jz/telegrab/releases) page and download the installer for your platform:
- **Windows**: `telegrab-setup.exe`
- **macOS**: `telegrab.dmg`

### 2. Configuration
On first launch, you will need your **Telegram API Credentials**:
1. Login to [my.telegram.org](https://my.telegram.org).
2. Go to **API development tools**.
3. Create a new application to get your `api_id` and `api_hash`.

---

## 🔄 Data Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Telegram

    User->>Frontend: Drag & Drop File
    Frontend->>Backend: cmd_upload_file(path)
    Backend->>Telegram: Multipart Upload (MTProto)
    Telegram-->>Backend: File Hash & ID
    Backend-->>Frontend: Progress Updates
    Backend->>Frontend: Upload Success
```

---

## 🤝 Credits

Telegrab is a modern evolution of the original [**Telegram-Drive**](https://github.com/caamer20/Telegram-Drive) project by [@caamer20](https://github.com/caamer20). 

While the core concept remains the same, Telegrab is a ground-up rewrite in Python, optimized for performance, security, and a premium user experience.

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <font size="2">
    <i>Disclaimer: This application is not affiliated with Telegram FZ-LLC. Use responsibly and in accordance with Telegram's Terms of Service.</i>
  </font>
</p>
