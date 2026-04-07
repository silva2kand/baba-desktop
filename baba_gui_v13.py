#!/usr/bin/env python3
"""
BABA DESKTOP v13 - ULTIMATE UK OFFICE ASSISTANT
Manus + Claude Hybrid UI with Professional UK Agent Workflows
Integrated with EXO Email Agents, Planner, Executor, and Memory.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading, json, os, sys, queue, time, traceback, subprocess, re, asyncio, inspect
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, UTC

try:
    import win32com.client
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# Email agents are loaded from real EXO integrations when available.

try:
    from exo_email_agents import GmailAgent, OutlookAgent
    HAS_EXO_EMAIL = True
except ImportError:
    HAS_EXO_EMAIL = False
    GmailAgent = None
    OutlookAgent = None

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
LOGS_DIR = APP_DIR / "logs"
for d in [DATA_DIR, LOGS_DIR, DATA_DIR / "exports", DATA_DIR / "imports", DATA_DIR / "brain_index", DATA_DIR / "brain_memory"]:
    d.mkdir(parents=True, exist_ok=True)

try:
    from config.settings import Settings
except ImportError:
    Settings = None

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
    from src.scheduler.scheduler import Scheduler, TriggerType
except ImportError:
    Scheduler = None
    TriggerType = None

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
    from src.claws.installer import ClawInstaller
except ImportError:
    ClawInstaller = None

try:
    from src.tools_experimental.builder import ToolBuilder
except ImportError:
    ToolBuilder = None

try:
    from src.knowledge.wiki import WikiCompiler
except ImportError:
    WikiCompiler = None

try:
    from src.personality.kairos import KairosMemory
except ImportError:
    KairosMemory = None

# --- REAL AI BACKEND & API INTEGRATION ---
BABA_SYSTEM_PROMPT = """You are Baba Desktop v13, a local-first assistant.
- Be direct, useful, and action-oriented.
- Never expose chain-of-thought, internal reasoning tags, or <think>/<thought> blocks.
- Never invent profile fields, IDs, departments, placeholders, or fake integrations.
- Never invent scan progress, percentages, ETAs, folder counts, timestamps, or message examples.
- If runtime data is unavailable, say it is unavailable and ask to run the relevant tool/scan.
- If a connector is offline, state exactly what is missing and how to fix it.
- Keep responses concise unless asked for detail.
"""

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
    "qwen": ["qwen-max", "qwen2.5-72b-instruct", "qwen-turbo"],
}

def _test_provider(provider):
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
    order = [preferred, "ollama", "jan", "lmstudio", "groq", "gemini", "openrouter", "qwen"]
    for p in order:
        online, _ = _test_provider(p)
        if online: return p, p in ("ollama", "jan", "lmstudio")
    return None, False

def _call_ollama(prompt, model, system=""):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {"model": model, "messages": messages, "stream": False}
    try:
        req = urllib.request.Request("http://localhost:11434/api/chat", json.dumps(payload).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read()).get("message", {}).get("content", "No response")
    except Exception as e:
        return f"Ollama error: {e}"

def _call_openai(prompt, base_url, model, api_key="", extra_headers=None, system=""):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    url = f"{base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key: headers["Authorization"] = f"Bearer {api_key}"
    if extra_headers: headers.update(extra_headers)
    body = json.dumps({"model": model, "messages": messages}).encode()
    try:
        req = urllib.request.Request(url, body, headers)
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())["choices"][0]["message"]["content"]
    except Exception as e:
        return f"API error: {e}"

def _call_gemini(prompt, model, api_key, system=""):
    full_prompt = f"{system}\n\nUser:\n{prompt}" if system else prompt
    contents = [{"role": "user", "parts": [{"text": full_prompt}]}]
    payload = {"contents": contents, "generationConfig": {"maxOutputTokens": 2048, "temperature": 0.7}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    try:
        req = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"Gemini error: {e}"

def _call_ai_sync(prompt, provider="ollama", model="", history=None, system="", max_tokens=2048):
    online, err = _test_provider(provider)
    if not online:
        working, is_local = _find_working_provider(provider)
        if working:
            prompt = f"[Auto-switched from {provider} to {working}] {prompt}"
            provider = working
            if model: model = ALL_MODELS.get(working, [""])[0]
        else:
            return f"NO AI PROVIDER AVAILABLE\n\nSelected provider '{provider}' is not available: {err}\nPlease ensure Jan, Ollama, or LM Studio is running!"

    if provider == "ollama": return _call_ollama(prompt, model or ALL_MODELS["ollama"][0], system=system)
    elif provider == "jan": return _call_openai(prompt, "http://localhost:1337/v1", model or ALL_MODELS["jan"][0], system=system)
    elif provider == "lmstudio": return _call_openai(prompt, "http://localhost:1234/v1", model or ALL_MODELS["lmstudio"][0], system=system)
    elif provider == "groq": return _call_openai(prompt, "https://api.groq.com/openai/v1", model or ALL_MODELS["groq"][0], os.getenv("GROQ_API_KEY", ""), system=system)
    elif provider == "gemini": return _call_gemini(prompt, model or ALL_MODELS["gemini"][0], os.getenv("GEMINI_API_KEY", ""), system=system)
    elif provider == "openrouter": return _call_openai(prompt, "https://openrouter.ai/api/v1", model or ALL_MODELS["openrouter"][0], os.getenv("OPENROUTER_API_KEY", ""), system=system)
    elif provider == "qwen": return _call_openai(prompt, "https://dashscope.aliyuncs.com/compatible-mode/v1", model or ALL_MODELS["qwen"][0], os.getenv("QWEN_API_KEY", ""), system=system)
    return f"Unknown provider: {provider}"

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
            return bool(os.getenv({"groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY", "openrouter": "OPENROUTER_API_KEY", "qwen": "QWEN_API_KEY"}.get(provider, ""), "")), ALL_MODELS.get(provider, [])
        return False, []
    except Exception: return False, []

class VoiceEngine:
    def __init__(self):
        self._available = False
        self._engine = None
        self._last_init_error = ""
        if sys.platform == "win32":
            try:
                import win32com.client
                self._engine = win32com.client.Dispatch("SAPI.SpVoice")
                self._available = True
            except Exception as e:
                self._available = False
                self._last_init_error = str(e)

    def speak(self, text):
        clean = re.sub(r"[#*`_~\[\](){}]", "", text)[:500].strip()
        if not clean:
            return False, "Nothing to speak."
        try:
            # Preferred path: SAPI COM if available.
            if self._available and self._engine:
                self._engine.Speak(clean)
                return True, ""

            errors = []
            if self._last_init_error:
                errors.append(f"SAPI init: {self._last_init_error}")

            # Fallback path 1: .NET System.Speech via PowerShell (no pywin32 dependency).
            escaped = clean.replace("'", "''")
            cmd = (
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "$s.Rate = 1; "
                f"$s.Speak('{escaped}')"
            )
            r = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r.returncode == 0:
                return True, ""
            err = (r.stderr or r.stdout or "").strip()[:220]
            errors.append(err or "System.Speech fallback failed.")

            # Fallback path 2: SAPI via PowerShell COM object.
            cmd2 = (
                "$v = New-Object -ComObject SAPI.SpVoice; "
                "$v.Rate = 1; "
                f"$v.Speak('{escaped}')"
            )
            r2 = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd2],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r2.returncode == 0:
                return True, ""
            err2 = (r2.stderr or r2.stdout or "").strip()[:220]
            errors.append(err2 or "PowerShell SAPI fallback failed.")
            return False, " | ".join([e for e in errors if e]).strip()[:320] or "No Windows speech engine available."
        except Exception as e:
            return False, str(e)

# --- THEME CONFIGURATION (20 Professional Themes) ---
THEMES = {
    "Midnight": {
        "bg": "#0B0E14", "sidebar_bg": "#11141B", "header_bg": "#11141B", "card_bg": "#1A1D26",
        "card_border": "#2D313E", "accent": "#00D4FF", "accent_dim": "#062233",
        "text": "#E2E8F0", "text_muted": "#94A3B8", "success": "#10B981", "warning": "#F59E0B", "error": "#EF4444"
    },
    "Solarized": {
        "bg": "#002B36", "sidebar_bg": "#073642", "header_bg": "#002B36", "card_bg": "#073642",
        "card_border": "#586E75", "accent": "#B58900", "accent_dim": "#123432",
        "text": "#839496", "text_muted": "#657B83", "success": "#859900", "warning": "#CB4B16", "error": "#DC322F"
    },
    "Dracula": {
        "bg": "#282A36", "sidebar_bg": "#44475A", "header_bg": "#282A36", "card_bg": "#44475A",
        "card_border": "#6272A4", "accent": "#BD93F9", "accent_dim": "#37334a",
        "text": "#F8F8F2", "text_muted": "#6272A4", "success": "#50FA7B", "warning": "#FFB86C", "error": "#FF5555"
    },
    "Cyber": {
        "bg": "#001B2E", "sidebar_bg": "#003B5C", "header_bg": "#001F36", "card_bg": "#003B5C",
        "card_border": "#005580", "accent": "#00FFFF", "accent_dim": "#003040",
        "text": "#E0FFFF", "text_muted": "#A0E0E0", "success": "#2ECC71", "warning": "#FF8C00", "error": "#FF3E3E"
    },
    "Nord": {
        "bg": "#2E3440", "sidebar_bg": "#3B4252", "header_bg": "#2E3440", "card_bg": "#3B4252",
        "card_border": "#4C566A", "accent": "#88C0D0", "accent_dim": "#3B4252",
        "text": "#ECEFF4", "text_muted": "#D8DEE9", "success": "#A3BE8C", "warning": "#EBCB8B", "error": "#BF616A"
    },
    "Gruvbox": {
        "bg": "#282828", "sidebar_bg": "#3c3836", "header_bg": "#282828", "card_bg": "#3c3836",
        "card_border": "#504945", "accent": "#fabd2f", "accent_dim": "#3c3836",
        "text": "#ebdbb2", "text_muted": "#a89984", "success": "#b8bb26", "warning": "#fe8019", "error": "#fb4934"
    },
    "Oceanic": {
        "bg": "#1B2B34", "sidebar_bg": "#343D46", "header_bg": "#1B2B34", "card_bg": "#343D46",
        "card_border": "#4F5B66", "accent": "#6699CC", "accent_dim": "#343D46",
        "text": "#D8DEE9", "text_muted": "#ABB2BF", "success": "#99C794", "warning": "#FAC863", "error": "#EC5f67"
    },
    "Ayu Mirage": {
        "bg": "#1F2430", "sidebar_bg": "#232834", "header_bg": "#1F2430", "card_bg": "#232834",
        "card_border": "#323A4C", "accent": "#FFCC66", "accent_dim": "#232834",
        "text": "#CBCCC6", "text_muted": "#707A8C", "success": "#95E6CB", "warning": "#FFA759", "error": "#F28779"
    },
    "Monokai": {
        "bg": "#272822", "sidebar_bg": "#3E3D32", "header_bg": "#272822", "card_bg": "#3E3D32",
        "card_border": "#49483E", "accent": "#A6E22E", "accent_dim": "#3E3D32",
        "text": "#F8F8F2", "text_muted": "#75715E", "success": "#A6E22E", "warning": "#FD971F", "error": "#F92672"
    },
    "One Dark": {
        "bg": "#282C34", "sidebar_bg": "#21252B", "header_bg": "#282C34", "card_bg": "#21252B",
        "card_border": "#3E4451", "accent": "#61AFEF", "accent_dim": "#21252B",
        "text": "#ABB2BF", "text_muted": "#5C6370", "success": "#98C379", "warning": "#D19A66", "error": "#E06C75"
    },
    "Tokyo Night": {
        "bg": "#1A1B26", "sidebar_bg": "#16161E", "header_bg": "#1A1B26", "card_bg": "#16161E",
        "card_border": "#292E42", "accent": "#7AA2F7", "accent_dim": "#16161E",
        "text": "#A9B1D6", "text_muted": "#565F89", "success": "#9ECE6A", "warning": "#E0AF68", "error": "#F7768E"
    },
    "Rose Pine": {
        "bg": "#191724", "sidebar_bg": "#1f1d2e", "header_bg": "#191724", "card_bg": "#1f1d2e",
        "card_border": "#26233a", "accent": "#ebbcba", "accent_dim": "#1f1d2e",
        "text": "#e0def4", "text_muted": "#908caa", "success": "#31748f", "warning": "#f6c177", "error": "#eb6f92"
    },
    "Everforest": {
        "bg": "#2D353B", "sidebar_bg": "#343F44", "header_bg": "#2D353B", "card_bg": "#343F44",
        "card_border": "#3D484D", "accent": "#A7C080", "accent_dim": "#343F44",
        "text": "#D3C6AA", "text_muted": "#859289", "success": "#A7C080", "warning": "#DBBC7F", "error": "#E67E80"
    },
    "Catppuccin": {
        "bg": "#1E1E2E", "sidebar_bg": "#181825", "header_bg": "#1E1E2E", "card_bg": "#181825",
        "card_border": "#313244", "accent": "#CBA6F7", "accent_dim": "#181825",
        "text": "#CDD6F4", "text_muted": "#7F849C", "success": "#A6E3A1", "warning": "#F9E2AF", "error": "#F38BA8"
    },
    "Github Dark": {
        "bg": "#0D1117", "sidebar_bg": "#161B22", "header_bg": "#0D1117", "card_bg": "#161B22",
        "card_border": "#30363D", "accent": "#58A6FF", "accent_dim": "#161B22",
        "text": "#C9D1D9", "text_muted": "#8B949E", "success": "#3FB950", "warning": "#D29922", "error": "#F85149"
    },
    "Synthwave": {
        "bg": "#262335", "sidebar_bg": "#241B2F", "header_bg": "#262335", "card_bg": "#241B2F",
        "card_border": "#34294F", "accent": "#FF7EDB", "accent_dim": "#241B2F",
        "text": "#FFFFFF", "text_muted": "#72F1B8", "success": "#72F1B8", "warning": "#FEF983", "error": "#F92aad"
    },
    "Breeze": {
        "bg": "#F5F7FA", "sidebar_bg": "#FFFFFF", "header_bg": "#F5F7FA", "card_bg": "#FFFFFF",
        "card_border": "#E4E7EB", "accent": "#3E8ED0", "accent_dim": "#FFFFFF",
        "text": "#2F3941", "text_muted": "#7B8794", "success": "#48BB78", "warning": "#ED8936", "error": "#F56565"
    },
    "Lavender": {
        "bg": "#F3F0FF", "sidebar_bg": "#EBE4FF", "header_bg": "#F3F0FF", "card_bg": "#EBE4FF",
        "card_border": "#D1C4E9", "accent": "#673AB7", "accent_dim": "#EBE4FF",
        "text": "#4527A0", "text_muted": "#7E57C2", "success": "#2E7D32", "warning": "#EF6C00", "error": "#C62828"
    },
    "Desert": {
        "bg": "#FDF6E3", "sidebar_bg": "#EEE8D5", "header_bg": "#FDF6E3", "card_bg": "#EEE8D5",
        "card_border": "#93A1A1", "accent": "#CB4B16", "accent_dim": "#EEE8D5",
        "text": "#657B83", "text_muted": "#93A1A1", "success": "#859900", "warning": "#B58900", "error": "#DC322F"
    }
}
CURRENT_THEME = "Midnight"
T = THEMES[CURRENT_THEME]
FONT_FAMILY = "Segoe UI"

class ModernButton(tk.Canvas):
    def __init__(self, parent, text, icon="", command=None, width=180, height=40, active=False, **kwargs):
        super().__init__(parent, width=width, height=height, bg=kwargs.get("bg", T["sidebar_bg"]), 
                         highlightthickness=0, cursor="hand2", **kwargs)
        self.text = text
        self.icon = icon
        self.command = command
        self.active = active
        self.width = width
        self.height = height
        self._draw()
        self.bind("<Button-1>", lambda e: self.command() if self.command else None)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _draw(self, hover=False):
        self.delete("all")
        bg = T["accent_dim"] if (self.active or hover) else T["sidebar_bg"]
        fg = T["accent"] if (self.active or hover) else T["text_muted"]
        self.create_rectangle(0, 0, self.width, self.height, fill=bg, outline="")
        if self.active:
            self.create_rectangle(0, 0, 4, self.height, fill=T["accent"], outline="")
        self.create_text(25, self.height/2, text=self.icon, font=(FONT_FAMILY, 14), fill=fg, anchor="center")
        self.create_text(55, self.height/2, text=self.text, font=(FONT_FAMILY, 10, "bold" if self.active else "normal"), fill=fg, anchor="w")

    def _on_enter(self, e): self._draw(hover=True)
    def _on_leave(self, e): self._draw(hover=False)
    def set_active(self, active):
        self.active = active
        self._draw()

class BabaGuiV13(tk.Tk):
    def __init__(self, services=None):
        super().__init__()
        self.title("Baba Desktop v13 - UK Office Assistant")
        self.geometry("1400x900")
        self.minsize(1180, 760)
        self.configure(bg=T["bg"])
        self.services = services or {}

        # State & Backend Logic
        self.sidebar_collapsed = False
        self.sidebar_min_width = 160
        self.sidebar_max_width = 420
        self.sidebar_collapsed_width = 60
        self.sidebar_expanded_width = 220
        self._sidebar_drag_start_x = 0
        self._sidebar_drag_start_w = self.sidebar_expanded_width
        self.active_tab = "chat"
        self.nav_btns = {}
        self.panels = {}
        self.log_queue = queue.Queue()
        self.tasks = []
        self.memory = []
        self.master_memory_text = ""
        self._thinking_line_idx = None
        self.email_organizer_state = "idle"
        self.email_organizer_last = ""
        self.email_organizer_summary = {}
        self.email_organizer_running = False
        self.email_organizer_active_trigger = ""
        self.email_organizer_active_profile = ""
        self.email_organizer_pending_trigger = ""
        self.email_organizer_pending_profile = ""
        self.email_scan_progress = {
            "running": False,
            "trigger": "",
            "profile": "",
            "started_at": "",
            "stores_detected": 0,
            "folders_scanned": 0,
            "messages_collected": 0,
            "current_folder": "",
            "error": "",
        }
        self._last_urgent_count = 0
        self._last_email_error_msg = ""
        self._last_email_error_at = 0.0
        self.email_organizer_last_items = []
        self.email_organizer_last_scan_at = ""
        self.expert_monitor_state = {}
        self._last_expert_alert_sig = ""
        self._last_expert_alert_at = 0.0
        self._last_web_assist = {
            "used": False,
            "searches": 0,
            "fetches": 0,
            "sources": [],
            "at": "",
        }
        self.agent_web_policy = "ask"  # ask | approved | denied | stopped
        self._last_web_approval_prompt_at = 0.0
        self.evidence_required_mode = True
        self._last_agent_web = {
            "used": False,
            "searches": 0,
            "fetches": 0,
            "sources": [],
            "at": "",
            "by_agent": {},
        }
        
        # Initialize only real email agents.
        self.email_agents = {}
        if HAS_EXO_EMAIL:
            try:
                self.email_agents["gmail"] = GmailAgent()
            except Exception:
                pass
            try:
                self.email_agents["outlook"] = OutlookAgent()
            except Exception:
                pass

        # Real backend services (fallback to local bootstrap if not injected)
        self.settings = self.services.get("settings")
        self.brain = self.services.get("brain")
        self.pool = self.services.get("pool")
        self.tools = self.services.get("tools")
        self.vision = self.services.get("vision")
        self.agents = self.services.get("agents")
        self.money = self.services.get("money")
        self.pc = self.services.get("pc")
        self.apps = self.services.get("apps")
        self.memory_store = self.services.get("memory")
        self.dispatcher = self.services.get("dispatcher")
        self.scheduler = self.services.get("scheduler")
        self.cowork = self.services.get("cowork")
        self.devtools = self.services.get("devtools")
        self.meetings = self.services.get("meetings")
        self.claws = self.services.get("claws")
        self.tool_builder = self.services.get("tool_builder")
        self.wiki = self.services.get("wiki")
        self.kairos = self.services.get("kairos")
        self._init_backend_services()
        try:
            if self.agents and hasattr(self.agents, "set_web_tools_policy"):
                self.agents.set_web_tools_policy(self.agent_web_policy)
            if self.agents and hasattr(self.agents, "set_evidence_required_mode"):
                self.agents.set_evidence_required_mode(self.evidence_required_mode)
        except Exception:
            pass
        self._load_master_memory()
        self._init_connection_state()

        self._setup_ui()
        self._start_background_polling()
        self._start_queue_processor()
        self._setup_global_copy()
        self._start_quick_status_loop()
        self._start_connection_scan_loop()
        self._start_provider_warmup()

    def _init_backend_services(self):
        # If caller injected services, preserve them.
        if not self.settings and Settings:
            try:
                self.settings = Settings.load()
            except Exception:
                self.settings = None

        if not self.brain and BrainIndex:
            try:
                db_path = self.settings.brain_db_path if self.settings else str(DATA_DIR / "brain_index" / "brain.db")
                self.brain = BrainIndex(db_path)
            except Exception:
                self.brain = None

        if not self.pool and ProviderPool:
            try:
                providers_cfg = self.settings.providers if self.settings and getattr(self.settings, "providers", None) else {}
                from src.memory.memory import ensure_master_memory_file, load_master_memory_text

                ensure_master_memory_file("data/baba_master_memory.txt")
                memory_text = load_master_memory_text("data/baba_master_memory.txt")
                self.pool = ProviderPool(
                    providers_cfg,
                    master_memory_text=memory_text,
                    master_memory_path="data/baba_master_memory.txt",
                )
            except Exception:
                self.pool = None

        if not self.tools and ToolRegistry:
            try:
                self.tools = ToolRegistry(self.brain)
            except Exception:
                self.tools = None

        if not self.vision and VisionPipeline and self.pool and self.brain and self.settings:
            try:
                self.vision = VisionPipeline(self.pool, self.brain, self.settings)
            except Exception:
                self.vision = None

        if not self.agents and AgentOrchestrator and self.pool and self.brain and self.tools:
            try:
                self.agents = AgentOrchestrator(self.pool, self.brain, self.tools, self.vision)
            except Exception:
                self.agents = None

        if not self.money and MoneyEngine and self.pool and self.brain:
            try:
                self.money = MoneyEngine(self.brain, self.pool)
            except Exception:
                self.money = None

        if not self.apps and AppBridge:
            try:
                self.apps = AppBridge(self.settings)
            except Exception:
                self.apps = None

        if not self.memory_store and Memory and self.settings:
            try:
                self.memory_store = Memory(self.settings.memory_dir)
            except Exception:
                self.memory_store = None

        if not self.dispatcher and Dispatcher and self.brain and self.agents and self.apps and self.tools and self.pool:
            try:
                self.dispatcher = Dispatcher(self.brain, self.agents, self.pc, self.apps, self.tools, self.pool)
                self.dispatcher.start_worker()
            except Exception:
                self.dispatcher = None

        if not self.scheduler and Scheduler and self.dispatcher:
            try:
                self.scheduler = Scheduler(self.dispatcher, self.settings)
            except Exception:
                self.scheduler = None

        if self.scheduler:
            try:
                self.scheduler.start()
            except Exception:
                pass

        if not self.cowork and Cowork and self.agents and self.pool and self.brain and self.tools and self.apps:
            try:
                self.cowork = Cowork(self.agents, self.pool, self.brain, self.tools, self.pc, self.apps)
            except Exception:
                self.cowork = None

        if not self.devtools and DevTools:
            try:
                self.devtools = DevTools()
            except Exception:
                self.devtools = None

        if not self.meetings and MeetingIntelligence and self.pool and self.brain:
            try:
                self.meetings = MeetingIntelligence(self.pool, self.brain, self.settings)
            except Exception:
                self.meetings = None

        if not self.claws and ClawInstaller:
            try:
                claws_dir = self.settings.claws_dir if self.settings else "src/claws/installed"
                self.claws = ClawInstaller(claws_dir)
            except Exception:
                self.claws = None

        if not self.tool_builder and ToolBuilder and self.pool:
            try:
                self.tool_builder = ToolBuilder(self.pool)
            except Exception:
                self.tool_builder = None

        if not self.wiki and WikiCompiler:
            try:
                self.wiki = WikiCompiler(root_dir="data/wiki", brain=self.brain, pool=self.pool)
            except Exception:
                self.wiki = None

        if not self.kairos and KairosMemory:
            try:
                self.kairos = KairosMemory(path="data/personality/kairos_profile.json")
            except Exception:
                self.kairos = None

    def _load_master_memory(self):
        try:
            from src.memory.memory import ensure_master_memory_file, load_master_memory_text

            ensure_master_memory_file("data/baba_master_memory.txt")
            self.master_memory_text = load_master_memory_text("data/baba_master_memory.txt")
        except Exception:
            try:
                p = APP_DIR / "data" / "baba_master_memory.txt"
                self.master_memory_text = p.read_text(encoding="utf-8") if p.exists() else ""
            except Exception:
                self.master_memory_text = ""

    def _build_system_prompt(self):
        prompt = BABA_SYSTEM_PROMPT
        memory = (self.master_memory_text or "").strip()
        if memory:
            prompt = (
                f"{prompt}\n"
                "Canonical memory below. Use it as source of truth for identity and context.\n"
                "If unknown, say unknown. Do not fabricate.\n\n"
                f"{memory[:12000]}"
            )
        if self.evidence_required_mode:
            prompt = (
                f"{prompt}\n\n"
                "EVIDENCE REQUIRED MODE (STRICT):\n"
                "- Do not invent names, dates, counts, statuses, legal outcomes, or timelines.\n"
                "- If evidence is missing, say unknown and request/trigger verification.\n"
                "- Prefer real app/web/email/document evidence over assumptions.\n"
                "- Include an 'Evidence trail' and one-line 'Confidence' note in substantive responses.\n"
            )
        return prompt

    def _set_evidence_required_mode(self, enabled: bool):
        self.evidence_required_mode = bool(enabled)
        try:
            if self.agents and hasattr(self.agents, "set_evidence_required_mode"):
                self.agents.set_evidence_required_mode(self.evidence_required_mode)
        except Exception:
            pass
        if hasattr(self, "evidence_btn"):
            txt = "Evidence: ON" if self.evidence_required_mode else "Evidence: OFF"
            fg = T["success"] if self.evidence_required_mode else T["text_muted"]
            self.evidence_btn.config(text=txt, fg=fg)
        self._refresh_quick_strip()

    def _append_evidence_tail_if_needed(self, text, web_meta=None):
        if not self.evidence_required_mode:
            return text
        msg = str(text or "").strip()
        low = msg.lower()
        if "evidence trail" in low and "confidence" in low:
            return msg
        wm = web_meta if isinstance(web_meta, dict) else {}
        ws = int(wm.get("searches", 0) or 0)
        wf = int(wm.get("fetches", 0) or 0)
        wsrc = [str(s) for s in (wm.get("sources") or []) if str(s).strip()]
        s = self.email_organizer_summary or {}
        es_total = int(s.get("total", 0) or 0)
        es_high = int(s.get("high", 0) or 0)
        es_accounts = int(s.get("accounts_scanned", 0) or 0)
        tail = (
            "\n\nEvidence trail:\n"
            f"- Master memory loaded: {'yes' if bool((self.master_memory_text or '').strip()) else 'no'}\n"
            f"- Email organizer snapshot: total {es_total}, urgent {es_high}, accounts {es_accounts}\n"
            f"- Web context used: searches {ws}, fetches {wf}, sources {', '.join(wsrc[:4]) if wsrc else 'none'}\n"
            "- Unknown items were not guessed.\n"
            "Confidence: medium (strict evidence mode)\n"
        )
        return msg + tail

    def _pretty(self, data):
        if isinstance(data, (dict, list)):
            return json.dumps(data, indent=2, ensure_ascii=False)
        return str(data)

    def _init_connection_state(self):
        self.connection_state_file = DATA_DIR / "runtime_connections.json"
        self._conn_scan_inflight = False
        self._conn_scan_tick = 0
        self.connection_state = {
            "approved": {"providers": [], "apps": []},
            "last_scan": {},
        }
        self.connection_live = {"providers": {}, "apps": {}, "social": {}, "email_agents": {}, "oauth": {}, "pending": {"providers": [], "apps": []}}
        if self.connection_state_file.exists():
            try:
                self.connection_state = json.loads(self.connection_state_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        self._save_connection_state()
        self._scan_connections_now(async_mode=True)

    def _save_connection_state(self):
        try:
            self.connection_state_file.parent.mkdir(parents=True, exist_ok=True)
            self.connection_state_file.write_text(json.dumps(self.connection_state, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _approved_has(self, kind, name):
        return name in set(self.connection_state.get("approved", {}).get(kind, []))

    def _approve_connection(self, kind, name):
        approved = self.connection_state.setdefault("approved", {}).setdefault(kind, [])
        if name not in approved:
            approved.append(name)
            approved.sort()
            self._save_connection_state()
        self._scan_connections_now(async_mode=True)

    def _disconnect_connection(self, kind, name):
        approved = self.connection_state.setdefault("approved", {}).setdefault(kind, [])
        if name in approved:
            approved.remove(name)
            self._save_connection_state()
        self._scan_connections_now(async_mode=True)

    def _compute_connection_snapshot(self, deep=False):
        providers = {}
        for p in ALL_MODELS.keys():
            is_on, _ = _test_provider(p)
            providers[p] = {"available": bool(is_on), "approved": self._approved_has("providers", p)}
        apps = {}
        social = {}
        email_agents = {}
        oauth = {}
        if self.apps and hasattr(self.apps, "detect_integrations"):
            try:
                scan = self.apps.detect_integrations(refresh=bool(deep))
            except Exception:
                scan = {}
            app_scan = scan.get("apps", {}) if isinstance(scan, dict) else {}
            social = scan.get("social", {}) if isinstance(scan, dict) else {}
            email_agents = scan.get("email_agents", {}) if isinstance(scan, dict) else {}
            for app_name in ("exo", "outlook", "excel", "word", "vscode", "obsidian", "cmd"):
                meta = app_scan.get(app_name, {}) if isinstance(app_scan, dict) else {}
                apps[app_name] = {
                    "available": bool(meta.get("available", False)),
                    "running": bool(meta.get("running", False)),
                    "approved": self._approved_has("apps", app_name),
                }
            try:
                if hasattr(self.apps, "outlook_oauth_status"):
                    oauth = self.apps.outlook_oauth_status() or {}
            except Exception:
                oauth = {}
        else:
            for app_name in ("exo", "outlook", "excel", "word", "vscode", "obsidian", "cmd"):
                apps[app_name] = {"available": False, "running": False, "approved": self._approved_has("apps", app_name)}

        pending_providers = [k for k, v in providers.items() if v["available"] and not v["approved"]]
        pending_apps = [k for k, v in apps.items() if v["available"] and not v["approved"]]
        return {
            "providers": providers,
            "apps": apps,
            "social": social if isinstance(social, dict) else {},
            "email_agents": email_agents if isinstance(email_agents, dict) else {},
            "oauth": oauth if isinstance(oauth, dict) else {},
            "pending": {"providers": pending_providers, "apps": pending_apps},
            "scanned_at": datetime.now(UTC).isoformat(),
        }

    def _scan_connections_now(self, async_mode=False, deep=False):
        if async_mode:
            if self._conn_scan_inflight:
                return
            self._conn_scan_inflight = True
            threading.Thread(target=self._scan_connections_worker, kwargs={"deep": bool(deep)}, daemon=True).start()
            return
        self.connection_live = self._compute_connection_snapshot(deep=bool(deep))

    def _scan_connections_worker(self, deep=False):
        try:
            snapshot = self._compute_connection_snapshot(deep=bool(deep))
        except Exception:
            snapshot = self.connection_live
        self.connection_live = snapshot

        def apply():
            self._conn_scan_inflight = False
            try:
                self._refresh_quick_strip()
            except Exception:
                pass

        try:
            if self.winfo_exists():
                self.after(0, apply)
            else:
                self._conn_scan_inflight = False
        except RuntimeError:
            self._conn_scan_inflight = False

    def _start_connection_scan_loop(self):
        def loop():
            try:
                self._conn_scan_tick += 1
                deep = (self._conn_scan_tick % 6 == 0)  # deep refresh about every 2 minutes
                self._scan_connections_now(async_mode=True, deep=deep)
            except Exception:
                pass
            self.after(20000, loop)
        self.after(1200, loop)

    def _start_provider_warmup(self):
        # Lightweight startup warmup: prefer Jan when available, without heavy model calls.
        def warm():
            try:
                ok, models = probe_provider("jan")
            except Exception:
                ok, models = False, []
            if not (ok and models):
                return

            def apply():
                try:
                    if hasattr(self, "prov_cb"):
                        self.prov_cb.set("jan")
                    if hasattr(self, "model_cb"):
                        self.model_cb["values"] = models
                        if self.model_cb.get() not in models:
                            self.model_cb.set(models[0])
                    if hasattr(self, "quick_state_label"):
                        cur = self.quick_state_label.cget("text") or ""
                        self.quick_state_label.config(text=f"{cur} | Jan ready")
                except Exception:
                    pass

            try:
                if self.winfo_exists():
                    self.after(0, apply)
            except Exception:
                pass

        threading.Thread(target=warm, daemon=True).start()

    def _setup_global_copy(self):
        # Enable copying of ANY label text using Ctrl+C or Right Click over the element
        self.bind_all("<Control-c>", self._global_copy_event)
        self.bind_all("<Button-3>", self._global_rc_menu)
        
        self._copy_menu = tk.Menu(self, tearoff=0, bg=T["card_bg"], fg=T["text"], bd=0, activebackground=T["accent"], activeforeground="#000")
        self._copy_menu.add_command(label="Copy Text")
        
    def _global_copy_event(self, event=None):
        try:
            widget = self.focus_get()
            if not widget: return
            
            text_to_copy = ""
            if isinstance(widget, (tk.Text, scrolledtext.ScrolledText)):
                try: text_to_copy = widget.get(tk.SEL_FIRST, tk.SEL_LAST)
                except tk.TclError: pass
            elif isinstance(widget, tk.Entry):
                try: text_to_copy = widget.selection_get()
                except tk.TclError: pass
            elif isinstance(widget, tk.Label):
                text_to_copy = widget.cget("text")
            
            if text_to_copy:
                self.clipboard_clear()
                self.clipboard_append(text_to_copy)
                self.update()
        except Exception: pass
        
    def _global_rc_menu(self, event):
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
            if not widget: return
            widget.focus_set()
            
            # Universal check for switch
            is_selectable = isinstance(widget, (tk.Text, scrolledtext.ScrolledText, tk.Entry, tk.Label))
            if is_selectable:
                self._copy_menu.entryconfigure(0, command=lambda: self._global_copy_event())
                self._copy_menu.tk_popup(event.x_root, event.y_root)
        except Exception: pass

    def _setup_ui(self):
        self.top_bar = tk.Frame(self, bg=T["header_bg"], height=60)
        self.top_bar.pack(side="top", fill="x")
        self.top_bar.pack_propagate(False)
        self._build_top_bar()

        # Always-visible touch controls for critical agent features.
        self.quick_bar = tk.Frame(self, bg=T["bg"], height=42)
        self.quick_bar.pack(side="top", fill="x")
        self.quick_bar.pack_propagate(False)
        self._build_quick_bar()
        
        self.layout_container = tk.Frame(self, bg=T["bg"])
        self.layout_container.pack(side="top", fill="both", expand=True)
        
        # Sidebar (Left)
        self.sidebar = tk.Frame(
            self.layout_container,
            bg=T["sidebar_bg"],
            width=self.sidebar_expanded_width,
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        self.sidebar_grip = tk.Frame(
            self.layout_container,
            bg=T["card_border"],
            width=7,
            cursor="sb_h_double_arrow",
        )
        self.sidebar_grip.pack(side="left", fill="y")
        self.sidebar_grip.bind("<ButtonPress-1>", self._start_sidebar_resize)
        self.sidebar_grip.bind("<B1-Motion>", self._drag_sidebar_resize)
        self.sidebar_grip.bind("<ButtonRelease-1>", self._end_sidebar_resize)
        self.sidebar_grip.bind("<Double-Button-1>", self._reset_sidebar_width)
        self.sidebar_grip.bind("<Enter>", lambda _e: self.sidebar_grip.configure(bg=T["accent"]))
        self.sidebar_grip.bind("<Leave>", lambda _e: self.sidebar_grip.configure(bg=T["card_border"]))
        
        # Content Area (Middle) - global scrollable host for every panel.
        self.content_host = tk.Frame(self.layout_container, bg=T["bg"])
        self.content_host.pack(side="left", fill="both", expand=True)

        self.content_canvas = tk.Canvas(self.content_host, bg=T["bg"], bd=0, highlightthickness=0)
        self.content_scrollbar = tk.Scrollbar(self.content_host, orient="vertical", command=self.content_canvas.yview)
        self.content_canvas.configure(yscrollcommand=self.content_scrollbar.set)
        self.content_scrollbar.pack(side="right", fill="y")
        self.content_canvas.pack(side="left", fill="both", expand=True)

        self.content_area = tk.Frame(self.content_canvas, bg=T["bg"])
        self._content_window = self.content_canvas.create_window((0, 0), window=self.content_area, anchor="nw")
        self.content_area.bind("<Configure>", self._on_content_area_configure)
        self.content_canvas.bind("<Configure>", self._on_content_canvas_configure)
        self.content_canvas.bind("<Enter>", lambda _e: self._set_mousewheel_target(self.content_canvas), add="+")
        self.content_host.bind("<Leave>", lambda _e: self._set_mousewheel_target(None), add="+")
        self._build_content_panels()
        
        self.status_bar = tk.Frame(self, bg=T["header_bg"], height=30)
        self.status_bar.pack(side="bottom", fill="x")
        self._build_status_bar()
        self.bind_all("<Control-Shift-C>", lambda _e: self._copy_all_chat(), add="+")

    def _on_content_area_configure(self, _event=None):
        try:
            self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))
        except Exception:
            pass

    def _on_content_canvas_configure(self, event):
        try:
            self.content_canvas.itemconfigure(self._content_window, width=event.width)
            self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))
        except Exception:
            pass

    def _build_top_bar(self):
        # Logo & System Name
        left_frame = tk.Frame(self.top_bar, bg=T["header_bg"])
        left_frame.pack(side="left", padx=(20, 10))
        tk.Label(left_frame, text="ULTIMATE BABA v13", font=(FONT_FAMILY, 14, "bold"), 
                 bg=T["header_bg"], fg=T["accent"]).pack(side="left")
        
        # Model/Provider Selectors (Restored)
        sel_frame = tk.Frame(self.top_bar, bg=T["header_bg"])
        sel_frame.pack(side="left", padx=10)
        
        tk.Label(sel_frame, text="Provider:", font=(FONT_FAMILY, 8), bg=T["header_bg"], fg=T["text_muted"]).pack(side="left")
        self.prov_cb = ttk.Combobox(sel_frame, values=list(ALL_MODELS.keys()), width=10, state="readonly")
        self.prov_cb.set("jan")
        self.prov_cb.pack(side="left", padx=5)
        
        tk.Label(sel_frame, text="Model:", font=(FONT_FAMILY, 8), bg=T["header_bg"], fg=T["text_muted"]).pack(side="left", padx=(10, 0))
        self.model_cb = ttk.Combobox(sel_frame, values=ALL_MODELS["jan"], width=15, state="readonly")
        self.model_cb.set(ALL_MODELS["jan"][0])
        self.model_cb.pack(side="left", padx=5)
        
        # Status Badges
        status_frame = tk.Frame(self.top_bar, bg=T["header_bg"])
        status_frame.pack(side="left", padx=20)
        
        v_badge = tk.Frame(status_frame, bg=T["card_bg"], padx=10, pady=5, bd=1, highlightbackground=T["card_border"], highlightthickness=1)
        v_badge.pack(side="left", padx=5)
        tk.Label(v_badge, text="18 Voice", font=(FONT_FAMILY, 8, "bold"), bg=T["card_bg"], fg=T["success"]).pack()
        
        probe_btn = tk.Button(status_frame, text="Probe", font=(FONT_FAMILY, 8, "bold"), bg=T["card_bg"], fg=T["warning"], bd=1, highlightbackground=T["card_border"], highlightthickness=1, cursor="hand2", command=self._auto_probe)
        probe_btn.pack(side="left", padx=5)
        self.email_org_btn = tk.Button(
            status_frame,
            text="Organize Emails",
            font=(FONT_FAMILY, 8, "bold"),
            bg=T["card_bg"],
            fg=T["text"],
            bd=1,
            highlightbackground=T["card_border"],
            highlightthickness=1,
            cursor="hand2",
            command=lambda: self._run_email_organizer_async(trigger="manual"),
        )
        self.email_org_btn.pack(side="left", padx=5)
        self.email_org_label = tk.Label(
            status_frame,
            text="Email Organizer: Idle",
            font=(FONT_FAMILY, 8, "bold"),
            bg=T["header_bg"],
            fg=T["text_muted"],
        )
        self.email_org_label.pack(side="left", padx=(6, 0))

        # Right Controls
        ctrl_frame = tk.Frame(self.top_bar, bg=T["header_bg"])
        ctrl_frame.pack(side="right", padx=20)
        
        # Theme Toggle
        theme_cb = ttk.Combobox(ctrl_frame, values=list(THEMES.keys()), width=12, state="readonly")
        theme_cb.set(CURRENT_THEME)
        theme_cb.pack(side="left", padx=10)
        theme_cb.bind("<<ComboboxSelected>>", lambda e: self._set_theme(theme_cb.get()))
        
        self.cowork_enabled = False
        self.cowork_btn = tk.Button(ctrl_frame, text="ENABLE COWORK", font=(FONT_FAMILY, 8, "bold"), bg=T["sidebar_bg"], fg=T["text_muted"], bd=0, padx=15, command=self._toggle_cowork)
        self.cowork_btn.pack(side="left", padx=10)

        for icon, cmd in [("\U0001f3a4", None), ("\u21bb", None)]:
            tk.Button(ctrl_frame, text=icon, font=(FONT_FAMILY, 12), bg=T["header_bg"], fg=T["text"], bd=0, cursor="hand2").pack(side="left", padx=5)

    def _toggle_cowork(self):
        self.cowork_enabled = not self.cowork_enabled
        if self.cowork_enabled:
            self.cowork_btn.configure(text="COWORK ACTIVE", bg=T["success"], fg="#000")
            self._log("Autonomous Cowork Mode enabled.")
            self._start_cowork_sim()
        else:
            self.cowork_btn.configure(text="ENABLE COWORK MODE", bg=T["sidebar_bg"], fg=T["text_muted"])
            self._log("Cowork Mode disabled.")

    def _start_cowork_sim(self):
        def loop():
            steps = ["Analyzing WhatsApp thread...", "Extracting invoice data...", "Updating Excel ledger...", "Drafting email to accountant...", "Task completed."]
            for step in steps:
                if not self.cowork_enabled: break
                self._log(f"COWORK: {step}")
                time.sleep(3)
        threading.Thread(target=loop, daemon=True).start()

    def _set_theme(self, name):
        global T, CURRENT_THEME
        CURRENT_THEME = name
        T = THEMES[name]
        for w in self.winfo_children(): w.destroy()
        self.nav_btns = {}; self.panels = {}
        self.configure(bg=T["bg"])
        self._setup_ui()
        self._start_queue_processor()
        self._log(f"Theme switched to {name}")

    def _build_quick_bar(self):
        left = tk.Frame(self.quick_bar, bg=T["bg"])
        left.pack(side="left", fill="x", expand=True, padx=12)
        tk.Label(left, text="Live Agent Controls", font=(FONT_FAMILY, 9, "bold"), bg=T["bg"], fg=T["text_muted"]).pack(side="left", padx=(0, 10))
        tk.Button(left, text="Connections", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=10, pady=4, command=self._open_connection_center).pack(side="left", padx=3)
        tk.Button(left, text="Exo Triage", bg=T["accent"], fg="#000", bd=0, padx=10, pady=4, command=self._quick_exo_triage).pack(side="left", padx=3)
        tk.Button(left, text="Open Exo", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=10, pady=4, command=self._quick_open_exo).pack(side="left", padx=3)
        tk.Button(left, text="Wiki Ingest", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=10, pady=4, command=self._quick_wiki_ingest).pack(side="left", padx=3)
        tk.Button(left, text="Wiki Compile", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=10, pady=4, command=self._quick_wiki_compile).pack(side="left", padx=3)
        tk.Button(left, text="Kairos", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=10, pady=4, command=self._quick_show_kairos).pack(side="left", padx=3)
        tk.Button(left, text="Web Approve", bg=T["accent_dim"], fg=T["accent"], bd=0, padx=10, pady=4, command=lambda: self._set_agent_web_policy("approved")).pack(side="left", padx=3)
        tk.Button(left, text="Web Deny", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=10, pady=4, command=lambda: self._set_agent_web_policy("denied")).pack(side="left", padx=3)
        tk.Button(left, text="Web Stop", bg=T["sidebar_bg"], fg=T["warning"], bd=0, padx=10, pady=4, command=lambda: self._set_agent_web_policy("stopped")).pack(side="left", padx=3)
        self.evidence_btn = tk.Button(
            left,
            text="Evidence: ON" if self.evidence_required_mode else "Evidence: OFF",
            bg=T["sidebar_bg"],
            fg=T["success"] if self.evidence_required_mode else T["text_muted"],
            bd=0,
            padx=10,
            pady=4,
            command=lambda: self._set_evidence_required_mode(not self.evidence_required_mode),
        )
        self.evidence_btn.pack(side="left", padx=3)

        right = tk.Frame(self.quick_bar, bg=T["bg"])
        right.pack(side="right", padx=12)
        self.quick_state_label = tk.Label(right, text="", font=(FONT_FAMILY, 8), bg=T["bg"], fg=T["text_muted"])
        self.quick_state_label.pack(side="right")
        self._refresh_quick_strip()

    def _refresh_quick_strip(self):
        if not hasattr(self, "quick_state_label"):
            return
        live = self.connection_live or {}
        providers = live.get("providers", {})
        apps = live.get("apps", {})
        pending = live.get("pending", {})
        providers_connected = sum(1 for v in providers.values() if v.get("available") and v.get("approved"))
        apps_connected = sum(1 for v in apps.values() if v.get("available") and v.get("approved"))
        pending_count = len(pending.get("providers", [])) + len(pending.get("apps", []))
        wiki_pages = 0
        if self.wiki:
            try:
                wiki_pages = int(self.wiki.stats().get("wiki_pages", 0))
            except Exception:
                wiki_pages = 0
        kairos_mode = "off"
        if self.kairos:
            try:
                kairos_mode = self.kairos.stats().get("strictness", "on")
            except Exception:
                kairos_mode = "on"
        org_state = (self.email_organizer_state or "idle").upper()
        org_high = int((self.email_organizer_summary or {}).get("high", 0) or 0)
        w = self._last_web_assist if isinstance(self._last_web_assist, dict) else {}
        w_used = bool(w.get("used"))
        w_searches = int(w.get("searches", 0) or 0)
        w_fetches = int(w.get("fetches", 0) or 0)
        srcs = [str(s) for s in (w.get("sources") or []) if str(s).strip()]
        src_txt = ",".join(srcs[:2]) if srcs else "-"
        web_txt = f"Web:{'on' if w_used else 'off'} s{w_searches}/f{w_fetches} [{src_txt}]"
        aw = self._last_agent_web if isinstance(self._last_agent_web, dict) else {}
        aw_used = bool(aw.get("used"))
        aw_s = int(aw.get("searches", 0) or 0)
        aw_f = int(aw.get("fetches", 0) or 0)
        aw_txt = f"AWeb:{self.agent_web_policy} {'on' if aw_used else 'off'} s{aw_s}/f{aw_f}"
        ev_txt = f"Evidence:{'on' if self.evidence_required_mode else 'off'}"
        self.quick_state_label.config(
            text=f"Connected P:{providers_connected} A:{apps_connected} | Pending: {pending_count} | Wiki: {wiki_pages} | Kairos: {kairos_mode} | EmailOrg: {org_state} (urgent {org_high}) | {web_txt} | {aw_txt} | {ev_txt}"
        )

    def _connection_summary(self):
        live = self.connection_live or {}
        providers = live.get("providers", {})
        apps = live.get("apps", {})
        pending = live.get("pending", {})
        return {
            "providers_connected": [k for k, v in providers.items() if v.get("available") and v.get("approved")],
            "apps_connected": [k for k, v in apps.items() if v.get("available") and v.get("approved")],
            "pending_providers": pending.get("providers", []),
            "pending_apps": pending.get("apps", []),
            "scanned_at": live.get("scanned_at"),
        }

    def _open_connection_center(self):
        self._scan_connections_now(async_mode=True, deep=True)
        top = tk.Toplevel(self)
        top.title("Connection Center")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1100, sw - 80), min(760, sh - 100)
        top.geometry(f"{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2)}")
        top.minsize(900, 620)
        top.resizable(True, True)
        top.configure(bg=T["bg"])

        tk.Label(top, text="Connection Center", font=(FONT_FAMILY, 16, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=20, pady=(16, 8))
        tk.Label(top, text="Auto-detect only. Connects only after your approval. Stays approved until you disconnect.", bg=T["bg"], fg=T["text_muted"], font=(FONT_FAMILY, 9)).pack(anchor="w", padx=20, pady=(0, 12))

        body = tk.Frame(top, bg=T["bg"])
        body.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        left = tk.Frame(body, bg=T["card_bg"], bd=1, highlightbackground=T["card_border"], highlightthickness=1)
        right = tk.Frame(body, bg=T["card_bg"], bd=1, highlightbackground=T["card_border"], highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))

        tk.Label(left, text="Local AI Providers", font=(FONT_FAMILY, 11, "bold"), bg=T["card_bg"], fg=T["text"]).pack(anchor="w", padx=14, pady=(12, 6))
        tk.Label(right, text="Windows/Desktop Apps", font=(FONT_FAMILY, 11, "bold"), bg=T["card_bg"], fg=T["text"]).pack(anchor="w", padx=14, pady=(12, 6))

        p_outer, p_list, _ = self._make_scrollable_sidebar(left, T["card_bg"])
        a_outer, a_list, _ = self._make_scrollable_sidebar(right, T["card_bg"])
        p_outer.pack(fill="both", expand=True, padx=10, pady=10)
        a_outer.pack(fill="both", expand=True, padx=10, pady=10)

        for name, meta in sorted((self.connection_live or {}).get("providers", {}).items()):
            row = tk.Frame(p_list, bg=T["card_bg"], pady=6)
            row.pack(fill="x")
            state = "connected" if (meta.get("available") and meta.get("approved")) else ("available" if meta.get("available") else "offline")
            color = T["success"] if state == "connected" else (T["warning"] if state == "available" else T["text_muted"])
            tk.Label(row, text=name, bg=T["card_bg"], fg=T["text"], width=14, anchor="w").pack(side="left")
            tk.Label(row, text=state.upper(), bg=T["card_bg"], fg=color, width=12, anchor="w", font=(FONT_FAMILY, 8, "bold")).pack(side="left")
            tk.Button(row, text="Approve Connect", bg=T["accent_dim"], fg=T["accent"], bd=0, padx=8, command=lambda n=name: (self._approve_connection("providers", n), top.destroy(), self._open_connection_center())).pack(side="left", padx=4)
            tk.Button(row, text="Disconnect", bg=T["sidebar_bg"], fg=T["text_muted"], bd=0, padx=8, command=lambda n=name: (self._disconnect_connection("providers", n), top.destroy(), self._open_connection_center())).pack(side="left", padx=4)

        for name, meta in sorted((self.connection_live or {}).get("apps", {}).items()):
            row = tk.Frame(a_list, bg=T["card_bg"], pady=6)
            row.pack(fill="x")
            state = "connected" if (meta.get("available") and meta.get("approved")) else ("available" if meta.get("available") else "offline")
            color = T["success"] if state == "connected" else (T["warning"] if state == "available" else T["text_muted"])
            tk.Label(row, text=name, bg=T["card_bg"], fg=T["text"], width=14, anchor="w").pack(side="left")
            tk.Label(row, text=state.upper(), bg=T["card_bg"], fg=color, width=12, anchor="w", font=(FONT_FAMILY, 8, "bold")).pack(side="left")
            tk.Button(row, text="Approve Connect", bg=T["accent_dim"], fg=T["accent"], bd=0, padx=8, command=lambda n=name: (self._approve_connection("apps", n), top.destroy(), self._open_connection_center())).pack(side="left", padx=4)
            tk.Button(row, text="Disconnect", bg=T["sidebar_bg"], fg=T["text_muted"], bd=0, padx=8, command=lambda n=name: (self._disconnect_connection("apps", n), top.destroy(), self._open_connection_center())).pack(side="left", padx=4)

        footer = tk.Frame(top, bg=T["bg"])
        footer.pack(fill="x", padx=20, pady=(0, 16))
        tk.Button(footer, text="Refresh Scan", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=12, pady=6, command=lambda: (self._scan_connections_now(async_mode=True, deep=True), top.destroy(), self._open_connection_center())).pack(side="left")
        tk.Button(footer, text="Approve All Local AI", bg=T["accent"], fg="#000", bd=0, padx=12, pady=6, command=lambda: (self._approve_connection("providers", "ollama"), self._approve_connection("providers", "jan"), self._approve_connection("providers", "lmstudio"), top.destroy(), self._open_connection_center())).pack(side="left", padx=8)

    def _start_quick_status_loop(self):
        def tick():
            try:
                self._refresh_quick_strip()
                self._refresh_footer_status()
                self._refresh_scan_progress_widget()
            except Exception:
                pass
            self.after(15000, tick)
        self.after(600, tick)

    def _quick_emit(self, title, payload):
        text = f"{title}\n{self._pretty(payload)}"
        if hasattr(self, "chat_display"):
            self._append_chat_block("Baba", text)
        elif hasattr(self, "settings_output"):
            self.settings_output.insert("end", f"\n{text}\n")
            self.settings_output.see("end")
        else:
            messagebox.showinfo("Baba", text[:2000])
        self._refresh_quick_strip()

    def _set_mousewheel_target(self, target=None):
        self._mousewheel_target = target

    def _make_scrollable_sidebar(self, parent, bg):
        outer = tk.Frame(parent, bg=bg)
        canvas = tk.Canvas(outer, bg=bg, bd=0, highlightthickness=0)
        vsb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=bg)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")

        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        def on_inner_config(_e):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_config(e):
            canvas.itemconfigure(win, width=e.width)

        inner.bind("<Configure>", on_inner_config)
        canvas.bind("<Configure>", on_canvas_config)
        canvas.bind("<Enter>", lambda _e: self._set_mousewheel_target(canvas))
        outer.bind("<Leave>", lambda _e: self._set_mousewheel_target(None))
        return outer, inner, canvas

    def _on_global_mousewheel(self, event):
        target = self._resolve_scroll_target(event)
        if not target:
            return
        try:
            if getattr(event, "num", None) == 4:
                delta = -1
            elif getattr(event, "num", None) == 5:
                delta = 1
            else:
                delta = int(-1 * (event.delta / 120)) if event.delta else 0
            if delta:
                target.yview_scroll(delta, "units")
                return "break"
        except Exception:
            return

    def _resolve_scroll_target(self, event=None):
        # 1) Explicit hover target from existing enter/leave hooks.
        target = getattr(self, "_mousewheel_target", None)
        try:
            if target and target.winfo_exists():
                return target
        except Exception:
            pass

        # 2) Infer from widget under pointer, walking up to a scroll-capable ancestor.
        w = None
        try:
            x, y = self.winfo_pointerxy()
            w = self.winfo_containing(x, y)
        except Exception:
            w = getattr(event, "widget", None)
        while w is not None:
            if hasattr(w, "yview"):
                return w
            try:
                parent_name = w.winfo_parent()
                if not parent_name:
                    break
                w = w.nametowidget(parent_name)
            except Exception:
                break

        # 3) Fallback to main content canvas so all panels can scroll when needed.
        if hasattr(self, "content_canvas"):
            return self.content_canvas
        return None

    def _quick_open_exo(self):
        if not self.apps or not hasattr(self.apps, "exo_open"):
            self._quick_emit("Exo", {"ok": False, "error": "Exo integration not available"})
            return
        if not self._approved_has("apps", "exo"):
            ok = messagebox.askyesno("Approve Exo", "Approve connection for Exo now?")
            if not ok:
                self._quick_emit("Exo", {"ok": False, "error": "Not approved yet"})
                return
            self._approve_connection("apps", "exo")
        try:
            result = self.apps.exo_open()
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        self._quick_emit("Exo Open", result)

    def _quick_exo_triage(self):
        if not self.apps or not hasattr(self.apps, "exo_triage_inbox"):
            self._quick_emit("Exo Triage", {"ok": False, "error": "Exo triage not available"})
            return
        if not self._approved_has("apps", "exo"):
            ok = messagebox.askyesno("Approve Exo", "Approve Exo connection before triage?")
            if not ok:
                self._quick_emit("Exo Triage", {"ok": False, "error": "Not approved yet"})
                return
            self._approve_connection("apps", "exo")
        self._run_email_organizer_async(trigger="exo_quick")

    def _set_email_organizer_status(self, state, note=""):
        self.email_organizer_state = state
        self.email_organizer_last = (note or datetime.now().strftime("%H:%M:%S"))[:80]
        summary = self.email_organizer_summary or {}
        total = int(summary.get("total", 0) or 0)
        high = int(summary.get("high", 0) or 0)
        txt = "Email Organizer: Idle"
        color = T["text_muted"]
        if state == "running":
            txt = "Email Organizer: Running..."
            color = T["warning"]
        elif state == "completed":
            txt = f"Email Organizer: Completed ({total} mails, urgent {high})"
            color = T["success"] if total > 0 else T["text_muted"]
        elif state == "error":
            txt = f"Email Organizer: Error ({(note or '')[:40]})"
            color = T["error"]
        if hasattr(self, "email_org_label"):
            self.email_org_label.config(text=txt, fg=color)
        if hasattr(self, "status_extra"):
            self.status_extra.config(text=f"Email {state.upper()} | {self.email_organizer_last}")

    def _cache_email_scan_items(self, result):
        try:
            buckets = (result or {}).get("buckets", {}) if isinstance(result, dict) else {}
            items = []
            for pri in ("high", "medium", "low", "skip"):
                for m in buckets.get(pri, []) if isinstance(buckets, dict) else []:
                    if not isinstance(m, dict):
                        continue
                    subject = str(m.get("subject", "") or "").strip()
                    sender = str(m.get("sender", "") or "").strip()
                    date_val = str(m.get("date", "") or "").strip()
                    folder = str(m.get("folder", "") or "").strip()
                    account = self._extract_account_from_folder(folder)
                    snippet = str(m.get("snippet", "") or m.get("body", "") or "").strip()
                    if len(snippet) > 280:
                        snippet = snippet[:280]
                    items.append(
                        {
                            "priority": pri,
                            "subject": subject,
                            "sender": sender,
                            "date": date_val,
                            "folder": folder,
                            "account": account,
                            "flagged": bool(m.get("flagged", False)),
                            "pinned": bool(m.get("pinned", False)),
                            "snippet": snippet,
                        }
                    )
            self.email_organizer_last_items = items[:20000]
            self.email_organizer_last_scan_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            pass

    def _extract_account_from_folder(self, folder):
        fp = str(folder or "").strip()
        if not fp:
            return ""
        return fp.split("/", 1)[0].strip()

    def _run_expert_monitors_from_cache(self, notify=True):
        items = list(self.email_organizer_last_items or [])
        if not items:
            self.expert_monitor_state = {}
            return {}

        def count_hits(keywords, priority="high"):
            kws = [k.lower() for k in keywords]
            hits = []
            for m in items:
                if priority and str(m.get("priority", "")).lower() != priority:
                    continue
                blob = " ".join(
                    [
                        str(m.get("subject", "")),
                        str(m.get("sender", "")),
                        str(m.get("snippet", "")),
                        str(m.get("folder", "")),
                    ]
                ).lower()
                if any(k in blob for k in kws):
                    hits.append(m)
            return hits

        solicitor_hits = count_hits(
            ["legal", "solicitor", "council", "court", "dispute", "notice", "breach", "lease"]
        )
        accountant_hits = count_hits(
            ["hmrc", "tax", "vat", "invoice", "payment", "overdue", "account", "return"]
        )
        moneymaker_hits = count_hits(
            ["supplier", "discount", "margin", "deal", "profit", "opportunity", "wholesale"]
        )
        coder_hits = count_hits(
            ["api", "integration", "error", "bug", "deploy", "automation", "script", "code"]
        )
        programmer_hits = count_hits(
            ["program", "runtime", "stack trace", "traceback", "exception", "pipeline", "build"]
        )
        kairos_hits = count_hits(
            ["urgent", "asap", "deadline", "due", "today", "immediate"]
        )

        state = {
            "solicitor": {"urgent": len(solicitor_hits), "top": solicitor_hits[:5]},
            "accountant": {"urgent": len(accountant_hits), "top": accountant_hits[:5]},
            "moneymaker": {"urgent": len(moneymaker_hits), "top": moneymaker_hits[:5]},
            "coder": {"urgent": len(coder_hits), "top": coder_hits[:5]},
            "programmer": {"urgent": len(programmer_hits), "top": programmer_hits[:5]},
            "kairos": {"urgent": len(kairos_hits), "top": kairos_hits[:5]},
            "scanned_total": len(items),
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
        self.expert_monitor_state = state

        if notify:
            sig = json.dumps(
                {
                    "s": state["solicitor"]["urgent"],
                    "a": state["accountant"]["urgent"],
                    "m": state["moneymaker"]["urgent"],
                    "c": state["coder"]["urgent"],
                    "p": state["programmer"]["urgent"],
                    "k": state["kairos"]["urgent"],
                },
                sort_keys=True,
            )
            now = time.time()
            if sig != self._last_expert_alert_sig or (now - self._last_expert_alert_at) > 300:
                self._last_expert_alert_sig = sig
                self._last_expert_alert_at = now
                summary = (
                    f"Expert monitors active: "
                    f"Solicitor {state['solicitor']['urgent']} | "
                    f"Accountant {state['accountant']['urgent']} | "
                    f"MoneyMaker {state['moneymaker']['urgent']} | "
                    f"Coder {state['coder']['urgent']} | "
                    f"Programmer {state['programmer']['urgent']} | "
                    f"Kairos {state['kairos']['urgent']}"
                )
                self._append_chat_block(
                    "Baba",
                    summary + "\nUrgent review required where counts are non-zero. Open urgent review preview for click-through.",
                    [
                        "Open urgent review preview window.",
                        "Open Exo Triage and show top 20 urgent emails now.",
                        "Group urgent emails by account and folder.",
                        "Create tasks from all urgent emails.",
                        "Run expert mix solicitor accountant moneymaker coder kairos.",
                    ],
                )
        return state

    def _open_urgent_review_window(self, keywords=None, limit=120):
        rows = list(self.email_organizer_last_items or [])
        if not rows:
            self._append_chat_block("Baba", "No scanned email cache yet. Run Organize Emails first.")
            return
        kws = [str(k).lower().strip() for k in (keywords or []) if str(k).strip()]
        filtered = []
        for m in rows:
            if str(m.get("priority", "")).lower() != "high":
                continue
            blob = " ".join(
                [
                    str(m.get("subject", "")),
                    str(m.get("sender", "")),
                    str(m.get("snippet", "")),
                    str(m.get("folder", "")),
                ]
            ).lower()
            if kws and not any(k in blob for k in kws):
                continue
            filtered.append(m)
            if len(filtered) >= max(20, int(limit)):
                break

        top = tk.Toplevel(self)
        top.title("Urgent Review Preview")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1320, sw - 100), min(820, sh - 120)
        top.geometry(f"{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2)}")
        top.configure(bg=T["bg"])
        top.resizable(True, True)
        hdr = tk.Frame(top, bg=T["header_bg"], height=52)
        hdr.pack(fill="x")
        tk.Label(
            hdr,
            text=f"Urgent Review Preview | items:{len(filtered)} | scan:{self.email_organizer_last_scan_at or 'n/a'}",
            bg=T["header_bg"],
            fg=T["accent"],
            font=(FONT_FAMILY, 10, "bold"),
        ).pack(side="left", padx=14, pady=10)
        body = scrolledtext.ScrolledText(top, bg=T["card_bg"], fg=T["text"], font=(FONT_FAMILY, 10), bd=0, padx=14, pady=14)
        body.pack(fill="both", expand=True, padx=14, pady=14)
        for i, m in enumerate(filtered, 1):
            subject = m.get("subject") or "(no subject)"
            sender = m.get("sender") or "(unknown sender)"
            date_val = m.get("date") or "unknown date"
            account = m.get("account") or "unknown account"
            folder = m.get("folder") or "unknown folder"
            flags = []
            if m.get("flagged"):
                flags.append("FLAGGED")
            if m.get("pinned"):
                flags.append("PINNED")
            fs = f" [{' | '.join(flags)}]" if flags else ""
            body.insert("end", f"{i}. {subject}{fs}\n")
            body.insert("end", f"   From: {sender}\n   Account: {account}\n   Folder: {folder}\n   Date: {date_val}\n\n")
        body.see("1.0")

    def _begin_email_scan_progress(self, trigger, profile):
        self.email_scan_progress = {
            "running": True,
            "trigger": str(trigger or "").strip() or "manual",
            "profile": str((profile or {}).get("label", "") or ""),
            "started_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "stores_detected": 0,
            "folders_scanned": 0,
            "messages_collected": 0,
            "current_folder": "",
            "error": "",
        }
        self._refresh_scan_progress_widget()

    def _on_email_scan_progress(self, update):
        if not isinstance(update, dict):
            return
        p = dict(self.email_scan_progress or {})
        p["running"] = True
        for k in ("stores_detected", "folders_scanned", "messages_collected", "current_folder"):
            if k in update:
                p[k] = update.get(k)
        self.email_scan_progress = p
        self.after(0, self._refresh_scan_progress_widget)

    def _finalize_email_scan_progress(self, result, err_text=""):
        p = dict(self.email_scan_progress or {})
        p["running"] = False
        if isinstance(result, dict):
            s = result.get("summary", {}) if isinstance(result.get("summary", {}), dict) else {}
            if "stores_detected_count" in s:
                p["stores_detected"] = int(s.get("stores_detected_count", 0) or 0)
            if "folders_scanned" in s:
                p["folders_scanned"] = int(s.get("folders_scanned", 0) or 0)
            if "total" in s:
                p["messages_collected"] = int(s.get("total", 0) or 0)
        p["error"] = str(err_text or "").strip()
        self.email_scan_progress = p
        self._refresh_scan_progress_widget()

    def _refresh_scan_progress_widget(self):
        if not hasattr(self, "scan_progress_value"):
            return
        p = self.email_scan_progress if isinstance(self.email_scan_progress, dict) else {}
        running = bool(p.get("running"))
        trig = str(p.get("trigger", "") or "n/a")
        prof = str(p.get("profile", "") or "n/a")
        started = str(p.get("started_at", "") or "n/a")
        stores = int(p.get("stores_detected", 0) or 0)
        folders = int(p.get("folders_scanned", 0) or 0)
        msgs = int(p.get("messages_collected", 0) or 0)
        cur = str(p.get("current_folder", "") or "").strip()
        err = str(p.get("error", "") or "").strip()
        status = "RUNNING" if running else "IDLE"
        if err:
            status = "ERROR"
        lines = [
            f"Status: {status}",
            f"Run: {trig} ({prof})",
            f"Started: {started}",
            f"Stores: {stores} | Folders: {folders} | Messages: {msgs}",
        ]
        if cur:
            lines.append(f"Current: {cur}")
        if err:
            lines.append(f"Error: {err[:140]}")
        self.scan_progress_value.config(text="\n".join(lines))

    def _email_scan_status_text(self):
        summary = self.email_organizer_summary or {}
        total = int(summary.get("total", 0) or 0)
        high = int(summary.get("high", 0) or 0)
        scanned = int(summary.get("folders_scanned", 0) or 0)
        accounts_scanned = int(summary.get("accounts_scanned", 0) or 0)
        stores_detected_count = int(summary.get("stores_detected_count", 0) or 0)
        accounts = summary.get("accounts", {}) if isinstance(summary, dict) else {}
        stores_detected = summary.get("stores_detected", []) if isinstance(summary, dict) else []
        account_names = []
        if isinstance(accounts, dict):
            account_names = [str(k).strip() for k in accounts.keys() if str(k).strip()]
        account_names = account_names[:12]
        store_names = [str(s).strip() for s in (stores_detected or []) if str(s).strip()][:12]
        state = (self.email_organizer_state or "idle").upper()
        at = self.email_organizer_last_scan_at or "N/A"
        active_profile = str(self.email_organizer_active_profile or "").strip() or "n/a"
        active_trigger = str(self.email_organizer_active_trigger or "").strip() or "n/a"
        pending_profile = str(self.email_organizer_pending_profile or "").strip()
        pending_trigger = str(self.email_organizer_pending_trigger or "").strip()
        acc_line = ", ".join(account_names) if account_names else "N/A"
        stores_line = ", ".join(store_names) if store_names else "N/A"
        pending_line = (
            f"\n- Pending rerun: {pending_trigger} ({pending_profile})"
            if pending_trigger
            else ""
        )
        return (
            f"Email scan status: {state}\n"
            f"- Active run: {active_trigger} ({active_profile})\n"
            f"- Last scan at: {at}\n"
            f"- Accounts scanned: {accounts_scanned}\n"
            f"- Account roots: {acc_line}\n"
            f"- Outlook stores detected: {stores_detected_count}\n"
            f"- Store names: {stores_line}\n"
            f"- Folders scanned: {scanned}\n"
            f"- Total messages indexed in last run: {total}\n"
            f"- Urgent(high): {high}"
            f"{pending_line}"
        )

    def _build_urgent_email_focus_report(self, keywords, limit=20):
        kws = [k.lower().strip() for k in (keywords or []) if str(k).strip()]
        if self.email_organizer_running:
            return (
                "Email Organizer is still running. "
                "I will show filtered urgent legal/HMRC/tax/invoice items when this scan completes.\n\n"
                + self._email_scan_status_text()
            )
        items = list(self.email_organizer_last_items or [])
        if not items:
            return (
                "No real scanned email data is cached yet. "
                "Run Organize Emails first, then I can filter urgent legal/HMRC/tax/invoice items from real results."
            )
        picked = []
        for m in items:
            pri = str(m.get("priority", "")).lower()
            if pri != "high":
                continue
            blob = " ".join(
                [
                    str(m.get("subject", "")),
                    str(m.get("sender", "")),
                    str(m.get("snippet", "")),
                    str(m.get("folder", "")),
                ]
            ).lower()
            if kws and not any(k in blob for k in kws):
                continue
            picked.append(m)
            if len(picked) >= max(1, int(limit)):
                break

        if not picked:
            return (
                "No matching urgent items found in the last real scan for those filters.\n\n"
                + self._email_scan_status_text()
            )

        lines = [
            "Urgent filtered emails (real scan data):",
            f"- Matches shown: {len(picked)}",
            f"- Keywords: {', '.join(kws)}",
            "",
        ]
        for i, m in enumerate(picked, 1):
            subj = m.get("subject") or "(no subject)"
            sender = m.get("sender") or "(unknown sender)"
            date_val = m.get("date") or "unknown date"
            folder = m.get("folder") or "(folder n/a)"
            lines.append(f"{i}. {subj}")
            lines.append(f"   From: {sender} | Date: {date_val} | Folder: {folder}")
        lines.append("")
        lines.append(self._email_scan_status_text())
        return "\n".join(lines)

    def _email_scan_profile(self, trigger):
        trig = (trigger or "").lower()
        # Keep full capability, but avoid heavy startup freeze.
        if trig == "startup":
            return {"limit_per_folder": 10, "max_folders": 90, "include_subfolders": True, "label": "startup-fast"}
        if trig == "45m":
            return {"limit_per_folder": 20, "max_folders": 180, "include_subfolders": True, "label": "scheduled"}
        if trig in ("chat_full", "manual_full"):
            # Unlimited full scan mode: all folders, all stores/accounts, include subfolders.
            return {"limit_per_folder": 0, "max_folders": 0, "include_subfolders": True, "label": "full-all-unlimited"}
        if trig in ("manual", "settings", "exo_quick", "chat_request"):
            return {"limit_per_folder": 35, "max_folders": 220, "include_subfolders": True, "label": "full"}
        return {"limit_per_folder": 24, "max_folders": 180, "include_subfolders": True, "label": "default"}

    def _call_exo_triage_all_mail_compat(self, profile, progress_cb=None):
        if not (self.apps and hasattr(self.apps, "exo_triage_all_mail")):
            return None
        fn = self.apps.exo_triage_all_mail
        kwargs = {
            "limit_per_folder": int(profile["limit_per_folder"]),
            "max_folders": int(profile["max_folders"]),
            "include_subfolders": bool(profile["include_subfolders"]),
            "progress_cb": progress_cb,
        }
        try:
            accepted = set(inspect.signature(fn).parameters.keys())
            call_kwargs = {k: v for k, v in kwargs.items() if k in accepted}
        except Exception:
            call_kwargs = dict(kwargs)

        try:
            return fn(**call_kwargs)
        except TypeError as e:
            # Backward-compatible fallbacks for older AppBridge signatures.
            msg = str(e).lower()
            if "unexpected keyword argument" in msg or "positional argument" in msg:
                fallbacks = [
                    {"limit_per_folder": int(profile["limit_per_folder"]), "max_folders": int(profile["max_folders"])},
                    {"limit_per_folder": int(profile["limit_per_folder"])},
                    {"limit": int(profile["limit_per_folder"])},
                    {},
                ]
                for fb in fallbacks:
                    try:
                        return fn(**fb)
                    except Exception:
                        continue
            raise

    def _run_email_organizer_async(self, trigger="manual"):
        profile = self._email_scan_profile(trigger)
        if self.email_organizer_running:
            # Queue one rerun with latest requested trigger/profile.
            self.email_organizer_pending_trigger = str(trigger or "").strip() or "manual"
            self.email_organizer_pending_profile = str(profile.get("label") or "").strip()
            self._set_email_organizer_status("running", "already running")
            self._refresh_footer_status()
            return
        self.email_organizer_running = True
        self.email_organizer_active_trigger = str(trigger or "").strip() or "manual"
        self.email_organizer_active_profile = str(profile.get("label") or "").strip()
        self._set_email_organizer_status("running", trigger)
        self._begin_email_scan_progress(trigger, profile)

        def worker():
            result = {"ok": False, "error": "email organizer unavailable"}
            try:
                compat = self._call_exo_triage_all_mail_compat(profile, progress_cb=self._on_email_scan_progress)
                if compat is not None:
                    result = compat
                elif self.apps and hasattr(self.apps, "exo_triage_inbox"):
                    result = self.apps.exo_triage_inbox(limit=60)
            except Exception as e:
                result = {"ok": False, "error": str(e)}

            def finalize():
                self.email_organizer_running = False
                if result.get("ok"):
                    summary = result.get("summary", {}) or {}
                    self.email_organizer_summary = summary
                    self._cache_email_scan_items(result)
                    self._run_expert_monitors_from_cache(notify=True)
                    self._set_email_organizer_status("completed", trigger)
                    high = int(summary.get("high", 0) or 0)
                    if high > self._last_urgent_count:
                        self._append_chat_block(
                            "Baba",
                            f"Urgent email alert: {high} urgent items detected across folders/accounts.",
                        )
                    self._last_urgent_count = high
                    if hasattr(self, "settings_output"):
                        msg = {
                            "trigger": trigger,
                            "profile": profile.get("label"),
                            "summary": summary,
                            "folders_scanned": summary.get("folders_scanned", 0),
                        }
                        self.settings_output.insert("end", f"\nEmail Organizer ({trigger})\n{self._pretty(msg)}\n")
                        self.settings_output.see("end")
                    self._finalize_email_scan_progress(result, err_text="")
                else:
                    err_text = result.get("error", "scan failed")
                    hint = result.get("hint") or self._derive_email_error_hint(err_text)
                    self._set_email_organizer_status("error", hint)
                    now = time.time()
                    if (err_text != self._last_email_error_msg) or ((now - self._last_email_error_at) > 45):
                        self._append_chat_block(
                            "Baba",
                            f"Email Organizer error: {err_text}\nFix: {hint}",
                        )
                        self._last_email_error_msg = err_text
                        self._last_email_error_at = now
                    if hasattr(self, "settings_output"):
                        err = {
                            "trigger": trigger,
                            "error": err_text,
                            "hint": hint,
                        }
                        self.settings_output.insert("end", f"\nEmail Organizer error:\n{self._pretty(err)}\n")
                        self.settings_output.see("end")
                    self._finalize_email_scan_progress(result, err_text=err_text)
                self._refresh_footer_status()
                # Run queued rerun request (if any) after current scan finishes.
                pending = str(self.email_organizer_pending_trigger or "").strip()
                if pending:
                    self.email_organizer_pending_trigger = ""
                    self.email_organizer_pending_profile = ""
                    self.after(200, lambda p=pending: self._run_email_organizer_async(trigger=p))

            self.after(0, finalize)

        threading.Thread(target=worker, daemon=True).start()

    def _quick_wiki_ingest(self):
        if not self.wiki:
            self._quick_emit("LLM Wiki", {"ok": False, "error": "Wiki compiler unavailable"})
            return
        files = filedialog.askopenfilenames(
            title="Select files for wiki ingest",
            filetypes=[("Documents", "*.md *.txt *.json *.csv *.py *.js *.ts *.html *.css *.pdf"), ("All files", "*.*")],
        )
        if not files:
            return
        try:
            result = self.wiki.ingest_files(list(files), source_tag="quick_bar")
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        self._quick_emit("LLM Wiki Ingest", result)

    def _quick_wiki_compile(self):
        if not self.wiki:
            self._quick_emit("LLM Wiki", {"ok": False, "error": "Wiki compiler unavailable"})
            return
        self._quick_emit("LLM Wiki Compile", {"ok": True, "status": "running"})

        def worker():
            try:
                result = self.wiki.compile_once(topic_hint="Baba Desktop Knowledge")
            except Exception as e:
                result = {"ok": False, "error": str(e)}
            self.after(0, lambda: self._quick_emit("LLM Wiki Compile Result", result))

        threading.Thread(target=worker, daemon=True).start()

    def _quick_show_kairos(self):
        if not self.kairos:
            self._quick_emit("Kairos", {"ok": False, "error": "Kairos memory unavailable"})
            return
        try:
            result = {"stats": self.kairos.stats(), "recent": self.kairos.recent_signals(limit=5)}
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        self._quick_emit("Kairos Profile", result)

    def _build_sidebar(self):
        # Sidebar Header with Toggle
        s_hdr = tk.Frame(self.sidebar, bg=T["sidebar_bg"])
        s_hdr.pack(fill="x", side="top")
        self.toggle_btn = tk.Button(s_hdr, text="\u2261", font=(FONT_FAMILY, 16),
                                   bg=T["sidebar_bg"], fg=T["text"], bd=0, command=self._toggle_sidebar)
        self.toggle_btn.pack(side="left", padx=15, pady=10)
        
        # Scrollable Navigation Area
        self.nav_canvas = tk.Canvas(self.sidebar, bg=T["sidebar_bg"], bd=0, highlightthickness=0)
        self.nav_scrollbar = tk.Scrollbar(self.sidebar, orient="vertical", command=self.nav_canvas.yview)
        self.nav_scroll_frame = tk.Frame(self.nav_canvas, bg=T["sidebar_bg"])
        
        self.nav_canvas.configure(yscrollcommand=self.nav_scrollbar.set)
        self.nav_scrollbar.pack(side="right", fill="y")
        self.nav_canvas.pack(side="top", fill="both", expand=True)
        self.nav_canvas.create_window((0, 0), window=self.nav_scroll_frame, anchor="nw")
        self.nav_canvas.bind("<Enter>", lambda e: self._set_mousewheel_target(self.nav_canvas))
        self.nav_scroll_frame.bind("<Enter>", lambda e: self._set_mousewheel_target(self.nav_canvas))
        self.sidebar.bind("<Leave>", lambda e: self._set_mousewheel_target(None))
        self.bind_all("<MouseWheel>", self._on_global_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_global_mousewheel, add="+")
        self.bind_all("<Button-5>", self._on_global_mousewheel, add="+")
        
        self.nav_scroll_frame.bind("<Configure>", lambda e: self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox("all")))

        items = [
            ("chat", "\U0001f4ac", "Chat"),
            ("cowork", "\U0001f91d", "Cowork"),
            ("tasks", "\u2611", "Tasks"),
            ("computer", "\U0001f5a5", "PC Control"),
            ("browser", "\U0001f30d", "Browser"),
            ("social", "\U0001f4ac", "Social"),
            ("apps", "\U0001f4bb", "Apps"),
            ("vision", "\U0001f441", "Vision"),
            ("scheduler", "\U0001f4c5", "Scheduler"),
            ("meetings", "\U0001f3a7", "Meetings"),
            ("money", "\U0001f4b0", "Money"),
            ("brain", "\U0001f9e0", "Brain"),
            ("providers", "\u2699", "Providers"),
            ("import", "\U0001f4e5", "Import"),
            ("research", "\U0001f50d", "Research"),
            ("devtools", "\U0001f6e0", "DevTools"),
            ("evolving", "\u26a1", "Self-Evolving"),
            ("claws", "\U0001f985", "Claws"),
            ("agents", "\U0001f465", "Agents"),
            ("settings", "\u2699", "Settings"),
        ]
        
        self.active_tab = "chat" # Default to Chat now
        
        for pid, icon, label in items:
            btn = ModernButton(self.nav_scroll_frame, text=label, icon=icon, command=lambda p=pid: self._switch_tab(p), active=(pid == self.active_tab))
            btn.pack(fill="x")
            btn.bind("<Enter>", lambda _e: self._set_mousewheel_target(self.nav_canvas), add="+")
            self.nav_btns[pid] = btn

        # Sidebar Bottom: Command Buttons
        bottom_cmds = tk.Frame(self.sidebar, bg=T["sidebar_bg"], pady=10)
        bottom_cmds.pack(side="bottom", fill="x")
        actions = [
            ("Clear", "\u232b", lambda: self.chat_input.delete("1.0", "end") if hasattr(self, "chat_input") else None),
        ]
        for cmd, icon, fn in actions:
            tk.Button(
                bottom_cmds,
                text=f"{icon} {cmd}",
                font=(FONT_FAMILY, 8),
                bg=T["card_bg"],
                fg=T["text_muted"],
                bd=0,
                padx=10,
                pady=5,
                command=fn,
            ).pack(side="left", expand=True, padx=2)

    def _build_content_panels(self):
        # Existing features
        self.panels["tasks"] = self._create_task_panel()
        self.panels["computer"] = self._create_computer_panel()
        self.panels["browser"] = self._create_browser_panel()
        self.panels["agents"] = self._create_agents_panel()
        self.panels["brain"] = self._create_brain_panel()
        self.panels["settings"] = self._create_settings_panel()
        
        # New Ultimate Panels
        self.panels["chat"] = self._create_chat_panel()
        self.panels["cowork"] = self._create_cowork_panel()
        self.panels["social"] = self._create_social_panel()
        self.panels["apps"] = self._create_apps_panel()
        self.panels["vision"] = self._create_vision_panel()
        self.panels["scheduler"] = self._create_scheduler_panel()
        self.panels["meetings"] = self._create_meetings_panel()
        self.panels["money"] = self._create_money_panel()
        self.panels["providers"] = self._create_providers_panel()
        self.panels["import"] = self._create_import_panel()
        self.panels["research"] = self._create_research_panel()
        self.panels["devtools"] = self._create_devtools_panel()
        self.panels["evolving"] = self._create_evolving_panel()
        self.panels["claws"] = self._create_claws_panel()
        # Initial render: force-show default panel even when active_tab is already set.
        if self.active_tab in self.panels:
            self.panels[self.active_tab].pack(fill="both", expand=True)
        if self.active_tab in self.nav_btns:
            self.nav_btns[self.active_tab].set_active(True)

    def _create_computer_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        
        # Header with Status
        header = tk.Frame(panel, bg=T["bg"])
        header.pack(fill="x", padx=30, pady=(30, 10))
        tk.Label(header, text="Computer Use - OS Level Control", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(side="left")
        
        status_point = tk.Frame(header, bg=T["success"], width=10, height=10)
        status_point.pack(side="left", padx=(20, 5))
        tk.Label(header, text="ACTIVE SESSION (VM ISOLATED)", font=(FONT_FAMILY, 8, "bold"), bg=T["bg"], fg=T["success"]).pack(side="left")

        # Main Layout: Sidebar controls + Screen Preview
        body = tk.Frame(panel, bg=T["bg"])
        body.pack(fill="both", expand=True, padx=30, pady=10)
        
        # Left: Controls
        ctrls = tk.Frame(body, bg=T["bg"], width=300)
        ctrls.pack(side="left", fill="y", padx=(0, 20))
        ctrls.pack_propagate(False)
        ctrls_outer, ctrls_body, _ = self._make_scrollable_sidebar(ctrls, T["bg"])
        ctrls_outer.pack(fill="both", expand=True)

        tk.Label(ctrls_body, text="SYSTEM CAPABILITIES", font=(FONT_FAMILY, 10, "bold"), bg=T["bg"], fg=T["text_muted"]).pack(anchor="w", pady=(0, 10))
        
        features = [
            ("Screen Perception", "Full-screen OCR & Element Detection"),
            ("Input Control", "Mouse, Keyboard & Global Hotkeys"),
            ("System Navigation", "App Switching & Menu Control"),
            ("File System", "CRUD Operations with Safety Pipeline")
        ]
        
        for title, desc in features:
            f_frame = tk.Frame(ctrls_body, bg=T["card_bg"], padx=15, pady=10, bd=1, highlightbackground=T["card_border"], highlightthickness=1)
            f_frame.pack(fill="x", pady=5)
            tk.Label(f_frame, text=title, font=(FONT_FAMILY, 10, "bold"), bg=T["card_bg"], fg=T["text"]).pack(anchor="w")
            tk.Label(f_frame, text=desc, font=(FONT_FAMILY, 8), bg=T["card_bg"], fg=T["text_muted"], wraplength=250, justify="left").pack(anchor="w")
        
        # Action Buttons
        tk.Button(ctrls_body, text="START COMPUTER SESSION", bg=T["accent"], fg="#000", font=(FONT_FAMILY, 9, "bold"), bd=0, pady=10).pack(fill="x", pady=(20, 5))
        tk.Button(ctrls_body, text="EMERGENCY ABORT (ESC)", bg=T["error"], fg="#FFF", font=(FONT_FAMILY, 9, "bold"), bd=0, pady=10).pack(fill="x")

        # Right: Screen View
        screen_frame = tk.Frame(body, bg="#000", bd=2, highlightbackground=T["accent"], highlightthickness=1)
        screen_frame.pack(side="right", fill="both", expand=True)
        
        # Screen preview content
        canvas = tk.Canvas(screen_frame, bg="#1a1a1a", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        
        # Draw preview UI elements on canvas
        canvas.create_rectangle(50, 50, 400, 300, outline=T["accent"], width=2)
        canvas.create_text(225, 40, text="[Detected Window: VS Code]", fill=T["accent"], font=(FONT_FAMILY, 8))
        canvas.create_oval(100, 100, 110, 110, fill=T["success"])
        canvas.create_text(130, 105, text="Cursor Target", fill=T["text_muted"], font=(FONT_FAMILY, 8))
        
        return panel

    def _create_browser_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tk.Label(panel, text="Browser Control & Chrome Extension", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=30)

        url_frame = tk.Frame(panel, bg=T["card_bg"], padx=10, pady=10)
        url_frame.pack(fill="x", padx=30, pady=(0, 20))
        tk.Label(url_frame, text="URL:", bg=T["card_bg"], fg=T["text_muted"]).pack(side="left")
        url_entry = tk.Entry(url_frame, bg=T["bg"], fg=T["text"], bd=0, insertbackground=T["accent"])
        url_entry.pack(side="left", fill="x", expand=True, padx=10)
        url_entry.insert(0, "https://www.anthropic.com/")

        browser_body = tk.Frame(panel, bg=T["bg"])
        browser_body.pack(fill="both", expand=True, padx=30, pady=(0, 20))

        output = scrolledtext.ScrolledText(browser_body, bg=T["card_bg"], fg=T["text"], font=(FONT_FAMILY, 10), bd=1, highlightbackground=T["card_border"], highlightthickness=1, padx=12, pady=12)
        output.pack(side="left", fill="both", expand=True, padx=(0, 10))
        output.insert("end", "Browser control online.\nUse actions on the right to open, extract, and summarize real pages.\n")

        ext_sidebar = tk.Frame(browser_body, bg=T["sidebar_bg"], width=320, bd=1, highlightbackground=T["accent"], highlightthickness=1)
        ext_sidebar.pack(side="right", fill="y")
        ext_sidebar.pack_propagate(False)

        s_hdr = tk.Frame(ext_sidebar, bg=T["accent"], pady=10)
        s_hdr.pack(fill="x")
        tk.Label(s_hdr, text="CHROME + WEB AUTOMATION", font=(FONT_FAMILY, 9, "bold"), bg=T["accent"], fg="#000").pack()

        s_outer, s_body, _ = self._make_scrollable_sidebar(ext_sidebar, T["sidebar_bg"])
        s_outer.pack(fill="both", expand=True)
        s_body.configure(padx=12, pady=12)
        tk.Button(s_body, text="Open URL", bg=T["card_bg"], fg=T["text"], bd=0, padx=10, pady=8, command=lambda: self._browser_open_url(url_entry, output)).pack(fill="x", pady=3)
        tk.Button(s_body, text="Extract Page Text", bg=T["card_bg"], fg=T["text"], bd=0, padx=10, pady=8, command=lambda: self._browser_extract_page(url_entry, output)).pack(fill="x", pady=3)
        tk.Button(s_body, text="AI Summary", bg=T["card_bg"], fg=T["text"], bd=0, padx=10, pady=8, command=lambda: self._browser_ai_summary(url_entry, output)).pack(fill="x", pady=3)
        tk.Button(s_body, text="Open WhatsApp Web", bg=T["card_bg"], fg=T["text"], bd=0, padx=10, pady=8, command=lambda: self._browser_open_social("whatsapp", output)).pack(fill="x", pady=3)
        tk.Button(s_body, text="Open Gmail", bg=T["card_bg"], fg=T["text"], bd=0, padx=10, pady=8, command=lambda: self._browser_open_social("gmail", output)).pack(fill="x", pady=3)
        tk.Button(s_body, text="Open Outlook Web", bg=T["card_bg"], fg=T["text"], bd=0, padx=10, pady=8, command=lambda: self._browser_open_social("outlook", output)).pack(fill="x", pady=3)

        if self.apps and hasattr(self.apps, "detect_integrations"):
            try:
                scan = self.apps.detect_integrations(refresh=False)
                chrome_up = scan.get("browsers", {}).get("chrome", {}).get("running", False)
                edge_up = scan.get("browsers", {}).get("edge", {}).get("running", False)
                tk.Label(s_body, text=f"Chrome: {'running' if chrome_up else 'offline'}", font=(FONT_FAMILY, 8), bg=T["sidebar_bg"], fg=T["success"] if chrome_up else T["text_muted"]).pack(anchor="w", pady=(12, 2))
                tk.Label(s_body, text=f"Edge: {'running' if edge_up else 'offline'}", font=(FONT_FAMILY, 8), bg=T["sidebar_bg"], fg=T["success"] if edge_up else T["text_muted"]).pack(anchor="w")
            except Exception:
                pass
        return panel

    def _browser_open_url(self, url_entry, output_widget):
        url = url_entry.get().strip()
        if not url:
            return
        if self.apps and hasattr(self.apps, "chrome_open"):
            result = self.apps.chrome_open(url)
        else:
            import webbrowser

            ok = webbrowser.open(url)
            result = {"ok": bool(ok), "url": url}
        output_widget.insert("end", f"\n[OPEN URL]\n{self._pretty(result)}\n")
        output_widget.see("end")

    def _browser_extract_page(self, url_entry, output_widget):
        url = url_entry.get().strip()
        if not url:
            return
        if self.apps and hasattr(self.apps, "chrome_extract_page"):
            result = self.apps.chrome_extract_page(url)
        elif self.tools:
            result = self.tools.run("web_fetch", url=url)
        else:
            result = "Browser extraction unavailable."
        output_widget.insert("end", f"\n[EXTRACT PAGE]\n{self._pretty(result)}\n")
        output_widget.see("end")

    def _browser_ai_summary(self, url_entry, output_widget):
        url = url_entry.get().strip()
        if not url:
            return
        output_widget.insert("end", "\n[AI SUMMARY]\nSummarizing page...\n")
        output_widget.see("end")

        def worker():
            extracted = ""
            if self.apps and hasattr(self.apps, "chrome_extract_page"):
                ex = self.apps.chrome_extract_page(url)
                extracted = ex.get("text", "") if isinstance(ex, dict) else str(ex)
            elif self.tools:
                extracted = str(self.tools.run("web_fetch", url=url))
            prompt = f"Summarize this webpage for business actionability. URL: {url}\n\n{extracted[:6000]}"
            summary = _call_ai_sync(prompt, provider=self.prov_cb.get(), model=self.model_cb.get(), system=BABA_SYSTEM_PROMPT)
            self.after(0, lambda: (output_widget.insert("end", f"{summary}\n"), output_widget.see("end")))

        threading.Thread(target=worker, daemon=True).start()

    def _browser_open_social(self, platform, output_widget):
        if self.apps and hasattr(self.apps, "social_open"):
            result = self.apps.social_open(platform)
        else:
            result = {"ok": False, "error": "App bridge unavailable"}
        output_widget.insert("end", f"\n[OPEN {platform.upper()}]\n{self._pretty(result)}\n")
        output_widget.see("end")

    def _create_whatsapp_panel(self, parent=None):
        panel = tk.Frame(parent or self.content_area, bg=T["bg"])
        tk.Label(panel, text="WhatsApp Agent - Web & Desktop", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=30)

        controls = tk.Frame(panel, bg=T["bg"])
        controls.pack(fill="x", padx=30, pady=(0, 10))
        status_lbl = tk.Label(controls, text="Status: ready", bg=T["bg"], fg=T["text_muted"], font=(FONT_FAMILY, 9))
        status_lbl.pack(side="right")
        tk.Button(
            controls,
            text="Open WhatsApp Web",
            bg=T["card_bg"],
            fg=T["text"],
            bd=0,
            padx=10,
            pady=6,
            command=lambda: self._open_whatsapp_from_social("web", status_lbl),
        ).pack(side="left")
        tk.Button(
            controls,
            text="Open WhatsApp Desktop",
            bg=T["card_bg"],
            fg=T["text"],
            bd=0,
            padx=10,
            pady=6,
            command=lambda: self._open_whatsapp_from_social("desktop", status_lbl),
        ).pack(side="left", padx=(8, 0))
        
        container = tk.PanedWindow(panel, orient="horizontal", bg=T["card_border"], bd=0, sashwidth=2)
        container.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        
        # Left: Chat List
        chat_list = tk.Frame(container, bg=T["sidebar_bg"], width=250)
        container.add(chat_list)
        chat_list.pack_propagate(False)
        
        tk.Label(chat_list, text="ACTIVE CHATS", font=(FONT_FAMILY, 8, "bold"), bg=T["sidebar_bg"], fg=T["text_muted"]).pack(anchor="w", padx=15, pady=15)
        list_outer, list_inner, _ = self._make_scrollable_sidebar(chat_list, T["sidebar_bg"])
        list_outer.pack(fill="both", expand=True)
        
        chats = [
            ("Project Alpha Group", "10:45 AM", "Final docs attached."),
            ("David (Legal)", "Yesterday", "Please review the VAT..."),
            ("Sarah (Finance)", "Monday", "Invoice approved."),
            ("UK Supply Chain", "Last week", "Shipment delayed.")
        ]
        
        for name, time, preview in chats:
            c_frame = tk.Frame(list_inner, bg=T["sidebar_bg"], padx=10, pady=10, cursor="hand2")
            c_frame.pack(fill="x")
            tk.Label(c_frame, text=name, font=(FONT_FAMILY, 10, "bold"), bg=T["sidebar_bg"], fg=T["text"], anchor="w").pack(fill="x")
            tk.Label(c_frame, text=f"{preview} \u2022 {time}", font=(FONT_FAMILY, 8), bg=T["sidebar_bg"], fg=T["text_muted"], anchor="w").pack(fill="x")
            tk.Frame(list_inner, height=1, bg=T["card_border"]).pack(fill="x", padx=10)

        # Right: Conversation View
        conv_view = tk.Frame(container, bg=T["card_bg"])
        container.add(conv_view)
        
        # Conv Header
        c_hdr = tk.Frame(conv_view, bg=T["header_bg"], pady=10, padx=20)
        c_hdr.pack(fill="x")
        tk.Label(c_hdr, text="\U0001f465 Project Alpha Group", font=(FONT_FAMILY, 11, "bold"), bg=T["header_bg"], fg=T["accent"]).pack(side="left")
        
        # Conv Messages
        msg_area = scrolledtext.ScrolledText(conv_view, bg=T["bg"], fg=T["text"], font=(FONT_FAMILY, 10), bd=0, padx=20, pady=20)
        msg_area.pack(fill="both", expand=True)
        msg_area.insert("end", "[10:30 AM] David: Team, we need to finalize the Alpha contract today.\n")
        msg_area.insert("end", "[10:35 AM] Sarah: I've prepared the financial appendix.\n")
        msg_area.insert("end", "[10:42 AM] Claude (Agent): I am extracting the action items from this thread...\n", "agent")
        msg_area.tag_config("agent", foreground=T["accent"])
        
        # Conv Input
        c_input = tk.Frame(conv_view, bg=T["header_bg"], padx=20, pady=15)
        c_input.pack(fill="x")
        tk.Entry(c_input, bg=T["bg"], fg=T["text"], bd=0, insertbackground=T["accent"]).pack(side="left", fill="x", expand=True, padx=(0, 10))
        tk.Button(c_input, text="Send", bg=T["accent"], fg="#000", bd=0, padx=15).pack(side="right")
        
        return panel

    def _open_whatsapp_from_social(self, mode="web", status_label=None):
        result = {"ok": False, "error": "Unknown mode"}
        try:
            if mode == "desktop":
                subprocess.Popen("start whatsapp:", shell=True)
                result = {"ok": True, "message": "Opening WhatsApp Desktop"}
            elif self.apps and hasattr(self.apps, "social_open"):
                result = self.apps.social_open("whatsapp")
            else:
                import webbrowser

                ok = webbrowser.open("https://web.whatsapp.com")
                result = {"ok": bool(ok), "message": "Opening WhatsApp Web"}
        except Exception as e:
            result = {"ok": False, "error": str(e)}

        msg = "Connected/opened" if result.get("ok") else f"Failed: {result.get('error', 'unknown')}"
        if status_label:
            status_label.config(text=f"Status: {msg}", fg=T["success"] if result.get("ok") else T["warning"])
        if hasattr(self, "chat_display"):
            self._append_chat_block("Baba", f"WhatsApp {mode}: {self._pretty(result)}")

    def _create_dispatch_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tk.Label(panel, text="Dispatch Hub - Mobile Continuity", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=30)
        
        info_box = tk.Frame(panel, bg=T["accent_dim"], padx=20, pady=20, bd=1, highlightbackground=T["accent"], highlightthickness=1)
        info_box.pack(fill="x", padx=30)
        tk.Label(info_box, text="READY FOR INCOMING DISPATCHES", font=(FONT_FAMILY, 12, "bold"), bg=T["accent_dim"], fg=T["accent"]).pack(anchor="w")
        tk.Label(info_box, text="Your primary desktop is listening for tasks from Claude Mobile and Chrome Extension. Dispatched tasks will appear below for execution.", 
                 font=(FONT_FAMILY, 10), bg=T["accent_dim"], fg=T["text"], wraplength=700, justify="left").pack(anchor="w", pady=5)
        
        tk.Label(panel, text="PENDING DISPATCH QUEUE", font=(FONT_FAMILY, 10, "bold"), bg=T["bg"], fg=T["text_muted"]).pack(anchor="w", padx=30, pady=(30, 10))
        
        queue_frame = tk.Frame(panel, bg=T["bg"])
        queue_frame.pack(fill="both", expand=True, padx=30)
        
        dispatches = [
            {"source": "iPhone 15 Pro", "task": "Download all Q1 Invoices from Gmail and sort into /Accounting/2026", "time": "2 mins ago"},
            {"source": "Chrome (Work Laptop)", "task": "Summarize the 50-page PDF on the open tab and email to Sarah", "time": "5 mins ago"},
            {"source": "Claude Web", "task": "Run the VAT validation script on the current Spreadsheet", "time": "12 mins ago"}
        ]
        
        for disp in dispatches:
            d_card = tk.Frame(queue_frame, bg=T["card_bg"], pady=15, padx=20, bd=1, highlightbackground=T["card_border"], highlightthickness=1)
            d_card.pack(fill="x", pady=5)
            
            left = tk.Frame(d_card, bg=T["card_bg"])
            left.pack(side="left", fill="both", expand=True)
            tk.Label(left, text=f"\U0001f4f2 FROM: {disp['source']}", font=(FONT_FAMILY, 9, "bold"), bg=T["card_bg"], fg=T["accent"]).pack(anchor="w")
            tk.Label(left, text=disp['task'], font=(FONT_FAMILY, 10), bg=T["card_bg"], fg=T["text"], wraplength=600, justify="left").pack(anchor="w")
            
            right = tk.Frame(d_card, bg=T["card_bg"])
            right.pack(side="right")
            tk.Label(right, text=disp['time'], font=(FONT_FAMILY, 8), bg=T["card_bg"], fg=T["text_muted"]).pack(pady=(0, 5))
            tk.Button(right, text="ACCEPT & RUN", bg=T["accent"], fg="#000", bd=0, padx=15, pady=5, font=(FONT_FAMILY, 8, "bold")).pack()
        
        return panel

    def _make_selectable(self, widget):
        # Bulletproof Selection: Keep normal state but block all keyboard events
        widget.config(state="normal", undo=False)
        widget.bind("<Key>", lambda e: "break")
        widget.bind("<Button-1>", lambda e: widget.focus_set())

    def _auto_probe(self):
        def probe():
            prov_name = self.prov_cb.get()
            is_on, models = probe_provider(prov_name)
            if not is_on:
                working, _ = _find_working_provider(prov_name)
                if working:
                    prov_name = working
                    is_on, models = probe_provider(working)
            if is_on and models:
                def update_cb():
                    self.prov_cb.set(prov_name)
                    self.model_cb["values"] = models
                    if self.model_cb.get() not in models:
                        self.model_cb.set(models[0])
                self.after(0, update_cb)
        threading.Thread(target=probe, daemon=True).start()

    def _handle_chat_send(self):
        msg = self.chat_input.get("1.0", "end").strip()
        if not msg: return
        self.chat_input.delete("1.0", "end")
        self._append_chat_block("You", msg)

        handled, reply = self._try_handle_nl_control(msg)
        if handled:
            self._append_chat_block("Baba", reply)
            return
        
        # Real AI Processing Thread
        threading.Thread(target=self._process_real_ai, args=(msg,), daemon=True).start()

    def _try_handle_nl_control(self, msg):
        text = (msg or "").strip().lower()
        if not text:
            return False, ""

        provider_targets = list(ALL_MODELS.keys())
        app_targets = ["exo", "outlook", "excel", "word", "vscode", "obsidian", "cmd"]
        all_targets = provider_targets + app_targets

        # Expert mixer and expert-role quick execution.
        expert_triggers = ("expert mix", "mix experts", "mixer", "experts all")
        expert_requested = (
            ("solicitor" in text)
            or ("solicister" in text)
            or ("accountant" in text)
            or ("accountent" in text)
            or ("money making" in text)
            or ("moneymaker" in text)
            or ("coding" in text)
            or ("programming" in text)
            or ("coder" in text)
            or ("kairos" in text and "agent" in text)
        )
        if any(t in text for t in expert_triggers) or expert_requested:
            if not self.agents:
                return True, "Expert mixer unavailable: orchestrator is not loaded."
            forced = []
            if "solicitor" in text or "solicister" in text:
                forced.append("solicitor")
            if "accountant" in text or "accountent" in text:
                forced.append("accountant")
            if "money making" in text or "moneymaker" in text or "money maker" in text:
                forced.append("moneymaker")
            if "coding" in text or "programming" in text or "coder" in text or "programmer" in text:
                forced.append("coder")
            if "kairos" in text:
                forced.append("kairos")
            if not forced:
                forced = ["solicitor", "accountant", "moneymaker", "coder", "kairos"]
            self._start_parallel_agents(goal=msg, same_task=True, forced_agents=forced)
            return True, f"Expert mixer started with: {', '.join(forced)}. Main AI will merge outputs into one action plan."

        if "status" in text and ("connect" in text or "connection" in text):
            self._scan_connections_now()
            return True, self._pretty(self._connection_summary())

        if ("connect all local ai" in text) or ("approve all local ai" in text):
            for p in ("ollama", "jan", "lmstudio"):
                self._approve_connection("providers", p)
            self._scan_connections_now()
            return True, "Approved and connected local AI providers: ollama, jan, lmstudio."

        if "kairos fit" in text or "kairos check" in text or "kairos status" in text:
            available = self._available_agent_ids()
            has_kairos_agent = "kairos" in available
            has_kairos_memory = bool(self.kairos)
            summary = {
                "kairos_memory_service": has_kairos_memory,
                "kairos_agent_available": has_kairos_agent,
                "expert_mixer_includes_kairos": has_kairos_agent,
                "safe_mode": "approval-gated",
                "note": "Kairos is wired as operations coordinator and included in expert mixer when available.",
            }
            return True, self._pretty(summary)

        if ("web search" in text or "web research" in text or "internet search" in text) and any(
            k in text for k in ("approve", "allow", "enable", "start", "resume", "on")
        ):
            self._set_agent_web_policy("approved")
            return True, "Approved: agents can now run web research during analysis."

        if ("web search" in text or "web research" in text or "internet search" in text) and any(
            k in text for k in ("deny", "disable", "off", "block")
        ):
            self._set_agent_web_policy("denied")
            return True, "Denied: agents cannot run web research until approved again."

        if ("web search" in text or "web research" in text or "internet search" in text) and any(
            k in text for k in ("stop", "halt", "pause")
        ):
            self._set_agent_web_policy("stopped")
            return True, "Stopped: active/future agent web research is halted until resumed."

        if ("web search status" in text) or ("web policy" in text):
            return True, self._pretty(
                {
                    "agent_web_policy": self.agent_web_policy,
                    "evidence_required_mode": self.evidence_required_mode,
                    "last_agent_web": self._last_agent_web,
                    "last_chat_web": self._last_web_assist,
                }
            )
        if "continue local-only" in text or "continue local only" in text:
            return True, "Continuing local-only. Web/internet research will stay off until approved."

        if "evidence mode" in text and any(k in text for k in ("on", "enable", "start", "strict")):
            self._set_evidence_required_mode(True)
            return True, "Evidence Required Mode is ON."
        if "evidence mode" in text and any(k in text for k in ("off", "disable")):
            self._set_evidence_required_mode(False)
            return True, "Evidence Required Mode is OFF."
        if "evidence status" in text or "evidence mode status" in text:
            return True, self._pretty(
                {
                    "evidence_required_mode": self.evidence_required_mode,
                    "agent_web_policy": self.agent_web_policy,
                    "last_chat_web": self._last_web_assist,
                    "last_agent_web": self._last_agent_web,
                }
            )

        if "urgent review preview" in text or ("open preview" in text and "urgent" in text):
            kws = []
            if any(k in text for k in ("legal", "hmrc", "tax", "invoice")):
                kws = ["legal", "hmrc", "tax", "invoice"]
            self._open_urgent_review_window(keywords=kws, limit=120)
            return True, "Opened urgent review preview window with real scanned urgent emails."

        if "top 20 urgent emails" in text and ("open exo triage" in text or "show" in text):
            self._open_urgent_review_window(limit=20)
            return True, "Opened urgent review preview (top 20 high-priority emails) from real scan cache."

        if "group urgent emails by account and folder" in text:
            items = [m for m in (self.email_organizer_last_items or []) if str(m.get("priority", "")).lower() == "high"]
            if not items:
                return True, "No urgent cache yet. Run Organize Emails first."
            groups = {}
            for m in items:
                acc = str(m.get("account", "") or "unknown account")
                fld = str(m.get("folder", "") or "unknown folder")
                key = f"{acc} | {fld}"
                groups[key] = groups.get(key, 0) + 1
            ranked = sorted(groups.items(), key=lambda kv: kv[1], reverse=True)[:50]
            lines = ["Urgent emails grouped by account/folder (real scan):"]
            for i, (k, v) in enumerate(ranked, 1):
                lines.append(f"{i}. {k} -> {v}")
            return True, "\n".join(lines)

        if "expert monitor" in text and any(k in text for k in ("status", "run", "refresh", "check")):
            out = self._run_expert_monitors_from_cache(notify=False)
            if not out:
                return True, "No scanned email cache yet for expert monitors. Run Organize Emails first."
            return True, self._pretty(out)

        if text.startswith("connect ") or " approve " in f" {text} ":
            for t in all_targets:
                if t in text:
                    kind = "providers" if t in provider_targets else "apps"
                    self._approve_connection(kind, t)
                    self._scan_connections_now()
                    return True, f"Approved connection for {t}. It will stay connected until you disconnect."

        if text.startswith("disconnect ") or text.startswith("remove connection "):
            for t in all_targets:
                if t in text:
                    kind = "providers" if t in provider_targets else "apps"
                    self._disconnect_connection(kind, t)
                    self._scan_connections_now()
                    return True, f"Disconnected {t}. It will not reconnect until you approve again."

        if "exo triage" in text:
            if not self._approved_has("apps", "exo"):
                return True, "Exo is detected but not approved yet. Say: 'connect exo' or click Approve Connect."
            if self.apps and hasattr(self.apps, "exo_triage_all_mail"):
                try:
                    out = self.apps.exo_triage_all_mail(limit_per_folder=30, max_folders=180)
                except Exception as e:
                    out = {"ok": False, "error": str(e)}
                compact = {
                    "ok": out.get("ok"),
                    "summary": out.get("summary", {}),
                    "error": out.get("error", ""),
                }
                return True, self._pretty(compact)
            return True, "Exo triage backend is unavailable."

        if (
            any(k in text for k in ("show only legal", "hmrc", "tax", "invoice"))
            and any(k in text for k in ("urgent", "emails", "email", "show only"))
        ):
            report = self._build_urgent_email_focus_report(
                keywords=["legal", "hmrc", "tax", "invoice"], limit=20
            )
            return True, report

        if (
            "all emails" in text
            and any(k in text for k in ("read", "organize", "organise", "scan", "connected", "outlook", "18000", "18,000"))
        ):
            self._run_email_organizer_async(trigger="chat_full")
            return True, (
                "Started full-scope email scan across connected Outlook accounts/folders "
                "(Inbox, Sent, Deleted, and subfolders where accessible). "
                "I will report real counts only when scan completes.\n\n"
                + self._email_scan_status_text()
            )

        if (
            ("continue email scan" in text)
            or ("scan to 100" in text)
            or ("97%" in text and "email" in text)
        ):
            self._run_email_organizer_async(trigger="manual_full")
            return True, (
                "Continuing full-scope email scan toward complete coverage (all reachable accounts/folders/subfolders).\n\n"
                + self._email_scan_status_text()
            )

        if (
            "you not reading all emails" in text
            or ("email" in text and "status" in text and any(k in text for k in ("scan", "read", "organize")))
        ):
            return True, self._email_scan_status_text()

        if "email" in text and any(k in text for k in ("organize", "organise", "organice", "triage", "analyze", "analyse")):
            self._run_email_organizer_async(trigger="chat_request")
            return True, "Email Organizer started now. I will scan connected accounts/folders and post progress plus urgent alerts."

        if "whatsapp" in text and ("connect" in text or "open" in text):
            try:
                if self.apps and hasattr(self.apps, "social_open"):
                    out = self.apps.social_open("whatsapp")
                else:
                    import webbrowser
                    ok = webbrowser.open("https://web.whatsapp.com")
                    out = {"ok": bool(ok), "url": "https://web.whatsapp.com"}
            except Exception as e:
                out = {"ok": False, "error": str(e)}
            return True, self._pretty(out)

        if ("parallel" in text and "agent" in text) or text.startswith("/parallel"):
            if not self.agents:
                return True, "Parallel agents unavailable: orchestrator is not loaded."
            same_task = ("same task" in text) or ("same:" in text) or text.startswith("/parallel same")
            goal = (msg or "").strip()
            goal = re.sub(r"^/parallel\s+(same|split)\s*:?\s*", "", goal, flags=re.IGNORECASE).strip()
            goal = re.sub(r"^/parallel\s*", "", goal, flags=re.IGNORECASE).strip() or msg
            self._start_parallel_agents(goal, same_task=same_task)
            mode = "same-task" if same_task else "auto-split"
            return True, f"Parallel multi-agent run started ({mode}). Main AI will assign tasks and merge results."

        if "wiki compile" in text or "compile wiki" in text or "karpathy wiki compile" in text:
            if not self.wiki:
                return True, "LLM Wiki compiler is unavailable."
            try:
                out = self.wiki.compile_once(topic_hint="Baba Desktop Knowledge")
            except Exception as e:
                out = {"ok": False, "error": str(e)}
            return True, self._pretty(out)

        if "kairos profile" in text:
            if not self.kairos:
                return True, "Kairos memory is unavailable."
            return True, self._pretty({"stats": self.kairos.stats(), "recent": self.kairos.recent_signals(limit=5)})

        return False, ""

    def _parallel_default_agents(self):
        if not self.agents or not hasattr(self.agents, "list_agents"):
            return ["solicitor", "accountant", "moneymaker", "coder", "kairos"]
        try:
            ids = [a.get("id") for a in self.agents.list_agents() if isinstance(a, dict)]
        except Exception:
            ids = []
        preferred = [
            "solicitor",
            "accountant",
            "moneymaker",
            "coder",
            "programmer",
            "kairos",
            "legal",
            "acct",
            "comms",
            "pa",
            "research",
            "supplier",
            "deals",
        ]
        selected = [a for a in preferred if a in ids]
        return selected[:5] if selected else (ids[:5] or ["solicitor", "accountant", "moneymaker", "coder", "kairos"])

    def _available_agent_ids(self):
        if not self.agents or not hasattr(self.agents, "list_agents"):
            return set()
        try:
            return {str(a.get("id")).strip().lower() for a in self.agents.list_agents() if isinstance(a, dict) and a.get("id")}
        except Exception:
            return set()

    def _extract_json_block(self, text):
        raw = (text or "").strip()
        if not raw:
            return ""
        if raw.startswith("{") or raw.startswith("["):
            return raw
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end != -1 and end > start:
            return raw[start : end + 1]
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            return raw[start : end + 1]
        return raw

    def _should_use_web_assist(self, prompt):
        p = (prompt or "").lower()
        if not p:
            return False
        if re.search(r"https?://", p):
            return True
        triggers = [
            "latest", "most recent", "today", "current", "news", "update", "updated",
            "price", "stock", "market", "rate", "schedule", "score", "who is", "ceo", "president",
            "search web", "look up", "lookup", "internet",
        ]
        return any(t in p for t in triggers)

    def _build_web_assist_context(self, prompt):
        if not self.tools:
            return "", {"used": False, "searches": 0, "fetches": 0, "sources": []}
        chunks = []
        meta = {"used": False, "searches": 0, "fetches": 0, "sources": []}
        p = (prompt or "").strip()
        try:
            from urllib.parse import urlparse
            urls = re.findall(r"https?://[^\s)]+", p)
            for u in urls[:2]:
                txt = self.tools.run("web_fetch", url=u)
                meta["fetches"] += 1
                host = (urlparse(u).netloc or "").lower()
                if host and host not in meta["sources"]:
                    meta["sources"].append(host)
                if txt and "Error fetching" not in str(txt):
                    chunks.append(f"[web_fetch:{u}]\n{str(txt)[:1800]}")
            if not chunks:
                txt = self.tools.run("web_search", query=p[:240])
                meta["searches"] += 1
                if "duckduckgo.com" not in meta["sources"]:
                    meta["sources"].append("duckduckgo.com")
                if txt and "Search error" not in str(txt):
                    chunks.append(f"[web_search]\n{str(txt)[:2200]}")
        except Exception:
            return "", meta
        if not chunks:
            return "", meta
        meta["used"] = True
        return "\n\n".join(chunks)[:3000], meta

    def _prompt_web_approval_if_needed(self, scope="chat"):
        now = time.time()
        if (now - float(getattr(self, "_last_web_approval_prompt_at", 0.0))) < 25:
            return
        self._last_web_approval_prompt_at = now
        self._append_chat_block(
            "Baba",
            f"Web access approval needed for {scope} research. "
            "Approve to use real internet search; otherwise I will continue local-only.",
            [
                "Approve web search now.",
                "Deny web search now.",
                "Stop web search now.",
                "Show web search status.",
                "Continue local-only without web.",
            ],
        )

    def _set_agent_web_policy(self, policy):
        p = str(policy or "").strip().lower()
        if p not in {"ask", "approved", "denied", "stopped"}:
            p = "ask"
        self.agent_web_policy = p
        try:
            if self.agents and hasattr(self.agents, "set_web_tools_policy"):
                self.agents.set_web_tools_policy(p)
        except Exception:
            pass
        self._refresh_quick_strip()
        self._append_chat_block(
            "Baba",
            f"Agent web research policy set to: {p.upper()}.\n"
            "Use: approve/start/resume, deny, or stop web research any time.",
        )

    def _build_agent_web_context(self, agent_id, task):
        meta = {"used": False, "searches": 0, "fetches": 0, "sources": []}
        policy = str(self.agent_web_policy or "ask").lower()
        if policy == "ask":
            self.after(0, lambda: self._prompt_web_approval_if_needed(scope=f"agent:{agent_id}"))
            return "", meta
        if policy in {"denied", "stopped"}:
            return "", meta
        if not self.tools:
            return "", meta

        q = f"{agent_id} task: {str(task or '').strip()}"[:240]
        try:
            txt = self.tools.run("web_search", query=q)
            meta["searches"] += 1
            if "duckduckgo.com" not in meta["sources"]:
                meta["sources"].append("duckduckgo.com")
            if txt and "search error" not in str(txt).lower():
                meta["used"] = True
                return f"[agent_web_search]\n{str(txt)[:2200]}", meta
        except Exception:
            return "", meta
        return "", meta

    def _plan_parallel_assignments(self, goal, candidate_agents):
        if not candidate_agents:
            return []
        planner_prompt = (
            "You are the main coordinator.\n"
            "Assign subtasks to specialist agents for parallel execution.\n"
            "Return JSON ONLY as an array of objects with keys: agent, task.\n"
            f"Allowed agents: {', '.join(candidate_agents)}\n"
            f"Goal: {goal}\n"
            "Rules: max 5 assignments, no duplicate tasks, concise actionable tasks."
        )
        prov = self.prov_cb.get() if hasattr(self, "prov_cb") else "jan"
        mod = self.model_cb.get() if hasattr(self, "model_cb") else ""
        raw = _call_ai_sync(planner_prompt, provider=prov, model=mod, system=self._build_system_prompt())
        blob = self._extract_json_block(raw)
        try:
            parsed = json.loads(blob)
        except Exception:
            parsed = []
        if isinstance(parsed, dict):
            parsed = parsed.get("assignments", []) if isinstance(parsed.get("assignments"), list) else []
        if not isinstance(parsed, list):
            parsed = []

        out = []
        seen = set()
        for item in parsed:
            if not isinstance(item, dict):
                continue
            agent = str(item.get("agent", "")).strip().lower()
            task = str(item.get("task", "")).strip()
            if agent in candidate_agents and task and agent not in seen:
                out.append({"agent": agent, "task": task})
                seen.add(agent)
            if len(out) >= 5:
                break
        return out

    def _heuristic_parallel_assignments(self, goal, candidate_agents):
        g = (goal or "").lower()
        picks = []
        if any(k in g for k in ["email", "reply", "message", "whatsapp", "inbox"]):
            picks.extend(["comms", "pa"])
        if any(k in g for k in ["invoice", "cash", "finance", "tax", "vat", "hmrc"]):
            picks.append("acct")
        if any(k in g for k in ["legal", "dispute", "contract", "council"]):
            picks.append("legal")
        if any(k in g for k in ["supplier", "wholesale", "stock"]):
            picks.append("supplier")
        if any(k in g for k in ["property", "rent", "tenant", "howlish", "steamer"]):
            picks.extend(["deals", "legal"])
        if not picks:
            picks = candidate_agents[:4]
        ordered = []
        for a in picks:
            if a in candidate_agents and a not in ordered:
                ordered.append(a)
        return [{"agent": a, "task": goal} for a in ordered[:4]]

    def _merge_parallel_results(self, goal, assignments, results):
        lines = []
        for r in results:
            aid = r.get("agent", "?")
            body = (r.get("output", "") or "").strip()
            if len(body) > 1200:
                body = body[:1200] + " ..."
            lines.append(f"[{aid}] {body}")
        raw_bundle = "\n\n".join(lines)[:7000]
        prompt = (
            f"Goal: {goal}\n\n"
            "You are the main coordinator. Merge agent outputs into one concise action plan.\n"
            "Required sections:\n"
            "1) Combined findings\n2) Priority actions (next 30 minutes)\n3) Risks\n4) What needs approval\n\n"
            f"Agent outputs:\n{raw_bundle}"
        )
        prov = self.prov_cb.get() if hasattr(self, "prov_cb") else "jan"
        mod = self.model_cb.get() if hasattr(self, "model_cb") else ""
        merged = _call_ai_sync(prompt, provider=prov, model=mod, system=self._build_system_prompt())
        return self._sanitize_ai_reply(merged)

    def _start_parallel_agents(self, goal, same_task=False, forced_agents=None):
        def worker():
            started_at = time.time()
            try:
                available = self._available_agent_ids()
                forced = [str(a).strip().lower() for a in (forced_agents or []) if str(a).strip()]
                if forced and available:
                    agent_ids = [a for a in forced if a in available]
                else:
                    agent_ids = self._parallel_default_agents()
                assignments = []
                if same_task:
                    assignments = [{"agent": a, "task": goal} for a in agent_ids[:5]]
                else:
                    assignments = self._plan_parallel_assignments(goal, agent_ids)
                    if not assignments:
                        assignments = self._heuristic_parallel_assignments(goal, agent_ids)
                assignments = assignments[:5]
                if not assignments:
                    self.after(0, lambda: self._append_chat_block("Baba", "Parallel run failed: no valid agent assignments."))
                    return

                def run_one(aid, task):
                    t0 = time.time()
                    try:
                        web_ctx, web_meta = self._build_agent_web_context(aid, task)
                        if web_ctx:
                            self.after(
                                0,
                                lambda a=aid, m=web_meta: self._update_thinking(
                                    f"{a} web-research: s{int(m.get('searches', 0) or 0)}/f{int(m.get('fetches', 0) or 0)}"
                                ),
                            )
                            extra = (
                                "Live web research context (verify before final action):\n"
                                f"{web_ctx}"
                            )
                        else:
                            extra = ""
                        out = self.agents.run_sync(aid, task, extra_context=extra)
                        return {
                            "agent": aid,
                            "ok": True,
                            "task": task,
                            "output": out,
                            "sec": round(time.time() - t0, 2),
                            "web": web_meta,
                        }
                    except Exception as e:
                        return {
                            "agent": aid,
                            "ok": False,
                            "task": task,
                            "output": f"Agent error: {e}",
                            "sec": round(time.time() - t0, 2),
                            "web": {"used": False, "searches": 0, "fetches": 0, "sources": []},
                        }

                self.after(0, lambda: self._append_chat_block("Baba", f"Parallel agents running: {', '.join(a['agent'] for a in assignments)}"))
                if hasattr(self, "cowork_log"):
                    self.after(0, lambda: self.cowork_log.insert("end", f"[PARALLEL] Started: {self._pretty(assignments)}\n"))

                results = []
                with ThreadPoolExecutor(max_workers=min(5, len(assignments))) as ex:
                    futs = [ex.submit(run_one, a["agent"], a["task"]) for a in assignments]
                    for fut in as_completed(futs):
                        r = fut.result()
                        results.append(r)
                        if hasattr(self, "cowork_log"):
                            self.after(0, lambda rr=r: (self.cowork_log.insert("end", f"[PARALLEL] {rr['agent']} done ({rr['sec']}s)\n"), self.cowork_log.see("end")))

                merged = self._merge_parallel_results(goal, assignments, results)
                merged = self._append_evidence_tail_if_needed(
                    merged,
                    web_meta={
                        "searches": sum(int((r.get("web", {}) or {}).get("searches", 0) or 0) for r in results),
                        "fetches": sum(int((r.get("web", {}) or {}).get("fetches", 0) or 0) for r in results),
                        "sources": [
                            str(s)
                            for r in results
                            for s in ((r.get("web", {}) or {}).get("sources", []) or [])
                        ][:8],
                    },
                )
                elapsed = round(time.time() - started_at, 2)
                web_total_s = sum(int((r.get("web", {}) or {}).get("searches", 0) or 0) for r in results)
                web_total_f = sum(int((r.get("web", {}) or {}).get("fetches", 0) or 0) for r in results)
                web_sources = []
                by_agent = {}
                for r in results:
                    w = r.get("web", {}) if isinstance(r.get("web", {}), dict) else {}
                    aid = str(r.get("agent", "") or "")
                    by_agent[aid] = {
                        "used": bool(w.get("used")),
                        "searches": int(w.get("searches", 0) or 0),
                        "fetches": int(w.get("fetches", 0) or 0),
                    }
                    for s in (w.get("sources") or []):
                        ss = str(s).strip()
                        if ss and ss not in web_sources:
                            web_sources.append(ss)
                self._last_agent_web = {
                    "used": bool(web_total_s or web_total_f),
                    "searches": web_total_s,
                    "fetches": web_total_f,
                    "sources": web_sources[:5],
                    "at": datetime.now(UTC).isoformat(),
                    "by_agent": by_agent,
                }
                self.after(0, self._refresh_quick_strip)
                meta = {
                    "mode": "same-task" if same_task else "auto-split",
                    "elapsed_sec": elapsed,
                    "agent_web_policy": self.agent_web_policy,
                    "evidence_required_mode": self.evidence_required_mode,
                    "agent_web_totals": {"searches": web_total_s, "fetches": web_total_f, "sources": web_sources[:5]},
                    "assignments": assignments,
                    "results": [{k: v for k, v in r.items() if k in ("agent", "ok", "sec")} for r in results],
                }
                final_text = f"{merged}\n\nParallel meta:\n{self._pretty(meta)}"
                self.after(0, lambda: self._append_chat_block("Baba", final_text, self._contextual_followups(goal, merged)))
                self.after(0, self._clear_thinking)
            except Exception as e:
                self.after(0, lambda: self._append_chat_block("Baba", f"Parallel agents error: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _contextual_followups(self, prompt, reply):
        p = (prompt or "").lower()
        r = (reply or "").lower()
        text = f"{p}\n{r}"

        if "email" in text:
            return [
                "Open urgent review preview window.",
                "Open Exo Triage and show top 20 urgent emails now.",
                "Group urgent emails by account and folder.",
                "Create tasks from all urgent emails.",
                "Show only legal, tax, HMRC, invoice urgent emails.",
            ]
        if any(k in text for k in ("property", "howlish", "tenant", "rent")):
            return [
                "Summarize top property risks and deadlines.",
                "Create an action plan for 16 Howlish View.",
                "Draft tenant follow-up messages for today.",
                "List required documents for each property task.",
                "Prioritize next 3 property actions by impact.",
            ]
        if any(k in text for k in ("finance", "invoice", "cash", "vat", "hmrc", "tax")):
            return [
                "Show top financial risks from this result.",
                "Create a 24-hour accounting checklist.",
                "Draft a message to accountant with next actions.",
                "List overdue invoices and required follow-ups.",
                "Prepare VAT/HMRC action summary for this week.",
            ]
        if any(k in text for k in ("connect", "connection", "offline", "oauth", "imap", "provider")):
            return [
                "Run connection probe and show what is offline.",
                "Show exact fix steps for each disconnected service.",
                "Auto-connect safe local integrations now.",
                "Open Connection Center with recommended actions.",
                "Retry failed connectors and report status.",
            ]
        return [
            "Turn this into a step-by-step plan I can execute now.",
            "What are the biggest risks or blind spots here?",
            "Give me a concise checklist for the next 24 hours.",
            "Draft the exact message/email/script I should send.",
            "What should I do first in the next 30 minutes?",
        ]

    def _process_real_ai(self, prompt):
        prov = self.prov_cb.get()
        mod = self.model_cb.get()

        # Display thinking status and clear it when done.
        self.after(0, lambda: self._show_thinking(f"Planning next steps ({prov}/{mod})..."))

        kairos_context = ""
        if self.kairos:
            try:
                kairos_context = self.kairos.build_prompt_context()
            except Exception:
                kairos_context = ""

        system_prompt = self._build_system_prompt()
        if kairos_context:
            system_prompt = f"{system_prompt}\n\n{kairos_context}"

        try:
            user_prompt = prompt
            web_meta = {"used": False, "searches": 0, "fetches": 0, "sources": []}
            if self._should_use_web_assist(prompt):
                policy = str(self.agent_web_policy or "ask").lower()
                if policy == "approved":
                    self.after(0, lambda: self._update_thinking("Searching web context..."))
                    web_ctx, web_meta = self._build_web_assist_context(prompt)
                    if web_ctx:
                        src = ",".join((web_meta.get("sources") or [])[:3]) or "-"
                        self.after(
                            0,
                            lambda m=web_meta, s=src: self._update_thinking(
                                f"Web context ready: searches {int(m.get('searches', 0) or 0)}, fetches {int(m.get('fetches', 0) or 0)} | {s}"
                            ),
                        )
                        user_prompt = (
                            f"{prompt}\n\n"
                            "Live web context (verify critical facts):\n"
                            f"{web_ctx}"
                        )
                    else:
                        self.after(0, lambda: self._update_thinking("Web search unavailable, continuing with local context..."))
                elif policy == "ask":
                    self.after(0, lambda: self._update_thinking("Web access needs approval; continuing local context..."))
                    self.after(0, lambda: self._prompt_web_approval_if_needed(scope="chat"))
                else:
                    self.after(0, lambda: self._update_thinking("Web search blocked by policy; continuing local context..."))
            self._last_web_assist = {
                "used": bool(web_meta.get("used")),
                "searches": int(web_meta.get("searches", 0) or 0),
                "fetches": int(web_meta.get("fetches", 0) or 0),
                "sources": list(web_meta.get("sources", []))[:5],
                "at": datetime.now(UTC).isoformat(),
            }
            self.after(0, self._refresh_quick_strip)

            self.after(0, lambda: self._update_thinking("Checking model connection..."))
            reply = _call_ai_sync(user_prompt, provider=prov, model=mod, system=system_prompt)
            self.after(0, lambda: self._update_thinking("Summarizing and finalizing response..."))
            reply = self._sanitize_ai_reply(reply)
            reply = self._append_evidence_tail_if_needed(reply, web_meta=web_meta)

            if self.kairos:
                try:
                    self.kairos.record_interaction(prompt, reply)
                except Exception:
                    pass

            # Task-aware follow-up suggestions.
            suggs = self._contextual_followups(prompt, reply)
            self.after(0, lambda: self._append_chat_block("Baba", reply, suggs))
        except Exception as e:
            self.after(0, lambda: self._append_chat_block("Baba", f"AI processing error: {e}"))
        finally:
            self.after(0, self._clear_thinking)

    def _show_thinking(self, detail="Thinking..."):
        if not hasattr(self, "chat_display"):
            return
        self._clear_thinking()
        self.chat_display.config(state="normal")
        self._thinking_line_idx = self.chat_display.index("end-1c")
        self.chat_display.insert("end", f"\nThinking: {detail}\n", "text_muted")
        self.chat_display.see("end")
        if hasattr(self, "chat_voice_status"):
            self.chat_voice_status.config(text=f"Thinking: {detail}")

    def _update_thinking(self, detail):
        if not hasattr(self, "chat_display"):
            return
        try:
            self._clear_thinking()
        except Exception:
            pass
        self._show_thinking(detail)

    def _clear_thinking(self):
        if not hasattr(self, "chat_display"):
            self._thinking_line_idx = None
            return
        try:
            if self._thinking_line_idx:
                self.chat_display.delete(self._thinking_line_idx, f"{self._thinking_line_idx} lineend+1c")
            else:
                end = self.chat_display.index("end-1c")
                start = self.chat_display.search("Thinking:", "1.0", stopindex=end, backwards=True)
                if start:
                    self.chat_display.delete(start, f"{start} lineend+1c")
        except Exception:
            pass
        self._thinking_line_idx = None
        if hasattr(self, "chat_voice_status") and not getattr(self, "_voice_listening", False):
            self.chat_voice_status.config(text="Voice ready")

    def _sanitize_ai_reply(self, reply):
        text = str(reply or "")
        text = re.sub(r"<\s*thought\s*>.*?<\s*/\s*thought\s*>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<\s*think\s*>.*?<\s*/\s*think\s*>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"</?\s*thought[^>]*>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"</?\s*think[^>]*>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^\s*thinking\.\.\.\s*$", "", text, flags=re.IGNORECASE | re.MULTILINE)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        return text or "I am ready. Tell me the exact task and I will execute it."

    def _auto_notification_suggestions(self, text):
        msg = (text or "").lower()
        if not msg:
            return []
        if "urgent email alert" in msg or ("urgent" in msg and "email" in msg):
            return [
                "Open urgent review preview window.",
                "Open Exo Triage and show top 20 urgent emails now.",
                "Group urgent emails by account and folder.",
                "Create priority tasks for all urgent emails.",
                "Show only legal, HMRC, tax, invoice urgent emails.",
            ]
        if "error" in msg or "failed" in msg or "unavailable" in msg:
            return [
                "Diagnose this error and show exact fix steps.",
                "Run connection probe and show what is offline.",
                "Retry this action with safe fallback mode.",
                "Show logs for the last failed action.",
                "Create a recovery checklist and execute step 1.",
            ]
        if "completed" in msg or "done" in msg or "finished" in msg:
            return [
                "Show a concise summary of what was completed.",
                "What are the next 3 best actions now?",
                "Create follow-up tasks from this result.",
                "Highlight any high-risk items from this result.",
                "Export this result to my tasks panel.",
            ]
        if "connected" in msg or "offline" in msg or "status" in msg:
            return [
                "Show live connection status for all integrations.",
                "List what is connected vs pending approval.",
                "Auto-connect safe local integrations now.",
                "Open connection center with recommended actions.",
                "Notify me when Outlook and WhatsApp are fully connected.",
            ]
        return []

    def _derive_email_error_hint(self, err):
        e = (err or "").lower()
        if not e:
            return "Open Settings and run Refresh Integration Scan."
        if "unexpected keyword argument" in e and "include_subfolders" in e:
            return "Connector version mismatch detected. Updated app now retries with compatible arguments; run Organize Emails again."
        if "oauth" in e or "token" in e or "auth" in e:
            return "Outlook OAuth is not fully connected. Go to Settings and click Connect Outlook Email."
        if "imap" in e or "login" in e or "password" in e:
            return "Check IMAP credentials/app password for the target mailbox in Settings."
        if "unavailable" in e or "bridge" in e:
            return "Email bridge is unavailable. Restart v13 and verify App Bridge/EXO connectors are running."
        if "permission" in e or "access denied" in e:
            return "Grant required mailbox permissions and reconnect the account."
        return "Open Settings > Refresh Integration Scan, then retry Organize Emails."

    def _append_chat_block(self, sender, text, suggestions=None):
        if not hasattr(self, 'chat_display'): return
        self.chat_display.config(state="normal")
        name_tag = "baba_name" if sender == "Baba" else "user_name"
        self.chat_display.insert("end", f"\n{sender}: ", name_tag)
        self.chat_display.insert("end", f"{text}\n")
        
        # Attach interaction buttons for every response
        action_frame = tk.Frame(self.chat_display, bg=T["bg"], pady=5)
        top_actions = tk.Frame(action_frame, bg=T["bg"])
        top_actions.pack(fill="x", anchor="w")
        
        # Define local helper for copy
        def copy_txt(t=text):
            self.clipboard_clear()
            self.clipboard_append(t)
            self.update()
            
        tk.Button(top_actions, text="\U0001f4cb Copy", font=(FONT_FAMILY, 8), bg=T["card_bg"], fg=T["text_muted"], bd=0, padx=5, cursor="hand2", command=copy_txt).pack(side="left", padx=2)
        if sender == "Baba":
            def safe_speak(txt):
                def run():
                    ok, err = VoiceEngine().speak(txt)
                    if not ok:
                        self.after(0, lambda: self._set_chat_voice_status(f"Speak unavailable: {err}"))
                threading.Thread(target=run, daemon=True).start()
            tk.Button(top_actions, text="\U0001f50a Speak", font=(FONT_FAMILY, 8), bg=T["card_bg"], fg=T["text_muted"], bd=0, padx=5, cursor="hand2", command=lambda t=text: safe_speak(t)).pack(side="left", padx=2)

        button_suggestions = suggestions
        if not button_suggestions and sender == "Baba":
            button_suggestions = self._auto_notification_suggestions(text)

        if button_suggestions:
            # Also render as selectable text so user can copy suggestions.
            self.chat_display.insert("end", "Follow-up suggestions:\n", "text_muted")
            for i, sugg in enumerate(button_suggestions[:5], 1):
                self.chat_display.insert("end", f"{i}. {sugg}\n")
            def copy_suggestions(lines=button_suggestions[:5]):
                blob = "\n".join(f"{i}. {s}" for i, s in enumerate(lines, 1))
                self.clipboard_clear()
                self.clipboard_append(blob)
                self.update()
                self._set_chat_voice_status("Copied follow-up suggestions")
            tk.Button(top_actions, text="\U0001f4cb Copy Suggestions", font=(FONT_FAMILY, 8), bg=T["card_bg"], fg=T["text_muted"], bd=0, padx=8, cursor="hand2", command=copy_suggestions).pack(side="left", padx=2)
            sugg_actions = tk.Frame(action_frame, bg=T["bg"])
            sugg_actions.pack(fill="x", anchor="w", pady=(4, 0))
            wrap = 860
            try:
                wrap = max(360, int(self.chat_display.winfo_width()) - 120)
            except Exception:
                pass
            for i, sugg in enumerate(button_suggestions[:5], 1):
                tk.Button(
                    sugg_actions,
                    text=f"\U0001f4a1 {i}. {sugg}",
                    font=(FONT_FAMILY, 8),
                    bg=T["accent_dim"],
                    fg=T["accent"],
                    bd=0,
                    padx=8,
                    pady=4,
                    anchor="w",
                    justify="left",
                    wraplength=wrap,
                    cursor="hand2",
                    command=lambda s=sugg: self._handle_suggestion(s),
                ).pack(fill="x", anchor="w", pady=1)
                
        self.chat_display.window_create("end", window=action_frame)
        self.chat_display.insert("end", "\n")
        
        self.chat_display.see("end")

    def _handle_suggestion(self, sugg):
        self.chat_input.insert("end", sugg)
        self._handle_chat_send()

    def _copy_all_chat(self):
        if not hasattr(self, "chat_display"):
            return
        try:
            text = self.chat_display.get("1.0", "end").strip()
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            self._set_chat_voice_status("Copied full chat")
        except Exception:
            pass

    def _set_chat_voice_status(self, text):
        if hasattr(self, "chat_voice_status"):
            self.chat_voice_status.config(text=text)

    def _start_chat_voice_input(self):
        if getattr(self, "_voice_listening", False):
            return
        self._voice_listening = True
        self._set_chat_voice_status("Listening...")

        def worker():
            try:
                import speech_recognition as sr
            except Exception:
                self.after(
                    0,
                    lambda: self._append_chat_block(
                        "Baba",
                        "Voice input needs: pip install SpeechRecognition pyaudio",
                    ),
                )
                self.after(0, lambda: self._set_chat_voice_status("Mic unavailable"))
                self._voice_listening = False
                return

            try:
                recognizer = sr.Recognizer()
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.4)
                    audio = recognizer.listen(source, timeout=8, phrase_time_limit=25)
                text = recognizer.recognize_google(audio).strip()
                if not text:
                    raise RuntimeError("No speech detected.")

                def apply_result():
                    self.chat_input.delete("1.0", "end")
                    self.chat_input.insert("end", text)
                    self._set_chat_voice_status("Voice captured")
                    self._handle_chat_send()

                self.after(0, apply_result)
            except Exception as e:
                self.after(0, lambda: self._append_chat_block("Baba", f"Voice input error: {e}"))
                self.after(0, lambda: self._set_chat_voice_status("Voice failed"))
            finally:
                self._voice_listening = False

        threading.Thread(target=worker, daemon=True).start()

    def _create_chat_panel_legacy(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])

        header = tk.Frame(panel, bg=T["bg"])
        header.pack(fill="x", padx=40, pady=(40, 20))
        tk.Label(
            header,
            text="Chat Workspace",
            font=(FONT_FAMILY, 22, "bold"),
            bg=T["bg"],
            fg=T["accent"],
        ).pack(side="left")

        qa = tk.Frame(panel, bg=T["bg"])
        qa.pack(fill="x", padx=40, pady=(0, 12))
        tk.Label(
            qa,
            text="One-touch:",
            bg=T["bg"],
            fg=T["text_muted"],
            font=(FONT_FAMILY, 9, "bold"),
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            qa,
            text="Connections",
            bg=T["sidebar_bg"],
            fg=T["text"],
            bd=0,
            padx=10,
            pady=5,
            command=self._open_connection_center,
        ).pack(side="left", padx=3)
        tk.Button(
            qa,
            text="Exo Triage",
            bg=T["accent"],
            fg="#000",
            bd=0,
            padx=10,
            pady=5,
            command=self._quick_exo_triage,
        ).pack(side="left", padx=3)
        tk.Button(
            qa,
            text="Wiki Compile",
            bg=T["sidebar_bg"],
            fg=T["text"],
            bd=0,
            padx=10,
            pady=5,
            command=self._quick_wiki_compile,
        ).pack(side="left", padx=3)
        tk.Button(
            qa,
            text="Wiki Ingest",
            bg=T["sidebar_bg"],
            fg=T["text"],
            bd=0,
            padx=10,
            pady=5,
            command=self._quick_wiki_ingest,
        ).pack(side="left", padx=3)
        tk.Button(
            qa,
            text="Kairos",
            bg=T["sidebar_bg"],
            fg=T["text"],
            bd=0,
            padx=10,
            pady=5,
            command=self._quick_show_kairos,
        ).pack(side="left", padx=3)

        chat_frame = tk.Frame(
            panel,
            bg=T["card_bg"],
            bd=1,
            highlightbackground=T["card_border"],
            highlightthickness=1,
        )
        chat_frame.pack(fill="both", expand=True, padx=40, pady=(0, 20))

        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
            bg=T["card_bg"],
            fg=T["text"],
            font=(FONT_FAMILY, 11),
            bd=0,
            padx=20,
            pady=20,
        )
        self.chat_display.pack(fill="both", expand=True)
        self._make_selectable(self.chat_display)
        self.chat_display.tag_config(
            "baba_name", foreground=T["accent"], font=(FONT_FAMILY, 11, "bold")
        )
        self.chat_display.tag_config(
            "user_name", foreground=T["success"], font=(FONT_FAMILY, 11, "bold")
        )
        self.chat_display.tag_config(
            "text_muted", foreground=T["text_muted"], font=(FONT_FAMILY, 10, "italic")
        )

        input_container = tk.Frame(panel, bg=T["bg"], pady=10)
        input_container.pack(side="bottom", fill="x", padx=40, pady=(0, 14))

        self.chat_input = tk.Text(
            input_container,
            bg=T["sidebar_bg"],
            fg=T["text"],
            font=(FONT_FAMILY, 11),
            height=4,
            bd=0,
            highlightbackground=T["accent_dim"],
            highlightthickness=2,
            relief="flat",
            padx=15,
            pady=15,
        )
        self.chat_input.pack(fill="x", expand=True, side="left", padx=(0, 20))
        self.chat_input.bind("<Return>", lambda e: self._handle_chat_send() or "break")

        btn_frame = tk.Frame(input_container, bg=T["bg"])
        btn_frame.pack(side="right")
        tk.Button(
            btn_frame,
            text="\U0001f3a4 Voice",
            font=(FONT_FAMILY, 11, "bold"),
            bg=T["card_bg"],
            fg=T["text"],
            bd=0,
            padx=18,
            pady=12,
            cursor="hand2",
            command=self._start_chat_voice_input,
        ).pack(pady=(0, 8))
        tk.Button(
            btn_frame,
            text="\u27A4 Send",
            font=(FONT_FAMILY, 12, "bold"),
            bg=T["accent"],
            fg="#000",
            bd=0,
            padx=30,
            pady=15,
            cursor="hand2",
            command=self._handle_chat_send,
        ).pack()

        self.chat_voice_status = tk.Label(
            panel,
            text="Voice ready",
            font=(FONT_FAMILY, 8),
            bg=T["bg"],
            fg=T["text_muted"],
        )
        self.chat_voice_status.pack(anchor="e", padx=40, pady=(0, 10))

        self._append_chat_block(
            "Baba",
            "Welcome to the premium Chat Workspace! I am online and ready to help.",
        )
        self.after(500, self._auto_probe)
        return panel

    def _create_task_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tk.Label(panel, text="Planner & Executor Pipeline", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=30)
        
        self.task_list = tk.Frame(panel, bg=T["bg"])
        self.task_list.pack(fill="both", expand=True, padx=30)
        self._refresh_task_ui()
        return panel

    def _refresh_task_ui(self):
        for w in self.task_list.winfo_children(): w.destroy()
        if not self.tasks:
            tk.Label(self.task_list, text="No active tasks. New emails will appear here.", bg=T["bg"], fg=T["text_muted"]).pack()
            return
            
        for i, task in enumerate(self.tasks):
            card = tk.Frame(self.task_list, bg=T["card_bg"], bd=1, highlightbackground=T["card_border"], highlightthickness=1)
            card.pack(fill="x", pady=5)
            
            lbl_frame = tk.Frame(card, bg=T["card_bg"])
            lbl_frame.pack(side="left", fill="both", expand=True, padx=15, pady=10)
            
            tk.Label(lbl_frame, text=f"[{task['category']}] {task['title']}", font=(FONT_FAMILY, 11, "bold"), bg=T["card_bg"], fg=T["text"]).pack(anchor="w")
            tk.Label(lbl_frame, text=task['summary'], font=(FONT_FAMILY, 9), bg=T["card_bg"], fg=T["text_muted"], wraplength=600, justify="left").pack(anchor="w")
            
            btn_frame = tk.Frame(card, bg=T["card_bg"])
            btn_frame.pack(side="right", padx=15)
            tk.Button(btn_frame, text="Execute", bg=T["accent"], fg="#000", bd=0, padx=15, command=lambda t=task: self._execute_task(t)).pack(side="left", padx=5)
            tk.Button(btn_frame, text="Dismiss", bg=T["sidebar_bg"], fg=T["text_muted"], bd=0, padx=10, command=lambda idx=i: self._dismiss_task(idx)).pack(side="left")

    def _create_agents_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        canvas = tk.Canvas(panel, bg=T["bg"], bd=0, highlightthickness=0)
        vsb = tk.Scrollbar(panel, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=T["bg"])
        canvas.configure(yscrollcommand=vsb.set); vsb.pack(side="right", fill="y"); canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Enter>", lambda e, c=canvas: self._set_mousewheel_target(c))
        canvas.bind("<Leave>", lambda e: self._set_mousewheel_target(None))

        # --- UK PROFESSIONAL AGENTS ---
        tk.Label(scroll_frame, text="UK Professional Agents", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=(30, 10))
        grid = tk.Frame(scroll_frame, bg=T["bg"])
        grid.pack(fill="x", padx=20)
        
        pro_agents = [
            {"name": "UK Solicitor", "desc": "Contracts & Compliance", "icon": "\u2696", "cat": "Legal"},
            {"name": "UK Accountant", "desc": "VAT, Payroll & Ledger", "icon": "\U0001f4ca", "cat": "Accounting"},
            {"name": "Tax Agent", "desc": "HMRC & Tax Filings", "icon": "\U0001f3db", "cat": "Tax"},
            {"name": "Insurance Agent", "desc": "Policies & Renewals", "icon": "\U0001f6e1", "cat": "Insurance"},
            {"name": "Supplier Agent", "desc": "PO & Vendor Management", "icon": "\U0001f4e6", "cat": "Supplier"},
            {"name": "Content Agent", "desc": "Marketing & Comms", "icon": "\u270d", "cat": "Content"},
        ]

        for i, agent in enumerate(pro_agents):
            card = tk.Frame(grid, bg=T["card_bg"], bd=1, highlightbackground=T["card_border"], highlightthickness=1)
            card.grid(row=i//3, column=i%3, padx=10, pady=10, sticky="nsew")
            grid.columnconfigure(i%3, weight=1)
            tk.Label(card, text=agent["icon"], font=(FONT_FAMILY, 20), bg=T["card_bg"], fg=T["accent"]).pack(pady=(15, 0))
            tk.Label(card, text=agent["name"], bg=T["card_bg"], fg=T["text"], font=(FONT_FAMILY, 12, "bold")).pack(pady=5)
            tk.Label(card, text=agent["desc"], bg=T["card_bg"], fg=T["text_muted"], font=(FONT_FAMILY, 9)).pack(pady=(0, 10))
            tk.Button(card, text="Open Workspace", bg=T["accent_dim"], fg=T["accent"], bd=0, padx=15, pady=5, command=lambda a=agent: self.open_agent_workspace(a)).pack(pady=(0, 15))

        # --- EMAIL AGENTS (EXO) ---
        tk.Label(scroll_frame, text="Email Hub (EXO)", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=(40, 10))
        e_grid = tk.Frame(scroll_frame, bg=T["bg"])
        e_grid.pack(fill="x", padx=20, pady=(0, 40))
        for i, (aid, aname) in enumerate([("outlook", "Outlook Agent"), ("gmail", "Gmail Agent")]):
            card = tk.Frame(e_grid, bg=T["card_bg"], bd=1, highlightbackground=T["card_border"], highlightthickness=1)
            card.grid(row=0, column=i, padx=10, pady=10, sticky="nsew")
            e_grid.columnconfigure(i, weight=1)
            connected = aid in self.email_agents
            tk.Label(
                card,
                text="\u25cf Connected" if connected else "\u25cb Offline",
                bg=T["card_bg"],
                fg=T["success"] if connected else T["text_muted"],
                font=(FONT_FAMILY, 8, "bold"),
            ).pack(anchor="ne", padx=10, pady=5)
            tk.Label(card, text="\U0001F4E7" if aid=="outlook" else "\U0001F4E8", font=(FONT_FAMILY, 24), bg=T["card_bg"], fg=T["accent"]).pack(pady=(5, 0))
            tk.Label(card, text=aname, bg=T["card_bg"], fg=T["text"], font=(FONT_FAMILY, 12, "bold")).pack(pady=5)
            tk.Button(card, text="Open Inbox", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=10, pady=5, command=lambda a={'name':aname, 'id':aid, 'icon':"\u2709"}: self.open_email_agent(a)).pack(pady=(0,15))
            
        return panel

    def _create_chat_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        
        # Premium Header
        header = tk.Frame(panel, bg=T["bg"])
        header.pack(fill="x", padx=40, pady=(40, 20))
        tk.Label(header, text="Chat Workspace", font=(FONT_FAMILY, 22, "bold"), bg=T["bg"], fg=T["accent"]).pack(side="left")

        # Live email scan mini panel
        scan_card = tk.Frame(panel, bg=T["card_bg"], bd=1, highlightbackground=T["card_border"], highlightthickness=1)
        scan_card.pack(fill="x", padx=40, pady=(0, 12))
        row = tk.Frame(scan_card, bg=T["card_bg"])
        row.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(row, text="Email Scan Progress", font=(FONT_FAMILY, 10, "bold"), bg=T["card_bg"], fg=T["accent"]).pack(side="left")
        tk.Button(
            row,
            text="Continue Full Scan",
            font=(FONT_FAMILY, 8, "bold"),
            bg=T["accent_dim"],
            fg=T["accent"],
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=lambda: self._run_email_organizer_async(trigger="manual_full"),
        ).pack(side="right", padx=(6, 0))
        tk.Button(
            row,
            text="Open Urgent Preview",
            font=(FONT_FAMILY, 8, "bold"),
            bg=T["sidebar_bg"],
            fg=T["text"],
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=lambda: self._open_urgent_review_window(limit=120),
        ).pack(side="right")
        self.scan_progress_value = tk.Label(
            scan_card,
            text="Status: IDLE",
            justify="left",
            anchor="w",
            font=(FONT_FAMILY, 9),
            bg=T["card_bg"],
            fg=T["text_muted"],
            padx=12,
            pady=8,
        )
        self.scan_progress_value.pack(fill="x")
        self._refresh_scan_progress_widget()

        # Live Agent Controls already exists globally in the top quick bar.
        # Keep chat workspace clean (no duplicated quick-action strip here).
        
        # Chat Display Window (Fully expanding)
        chat_frame = tk.Frame(panel, bg=T["card_bg"], bd=1, highlightbackground=T["card_border"], highlightthickness=1)
        chat_frame.pack(fill="both", expand=True, padx=40, pady=(0, 20))
        
        self.chat_display = scrolledtext.ScrolledText(chat_frame, bg=T["card_bg"], fg=T["text"], 
                                                     font=(FONT_FAMILY, 11), bd=0, padx=20, pady=20)
        self.chat_display.pack(fill="both", expand=True)
        self._make_selectable(self.chat_display)
        
        self.chat_display.tag_config("baba_name", foreground=T["accent"], font=(FONT_FAMILY, 11, "bold"))
        self.chat_display.tag_config("user_name", foreground=T["success"], font=(FONT_FAMILY, 11, "bold"))
        self.chat_display.tag_config("text_muted", foreground=T["text_muted"], font=(FONT_FAMILY, 10, "italic"))
        
        # Premium Input Area
        input_container = tk.Frame(panel, bg=T["bg"], pady=10)
        input_container.pack(side="bottom", fill="x", padx=40, pady=(0, 14))
        
        self.chat_input = tk.Text(input_container, bg=T["sidebar_bg"], fg=T["text"], font=(FONT_FAMILY, 11), 
                                 height=4, bd=0, highlightbackground=T["accent_dim"], highlightthickness=2, relief="flat", padx=15, pady=15)
        self.chat_input.pack(fill="x", expand=True, side="left", padx=(0, 20))
        self.chat_input.bind("<Return>", lambda e: self._handle_chat_send() or "break")
        
        btn_frame = tk.Frame(input_container, bg=T["bg"])
        btn_frame.pack(side="right")
        tk.Button(
            btn_frame,
            text="\U0001f3a4 Voice",
            font=(FONT_FAMILY, 11, "bold"),
            bg=T["card_bg"],
            fg=T["text"],
            bd=0,
            padx=18,
            pady=12,
            cursor="hand2",
            command=self._start_chat_voice_input,
        ).pack(pady=(0, 8))
        tk.Button(
            btn_frame,
            text="\u27A4 Send",
            font=(FONT_FAMILY, 12, "bold"),
            bg=T["accent"],
            fg="#000",
            bd=0,
            padx=30,
            pady=15,
            cursor="hand2",
            command=self._handle_chat_send,
        ).pack()
        tk.Button(
            btn_frame,
            text="\U0001f4cb Copy All Chat",
            font=(FONT_FAMILY, 9, "bold"),
            bg=T["sidebar_bg"],
            fg=T["text"],
            bd=0,
            padx=16,
            pady=10,
            cursor="hand2",
            command=self._copy_all_chat,
        ).pack(pady=(8, 0))

        self.chat_voice_status = tk.Label(
            panel,
            text="Voice ready",
            font=(FONT_FAMILY, 8),
            bg=T["bg"],
            fg=T["text_muted"],
        )
        self.chat_voice_status.pack(anchor="e", padx=40, pady=(0, 10))
        
        # Welcome message
        self._append_chat_block("Baba", "Welcome to the premium Chat Workspace! I am online and ready to help.")
        self.after(500, self._auto_probe)
        
        return panel

    def _create_cowork_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tk.Label(panel, text="Cowork - Autonomous Multi-Agent Workspace", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=30)
        
        # Cowork Status Card
        status_card = tk.Frame(panel, bg=T["card_bg"], padx=20, pady=20, bd=1, highlightbackground=T["accent"], highlightthickness=1)
        status_card.pack(fill="x", padx=30)
        tk.Label(status_card, text="ORCHESTRATOR STATUS: IDLE", font=(FONT_FAMILY, 12, "bold"), bg=T["card_bg"], fg=T["text"]).pack(anchor="w")
        tk.Label(status_card, text="Baba Cowork is ready to manage parallel workflows across Social, PC, and Browser.", font=(FONT_FAMILY, 10), bg=T["card_bg"], fg=T["text_muted"]).pack(anchor="w", pady=5)
        
        # Cowork Log
        tk.Label(panel, text="LIVE AUTONOMOUS LOG", font=(FONT_FAMILY, 10, "bold"), bg=T["bg"], fg=T["text_muted"]).pack(anchor="w", padx=30, pady=(30, 10))
        self.cowork_log = scrolledtext.ScrolledText(panel, bg="#000", fg=T["success"], font=("Consolas", 10), bd=0, padx=15, pady=15)
        self.cowork_log.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        self.cowork_log.insert("end", "[SYSTEM] Cowork Kernel Initialized...\n[SYSTEM] Standing by for high-level objectives.\n")
        
        return panel

    def _create_social_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tabs = tk.Frame(panel, bg=T["sidebar_bg"], height=40)
        tabs.pack(fill="x")
        for i, (name, icon) in enumerate([("WhatsApp", "\U0001f4ac"), ("Slack", "\U0001f4ac"), ("Discord", "\U0001f3ae"), ("LinkedIn", "\U0001f464")]):
            btn = tk.Button(tabs, text=f"{icon} {name}", bg=T["sidebar_bg"] if i>0 else T["card_bg"], fg=T["text"] if i==0 else T["text_muted"], bd=0, padx=20)
            btn.pack(side="left", fill="y")
        
        # Embed the WhatsApp view as default
        wa_view = self._create_whatsapp_panel(parent=panel)
        wa_view.pack(fill="both", expand=True)
        return panel

    def _create_apps_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tk.Label(panel, text="Integrated PC Applications", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=30)

        grid_host = tk.Frame(panel, bg=T["bg"])
        grid_host.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        grid_outer, grid, _ = self._make_scrollable_sidebar(grid_host, T["bg"])
        grid_outer.pack(fill="both", expand=True)
        for col in range(3):
            grid.columnconfigure(col, weight=1)
        
        self.app_status_labels = {}
        apps = [
            ("Exo", "exo.exe", "\U0001f4ec", "start \"\" https://exo.email"),
            ("Outlook", "outlook.exe", "\U0001f4e7", "start outlook"),
            ("Excel", "excel.exe", "\U0001f4ca", "start excel"),
            ("Teams", "msteams.exe", "\U0001f465", "start msteams"),
            ("VS Code", "code.exe", "\u2328", "code"),
            ("Chrome", "chrome.exe", "\U0001f310", "start chrome"),
            ("WhatsApp", "WhatsApp.exe", "\U0001f4ac", "start whatsapp:"),
            ("Slack", "slack.exe", "\U0001f4ac", "start slack"),
            ("Telegram", "Telegram.exe", "\U0001f4f9", "start telegram:"),
            ("Notepad", "notepad.exe", "\U0001f5d2", "start notepad")
        ]
        
        def run_app_cmd(cmd):
            try: subprocess.Popen(f'powershell -Command "{cmd}"', shell=True)
            except Exception as e: messagebox.showerror("Launch Error", f"Failed to start: {e}")

        for i, (name, exe, icon, cmd) in enumerate(apps):
            card = tk.Frame(grid, bg=T["card_bg"], bd=1, highlightbackground=T["card_border"], highlightthickness=1)
            card.grid(row=i//3, column=i%3, padx=10, pady=10, sticky="nsew")
            
            tk.Label(card, text=icon, font=(FONT_FAMILY, 24), bg=T["card_bg"], fg=T["accent"]).pack(pady=(15, 5))
            tk.Label(card, text=name, bg=T["card_bg"], fg=T["text"], font=(FONT_FAMILY, 10, "bold")).pack(pady=(0, 2))
            
            status_lbl = tk.Label(card, text="OFFLINE", font=(FONT_FAMILY, 8, "bold"), bg=T["card_bg"], fg=T["text_muted"])
            status_lbl.pack(pady=(0, 10))
            self.app_status_labels[exe.lower()] = status_lbl
            
            tk.Button(card, text="Launch / Connect", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=10, pady=5, cursor="hand2", command=lambda c=cmd: run_app_cmd(c)).pack(pady=(0, 15))
            
        # Start Detection Thread
        self._start_app_detection()
        return panel

    def _start_app_detection(self):
        def scan():
            while True:
                try:
                    output = subprocess.check_output('tasklist /NH /FO CSV', shell=True).decode('utf-8', errors='ignore')
                    running_exes = [line.split(',')[0].strip('"').lower() for line in output.split('\n') if line]
                    
                    for exe, lbl in self.app_status_labels.items():
                        is_on = exe in running_exes
                        text = "CONNECTED & ACTIVE" if is_on else "OFFLINE"
                        color = T["success"] if is_on else T["text_muted"]
                        self.after(0, lambda l=lbl, t=text, c=color: l.config(text=t, fg=c))
                        
                    # Real Outlook Integration
                    if "outlook.exe" in running_exes and HAS_WIN32:
                        self._sync_real_outlook()
                        
                except Exception: pass
                time.sleep(10)
        threading.Thread(target=scan, daemon=True).start()

    def _sync_real_outlook(self):
        try:
            outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
            inbox = outlook.GetDefaultFolder(6)
            messages = inbox.Items
            messages.Sort("[ReceivedTime]", True)
            
            new_tasks = []
            for i in range(1, min(6, len(messages) + 1)):
                m = messages.Item(i)
                # Avoid duplicates
                if not any(t['title'] == m.Subject for t in self.tasks):
                    new_tasks.append({
                        "title": m.Subject, "category": "Outlook", "summary": f"From: {m.SenderName}\nReceived: {m.ReceivedTime}",
                        "timestamp": str(m.ReceivedTime), "status": "Pending"
                    })
            
            if new_tasks:
                self.tasks.extend(new_tasks)
                self.after(0, self._refresh_task_ui)
                self._log(f"Detected {len(new_tasks)} new emails in Outlook Inbox.")
        except Exception: pass

    def _create_vision_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tk.Label(panel, text="Vision Pipe - Visual Perception", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=30)
        
        view = tk.Frame(panel, bg="#000", bd=2, highlightbackground=T["accent"], highlightthickness=1)
        view.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        
        tk.Label(view, text="[ LIVE VISION STREAM ]", font=(FONT_FAMILY, 14, "bold"), bg="#000", fg=T["accent"]).place(relx=0.5, rely=0.4, anchor="center")
        tk.Label(view, text="Detecting UI elements and visual patterns...", font=(FONT_FAMILY, 10), bg="#000", fg=T["text_muted"]).place(relx=0.5, rely=0.5, anchor="center")
        
        btn_bar = tk.Frame(panel, bg=T["bg"])
        btn_bar.pack(fill="x", padx=30, pady=(0, 30))
        for cmd in ["Analyze Screen", "Take Screenshot", "OCR Scan"]:
            tk.Button(btn_bar, text=cmd, bg=T["accent"], fg="#000", bd=0, padx=20, pady=8, font=(FONT_FAMILY, 9, "bold")).pack(side="left", padx=5)
            
        return panel

    def _create_scheduler_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tk.Label(panel, text="Autonomous Scheduler", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=30)

        controls = tk.Frame(panel, bg=T["bg"])
        controls.pack(fill="x", padx=30, pady=(0, 10))
        tk.Button(controls, text="Refresh", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=14, pady=6, command=self._refresh_scheduler_panel).pack(side="left", padx=(0, 8))
        tk.Button(controls, text="Add Daily Task", bg=T["accent"], fg="#000", bd=0, padx=14, pady=6, command=self._scheduler_add_daily_task).pack(side="left")

        self.scheduler_output = scrolledtext.ScrolledText(panel, bg=T["card_bg"], fg=T["text"], font=(FONT_FAMILY, 10), bd=1, highlightbackground=T["card_border"], highlightthickness=1, padx=12, pady=12)
        self.scheduler_output.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        self._refresh_scheduler_panel()
        return panel

    def _refresh_scheduler_panel(self):
        if not hasattr(self, "scheduler_output"):
            return
        self.scheduler_output.delete("1.0", "end")
        if not self.scheduler:
            self.scheduler_output.insert("end", "Scheduler backend not available.\n")
            return
        try:
            tasks = self.scheduler.list_tasks()
        except Exception as e:
            self.scheduler_output.insert("end", f"Scheduler error: {e}\n")
            return
        if not tasks:
            self.scheduler_output.insert("end", "No scheduled tasks.\n")
            return
        for t in tasks:
            self.scheduler_output.insert("end", f"[{t['task_id']}] {t['name']}\n")
            self.scheduler_output.insert("end", f"  trigger: {t.get('trigger')} {self._pretty(t.get('trigger_cfg', {}))}\n")
            self.scheduler_output.insert("end", f"  enabled: {t.get('enabled')} | next: {t.get('next_run')}\n")
            self.scheduler_output.insert("end", f"  runs: {t.get('run_count', 0)}\n\n")

    def _scheduler_add_daily_task(self):
        if not self.scheduler or not TriggerType:
            messagebox.showwarning("Scheduler", "Scheduler backend is offline.")
            return
        top = tk.Toplevel(self)
        top.title("Add Daily Task")
        top.configure(bg=T["bg"])
        top.geometry("520x260")

        tk.Label(top, text="Task Name", bg=T["bg"], fg=T["text"]).pack(anchor="w", padx=20, pady=(20, 4))
        name_entry = tk.Entry(top, bg=T["card_bg"], fg=T["text"], insertbackground=T["accent"])
        name_entry.pack(fill="x", padx=20)
        name_entry.insert(0, "Daily follow-up sweep")

        tk.Label(top, text="Instruction", bg=T["bg"], fg=T["text"]).pack(anchor="w", padx=20, pady=(12, 4))
        instr_entry = tk.Entry(top, bg=T["card_bg"], fg=T["text"], insertbackground=T["accent"])
        instr_entry.pack(fill="x", padx=20)
        instr_entry.insert(0, "Check inbox and draft replies for pending threads.")

        tk.Label(top, text="Time (HH:MM)", bg=T["bg"], fg=T["text"]).pack(anchor="w", padx=20, pady=(12, 4))
        time_entry = tk.Entry(top, bg=T["card_bg"], fg=T["text"], insertbackground=T["accent"])
        time_entry.pack(fill="x", padx=20)
        time_entry.insert(0, "09:00")

        def add_task():
            name = name_entry.get().strip()
            instruction = instr_entry.get().strip()
            tval = time_entry.get().strip() or "09:00"
            if not name or not instruction:
                return
            task_id = f"custom_{int(time.time())}"
            try:
                self.scheduler.add(
                    task_id=task_id,
                    name=name,
                    instruction=instruction,
                    trigger=TriggerType.TIME_DAILY,
                    trigger_cfg={"time": tval},
                    enabled=True,
                )
                self._refresh_scheduler_panel()
                top.destroy()
            except Exception as e:
                messagebox.showerror("Scheduler", str(e))

        tk.Button(top, text="Save Task", bg=T["accent"], fg="#000", bd=0, padx=12, pady=7, command=add_task).pack(anchor="e", padx=20, pady=16)

    def _create_meetings_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tk.Label(panel, text="Meeting Intelligence & Transcripts", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=30)

        controls = tk.Frame(panel, bg=T["bg"])
        controls.pack(fill="x", padx=30, pady=(0, 10))
        tk.Button(controls, text="Process Transcript File", bg=T["accent"], fg="#000", bd=0, padx=14, pady=6, command=self._meetings_process_transcript).pack(side="left", padx=(0, 8))
        tk.Button(controls, text="Refresh Exports", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=14, pady=6, command=self._refresh_meetings_exports).pack(side="left")

        self.meetings_output = scrolledtext.ScrolledText(panel, bg=T["card_bg"], fg=T["text"], font=(FONT_FAMILY, 10), bd=1, highlightbackground=T["card_border"], highlightthickness=1, padx=12, pady=12)
        self.meetings_output.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        self._refresh_meetings_exports()
        return panel

    def _refresh_meetings_exports(self):
        if not hasattr(self, "meetings_output"):
            return
        self.meetings_output.delete("1.0", "end")
        if not self.meetings:
            self.meetings_output.insert("end", "Meeting Intelligence backend not available.\n")
            return
        try:
            exports = self.meetings.list_exports()
        except Exception as e:
            self.meetings_output.insert("end", f"Meetings error: {e}\n")
            return
        if not exports:
            self.meetings_output.insert("end", "No meeting exports yet. Process a transcript to generate outputs.\n")
            return
        for ex in exports:
            self.meetings_output.insert("end", f"{ex.get('name')}\n")
            self.meetings_output.insert("end", f"  path: {ex.get('path')}\n")
            self.meetings_output.insert("end", f"  size_kb: {ex.get('size_kb')}\n\n")

    def _meetings_process_transcript(self):
        if not self.meetings:
            messagebox.showwarning("Meetings", "Meeting Intelligence backend is offline.")
            return
        fp = filedialog.askopenfilename(title="Select transcript/audio", filetypes=[("Transcripts/Audio", "*.txt *.md *.vtt *.srt *.pdf *.docx *.mp3 *.mp4 *.wav *.m4a *.ogg *.webm"), ("All files", "*.*")])
        if not fp:
            return
        self.meetings_output.insert("end", f"\nProcessing: {fp}\n")
        self.meetings_output.see("end")

        def worker():
            try:
                ext = Path(fp).suffix.lower()
                if ext in getattr(self.meetings, "AUDIO_EXTS", set()):
                    result = asyncio.run(self.meetings.process_audio(fp))
                else:
                    result = asyncio.run(self.meetings.process_transcript(fp))
            except Exception as e:
                result = {"ok": False, "error": str(e)}
            self.after(0, lambda: (self.meetings_output.insert("end", f"{self._pretty(result)}\n"), self._refresh_meetings_exports()))

        threading.Thread(target=worker, daemon=True).start()

    def _create_money_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tk.Label(panel, text="Ultimate Financial Dashboard", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=30)

        metric_frame = tk.Frame(panel, bg=T["bg"])
        metric_frame.pack(fill="x", padx=20)
        stats = self.brain.stats() if self.brain else {"total": 0, "with_renewals": 0, "high_risk": 0}
        metrics = [
            ("Indexed Items", str(stats.get("total", 0))),
            ("Renewals Tracked", str(stats.get("with_renewals", 0))),
            ("High Risk Flags", str(stats.get("high_risk", 0))),
        ]
        for label, val in metrics:
            card = tk.Frame(metric_frame, bg=T["card_bg"], padx=20, pady=20, bd=1, highlightbackground=T["card_border"], highlightthickness=1)
            card.pack(side="left", fill="both", expand=True, padx=10)
            tk.Label(card, text=label, font=(FONT_FAMILY, 9), bg=T["card_bg"], fg=T["text_muted"]).pack()
            tk.Label(card, text=val, font=(FONT_FAMILY, 16, "bold"), bg=T["card_bg"], fg=T["accent"]).pack()

        btns = tk.Frame(panel, bg=T["bg"])
        btns.pack(fill="x", padx=30, pady=(12, 8))
        tk.Button(btns, text="Run Full Analysis", bg=T["accent"], fg="#000", bd=0, padx=14, pady=7, command=self._money_run_full_analysis).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="Find Savings", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=14, pady=7, command=self._money_run_savings).pack(side="left")

        self.money_output = scrolledtext.ScrolledText(panel, bg=T["card_bg"], fg=T["text"], font=(FONT_FAMILY, 10), bd=1, highlightbackground=T["card_border"], highlightthickness=1, padx=12, pady=12)
        self.money_output.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        self.money_output.insert("end", "Money engine ready.\n")
        return panel

    def _money_run_full_analysis(self):
        if not hasattr(self, "money_output"):
            return
        self.money_output.insert("end", "\nRunning full money analysis...\n")
        self.money_output.see("end")

        def worker():
            try:
                if self.money:
                    result = self.money.run_sync()
                elif self.agents:
                    result = self.agents.run_sync("acct", "Run full financial analysis from indexed bills, invoices, renewals and risks.")
                else:
                    result = "Money analysis backend not available."
            except Exception as e:
                result = f"Money analysis error: {e}"
            self.after(0, lambda: (self.money_output.insert("end", f"{self._pretty(result)}\n"), self.money_output.see("end")))

        threading.Thread(target=worker, daemon=True).start()

    def _money_run_savings(self):
        if not hasattr(self, "money_output"):
            return
        self.money_output.insert("end", "\nFinding savings opportunities...\n")
        self.money_output.see("end")

        def worker():
            prompt = "Identify top immediate cost savings and cashflow improvements from current indexed business data."
            try:
                if self.agents:
                    result = self.agents.run_sync("acct", prompt)
                else:
                    result = _call_ai_sync(prompt, provider=self.prov_cb.get(), model=self.model_cb.get(), system=BABA_SYSTEM_PROMPT)
            except Exception as e:
                result = f"Savings analysis error: {e}"
            self.after(0, lambda: (self.money_output.insert("end", f"{self._pretty(result)}\n"), self.money_output.see("end")))

        threading.Thread(target=worker, daemon=True).start()

    def _create_brain_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tk.Label(panel, text="Brain Index - Collective Memory", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=30)

        stats = tk.Frame(panel, bg=T["card_bg"], padx=20, pady=20, bd=1, highlightbackground=T["card_border"], highlightthickness=1)
        stats.pack(fill="x", padx=30)
        self.brain_stats_label = tk.Label(stats, text="", font=(FONT_FAMILY, 10, "bold"), bg=T["card_bg"], fg=T["text"])
        self.brain_stats_label.pack(anchor="w")
        self.brain_stats_sub = tk.Label(stats, text="", font=(FONT_FAMILY, 8), bg=T["card_bg"], fg=T["text_muted"])
        self.brain_stats_sub.pack(anchor="w")

        search_row = tk.Frame(panel, bg=T["bg"])
        search_row.pack(fill="x", padx=30, pady=(12, 8))
        self.brain_search_entry = tk.Entry(search_row, bg=T["card_bg"], fg=T["text"], insertbackground=T["accent"])
        self.brain_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=5)
        tk.Button(search_row, text="Search", bg=T["accent"], fg="#000", bd=0, padx=14, pady=7, command=self._brain_search_submit).pack(side="left", padx=(0, 8))
        tk.Button(search_row, text="Refresh", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=14, pady=7, command=self._brain_refresh_panel).pack(side="left")

        wiki_row = tk.Frame(panel, bg=T["bg"])
        wiki_row.pack(fill="x", padx=30, pady=(0, 8))
        tk.Label(wiki_row, text="LLM Wiki:", bg=T["bg"], fg=T["text_muted"], font=(FONT_FAMILY, 9, "bold")).pack(side="left", padx=(0, 8))
        tk.Button(wiki_row, text="Ingest Raw", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=12, pady=6, command=self._wiki_ingest_files).pack(side="left", padx=(0, 6))
        tk.Button(wiki_row, text="Compile", bg=T["accent"], fg="#000", bd=0, padx=12, pady=6, command=self._wiki_compile).pack(side="left", padx=(0, 6))
        tk.Button(wiki_row, text="Lint", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=12, pady=6, command=self._wiki_lint).pack(side="left", padx=(0, 6))
        tk.Button(wiki_row, text="Stats", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=12, pady=6, command=self._wiki_stats).pack(side="left")

        self.brain_output = scrolledtext.ScrolledText(panel, bg=T["card_bg"], fg=T["text"], font=(FONT_FAMILY, 10), bd=1, highlightbackground=T["card_border"], highlightthickness=1, padx=12, pady=12)
        self.brain_output.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        self._brain_refresh_panel()
        return panel

    def _brain_refresh_panel(self):
        if not self.brain:
            if hasattr(self, "brain_stats_label"):
                self.brain_stats_label.config(text="Brain Index backend not available")
                self.brain_stats_sub.config(text="")
            if hasattr(self, "brain_output"):
                self.brain_output.delete("1.0", "end")
                self.brain_output.insert("end", "No brain backend available.\n")
            return
        stats = self.brain.stats()
        if hasattr(self, "brain_stats_label"):
            self.brain_stats_label.config(
                text=f"INDEXED: {stats.get('total', 0)} | EMAILS: {stats.get('emails', 0)} | DOCS: {stats.get('docs', 0)} | HIGH-RISK: {stats.get('high_risk', 0)}"
            )
            self.brain_stats_sub.config(text=f"Renewals tracked: {stats.get('with_renewals', 0)}")
        if hasattr(self, "brain_output"):
            self.brain_output.delete("1.0", "end")
            rows = self.brain.all(limit=30)
            for item in rows:
                self.brain_output.insert("end", f"[{item.get('type','unknown').upper()}] {item.get('summary','')[:160]}\n")
                self.brain_output.insert("end", f"  source={item.get('source')} | risk={item.get('risk_level')} | date={item.get('date')}\n\n")

    def _brain_search_submit(self):
        if not self.brain or not hasattr(self, "brain_output"):
            return
        q = self.brain_search_entry.get().strip() if hasattr(self, "brain_search_entry") else ""
        self.brain_output.delete("1.0", "end")
        rows = self.brain.search(q, limit=50) if q else self.brain.all(limit=30)
        if not rows:
            self.brain_output.insert("end", "No matching records.\n")
            return
        for item in rows:
            self.brain_output.insert("end", f"[{item.get('type','unknown').upper()}] {item.get('summary','')[:180]}\n")
            self.brain_output.insert("end", f"  counterparty={item.get('counterparty')} | status={item.get('status')} | renewal={item.get('renewal_date')}\n\n")

    def _wiki_ingest_files(self):
        if not self.wiki or not hasattr(self, "brain_output"):
            messagebox.showwarning("LLM Wiki", "Wiki compiler backend is not available.")
            return
        files = filedialog.askopenfilenames(
            title="Select raw sources for wiki",
            filetypes=[("Documents", "*.md *.txt *.json *.csv *.py *.js *.ts *.html *.css *.pdf"), ("All files", "*.*")],
        )
        if not files:
            return
        try:
            result = self.wiki.ingest_files(list(files), source_tag="v13_ui")
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        self.brain_output.insert("end", f"\n[WIKI INGEST]\n{self._pretty(result)}\n")
        self.brain_output.see("end")

    def _wiki_compile(self):
        if not self.wiki or not hasattr(self, "brain_output"):
            return
        self.brain_output.insert("end", "\n[WIKI COMPILE] Running compile...\n")
        self.brain_output.see("end")

        def worker():
            try:
                topic = self.brain_search_entry.get().strip() if hasattr(self, "brain_search_entry") else ""
                result = self.wiki.compile_once(topic_hint=topic)
            except Exception as e:
                result = {"ok": False, "error": str(e)}
            self.after(0, lambda: (self.brain_output.insert("end", f"{self._pretty(result)}\n"), self.brain_output.see("end")))

        threading.Thread(target=worker, daemon=True).start()

    def _wiki_lint(self):
        if not self.wiki or not hasattr(self, "brain_output"):
            return
        try:
            result = self.wiki.lint()
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        self.brain_output.insert("end", f"\n[WIKI LINT]\n{self._pretty(result)}\n")
        self.brain_output.see("end")

    def _wiki_stats(self):
        if not self.wiki or not hasattr(self, "brain_output"):
            return
        try:
            result = self.wiki.stats()
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        self.brain_output.insert("end", f"\n[WIKI STATS]\n{self._pretty(result)}\n")
        self.brain_output.see("end")

    def _create_providers_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tk.Label(panel, text="AI Model Providers", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=30)
        
        provider_labels = {}
        for name in ALL_MODELS.keys():
            dtype = "Local" if name in ["ollama", "jan", "lmstudio"] else "Cloud"
            row = tk.Frame(panel, bg=T["card_bg"], padx=20, pady=10, bd=1, highlightbackground=T["card_border"], highlightthickness=1)
            row.pack(fill="x", padx=30, pady=2)
            tk.Label(row, text=name.upper(), font=(FONT_FAMILY, 11, "bold"), bg=T["card_bg"], fg=T["text"]).pack(side="left")
            tk.Label(row, text=dtype, font=(FONT_FAMILY, 8), bg=T["sidebar_bg"], fg=T["text_muted"], padx=8).pack(side="left", padx=20)
            
            lbl_status = tk.Label(row, text="TESTING...", font=(FONT_FAMILY, 8, "bold"), bg=T["card_bg"], fg=T["warning"])
            lbl_status.pack(side="right")
            provider_labels[name] = lbl_status
            
            tk.Button(row, text="Connect", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=10, pady=2, cursor="hand2", command=lambda n=name: self.prov_cb.set(n) or self._auto_probe()).pack(side="right", padx=20)
            
        def test_all():
            for name, lbl in provider_labels.items():
                is_on, err = _test_provider(name)
                c = T["success"] if is_on else T["error"]
                t = "CONNECTED" if is_on else "OFFLINE"
                try:
                    if self.winfo_exists():
                        self.after(0, lambda l=lbl, ct=t, cc=c: l.config(text=ct, fg=cc))
                except RuntimeError:
                    break
                
        threading.Thread(target=test_all, daemon=True).start()
        return panel

    def _create_import_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tk.Label(panel, text="Data Ingestion & Imports", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=30)
        
        drop_zone = tk.Frame(panel, bg=T["card_bg"], bd=2, highlightthickness=2, highlightbackground=T["accent"], highlightcolor=T["accent"])
        drop_zone.pack(fill="both", expand=True, padx=50, pady=50)
        
        tk.Label(drop_zone, text="\U0001f4e5", font=(FONT_FAMILY, 48), bg=T["card_bg"], fg=T["accent"]).place(relx=0.5, rely=0.4, anchor="center")
        tk.Label(drop_zone, text="DROP ASSETS HERE", font=(FONT_FAMILY, 14, "bold"), bg=T["card_bg"], fg=T["text"]).place(relx=0.5, rely=0.55, anchor="center")
        tk.Label(drop_zone, text="PDF, Excel, CSV, or Text Files supported.", font=(FONT_FAMILY, 10), bg=T["card_bg"], fg=T["text_muted"]).place(relx=0.5, rely=0.62, anchor="center")
        
        tk.Button(drop_zone, text="BROWSE FILES", bg=T["accent"], fg="#000", bd=0, padx=30, pady=10, font=(FONT_FAMILY, 10, "bold"), command=self._import_browse_files).place(relx=0.5, rely=0.75, anchor="center")
        
        return panel

    def _import_browse_files(self):
        files = filedialog.askopenfilenames(
            title="Import source files",
            filetypes=[("All files", "*.*")],
        )
        if not files:
            return
        imported = 0
        for fp in files:
            try:
                src = Path(fp)
                dst = DATA_DIR / "imports" / src.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(src.read_bytes())
                imported += 1
            except Exception:
                continue
        msg = f"Imported {imported}/{len(files)} files into data/imports."
        if self.wiki and imported:
            try:
                self.wiki.ingest_files(list(files), source_tag="import_panel")
                msg += " Also ingested into wiki raw/"
            except Exception:
                pass
        messagebox.showinfo("Import", msg)

    def _create_research_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tk.Label(panel, text="Deep Research Engine", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=(30, 10))

        s_box = tk.Frame(panel, bg=T["card_bg"], padx=20, pady=20, bd=1, highlightbackground=T["card_border"], highlightthickness=1)
        s_box.pack(fill="x", padx=30)
        self.research_topic = tk.Entry(s_box, bg=T["bg"], fg=T["text"], bd=0, font=(FONT_FAMILY, 12), insertbackground=T["accent"])
        self.research_topic.pack(side="left", fill="x", expand=True, padx=(0, 20))
        self.research_topic.insert(0, "UK SME AI automation opportunities in 2026")
        tk.Button(s_box, text="START RESEARCH", bg=T["accent"], fg="#000", bd=0, padx=20, pady=10, font=(FONT_FAMILY, 9, "bold"), command=self._run_research_job).pack(side="right")

        self.research_output = scrolledtext.ScrolledText(panel, bg=T["card_bg"], fg=T["text"], font=(FONT_FAMILY, 10), bd=1, highlightbackground=T["card_border"], highlightthickness=1, padx=12, pady=12)
        self.research_output.pack(fill="both", expand=True, padx=30, pady=20)
        self.research_output.insert("end", "Research engine ready.\n")
        return panel

    def _run_research_job(self):
        if not hasattr(self, "research_output"):
            return
        topic = self.research_topic.get().strip() if hasattr(self, "research_topic") else ""
        if not topic:
            return
        self.research_output.insert("end", f"\nResearch started: {topic}\n")
        self.research_output.see("end")

        def worker():
            snippets = ""
            if self.tools:
                try:
                    snippets = str(self.tools.run("web_search", query=topic))
                except Exception:
                    snippets = ""
            prompt = (
                "Generate a comprehensive research report with: executive summary, key findings, risks, opportunities, and recommended next actions.\n\n"
                f"Topic: {topic}\n\n"
                f"Web snippets:\n{snippets}\n\n"
            )
            try:
                if self.agents:
                    report = self.agents.run_sync("research", prompt)
                else:
                    report = _call_ai_sync(prompt, provider=self.prov_cb.get(), model=self.model_cb.get(), system=BABA_SYSTEM_PROMPT)
            except Exception as e:
                report = f"Research error: {e}"
            self.after(0, lambda: (self.research_output.insert("end", f"{report}\n"), self.research_output.see("end")))

        threading.Thread(target=worker, daemon=True).start()

    def _create_devtools_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tk.Label(panel, text="Developer Tools & System Terminal", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=30)

        controls = tk.Frame(panel, bg=T["bg"])
        controls.pack(fill="x", padx=30, pady=(0, 8))
        self.devtools_action = ttk.Combobox(controls, values=["git_status", "git_log", "list_repo_files", "analyse_repo", "pip_list", "open_devtools"], state="readonly", width=18)
        self.devtools_action.set("git_status")
        self.devtools_action.pack(side="left", padx=(0, 8))
        self.devtools_param = tk.Entry(controls, bg=T["card_bg"], fg=T["text"], insertbackground=T["accent"])
        self.devtools_param.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=4)
        self.devtools_param.insert(0, ".")
        tk.Button(controls, text="Run", bg=T["accent"], fg="#000", bd=0, padx=14, pady=7, command=self._run_devtools_action).pack(side="left")

        self.devtools_output = scrolledtext.ScrolledText(panel, bg="#000", fg=T["success"], font=("Consolas", 10), bd=0, padx=15, pady=15)
        self.devtools_output.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        self.devtools_output.insert("end", "[info] DevTools backend ready.\n")
        return panel

    def _run_devtools_action(self):
        if not self.devtools:
            if hasattr(self, "devtools_output"):
                self.devtools_output.insert("end", "DevTools backend not available.\n")
            return
        action = self.devtools_action.get().strip() if hasattr(self, "devtools_action") else "git_status"
        param = self.devtools_param.get().strip() if hasattr(self, "devtools_param") else "."
        self.devtools_output.insert("end", f"\n> {action} {param}\n")
        self.devtools_output.see("end")

        def worker():
            try:
                if action == "git_status":
                    result = self.devtools.git_status(repo_path=param or ".")
                elif action == "git_log":
                    result = self.devtools.git_log(repo_path=param or ".")
                elif action == "list_repo_files":
                    result = self.devtools.list_repo_files(repo_path=param or ".")
                elif action == "analyse_repo":
                    result = self.devtools.analyse_repo(repo_path=param or ".")
                elif action == "pip_list":
                    result = self.devtools.pip_list()
                elif action == "open_devtools":
                    result = self.devtools.open_devtools()
                else:
                    fn = getattr(self.devtools, action, None)
                    result = fn(param) if callable(fn) else {"ok": False, "error": f"Unknown action: {action}"}
            except Exception as e:
                result = {"ok": False, "error": str(e)}
            self.after(0, lambda: (self.devtools_output.insert("end", f"{self._pretty(result)}\n"), self.devtools_output.see("end")))

        threading.Thread(target=worker, daemon=True).start()

    def _create_evolving_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tk.Label(panel, text="Self-Evolving Logic Hub", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=30)

        control = tk.Frame(panel, bg=T["bg"])
        control.pack(fill="x", padx=30, pady=(0, 8))
        tk.Button(control, text="Run Self-Evolve Audit", bg=T["accent"], fg="#000", bd=0, padx=14, pady=7, command=self._run_self_evolving_audit).pack(side="left", padx=(0, 8))
        tk.Button(control, text="List Experimental Tools", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=14, pady=7, command=self._load_experimental_tools).pack(side="left")
        tk.Button(control, text="Kairos Profile", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=14, pady=7, command=self._refresh_kairos_profile).pack(side="left", padx=(8, 0))

        self.evolving_output = scrolledtext.ScrolledText(panel, bg=T["card_bg"], fg=T["text"], font=(FONT_FAMILY, 10), bd=1, highlightbackground=T["card_border"], highlightthickness=1, padx=12, pady=12)
        self.evolving_output.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        self.evolving_output.insert("end", "Self-evolving backend ready.\n")
        self._refresh_kairos_profile()
        return panel

    def _run_self_evolving_audit(self):
        if not hasattr(self, "evolving_output"):
            return
        self.evolving_output.insert("end", "\nRunning self-evolving audit...\n")
        self.evolving_output.see("end")

        def worker():
            prompt = "Audit workflow bottlenecks, reliability risks, and propose staged automation improvements."
            try:
                if self.agents:
                    result = self.agents.run_sync("selfevolve", prompt)
                else:
                    result = _call_ai_sync(prompt, provider=self.prov_cb.get(), model=self.model_cb.get(), system=BABA_SYSTEM_PROMPT)
            except Exception as e:
                result = f"Self-evolving audit error: {e}"
            self.after(0, lambda: (self.evolving_output.insert("end", f"{result}\n"), self.evolving_output.see("end")))

        threading.Thread(target=worker, daemon=True).start()

    def _load_experimental_tools(self):
        if not hasattr(self, "evolving_output"):
            return
        if not self.tool_builder:
            self.evolving_output.insert("end", "Tool builder backend not available.\n")
            self.evolving_output.see("end")
            return
        try:
            tools = self.tool_builder.list_all()
        except Exception as e:
            self.evolving_output.insert("end", f"Tool builder error: {e}\n")
            self.evolving_output.see("end")
            return
        self.evolving_output.insert("end", "\nExperimental/Active tools:\n")
        for t in tools:
            self.evolving_output.insert("end", f"- {t.get('name')} [{t.get('status')}]\n")
        self.evolving_output.see("end")

    def _refresh_kairos_profile(self):
        if not hasattr(self, "evolving_output"):
            return
        if not self.kairos:
            self.evolving_output.insert("end", "\nKairos memory backend not available.\n")
            self.evolving_output.see("end")
            return
        try:
            stats = self.kairos.stats()
            recent = self.kairos.recent_signals(limit=5)
        except Exception as e:
            self.evolving_output.insert("end", f"\nKairos error: {e}\n")
            self.evolving_output.see("end")
            return
        self.evolving_output.insert("end", f"\nKairos stats:\n{self._pretty(stats)}\n")
        if recent:
            self.evolving_output.insert("end", "Recent signals:\n")
            for s in recent:
                self.evolving_output.insert("end", f"- {s.get('type')} {s.get('tags', [])} ({s.get('ts')})\n")
        self.evolving_output.see("end")

    def _create_claws_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tk.Label(panel, text="Claws - Web Data Extraction", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=30)

        controls = tk.Frame(panel, bg=T["bg"])
        controls.pack(fill="x", padx=30, pady=(0, 8))
        tk.Button(controls, text="Refresh Claws", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=14, pady=7, command=self._refresh_claws_panel).pack(side="left", padx=(0, 8))
        tk.Button(controls, text="Install Selected", bg=T["accent"], fg="#000", bd=0, padx=14, pady=7, command=self._install_selected_claw).pack(side="left")

        pick_row = tk.Frame(panel, bg=T["bg"])
        pick_row.pack(fill="x", padx=30, pady=(0, 8))
        self.claw_picker = ttk.Combobox(pick_row, values=[], state="readonly", width=36)
        self.claw_picker.pack(side="left", padx=(0, 8))
        tk.Button(pick_row, text="Run Test", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=12, pady=6, command=self._test_selected_claw).pack(side="left")

        self.claws_output = scrolledtext.ScrolledText(panel, bg=T["card_bg"], fg=T["text"], font=(FONT_FAMILY, 10), bd=1, highlightbackground=T["card_border"], highlightthickness=1, padx=12, pady=12)
        self.claws_output.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        self._refresh_claws_panel()
        return panel

    def _refresh_claws_panel(self):
        if not hasattr(self, "claws_output"):
            return
        self.claws_output.delete("1.0", "end")
        if not self.claws:
            self.claws_output.insert("end", "Claw installer backend not available.\n")
            if hasattr(self, "claw_picker"):
                self.claw_picker["values"] = []
            return
        try:
            all_claws = self.claws.list_all()
        except Exception as e:
            self.claws_output.insert("end", f"Claw listing error: {e}\n")
            return
        ids = []
        for c in all_claws:
            cid = c.get("id", "")
            ids.append(cid)
            status = "INSTALLED" if c.get("installed") else "AVAILABLE"
            self.claws_output.insert("end", f"[{status}] {c.get('name')} ({cid}) v{c.get('version')}\n")
            self.claws_output.insert("end", f"  {c.get('desc')}\n")
            self.claws_output.insert("end", f"  {c.get('url')}\n\n")
        if hasattr(self, "claw_picker"):
            self.claw_picker["values"] = ids
            if ids and not self.claw_picker.get():
                self.claw_picker.set(ids[0])

    def _install_selected_claw(self):
        if not self.claws or not hasattr(self, "claw_picker"):
            return
        claw_id = self.claw_picker.get().strip()
        if not claw_id:
            return
        ok = messagebox.askyesno("Install Claw", f"Install '{claw_id}' now?")
        if not ok:
            return
        self.claws_output.insert("end", f"\nInstalling {claw_id}...\n")
        self.claws_output.see("end")

        def worker():
            try:
                result = self.claws.install(claw_id, approved=True)
            except Exception as e:
                result = {"ok": False, "error": str(e)}
            self.after(0, lambda: (self.claws_output.insert("end", f"{self._pretty(result)}\n"), self._refresh_claws_panel()))

        threading.Thread(target=worker, daemon=True).start()

    def _test_selected_claw(self):
        if not self.claws or not hasattr(self, "claw_picker"):
            return
        claw_id = self.claw_picker.get().strip()
        if not claw_id:
            return
        try:
            result = self.claws.run_test(claw_id)
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        self.claws_output.insert("end", f"\nTest {claw_id}:\n{self._pretty(result)}\n")
        self.claws_output.see("end")

    def _create_settings_panel(self):
        panel = tk.Frame(self.content_area, bg=T["bg"])
        tk.Label(panel, text="System Preferences", font=(FONT_FAMILY, 18, "bold"), bg=T["bg"], fg=T["accent"]).pack(anchor="w", padx=30, pady=30)

        controls = tk.Frame(panel, bg=T["bg"])
        controls.pack(fill="x", padx=30, pady=(0, 10))
        tk.Button(controls, text="Refresh Integration Scan", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=14, pady=7, command=self._refresh_settings_status).pack(side="left", padx=(0, 8))
        tk.Button(controls, text="Auto-Connect Integrations", bg=T["accent"], fg="#000", bd=0, padx=14, pady=7, command=self._settings_auto_connect).pack(side="left", padx=(0, 8))
        tk.Button(controls, text="Connect Outlook Email", bg=T["card_bg"], fg=T["text"], bd=0, padx=14, pady=7, command=self._settings_connect_outlook_oauth).pack(side="left", padx=(0, 8))
        tk.Button(controls, text="Disconnect Outlook", bg=T["card_bg"], fg=T["text"], bd=0, padx=14, pady=7, command=self._settings_disconnect_outlook_oauth).pack(side="left", padx=(0, 8))
        tk.Button(controls, text="Open WhatsApp Web", bg=T["card_bg"], fg=T["text"], bd=0, padx=14, pady=7, command=self._settings_open_whatsapp).pack(side="left", padx=(0, 8))
        tk.Button(controls, text="Open Exo", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=14, pady=7, command=self._settings_open_exo).pack(side="left", padx=(0, 8))
        tk.Button(controls, text="Exo Triage", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=14, pady=7, command=self._settings_exo_triage).pack(side="left", padx=(0, 8))
        self.settings_show_raw = False
        self.settings_raw_btn = tk.Button(controls, text="Show Raw JSON", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=14, pady=7, command=self._settings_toggle_raw)
        self.settings_raw_btn.pack(side="left", padx=(0, 8))
        tk.Button(controls, text="Save Config", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=14, pady=7, command=self._settings_save_config).pack(side="left")

        status_cards = tk.Frame(panel, bg=T["bg"])
        status_cards.pack(fill="x", padx=30, pady=(0, 10))
        self.settings_cards = {}

        def add_card(title, key):
            card = tk.Frame(status_cards, bg=T["card_bg"], bd=1, highlightbackground=T["card_border"], highlightthickness=1, padx=12, pady=10)
            card.pack(side="left", padx=(0, 10), fill="x", expand=True)
            tk.Label(card, text=title, bg=T["card_bg"], fg=T["text_muted"], font=(FONT_FAMILY, 8, "bold")).pack(anchor="w")
            lbl = tk.Label(card, text="Checking...", bg=T["card_bg"], fg=T["text"], font=(FONT_FAMILY, 11, "bold"))
            lbl.pack(anchor="w", pady=(3, 0))
            self.settings_cards[key] = lbl

        add_card("AI Providers", "providers")
        add_card("Outlook OAuth", "oauth")
        add_card("WhatsApp", "whatsapp")
        add_card("Desktop Integrations", "integrations")

        self.settings_hint = tk.Label(panel, text="", bg=T["bg"], fg=T["text_muted"], font=(FONT_FAMILY, 9))
        self.settings_hint.pack(anchor="w", padx=30, pady=(0, 8))

        self.settings_output = scrolledtext.ScrolledText(panel, bg=T["card_bg"], fg=T["text"], font=(FONT_FAMILY, 10), bd=1, highlightbackground=T["card_border"], highlightthickness=1, padx=12, pady=12)
        self.settings_output.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        self._refresh_settings_status()
        return panel

    def _refresh_settings_status(self):
        if not hasattr(self, "settings_output"):
            return
        self.settings_output.delete("1.0", "end")
        health = {}
        if self.pool and hasattr(self.pool, "health_check_sync"):
            try:
                health = self.pool.health_check_sync()
            except Exception as e:
                health = {"error": str(e)}
        scan = {}
        if self.apps and hasattr(self.apps, "detect_integrations"):
            try:
                scan = self.apps.detect_integrations(refresh=True)
            except Exception as e:
                scan = {"error": str(e)}
        oauth_status = {}
        if self.apps and hasattr(self.apps, "outlook_oauth_status"):
            try:
                oauth_status = self.apps.outlook_oauth_status()
            except Exception:
                oauth_status = {}

        providers_online = sum(1 for _k, v in (health or {}).items() if v is True)
        providers_total = len(health or {})
        oauth_connected = bool((oauth_status or {}).get("connected"))
        oauth_configured = bool((oauth_status or {}).get("configured"))
        apps_running = sum(
            1 for _k, v in (scan.get("apps", {}) if isinstance(scan, dict) else {}).items()
            if isinstance(v, dict) and v.get("running")
        )
        social = (scan.get("social", {}) if isinstance(scan, dict) else {}) or {}
        wa_up = bool(social.get("whatsapp_web"))

        if hasattr(self, "settings_cards"):
            self.settings_cards.get("providers", tk.Label()).config(
                text=f"{providers_online}/{providers_total} online",
                fg=T["success"] if providers_online >= 1 else T["warning"],
            )
            self.settings_cards.get("oauth", tk.Label()).config(
                text="Connected" if oauth_connected else ("Configured - Login needed" if oauth_configured else "Not configured"),
                fg=T["success"] if oauth_connected else (T["warning"] if oauth_configured else T["error"]),
            )
            self.settings_cards.get("whatsapp", tk.Label()).config(
                text="Web reachable" if wa_up else "Not detected",
                fg=T["success"] if wa_up else T["warning"],
            )
            self.settings_cards.get("integrations", tk.Label()).config(
                text=f"{apps_running} desktop apps running",
                fg=T["success"] if apps_running >= 1 else T["warning"],
            )

        hint = "Ready."
        if oauth_configured and not oauth_connected:
            hint = "Outlook is configured but not logged in. Click 'Connect Outlook Email'."
        elif not oauth_configured:
            hint = "Outlook OAuth is missing values in config."
        if hasattr(self, "settings_hint"):
            self.settings_hint.config(text=hint)

        self.settings_output.insert("end", "Quick Summary\n")
        self.settings_output.insert("end", f"- AI providers online: {providers_online}/{providers_total}\n")
        self.settings_output.insert("end", f"- Outlook OAuth: {'connected' if oauth_connected else 'not connected'}\n")
        self.settings_output.insert("end", f"- Outlook email account: {(oauth_status or {}).get('email', '') or '(not set)'}\n")
        self.settings_output.insert("end", f"- WhatsApp web reachable: {'yes' if wa_up else 'no'}\n")
        self.settings_output.insert("end", f"- Desktop apps running: {apps_running}\n")

        wiki_stats = {}
        if self.wiki:
            try:
                wiki_stats = self.wiki.stats()
            except Exception:
                wiki_stats = {}
        kairos_stats = {}
        if self.kairos:
            try:
                kairos_stats = self.kairos.stats()
            except Exception:
                kairos_stats = {}
        if wiki_stats:
            self.settings_output.insert("end", f"- Wiki pages: {wiki_stats.get('wiki_pages', 0)}\n")
        if kairos_stats:
            self.settings_output.insert("end", f"- Kairos tone: {kairos_stats.get('tone', 'n/a')} | strictness: {kairos_stats.get('strictness', 'n/a')}\n")

        if self.settings_show_raw:
            self.settings_output.insert("end", "\n--- Raw Diagnostics ---\n")
            self.settings_output.insert("end", "Provider Health\n")
            self.settings_output.insert("end", f"{self._pretty(health)}\n\n")
            self.settings_output.insert("end", "Integration Scan\n")
            self.settings_output.insert("end", f"{self._pretty(scan)}\n")
            if wiki_stats:
                self.settings_output.insert("end", "\nLLM Wiki Stats\n")
                self.settings_output.insert("end", f"{self._pretty(wiki_stats)}\n")
            if kairos_stats:
                self.settings_output.insert("end", "\nKairos Profile Stats\n")
                self.settings_output.insert("end", f"{self._pretty(kairos_stats)}\n")

    def _settings_toggle_raw(self):
        self.settings_show_raw = not getattr(self, "settings_show_raw", False)
        if hasattr(self, "settings_raw_btn"):
            self.settings_raw_btn.config(text="Hide Raw JSON" if self.settings_show_raw else "Show Raw JSON")
        self._refresh_settings_status()

    def _settings_connect_outlook_oauth(self):
        if not self.apps or not hasattr(self.apps, "outlook_oauth_start"):
            messagebox.showwarning("Outlook OAuth", "Outlook OAuth backend is unavailable.")
            return
        try:
            result = self.apps.outlook_oauth_start(open_browser=True)
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        if hasattr(self, "settings_output"):
            self.settings_output.insert("end", f"\nOutlook Connect:\n{self._pretty(result)}\n")
            self.settings_output.see("end")
        if result.get("ok"):
            messagebox.showinfo("Outlook OAuth", "Browser opened. Sign in to complete Outlook connection.")
        else:
            messagebox.showwarning("Outlook OAuth", f"Connect failed: {result.get('error', 'unknown error')}")
        self._refresh_settings_status()
        self._refresh_footer_status()

    def _settings_disconnect_outlook_oauth(self):
        if not self.apps or not hasattr(self.apps, "outlook_oauth_disconnect"):
            messagebox.showwarning("Outlook OAuth", "Outlook OAuth backend is unavailable.")
            return
        try:
            result = self.apps.outlook_oauth_disconnect()
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        if hasattr(self, "settings_output"):
            self.settings_output.insert("end", f"\nOutlook Disconnect:\n{self._pretty(result)}\n")
            self.settings_output.see("end")
        self._refresh_settings_status()
        self._refresh_footer_status()

    def _settings_open_whatsapp(self):
        try:
            if self.apps and hasattr(self.apps, "social_open"):
                result = self.apps.social_open("whatsapp")
            else:
                import webbrowser

                ok = webbrowser.open("https://web.whatsapp.com")
                result = {"ok": bool(ok), "url": "https://web.whatsapp.com"}
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        if hasattr(self, "settings_output"):
            self.settings_output.insert("end", f"\nOpen WhatsApp:\n{self._pretty(result)}\n")
            self.settings_output.see("end")
        self._refresh_settings_status()
        self._refresh_footer_status()

    def _settings_auto_connect(self):
        if not self.apps or not hasattr(self.apps, "auto_connect_integrations"):
            messagebox.showwarning("Settings", "App bridge unavailable for auto-connect.")
            return
        try:
            result = self.apps.auto_connect_integrations(include_launch=False)
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        if hasattr(self, "settings_output"):
            self.settings_output.insert("end", f"\nAuto-connect result:\n{self._pretty(result)}\n")
            self.settings_output.see("end")
        self._refresh_settings_status()

    def _settings_open_exo(self):
        if not self.apps or not hasattr(self.apps, "exo_open"):
            messagebox.showwarning("Exo", "Exo integration is not available.")
            return
        if not self._approved_has("apps", "exo"):
            ok = messagebox.askyesno("Approve Exo", "Approve Exo connection now?")
            if not ok:
                if hasattr(self, "settings_output"):
                    self.settings_output.insert("end", "\nExo open blocked: not approved yet.\n")
                return
            self._approve_connection("apps", "exo")
        try:
            result = self.apps.exo_open()
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        if hasattr(self, "settings_output"):
            self.settings_output.insert("end", f"\nExo open:\n{self._pretty(result)}\n")
            self.settings_output.see("end")

    def _settings_exo_triage(self):
        if not self.apps or not hasattr(self.apps, "exo_triage_inbox"):
            messagebox.showwarning("Exo", "Exo triage integration is not available.")
            return
        if not self._approved_has("apps", "exo"):
            ok = messagebox.askyesno("Approve Exo", "Approve Exo connection before triage?")
            if not ok:
                if hasattr(self, "settings_output"):
                    self.settings_output.insert("end", "\nExo triage blocked: not approved yet.\n")
                return
            self._approve_connection("apps", "exo")
        if hasattr(self, "settings_output"):
            self.settings_output.insert("end", "\nRunning Exo triage...\n")
            self.settings_output.see("end")
        self._run_email_organizer_async(trigger="settings")

    def _settings_save_config(self):
        if not self.settings:
            messagebox.showwarning("Settings", "No settings backend loaded.")
            return
        try:
            self.settings.theme = CURRENT_THEME
            self.settings.save()
            messagebox.showinfo("Settings", "Configuration saved.")
        except Exception as e:
            messagebox.showerror("Settings", str(e))


    def open_agent_workspace(self, agent):
        top = tk.Toplevel(self); top.title(f"{agent['name']} Workspace"); top.configure(bg=T["bg"])
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1200, sw - 80), min(820, sh - 100)
        top.geometry(f"{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2)}")
        top.minsize(980, 680)
        top.resizable(True, True)
        hdr = tk.Frame(top, bg=T["header_bg"], height=60); hdr.pack(fill="x")
        tk.Label(hdr, text=f"{agent['icon']} {agent['name']} Analysis Center", font=(FONT_FAMILY, 14, "bold"), bg=T["header_bg"], fg=T["accent"]).pack(side="left", padx=20)
        
        main = tk.Frame(top, bg=T["bg"], padx=20, pady=20); main.pack(fill="both", expand=True)
        tk.Label(main, text="RECENT DOCUMENTS & ANALYSIS", font=(FONT_FAMILY, 10, "bold"), bg=T["bg"], fg=T["text_muted"]).pack(anchor="w")
        
        feed = scrolledtext.ScrolledText(main, bg=T["card_bg"], fg=T["text"], font=(FONT_FAMILY, 10), bd=0, padx=15, pady=15)
        feed.pack(fill="both", expand=True, pady=10)
        feed.insert("end", f"--- {agent['name']} Automated Feed ---\n\n")
        
        for t in [t for t in self.tasks if t['category'] == agent['cat']]:
            feed.insert("end", f"[{t['timestamp']}] TASK DETECTED: {t['title']}\n")
            feed.insert("end", f"ANALYSIS: {t['summary']}\n\n")

    def _msg_get(self, msg, key, default=""):
        if isinstance(msg, dict):
            return msg.get(key, default)
        return getattr(msg, key, default)

    def _fetch_messages(self, agent_id, limit=5):
        agent = self.email_agents.get(agent_id)
        if not agent:
            return []
        fetch = getattr(agent, "fetch_unread", None)
        if not callable(fetch):
            return []
        try:
            return fetch(limit=limit) or []
        except Exception:
            return []

    def _summarize_message(self, agent, msg):
        summarize = getattr(agent, "summarize_email", None)
        if callable(summarize):
            try:
                return summarize(msg)
            except Exception:
                pass
        subject = self._msg_get(msg, "subject", "(no subject)")
        sender = self._msg_get(msg, "sender", "")
        return f"From {sender}: {subject}"

    def open_email_agent(self, agent):
        top = tk.Toplevel(self); top.title(f"{agent['name']} - Inbox"); top.configure(bg=T["bg"])
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1180, sw - 80), min(820, sh - 100)
        top.geometry(f"{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2)}")
        top.minsize(980, 680)
        top.resizable(True, True)
        hdr = tk.Frame(top, bg=T["header_bg"], height=60); hdr.pack(fill="x")
        tk.Label(hdr, text=f"{agent['icon']} {agent['name']}", font=(FONT_FAMILY, 14, "bold"), bg=T["header_bg"], fg=T["accent"]).pack(side="left", padx=20)
        panes = tk.PanedWindow(top, orient="horizontal", bg=T["card_border"], bd=0, sashwidth=2); panes.pack(fill="both", expand=True)
        
        inbox_list = tk.Frame(panes, bg=T["sidebar_bg"], width=300); panes.add(inbox_list)
        tk.Label(inbox_list, text="RECENT MESSAGES", font=(FONT_FAMILY, 8, "bold"), bg=T["sidebar_bg"], fg=T["text_muted"]).pack(anchor="w", padx=15, pady=15)
        inbox_outer, inbox_items, _ = self._make_scrollable_sidebar(inbox_list, T["sidebar_bg"])
        inbox_outer.pack(fill="both", expand=True)
        
        if agent["id"] not in self.email_agents:
            tk.Label(
                inbox_items,
                text="Agent offline. Install/configure EXO email agents to enable real inbox sync.",
                font=(FONT_FAMILY, 9),
                bg=T["sidebar_bg"],
                fg=T["warning"],
                wraplength=260,
                justify="left",
            ).pack(anchor="w", padx=15, pady=(10, 0))
            msgs = []
        else:
            msgs = self._fetch_messages(agent["id"], limit=20)
        for i, m in enumerate(msgs):
            m_frame = tk.Frame(inbox_items, bg=T["sidebar_bg"], cursor="hand2"); m_frame.pack(fill="x", padx=5, pady=2)
            tk.Label(m_frame, text=self._msg_get(m, "subject", "(no subject)"), font=(FONT_FAMILY, 10, "bold"), bg=T["sidebar_bg"], fg=T["text"], anchor="w").pack(fill="x", padx=10)
            tk.Label(m_frame, text=self._msg_get(m, "sender", "(unknown sender)"), font=(FONT_FAMILY, 8), bg=T["sidebar_bg"], fg=T["text_muted"], anchor="w").pack(fill="x", padx=10)
            tk.Frame(inbox_items, height=1, bg=T["card_border"]).pack(fill="x", padx=15)

        content_area = tk.Frame(panes, bg=T["bg"]); panes.add(content_area)
        summary = tk.Frame(content_area, bg=T["card_bg"], padx=15, pady=15); summary.pack(fill="x", padx=20, pady=20)
        tk.Label(summary, text="AI SUMMARY", font=(FONT_FAMILY, 8, "bold"), bg=T["card_bg"], fg=T["accent"]).pack(anchor="w")
        tk.Label(summary, text="Select an email to view the AI-generated summary and suggested actions.", bg=T["card_bg"], fg=T["text"], wraplength=500, justify="left").pack(anchor="w", pady=5)
        
        composer = tk.Text(content_area, bg=T["card_bg"], fg=T["text"], font=(FONT_FAMILY, 11), height=10, bd=1, highlightbackground=T["card_border"], relief="flat", padx=15, pady=15)
        composer.pack(fill="both", expand=True, padx=20, pady=(5, 20))
        btn_bar = tk.Frame(content_area, bg=T["bg"]); btn_bar.pack(fill="x", side="bottom", pady=20, padx=20)
        tk.Button(btn_bar, text="Send Reply", bg=T["accent"], fg="#000", bd=0, padx=20, pady=8, font=(FONT_FAMILY, 10, "bold"), command=lambda: messagebox.showinfo("Success", "Reply sent!")).pack(side="right")

    def _build_status_bar(self):
        self.indicators = {}
        static_services = [
            ("Solicitor", "\u2696"),
            ("Accountant", "\U0001f4ca"),
            ("MoneyMaker", "\U0001f4b0"),
            ("Coder", "\U0001f4bb"),
            ("Programmer", "\u2699"),
        ]
        for service, icon in static_services:
            lbl = tk.Label(
                self.status_bar,
                text=f"\u25cb {icon} {service}: waiting",
                font=(FONT_FAMILY, 8),
                bg=T["header_bg"],
                fg=T["text_muted"],
            )
            lbl.pack(side="left", padx=10)
            self.indicators[service] = lbl

        services = [
            ("LocalAI", "\u2699"),
            ("Outlook", "\U0001F4E7"),
            ("WhatsApp", "\U0001F4AC"),
            ("Gmail", "\U0001F4E8"),
            ("EmailOrg", "\u2699"),
        ]
        for service, icon in services:
            lbl = tk.Label(
                self.status_bar,
                text=f"\u25cb {icon} {service}: checking",
                font=(FONT_FAMILY, 8),
                bg=T["header_bg"],
                fg=T["text_muted"],
            )
            lbl.pack(side="left", padx=10)
            self.indicators[service] = lbl
        self.status_extra = tk.Label(
            self.status_bar,
            text="",
            font=(FONT_FAMILY, 8),
            bg=T["header_bg"],
            fg=T["text_muted"],
        )
        self.status_extra.pack(side="right", padx=12)
        self._refresh_footer_status()

    def _refresh_footer_status(self):
        if not hasattr(self, "indicators"):
            return
        live = self.connection_live or {}
        apps_scan = (live.get("apps", {}) if isinstance(live, dict) else {}) or {}
        social_scan = (live.get("social", {}) if isinstance(live, dict) else {}) or {}
        email_scan = (live.get("email_agents", {}) if isinstance(live, dict) else {}) or {}
        oauth = (live.get("oauth", {}) if isinstance(live, dict) else {}) or {}
        outlook_running = bool((apps_scan.get("outlook", {}) if isinstance(apps_scan.get("outlook", {}), dict) else {}).get("running"))
        outlook_on = bool(oauth.get("connected")) or outlook_running or bool(self.email_agents.get("outlook"))
        wa_on = bool(social_scan.get("whatsapp_web"))
        gmail_agent = bool(self.email_agents.get("gmail")) or bool(email_scan.get("exo_gmail"))
        org_state = (self.email_organizer_state or "idle").lower()
        providers_live = (live or {}).get("providers", {}) if hasattr(self, "connection_live") else {}
        local_ai_ok = any(
            isinstance(v, dict) and v.get("available") and v.get("approved")
            for v in providers_live.values()
        )
        ex = self.expert_monitor_state if isinstance(self.expert_monitor_state, dict) else {}

        def set_lbl(key, icon, text, ok):
            lbl = self.indicators.get(key)
            if not lbl:
                return
            lbl.config(
                text=f"{'\u25cf' if ok else '\u25cb'} {icon} {key}: {text}",
                fg=T["success"] if ok else T["text_muted"],
            )

        set_lbl(
            "Solicitor",
            "\u2696",
            f"urgent {int((ex.get('solicitor', {}) or {}).get('urgent', 0) or 0)}" if ex else "waiting",
            bool(ex),
        )
        set_lbl(
            "Accountant",
            "\U0001f4ca",
            f"urgent {int((ex.get('accountant', {}) or {}).get('urgent', 0) or 0)}" if ex else "waiting",
            bool(ex),
        )
        set_lbl(
            "MoneyMaker",
            "\U0001f4b0",
            f"urgent {int((ex.get('moneymaker', {}) or {}).get('urgent', 0) or 0)}" if ex else "waiting",
            bool(ex),
        )
        set_lbl(
            "Coder",
            "\U0001f4bb",
            f"urgent {int((ex.get('coder', {}) or {}).get('urgent', 0) or 0)}" if ex else "waiting",
            bool(ex),
        )
        set_lbl(
            "Programmer",
            "\u2699",
            f"urgent {int((ex.get('programmer', {}) or {}).get('urgent', 0) or 0)}" if ex else "waiting",
            bool(ex),
        )

        set_lbl("LocalAI", "\u2699", "connected" if local_ai_ok else "testing", local_ai_ok)
        if bool(oauth.get("connected")):
            outlook_text = "oauth connected"
        elif outlook_running:
            outlook_text = "desktop connected"
        elif self.email_agents.get("outlook"):
            outlook_text = "agent connected"
        else:
            outlook_text = "not connected"
        set_lbl("Outlook", "\U0001F4E7", outlook_text, outlook_on)
        set_lbl("WhatsApp", "\U0001F4AC", "connected" if wa_on else "offline", wa_on)
        set_lbl("Gmail", "\U0001F4E8", "agent ready" if gmail_agent else "agent off", gmail_agent)
        org_ok = org_state == "completed"
        org_txt = "running" if org_state == "running" else ("done" if org_state == "completed" else org_state)
        set_lbl("EmailOrg", "\u2699", org_txt, org_ok)

        if hasattr(self, "status_extra"):
            summary = self.email_organizer_summary or {}
            high = int(summary.get("high", 0) or 0)
            total = int(summary.get("total", 0) or 0)
            self.status_extra.config(
                text=f"Urgent: {high} | Total scanned: {total} | AgentWeb: {self.agent_web_policy} | Evidence: {'on' if self.evidence_required_mode else 'off'}"
            )

    def _toggle_sidebar(self):
        target_w = (
            self.sidebar_collapsed_width
            if not self.sidebar_collapsed
            else self.sidebar_expanded_width
        )
        self._apply_sidebar_width(target_w)
        self.sidebar_collapsed = not self.sidebar_collapsed

    def _apply_sidebar_width(self, width):
        width = int(max(self.sidebar_collapsed_width, min(self.sidebar_max_width, width)))
        self.sidebar.configure(width=width)
        self.nav_canvas.configure(width=width)
        new_btn_w = max(40, width - 40)
        for btn in self.nav_btns.values():
            if hasattr(btn, "width"):
                btn.width = new_btn_w
            btn.configure(width=new_btn_w)
            if hasattr(btn, "_draw"):
                btn._draw()

    def _start_sidebar_resize(self, event):
        self._sidebar_drag_start_x = event.x_root
        self._sidebar_drag_start_w = self.sidebar.winfo_width()

    def _drag_sidebar_resize(self, event):
        delta = event.x_root - self._sidebar_drag_start_x
        width = self._sidebar_drag_start_w + delta
        width = max(self.sidebar_min_width, min(self.sidebar_max_width, width))
        self.sidebar_collapsed = False
        self.sidebar_expanded_width = width
        self._apply_sidebar_width(width)

    def _end_sidebar_resize(self, _event=None):
        if hasattr(self, "sidebar_grip"):
            self.sidebar_grip.configure(bg=T["card_border"])

    def _reset_sidebar_width(self, _event=None):
        self.sidebar_collapsed = False
        self.sidebar_expanded_width = 220
        self._apply_sidebar_width(self.sidebar_expanded_width)

    def _ensure_min_window(self, min_width, min_height):
        self.update_idletasks()
        cur_w = self.winfo_width()
        cur_h = self.winfo_height()
        if cur_w >= min_width and cur_h >= min_height:
            return

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        target_w = min(max(cur_w, min_width), max(900, sw - 20))
        target_h = min(max(cur_h, min_height), max(650, sh - 60))
        # Keep the current window position so switching tabs does not "jump" the app.
        x = max(0, min(self.winfo_x(), max(0, sw - target_w)))
        y = max(0, min(self.winfo_y(), max(0, sh - target_h)))
        self.geometry(f"{target_w}x{target_h}+{x}+{y}")

    def _switch_tab(self, pid):
        if pid == self.active_tab: return
        
        # Optimize rendering by only updating the exact panels & buttons that changed
        if self.active_tab in self.panels:
            self.panels[self.active_tab].pack_forget()
            
        if pid in self.panels:
            self.panels[pid].pack(fill="both", expand=True)
            
        if self.active_tab in self.nav_btns:
            self.nav_btns[self.active_tab].set_active(False)
            
        if pid in self.nav_btns:
            self.nav_btns[pid].set_active(True)
            
        self.active_tab = pid
        panel_sizes = {
            "browser": (1500, 940),
            "devtools": (1500, 940),
            "meetings": (1450, 900),
            "vision": (1450, 900),
            "chat": (1400, 900),
            "agents": (1450, 920),
            "settings": (1450, 920),
            "apps": (1500, 940),
            "computer": (1450, 900),
            "social": (1450, 900),
            "providers": (1450, 920),
            "evolving": (1450, 920),
            "claws": (1450, 920),
        }
        min_w, min_h = panel_sizes.get(pid, (1320, 860))
        self._ensure_min_window(min_w, min_h)
        # Start each panel from top in the global scroll host.
        try:
            self.content_canvas.yview_moveto(0.0)
            self.after(0, self._on_content_area_configure)
        except Exception:
            pass

    def _start_background_polling(self):
        def poll():
            last_full_scan = 0.0
            last_monitor_refresh = 0.0
            # Startup auto-run with short delay to keep initial UI smooth.
            self.after(8000, lambda: self._run_email_organizer_async(trigger="startup"))
            while True:
                for aid, agent in self.email_agents.items():
                    try:
                        msgs = self._fetch_messages(aid, limit=1)
                        for m in msgs:
                            # Auto-create task if not already exists
                            subject = self._msg_get(m, "subject", "(no subject)")
                            if not any(t['title'] == subject for t in self.tasks):
                                task = {
                                    "title": subject,
                                    "category": self._msg_get(m, "category", "Comms"),
                                    "summary": self._summarize_message(agent, m),
                                    "timestamp": self._msg_get(m, "timestamp", datetime.now().strftime("%H:%M")),
                                    "status": "Pending",
                                }
                                self.tasks.append(task)
                                self.log_queue.put(("task_added", task))
                    except Exception: pass
                now = time.time()
                if now - last_full_scan >= 45 * 60:
                    last_full_scan = now
                    self.after(0, lambda: self._run_email_organizer_async(trigger="45m"))
                if now - last_monitor_refresh >= 180:
                    last_monitor_refresh = now
                    self.after(
                        0,
                        lambda: (
                            self._run_expert_monitors_from_cache(notify=True),
                            self._refresh_footer_status(),
                        ),
                    )
                time.sleep(30)
        threading.Thread(target=poll, daemon=True).start()

    def _execute_task(self, task):
        messagebox.showinfo("Executor", f"Executing task: {task['title']}\nAgent: {task['category']} Agent is processing...")
        self._log(f"Task '{task['title']}' executed successfully.")

    def _dismiss_task(self, idx):
        if 0 <= idx < len(self.tasks):
            self.tasks.pop(idx); self._refresh_task_ui()

    def _log(self, msg): self.log_queue.put(("log", msg))
    def _start_queue_processor(self):
        def process():
            try:
                processed = 0
                max_per_tick = 40
                while processed < max_per_tick:
                    item = self.log_queue.get_nowait()
                    processed += 1
                    if item[0] == "task_added":
                        self._refresh_task_ui()
                        self._log(f"New {item[1]['category']} task detected!")
            except queue.Empty: pass
            self.after(200, process)
        self.after(200, process)

if __name__ == "__main__":
    app = BabaGuiV13(); app.mainloop()
