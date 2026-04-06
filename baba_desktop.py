#!/usr/bin/env python3
"""BABA DESKTOP v12 ULTIMATE - COMPLETE AI Desktop App. CONNECTED to ALL backend src/ modules."""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, simpledialog
import threading, json, os, sys, subprocess, queue, time, sqlite3, re, base64, traceback
from pathlib import Path
from datetime import datetime, UTC
from concurrent.futures import ThreadPoolExecutor
import urllib.request, urllib.error

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
LOGS_DIR = APP_DIR / "logs"
for d in [
    DATA_DIR,
    LOGS_DIR,
    DATA_DIR / "imports",
    DATA_DIR / "screenshots",
    DATA_DIR / "exports",
    DATA_DIR / "brain_index",
    DATA_DIR / "brain_memory",
]:
    d.mkdir(parents=True, exist_ok=True)

try:
    from config.settings import Settings
except ImportError:

    class Settings:
        def __init__(self):
            self.brain_db_path = str(DATA_DIR / "brain_index" / "brain.db")
            self.memory_dir = str(DATA_DIR / "brain_memory")
            self.log_dir = str(LOGS_DIR)
            self.theme = "Midnight"
            self.default_provider = "ollama"
            self.default_model = "qwen3.5:latest"
            self.voice_enabled = False
            self.safe_mode = True
            self.pc_bridge_port = 8765
            self.dispatch_port = 8767
            self.claws_dir = "src/claws/installed"

        @classmethod
        def load(cls):
            return cls()

        def save(self):
            pass


try:
    from src.brain.index import BrainIndex
except ImportError:
    BrainIndex = None

try:
    from src.providers.pool import ProviderPool
except ImportError:
    ProviderPool = None

try:
    from src.tools.registry import ToolRegistry
except ImportError:
    ToolRegistry = None

try:
    from src.vision.pipeline import VisionPipeline
except ImportError:
    VisionPipeline = None

try:
    from src.agents.orchestrator import AgentOrchestrator, MoneyEngine
except ImportError:
    AgentOrchestrator = None
    MoneyEngine = None

try:
    from src.pc_bridge.bridge import PCBridge
except ImportError:
    PCBridge = None

try:
    from src.app_bridge.bridge import AppBridge
except ImportError:
    AppBridge = None

try:
    from src.memory.memory import Memory
except ImportError:
    Memory = None

try:
    from src.dispatch.dispatcher import Dispatcher
except ImportError:
    Dispatcher = None

try:
    from src.scheduler.scheduler import Scheduler
except ImportError:
    Scheduler = None

try:
    from src.cowork.cowork import Cowork
except ImportError:
    Cowork = None

try:
    from src.devtools.devtools import DevTools
except ImportError:
    DevTools = None

try:
    from src.meetings.intelligence import MeetingIntelligence
except ImportError:
    MeetingIntelligence = None

try:
    from src.chrome.connector import ChromeConnector
except ImportError:
    ChromeConnector = None

try:
    from src.claws.installer import ClawInstaller
except ImportError:
    ClawInstaller = None

try:
    from src.tools_experimental.builder import ToolBuilder
except ImportError:
    ToolBuilder = None

THEMES = {
    "Midnight": {
        "bg": "#0f1117",
        "panel": "#161922",
        "panel2": "#1c2030",
        "card": "#1e2235",
        "border": "#2a2f45",
        "input_bg": "#1a1e2e",
        "header_bg": "#161922",
        "sidebar_bg": "#12141c",
        "sidebar_hover": "#1c2030",
        "accent": "#6c63ff",
        "accent2": "#ff6b6b",
        "green": "#00d68f",
        "red": "#ff6b6b",
        "yellow": "#ffc107",
        "purple": "#a78bfa",
        "text": "#e8eaf0",
        "text_sec": "#9ca3af",
        "muted": "#5a6080",
        "user_bubble": "#6c63ff",
        "ai_bubble": "#1e2235",
        "user_text": "#ffffff",
        "ai_text": "#e8eaf0",
        "sidebar_text": "#9ca3af",
        "sidebar_active": "#6c63ff",
        "input_text": "#e8eaf0",
        "suggestion_bg": "#1c2030",
        "suggestion_text": "#6c63ff",
    },
    "Ocean": {
        "bg": "#0b192c",
        "panel": "#0f2239",
        "panel2": "#132d4a",
        "card": "#153355",
        "border": "#1a3f63",
        "input_bg": "#0f2239",
        "header_bg": "#0f2239",
        "sidebar_bg": "#081420",
        "sidebar_hover": "#132d4a",
        "accent": "#00b4d8",
        "accent2": "#ff9f1c",
        "green": "#06d6a0",
        "red": "#ef476f",
        "yellow": "#ffd166",
        "purple": "#7b68ee",
        "text": "#caf0f8",
        "text_sec": "#90e0ef",
        "muted": "#48a9a6",
        "user_bubble": "#0077b6",
        "ai_bubble": "#153355",
        "user_text": "#ffffff",
        "ai_text": "#caf0f8",
        "sidebar_text": "#90e0ef",
        "sidebar_active": "#00b4d8",
        "input_text": "#caf0f8",
        "suggestion_bg": "#132d4a",
        "suggestion_text": "#00b4d8",
    },
    "Purple": {
        "bg": "#130f26",
        "panel": "#1a1535",
        "panel2": "#221c42",
        "card": "#282050",
        "border": "#332860",
        "input_bg": "#1a1535",
        "header_bg": "#1a1535",
        "sidebar_bg": "#0e0b1c",
        "sidebar_hover": "#221c42",
        "accent": "#bb86fc",
        "accent2": "#ff79c6",
        "green": "#03dac6",
        "red": "#cf6679",
        "yellow": "#ffd700",
        "purple": "#bb86fc",
        "text": "#e6e1f5",
        "text_sec": "#b4a8e0",
        "muted": "#6b6290",
        "user_bubble": "#7c4dff",
        "ai_bubble": "#282050",
        "user_text": "#ffffff",
        "ai_text": "#e6e1f5",
        "sidebar_text": "#b4a8e0",
        "sidebar_active": "#bb86fc",
        "input_text": "#e6e1f5",
        "suggestion_bg": "#221c42",
        "suggestion_text": "#bb86fc",
    },
    "White": {
        "bg": "#ffffff",
        "panel": "#f8f9fa",
        "panel2": "#f0f1f3",
        "card": "#ffffff",
        "border": "#e2e5ea",
        "input_bg": "#f0f1f3",
        "header_bg": "#ffffff",
        "sidebar_bg": "#ffffff",
        "sidebar_hover": "#f0f1f3",
        "accent": "#4f46e5",
        "accent2": "#f59e0b",
        "green": "#10b981",
        "red": "#ef4444",
        "yellow": "#f59e0b",
        "purple": "#8b5cf6",
        "text": "#1f2937",
        "text_sec": "#6b7280",
        "muted": "#9ca3af",
        "user_bubble": "#4f46e5",
        "ai_bubble": "#f0f1f3",
        "user_text": "#ffffff",
        "ai_text": "#1f2937",
        "sidebar_text": "#6b7280",
        "sidebar_active": "#4f46e5",
        "input_text": "#1f2937",
        "suggestion_bg": "#f0f1f3",
        "suggestion_text": "#4f46e5",
    },
    "Yellow": {
        "bg": "#1a1600",
        "panel": "#242000",
        "panel2": "#2e2800",
        "card": "#332c00",
        "border": "#3d3500",
        "input_bg": "#242000",
        "header_bg": "#242000",
        "sidebar_bg": "#141200",
        "sidebar_hover": "#2e2800",
        "accent": "#fbbf24",
        "accent2": "#f97316",
        "green": "#34d399",
        "red": "#f87171",
        "yellow": "#fbbf24",
        "purple": "#c084fc",
        "text": "#fef3c7",
        "text_sec": "#fcd34d",
        "muted": "#92700a",
        "user_bubble": "#d97706",
        "ai_bubble": "#332c00",
        "user_text": "#ffffff",
        "ai_text": "#fef3c7",
        "sidebar_text": "#fcd34d",
        "sidebar_active": "#fbbf24",
        "input_text": "#fef3c7",
        "suggestion_bg": "#2e2800",
        "suggestion_text": "#fbbf24",
    },
    "Green": {
        "bg": "#0a1a0a",
        "panel": "#0f240f",
        "panel2": "#142e14",
        "card": "#1a331a",
        "border": "#1f3d1f",
        "input_bg": "#0f240f",
        "header_bg": "#0f240f",
        "sidebar_bg": "#081408",
        "sidebar_hover": "#142e14",
        "accent": "#22c55e",
        "accent2": "#f59e0b",
        "green": "#22c55e",
        "red": "#ef4444",
        "yellow": "#eab308",
        "purple": "#a855f7",
        "text": "#dcfce7",
        "text_sec": "#86efac",
        "muted": "#166534",
        "user_bubble": "#16a34a",
        "ai_bubble": "#1a331a",
        "user_text": "#ffffff",
        "ai_text": "#dcfce7",
        "sidebar_text": "#86efac",
        "sidebar_active": "#22c55e",
        "input_text": "#dcfce7",
        "suggestion_bg": "#142e14",
        "suggestion_text": "#22c55e",
    },
    "Blue": {
        "bg": "#0a1628",
        "panel": "#0f1f35",
        "panel2": "#142842",
        "card": "#1a3350",
        "border": "#1f3d60",
        "input_bg": "#0f1f35",
        "header_bg": "#0f1f35",
        "sidebar_bg": "#081220",
        "sidebar_hover": "#142842",
        "accent": "#3b82f6",
        "accent2": "#f97316",
        "green": "#22c55e",
        "red": "#ef4444",
        "yellow": "#eab308",
        "purple": "#a855f7",
        "text": "#dbeafe",
        "text_sec": "#93c5fd",
        "muted": "#1e40af",
        "user_bubble": "#2563eb",
        "ai_bubble": "#1a3350",
        "user_text": "#ffffff",
        "ai_text": "#dbeafe",
        "sidebar_text": "#93c5fd",
        "sidebar_active": "#3b82f6",
        "input_text": "#dbeafe",
        "suggestion_bg": "#142842",
        "suggestion_text": "#3b82f6",
    },
    "Rose": {
        "bg": "#1a0a10",
        "panel": "#240f18",
        "panel2": "#2e1420",
        "card": "#331a28",
        "border": "#3d1f30",
        "input_bg": "#240f18",
        "header_bg": "#240f18",
        "sidebar_bg": "#14080c",
        "sidebar_hover": "#2e1420",
        "accent": "#f43f5e",
        "accent2": "#f59e0b",
        "green": "#10b981",
        "red": "#f43f5e",
        "yellow": "#fbbf24",
        "purple": "#a855f7",
        "text": "#ffe4e6",
        "text_sec": "#fda4af",
        "muted": "#9f1239",
        "user_bubble": "#e11d48",
        "ai_bubble": "#331a28",
        "user_text": "#ffffff",
        "ai_text": "#ffe4e6",
        "sidebar_text": "#fda4af",
        "sidebar_active": "#f43f5e",
        "input_text": "#ffe4e6",
        "suggestion_bg": "#2e1420",
        "suggestion_text": "#f43f5e",
    },
}
CURRENT_THEME = "Midnight"
T = THEMES[CURRENT_THEME]
FF = "Segoe UI"
FONT = (FF, 10)
FONT_SM = (FF, 9)
FONT_LG = (FF, 12, "bold")
FONT_XL = (FF, 14, "bold")
FONT_CHAT = (FF, 10)
FONT_CODE = ("Consolas", 10)

ALL_MODELS = {
    "ollama": [
        "qwen3.5:latest",
        "sorc/qwen3.5-claude-4.6-opus:4b",
        "sorc/qwen3.5-claude-4.6-opus:2b",
        "sorc/qwen3.5-claude-4.6-opus:0.8b",
        "huihui_ai/qwen3.5-abliterated:9b",
        "gemma-3-12b-it:latest",
        "gemma3:12b",
        "llama3.2:3b",
        "llama3.1:8b",
        "hf.co/prism-ml/Bonsai-8B-gguf:latest",
    ],
    "jan": [
        "unsloth/Qwen3.5-4B-GGUF",
        "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
        "Jackrong/Qwen3.5-9B-Claude-4.6-Opus-Reasoning-Distilled-v2-GGUF",
        "Jackrong/Qwen3.5-9B-Claude-4.6-Opus-Reasoning-Distilled-GGUF",
        "Jackrong/Qwen3.5-4B-Claude-4.6-Opus-Reasoning-Distilled-v2-GGUF",
        "Jackrong/Qwen3.5-9B-Gemini-3.1-Pro-Reasoning-Distill-GGUF",
        "Jackrong/Qwen3.5-9B-Neo-GGUF",
        "Jackrong/Qwopus3.5-9B-v3-GGUF",
        "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF",
    ],
    "lmstudio": [
        "lmstudio-community/qwen/qwen3.5-9b",
        "Jackrong/qwen3.5-9b-claude-4.6-opus-reasoning-distilled",
        "Jackrong/qwen3.5-4b-claude-4.6-opus-reasoning-distilled",
        "mradermacher/omnicoder-9b",
        "bartowski/prism-ml_bonsai-8b-unpacked",
        "ggml-org/gemma-4-e2b-it",
        "lmstudio-community/zai-org/glm-4.6v-flash",
        "prism-ml/bonsai-8b",
    ],
    "groq": ["llama-3.3-70b-versatile", "gemma2-9b-it", "mixtral-8x7b-32768"],
    "gemini": ["gemini-2.0-flash-exp", "gemini-1.5-pro"],
    "openrouter": [
        "mistralai/mistral-7b-instruct:free",
        "meta-llama/llama-3-8b-instruct:free",
    ],
    "qwen": [
        "qwen-max",
        "qwen2.5-72b-instruct",
        "qwen-turbo",
    ],
}

