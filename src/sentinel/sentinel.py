"""
src/sentinel/sentinel.py
Opt-in sentinel with:
- global hotkey capture (when supported)
- app allowlist awareness
- folder watcher events
- clipboard hooks
- central task inbox
"""

from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional

from src.sentinel.inbox import SentinelInbox


DEFAULT_STATE = {
    "enabled": True,
    "allow_screenshot_on_capture": False,
    "hotkey": "ctrl+alt+b",
    "run_hotkey_listener": True,
    "run_folder_watchers": True,
    "run_clipboard_watcher": True,
    "clipboard_mode": "passive",  # off | passive | smart
    "folder_poll_seconds": 15,
    "clipboard_poll_seconds": 2,
    "watch_apps": [
        "outlook.exe",
        "chrome.exe",
        "msedge.exe",
        "whatsapp.exe",
        "excel.exe",
        "winword.exe",
    ],
    "watch_folders": [
        "data/imports/emails",
        "data/imports/pdfs",
        "data/imports/bills",
        "data/imports/contracts",
    ],
    "updated_at": "",
}


class Sentinel:
    def __init__(
        self,
        state_path: str = "config/sentinel_state.json",
        pc_bridge=None,
        inbox: Optional[SentinelInbox] = None,
        on_event: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    ):
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.pc_bridge = pc_bridge
        self.on_event = on_event
        self.inbox = inbox or SentinelInbox()
        self._state = self._load()

        self._running = False
        self._stop_event = threading.Event()
        self._threads: List[threading.Thread] = []
        self._folder_seen: Dict[str, float] = {}
        self._last_clipboard = ""
        self._last_event_at = ""
        self._hotkey_backend = ""
        self._hotkey_registered = False
        self._keyboard_mod = None

    def start(self) -> Dict[str, Any]:
        if self._running:
            return {"ok": True, "status": "already_running", **self.status()}
        self._running = True
        self._stop_event.clear()
        self._threads = []

        if self._state.get("run_folder_watchers", True):
            t = threading.Thread(target=self._folder_loop, daemon=True)
            t.start()
            self._threads.append(t)

        if self._state.get("run_clipboard_watcher", True):
            t = threading.Thread(target=self._clipboard_loop, daemon=True)
            t.start()
            self._threads.append(t)

        if self._state.get("run_hotkey_listener", True):
            self._start_hotkey_listener()

        return {"ok": True, "status": "started", **self.status()}

    def stop(self) -> Dict[str, Any]:
        self._running = False
        self._stop_event.set()
        self._stop_hotkey_listener()
        return {"ok": True, "status": "stopped", **self.status()}

    def status(self) -> Dict[str, Any]:
        active = self._active_window()
        return {
            "ok": True,
            "enabled": bool(self._state.get("enabled", True)),
            "running": self._running,
            "allow_screenshot_on_capture": bool(
                self._state.get("allow_screenshot_on_capture", False)
            ),
            "hotkey": self._state.get("hotkey", "ctrl+alt+b"),
            "hotkey_registered": self._hotkey_registered,
            "hotkey_backend": self._hotkey_backend,
            "clipboard_mode": self._state.get("clipboard_mode", "passive"),
            "watch_apps": list(self._state.get("watch_apps", [])),
            "watch_folders": list(self._state.get("watch_folders", [])),
            "active_window": active,
            "active_app_allowed": self._is_active_app_allowed(active),
            "inbox": self.inbox.stats(),
            "last_event_at": self._last_event_at,
            "updated_at": self._state.get("updated_at", ""),
        }

    def set_enabled(self, enabled: bool) -> Dict[str, Any]:
        self._state["enabled"] = bool(enabled)
        self._save()
        return self.status()

    def set_allow_screenshot(self, allow: bool) -> Dict[str, Any]:
        self._state["allow_screenshot_on_capture"] = bool(allow)
        self._save()
        return self.status()

    def set_hotkey(self, hotkey: str) -> Dict[str, Any]:
        text = str(hotkey or "").strip().lower() or "ctrl+alt+b"
        self._state["hotkey"] = text
        self._save()
        if self._running:
            self._stop_hotkey_listener()
            if self._state.get("run_hotkey_listener", True):
                self._start_hotkey_listener()
        return self.status()

    def set_clipboard_mode(self, mode: str) -> Dict[str, Any]:
        text = str(mode or "").strip().lower()
        if text not in {"off", "passive", "smart"}:
            text = "passive"
        self._state["clipboard_mode"] = text
        self._save()
        return self.status()

    def set_watch_apps(self, apps: List[str]) -> Dict[str, Any]:
        cleaned = []
        for app in apps or []:
            text = str(app).strip().lower()
            if text and text not in cleaned:
                cleaned.append(text)
        self._state["watch_apps"] = cleaned
        self._save()
        return self.status()

    def set_watch_folders(self, folders: List[str]) -> Dict[str, Any]:
        cleaned = []
        for folder in folders or []:
            text = str(folder).strip()
            if text and text not in cleaned:
                cleaned.append(text)
        self._state["watch_folders"] = cleaned
        self._save()
        return self.status()

    def capture_context(self, include_screenshot: bool = False) -> Dict[str, Any]:
        if not self._state.get("enabled", True):
            return {"ok": False, "error": "Sentinel disabled"}

        active = self._active_window()
        context = {
            "captured_at": datetime.now(UTC).isoformat(),
            "active_window": active,
            "clipboard": self._clipboard_text(),
            "active_app_allowed": self._is_active_app_allowed(active),
        }

        should_capture_shot = bool(include_screenshot) and bool(
            self._state.get("allow_screenshot_on_capture", False)
        )
        if should_capture_shot and self.pc_bridge:
            try:
                if hasattr(self.pc_bridge, "run_sync"):
                    shot = self.pc_bridge.run_sync("screenshot")
                else:
                    shot = None
                if shot:
                    context["screenshot"] = shot
            except Exception as e:
                context["screenshot_error"] = str(e)

        return {"ok": True, "context": context}

    def trigger_hotkey_capture(self, include_screenshot: bool = False) -> Dict[str, Any]:
        captured = self.capture_context(include_screenshot=include_screenshot)
        if not captured.get("ok"):
            return captured
        event_payload = captured.get("context", {})
        emitted = self._emit_event(
            source="hotkey",
            event_type="hotkey_context",
            payload=event_payload,
            priority="high",
        )
        return {"ok": True, "captured": event_payload, "task": emitted}

    def push_event(
        self,
        source: str,
        event_type: str,
        payload: Dict[str, Any],
        priority: str = "normal",
    ) -> Dict[str, Any]:
        return self._emit_event(source=source, event_type=event_type, payload=payload, priority=priority)

    def list_inbox(self, limit: int = 100, status: str = "") -> List[Dict[str, Any]]:
        return self.inbox.list(limit=limit, status=status)

    def _emit_event(
        self,
        source: str,
        event_type: str,
        payload: Dict[str, Any],
        priority: str = "normal",
    ) -> Dict[str, Any]:
        task = self.inbox.enqueue(
            source=source,
            event_type=event_type,
            payload=payload,
            priority=priority,
        )
        self._last_event_at = datetime.now(UTC).isoformat()

        if self.on_event:
            try:
                result = self.on_event(task) or {}
                self.inbox.update(task["id"], status="queued", result=result)
                task["result"] = result
            except Exception as e:
                self.inbox.update(task["id"], status="error", error=str(e))
                task["error"] = str(e)
        return task

    def _folder_loop(self):
        while not self._stop_event.is_set():
            if not self._state.get("enabled", True):
                time.sleep(1)
                continue
            interval = max(2, int(self._state.get("folder_poll_seconds", 15)))
            folders = self._state.get("watch_folders", []) or []
            for folder in folders:
                p = Path(folder)
                if not p.exists() or not p.is_dir():
                    continue
                try:
                    for f in p.rglob("*"):
                        if not f.is_file():
                            continue
                        key = str(f.resolve())
                        mtime = f.stat().st_mtime
                        prev = self._folder_seen.get(key)
                        if prev is None:
                            self._folder_seen[key] = mtime
                            continue
                        if mtime > prev:
                            self._folder_seen[key] = mtime
                            self._emit_event(
                                source="folder_watcher",
                                event_type="file_event",
                                payload={
                                    "path": key,
                                    "folder": str(p.resolve()),
                                    "modified_at": datetime.fromtimestamp(mtime, tz=UTC).isoformat(),
                                },
                                priority="normal",
                            )
                except Exception:
                    continue
            self._stop_event.wait(interval)

    def _clipboard_loop(self):
        while not self._stop_event.is_set():
            if not self._state.get("enabled", True):
                time.sleep(1)
                continue
            mode = str(self._state.get("clipboard_mode", "passive")).lower()
            interval = max(1, int(self._state.get("clipboard_poll_seconds", 2)))
            if mode == "off":
                self._stop_event.wait(interval)
                continue

            text = self._clipboard_text()
            if text and text != self._last_clipboard:
                self._last_clipboard = text
                if mode == "smart" and self._clipboard_signal(text):
                    active = self._active_window()
                    self._emit_event(
                        source="clipboard_hook",
                        event_type="clipboard_signal",
                        payload={
                            "clipboard": text[:6000],
                            "active_window": active,
                        },
                        priority="normal",
                    )
            self._stop_event.wait(interval)

    def _clipboard_signal(self, text: str) -> bool:
        probe = (text or "").strip().lower()
        if len(probe) < 6:
            return False
        patterns = [
            r"https?://",
            r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b",
            r"\b(inv|invoice|vat|hmrc|payment|amount due)\b",
            r"\b(la[0-9]{1,2}\s?[0-9a-z]{2,4})\b",
        ]
        return any(re.search(p, probe) for p in patterns)

    def _start_hotkey_listener(self):
        hotkey = str(self._state.get("hotkey", "ctrl+alt+b")).strip().lower()
        if not hotkey:
            return
        try:
            import keyboard  # type: ignore

            keyboard.add_hotkey(hotkey, self.trigger_hotkey_capture)
            self._keyboard_mod = keyboard
            self._hotkey_backend = "keyboard"
            self._hotkey_registered = True
        except Exception:
            self._keyboard_mod = None
            self._hotkey_backend = "disabled"
            self._hotkey_registered = False

    def _stop_hotkey_listener(self):
        try:
            if self._keyboard_mod and self._hotkey_registered:
                self._keyboard_mod.clear_all_hotkeys()
        except Exception:
            pass
        self._hotkey_registered = False
        if self._hotkey_backend != "disabled":
            self._hotkey_backend = ""

    def _is_active_app_allowed(self, active: Dict[str, Any]) -> bool:
        exe = str(active.get("process_name", "")).lower()
        watch = [str(x).lower() for x in self._state.get("watch_apps", [])]
        if not exe or not watch:
            return False
        return exe in watch

    def _active_window(self) -> Dict[str, Any]:
        try:
            import pygetwindow as gw

            title = ""
            try:
                active = gw.getActiveWindow()
                if active:
                    title = getattr(active, "title", "") or ""
            except Exception:
                title = ""
        except Exception:
            title = ""

        proc = self._active_process_name()
        return {"title": title, "process_name": proc}

    def _active_process_name(self) -> str:
        try:
            import ctypes
            from ctypes import wintypes
            import psutil

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return ""
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return ""
            return psutil.Process(pid.value).name()
        except Exception:
            return ""

    def _clipboard_text(self) -> str:
        try:
            import pyperclip

            text = pyperclip.paste() or ""
            return str(text)[:6000]
        except Exception:
            return ""

    def _load(self) -> Dict[str, Any]:
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    merged = dict(DEFAULT_STATE)
                    merged.update(data)
                    return merged
            except Exception:
                pass
        return dict(DEFAULT_STATE)

    def _save(self):
        self._state["updated_at"] = datetime.now(UTC).isoformat()
        self.state_path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

