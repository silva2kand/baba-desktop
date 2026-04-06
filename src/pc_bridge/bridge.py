"""
src/pc_bridge/bridge.py
PC Control Bridge - WebSocket server that executes safe PC actions.
"""

import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime, UTC
from typing import Any, Dict

LOG = logging.getLogger("pc_bridge")


class PCBridge:
    """WebSocket server exposing safe PC control actions to Baba."""

    SAFE_ACTIONS = {
        "click",
        "move",
        "type",
        "hotkey",
        "scroll",
        "screenshot",
        "clipboard_get",
        "clipboard_set",
        "list_windows",
        "focus_window",
        "ocr_screen",
        "run_process",
    }

    def __init__(self, port: int = 8765, safe_mode: bool = True, log_dir: str = "logs"):
        self.port = port
        self.safe_mode = safe_mode
        self.log_path = Path(log_dir) / "pc_actions.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def serve(self):
        try:
            import websockets

            asyncio.run(self._start_ws())
        except ImportError:
            LOG.error("websockets not installed: pip install websockets")
        except Exception as e:
            LOG.error(f"PC Bridge error: {e}")

    async def _start_ws(self):
        import websockets

        LOG.info(f"PC Bridge listening on ws://localhost:{self.port}")
        async with websockets.serve(self._handle, "localhost", self.port):
            await asyncio.Future()

    async def _handle(self, websocket):
        async for raw in websocket:
            try:
                cmd = json.loads(raw)
                result = await self.execute(cmd)
                await websocket.send(json.dumps({"ok": True, "result": result}))
            except Exception as e:
                await websocket.send(json.dumps({"ok": False, "error": str(e)}))

    async def execute(self, cmd: Dict[str, Any]) -> Any:
        action = cmd.get("action")
        if action not in self.SAFE_ACTIONS:
            raise ValueError(f"Action '{action}' not in safe list")

        self._log(cmd)

        import pyautogui

        pyautogui.FAILSAFE = True

        if action == "click":
            x, y = cmd.get("x", 0), cmd.get("y", 0)
            button = cmd.get("button", "left")
            pyautogui.click(x, y, button=button)
            return f"Clicked {button} at ({x},{y})"

        elif action == "move":
            x, y = cmd.get("x", 0), cmd.get("y", 0)
            pyautogui.moveTo(x, y, duration=0.3)
            return f"Moved to ({x},{y})"

        elif action == "type":
            text = cmd.get("text", "")
            interval = cmd.get("interval", 0.02)
            pyautogui.typewrite(text, interval=interval)
            return f"Typed {len(text)} characters"

        elif action == "hotkey":
            keys = cmd.get("keys", [])
            pyautogui.hotkey(*keys)
            return f"Hotkey: {'+'.join(keys)}"

        elif action == "scroll":
            x, y = cmd.get("x", 0), cmd.get("y", 0)
            clicks = cmd.get("clicks", 3)
            pyautogui.scroll(clicks, x=x, y=y)
            return f"Scrolled {clicks} at ({x},{y})"

        elif action == "screenshot":
            region = cmd.get("region")
            img = pyautogui.screenshot(region=region)
            out = cmd.get(
                "save_path",
                f"data/exports/screenshot_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.png",
            )
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            img.save(out)
            return {"path": out, "size": img.size}

        elif action == "clipboard_get":
            import pyperclip

            return pyperclip.paste()

        elif action == "clipboard_set":
            import pyperclip

            text = cmd.get("text", "")
            pyperclip.copy(text)
            return f"Copied {len(text)} chars to clipboard"

        elif action == "list_windows":
            try:
                import pygetwindow as gw

                return [
                    {"title": w.title, "visible": w.visible}
                    for w in gw.getAllWindows()
                    if w.title
                ]
            except ImportError:
                return ["pygetwindow not installed: pip install pygetwindow"]

        elif action == "focus_window":
            try:
                import pygetwindow as gw

                title = cmd.get("title", "")
                wins = gw.getWindowsWithTitle(title)
                if wins:
                    wins[0].activate()
                    return f"Focused: {title}"
                return f"Window not found: {title}"
            except ImportError:
                return "pygetwindow not installed"

        elif action == "ocr_screen":
            import pytesseract
            from PIL import Image

            region = cmd.get("region")
            img = pyautogui.screenshot(region=region)
            text = pytesseract.image_to_string(img)
            return {"text": text.strip()}

        elif action == "run_process":
            import subprocess

            command = cmd.get("command", "")
            if self.safe_mode:
                blocked = ["rm -rf", "format", "del /f", "shutdown", "mkfs"]
                if any(b in command.lower() for b in blocked):
                    raise ValueError(f"Command blocked in safe mode: {command}")
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=30
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }

        raise ValueError(f"Unhandled action: {action}")

    def _log(self, cmd: Dict):
        entry = {"ts": datetime.now(UTC).isoformat(), **cmd}
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")


class PCBridgeClient:
    """Async client that sends commands to the running PCBridge server."""

    def __init__(self, port: int = 8765):
        self.url = f"ws://localhost:{port}"

    async def run(self, action: str, **kwargs) -> Any:
        import websockets

        cmd = {"action": action, **kwargs}
        async with websockets.connect(self.url) as ws:
            await ws.send(json.dumps(cmd))
            raw = await ws.recv()
            result = json.loads(raw)
            if not result.get("ok"):
                raise RuntimeError(result.get("error", "Unknown error"))
            return result.get("result")

    def run_sync(self, action: str, **kwargs) -> Any:
        return asyncio.run(self.run(action, **kwargs))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bridge = PCBridge()
    print(f"Starting PC Bridge on port {bridge.port}...")
    print("Ctrl+C to stop. Move mouse to corner to abort any action (failsafe).")
    bridge.serve()