AGENTS_LIST = [
    {
        "id": "legal",
        "icon": "\u2696",
        "name": "Legal Agent",
        "tasks": [
            "Find all unresolved legal issues",
            "Scan contract deadlines",
            "Draft letter to council",
            "Draft formal demand to debtor",
            "Flag high-risk items",
        ],
    },
    {
        "id": "acct",
        "icon": "\U0001f4ca",
        "name": "Accounting Agent",
        "tasks": [
            "Build renewal calendar (90 days)",
            "Flag overdue invoices",
            "Cashflow summary",
            "VAT deadline check",
            "Draft invoice chaser",
        ],
    },
    {
        "id": "supplier",
        "icon": "\U0001f3ed",
        "name": "Supplier Agent",
        "tasks": [
            "Cluster suppliers by spend",
            "Find renegotiation targets",
            "Draft renegotiation email",
            "Find missing rebates",
        ],
    },
    {
        "id": "deals",
        "icon": "\U0001f3e0",
        "name": "Deal & Property Agent",
        "tasks": [
            "Find empty/closing premises",
            "Scan auction listings",
            "Subletting potential",
            "Liquidation stock scan",
        ],
    },
    {
        "id": "content",
        "icon": "\U0001f4dd",
        "name": "Content Agent",
        "tasks": [
            "Generate 10 content ideas",
            "Draft social media post",
            "Build 30-day calendar",
            "Write product description",
        ],
    },
    {
        "id": "comms",
        "icon": "\U0001f4ac",
        "name": "Comms Agent",
        "tasks": [
            "Find unanswered messages (7d+)",
            "Summarise WhatsApp conversations",
            "Draft follow-up email",
            "Build contact map",
        ],
    },
    {
        "id": "pa",
        "icon": "\U0001f4cb",
        "name": "PA & Admin Agent",
        "tasks": [
            "List upcoming renewals (90 days)",
            "Council correspondence summary",
            "Insurance review dates",
            "Vehicle MOT reminders",
        ],
    },
    {
        "id": "research",
        "icon": "\U0001f50d",
        "name": "Research Agent",
        "tasks": [
            "Run deep research on business priority",
            "Compare strategic options with risks",
            "Build executive brief with references",
        ],
    },
    {
        "id": "selfevolve",
        "icon": "\U0001f9ec",
        "name": "Self-Evolving Agent",
        "tasks": [
            "Audit repetitive tasks and propose automation",
            "Recommend workflow optimization plan",
            "Generate system-improvement roadmap",
        ],
    },
    {
        "id": "kairos",
        "icon": "\u23f1",
        "name": "Kairos Operations Agent",
        "tasks": [
            "Prioritise urgent tasks for next 24 hours",
            "Generate critical-path execution plan",
            "Build deadline-risk escalation matrix",
        ],
    },
    {
        "id": "obsidian",
        "icon": "\U0001f4d4",
        "name": "Obsidian Knowledge Agent",
        "tasks": [
            "Generate structured note from latest decisions",
            "Build linked knowledge map from recent projects",
            "Create weekly knowledge digest",
        ],
    },
]

AGENT_ICONS = {
    "legal": "\u2696",
    "acct": "\U0001f4ca",
    "supplier": "\U0001f3ed",
    "deals": "\U0001f3e0",
    "content": "\U0001f4dd",
    "comms": "\U0001f4ac",
    "pa": "\U0001f4cb",
    "research": "\U0001f50d",
    "selfevolve": "\U0001f9ec",
    "kairos": "\u23f1",
    "obsidian": "\U0001f4d4",
}


def _test_provider(provider):
    """Quick connectivity test for a provider. Returns (online, error_msg)."""
    try:
        if provider == "ollama":
            urllib.request.urlopen("http://localhost:11434", timeout=3)
            return True, ""
        elif provider == "jan":
            urllib.request.urlopen("http://localhost:1337", timeout=3)
            return True, ""
        elif provider == "lmstudio":
            urllib.request.urlopen("http://localhost:1234", timeout=3)
            return True, ""
        elif provider == "groq":
            return bool(os.getenv("GROQ_API_KEY", "")), "GROQ_API_KEY not set"
        elif provider == "gemini":
            return bool(os.getenv("GEMINI_API_KEY", "")), "GEMINI_API_KEY not set"
        elif provider == "openrouter":
            return bool(os.getenv("OPENROUTER_API_KEY", "")), "OPENROUTER_API_KEY not set"
        elif provider == "qwen":
            return bool(os.getenv("QWEN_API_KEY", "")), "QWEN_API_KEY not set"
        return False, f"Unknown provider: {provider}"
    except Exception as e:
        return False, str(e)


def _find_working_provider(preferred="ollama"):
    """Find the first working provider. Returns (provider_name, is_local)."""
    order = [preferred, "ollama", "jan", "lmstudio", "groq", "gemini", "openrouter", "qwen"]
    for p in order:
        online, _ = _test_provider(p)
        if online:
            return p, p in ("ollama", "jan", "lmstudio")
    return None, False


def _call_ai_sync(
    prompt, provider="ollama", model="", history=None, system="", max_tokens=2048
):
    if system:
        prompt = f"System: {system}\n\n{prompt}"

    # Test connectivity first
    online, err = _test_provider(provider)
    if not online:
        # Try to find a working provider
        working, is_local = _find_working_provider(provider)
        if working:
            # Auto-switch to working provider
            prompt = f"[Auto-switched from {provider} to {working}] {prompt}"
            provider = working
            if model:
                model = ALL_MODELS.get(working, [""])[0]
        else:
            return (
                f"NO AI PROVIDER AVAILABLE\n\n"
                f"Selected provider '{provider}' is not available: {err}\n\n"
                f"To fix this, do ONE of the following:\n\n"
                f"1. START OLLAMA: Run 'ollama serve' in a terminal\n"
                f"   (Download from https://ollama.com)\n\n"
                f"2. START JAN: Open Jan app\n"
                f"   (Download from https://jan.ai)\n\n"
                f"3. START LM STUDIO: Open LM Studio and start a server\n"
                f"   (Download from https://lmstudio.ai)\n\n"
                f"4. ADD API KEY: Set GROQ_API_KEY or GEMINI_API_KEY in .env file\n"
                f"   (Free keys at console.groq.com or aistudio.google.com)\n\n"
                f"5. Click the 'Probe' button in the top bar to check all providers"
            )

    if provider == "ollama":
        return _call_ollama(prompt, model or ALL_MODELS["ollama"][0])
    elif provider == "jan":
        return _call_openai(
            prompt, "http://localhost:1337/v1", model or ALL_MODELS["jan"][0]
        )
    elif provider == "lmstudio":
        return _call_openai(
            prompt, "http://localhost:1234/v1", model or ALL_MODELS["lmstudio"][0]
        )
    elif provider == "groq":
        key = os.getenv("GROQ_API_KEY", "")
        if not key:
            return "ERROR: GROQ_API_KEY not set in .env file"
        return _call_openai(
            prompt,
            "https://api.groq.com/openai/v1",
            model or ALL_MODELS["groq"][0],
            key,
        )
    elif provider == "gemini":
        key = os.getenv("GEMINI_API_KEY", "")
        if not key:
            return "ERROR: GEMINI_API_KEY not set in .env file"
        return _call_gemini(prompt, model or ALL_MODELS["gemini"][0], key)
    elif provider == "openrouter":
        key = os.getenv("OPENROUTER_API_KEY", "")
        if not key:
            return "ERROR: OPENROUTER_API_KEY not set in .env file"
        return _call_openai(
            prompt,
            "https://openrouter.ai/api/v1",
            model or ALL_MODELS["openrouter"][0],
            key,
            extra_headers={
                "HTTP-Referer": "http://localhost",
                "X-Title": "BabaDesktop",
            },
        )
    elif provider == "qwen":
        key = os.getenv("QWEN_API_KEY", "")
        if not key:
            return "ERROR: QWEN_API_KEY not set in .env file"
        return _call_openai(
            prompt,
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            model or "qwen-max",
            key,
        )
    return f"Unknown provider: {provider}"


def _call_ollama(prompt, model):
    messages = [{"role": "user", "content": prompt}]
    payload = {"model": model, "messages": messages, "stream": False}
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/chat",
            json.dumps(payload).encode(),
            {"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            return (
                json.loads(resp.read()).get("message", {}).get("content", "No response")
            )
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()
        except Exception:
            pass
        return (
            f"Ollama HTTP {e.code}: {e.reason}\n\n"
            f"Model '{model}' not found or not loaded.\n\n"
            f"Fix: Run 'ollama pull {model}' in a terminal first.\n\n"
            f"Or check available models: 'ollama list'\n\n"
            f"Raw error: {body}"
        )
    except Exception as e:
        return f"Ollama error: {e}"


def _call_openai(prompt, base_url, model, api_key="", extra_headers=None):
    messages = [{"role": "user", "content": prompt}]
    url = f"{base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if extra_headers:
        headers.update(extra_headers)
    body = json.dumps({"model": model, "messages": messages}).encode()
    try:
        req = urllib.request.Request(url, body, headers)
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode()
        except Exception:
            pass
        return (
            f"API Error {e.code}: {e.reason}\n\n"
            f"Provider: {base_url}\n"
            f"Model: {model}\n\n"
            f"Response: {err_body[:500]}\n\n"
            f"Fix: Check that the model '{model}' is loaded in your provider."
        )
    except urllib.error.URLError as e:
        return (
            f"Connection Error: Cannot reach {base_url}\n\n"
            f"Fix: Make sure your AI provider is running.\n"
            f"  - Ollama: ollama serve\n"
            f"  - Jan: Open Jan app\n"
            f"  - LM Studio: Start server in LM Studio"
        )
    except Exception as e:
        return f"API error: {e}"


