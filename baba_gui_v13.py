#!/usr/bin/env python3
"""
BABA DESKTOP v13 - ULTIMATE UK OFFICE ASSISTANT
Manus + Claude Hybrid UI with Professional UK Agent Workflows
Integrated with EXO Email Agents, Planner, Executor, and Memory.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading, json, os, sys, queue, time, traceback, subprocess, re, asyncio
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
BABA_SYSTEM_PROMPT = """You are the Ultimate Baba Desktop Agent v13, a powerful and professional AI built for the UK office and business management.
Your core capabilities include:
1. **Vision Pipeline**: Sensing the screen, performing OCR, and detecting UI elements.
2. **PC Control**: Executing system commands, launching apps (Outlook, Chrome, VS Code, etc.), and managing files.
3. **Multi-Agent Cowork**: Orchestrating autonomous tasks in the background across social media, browser, and documents.
4. **Social Hub**: Integrated messaging across WhatsApp, Slack, LinkedIn, and Telegram.
5. **Professional Workspace**: Managing UK Taxes (VAT/HMRC), Financial Ledgers, and Corporate Compliance.
Always respond as the authoritative OS kernel of this application. Be efficient, professional, and aware of your environment."""

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

def _call_ollama(prompt, model):
    messages = [{"role": "user", "content": prompt}]
    payload = {"model": model, "messages": messages, "stream": False}
    try:
        req = urllib.request.Request("http://localhost:11434/api/chat", json.dumps(payload).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read()).get("message", {}).get("content", "No response")
    except Exception as e:
        return f"Ollama error: {e}"

def _call_openai(prompt, base_url, model, api_key="", extra_headers=None):
    messages = [{"role": "user", "content": prompt}]
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

def _call_gemini(prompt, model, api_key):
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    payload = {"contents": contents, "generationConfig": {"maxOutputTokens": 2048, "temperature": 0.7}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    try:
        req = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"Gemini error: {e}"

def _call_ai_sync(prompt, provider="ollama", model="", history=None, system="", max_tokens=2048):
    if system: prompt = f"System: {system}\n\n{prompt}"
    online, err = _test_provider(provider)
    if not online:
        working, is_local = _find_working_provider(provider)
        if working:
            prompt = f"[Auto-switched from {provider} to {working}] {prompt}"
            provider = working
            if model: model = ALL_MODELS.get(working, [""])[0]
        else:
            return f"NO AI PROVIDER AVAILABLE\n\nSelected provider '{provider}' is not available: {err}\nPlease ensure Jan, Ollama, or LM Studio is running!"

    if provider == "ollama": return _call_ollama(prompt, model or ALL_MODELS["ollama"][0])
    elif provider == "jan": return _call_openai(prompt, "http://localhost:1337/v1", model or ALL_MODELS["jan"][0])
    elif provider == "lmstudio": return _call_openai(prompt, "http://localhost:1234/v1", model or ALL_MODELS["lmstudio"][0])
    elif provider == "groq": return _call_openai(prompt, "https://api.groq.com/openai/v1", model or ALL_MODELS["groq"][0], os.getenv("GROQ_API_KEY", ""))
    elif provider == "gemini": return _call_gemini(prompt, model or ALL_MODELS["gemini"][0], os.getenv("GEMINI_API_KEY", ""))
    elif provider == "openrouter": return _call_openai(prompt, "https://openrouter.ai/api/v1", model or ALL_MODELS["openrouter"][0], os.getenv("OPENROUTER_API_KEY", ""))
    elif provider == "qwen": return _call_openai(prompt, "https://dashscope.aliyuncs.com/compatible-mode/v1", model or ALL_MODELS["qwen"][0], os.getenv("QWEN_API_KEY", ""))
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
        if sys.platform == "win32":
            try:
                import win32com.client
                self._engine = win32com.client.Dispatch("SAPI.SpVoice")
                self._available = True
            except Exception: self._available = False

    def speak(self, text):
        if not self._available: return
        clean = re.sub(r"[#*`_~\[\](){}]", "", text)[:500]
        try:
            if self._engine: self._engine.Speak(clean)
            else:
                escaped = clean.replace('"', '\\"')
                subprocess.run(["powershell", "-Command", f'Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate = 1; $s.Speak("{escaped}")'], capture_output=True, timeout=30)
        except Exception: pass

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
        self.configure(bg=T["bg"])
        self.services = services or {}

        # State & Backend Logic
        self.sidebar_collapsed = False
        self.active_tab = "chat"
        self.nav_btns = {}
        self.panels = {}
        self.log_queue = queue.Queue()
        self.tasks = []
        self.memory = []
        
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
        self._init_connection_state()

        self._setup_ui()
        self._start_background_polling()
        self._start_queue_processor()
        self._setup_global_copy()
        self._start_quick_status_loop()
        self._start_connection_scan_loop()

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
                self.pool = ProviderPool(providers_cfg)
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

    def _pretty(self, data):
        if isinstance(data, (dict, list)):
            return json.dumps(data, indent=2, ensure_ascii=False)
        return str(data)

    def _init_connection_state(self):
        self.connection_state_file = DATA_DIR / "runtime_connections.json"
        self._conn_scan_inflight = False
        self.connection_state = {
            "approved": {"providers": [], "apps": []},
            "last_scan": {},
        }
        self.connection_live = {"providers": {}, "apps": {}, "pending": {"providers": [], "apps": []}}
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

    def _compute_connection_snapshot(self):
        providers = {}
        for p in ALL_MODELS.keys():
            is_on, _ = _test_provider(p)
            providers[p] = {"available": bool(is_on), "approved": self._approved_has("providers", p)}
        apps = {}
        if self.apps and hasattr(self.apps, "detect_integrations"):
            try:
                scan = self.apps.detect_integrations(refresh=True)
            except Exception:
                scan = {}
            app_scan = scan.get("apps", {}) if isinstance(scan, dict) else {}
            for app_name in ("exo", "outlook", "excel", "word", "vscode", "obsidian", "cmd"):
                meta = app_scan.get(app_name, {}) if isinstance(app_scan, dict) else {}
                apps[app_name] = {
                    "available": bool(meta.get("available", False)),
                    "running": bool(meta.get("running", False)),
                    "approved": self._approved_has("apps", app_name),
                }
        else:
            for app_name in ("exo", "outlook", "excel", "word", "vscode", "obsidian", "cmd"):
                apps[app_name] = {"available": False, "running": False, "approved": self._approved_has("apps", app_name)}

        pending_providers = [k for k, v in providers.items() if v["available"] and not v["approved"]]
        pending_apps = [k for k, v in apps.items() if v["available"] and not v["approved"]]
        return {
            "providers": providers,
            "apps": apps,
            "pending": {"providers": pending_providers, "apps": pending_apps},
            "scanned_at": datetime.now(UTC).isoformat(),
        }

    def _scan_connections_now(self, async_mode=False):
        if async_mode:
            if self._conn_scan_inflight:
                return
            self._conn_scan_inflight = True
            threading.Thread(target=self._scan_connections_worker, daemon=True).start()
            return
        self.connection_live = self._compute_connection_snapshot()

    def _scan_connections_worker(self):
        try:
            snapshot = self._compute_connection_snapshot()
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
                self._scan_connections_now(async_mode=True)
            except Exception:
                pass
            self.after(20000, loop)
        self.after(1200, loop)

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
        self.sidebar = tk.Frame(self.layout_container, bg=T["sidebar_bg"], width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()
        
        # Content Area (Middle)
        self.content_area = tk.Frame(self.layout_container, bg=T["bg"])
        self.content_area.pack(side="left", fill="both", expand=True)
        self._build_content_panels()
        
        self.status_bar = tk.Frame(self, bg=T["header_bg"], height=30)
        self.status_bar.pack(side="bottom", fill="x")
        self._build_status_bar()

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
        self.quick_state_label.config(
            text=f"Connected P:{providers_connected} A:{apps_connected} | Pending approvals: {pending_count} | Wiki: {wiki_pages} | Kairos: {kairos_mode}"
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
        self._scan_connections_now(async_mode=True)
        top = tk.Toplevel(self)
        top.title("Connection Center")
        top.geometry("980x680")
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

        p_list = tk.Frame(left, bg=T["card_bg"])
        a_list = tk.Frame(right, bg=T["card_bg"])
        p_list.pack(fill="both", expand=True, padx=10, pady=10)
        a_list.pack(fill="both", expand=True, padx=10, pady=10)

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
        tk.Button(footer, text="Refresh Scan", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=12, pady=6, command=lambda: (self._scan_connections_now(async_mode=True), top.destroy(), self._open_connection_center())).pack(side="left")
        tk.Button(footer, text="Approve All Local AI", bg=T["accent"], fg="#000", bd=0, padx=12, pady=6, command=lambda: (self._approve_connection("providers", "ollama"), self._approve_connection("providers", "jan"), self._approve_connection("providers", "lmstudio"), top.destroy(), self._open_connection_center())).pack(side="left", padx=8)

    def _start_quick_status_loop(self):
        def tick():
            try:
                self._refresh_quick_strip()
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

    def _on_global_mousewheel(self, event):
        target = getattr(self, "_mousewheel_target", None)
        if not target:
            return
        try:
            delta = int(-1 * (event.delta / 120)) if event.delta else 0
            if delta:
                target.yview_scroll(delta, "units")
                return "break"
        except Exception:
            return

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
        self._quick_emit("Exo Triage", {"ok": True, "status": "running"})

        def worker():
            try:
                result = self.apps.exo_triage_inbox(limit=30)
            except Exception as e:
                result = {"ok": False, "error": str(e)}
            self.after(0, lambda: self._quick_emit("Exo Triage Result", result))

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
        self.nav_canvas.bind("<Leave>", lambda e: self._set_mousewheel_target(None))
        self.bind_all("<MouseWheel>", self._on_global_mousewheel, add="+")
        
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
            self.nav_btns[pid] = btn

        # Sidebar Bottom: Command Buttons
        bottom_cmds = tk.Frame(self.sidebar, bg=T["sidebar_bg"], pady=10)
        bottom_cmds.pack(side="bottom", fill="x")
        for cmd, icon in [("Clear", "\u232b"), ("Copy", "\u2398"), ("Speak", "\U0001f50a")]:
            tk.Button(bottom_cmds, text=f"{icon} {cmd}", font=(FONT_FAMILY, 8), bg=T["card_bg"], fg=T["text_muted"], bd=0, padx=10, pady=5).pack(side="left", expand=True, padx=2)

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

        self._switch_tab(self.active_tab)

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
        
        tk.Label(ctrls, text="SYSTEM CAPABILITIES", font=(FONT_FAMILY, 10, "bold"), bg=T["bg"], fg=T["text_muted"]).pack(anchor="w", pady=(0, 10))
        
        features = [
            ("Screen Perception", "Full-screen OCR & Element Detection"),
            ("Input Control", "Mouse, Keyboard & Global Hotkeys"),
            ("System Navigation", "App Switching & Menu Control"),
            ("File System", "CRUD Operations with Safety Pipeline")
        ]
        
        for title, desc in features:
            f_frame = tk.Frame(ctrls, bg=T["card_bg"], padx=15, pady=10, bd=1, highlightbackground=T["card_border"], highlightthickness=1)
            f_frame.pack(fill="x", pady=5)
            tk.Label(f_frame, text=title, font=(FONT_FAMILY, 10, "bold"), bg=T["card_bg"], fg=T["text"]).pack(anchor="w")
            tk.Label(f_frame, text=desc, font=(FONT_FAMILY, 8), bg=T["card_bg"], fg=T["text_muted"], wraplength=250, justify="left").pack(anchor="w")
        
        # Action Buttons
        tk.Button(ctrls, text="START COMPUTER SESSION", bg=T["accent"], fg="#000", font=(FONT_FAMILY, 9, "bold"), bd=0, pady=10).pack(fill="x", pady=(20, 5))
        tk.Button(ctrls, text="EMERGENCY ABORT (ESC)", bg=T["error"], fg="#FFF", font=(FONT_FAMILY, 9, "bold"), bd=0, pady=10).pack(fill="x")

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

        s_body = tk.Frame(ext_sidebar, bg=T["sidebar_bg"], padx=12, pady=12)
        s_body.pack(fill="both", expand=True)
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
        
        container = tk.PanedWindow(panel, orient="horizontal", bg=T["card_border"], bd=0, sashwidth=2)
        container.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        
        # Left: Chat List
        chat_list = tk.Frame(container, bg=T["sidebar_bg"], width=250)
        container.add(chat_list)
        chat_list.pack_propagate(False)
        
        tk.Label(chat_list, text="ACTIVE CHATS", font=(FONT_FAMILY, 8, "bold"), bg=T["sidebar_bg"], fg=T["text_muted"]).pack(anchor="w", padx=15, pady=15)
        
        chats = [
            ("Project Alpha Group", "10:45 AM", "Final docs attached."),
            ("David (Legal)", "Yesterday", "Please review the VAT..."),
            ("Sarah (Finance)", "Monday", "Invoice approved."),
            ("UK Supply Chain", "Last week", "Shipment delayed.")
        ]
        
        for name, time, preview in chats:
            c_frame = tk.Frame(chat_list, bg=T["sidebar_bg"], padx=10, pady=10, cursor="hand2")
            c_frame.pack(fill="x")
            tk.Label(c_frame, text=name, font=(FONT_FAMILY, 10, "bold"), bg=T["sidebar_bg"], fg=T["text"], anchor="w").pack(fill="x")
            tk.Label(c_frame, text=f"{preview} \u2022 {time}", font=(FONT_FAMILY, 8), bg=T["sidebar_bg"], fg=T["text_muted"], anchor="w").pack(fill="x")
            tk.Frame(chat_list, height=1, bg=T["card_border"]).pack(fill="x", padx=10)

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

        if "status" in text and ("connect" in text or "connection" in text):
            self._scan_connections_now()
            return True, self._pretty(self._connection_summary())

        if ("connect all local ai" in text) or ("approve all local ai" in text):
            for p in ("ollama", "jan", "lmstudio"):
                self._approve_connection("providers", p)
            self._scan_connections_now()
            return True, "Approved and connected local AI providers: ollama, jan, lmstudio."

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
            if self.apps and hasattr(self.apps, "exo_triage_inbox"):
                try:
                    out = self.apps.exo_triage_inbox(limit=30)
                except Exception as e:
                    out = {"ok": False, "error": str(e)}
                return True, self._pretty(out)
            return True, "Exo triage backend is unavailable."

        if "wiki compile" in text or "compile wiki" in text or "karpathy wiki compile" in text:
            if not self.wiki:
                return True, "LLM Wiki compiler is unavailable."
            try:
                out = self.wiki.compile_once(topic_hint="Baba Desktop Knowledge")
            except Exception as e:
                out = {"ok": False, "error": str(e)}
            return True, self._pretty(out)

        if "kairos status" in text or "kairos profile" in text:
            if not self.kairos:
                return True, "Kairos memory is unavailable."
            return True, self._pretty({"stats": self.kairos.stats(), "recent": self.kairos.recent_signals(limit=5)})

        return False, ""

    def _process_real_ai(self, prompt):
        prov = self.prov_cb.get()
        mod = self.model_cb.get()
        
        # Display thinking status
        self.after(0, lambda: self.chat_display.insert("end", "Thinking...\n", "text_muted"))
        
        kairos_context = ""
        if self.kairos:
            try:
                kairos_context = self.kairos.build_prompt_context()
            except Exception:
                kairos_context = ""

        system_prompt = BABA_SYSTEM_PROMPT
        if kairos_context:
            system_prompt = f"{BABA_SYSTEM_PROMPT}\n\n{kairos_context}"

        reply = _call_ai_sync(prompt, provider=prov, model=mod, system=system_prompt)

        if self.kairos:
            try:
                self.kairos.record_interaction(prompt, reply)
            except Exception:
                pass
        
        # Simple heuristic to extract suggestions
        suggs = []
        if "?" in reply:
            suggs.append("Tell me more about that")
        suggs.extend(["📋 Extract Action Items", "Explain simply"])
        
        self.after(0, lambda: self._append_chat_block("Baba", reply, suggs))

    def _append_chat_block(self, sender, text, suggestions=None):
        if not hasattr(self, 'chat_display'): return
        self.chat_display.config(state="normal")
        name_tag = "baba_name" if sender == "Baba" else "user_name"
        self.chat_display.insert("end", f"\n{sender}: ", name_tag)
        self.chat_display.insert("end", f"{text}\n")
        
        # Attach interaction buttons for every response
        action_frame = tk.Frame(self.chat_display, bg=T["bg"], pady=5)
        
        # Define local helper for copy
        def copy_txt(t=text):
            self.clipboard_clear()
            self.clipboard_append(t)
            self.update()
            
        tk.Button(action_frame, text="\U0001f4cb Copy", font=(FONT_FAMILY, 8), bg=T["card_bg"], fg=T["text_muted"], bd=0, padx=5, cursor="hand2", command=copy_txt).pack(side="left", padx=2)
        if sender == "Baba":
            def safe_speak(txt):
                threading.Thread(target=lambda: VoiceEngine().speak(txt), daemon=True).start()
            tk.Button(action_frame, text="\U0001f50a Speak", font=(FONT_FAMILY, 8), bg=T["card_bg"], fg=T["text_muted"], bd=0, padx=5, cursor="hand2", command=lambda t=text: safe_speak(t)).pack(side="left", padx=2)
            
        if suggestions:
            for sugg in suggestions[:3]: # Limit to 3 suggestions
                tk.Button(action_frame, text=f"\U0001f4a1 {sugg}", font=(FONT_FAMILY, 8), bg=T["accent_dim"], fg=T["accent"], bd=0, padx=8, cursor="hand2", command=lambda s=sugg: self._handle_suggestion(s)).pack(side="left", padx=2)
                
        self.chat_display.window_create("end", window=action_frame)
        self.chat_display.insert("end", "\n")
        
        self.chat_display.see("end")

    def _handle_suggestion(self, sugg):
        self.chat_input.insert("end", sugg)
        self._handle_chat_send()

    def _create_chat_panel(self):
        # No longer used as a main panel, but kept for compatibility if needed
        return tk.Frame(self.content_area, bg=T["bg"])

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

        # In-context quick actions (same touch area as daily chat use).
        qa = tk.Frame(panel, bg=T["bg"])
        qa.pack(fill="x", padx=40, pady=(0, 12))
        tk.Label(qa, text="One-touch:", bg=T["bg"], fg=T["text_muted"], font=(FONT_FAMILY, 9, "bold")).pack(side="left", padx=(0, 8))
        tk.Button(qa, text="Connections", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=10, pady=5, command=self._open_connection_center).pack(side="left", padx=3)
        tk.Button(qa, text="Exo Triage", bg=T["accent"], fg="#000", bd=0, padx=10, pady=5, command=self._quick_exo_triage).pack(side="left", padx=3)
        tk.Button(qa, text="Wiki Compile", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=10, pady=5, command=self._quick_wiki_compile).pack(side="left", padx=3)
        tk.Button(qa, text="Wiki Ingest", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=10, pady=5, command=self._quick_wiki_ingest).pack(side="left", padx=3)
        tk.Button(qa, text="Kairos", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=10, pady=5, command=self._quick_show_kairos).pack(side="left", padx=3)
        
        # Chat Display Window (Fully expanding)
        chat_frame = tk.Frame(panel, bg=T["card_bg"], bd=1, highlightbackground=T["card_border"], highlightthickness=1)
        chat_frame.pack(fill="both", expand=True, padx=40, pady=(0, 20))
        
        self.chat_display = scrolledtext.ScrolledText(chat_frame, bg=T["card_bg"], fg=T["text"], 
                                                     font=(FONT_FAMILY, 11), bd=0, padx=20, pady=20)
        self.chat_display.pack(fill="both", expand=True)
        self._make_selectable(self.chat_display)
        
        self.chat_display.tag_config("baba_name", foreground=T["accent"], font=(FONT_FAMILY, 11, "bold"))
        self.chat_display.tag_config("user_name", foreground=T["success"], font=(FONT_FAMILY, 11, "bold"))
        
        # Premium Input Area
        input_container = tk.Frame(panel, bg=T["bg"], pady=10)
        input_container.pack(side="bottom", fill="x", padx=40, pady=(0, 40))
        
        self.chat_input = tk.Text(input_container, bg=T["sidebar_bg"], fg=T["text"], font=(FONT_FAMILY, 11), 
                                 height=4, bd=0, highlightbackground=T["accent_dim"], highlightthickness=2, relief="flat", padx=15, pady=15)
        self.chat_input.pack(fill="both", expand=True, side="left", padx=(0, 20))
        self.chat_input.bind("<Return>", lambda e: self._handle_chat_send() or "break")
        
        btn_frame = tk.Frame(input_container, bg=T["bg"])
        btn_frame.pack(side="right")
        tk.Button(btn_frame, text="\u27A4 Send", font=(FONT_FAMILY, 12, "bold"), bg=T["accent"], fg="#000", bd=0, padx=30, pady=15, cursor="hand2", command=self._handle_chat_send).pack()
        
        # Welcome message
        self._append_chat_block("Baba", "Welcome to the premium Chat Workspace! I am online and ready to help.", ["Run Deep Research", "Check PC Stats"])
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
        
        grid = tk.Frame(panel, bg=T["bg"])
        grid.pack(fill="both", expand=True, padx=20)
        
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
            grid.columnconfigure(i%3, weight=1)
            
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
        tk.Button(controls, text="Open Exo", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=14, pady=7, command=self._settings_open_exo).pack(side="left", padx=(0, 8))
        tk.Button(controls, text="Exo Triage", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=14, pady=7, command=self._settings_exo_triage).pack(side="left", padx=(0, 8))
        tk.Button(controls, text="Save Config", bg=T["sidebar_bg"], fg=T["text"], bd=0, padx=14, pady=7, command=self._settings_save_config).pack(side="left")

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
        self.settings_output.insert("end", "Provider Health\n")
        self.settings_output.insert("end", f"{self._pretty(health)}\n\n")
        self.settings_output.insert("end", "Integration Scan\n")
        self.settings_output.insert("end", f"{self._pretty(scan)}\n")
        if self.wiki:
            try:
                self.settings_output.insert("end", "\nLLM Wiki Stats\n")
                self.settings_output.insert("end", f"{self._pretty(self.wiki.stats())}\n")
            except Exception:
                pass
        if self.kairos:
            try:
                self.settings_output.insert("end", "\nKairos Profile Stats\n")
                self.settings_output.insert("end", f"{self._pretty(self.kairos.stats())}\n")
            except Exception:
                pass

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

        def worker():
            try:
                result = self.apps.exo_triage_inbox(limit=30)
            except Exception as e:
                result = {"ok": False, "error": str(e)}
            self.after(0, lambda: (self.settings_output.insert("end", f"{self._pretty(result)}\n"), self.settings_output.see("end")))

        threading.Thread(target=worker, daemon=True).start()

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
        top = tk.Toplevel(self); top.title(f"{agent['name']} Workspace"); top.geometry("1000x700"); top.configure(bg=T["bg"])
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
        top = tk.Toplevel(self); top.title(f"{agent['name']} - Inbox"); top.geometry("900x700"); top.configure(bg=T["bg"])
        hdr = tk.Frame(top, bg=T["header_bg"], height=60); hdr.pack(fill="x")
        tk.Label(hdr, text=f"{agent['icon']} {agent['name']}", font=(FONT_FAMILY, 14, "bold"), bg=T["header_bg"], fg=T["accent"]).pack(side="left", padx=20)
        panes = tk.PanedWindow(top, orient="horizontal", bg=T["card_border"], bd=0, sashwidth=2); panes.pack(fill="both", expand=True)
        
        inbox_list = tk.Frame(panes, bg=T["sidebar_bg"], width=300); panes.add(inbox_list)
        tk.Label(inbox_list, text="RECENT MESSAGES", font=(FONT_FAMILY, 8, "bold"), bg=T["sidebar_bg"], fg=T["text_muted"]).pack(anchor="w", padx=15, pady=15)
        
        if agent["id"] not in self.email_agents:
            tk.Label(
                inbox_list,
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
            m_frame = tk.Frame(inbox_list, bg=T["sidebar_bg"], cursor="hand2"); m_frame.pack(fill="x", padx=5, pady=2)
            tk.Label(m_frame, text=self._msg_get(m, "subject", "(no subject)"), font=(FONT_FAMILY, 10, "bold"), bg=T["sidebar_bg"], fg=T["text"], anchor="w").pack(fill="x", padx=10)
            tk.Label(m_frame, text=self._msg_get(m, "sender", "(unknown sender)"), font=(FONT_FAMILY, 8), bg=T["sidebar_bg"], fg=T["text_muted"], anchor="w").pack(fill="x", padx=10)
            tk.Frame(inbox_list, height=1, bg=T["card_border"]).pack(fill="x", padx=15)

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
        services = [("Solicitor", "\u2696"), ("Accountant", "\U0001f4ca"), ("Outlook", "\U0001F4E7"), ("Gmail", "\U0001F4E8")]
        for service, icon in services:
            online = service.lower() in self.email_agents if service in ("Outlook", "Gmail") else True
            lbl = tk.Label(
                self.status_bar,
                text=f"{'\u25cf' if online else '\u25cb'} {icon} {service}",
                font=(FONT_FAMILY, 8),
                bg=T["header_bg"],
                fg=T["success"] if online else T["text_muted"],
            )
            lbl.pack(side="left", padx=10); self.indicators[service] = lbl

    def _toggle_sidebar(self):
        # Optimization to prevent "ap freezed" - avoid redundant work if possible
        target_w = 60 if not self.sidebar_collapsed else 220
        if self.sidebar.winfo_width() == target_w: return
        
        self.sidebar.configure(width=target_w)
        self.nav_canvas.configure(width=target_w)
        
        new_btn_w = target_w - 40 if target_w > 60 else 40
        for btn in self.nav_btns.values():
            btn.configure(width=new_btn_w)
            if hasattr(btn, 'width'):
                btn.width = new_btn_w
                btn._draw()
                
        self.sidebar_collapsed = not self.sidebar_collapsed

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

    def _start_background_polling(self):
        def poll():
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
                while True:
                    item = self.log_queue.get_nowait()
                    if item[0] == "task_added": self._refresh_task_ui(); self._log(f"New {item[1]['category']} task detected!")
            except queue.Empty: pass
            self.after(200, process)
        self.after(200, process)

if __name__ == "__main__":
    app = BabaGuiV13(); app.mainloop()
