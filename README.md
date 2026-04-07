# Baba Desktop v9 — Business Brain OS ULTIMATE MERGED EDITION

A local-first, privacy-preserving AI desktop application. **ULTIMATE MERGED EDITION** — everything connected, everything working, no limits.

## Features

### AI & Intelligence
- **7 AI Providers** — Ollama, Jan, LM Studio (local) + Groq, Gemini, OpenRouter, Qwen (cloud)
- **Auto-detect & fallback** — automatically finds running local servers, chains providers on failure
- **8 Domain Agents** — Legal, Accounting, Supplier, Deals/Property, Content, Comms, PA/Admin, Money Engine
- **Cowork Autonomous Mode** — multi-step planning, execution, self-correction with approval gates
- **Vision Pipeline** — image/PDF analysis with actual multimodal model support
- **Self-Tool Builder** — AI proposes, writes, tests, and promotes new Python tools

### Data & Knowledge
- **Brain Index** — SQLite-powered local knowledge base with 19-column rich schema
- **Smart Import** — emails (.eml), WhatsApp exports, PDFs, web pages, auto-classification
- **Persistent Memory** — cross-session context with ChromaDB vector store
- **Meeting Intelligence** — transcript/audio processing, action items, follow-up emails

### Automation & Control
- **PC Control** — mouse, keyboard, screenshot, OCR, window management via WebSocket bridge
- **App Automation** — Outlook, WhatsApp Web, Chrome, Excel, VS Code, social platforms
- **Task Scheduler** — daily, weekly, monthly, file-triggered automation
- **Dispatch System** — priority task queue with background worker
- **Chrome Connector** — HTTP bridge for Chrome extension integration

### Developer & Extensions
- **DevTools** — Git operations, VS Code integration, terminal, code analysis
- **Claw Installers** — 6 specialist runtime plugins (CoClaw, NemoClaw, AutoClaw, etc.)
- **REST API** — full HTTP endpoints for chat, brain, agents, vision, PC control

### Safety
- **Approval Gates** — nothing sends, writes, executes, or installs without your approval
- **Never moves money** — never signs documents — never installs without approval
- **Local-first** — your data stays on your machine

## Quick Start

### 1. Setup
```bash
python setup.py
```

### 2. Add API Keys (optional — local AI works without keys)
```bash
copy .env.example .env
# Edit .env and add your keys
```

### 3. Launch
```bash
# Windows — double-click:
start_windows.bat

# Or from terminal:
python main.py
```

## CLI Commands

```bash
python run_agent.py legal "Find all unresolved legal issues"
python run_agent.py money                           # Full money analysis
python run_local_ai_link.py                         # Link/verify Ollama + Jan + LM Studio
python run_cowork.py "Download all invoices and summarize"
python run_import.py stats                          # Brain Index statistics
python run_import.py emails /path/to/emails/
python run_pc_bridge.py --port 8765
python verify_setup.py                              # Check everything
```

## AI Providers

| Provider | Type | Port | API Key |
|----------|------|------|---------|
| Ollama | Local | 11434 | None |
| Jan | Local | 1337 | None |
| LM Studio | Local | 1234 | None |
| Groq | Cloud | — | GROQ_API_KEY (free) |
| Gemini | Cloud | — | GEMINI_API_KEY (free) |
| OpenRouter | Cloud | — | OPENROUTER_API_KEY (free models) |
| Qwen | Cloud | — | QWEN_API_KEY |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Baba Desktop v9 (Tkinter GUI)           │
├──────────────┬──────────────────────────────────────────┤
│   Sidebar    │          Main Content Area               │
│              │                                          │
│ INTELLIGENCE │  Chat / Cowork / Agents / Tools          │
│ DATA         │  Brain Index / Import / Vision           │
│ MONEY        │  Money Engine                            │
│ CONTROL      │  PC Control / Scheduler / Meetings       │
│ SYSTEM       │  Providers / Apps / Social / Browser     │
│              │  DevTools / Claws / Self-Evolving        │
│              │  Research / Settings                     │
├──────────────┴──────────────────────────────────────────┤
│  Backend: Brain Index → Provider Pool → Agents → Tools  │
│           Vision → PC Bridge → App Bridge → Cowork      │
│           Scheduler → Dispatcher → Memory → Chrome       │
│           DevTools → Meetings → Claws → Tool Builder     │
└─────────────────────────────────────────────────────────┘
```

## Folder Structure

```
baba_merged/
├── main.py                    # Entry point — starts everything
├── baba_desktop.py            # Full Tkinter GUI (connected to ALL backend)
├── setup.py                   # One-shot setup
├── verify_setup.py            # Comprehensive verification
├── run_agent.py               # CLI: run domain agents
├── run_cowork.py              # CLI: autonomous tasks
├── run_import.py              # CLI: import data
├── run_pc_bridge.py           # CLI: PC Bridge server
├── start_windows.bat          # Windows launcher
├── start_mac_linux.sh         # Mac/Linux launcher
├── requirements.txt           # Dependencies
├── .env.example               # API key template
├── config/
│   ├── config.json            # Full configuration
│   └── settings.py            # Settings loader
├── src/
│   ├── brain/                 # Brain Index + importers
│   ├── providers/             # 7-provider pool with fallback
│   ├── agents/                # 8 domain agents + Money Engine
│   ├── tools/                 # Tool registry (11 built-in tools)
│   ├── vision/                # Image/PDF analysis pipeline
│   ├── pc_bridge/             # WebSocket PC control
│   ├── app_bridge/            # App automation (Outlook, WhatsApp, etc.)
│   ├── cowork/                # Autonomous multi-step agent
│   ├── scheduler/             # Time/trigger-based automation
│   ├── memory/                # Persistent cross-session memory
│   ├── dispatch/              # Priority task queue
│   ├── devtools/              # Git, VS Code, terminal, code analysis
│   ├── meetings/              # Meeting transcript processing
│   ├── chrome/                # Chrome extension HTTP bridge
│   ├── claws/                 # Plugin installer (6 claws)
│   └── tools_experimental/    # Self-tool builder + auto-generated tools
├── data/                      # Databases, imports, exports
├── logs/                      # Runtime logs (JSONL)
└── assets/                    # UI assets
```

## Requirements

- **Python 3.8+** (3.12+ recommended)
- **tkinter** (ships with Python)
- At least one AI provider (local or cloud)

## Philosophy

Local-first. Privacy-preserving. Your data stays on your machine.
You stay director — Baba never acts without your approval.

---

Built by Silva — v9 ULTIMATE MERGED EDITION