def _call_gemini(prompt, model, api_key):
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    payload = {
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 2048, "temperature": 0.7},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    try:
        req = urllib.request.Request(
            url, json.dumps(payload).encode(), {"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())["candidates"][0]["content"]["parts"][0][
                "text"
            ]
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode()
        except Exception:
            pass
        return (
            f"Gemini API Error {e.code}: {e.reason}\n\n"
            f"Model: {model}\n\n"
            f"Response: {err_body[:500]}\n\n"
            f"Fix: Check your GEMINI_API_KEY and model name."
        )
    except Exception as e:
        return f"Gemini error: {e}"


def probe_provider(provider):
    try:
        if provider == "ollama":
            r = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
            return True, [m["name"] for m in json.loads(r.read()).get("models", [])]
        elif provider == "jan":
            r = urllib.request.urlopen("http://localhost:1337/v1/models", timeout=3)
            return True, [m["id"] for m in json.loads(r.read()).get("data", [])]
        elif provider == "lmstudio":
            r = urllib.request.urlopen("http://localhost:1234/v1/models", timeout=3)
            return True, [m["id"] for m in json.loads(r.read()).get("data", [])]
        elif provider in ("groq", "gemini", "openrouter", "qwen"):
            key_map = {
                "groq": "GROQ_API_KEY",
                "gemini": "GEMINI_API_KEY",
                "openrouter": "OPENROUTER_API_KEY",
                "qwen": "QWEN_API_KEY",
            }
            return bool(os.getenv(key_map.get(provider, ""), "")), ALL_MODELS.get(
                provider, []
            )
        return False, []
    except Exception:
        return False, []


class VoiceEngine:
    def __init__(self):
        self._available = False
        self._engine = None
        if sys.platform == "win32":
            try:
                import win32com.client

                self._engine = win32com.client.Dispatch("SAPI.SpVoice")
                self._available = True
            except Exception:
                self._available = False

    def speak(self, text):
        if not self._available:
            return
        clean = re.sub(r"[#*`_~\[\](){}]", "", text)[:500]
        try:
            if self._engine:
                self._engine.Speak(clean)
            else:
                escaped = clean.replace('"', '\\"')
                subprocess.run(
                    [
                        "powershell",
                        "-Command",
                        f'Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate = 1; $s.Speak("{escaped}")',
                    ],
                    capture_output=True,
                    timeout=30,
                )
        except Exception:
            pass


class BabaDesktop(tk.Tk):
    def __init__(self):
        global CURRENT_THEME, T
        super().__init__()
        self.title("BABA DESKTOP v12 ULTIMATE")
        self.geometry("1400x900")
        self.minsize(1000, 700)

        self.settings = Settings.load()
        saved_theme = (getattr(self.settings, "theme", "") or "").strip()
        theme_aliases = {"dark": "Midnight", "light": "White"}
        resolved_theme = theme_aliases.get(saved_theme.lower(), saved_theme)
        if resolved_theme not in THEMES:
            resolved_theme = "Midnight"
        CURRENT_THEME = resolved_theme
        T = THEMES[CURRENT_THEME]
        self.configure(bg=T["bg"])

        self.provider_status = {}
        self.provider_models_live = {}
        self.chat_history = []
        self.voice_enabled = tk.BooleanVar(
            value=bool(getattr(self.settings, "voice_enabled", False))
        )
        self.current_provider = tk.StringVar(value="ollama")
        self.current_model = tk.StringVar(value=ALL_MODELS["ollama"][0])
        self.active_panel = "chat"
        self.panels = {}
        self.log_queue = queue.Queue()
        self.last_response = ""
        self._sidebar_btns = {}
        self._sidebar_hover_bindings = {}
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="baba_worker"
        )

        self._init_backend()
        self._build()
        self._log_strip()
        self.after(100, self._process_log_queue)
        self.after(500, self._auto_probe)
        self.after(30000, self._auto_probe)

    def _init_backend(self):
        self.brain = None
        self.pool = None
        self.tools = None
        self.vision = None
        self.agents = None
        self.money = None
        self.pc = None
        self.apps = None
        self.memory = None
        self.dispatcher = None
        self.scheduler = None
        self.cowork = None
        self.devtools = None
        self.meetings = None
        self.chrome = None
        self.claws = None
        self.tool_builder = None
        self.voice = VoiceEngine()

        try:
            self.brain = BrainIndex(self.settings.brain_db_path)
            self.log_queue.put(("log", "Brain Index initialized"))
        except Exception as e:
            self.log_queue.put(("log", f"Brain Index init failed: {e}"))

        try:
            cfg = self.settings.providers if getattr(self.settings, "providers", None) else {
                "groq": {"api_key_env": "GROQ_API_KEY"},
                "gemini": {"api_key_env": "GEMINI_API_KEY"},
                "openrouter": {"api_key_env": "OPENROUTER_API_KEY"},
                "qwen": {"api_key_env": "QWEN_API_KEY"},
            }
            self.pool = ProviderPool(cfg)
            self.log_queue.put(("log", "Provider Pool initialized"))
        except Exception as e:
            self.log_queue.put(("log", f"Provider Pool init failed: {e}"))

        try:
            self.tools = ToolRegistry(self.brain) if self.brain else ToolRegistry()
            self.log_queue.put(("log", "Tool Registry initialized"))
        except Exception as e:
            self.log_queue.put(("log", f"Tool Registry init failed: {e}"))

        try:
            self.vision = (
                VisionPipeline(self.pool, self.brain, self.settings)
                if self.pool
                else None
            )
            self.log_queue.put(("log", "Vision Pipeline initialized"))
        except Exception as e:
            self.log_queue.put(("log", f"Vision Pipeline init failed: {e}"))

        try:
            if self.brain and self.pool and self.tools:
                self.agents = AgentOrchestrator(
                    self.pool, self.brain, self.tools, self.vision
                )
                self.log_queue.put(("log", "Agent Orchestrator initialized"))
        except Exception as e:
            self.log_queue.put(("log", f"Agent Orchestrator init failed: {e}"))

        try:
            if self.brain and self.pool:
                self.money = MoneyEngine(self.brain, self.pool)
                self.log_queue.put(("log", "Money Engine initialized"))
        except Exception as e:
            self.log_queue.put(("log", f"Money Engine init failed: {e}"))

        try:
            self.pc = PCBridge(port=self.settings.pc_bridge_port)
            self.log_queue.put(("log", "PC Bridge initialized"))
        except Exception as e:
            self.log_queue.put(("log", f"PC Bridge init failed: {e}"))

        try:
            self.apps = AppBridge(self.settings)
            self.log_queue.put(("log", "App Bridge initialized"))
        except Exception as e:
            self.log_queue.put(("log", f"App Bridge init failed: {e}"))

        try:
            self.memory = Memory(self.settings.memory_dir)
            self.log_queue.put(("log", "Memory initialized"))
        except Exception as e:
            self.log_queue.put(("log", f"Memory init failed: {e}"))

        try:
            if (
                self.brain
                and self.agents
                and self.pc
                and self.apps
                and self.tools
                and self.pool
            ):
                self.dispatcher = Dispatcher(
                    self.brain, self.agents, self.pc, self.apps, self.tools, self.pool
                )
                self.dispatcher.start_worker()
                self.log_queue.put(("log", "Dispatcher initialized + worker started"))
        except Exception as e:
            self.log_queue.put(("log", f"Dispatcher init failed: {e}"))

        try:
            self.scheduler = (
                Scheduler(self.dispatcher, self.settings) if self.dispatcher else None
            )
            if self.scheduler:
                self.scheduler.start()
                self.log_queue.put(("log", "Scheduler initialized + loop started"))
        except Exception as e:
            self.log_queue.put(("log", f"Scheduler init failed: {e}"))

        try:
            if (
                self.agents
                and self.pool
                and self.brain
                and self.tools
                and self.pc
                and self.apps
            ):
                self.cowork = Cowork(
                    self.agents, self.pool, self.brain, self.tools, self.pc, self.apps
                )
                self.log_queue.put(("log", "Cowork initialized"))
        except Exception as e:
            self.log_queue.put(("log", f"Cowork init failed: {e}"))

        try:
            self.devtools = DevTools()
            self.log_queue.put(("log", "DevTools initialized"))
        except Exception as e:
            self.log_queue.put(("log", f"DevTools init failed: {e}"))

        try:
            if self.pool and self.brain:
                self.meetings = MeetingIntelligence(
                    self.pool, self.brain, self.settings
                )
                self.log_queue.put(("log", "Meeting Intelligence initialized"))
        except Exception as e:
            self.log_queue.put(("log", f"Meeting Intelligence init failed: {e}"))

        try:
            if self.dispatcher and self.brain and self.pool:
                self.chrome = ChromeConnector(self.dispatcher, self.brain, self.pool)
                self.log_queue.put(("log", "Chrome Connector initialized"))
        except Exception as e:
            self.log_queue.put(("log", f"Chrome Connector init failed: {e}"))

        try:
            self.claws = ClawInstaller(self.settings.claws_dir)
            self.log_queue.put(("log", "Claw Installer initialized"))
        except Exception as e:
            self.log_queue.put(("log", f"Claw Installer init failed: {e}"))

        try:
            if self.pool and self.brain:
                self.tool_builder = ToolBuilder(self.pool, self.brain, self.settings)
                self.log_queue.put(("log", "Tool Builder initialized"))
        except Exception as e:
            self.log_queue.put(("log", f"Tool Builder init failed: {e}"))

        self.log_queue.put(("log", "All backend services initialized"))

    def _build(self):
        self._header()
        self._sidebar()
        self._main_area()

    def _header(self):
        hdr = tk.Frame(self, bg=T["header_bg"], height=56)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)
        tk.Label(
            hdr,
            text="\u26a1 BABA DESKTOP",
            font=(FF, 16, "bold"),
            bg=T["header_bg"],
            fg=T["accent"],
        ).pack(side="left", padx=16, pady=8)
        tk.Label(
            hdr, text="v12 ULTIMATE", font=(FF, 9), bg=T["header_bg"], fg=T["text_sec"]
        ).pack(side="left", padx=(0, 20), pady=12)
        pf = tk.Frame(hdr, bg=T["header_bg"])
        pf.pack(side="left", padx=20)
        tk.Label(
            pf, text="Provider:", font=FONT_SM, bg=T["header_bg"], fg=T["text_sec"]
        ).pack(side="left", padx=(0, 4))
        cb = ttk.Combobox(
            pf,
            textvariable=self.current_provider,
            values=list(ALL_MODELS.keys()),
            width=12,
            font=FONT_SM,
            state="readonly",
        )
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", self._on_provider_change)
        self.model_cb = ttk.Combobox(
            pf,
            textvariable=self.current_model,
            values=ALL_MODELS["ollama"],
            width=22,
            font=FONT_SM,
            state="readonly",
        )
        self.model_cb.pack(side="left", padx=(8, 0))
        sf = tk.Frame(hdr, bg=T["header_bg"])
        sf.pack(side="right", padx=16)
        self.status_lbl = tk.Label(
            sf, text="Probing...", font=FONT_SM, bg=T["header_bg"], fg=T["yellow"]
        )
        self.status_lbl.pack(side="right", padx=8)
        tk.Button(
            sf,
            text="\u21bb Probe",
            font=FONT_SM,
            bg=T["accent"],
            fg="white",
            bd=0,
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._auto_probe,
        ).pack(side="right", padx=4)
        tf = tk.Frame(hdr, bg=T["header_bg"])
        tf.pack(side="right", padx=16)
        tk.Label(
            tf, text="Theme:", font=FONT_SM, bg=T["header_bg"], fg=T["text_sec"]
        ).pack(side="left", padx=(0, 4))
        tcb = ttk.Combobox(
            tf, values=list(THEMES.keys()), width=10, font=FONT_SM, state="readonly"
        )
        tcb.set(CURRENT_THEME)
        tcb.pack(side="left")
        tcb.bind("<<ComboboxSelected>>", lambda e: self._set_theme(tcb.get()))
        tk.Checkbutton(
            hdr,
            text="\U0001f50a Voice",
            variable=self.voice_enabled,
            bg=T["header_bg"],
            fg=T["text"],
            selectcolor=T["panel2"],
            font=FONT_SM,
        ).pack(side="right", padx=16)

    def _sidebar(self):
        outer = tk.Frame(self, bg=T["sidebar_bg"], width=200)
        outer.pack(side="left", fill="y")
        outer.pack_propagate(False)
        canvas = tk.Canvas(outer, bg=T["sidebar_bg"], bd=0, highlightthickness=0)
        vsb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=T["sidebar_bg"])
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("all", width=e.width))

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.unbind_all("<MouseWheel>")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        items = [
            ("chat", "\U0001f4ac", "Chat"),
            ("cowork", "\U0001f916", "Cowork"),
            ("agents", "\U0001f465", "Agents"),
            ("brain", "\U0001f9e0", "Brain"),
            ("import", "\U0001f4e5", "Import"),
            ("money", "\U0001f4b0", "Money"),
            ("pc", "\U0001f5a5", "PC Control"),
            ("providers", "\U0001f50c", "Providers"),
            ("apps", "\U0001f4f1", "Apps"),
            ("social", "\U0001f310", "Social"),
            ("browser", "\U0001f30d", "Browser"),
            ("vision", "\U0001f441", "Vision"),
            ("scheduler", "\u23f0", "Scheduler"),
            ("meetings", "\U0001f3a4", "Meetings"),
            ("devtools", "\U0001f6e0", "DevTools"),
            ("claws", "\U0001f980", "Claws"),
            ("evolve", "\U0001f9ec", "Self-Evolving"),
            ("research", "\U0001f50d", "Research"),
            ("settings", "\u2699", "Settings"),
        ]
        for pid, icon, label in items:
            btn = tk.Button(
                inner,
                text=f"  {icon}  {label}",
                font=FONT,
                bg=T["sidebar_bg"],
                fg=T["sidebar_text"],
                bd=0,
                relief="flat",
                anchor="w",
                padx=16,
                pady=8,
                cursor="hand2",
                command=lambda p=pid: self._switch_panel(p),
            )
            btn.pack(fill="x", padx=2, pady=1)
            self._sidebar_btns[pid] = btn
        self._sidebar_btns["chat"].configure(bg=T["sidebar_hover"], fg=T["accent"])

    def _switch_panel(self, pid):
        for p, btn in self._sidebar_btns.items():
            btn.configure(bg=T["sidebar_bg"], fg=T["sidebar_text"])
        if pid in self._sidebar_btns:
            self._sidebar_btns[pid].configure(bg=T["sidebar_hover"], fg=T["accent"])
        if pid in self.panels:
            self.panels[pid].tkraise()
        else:
            builder = getattr(self, f"_panel_{pid}", None)
            if builder:
                builder()

    def _main_area(self):
        self.main = tk.Frame(self, bg=T["bg"])
        self.main.pack(fill="both", expand=True, side="top")

    def _clear_panel(self, pid):
        if pid in self.panels:
            self.panels[pid].destroy()
            del self.panels[pid]

    def _on_provider_change(self, *_):
        p = self.current_provider.get()
        models = self.provider_models_live.get(p) or ALL_MODELS.get(p, [])
        self.model_cb["values"] = models
        if models and self.current_model.get() not in models:
            self.current_model.set(models[0])

    def _auto_probe(self):
        def _do():
            status = {}
            for prov in ["ollama", "jan", "lmstudio", "groq", "gemini", "openrouter", "qwen"]:
                online, _ = probe_provider(prov)
                status[prov] = online
            self.log_queue.put(("probe_done", status))
            if self.pool:
                try:
                    detected = self.pool.detect_all()
                    live_catalog = {}
                    for prov, meta in detected.items():
                        if isinstance(meta, dict):
                            if "online" in meta:
                                status[prov] = bool(meta.get("online"))
                            models = meta.get("models")
                            if isinstance(models, list) and models:
                                live_catalog[prov] = models
                    self.log_queue.put(("provider_catalog", live_catalog))
                    self.log_queue.put(("probe_done", status))
                except Exception:
                    pass

        threading.Thread(target=_do, daemon=True).start()

    def _log(self, msg):
        self.log_queue.put(("log", msg))

    def _process_log_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                if item[0] == "status":
                    self.status_lbl.configure(text=item[1])
                elif item[0] == "log":
                    self.log_lbl.configure(
                        text=f"[{datetime.now(UTC).strftime('%H:%M:%S')}] {item[1]}"
                    )
                elif item[0] == "probe_done":
                    self.provider_status = item[1]
                    online = [p for p, s in item[1].items() if s]
                    self.status_lbl.configure(
                        text=f"\u25cf {', '.join(online)}"
                        if online
                        else "\u25cb No providers online",
                        fg=T["green"] if online else T["red"],
                    )
                    if "providers" in self.panels:
                        self._refresh_providers()
                elif item[0] == "provider_catalog":
                    self.provider_models_live = item[1] or {}
                    self._on_provider_change()
                    if "providers" in self.panels:
                        self._refresh_providers()
                elif item[0] == "apps_status":
                    if hasattr(self, "apps_status") and self.apps_status.winfo_exists():
                        self.apps_status.configure(state="normal")
                        self.apps_status.delete("1.0", "end")
                        self.apps_status.insert("end", item[1])
                        self.apps_status.configure(state="disabled")
                elif item[0] == "chat_reply":
                    self._chat_display_reply(item[1])
                elif item[0] == "cowork_result":
                    self._cowork_display(item[1])
                elif item[0] == "agent_result":
                    self._agent_display(item[1], item[2])
                elif item[0] == "money_result":
                    self._money_display(item[1])
                elif item[0] == "vision_result":
                    self._vision_display(item[1])
                elif item[0] == "meeting_result":
                    self._meeting_display(item[1])
                elif item[0] == "research_result":
                    self._research_display(item[1])
                elif item[0] == "scheduler_result":
                    self._scheduler_display(item[1])
                elif item[0] == "devtools_result":
                    self._devtools_display(item[1])
                elif item[0] == "claw_result":
                    self._claw_display(item[1])
                elif item[0] == "tool_builder_result":
                    self._tool_builder_display(item[1])
        except queue.Empty:
            pass
        self.after(100, self._process_log_queue)

    def _log_strip(self):
        log = tk.Frame(self, bg=T["header_bg"], height=28)
        log.pack(fill="x", side="bottom")
        log.pack_propagate(False)
        self.log_lbl = tk.Label(
            log,
            text="BABA v12 ULTIMATE | Ready",
            font=(FF, 8),
            bg=T["header_bg"],
            fg=T["muted"],
        )
        self.log_lbl.pack(side="left", padx=12)

    def _set_theme(self, name):
        global T, CURRENT_THEME
        CURRENT_THEME = name
        T = THEMES[name]
        for w in self.winfo_children():
            w.destroy()
        self.configure(bg=T["bg"])
        self._sidebar_btns.clear()
        self.panels.clear()
        self._build()
        self._log_strip()
        self.after(100, self._process_log_queue)
        self._panel_chat()
        self.settings.theme = name
        self.settings.voice_enabled = bool(self.voice_enabled.get())
        self.settings.save()

    # ==================== CHAT ====================
    def _panel_chat(self):
        self._clear_panel("chat")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["chat"] = frame
        tk.Label(
            frame,
            text="\U0001f4ac Chat with Baba AI",
            font=FONT_XL,
            bg=T["bg"],
            fg=T["accent"],
        ).pack(pady=12)
        self.chat_display = scrolledtext.ScrolledText(
            frame,
            bg=T["panel"],
            fg=T["text"],
            font=FONT_CHAT,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            state="disabled",
        )
        self.chat_display.pack(fill="both", expand=True, padx=16, pady=4)
        for tag, fg, font_cfg in [
            ("user", T["accent"], (FF, 10, "bold")),
            ("ai", T["text"], FONT_CHAT),
            ("system", T["muted"], (FF, 9, "italic")),
            ("error", T["red"], FONT_CHAT),
        ]:
            self.chat_display.tag_config(tag, foreground=fg, font=font_cfg)
        self._chat_append(
            "system",
            "Welcome to Baba Desktop v12 ULTIMATE. Connected to Brain Index, Provider Pool, Agent Orchestrator, Vision Pipeline, PC Bridge, App Bridge, Memory, Scheduler, and more.\n\n"
            "QUICK START:\n"
            "1. Click 'Probe' in the top bar to check which AI providers are online\n"
            "2. Select an ONLINE provider from the dropdown (green dot = online)\n"
            "3. Select a model that is loaded in that provider\n"
            "4. Type anything or use slash commands:\n"
            "   /legal, /acct, /supplier, /deals, /content, /comms, /pa, /money, /cowork, /vision, /brain, /meeting",
        )
        inf = tk.Frame(frame, bg=T["bg"])
        inf.pack(fill="x", padx=16, pady=8)
        inf.columnconfigure(0, weight=1)
        self.chat_entry = tk.Text(
            inf,
            bg=T["input_bg"],
            fg=T["input_text"],
            font=FONT,
            height=3,
            wrap="word",
            bd=0,
            padx=10,
            pady=8,
            insertbackground=T["accent"],
        )
        self.chat_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.chat_entry.bind("<Return>", self._chat_send)
        tk.Button(
            inf,
            text="Send",
            font=(FF, 11, "bold"),
            bg=T["accent"],
            fg="white",
            bd=0,
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._chat_send,
        ).grid(row=0, column=1)
        cf = tk.Frame(inf, bg=T["bg"])
        cf.grid(row=1, column=0, columnspan=2, sticky="w", pady=4)
        for txt, cmd in [
            ("Clear", self._chat_clear),
            ("Copy", self._chat_copy),
            ("\U0001f50a Speak", self._chat_speak),
        ]:
            tk.Button(
                cf,
                text=txt,
                font=FONT_SM,
                bg=T["panel2"],
                fg=T["text"],
                bd=0,
                relief="flat",
                padx=10,
                pady=4,
                cursor="hand2",
                command=cmd,
            ).pack(side="left", padx=2)

    def _chat_send(self, event=None):
        text = self.chat_entry.get("1.0", "end").strip()
        if not text:
            return
        if event and event.keysym == "Return" and not event.state & 0x4:
            if text.endswith("\n"):
                text = text[:-1]
                if not text:
                    return
        self.chat_entry.delete("1.0", "end")
        self._chat_append("user", f"You: {text}")
        self.chat_history.append({"role": "user", "content": text})

        if text.startswith("/"):
            self._handle_slash_command(text)
            return

        self._chat_append("system", "Thinking...")
        prov = self.current_provider.get()
        model = self.current_model.get()

        def _do():
            reply = _call_ai_sync(
                text, provider=prov, model=model, history=self.chat_history[-10:]
            )
            self.log_queue.put(("chat_reply", reply))
            if self.memory:
                try:
                    self.memory.remember(text, category="chat")
                except Exception:
                    pass

        threading.Thread(target=_do, daemon=True).start()

    def _handle_slash_command(self, text):
        parts = text.split(" ", 1)
        cmd = parts[0].lower().lstrip("/")
        arg = parts[1].strip() if len(parts) > 1 else ""
        prov = self.current_provider.get()
        model = self.current_model.get()

        agent_map = {
            "legal": "legal",
            "acct": "acct",
            "supplier": "supplier",
            "deals": "deals",
            "content": "content",
            "comms": "comms",
            "pa": "pa",
        }
        if cmd in agent_map:
            task = arg or f"Run full {cmd} analysis"
            self._chat_append("system", f"Running {cmd} agent...")

            def _do():
                if self.agents:
                    try:
                        reply = self.agents.run_sync(agent_map[cmd], task)
                    except Exception as e:
                        reply = _call_ai_sync(
                            f"You are a {cmd} agent. Task: {task}. Provide detailed, actionable results.",
                            provider=prov,
                            model=model,
                            system=f"You are a {cmd} specialist. Be concise and actionable.",
                        )
                else:
                    reply = _call_ai_sync(
                        f"You are a {cmd} agent. Task: {task}. Provide detailed, actionable results.",
                        provider=prov,
                        model=model,
                    )
                self.log_queue.put(("agent_result", cmd, reply))

            threading.Thread(target=_do, daemon=True).start()
            return

        if cmd == "money":
            self._chat_append("system", "Running Money Engine analysis...")

            def _do():
                if self.money:
                    try:
                        result = self.money.run_sync()
                        reply = result.get("analysis", "No analysis available")
                    except Exception as e:
                        reply = f"Money Engine error: {e}"
                else:
                    reply = _call_ai_sync(
                        "Analyse this business for savings and income opportunities. Be specific and actionable.",
                        provider=prov,
                        model=model,
                    )
                self.log_queue.put(("money_result", reply))

            threading.Thread(target=_do, daemon=True).start()
            return

        if cmd == "cowork":
            if not arg:
                self._chat_append("system", "Usage: /cowork <describe your goal>")
                return
            self._chat_append("system", f"Starting Cowork: {arg}")

            def _do():
                if self.cowork:
                    try:
                        session = self.cowork.run_sync(arg)
                        reply = (
                            session.final_result
                            if session.final_result
                            else "Cowork session completed"
                        )
                    except Exception as e:
                        reply = f"Cowork error: {e}"
                else:
                    reply = _call_ai_sync(
                        f"Break this goal into clear numbered steps:\n\nGoal: {arg}",
                        provider=prov,
                        model=model,
                    )
                self.log_queue.put(("cowork_result", reply))

            threading.Thread(target=_do, daemon=True).start()
            return

        if cmd == "vision":
            self._chat_append("system", "Open the Vision panel to analyse images")
            return

        if cmd == "brain":
            self._chat_append("system", "Opening Brain Index...")
            if self.brain:
                stats = self.brain.stats()
                self._chat_append(
                    "ai",
                    f"Brain Index Stats:\n- Total: {stats.get('total', 0)}\n- Emails: {stats.get('emails', 0)}\n- Docs: {stats.get('docs', 0)}\n- High Risk: {stats.get('high_risk', 0)}\n- Renewals: {stats.get('with_renewals', 0)}",
                )
            return

        if cmd == "meeting":
            self._chat_append(
                "system", "Open the Meetings panel to process transcripts"
            )
            return

        self._chat_append(
            "system",
            f"Unknown command: /{cmd}. Available: /legal, /acct, /supplier, /deals, /content, /comms, /pa, /money, /cowork, /vision, /brain, /meeting",
        )

    def _chat_append(self, tag, text):
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", text + "\n\n", tag)
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def _chat_display_reply(self, reply):
        self.chat_display.configure(state="normal")
        idx = self.chat_display.search("Thinking...", "1.0", "end")
        if idx:
            line = idx.split(".")[0]
            self.chat_display.delete(f"{line}.0", f"{line}.end+1c")
        self.chat_display.insert("end", f"Baba AI:\n{reply}\n", "ai")
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")
        self.last_response = reply
        self.chat_history.append({"role": "assistant", "content": reply})
        if self.voice_enabled.get():
            threading.Thread(
                target=self.voice.speak, args=(reply,), daemon=True
            ).start()

    def _chat_clear(self):
        self.chat_history.clear()
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.chat_display.configure(state="disabled")
        self.last_response = ""
        self._chat_append("system", "Chat cleared.")

    def _chat_copy(self):
        if self.last_response:
            self.clipboard_clear()
            self.clipboard_append(self.last_response)
            self._log("Copied to clipboard")

    def _chat_speak(self):
        if self.last_response:
            threading.Thread(
                target=self.voice.speak, args=(self.last_response,), daemon=True
            ).start()
            self._log("Speaking...")

    # ==================== COWORK ====================
    def _panel_cowork(self):
        self._clear_panel("cowork")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["cowork"] = frame
        tk.Label(
            frame,
            text="\U0001f916 Cowork - Autonomous Agent",
            font=FONT_XL,
            bg=T["bg"],
            fg=T["accent"],
        ).pack(pady=12)
        tk.Label(
            frame,
            text="Describe what you want. Baba will plan and execute autonomously.",
            font=FONT,
            bg=T["bg"],
            fg=T["text_sec"],
        ).pack()
        self.cowork_entry = tk.Text(
            frame,
            bg=T["input_bg"],
            fg=T["input_text"],
            font=FONT,
            height=4,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
        )
        self.cowork_entry.pack(fill="x", padx=20, pady=8)
        tk.Button(
            frame,
            text="Start Cowork",
            font=(FF, 11, "bold"),
            bg=T["accent"],
            fg="white",
            bd=0,
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._cowork_run,
        ).pack(pady=4)
        self.cowork_output = scrolledtext.ScrolledText(
            frame,
            bg=T["panel"],
            fg=T["text"],
            font=FONT_CHAT,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            state="disabled",
        )
        self.cowork_output.pack(fill="both", expand=True, padx=20, pady=8)

    def _cowork_run(self):
        goal = self.cowork_entry.get("1.0", "end").strip()
        if not goal:
            return
        self.cowork_output.configure(state="normal")
        self.cowork_output.delete("1.0", "end")
        self.cowork_output.insert("end", f"Goal: {goal}\n\nPlanning...\n")
        self.cowork_output.configure(state="disabled")

        def _do():
            if self.cowork:
                try:
                    session = self.cowork.run_sync(goal)
                    reply = (
                        session.final_result
                        if session.final_result
                        else "Cowork session completed"
                    )
                except Exception as e:
                    reply = f"Cowork error: {e}\n\n{traceback.format_exc()}"
            else:
                reply = _call_ai_sync(
                    f"Break this goal into clear numbered steps:\n\nGoal: {goal}",
                    provider=self.current_provider.get(),
                    model=self.current_model.get(),
                )
            self.log_queue.put(("cowork_result", reply))

        threading.Thread(target=_do, daemon=True).start()

    def _cowork_display(self, result):
        self.cowork_output.configure(state="normal")
        self.cowork_output.delete("1.0", "end")
        self.cowork_output.insert("end", result)
        self.cowork_output.configure(state="disabled")
        self._log("Cowork completed")

    # ==================== AGENTS ====================
    def _panel_agents(self):
        self._clear_panel("agents")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["agents"] = frame
        tk.Label(
            frame,
            text="\U0001f465 Domain Agents",
            font=FONT_XL,
            bg=T["bg"],
            fg=T["accent"],
        ).pack(pady=12)
        canvas = tk.Canvas(frame, bg=T["bg"], bd=0, highlightthickness=0)
        vsb = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=T["bg"])
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.unbind_all("<MouseWheel>")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        agents_to_show = list(AGENTS_LIST)
        if self.agents:
            try:
                dynamic = []
                for a in self.agents.list_agents():
                    aid = a.get("id", "")
                    dynamic.append(
                        {
                            "id": aid,
                            "icon": AGENT_ICONS.get(aid, "\U0001f9e0"),
                            "name": a.get("name", aid),
                            "tasks": a.get("tasks", []),
                        }
                    )
                if dynamic:
                    agents_to_show = dynamic
            except Exception:
                pass

        for agent in agents_to_show:
            card = tk.Frame(
                inner,
                bg=T["card"],
                highlightbackground=T["border"],
                highlightthickness=1,
            )
            card.pack(fill="x", padx=12, pady=4)
            tk.Label(
                card,
                text=f"{agent['icon']} {agent['name']}",
                font=FONT_LG,
                bg=T["card"],
                fg=T["text"],
            ).pack(anchor="w", padx=12, pady=(8, 4))
            for task in agent["tasks"]:
                tk.Button(
                    card,
                    text=f"\u25b6 {task}",
                    font=FONT_SM,
                    bg=T["panel2"],
                    fg=T["text"],
                    bd=0,
                    relief="flat",
                    anchor="w",
                    padx=12,
                    pady=4,
                    cursor="hand2",
                    command=lambda a=agent["id"], t=task: self._run_agent(a, t),
                ).pack(fill="x", padx=12, pady=1)

    def _run_agent(self, agent_id, task):
        prov = self.current_provider.get()
        model = self.current_model.get()
        self._log(f"Running agent: {agent_id} - {task}")

        def _do():
            if self.agents:
                try:
                    reply = self.agents.run_sync(agent_id, task)
                except Exception as e:
                    reply = f"Agent error: {e}"
            else:
                reply = _call_ai_sync(
                    f"You are a {agent_id} agent. Task: {task}. Provide detailed, actionable results.",
                    provider=prov,
                    model=model,
                )
            self.log_queue.put(("agent_result", agent_id, reply))

        threading.Thread(target=_do, daemon=True).start()

    def _agent_display(self, agent_id, result):
        self._switch_panel("chat")
        self._chat_append("system", f"Agent Results: {agent_id}")
        self._chat_append("ai", result)
        self.last_response = result
        self._log(f"Agent {agent_id} completed")

    # ==================== BRAIN ====================
    def _panel_brain(self):
        self._clear_panel("brain")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["brain"] = frame
        tk.Label(
            frame,
            text="\U0001f9e0 Brain Index",
            font=FONT_XL,
            bg=T["bg"],
            fg=T["accent"],
        ).pack(pady=12)
        sf = tk.Frame(frame, bg=T["bg"])
        sf.pack(fill="x", padx=20, pady=4)
        if self.brain:
            stats = self.brain.stats()
            for label, val in [
                ("Total", stats.get("total", 0)),
                ("Emails", stats.get("emails", 0)),
                ("Docs", stats.get("docs", 0)),
                ("High Risk", stats.get("high_risk", 0)),
                ("Renewals", stats.get("with_renewals", 0)),
            ]:
                chip = tk.Frame(
                    sf,
                    bg=T["card"],
                    highlightbackground=T["border"],
                    highlightthickness=1,
                )
                chip.pack(side="left", padx=8, pady=4)
                tk.Label(
                    chip,
                    text=str(val),
                    bg=T["card"],
                    fg=T["accent"],
                    font=(FF, 20, "bold"),
                ).pack(padx=14, pady=(6, 0))
                tk.Label(
                    chip, text=label.upper(), bg=T["card"], fg=T["muted"], font=(FF, 7)
                ).pack(pady=(0, 6))
        sef = tk.Frame(frame, bg=T["bg"])
        sef.pack(fill="x", padx=20, pady=8)
        sef.columnconfigure(0, weight=1)
        self.brain_search_var = tk.StringVar()
        tk.Entry(
            sef,
            textvariable=self.brain_search_var,
            bg=T["input_bg"],
            fg=T["input_text"],
            font=FONT,
            bd=0,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=6)
        tk.Button(
            sef,
            text="Search",
            font=FONT_SM,
            bg=T["accent"],
            fg="white",
            bd=0,
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._brain_search,
        ).pack(side="left")
        self.brain_results = scrolledtext.ScrolledText(
            frame,
            bg=T["panel"],
            fg=T["text"],
            font=FONT_CHAT,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            state="disabled",
        )
        self.brain_results.pack(fill="both", expand=True, padx=20, pady=4)
        self._brain_search()

    def _brain_search(self):
        q = self.brain_search_var.get().strip()
        self.brain_results.configure(state="normal")
        self.brain_results.delete("1.0", "end")
        if self.brain:
            results = self.brain.search(q) if q else self.brain.all(limit=20)
            if not results:
                self.brain_results.insert("end", "No entries found.\n", "system")
            for r in results:
                title = r.get("summary", r.get("title", "Untitled"))
                self.brain_results.insert("end", f"{title}\n")
                self.brain_results.insert(
                    "end",
                    f"  {r.get('type', '')} | {r.get('counterparty', '')} | {r.get('date', '')}\n",
                )
                content = r.get("raw_text", r.get("content", ""))
                self.brain_results.insert("end", f"  {str(content)[:300]}\n\n")
        else:
            self.brain_results.insert("end", "Brain Index not available.\n")
        self.brain_results.configure(state="disabled")

    # ==================== IMPORT ====================
    def _panel_import(self):
        self._clear_panel("import")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["import"] = frame
        tk.Label(
            frame,
            text="\U0001f4e5 Import to Brain",
            font=FONT_XL,
            bg=T["bg"],
            fg=T["accent"],
        ).pack(pady=12)
        bf = tk.Frame(frame, bg=T["bg"])
        bf.pack(fill="x", padx=20, pady=4)
        tk.Button(
            bf,
            text="Select Files",
            font=(FF, 11, "bold"),
            bg=T["accent"],
            fg="white",
            bd=0,
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._import_files,
        ).pack(side="left", padx=4)
        tk.Button(
            bf,
            text="Select Folder",
            font=(FF, 11, "bold"),
            bg=T["panel2"],
            fg=T["accent"],
            bd=0,
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._import_folder,
        ).pack(side="left", padx=4)
        self.import_log = scrolledtext.ScrolledText(
            frame,
            bg=T["panel"],
            fg=T["text"],
            font=FONT_CHAT,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            state="disabled",
        )
        self.import_log.pack(fill="both", expand=True, padx=20, pady=8)

    def _import_files(self):
        files = filedialog.askopenfilenames(
            filetypes=[
                ("All", "*.*"),
                ("Text", "*.txt"),
                ("PDF", "*.pdf"),
                ("CSV", "*.csv"),
            ]
        )
        if not files:
            return
        self._do_import(list(files))

    def _import_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        files = []
        for ext in ("*.txt", "*.pdf", "*.csv", "*.md", "*.json", "*.html"):
            files.extend(Path(folder).rglob(ext))
        self._do_import([str(f) for f in files])

    def _do_import(self, files):
        self.import_log.configure(state="normal")
        self.import_log.delete("1.0", "end")
        self.import_log.insert("end", f"Importing {len(files)} files...\n\n")
        self.import_log.configure(state="disabled")
        count = 0
        errors = 0
        for fp in files:
            try:
                content = Path(fp).read_text(errors="replace")[:50000]
                if self.brain:
                    self.brain.ingest(
                        {
                            "source": "import",
                            "type": "personal",
                            "tags": ["imported"],
                            "summary": Path(fp).name,
                            "raw_text": content,
                            "raw_path": fp,
                        }
                    )
                count += 1
                self.import_log.configure(state="normal")
                self.import_log.insert("end", f"Imported: {Path(fp).name}\n")
                self.import_log.configure(state="disabled")
            except Exception as e:
                errors += 1
                self.import_log.configure(state="normal")
                self.import_log.insert("end", f"Error: {Path(fp).name} - {e}\n")
                self.import_log.configure(state="disabled")
        self.import_log.configure(state="normal")
        self.import_log.insert("end", f"\nDone: {count} imported, {errors} errors\n")
        self.import_log.configure(state="disabled")
        self._log(f"Imported {count} files, {errors} errors")

    # ==================== MONEY ====================
    def _panel_money(self):
        self._clear_panel("money")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["money"] = frame
        tk.Label(
            frame,
            text="\U0001f4b0 Money Engine",
            font=FONT_XL,
            bg=T["bg"],
            fg=T["accent"],
        ).pack(pady=12)
        bf = tk.Frame(frame, bg=T["bg"])
        bf.pack(fill="x", padx=20, pady=4)
        tk.Button(
            bf,
            text="Full Analysis",
            font=(FF, 11, "bold"),
            bg=T["accent"],
            fg="white",
            bd=0,
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._money_analysis,
        ).pack(side="left", padx=4)
        tk.Button(
            bf,
            text="Savings Opportunities",
            font=FONT_SM,
            bg=T["panel2"],
            fg=T["accent"],
            bd=0,
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            command=self._money_savings,
        ).pack(side="left", padx=4)
        self.money_output = scrolledtext.ScrolledText(
            frame,
            bg=T["panel"],
            fg=T["text"],
            font=FONT_CHAT,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            state="disabled",
        )
        self.money_output.pack(fill="both", expand=True, padx=20, pady=8)

    def _money_analysis(self):
        self.money_output.configure(state="normal")
        self.money_output.delete("1.0", "end")
        self.money_output.insert("end", "Running full money analysis...\n")
        self.money_output.configure(state="disabled")

        def _do():
            if self.money:
                try:
                    result = self.money.run_sync()
                    reply = result.get("analysis", "No analysis available")
                except Exception as e:
                    reply = f"Money Engine error: {e}"
            else:
                reply = _call_ai_sync(
                    "Analyse this business for ALL savings and income opportunities. Be specific with GBP values.",
                    provider=self.current_provider.get(),
                    model=self.current_model.get(),
                )
            self.log_queue.put(("money_result", reply))

        threading.Thread(target=_do, daemon=True).start()

    def _money_savings(self):
        self.money_output.configure(state="normal")
        self.money_output.delete("1.0", "end")
        self.money_output.insert("end", "Finding savings opportunities...\n")
        self.money_output.configure(state="disabled")

        def _do():
            reply = _call_ai_sync(
                "List the top 10 immediate savings opportunities for a UK small business. Include estimated GBP values.",
                provider=self.current_provider.get(),
                model=self.current_model.get(),
            )
            self.log_queue.put(("money_result", reply))

        threading.Thread(target=_do, daemon=True).start()

    def _money_display(self, result):
        self.money_output.configure(state="normal")
        self.money_output.delete("1.0", "end")
        self.money_output.insert("end", result)
        self.money_output.configure(state="disabled")
        self._log("Money Engine analysis complete")

    # ==================== PC CONTROL ====================
    def _panel_pc(self):
        self._clear_panel("pc")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["pc"] = frame
        tk.Label(
            frame,
            text="\U0001f5a5 PC Control",
            font=FONT_XL,
            bg=T["bg"],
            fg=T["accent"],
        ).pack(pady=12)
        tk.Label(
            frame,
            text="All actions require approval. Move mouse to corner to abort (failsafe).",
            font=FONT_SM,
            bg=T["bg"],
            fg=T["yellow"],
        ).pack(pady=4)
        for title, actions in [
            (
                "Mouse",
                [
                    ("Screenshot", "screenshot", ""),
                    ("Click x,y", "click", "x,y"),
                    ("Move to x,y", "move", "x,y"),
                ],
            ),
            (
                "Keyboard",
                [
                    ("Type Text", "type", "text"),
                    ("Ctrl+C", "hotkey", "ctrl+c"),
                    ("Escape", "key", "escape"),
                ],
            ),
            (
                "Apps",
                [
                    ("Explorer", "open_app", "explorer"),
                    ("Notepad", "open_app", "notepad"),
                    ("Calculator", "open_app", "calc"),
                ],
            ),
            (
                "Processes",
                [
                    ("List Windows", "list_windows", ""),
                    ("OCR Screen", "ocr_screen", ""),
                    ("Run Command", "run_process", "command"),
                ],
            ),
        ]:
            tk.Label(
                frame, text=title, font=(FF, 11, "bold"), bg=T["bg"], fg=T["text"]
            ).pack(anchor="w", padx=20, pady=(8, 4))
            row = tk.Frame(frame, bg=T["bg"])
            row.pack(fill="x", padx=20)
            for label, action, hint in actions:
                tk.Button(
                    row,
                    text=label,
                    font=FONT_SM,
                    bg=T["panel2"],
                    fg=T["text"],
                    bd=0,
                    relief="flat",
                    padx=10,
                    pady=6,
                    cursor="hand2",
                    command=lambda a=action, h=hint: self._pc_action(a, h),
                ).pack(side="left", padx=4)
        self.pc_log = scrolledtext.ScrolledText(
            frame,
            bg=T["panel"],
            fg=T["muted"],
            font=FONT_CODE,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            state="disabled",
            height=6,
        )
        self.pc_log.pack(fill="x", padx=20, pady=8)

    def _pc_action(self, action, hint=""):
        param = ""
        if hint:
            param = simpledialog.askstring("PC Action", f"Enter {hint}:")
            if param is None:
                return
        if not messagebox.askyesno(
            "PC Action", f"Action: {action}\nParam: {param or '(none)'}\n\nAllow?"
        ):
            return
        self.pc_log.configure(state="normal")
        self.pc_log.insert(
            "end", f"[{datetime.now(UTC).strftime('%H:%M:%S')}] {action} {param}\n"
        )
        self.pc_log.configure(state="disabled")

        def _do():
            try:
                if action == "screenshot":
                    import pyautogui

                    fp = DATA_DIR / "screenshots" / f"screenshot_{int(time.time())}.png"
                    pyautogui.screenshot().save(str(fp))
                    self.log_queue.put(("log", f"Screenshot saved: {fp}"))
                elif action == "click":
                    import pyautogui

                    x, y = map(int, param.split(","))
                    pyautogui.click(x, y)
                    self.log_queue.put(("log", f"Clicked {x},{y}"))
                elif action == "type":
                    import pyautogui

                    pyautogui.write(param, interval=0.03)
                    self.log_queue.put(("log", f"Typed: {param[:50]}"))
                elif action == "hotkey":
                    import pyautogui

                    pyautogui.hotkey(*param.split("+"))
                    self.log_queue.put(("log", f"Hotkey: {param}"))
                elif action == "key":
                    import pyautogui

                    pyautogui.press(param)
                    self.log_queue.put(("log", f"Key: {param}"))
                elif action == "move":
                    import pyautogui

                    x, y = map(int, param.split(","))
                    pyautogui.moveTo(x, y)
                    self.log_queue.put(("log", f"Moved to {x},{y}"))
                elif action == "open_app":
                    subprocess.Popen(f"start {param}", shell=True)
                    self.log_queue.put(("log", f"Opened: {param}"))
                elif action == "list_windows":
                    import pygetwindow as gw

                    wins = [{"title": w.title} for w in gw.getAllWindows() if w.title]
                    self.log_queue.put(("log", f"Windows: {len(wins)} found"))
                elif action == "ocr_screen":
                    import pyautogui, pytesseract

                    img = pyautogui.screenshot()
                    text = pytesseract.image_to_string(img)
                    self.log_queue.put(("log", f"OCR: {text[:200]}"))
                elif action == "run_process":
                    result = subprocess.run(
                        param, shell=True, capture_output=True, text=True, timeout=30
                    )
                    self.log_queue.put(
                        ("log", f"Command output: {result.stdout[:200]}")
                    )
            except ImportError as e:
                self.log_queue.put(("log", f"Missing dependency: {e}"))
            except Exception as e:
                self.log_queue.put(("log", f"Error: {e}"))

        threading.Thread(target=_do, daemon=True).start()

    # ==================== PROVIDERS ====================
    def _panel_providers(self):
        self._clear_panel("providers")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["providers"] = frame
        tk.Label(
            frame,
            text="\U0001f50c AI Providers",
            font=FONT_XL,
            bg=T["bg"],
            fg=T["accent"],
        ).pack(pady=12)
        tk.Button(
            frame,
            text="Probe All",
            font=(FF, 11, "bold"),
            bg=T["accent"],
            fg="white",
            bd=0,
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._auto_probe,
        ).pack(pady=4)
        self.provider_list = scrolledtext.ScrolledText(
            frame,
            bg=T["panel"],
            fg=T["text"],
            font=FONT_CHAT,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            state="disabled",
        )
        self.provider_list.pack(fill="both", expand=True, padx=20, pady=8)
        self.provider_list.tag_config(
            "prov", font=(FF, 11, "bold"), foreground=T["accent"]
        )
        self.provider_list.tag_config("model", foreground=T["muted"])
        self._refresh_providers()

    def _refresh_providers(self):
        self.provider_list.configure(state="normal")
        self.provider_list.delete("1.0", "end")
        for prov, models in ALL_MODELS.items():
            online = self.provider_status.get(prov, False)
            live_models = self.provider_models_live.get(prov) or models
            status_text = "\u25cf ONLINE" if online else "\u25cb offline"
            self.provider_list.insert("end", f"{status_text}  {prov}\n", "prov")
            for m in live_models[:8]:
                self.provider_list.insert("end", f"    - {m}\n", "model")
            if len(live_models) > 8:
                self.provider_list.insert(
                    "end", f"    ... and {len(live_models) - 8} more\n", "model"
                )
            self.provider_list.insert("end", "\n")
        self.provider_list.configure(state="disabled")

    # ==================== APPS ====================
    def _panel_apps(self):
        self._clear_panel("apps")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["apps"] = frame
        tk.Label(
            frame, text="\U0001f4f1 Apps", font=FONT_XL, bg=T["bg"], fg=T["accent"]
        ).pack(pady=12)
        tk.Button(
            frame,
            text="Re-Scan",
            font=FONT_SM,
            bg=T["panel2"],
            fg=T["accent"],
            bd=0,
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._refresh_apps,
        ).pack(pady=4)
        tk.Button(
            frame,
            text="Auto Detect + Connect",
            font=FONT_SM,
            bg=T["accent"],
            fg="white",
            bd=0,
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._auto_connect_apps,
        ).pack(pady=(0, 6))
        self.apps_status = scrolledtext.ScrolledText(
            frame,
            bg=T["panel"],
            fg=T["text"],
            font=FONT_SM,
            wrap="word",
            height=11,
            bd=0,
            padx=10,
            pady=8,
            state="disabled",
        )
        self.apps_status.pack(fill="x", padx=20, pady=(0, 8))
        canvas = tk.Canvas(frame, bg=T["bg"], bd=0, highlightthickness=0)
        vsb = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=T["bg"])
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.unbind_all("<MouseWheel>")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        app_groups = {
            "Email & Comms": [
                ("Gmail", lambda: self._app_action("gmail", "open")),
                ("Outlook", lambda: self._app_action("outlook", "read_inbox")),
                ("WhatsApp Web", lambda: self._open_url("https://web.whatsapp.com")),
            ],
            "Browsers": [
                ("Chrome", lambda: subprocess.Popen("start chrome", shell=True)),
                ("Edge", lambda: subprocess.Popen("start msedge", shell=True)),
            ],
            "Office": [
                ("Excel", lambda: subprocess.Popen("start excel", shell=True)),
                ("Word", lambda: subprocess.Popen("start winword", shell=True)),
            ],
            "Dev Tools": [
                ("VS Code", lambda: self._app_action("vscode", "open")),
                ("Terminal", lambda: subprocess.Popen("start cmd", shell=True)),
            ],
            "Knowledge": [
                ("Obsidian", lambda: self._app_action("obsidian", "open")),
                ("Capture Obsidian Note", self._obsidian_capture_note),
            ],
            "Social": [
                ("Facebook", lambda: self._app_action("social", "open", platform="facebook")),
                ("Instagram", lambda: self._app_action("social", "open", platform="instagram")),
                ("TikTok", lambda: self._app_action("social", "open", platform="tiktok")),
                ("Telegram", lambda: self._app_action("social", "open", platform="telegram")),
            ],
        }
        for cat, items in app_groups.items():
            tk.Label(
                inner, text=cat, font=(FF, 11, "bold"), bg=T["bg"], fg=T["accent"]
            ).pack(anchor="w", padx=16, pady=(8, 4))
            for name, cmd in items:
                btn = tk.Button(
                    inner,
                    text=f"\u25b6 {name}",
                    font=FONT_SM,
                    bg=T["card"],
                    fg=T["text"],
                    bd=0,
                    relief="flat",
                    anchor="w",
                    padx=12,
                    pady=4,
                    cursor="hand2",
                    command=cmd,
                )
                btn.pack(fill="x", padx=16, pady=1)
                btn.bind(
                    "<Enter>", lambda e, b=btn: b.configure(bg=T["accent"], fg="white")
                )
                btn.bind(
                    "<Leave>", lambda e, b=btn: b.configure(bg=T["card"], fg=T["text"])
                )
        self._refresh_apps()

    def _app_action(self, app_id, action, **kwargs):
        if self.apps:
            method = getattr(self.apps, f"{app_id}_{action}", None)
            if method:
                try:
                    result = method(**kwargs) if kwargs else method()
                    self._log(f"App {app_id}.{action}: {result}")
                    return
                except Exception as e:
                    self._log(f"App error: {e}")
        self._log(f"App {app_id}.{action} not available")

    def _refresh_apps(self):
        def _do():
            if not self.apps:
                self.log_queue.put(
                    ("apps_status", "App Bridge not initialized. Open Settings to verify backend status.")
                )
                return
            try:
                scan = self.apps.detect_integrations(refresh=True)
                self.log_queue.put(("apps_status", self._format_apps_scan(scan)))
                self._log("Apps scan complete")
            except Exception as e:
                self.log_queue.put(("apps_status", f"App scan error: {e}"))
                self._log(f"Apps scan error: {e}")

        threading.Thread(target=_do, daemon=True).start()

    def _auto_connect_apps(self):
        def _do():
            if not self.apps:
                self.log_queue.put(
                    ("apps_status", "App Bridge not initialized. Cannot auto-connect.")
                )
                return
            try:
                result = self.apps.auto_connect_integrations(include_launch=True)
                scan_text = self._format_apps_scan(result.get("scan", {}))
                actions = result.get("actions", [])
                action_text = "\n".join(f"- {a}" for a in actions) if actions else "- no launch actions needed"
                payload = (
                    "Auto-connect completed.\n\nActions:\n"
                    f"{action_text}\n\n"
                    f"{scan_text}"
                )
                self.log_queue.put(("apps_status", payload))
                self._log("Apps auto-connect complete")
            except Exception as e:
                self.log_queue.put(("apps_status", f"Auto-connect error: {e}"))
                self._log(f"Auto-connect error: {e}")

        threading.Thread(target=_do, daemon=True).start()

    def _obsidian_capture_note(self):
        if not self.apps:
            self._log("App Bridge not initialized")
            return
        title = simpledialog.askstring("Obsidian Note", "Title:")
        if not title:
            return
        content = simpledialog.askstring("Obsidian Note", "Content (quick capture):")
        if not content:
            return
        if not messagebox.askyesno("Approval Required", f"Write note '{title}' to Obsidian vault?"):
            self._log("Obsidian note capture cancelled")
            return
        try:
            result = self.apps.obsidian_capture_note(
                title=title,
                content=content,
                approved=True,
            )
            self._log(f"Obsidian capture: {result}")
            if not result.get("ok"):
                messagebox.showwarning("Obsidian", str(result))
        except Exception as e:
            self._log(f"Obsidian capture error: {e}")

    def _format_apps_scan(self, scan):
        if not scan:
            return "No integration scan data available."
        lines = [f"Last scan: {scan.get('timestamp', 'n/a')}"]
        runtime = scan.get("runtime", {})
        if runtime:
            lines.append(f"Runtime: {runtime.get('os', 'n/a')} | Python: {runtime.get('python', 'n/a')}")
        lines.append("")
        lines.append("Services")
        for key, value in scan.get("services", {}).items():
            lines.append(f"  {'ON ' if value else 'OFF'}  {key}")
        lines.append("")
        lines.append("Apps")
        for key, value in scan.get("apps", {}).items():
            extra = f", vault={value.get('vault')}" if value.get("vault") else ""
            lines.append(
                f"  {'RUN' if value.get('running') else '---'}  {key} "
                f"(available={value.get('available')}{extra})"
            )
        lines.append("")
        lines.append("Browsers")
        for key, value in scan.get("browsers", {}).items():
            lines.append(
                f"  {'RUN' if value.get('running') else '---'}  {key} "
                f"(available={value.get('available')})"
            )
        email_agents = scan.get("email_agents", {})
        if email_agents:
            lines.append("")
            lines.append(
                "Email Agents: "
                f"exo={email_agents.get('exo_available')} "
                f"gmail={email_agents.get('exo_gmail')} "
                f"outlook={email_agents.get('exo_outlook')}"
            )
        return "\n".join(lines)

    def _launch_app(self, name):
        if messagebox.askyesno("Launch", f"Open {name}?"):
            subprocess.Popen(f"start {name.lower().replace(' ', '')}", shell=True)
            self._log(f"Launched: {name}")

    # ==================== SOCIAL ====================
    def _panel_social(self):
        self._clear_panel("social")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["social"] = frame
        tk.Label(
            frame,
            text="\U0001f310 Social Media",
            font=FONT_XL,
            bg=T["bg"],
            fg=T["accent"],
        ).pack(pady=12)
        for name, url in [
            ("WhatsApp Web", "https://web.whatsapp.com"),
            ("Gmail", "https://mail.google.com"),
            ("Outlook Web", "https://outlook.office.com/mail/"),
            ("LinkedIn", "https://linkedin.com"),
            ("X/Twitter", "https://x.com"),
            ("Facebook", "https://facebook.com"),
            ("Instagram", "https://instagram.com"),
            ("TikTok", "https://tiktok.com"),
            ("Telegram", "https://web.telegram.org"),
            ("Discord", "https://discord.com"),
            ("Slack", "https://slack.com"),
            ("Zoom", "https://zoom.us"),
        ]:
            card = tk.Frame(
                frame,
                bg=T["card"],
                highlightbackground=T["border"],
                highlightthickness=1,
            )
            card.pack(fill="x", padx=20, pady=4)
            tk.Label(card, text=name, font=FONT_LG, bg=T["card"], fg=T["text"]).pack(
                side="left", padx=12, pady=8
            )
            tk.Button(
                card,
                text="Open",
                font=FONT_SM,
                bg=T["accent"],
                fg="white",
                bd=0,
                relief="flat",
                padx=12,
                pady=4,
                cursor="hand2",
                command=lambda u=url: self._open_url(u),
            ).pack(side="right", padx=12, pady=4)

    def _open_url(self, url):
        subprocess.Popen(f"start {url}", shell=True)
        self._log(f"Opened: {url}")

    # ==================== BROWSER ====================
    def _panel_browser(self):
        self._clear_panel("browser")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["browser"] = frame
        tk.Label(
            frame,
            text="\U0001f30d Web Browser",
            font=FONT_XL,
            bg=T["bg"],
            fg=T["accent"],
        ).pack(pady=12)
        uf = tk.Frame(frame, bg=T["bg"])
        uf.pack(fill="x", padx=20, pady=4)
        uf.columnconfigure(0, weight=1)
        self.browser_url = tk.StringVar(value="https://")
        tk.Entry(
            uf,
            textvariable=self.browser_url,
            bg=T["input_bg"],
            fg=T["input_text"],
            font=FONT,
            bd=0,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=6)
        tk.Button(
            uf,
            text="Go",
            font=FONT_SM,
            bg=T["accent"],
            fg="white",
            bd=0,
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._browser_go,
        ).pack(side="left")
        tk.Button(
            uf,
            text="Fetch Content",
            font=FONT_SM,
            bg=T["panel2"],
            fg=T["accent"],
            bd=0,
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._browser_fetch,
        ).pack(side="left", padx=4)
        self.browser_output = scrolledtext.ScrolledText(
            frame,
            bg=T["panel"],
            fg=T["text"],
            font=FONT_CHAT,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            state="disabled",
        )
        self.browser_output.pack(fill="both", expand=True, padx=20, pady=4)
        for group, links in [
            (
                "Search",
                [("Google", "https://google.com"), ("Bing", "https://bing.com")],
            ),
            (
                "AI",
                [
                    ("ChatGPT", "https://chat.openai.com"),
                    ("Gemini", "https://gemini.google.com"),
                    ("Claude", "https://claude.ai"),
                ],
            ),
            (
                "Dev",
                [("GitHub", "https://github.com"), ("Cursor", "https://cursor.sh")],
            ),
        ]:
            tk.Label(frame, text=group, font=FONT_SM, bg=T["bg"], fg=T["accent"]).pack(
                anchor="w", padx=20, pady=(4, 2)
            )
            row = tk.Frame(frame, bg=T["bg"])
            row.pack(fill="x", padx=20)
            for name, url in links:
                tk.Button(
                    row,
                    text=name,
                    font=FONT_SM,
                    bg=T["card"],
                    fg=T["text"],
                    bd=0,
                    relief="flat",
                    padx=10,
                    pady=4,
                    cursor="hand2",
                    command=lambda u=url: self._open_url(u),
                ).pack(side="left", padx=4)

    def _browser_go(self):
        url = self.browser_url.get().strip()
        if not url or url == "https://":
            return
        if not url.startswith("http"):
            url = "https://" + url
        self._open_url(url)

    def _browser_fetch(self):
        url = self.browser_url.get().strip()
        if not url or url == "https://":
            return
        if not url.startswith("http"):
            url = "https://" + url
        self.browser_output.configure(state="normal")
        self.browser_output.delete("1.0", "end")
        self.browser_output.insert("end", f"Fetching {url}...\n")
        self.browser_output.configure(state="disabled")

        def _do():
            if self.tools:
                try:
                    result = self.tools.run("web_fetch", url=url)
                except Exception as e:
                    result = f"Fetch error: {e}"
            else:
                try:
                    with urllib.request.urlopen(url, timeout=15) as r:
                        html = r.read().decode("utf-8", errors="ignore")
                    result = re.sub(r"<[^>]+>", " ", html)
                    result = re.sub(r"\s+", " ", result).strip()[:3000]
                except Exception as e:
                    result = f"Error: {e}"
            self.browser_output.configure(state="normal")
            self.browser_output.delete("1.0", "end")
            self.browser_output.insert("end", result)
            self.browser_output.configure(state="disabled")

        threading.Thread(target=_do, daemon=True).start()

    # ==================== VISION ====================
    def _panel_vision(self):
        self._clear_panel("vision")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["vision"] = frame
        tk.Label(
            frame,
            text="\U0001f441 Vision Analysis",
            font=FONT_XL,
            bg=T["bg"],
            fg=T["accent"],
        ).pack(pady=12)
        tk.Label(
            frame,
            text="Select an image or PDF to analyse with AI vision models.",
            font=FONT,
            bg=T["bg"],
            fg=T["text_sec"],
        ).pack()
        vf = tk.Frame(frame, bg=T["bg"])
        vf.pack(fill="x", padx=20, pady=8)
        tk.Button(
            vf,
            text="Select Image/PDF",
            font=(FF, 11, "bold"),
            bg=T["accent"],
            fg="white",
            bd=0,
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._vision_select,
        ).pack(side="left", padx=4)
        self.vision_task_var = tk.StringVar(value="general")
        tk.Label(vf, text="Task:", font=FONT_SM, bg=T["bg"], fg=T["text"]).pack(
            side="left", padx=(16, 4)
        )
        ttk.Combobox(
            vf,
            textvariable=self.vision_task_var,
            values=["general", "bill", "contract", "receipt", "screenshot", "product"],
            width=12,
            state="readonly",
            font=FONT_SM,
        ).pack(side="left")
        self.vision_preview = tk.Label(
            frame,
            text="No image selected",
            font=FONT_SM,
            bg=T["panel"],
            fg=T["muted"],
            padx=20,
            pady=20,
        )
        self.vision_preview.pack(fill="x", padx=20, pady=4)
        self.vision_output = scrolledtext.ScrolledText(
            frame,
            bg=T["panel"],
            fg=T["text"],
            font=FONT_CHAT,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            state="disabled",
        )
        self.vision_output.pack(fill="both", expand=True, padx=20, pady=4)
        self._vision_image_path = None
        self._vision_image_b64 = None

    def _vision_select(self):
        fp = filedialog.askopenfilename(
            filetypes=[
                ("Images", "*.jpg *.jpeg *.png *.webp *.bmp"),
                ("PDFs", "*.pdf"),
                ("All", "*.*"),
            ]
        )
        if not fp:
            return
        self._vision_image_path = fp
        self.vision_preview.configure(text=f"Selected: {Path(fp).name}", fg=T["text"])
        try:
            with open(fp, "rb") as f:
                self._vision_image_b64 = base64.b64encode(f.read()).decode()
        except Exception as e:
            self._vision_image_b64 = None
            self._log(f"Image read error: {e}")
        self._vision_analyse()

    def _vision_analyse(self):
        if not self._vision_image_path:
            messagebox.showinfo("Vision", "Please select an image or PDF first.")
            return
        task = self.vision_task_var.get()
        self.vision_output.configure(state="normal")
        self.vision_output.delete("1.0", "end")
        self.vision_output.insert(
            "end", f"Analysing {Path(self._vision_image_path).name} (task: {task})...\n"
        )
        self.vision_output.configure(state="disabled")

        def _do():
            if self.vision and self._vision_image_path:
                try:
                    result = self.vision.analyse_sync(self._vision_image_path, task)
                    reply = (
                        json.dumps(result, indent=2)
                        if isinstance(result, dict)
                        else str(result)
                    )
                except Exception as e:
                    reply = f"Vision analysis error: {e}\n\n{traceback.format_exc()}"
            elif self._vision_image_b64:
                reply = _call_ai_sync(
                    f"Analyse this image (base64 data available). Task: {task}. Describe what you see in detail.",
                    provider=self.current_provider.get(),
                    model=self.current_model.get(),
                )
            else:
                reply = "No vision backend available and image data not available."
            self.log_queue.put(("vision_result", reply))

        threading.Thread(target=_do, daemon=True).start()

    def _vision_display(self, result):
        self.vision_output.configure(state="normal")
        self.vision_output.delete("1.0", "end")
        self.vision_output.insert("end", result)
        self.vision_output.configure(state="disabled")
        self._log("Vision analysis complete")

    # ==================== SCHEDULER ====================
    def _panel_scheduler(self):
        self._clear_panel("scheduler")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["scheduler"] = frame
        tk.Label(
            frame,
            text="\u23f0 Task Scheduler",
            font=FONT_XL,
            bg=T["bg"],
            fg=T["accent"],
        ).pack(pady=12)
        tk.Label(
            frame,
            text="Time-based and trigger-based automated tasks",
            font=FONT,
            bg=T["bg"],
            fg=T["text_sec"],
        ).pack()
        bf = tk.Frame(frame, bg=T["bg"])
        bf.pack(fill="x", padx=20, pady=8)
        tk.Button(
            bf,
            text="Refresh",
            font=FONT_SM,
            bg=T["panel2"],
            fg=T["accent"],
            bd=0,
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._refresh_scheduler,
        ).pack(side="left", padx=4)
        tk.Button(
            bf,
            text="Add Task",
            font=FONT_SM,
            bg=T["accent"],
            fg="white",
            bd=0,
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._add_scheduler_task,
        ).pack(side="left", padx=4)
        self.scheduler_output = scrolledtext.ScrolledText(
            frame,
            bg=T["panel"],
            fg=T["text"],
            font=FONT_CHAT,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            state="disabled",
        )
        self.scheduler_output.pack(fill="both", expand=True, padx=20, pady=4)
        self._refresh_scheduler()

    def _refresh_scheduler(self):
        self.scheduler_output.configure(state="normal")
        self.scheduler_output.delete("1.0", "end")
        if self.scheduler:
            tasks = self.scheduler.list_tasks()
            if not tasks:
                self.scheduler_output.insert("end", "No scheduled tasks.\n", "system")
            for t in tasks:
                status = "\u25cf" if t["enabled"] else "\u25cb"
                self.scheduler_output.insert(
                    "end",
                    f"{status} {t['name']} [{t['trigger']}] - {'ENABLED' if t['enabled'] else 'DISABLED'}\n",
                )
                self.scheduler_output.insert(
                    "end", f"   Last run: {t.get('last_run', 'Never')}\n"
                )
                if t.get("next_run"):
                    self.scheduler_output.insert(
                        "end", f"   Next run: {t['next_run'][:19]}\n"
                    )
                self.scheduler_output.insert(
                    "end", f"   Run count: {t.get('run_count', 0)}\n"
                )
                self.scheduler_output.insert("end", "\n")
        else:
            self.scheduler_output.insert("end", "Scheduler not available.\n")
        self.scheduler_output.configure(state="disabled")

    def _add_scheduler_task(self):
        if not self.scheduler:
            messagebox.showinfo("Scheduler", "Scheduler not initialized.")
            return
        name = simpledialog.askstring("Add Task", "Task name:")
        if not name:
            return
        instruction = simpledialog.askstring("Add Task", "What should this task do?")
        if not instruction:
            return
        trigger = simpledialog.askstring(
            "Add Task",
            "Trigger type (daily/weekly/monthly/once):",
            initialvalue="daily",
        )
        if not trigger:
            trigger = "daily"
        trigger_cfg = simpledialog.askstring(
            "Add Task", "Trigger config (e.g. time=09:00):", initialvalue="time=09:00"
        )
        cfg = {}
        if trigger_cfg:
            for part in trigger_cfg.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    cfg[k.strip()] = v.strip()
        from src.scheduler.scheduler import TriggerType

        trigger_map = {
            "daily": TriggerType.TIME_DAILY,
            "weekly": TriggerType.TIME_WEEKLY,
            "monthly": TriggerType.TIME_MONTHLY,
            "once": TriggerType.TIME_ONCE,
        }
        tt = trigger_map.get(trigger.lower(), TriggerType.TIME_DAILY)
        task_id = name.lower().replace(" ", "_")
        self.scheduler.add(task_id, name, instruction, tt, cfg)
        self._log(f"Added scheduled task: {name}")
        self._refresh_scheduler()

    def _scheduler_display(self, result):
        self.scheduler_output.configure(state="normal")
        self.scheduler_output.insert("end", f"\n--- Scheduler Result ---\n{result}\n")
        self.scheduler_output.configure(state="disabled")

    # ==================== MEETINGS ====================
    def _panel_meetings(self):
        self._clear_panel("meetings")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["meetings"] = frame
        tk.Label(
            frame,
            text="\U0001f3a4 Meeting Intelligence",
            font=FONT_XL,
            bg=T["bg"],
            fg=T["accent"],
        ).pack(pady=12)
        tk.Label(
            frame,
            text="Upload meeting transcripts (.txt, .vtt, .srt, .md) for AI analysis.",
            font=FONT,
            bg=T["bg"],
            fg=T["text_sec"],
        ).pack()
        bf = tk.Frame(frame, bg=T["bg"])
        bf.pack(fill="x", padx=20, pady=8)
        tk.Button(
            bf,
            text="Select Transcript",
            font=(FF, 11, "bold"),
            bg=T["accent"],
            fg="white",
            bd=0,
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._meeting_process,
        ).pack(side="left", padx=4)
        self.meeting_output = scrolledtext.ScrolledText(
            frame,
            bg=T["panel"],
            fg=T["text"],
            font=FONT_CHAT,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            state="disabled",
        )
        self.meeting_output.pack(fill="both", expand=True, padx=20, pady=4)

    def _meeting_process(self):
        fp = filedialog.askopenfilename(
            filetypes=[("Transcripts", "*.txt *.vtt *.srt *.md *.pdf"), ("All", "*.*")]
        )
        if not fp:
            return
        self.meeting_output.configure(state="normal")
        self.meeting_output.delete("1.0", "end")
        self.meeting_output.insert(
            "end", f"Processing transcript: {Path(fp).name}...\n"
        )
        self.meeting_output.configure(state="disabled")

        def _do():
            if self.meetings:
                try:
                    import asyncio

                    result = asyncio.run(self.meetings.process_transcript(fp))
                    reply = (
                        json.dumps(result, indent=2)
                        if isinstance(result, dict)
                        else str(result)
                    )
                except Exception as e:
                    reply = f"Meeting processing error: {e}"
            else:
                text = Path(fp).read_text(errors="replace")[:4000]
                reply = _call_ai_sync(
                    f"Analyse this meeting transcript and extract action items, decisions, and key points:\n\n{text}",
                    provider=self.current_provider.get(),
                    model=self.current_model.get(),
                )
            self.log_queue.put(("meeting_result", reply))

        threading.Thread(target=_do, daemon=True).start()

    def _meeting_display(self, result):
        self.meeting_output.configure(state="normal")
        self.meeting_output.delete("1.0", "end")
        self.meeting_output.insert("end", result)
        self.meeting_output.configure(state="disabled")
        self._log("Meeting analysis complete")

    # ==================== DEVTOOLS ====================
    def _panel_devtools(self):
        self._clear_panel("devtools")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["devtools"] = frame
        tk.Label(
            frame, text="\U0001f6e0 DevTools", font=FONT_XL, bg=T["bg"], fg=T["accent"]
        ).pack(pady=12)
        for title, actions in [
            (
                "Git",
                [
                    ("Status", "git_status"),
                    ("Log", "git_log"),
                    ("Diff", "git_diff"),
                    ("Branches", "git_branch_list"),
                ],
            ),
            (
                "VS Code",
                [
                    ("Open Folder", "vscode_open_folder"),
                    ("List Extensions", "vscode_list_extensions"),
                ],
            ),
            (
                "Terminal",
                [
                    ("Run Command", "run_command"),
                    ("Python Script", "run_python"),
                    ("Run Tests", "run_tests"),
                    ("Pip List", "pip_list"),
                ],
            ),
            (
                "Code Analysis",
                [
                    ("Analyse File", "analyse_file"),
                    ("Analyse Repo", "analyse_repo"),
                    ("List Files", "list_repo_files"),
                ],
            ),
        ]:
            tk.Label(
                frame, text=title, font=(FF, 11, "bold"), bg=T["bg"], fg=T["text"]
            ).pack(anchor="w", padx=20, pady=(8, 4))
            row = tk.Frame(frame, bg=T["bg"])
            row.pack(fill="x", padx=20)
            for label, action in actions:
                tk.Button(
                    row,
                    text=label,
                    font=FONT_SM,
                    bg=T["panel2"],
                    fg=T["text"],
                    bd=0,
                    relief="flat",
                    padx=10,
                    pady=6,
                    cursor="hand2",
                    command=lambda a=action: self._devtools_action(a),
                ).pack(side="left", padx=4)
        self.devtools_output = scrolledtext.ScrolledText(
            frame,
            bg=T["panel"],
            fg=T["text"],
            font=FONT_CODE,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            state="disabled",
        )
        self.devtools_output.pack(fill="both", expand=True, padx=20, pady=8)

    def _devtools_action(self, action):
        if not self.devtools:
            self._log("DevTools not available")
            return
        param = None
        if action in ("analyse_file", "vscode_open_folder"):
            param = simpledialog.askstring("DevTools", "Enter path:")
            if not param:
                return
        elif action == "run_command":
            param = simpledialog.askstring("DevTools", "Enter command:")
            if not param:
                return

        self.devtools_output.configure(state="normal")
        self.devtools_output.delete("1.0", "end")
        self.devtools_output.insert("end", f"Running: {action}...\n")
        self.devtools_output.configure(state="disabled")

        def _do():
            try:
                if param:
                    if action == "analyse_file":
                        result = self.devtools.analyse_file(param)
                    elif action == "vscode_open_folder":
                        result = self.devtools.vscode_open_folder(param)
                    elif action == "run_command":
                        result = self.devtools.run_command(param, approved=True)
                    else:
                        result = getattr(self.devtools, action)(param)
                else:
                    result = getattr(self.devtools, action)()
                reply = (
                    json.dumps(result, indent=2)
                    if isinstance(result, dict)
                    else str(result)
                )
            except Exception as e:
                reply = f"DevTools error: {e}"
            self.log_queue.put(("devtools_result", reply))

        threading.Thread(target=_do, daemon=True).start()

    def _devtools_display(self, result):
        self.devtools_output.configure(state="normal")
        self.devtools_output.delete("1.0", "end")
        self.devtools_output.insert("end", result)
        self.devtools_output.configure(state="disabled")
        self._log("DevTools action complete")

    # ==================== CLAWS ====================
    def _panel_claws(self):
        self._clear_panel("claws")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["claws"] = frame
        tk.Label(
            frame,
            text="\U0001f980 Claws - Plugin Installer",
            font=FONT_XL,
            bg=T["bg"],
            fg=T["accent"],
        ).pack(pady=12)
        tk.Label(
            frame,
            text="Install and manage BABA plugins (claws).",
            font=FONT,
            bg=T["bg"],
            fg=T["text_sec"],
        ).pack()
        bf = tk.Frame(frame, bg=T["bg"])
        bf.pack(fill="x", padx=20, pady=8)
        tk.Button(
            bf,
            text="Install Claw",
            font=(FF, 11, "bold"),
            bg=T["accent"],
            fg="white",
            bd=0,
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._claw_install,
        ).pack(side="left", padx=4)
        tk.Button(
            bf,
            text="List Installed",
            font=FONT_SM,
            bg=T["panel2"],
            fg=T["accent"],
            bd=0,
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            command=self._claw_list,
        ).pack(side="left", padx=4)
        self.claw_output = scrolledtext.ScrolledText(
            frame,
            bg=T["panel"],
            fg=T["text"],
            font=FONT_CHAT,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            state="disabled",
        )
        self.claw_output.pack(fill="both", expand=True, padx=20, pady=4)

    def _claw_install(self):
        claw_path = filedialog.askopenfilename(
            filetypes=[("Python", "*.py"), ("All", "*.*")]
        )
        if not claw_path:
            return
        if not messagebox.askyesno("Install Claw", f"Install {Path(claw_path).name}?"):
            return
        self.claw_output.configure(state="normal")
        self.claw_output.delete("1.0", "end")
        self.claw_output.insert("end", f"Installing claw: {Path(claw_path).name}...\n")
        self.claw_output.configure(state="disabled")

        def _do():
            if self.claws:
                try:
                    result = self.claws.install(claw_path)
                    reply = f"Claw installed: {result}"
                except Exception as e:
                    reply = f"Claw install error: {e}"
            else:
                reply = "Claw installer not available."
            self.log_queue.put(("claw_result", reply))

        threading.Thread(target=_do, daemon=True).start()

    def _claw_list(self):
        self.claw_output.configure(state="normal")
        self.claw_output.delete("1.0", "end")
        if self.claws:
            try:
                installed = self.claws.list_installed()
                if installed:
                    for c in installed:
                        self.claw_output.insert("end", f"  - {c}\n")
                else:
                    self.claw_output.insert("end", "No claws installed.\n")
            except Exception as e:
                self.claw_output.insert("end", f"Error listing claws: {e}\n")
        else:
            self.claw_output.insert("end", "Claw installer not available.\n")
        self.claw_output.configure(state="disabled")

    def _claw_display(self, result):
        self.claw_output.configure(state="normal")
        self.claw_output.insert("end", f"\n{result}\n")
        self.claw_output.configure(state="disabled")

    # ==================== SELF-EVOLVING ====================
    def _panel_evolve(self):
        self._clear_panel("evolve")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["evolve"] = frame
        tk.Label(
            frame,
            text="\U0001f9ec Self-Evolving System",
            font=FONT_XL,
            bg=T["bg"],
            fg=T["accent"],
        ).pack(pady=12)
        tk.Label(
            frame,
            text="Learns from every interaction. Gets smarter over time.",
            font=FONT,
            bg=T["bg"],
            fg=T["text_sec"],
        ).pack()
        sf = tk.Frame(frame, bg=T["bg"])
        sf.pack(fill="x", padx=20, pady=12)
        if self.memory:
            stats = self.memory.stats()
            for label, val in [
                ("Memories", stats.get("total_memories", 0)),
                ("Preferences", stats.get("preferences", 0)),
                ("Decisions", stats.get("decisions", 0)),
                ("ChromaDB", "Yes" if stats.get("chroma_active") else "No"),
            ]:
                chip = tk.Frame(
                    sf,
                    bg=T["card"],
                    highlightbackground=T["border"],
                    highlightthickness=1,
                )
                chip.pack(side="left", padx=8, pady=4)
                tk.Label(
                    chip,
                    text=str(val),
                    bg=T["card"],
                    fg=T["accent"],
                    font=(FF, 20, "bold"),
                ).pack(padx=14, pady=(6, 0))
                tk.Label(
                    chip, text=label.upper(), bg=T["card"], fg=T["muted"], font=(FF, 7)
                ).pack(pady=(0, 6))
        self.evolve_output = scrolledtext.ScrolledText(
            frame,
            bg=T["panel"],
            fg=T["text"],
            font=FONT_CHAT,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            state="disabled",
        )
        self.evolve_output.pack(fill="both", expand=True, padx=20, pady=8)
        self.evolve_output.configure(state="normal")
        self.evolve_output.insert("end", "Self-Evolving System Active\n\n")
        self.evolve_output.insert(
            "end",
            "- Records all interactions\n- Detects usage patterns\n- Improves prompts automatically\n- Builds knowledge base\n\n",
        )
        if self.memory:
            ctx = self.memory.get_context_summary()
            self.evolve_output.insert("end", f"{ctx}\n\n")
            suggestions = self.memory.proactive_suggestions()
            if suggestions:
                self.evolve_output.insert("end", "Suggestions:\n")
                for s in suggestions:
                    self.evolve_output.insert("end", f"  - {s}\n")
        self.evolve_output.configure(state="disabled")
        tk.Button(
            frame,
            text="Refresh",
            font=FONT_SM,
            bg=T["panel2"],
            fg=T["accent"],
            bd=0,
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._panel_evolve,
        ).pack(pady=4)

    # ==================== RESEARCH ====================
    def _panel_research(self):
        self._clear_panel("research")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["research"] = frame
        tk.Label(
            frame,
            text="\U0001f50d AutoResearch Engine",
            font=FONT_XL,
            bg=T["bg"],
            fg=T["accent"],
        ).pack(pady=12)
        inf = tk.Frame(frame, bg=T["bg"])
        inf.pack(fill="x", padx=20, pady=8)
        tk.Label(inf, text="Topic:", bg=T["bg"], fg=T["text"], font=FONT_SM).pack(
            side="left", padx=(0, 4)
        )
        self.research_topic = tk.Entry(
            inf, bg=T["input_bg"], fg=T["input_text"], font=FONT, bd=0
        )
        self.research_topic.pack(side="left", fill="x", expand=True, ipady=6)
        tk.Label(inf, text="Depth:", bg=T["bg"], fg=T["text"], font=FONT_SM).pack(
            side="left", padx=(8, 4)
        )
        self.research_depth = ttk.Combobox(
            inf,
            values=["quick", "medium", "deep"],
            width=8,
            state="readonly",
            font=FONT_SM,
        )
        self.research_depth.set("medium")
        self.research_depth.pack(side="left", padx=(0, 8))
        tk.Button(
            inf,
            text="Research",
            font=FONT_SM,
            bg=T["accent"],
            fg="white",
            bd=0,
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._run_research,
        ).pack(side="left")
        self.research_output = scrolledtext.ScrolledText(
            frame,
            bg=T["panel"],
            fg=T["text"],
            font=FONT_CHAT,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            state="disabled",
        )
        self.research_output.pack(fill="both", expand=True, padx=20, pady=4)

    def _run_research(self):
        topic = self.research_topic.get().strip()
        if not topic:
            return
        depth = self.research_depth.get()
        self.research_output.configure(state="normal")
        self.research_output.delete("1.0", "end")
        self.research_output.insert(
            "end", f"Researching: {topic} (depth: {depth})...\n\n"
        )
        self.research_output.configure(state="disabled")

        def _do():
            prov = self.current_provider.get()
            model = self.current_model.get()
            config = {"quick": (3, 1500), "medium": (5, 3000), "deep": (8, 5000)}
            num_q, tokens = config.get(depth, (5, 3000))
            try:
                resp = _call_ai_sync(
                    f"Break this topic into {num_q} specific sub-questions. Return ONLY numbered questions.\n\nTopic: {topic}",
                    provider=prov,
                    model=model,
                )
                questions = [
                    q.strip()
                    for q in resp.split("\n")
                    if q.strip() and any(c.isdigit() for c in q[:3])
                ][:num_q]
            except Exception:
                questions = [
                    f"What is {topic}?",
                    f"Key aspects of {topic}?",
                    f"Risks related to {topic}?",
                    f"Opportunities in {topic}?",
                    f"Actions for {topic}?",
                ]
            if self.brain:
                for q in questions[:2]:
                    self.brain.search(q)
            findings = []
            for q in questions:
                finding = _call_ai_sync(
                    f"Research: {q}. Provide detailed facts, data, sources, and practical insights.",
                    provider=prov,
                    model=model,
                    max_tokens=tokens,
                )
                findings.append({"question": q, "finding": finding})
            synthesis = f"Research Topic: {topic}\n\nFindings:\n" + "\n\n".join(
                [f"Q: {f['question']}\n{f['finding'][:500]}" for f in findings]
            )
            report = _call_ai_sync(
                f"Generate a comprehensive research report:\n\n{synthesis}\n\nInclude: Executive Summary, Key Findings, Data, Risks, Opportunities, Recommended Actions.",
                provider=prov,
                model=model,
                max_tokens=5000,
            )
            self.log_queue.put(("research_result", report))

        threading.Thread(target=_do, daemon=True).start()

    def _research_display(self, report):
        self.research_output.configure(state="normal")
        self.research_output.delete("1.0", "end")
        self.research_output.insert("end", report)
        self.research_output.configure(state="disabled")
        self._log("Research complete")

    # ==================== SETTINGS ====================
    def _panel_settings(self):
        self._clear_panel("settings")
        frame = tk.Frame(self.main, bg=T["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.panels["settings"] = frame
        tk.Label(
            frame, text="\u2699 Settings", font=FONT_XL, bg=T["bg"], fg=T["accent"]
        ).pack(pady=16)
        canvas = tk.Canvas(frame, bg=T["bg"], bd=0, highlightthickness=0)
        vsb = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=T["bg"])
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.unbind_all("<MouseWheel>")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        sections = [
            (
                "Provider Configuration",
                [
                    ("Default Provider:", self.current_provider.get(), None),
                    ("Default Model:", self.current_model.get(), None),
                ],
            ),
            (
                "Voice",
                [
                    ("Enable TTS", self.voice_enabled, None),
                ],
            ),
            (
                "Theme",
                [
                    (f"Switch to {t}", None, lambda th=t: self._set_theme(th))
                    for t in THEMES
                ],
            ),
            (
                "API Keys",
                [
                    (
                        "Edit .env",
                        None,
                        lambda: subprocess.Popen(
                            f"start notepad {APP_DIR / '.env'}", shell=True
                        ),
                    ),
                    (
                        "Edit config.json",
                        None,
                        lambda: subprocess.Popen(
                            f"start notepad {APP_DIR / 'config' / 'config.json'}",
                            shell=True,
                        ),
                    ),
                ],
            ),
            (
                "Backend Status",
                [
                    (f"Brain Index: {'OK' if self.brain else 'N/A'}", None, None),
                    (f"Provider Pool: {'OK' if self.pool else 'N/A'}", None, None),
                    (
                        f"Agent Orchestrator: {'OK' if self.agents else 'N/A'}",
                        None,
                        None,
                    ),
                    (f"Vision Pipeline: {'OK' if self.vision else 'N/A'}", None, None),
                    (f"Money Engine: {'OK' if self.money else 'N/A'}", None, None),
                    (f"PC Bridge: {'OK' if self.pc else 'N/A'}", None, None),
                    (f"App Bridge: {'OK' if self.apps else 'N/A'}", None, None),
                    (f"Memory: {'OK' if self.memory else 'N/A'}", None, None),
                    (f"Dispatcher: {'OK' if self.dispatcher else 'N/A'}", None, None),
                    (f"Scheduler: {'OK' if self.scheduler else 'N/A'}", None, None),
                    (f"Cowork: {'OK' if self.cowork else 'N/A'}", None, None),
                    (f"DevTools: {'OK' if self.devtools else 'N/A'}", None, None),
                    (f"Meetings: {'OK' if self.meetings else 'N/A'}", None, None),
                    (f"Chrome Connector: {'OK' if self.chrome else 'N/A'}", None, None),
                    (f"Claw Installer: {'OK' if self.claws else 'N/A'}", None, None),
                    (
                        f"Tool Builder: {'OK' if self.tool_builder else 'N/A'}",
                        None,
                        None,
                    ),
                ],
            ),
        ]
        for section, items in sections:
            tk.Label(
                inner, text=section, font=(FF, 11, "bold"), bg=T["bg"], fg=T["text"]
            ).pack(anchor="w", padx=20, pady=(12, 4))
            for item in items:
                if len(item) == 3:
                    label, var, cmd = item
                else:
                    continue
                row = tk.Frame(inner, bg=T["bg"])
                row.pack(fill="x", padx=20, pady=2)
                tk.Label(
                    row,
                    text=label,
                    bg=T["bg"],
                    fg=T["text"],
                    font=FONT,
                    width=30,
                    anchor="w",
                ).pack(side="left")
                if isinstance(var, tk.BooleanVar):
                    tk.Checkbutton(
                        row,
                        variable=var,
                        bg=T["bg"],
                        fg=T["text"],
                        selectcolor=T["panel2"],
                        font=FONT_SM,
                    ).pack(side="left")
                elif var is not None and not isinstance(var, bool):
                    tk.Label(
                        row, text=str(var), bg=T["bg"], fg=T["text_sec"], font=FONT_SM
                    ).pack(side="left")
                if cmd:
                    tk.Button(
                        row,
                        text="Go",
                        font=FONT_SM,
                        bg=T["panel2"],
                        fg=T["accent"],
                        bd=0,
                        relief="flat",
                        padx=10,
                        pady=4,
                        cursor="hand2",
                        command=cmd,
                    ).pack(side="right", padx=4)


if __name__ == "__main__":
    app = BabaDesktop()
    app.mainloop()
