#!/usr/bin/env python3
"""Baba Desktop v13 Safe Shell UI.

UI-first shell remap that keeps the existing backend capability surface:
- provider/model switching
- real connection auto-detect via AppBridge
- explicit approve/disconnect flow persisted to disk
- connection actions launch real apps/links where available
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import scrolledtext, ttk

try:
    from src.app_bridge.bridge import AppBridge
except Exception:
    AppBridge = None

try:
    from src.claws.installer import ClawInstaller, CLAWS_REGISTRY
except Exception:
    ClawInstaller = None
    CLAWS_REGISTRY = {}

try:
    from src.tools_experimental.builder import ToolBuilder
except Exception:
    ToolBuilder = None

from baba_gui_v13 import ALL_MODELS, BABA_SYSTEM_PROMPT, _call_ai_sync, _test_provider, probe_provider

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


THEME = {
    "bg": "#F4F2EE",
    "card": "#FFFFFF",
    "line": "#D9D4CB",
    "text": "#2F2B25",
    "muted": "#6F675D",
    "accent": "#D16A2F",
    "accent_soft": "#F4E3D8",
    "success": "#2E8B57",
    "warn": "#B8860B",
    "error": "#B23A48",
    "sidebar": "#EFECE7",
}


@dataclass
class ConnectionItem:
    name: str
    kind: str  # providers | apps
    available: bool
    running: bool
    approved: bool


class _LocalPoolProxy:
    """Async adapter for ToolBuilder that routes chat through current provider/model."""

    def __init__(self, ui: "BabaGuiV13SafeShell"):
        self.ui = ui

    async def chat(self, provider: str, model: str, messages: List[Dict[str, str]], max_tokens: int = 2000) -> str:
        prompt = "\n\n".join(m.get("content", "") for m in messages)
        use_provider = self.ui.provider_var.get().strip().lower() or provider
        use_model = self.ui.model_var.get().strip() or model
        return _call_ai_sync(prompt, provider=use_provider, model=use_model, system=BABA_SYSTEM_PROMPT, max_tokens=max_tokens)


class BabaGuiV13SafeShell(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Baba Desktop v13 - Safe Shell")
        self.geometry("1460x900")
        self.minsize(1200, 760)
        self.configure(bg=THEME["bg"])

        self.apps = None
        if AppBridge is not None:
            try:
                self.apps = AppBridge()
            except Exception:
                self.apps = None

        self.state_file = DATA_DIR / "runtime_connections_safe_shell.json"
        self.approvals_file = DATA_DIR / "runtime_approvals_safe_shell.json"
        self.connection_state: Dict[str, Any] = {
            "approved": {"providers": [], "apps": []},
            "updated_at": "",
        }
        self.pending_approvals: List[Dict[str, Any]] = []
        self.connection_live: Dict[str, Any] = {
            "providers": {},
            "apps": {},
            "pending": {"providers": [], "apps": []},
            "meta": {},
        }
        self._scan_lock = threading.Lock()
        self._ai_jobs: List[Tuple[str, str]] = []
        self.claws = ClawInstaller("src/claws/installed") if ClawInstaller else None
        self.tool_builder = None

        self.provider_var = tk.StringVar(value="jan")
        self.model_var = tk.StringVar(value=ALL_MODELS.get("jan", [""])[0])
        self.mic_enabled = False
        self.wave_phase = 0.0

        self._load_connection_state()
        self._load_approvals_state()
        self._build_ui()
        self._refresh_approvals_list()
        self._bind_global_scroll()
        self._refresh_models_for_provider()
        self._scan_connections_now(async_mode=True)
        self._start_scan_loop()
        self._animate_wave()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        top = tk.Frame(self, bg=THEME["bg"], height=62)
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        top.grid_columnconfigure(1, weight=1)

        tk.Label(
            top,
            text="BABA v13",
            font=("Segoe UI", 16, "bold"),
            bg=THEME["bg"],
            fg=THEME["accent"],
        ).grid(row=0, column=0, padx=(16, 6), pady=10, sticky="w")

        tk.Label(
            top,
            text="Safe Shell (Claude/Manus style GUI)",
            font=("Segoe UI", 10),
            bg=THEME["bg"],
            fg=THEME["muted"],
        ).grid(row=0, column=1, sticky="w")

        tk.Button(
            top,
            text="Refresh Detect",
            bg=THEME["card"],
            fg=THEME["text"],
            bd=1,
            relief="solid",
            command=lambda: self._scan_connections_now(async_mode=True),
        ).grid(row=0, column=2, padx=6)

        tk.Button(
            top,
            text="Approve All Local AI",
            bg=THEME["accent_soft"],
            fg=THEME["accent"],
            bd=0,
            command=self._approve_all_local_ai,
        ).grid(row=0, column=3, padx=(0, 16))

        self.sidebar = tk.Frame(self, bg=THEME["sidebar"], width=300)
        self.sidebar.grid(row=1, column=0, sticky="ns")
        self.sidebar.grid_propagate(False)

        self.main = tk.Frame(self, bg=THEME["bg"])
        self.main.grid(row=1, column=1, sticky="nsew")
        self.main.rowconfigure(1, weight=1)
        self.main.columnconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_chat()
        self._build_connection_hub(parent=self.sidebar)

    def _build_sidebar(self) -> None:
        tk.Label(
            self.sidebar,
            text="Navigation",
            bg=THEME["sidebar"],
            fg=THEME["muted"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=14, pady=(14, 8))

        items = [
            ("💬", "Chat"),
            ("🧠", "Agents"),
            ("🖥", "Computer Use"),
            ("🌐", "Browser"),
            ("📬", "Email"),
            ("⚙", "Settings"),
        ]
        for icon, label in items:
            tk.Button(
                self.sidebar,
                text=f"{icon}  {label}",
                bg=THEME["sidebar"],
                fg=THEME["text"],
                bd=0,
                anchor="w",
                padx=14,
                pady=8,
                activebackground=THEME["card"],
                command=lambda l=label: self._emit_system(f"Opened {l} panel."),
            ).pack(fill="x", pady=1)

        self.sidebar_hint = tk.Label(
            self.sidebar,
            text="Auto detect only.\nClick Approve to connect.",
            justify="left",
            bg=THEME["sidebar"],
            fg=THEME["muted"],
            font=("Segoe UI", 9),
        )
        self.sidebar_hint.pack(anchor="w", padx=14, pady=(16, 4))

        approvals_card = tk.Frame(self.sidebar, bg=THEME["card"], highlightthickness=1, highlightbackground=THEME["line"])
        approvals_card.pack(fill="x", padx=10, pady=(6, 8))
        tk.Label(
            approvals_card,
            text="Approvals",
            bg=THEME["card"],
            fg=THEME["text"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 2))

        self.approvals_count = tk.Label(
            approvals_card,
            text="Pending: 0",
            bg=THEME["card"],
            fg=THEME["muted"],
            font=("Segoe UI", 9),
        )
        self.approvals_count.pack(anchor="w", padx=8, pady=(0, 4))

        self.approvals_list = tk.Listbox(
            approvals_card,
            height=4,
            bg=THEME["card"],
            fg=THEME["text"],
            bd=0,
            highlightthickness=0,
            activestyle="none",
            selectbackground=THEME["accent_soft"],
            selectforeground=THEME["text"],
            font=("Segoe UI", 9),
        )
        self.approvals_list.pack(fill="x", padx=8, pady=(0, 6))

        ap_btns = tk.Frame(approvals_card, bg=THEME["card"])
        ap_btns.pack(fill="x", padx=8, pady=(0, 8))
        tk.Button(
            ap_btns,
            text="Approve",
            bg=THEME["accent_soft"],
            fg=THEME["accent"],
            bd=0,
            command=self._approve_selected_request,
        ).pack(side="left", padx=(0, 4))
        tk.Button(
            ap_btns,
            text="Deny",
            bg=THEME["bg"],
            fg=THEME["muted"],
            bd=0,
            command=self._deny_selected_request,
        ).pack(side="left")

    def _build_main_chat(self) -> None:
        head = tk.Frame(self.main, bg=THEME["bg"])
        head.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        head.grid_columnconfigure(0, weight=1)

        tk.Label(
            head,
            text="Good evening, Silva",
            font=("Segoe UI", 34, "bold"),
            bg=THEME["bg"],
            fg=THEME["text"],
        ).grid(row=0, column=0, sticky="w")

        self.status_line = tk.Label(
            head,
            text="Scanning local AI + desktop apps...",
            font=("Segoe UI", 10),
            bg=THEME["bg"],
            fg=THEME["muted"],
        )
        self.status_line.grid(row=1, column=0, sticky="w", pady=(2, 0))

        chat_wrap = tk.Frame(
            self.main,
            bg=THEME["card"],
            highlightthickness=1,
            highlightbackground=THEME["line"],
        )
        chat_wrap.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 16))
        chat_wrap.rowconfigure(0, weight=1)
        chat_wrap.columnconfigure(0, weight=1)

        self.chat_display = scrolledtext.ScrolledText(
            chat_wrap,
            wrap="word",
            bg=THEME["card"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            bd=0,
            font=("Segoe UI", 11),
            padx=14,
            pady=12,
        )
        self.chat_display.grid(row=0, column=0, sticky="nsew")
        self.chat_display.insert("end", "Baba: Safe Shell is ready. Ask naturally: connect outlook, open whatsapp, status connections.\n\n")
        self.chat_display.configure(state="disabled")

        composer = tk.Frame(self.main, bg=THEME["card"], highlightthickness=1, highlightbackground=THEME["line"])
        composer.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        composer.columnconfigure(1, weight=1)

        tk.Button(
            composer,
            text="＋",
            bg=THEME["card"],
            fg=THEME["muted"],
            bd=0,
            font=("Segoe UI", 16),
            command=lambda: self._emit_system("Attach action coming next step."),
        ).grid(row=0, column=0, padx=(8, 2), pady=8)

        self.chat_input = tk.Text(
            composer,
            height=2,
            wrap="word",
            bg=THEME["card"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            bd=0,
            font=("Segoe UI", 12),
            padx=8,
            pady=8,
        )
        self.chat_input.grid(row=0, column=1, sticky="ew", padx=(2, 6), pady=8)
        self.chat_input.bind("<KeyRelease>", self._auto_expand_input)
        self.chat_input.bind("<Control-Return>", lambda e: (self._send_chat(), "break"))

        bar = tk.Frame(composer, bg=THEME["card"])
        bar.grid(row=0, column=2, padx=(0, 8), pady=8, sticky="ne")

        self.wave = tk.Canvas(bar, width=74, height=24, bg=THEME["card"], bd=0, highlightthickness=0)
        self.wave.pack(side="left", padx=(0, 4))

        self.mic_btn = tk.Button(
            bar,
            text="🎤",
            width=3,
            bg=THEME["card"],
            fg=THEME["text"],
            bd=0,
            command=self._toggle_mic,
        )
        self.mic_btn.pack(side="left", padx=(0, 6))

        self.provider_cb = ttk.Combobox(
            bar,
            state="readonly",
            width=10,
            textvariable=self.provider_var,
            values=list(ALL_MODELS.keys()),
        )
        self.provider_cb.pack(side="left", padx=2)
        self.provider_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_models_for_provider())

        self.model_cb = ttk.Combobox(
            bar,
            state="readonly",
            width=22,
            textvariable=self.model_var,
        )
        self.model_cb.pack(side="left", padx=2)

        tk.Button(
            bar,
            text="Send",
            bg="#2F7CC4",
            fg="#FFFFFF",
            bd=0,
            padx=14,
            pady=7,
            command=self._send_chat,
        ).pack(side="left", padx=(6, 0))

        quick = tk.Frame(self.main, bg=THEME["bg"])
        quick.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 14))
        quick.columnconfigure(0, weight=1)

        tk.Label(
            quick,
            text="Quick App Links",
            font=("Segoe UI", 10, "bold"),
            bg=THEME["bg"],
            fg=THEME["muted"],
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.quick_apps_frame = tk.Frame(quick, bg=THEME["bg"])
        self.quick_apps_frame.grid(row=1, column=0, sticky="w")
        self._render_quick_app_icons()

    def _build_connection_hub(self, parent: tk.Widget) -> None:
        hub_host = tk.Frame(parent, bg=THEME["sidebar"])
        hub_host.pack(fill="both", expand=True, padx=10, pady=(8, 10))

        tk.Label(
            hub_host,
            text="Connection Hub",
            bg=THEME["sidebar"],
            fg=THEME["text"],
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w", padx=12, pady=(12, 2))

        tk.Label(
            hub_host,
            text="Auto detect local apps/AI. Approve once to stay connected.",
            bg=THEME["sidebar"],
            fg=THEME["muted"],
            font=("Segoe UI", 9),
            wraplength=260,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 8))

        self.conn_shell = tk.Frame(hub_host, bg=THEME["card"], highlightthickness=1, highlightbackground=THEME["line"])
        self.conn_shell.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.conn_canvas = tk.Canvas(self.conn_shell, bg=THEME["card"], bd=0, highlightthickness=0)
        self.conn_scroll = tk.Scrollbar(self.conn_shell, orient="vertical", command=self.conn_canvas.yview)
        self.conn_body = tk.Frame(self.conn_canvas, bg=THEME["card"])
        self.conn_body.bind(
            "<Configure>",
            lambda _e: self.conn_canvas.configure(scrollregion=self.conn_canvas.bbox("all")),
        )
        self.conn_canvas.create_window((0, 0), window=self.conn_body, anchor="nw", width=264)
        self.conn_canvas.configure(yscrollcommand=self.conn_scroll.set)

        self.conn_canvas.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=(6, 6))
        self.conn_scroll.pack(side="right", fill="y", pady=(6, 6))
        self.conn_canvas.bind_all("<MouseWheel>", self._hub_mousewheel, add="+")

        foot = tk.Frame(hub_host, bg=THEME["sidebar"])
        foot.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(
            foot,
            text="Refresh",
            bg=THEME["bg"],
            fg=THEME["text"],
            bd=0,
            command=lambda: self._scan_connections_now(async_mode=True),
        ).pack(side="left", padx=2)
        tk.Button(
            foot,
            text="Approve All Apps",
            bg=THEME["accent_soft"],
            fg=THEME["accent"],
            bd=0,
            command=self._approve_all_apps,
        ).pack(side="left", padx=2)

    def _load_connection_state(self) -> None:
        if not self.state_file.exists():
            self._save_connection_state()
            return
        try:
            self.connection_state = json.loads(self.state_file.read_text(encoding="utf-8"))
            self.connection_state.setdefault("approved", {}).setdefault("providers", [])
            self.connection_state.setdefault("approved", {}).setdefault("apps", [])
        except Exception:
            self.connection_state = {"approved": {"providers": [], "apps": []}, "updated_at": ""}
            self._save_connection_state()

    def _load_approvals_state(self) -> None:
        if not self.approvals_file.exists():
            self._save_approvals_state()
            return
        try:
            data = json.loads(self.approvals_file.read_text(encoding="utf-8"))
            self.pending_approvals = list(data.get("pending", []))
        except Exception:
            self.pending_approvals = []
            self._save_approvals_state()

    def _save_approvals_state(self) -> None:
        payload = {
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pending": self.pending_approvals,
        }
        self.approvals_file.parent.mkdir(parents=True, exist_ok=True)
        self.approvals_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _refresh_approvals_list(self) -> None:
        if not hasattr(self, "approvals_list"):
            return
        self.approvals_list.delete(0, "end")
        for req in self.pending_approvals:
            self.approvals_list.insert("end", f"{req.get('id')} | {req.get('title')}")
        self.approvals_count.configure(text=f"Pending: {len(self.pending_approvals)}")

    def _enqueue_approval(self, title: str, action: str, payload: Dict[str, Any], detail: str = "") -> str:
        req_id = str(uuid.uuid4())[:8]
        item = {
            "id": req_id,
            "title": title,
            "action": action,
            "payload": payload,
            "detail": detail,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.pending_approvals.append(item)
        self._save_approvals_state()
        self._refresh_approvals_list()
        if detail:
            self._append_chat("Approval", f"[{req_id}] {title}\n{detail}\nReply: approve {req_id} or deny {req_id}")
        else:
            self._append_chat("Approval", f"[{req_id}] {title}\nReply: approve {req_id} or deny {req_id}")
        return req_id

    def _pop_approval(self, req_id: str) -> Optional[Dict[str, Any]]:
        for i, req in enumerate(self.pending_approvals):
            if req.get("id") == req_id:
                out = self.pending_approvals.pop(i)
                self._save_approvals_state()
                self._refresh_approvals_list()
                return out
        return None

    def _get_selected_approval_id(self) -> Optional[str]:
        if not hasattr(self, "approvals_list"):
            return None
        sel = self.approvals_list.curselection()
        if not sel:
            return None
        row = self.approvals_list.get(sel[0])
        return row.split("|", 1)[0].strip() if "|" in row else None

    def _approve_selected_request(self) -> None:
        req_id = self._get_selected_approval_id()
        if not req_id:
            self._emit_system("Select a pending approval first.")
            return
        self._handle_approval_decision(req_id, approved=True)

    def _deny_selected_request(self) -> None:
        req_id = self._get_selected_approval_id()
        if not req_id:
            self._emit_system("Select a pending approval first.")
            return
        self._handle_approval_decision(req_id, approved=False)

    def _ensure_tool_builder(self) -> Optional[ToolBuilder]:
        if self.tool_builder is not None:
            return self.tool_builder
        if ToolBuilder is None:
            return None
        try:
            self.tool_builder = ToolBuilder(_LocalPoolProxy(self))
            return self.tool_builder
        except Exception:
            return None

    def _handle_approval_decision(self, req_id: str, approved: bool) -> None:
        req = self._pop_approval(req_id)
        if not req:
            self._emit_system(f"Approval request not found: {req_id}")
            return
        if not approved:
            self._append_chat("Approval", f"[{req_id}] Denied: {req.get('title')}")
            return

        self._append_chat("Approval", f"[{req_id}] Approved: {req.get('title')}")
        action = req.get("action")
        payload = req.get("payload", {})

        def worker() -> None:
            try:
                if action == "connect_resource":
                    kind = payload.get("kind", "apps")
                    name = payload.get("name", "")
                    self._approve_connection(kind, name)
                    if payload.get("open_after"):
                        self.after(0, lambda n=name: self._open_target(n))
                    self.after(0, lambda: self._emit_system(f"Connected {name}."))
                elif action == "install_claw":
                    claw_id = payload.get("claw_id", "")
                    if not self.claws:
                        self.after(0, lambda: self._emit_system("Claw installer is not available."))
                        return
                    result = self.claws.install(claw_id, approved=True)
                    self.after(0, lambda r=result: self._append_chat("Claws", r.get("message", "Install completed.")))
                elif action == "build_tool":
                    tool_name = payload.get("tool_name", "custom_tool")
                    description = payload.get("description", "Custom tool")
                    auto_promote = bool(payload.get("auto_promote", True))
                    builder = self._ensure_tool_builder()
                    if not builder:
                        self.after(0, lambda: self._emit_system("Tool builder is unavailable in this run."))
                        return
                    draft = asyncio.run(builder.build_from_description(description, name=tool_name))
                    if not draft.get("ok"):
                        self.after(0, lambda d=draft: self._append_chat("Builder", f"Build failed: {d.get('error', 'unknown error')}"))
                        return
                    test = builder.test_tool(tool_name)
                    summary = f"Built draft tool: {tool_name}. Test: {'ok' if test.get('ok') else 'failed'}"
                    if auto_promote and test.get("ok"):
                        promoted = builder.promote(tool_name, approved=True)
                        summary += f". {promoted.get('message', '')}"
                    self.after(0, lambda s=summary: self._append_chat("Builder", s))
                else:
                    self.after(0, lambda: self._emit_system(f"Unknown approval action: {action}"))
            except Exception as e:
                self.after(0, lambda: self._append_chat("Approval", f"Action failed: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _save_connection_state(self) -> None:
        self.connection_state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.connection_state, indent=2), encoding="utf-8")

    def _approved_has(self, kind: str, name: str) -> bool:
        return name in set(self.connection_state.get("approved", {}).get(kind, []))

    def _approve_connection(self, kind: str, name: str) -> None:
        approved = self.connection_state.setdefault("approved", {}).setdefault(kind, [])
        if name not in approved:
            approved.append(name)
            approved.sort()
            self._save_connection_state()
        self._scan_connections_now(async_mode=True)

    def _disconnect_connection(self, kind: str, name: str) -> None:
        approved = self.connection_state.setdefault("approved", {}).setdefault(kind, [])
        if name in approved:
            approved.remove(name)
            self._save_connection_state()
        self._scan_connections_now(async_mode=True)

    def _refresh_models_for_provider(self) -> None:
        provider = self.provider_var.get().strip().lower()
        values = ALL_MODELS.get(provider, [""])
        live_ok, live_models = probe_provider(provider)
        if live_ok and live_models:
            values = live_models
        self.model_cb["values"] = values
        if values and self.model_var.get() not in values:
            self.model_var.set(values[0])

    def _running_processes(self) -> set:
        names: set = set()
        try:
            if os.name == "nt":
                out = subprocess.run(
                    ["tasklist", "/FO", "CSV", "/NH"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                    timeout=5,
                )
                if out.returncode == 0:
                    for line in out.stdout.splitlines():
                        if not line:
                            continue
                        name = line.split(",", 1)[0].strip().strip('"').lower()
                        if name:
                            names.add(name)
            else:
                out = subprocess.run(["ps", "-A", "-o", "comm="], capture_output=True, text=True, timeout=5)
                if out.returncode == 0:
                    for line in out.stdout.splitlines():
                        names.add(Path(line.strip()).name.lower())
        except Exception:
            pass
        return names

    def _compute_connection_snapshot(self) -> Dict[str, Any]:
        providers: Dict[str, Dict[str, Any]] = {}
        for p in ALL_MODELS.keys():
            is_on, _ = _test_provider(p)
            providers[p] = {
                "available": bool(is_on),
                "running": bool(is_on),
                "approved": self._approved_has("providers", p),
            }

        scan = {}
        if self.apps and hasattr(self.apps, "detect_integrations"):
            try:
                scan = self.apps.detect_integrations(refresh=True)
            except Exception:
                scan = {}

        proc = self._running_processes()
        apps: Dict[str, Dict[str, Any]] = {}

        def row(available: bool, running: bool, key: str) -> Dict[str, Any]:
            return {"available": bool(available), "running": bool(running), "approved": self._approved_has("apps", key)}

        scan_apps = scan.get("apps", {})
        scan_browsers = scan.get("browsers", {})
        scan_social = scan.get("social", {})
        scan_services = scan.get("services", {})

        apps["exo"] = row(scan_apps.get("exo", {}).get("available", False), scan_apps.get("exo", {}).get("running", False), "exo")
        apps["outlook"] = row(scan_apps.get("outlook", {}).get("available", os.name == "nt"), scan_apps.get("outlook", {}).get("running", "outlook.exe" in proc), "outlook")
        apps["gmail"] = row(scan_social.get("gmail_web", True), False, "gmail")
        apps["whatsapp"] = row(scan_social.get("whatsapp_web", True), False, "whatsapp")
        apps["facebook"] = row(scan_social.get("facebook_web", True), False, "facebook")
        apps["telegram"] = row(scan_social.get("telegram_web", True), False, "telegram")
        apps["tiktok"] = row(scan_social.get("tiktok_web", True), False, "tiktok")
        apps["instagram"] = row(scan_social.get("instagram_web", True), False, "instagram")
        apps["x"] = row(True, False, "x")

        apps["edge"] = row(scan_browsers.get("edge", {}).get("available", os.name == "nt"), scan_browsers.get("edge", {}).get("running", "msedge.exe" in proc), "edge")
        apps["chrome"] = row(scan_browsers.get("chrome", {}).get("available", os.name == "nt"), scan_browsers.get("chrome", {}).get("running", "chrome.exe" in proc), "chrome")
        apps["github"] = row(True, False, "github")

        one_drive_dir = os.getenv("OneDrive", "")
        one_drive_run = "onedrive.exe" in proc
        apps["onedrive"] = row(bool(one_drive_dir) or one_drive_run, one_drive_run, "onedrive")
        gdrive_run = "googledrivefs.exe" in proc
        apps["gdrive"] = row(gdrive_run or os.name == "nt", gdrive_run, "gdrive")

        apps["pc_files"] = row(True, True, "pc_files")
        apps["computer_use"] = row(bool(scan_services.get("pc_bridge_8765", os.name == "nt")), bool(scan_services.get("pc_bridge_8765", False)), "computer_use")

        pending_providers = [k for k, v in providers.items() if v["available"] and not v["approved"]]
        pending_apps = [k for k, v in apps.items() if v["available"] and not v["approved"]]

        return {
            "providers": providers,
            "apps": apps,
            "pending": {"providers": pending_providers, "apps": pending_apps},
            "meta": {
                "services": scan_services,
                "email_agents": scan.get("email_agents", {}),
                "last_scan": scan.get("timestamp", ""),
            },
        }

    def _scan_connections_now(self, async_mode: bool = False) -> None:
        if async_mode:
            t = threading.Thread(target=self._scan_worker, daemon=True)
            t.start()
            return
        self.connection_live = self._compute_connection_snapshot()
        self._render_connection_hub()
        self._render_quick_app_icons()
        self._update_status_line()

    def _scan_worker(self) -> None:
        if not self._scan_lock.acquire(blocking=False):
            return
        try:
            snap = self._compute_connection_snapshot()
            self.after(0, lambda: self._apply_snapshot(snap))
        finally:
            self._scan_lock.release()

    def _apply_snapshot(self, snap: Dict[str, Any]) -> None:
        self.connection_live = snap
        self._render_connection_hub()
        self._render_quick_app_icons()
        self._update_status_line()

    def _update_status_line(self) -> None:
        providers = self.connection_live.get("providers", {})
        apps = self.connection_live.get("apps", {})
        p_connected = sum(1 for v in providers.values() if v.get("available") and v.get("approved"))
        a_connected = sum(1 for v in apps.values() if v.get("available") and v.get("approved"))
        pending = len(self.connection_live.get("pending", {}).get("providers", [])) + len(self.connection_live.get("pending", {}).get("apps", []))
        human_approvals = len(self.pending_approvals)
        self.status_line.configure(text=f"Connected providers: {p_connected} | Connected apps: {a_connected} | Pending detects: {pending} | Pending approvals: {human_approvals}")

    def _render_connection_hub(self) -> None:
        for child in self.conn_body.winfo_children():
            child.destroy()

        section_p = tk.Label(self.conn_body, text="AI Providers", bg=THEME["card"], fg=THEME["muted"], font=("Segoe UI", 9, "bold"))
        section_p.pack(anchor="w", padx=8, pady=(4, 4))

        for name, meta in sorted(self.connection_live.get("providers", {}).items()):
            self._render_connection_row(name, "providers", meta)

        section_a = tk.Label(self.conn_body, text="Desktop / Web Apps", bg=THEME["card"], fg=THEME["muted"], font=("Segoe UI", 9, "bold"))
        section_a.pack(anchor="w", padx=8, pady=(12, 4))
        for name, meta in sorted(self.connection_live.get("apps", {}).items()):
            self._render_connection_row(name, "apps", meta)

    def _render_connection_row(self, name: str, kind: str, meta: Dict[str, Any]) -> None:
        row = tk.Frame(self.conn_body, bg=THEME["card"], highlightthickness=1, highlightbackground=THEME["line"])
        row.pack(fill="x", padx=8, pady=4)

        state = "offline"
        color = THEME["muted"]
        if meta.get("available") and meta.get("approved"):
            state = "connected"
            color = THEME["success"]
        elif meta.get("available"):
            state = "available"
            color = THEME["warn"]

        title = tk.Frame(row, bg=THEME["card"])
        title.pack(fill="x", padx=8, pady=(6, 2))
        icon = "🟢" if state == "connected" else ("🟡" if state == "available" else "⚪")
        tk.Label(title, text=f"{icon} {name}", bg=THEME["card"], fg=THEME["text"], font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Label(title, text=state, bg=THEME["card"], fg=color, font=("Segoe UI", 9)).pack(side="right")

        btns = tk.Frame(row, bg=THEME["card"])
        btns.pack(fill="x", padx=8, pady=(0, 6))
        tk.Button(btns, text="Approve", bg=THEME["accent_soft"], fg=THEME["accent"], bd=0, command=lambda: self._approve_connection(kind, name)).pack(side="left", padx=2)
        tk.Button(btns, text="Disconnect", bg=THEME["bg"], fg=THEME["muted"], bd=0, command=lambda: self._disconnect_connection(kind, name)).pack(side="left", padx=2)
        if kind == "apps":
            tk.Button(btns, text="Open", bg=THEME["bg"], fg=THEME["text"], bd=0, command=lambda: self._open_target(name)).pack(side="left", padx=2)

    def _render_quick_app_icons(self) -> None:
        if not hasattr(self, "quick_apps_frame"):
            return
        for child in self.quick_apps_frame.winfo_children():
            child.destroy()

        icon_map = {
            "whatsapp": "🟢",
            "gmail": "📧",
            "outlook": "📬",
            "facebook": "f",
            "telegram": "✈",
            "tiktok": "♪",
            "instagram": "◉",
            "x": "X",
            "chrome": "🌐",
            "edge": "e",
            "github": "⌘",
            "onedrive": "☁",
            "gdrive": "△",
            "pc_files": "📁",
            "computer_use": "🖥",
        }
        order = [
            "whatsapp",
            "gmail",
            "outlook",
            "facebook",
            "telegram",
            "instagram",
            "tiktok",
            "x",
            "chrome",
            "edge",
            "github",
            "onedrive",
            "gdrive",
            "pc_files",
            "computer_use",
        ]

        for i, name in enumerate(order):
            meta = self.connection_live.get("apps", {}).get(name, {})
            available = bool(meta.get("available"))
            approved = bool(meta.get("approved"))
            if available and approved:
                bg = "#E5F4EA"
                fg = THEME["success"]
            elif available:
                bg = "#F8F1DE"
                fg = THEME["warn"]
            else:
                bg = THEME["card"]
                fg = THEME["muted"]

            label = icon_map.get(name, "•")
            btn = tk.Button(
                self.quick_apps_frame,
                text=label,
                font=("Segoe UI", 11, "bold"),
                width=3,
                bg=bg,
                fg=fg,
                bd=1,
                relief="solid",
                highlightthickness=0,
                command=lambda n=name: self._open_target(n),
            )
            btn.grid(row=0, column=i, padx=3, pady=2)
            btn.bind("<Enter>", lambda _e, n=name: self.status_line.configure(text=f"Quick open: {n}"))
            btn.bind("<Leave>", lambda _e: self._update_status_line())

    def _approve_all_local_ai(self) -> None:
        for p in ("ollama", "jan", "lmstudio"):
            self._approve_connection("providers", p)
        self._emit_system("Approved local AI providers: ollama, jan, lmstudio.")

    def _approve_all_apps(self) -> None:
        for name in self.connection_live.get("apps", {}).keys():
            self._approve_connection("apps", name)
        self._emit_system("Approved all detected apps for this safe shell.")

    def _require_approval_or_prompt(self, kind: str, name: str) -> bool:
        if self._approved_has(kind, name):
            return True
        self._enqueue_approval(
            title=f"Approve connection for {name}",
            action="connect_resource",
            payload={"kind": kind, "name": name, "open_after": True},
            detail=f"{name} is available but not approved yet.",
        )
        return False

    def _open_target(self, target: str) -> None:
        t = target.lower().strip()
        if not self._require_approval_or_prompt("apps", t):
            self._emit_system(f"Open blocked: {t} is not approved yet.")
            return

        result: Dict[str, Any] = {"ok": False, "error": "No action"}
        try:
            if t in {"whatsapp", "gmail", "outlook", "facebook", "telegram", "tiktok", "instagram", "x", "exo"} and self.apps:
                result = self.apps.social_open(t)
            elif t == "github" and self.apps:
                result = self.apps.chrome_open("https://github.com")
            elif t == "onedrive" and self.apps:
                result = self.apps.chrome_open("https://onedrive.live.com")
            elif t == "gdrive" and self.apps:
                result = self.apps.chrome_open("https://drive.google.com")
            elif t == "chrome" and self.apps:
                result = self.apps.chrome_open("https://www.google.com")
            elif t == "edge" and self.apps:
                result = self.apps.edge_open("about:blank")
            elif t == "pc_files":
                if os.name == "nt":
                    subprocess.Popen('start "" explorer', shell=True)
                    result = {"ok": True, "message": "Explorer launched"}
                else:
                    result = {"ok": False, "error": "pc_files opener currently Windows only"}
            elif t == "computer_use":
                online = bool(self.connection_live.get("meta", {}).get("services", {}).get("pc_bridge_8765", False))
                if online:
                    result = {"ok": True, "message": "Computer Use bridge is online on port 8765"}
                else:
                    result = {"ok": False, "error": "Computer Use bridge offline. Start app backend to enable."}
            else:
                result = {"ok": False, "error": f"No open action mapped for {t}"}
        except Exception as e:
            result = {"ok": False, "error": str(e)}

        if result.get("ok"):
            msg = result.get("message") or result.get("url") or f"Opened {t}."
            self._emit_system(str(msg))
        else:
            self._emit_system(f"Open failed for {t}: {result.get('error', 'unknown error')}")

    def _tool_exists(self, tool_name: str) -> bool:
        p1 = APP_DIR / "src" / "tools" / f"{tool_name}.py"
        p2 = APP_DIR / "src" / "tools_experimental" / f"{tool_name}.py"
        return p1.exists() or p2.exists()

    def _tool_path(self, tool_name: str) -> Optional[Path]:
        p1 = APP_DIR / "src" / "tools" / f"{tool_name}.py"
        p2 = APP_DIR / "src" / "tools_experimental" / f"{tool_name}.py"
        if p1.exists():
            return p1
        if p2.exists():
            return p2
        return None

    def _run_tool_script(self, tool_name: str, prompt: str = "") -> None:
        path = self._tool_path(tool_name)
        if not path:
            self._emit_system(f"Tool not found: {tool_name}")
            return

        def worker() -> None:
            try:
                cmd = [os.sys.executable, str(path)]
                if prompt:
                    cmd += ["--prompt", prompt]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                out = (r.stdout or "").strip()
                err = (r.stderr or "").strip()
                msg = out[:1200] if out else ("Tool ran successfully." if r.returncode == 0 else f"Tool error: {err[:500]}")
                self.after(0, lambda m=msg: self._append_chat("Tool", f"{tool_name}: {m}"))
            except Exception as e:
                self.after(0, lambda: self._append_chat("Tool", f"{tool_name} failed: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _parse_local_command(self, text: str) -> Tuple[bool, str]:
        low = text.lower().strip()
        if not low:
            return True, ""

        provider_names = list(ALL_MODELS.keys())
        app_names = list(self.connection_live.get("apps", {}).keys())
        pending_ids = [r.get("id", "") for r in self.pending_approvals]

        if low == "approvals" or low == "list approvals":
            if not self.pending_approvals:
                return True, "No pending approvals."
            lines = [f"[{r.get('id')}] {r.get('title')}" for r in self.pending_approvals]
            return True, "Pending approvals:\n" + "\n".join(lines)

        if low in {"help", "capabilities", "what can you do", "what it can do"}:
            return True, (
                "I can do this in the same app window:\n"
                "- Auto-detect local AI/providers and desktop/web apps\n"
                "- Approve/deny connection and tool actions with persistent memory\n"
                "- Open and control approved targets: outlook, gmail, whatsapp, facebook, telegram, tiktok, instagram, x, edge, chrome, github, onedrive, gdrive, pc files\n"
                "- Use provider/model from chat bar for AI responses\n"
                "- Install claws with your approval: install claw <id>\n"
                "- Build missing tools with your approval: build tool <name>\n"
                "- Missing capability flow (example: create video) -> approval request -> approve -> build/deploy -> run\n"
                "- Commands: status connections, connect <name>, disconnect <name>, open <name>, approvals, approve <id>, deny <id>"
            )

        if low.startswith("approve "):
            req_id = low.replace("approve ", "", 1).strip()
            if req_id in pending_ids:
                self._handle_approval_decision(req_id, approved=True)
                return True, f"Approved request {req_id}."
            for t in provider_names + app_names:
                if t in low:
                    kind = "providers" if t in provider_names else "apps"
                    self._approve_connection(kind, t)
                    return True, f"Approved connection for {t}. It will stay connected until you disconnect it."

        if low == "approve" and self.pending_approvals:
            req_id = self.pending_approvals[-1].get("id", "")
            if req_id:
                self._handle_approval_decision(req_id, approved=True)
                return True, f"Approved latest request {req_id}."

        if low.startswith("deny "):
            req_id = low.replace("deny ", "", 1).strip()
            if req_id in pending_ids:
                self._handle_approval_decision(req_id, approved=False)
                return True, f"Denied request {req_id}."

        if low == "deny" and self.pending_approvals:
            req_id = self.pending_approvals[-1].get("id", "")
            if req_id:
                self._handle_approval_decision(req_id, approved=False)
                return True, f"Denied latest request {req_id}."

        if "status" in low and ("connect" in low or "connection" in low):
            p_conn = [k for k, v in self.connection_live.get("providers", {}).items() if v.get("available") and v.get("approved")]
            a_conn = [k for k, v in self.connection_live.get("apps", {}).items() if v.get("available") and v.get("approved")]
            pending_p = self.connection_live.get("pending", {}).get("providers", [])
            pending_a = self.connection_live.get("pending", {}).get("apps", [])
            msg = (
                f"Providers connected: {', '.join(p_conn) if p_conn else 'none'}\n"
                f"Apps connected: {', '.join(a_conn) if a_conn else 'none'}\n"
                f"Pending providers: {', '.join(pending_p) if pending_p else 'none'}\n"
                f"Pending apps: {', '.join(pending_a) if pending_a else 'none'}\n"
                f"Pending approvals: {len(self.pending_approvals)}"
            )
            return True, msg

        if "approve all local ai" in low or "connect all local ai" in low:
            self._approve_all_local_ai()
            return True, "Approved local AI providers and kept them connected."

        if low.startswith("connect "):
            for t in provider_names + app_names:
                if t in low:
                    kind = "providers" if t in provider_names else "apps"
                    self._approve_connection(kind, t)
                    return True, f"Approved connection for {t}. It will stay connected until you disconnect it."

        if low.startswith("disconnect "):
            for t in provider_names + app_names:
                if t in low:
                    kind = "providers" if t in provider_names else "apps"
                    self._disconnect_connection(kind, t)
                    return True, f"Disconnected {t}."

        if low.startswith("open "):
            for t in app_names:
                if t in low:
                    self._open_target(t)
                    return True, f"Opening {t}."

        if low.startswith("use provider "):
            for p in provider_names:
                if p in low:
                    self.provider_var.set(p)
                    self._refresh_models_for_provider()
                    return True, f"Provider switched to {p}."

        if "install claw" in low or "enable claw" in low:
            claw_id = ""
            for cid in CLAWS_REGISTRY.keys():
                if cid in low:
                    claw_id = cid
                    break
            if not claw_id:
                return True, f"Specify claw id: {', '.join(CLAWS_REGISTRY.keys())}" if CLAWS_REGISTRY else "No claws registry available."
            self._enqueue_approval(
                title=f"Install claw: {claw_id}",
                action="install_claw",
                payload={"claw_id": claw_id},
                detail=f"This will run installer commands for {claw_id}.",
            )
            return True, f"Approval requested to install {claw_id}."

        if low.startswith("build tool ") or "build a tool" in low or "create tool" in low:
            raw_name = low.replace("build tool", "").replace("create tool", "").strip()
            tool_name = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in raw_name).strip("_")[:40] or f"tool_{int(time.time())}"
            description = text.strip()
            self._enqueue_approval(
                title=f"Build tool: {tool_name}",
                action="build_tool",
                payload={"tool_name": tool_name, "description": description, "auto_promote": True},
                detail="Will generate, test, and promote tool if test passes.",
            )
            return True, f"Approval requested to build tool '{tool_name}'."

        if any(k in low for k in ("create video", "make video", "generate video")):
            if self._tool_exists("video_creator"):
                self._run_tool_script("video_creator", prompt=text)
                return True, "Running existing video_creator tool."
            self._enqueue_approval(
                title="Build missing tool: video_creator",
                action="build_tool",
                payload={
                    "tool_name": "video_creator",
                    "description": "Create videos from user prompts and local assets, with safe approval checks before export and upload.",
                    "auto_promote": True,
                },
                detail="Video capability is missing. Approve build+deploy of video_creator tool?",
            )
            return True, "Video tool is missing. I requested approval to build and deploy it."

        return False, ""

    def _send_chat(self) -> None:
        text = self.chat_input.get("1.0", "end").strip()
        if not text:
            return

        self.chat_input.delete("1.0", "end")
        self._auto_expand_input()
        self._append_chat("You", text)

        handled, out = self._parse_local_command(text)
        if handled:
            if out:
                self._append_chat("Baba", out)
            return

        provider = self.provider_var.get().strip().lower()
        model = self.model_var.get().strip()
        self._append_chat("Baba", "Thinking...")

        def worker() -> None:
            try:
                reply = _call_ai_sync(text, provider=provider, model=model, system=BABA_SYSTEM_PROMPT)
            except Exception as e:
                reply = f"AI call error: {e}"
            self.after(0, lambda: self._replace_last_baba(reply))

        threading.Thread(target=worker, daemon=True).start()

    def _append_chat(self, who: str, text: str) -> None:
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"{who}: {text}\n\n")
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def _replace_last_baba(self, text: str) -> None:
        self.chat_display.configure(state="normal")
        content = self.chat_display.get("1.0", "end")
        marker = "Baba: Thinking..."
        idx = content.rfind(marker)
        if idx >= 0:
            new_content = content[:idx] + f"Baba: {text}\n\n"
            self.chat_display.delete("1.0", "end")
            self.chat_display.insert("1.0", new_content)
        else:
            self.chat_display.insert("end", f"Baba: {text}\n\n")
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def _emit_system(self, text: str) -> None:
        self._append_chat("System", text)

    def _auto_expand_input(self, _event: Optional[tk.Event] = None) -> None:
        line_count = int(self.chat_input.index("end-1c").split(".")[0])
        line_count = max(2, min(7, line_count))
        self.chat_input.configure(height=line_count)

    def _toggle_mic(self) -> None:
        self.mic_enabled = not self.mic_enabled
        if self.mic_enabled:
            self.mic_btn.configure(bg=THEME["accent_soft"], fg=THEME["accent"])
            self._emit_system("Voice mic armed. (Wave active)")
        else:
            self.mic_btn.configure(bg=THEME["card"], fg=THEME["text"])
            self._emit_system("Voice mic paused.")

    def _animate_wave(self) -> None:
        self.wave.delete("all")
        bars = 8
        w = 74
        h = 24
        gap = 3
        bw = (w - (bars + 1) * gap) / bars
        for i in range(bars):
            x0 = gap + i * (bw + gap)
            base = 4 if self.mic_enabled else 2
            amp = (math.sin(self.wave_phase + i * 0.75) + 1.0) * (6 if self.mic_enabled else 2)
            bar_h = base + amp
            y0 = (h - bar_h) / 2
            y1 = h - y0
            color = THEME["accent"] if self.mic_enabled else THEME["line"]
            self.wave.create_rectangle(x0, y0, x0 + bw, y1, fill=color, width=0)
        self.wave_phase += 0.35
        self.after(120, self._animate_wave)

    def _hub_mousewheel(self, event: tk.Event) -> None:
        if str(event.widget).startswith(str(self.conn_canvas)) or self.sidebar.winfo_containing(event.x_root, event.y_root):
            delta = -1 * int(event.delta / 120) if event.delta else 0
            if delta:
                self.conn_canvas.yview_scroll(delta, "units")

    def _bind_global_scroll(self) -> None:
        def on_mousewheel(event: tk.Event) -> None:
            widget = self.winfo_containing(event.x_root, event.y_root)
            if isinstance(widget, (tk.Text, scrolledtext.ScrolledText)):
                return
            if not widget or widget.winfo_toplevel() != self:
                return
            delta = -1 * int(event.delta / 120) if event.delta else 0
            if not delta:
                return
            if self.sidebar.winfo_containing(event.x_root, event.y_root):
                self.conn_canvas.yview_scroll(delta, "units")
                return
            self.chat_display.yview_scroll(delta, "units")

        self.bind_all("<MouseWheel>", on_mousewheel, add="+")

    def _start_scan_loop(self) -> None:
        def loop() -> None:
            self._scan_connections_now(async_mode=True)
            self.after(8000, loop)

        self.after(1000, loop)


__all__ = ["BabaGuiV13SafeShell"]
