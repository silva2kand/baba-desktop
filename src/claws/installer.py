"""
src/claws/installer.py
Claw Installer - manages specialist runtime installations.
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, UTC
from typing import List, Dict, Any, Optional


CLAWS_REGISTRY = {
    "coclaw": {
        "name": "CoClaw",
        "version": "1.2.0",
        "desc": "Co-pilot claw - dual-agent reasoning. Pairs with Baba for parallel analysis.",
        "install": ["pip install coclaw --upgrade", "python -m coclaw.setup"],
        "test": "python -c \"import coclaw; print('CoClaw', coclaw.__version__)\"",
        "url": "https://pypi.org/project/coclaw",
    },
    "nemoclaw": {
        "name": "NemoClaw",
        "version": "0.9.1",
        "desc": "Adversarial tester - red-teams your agent outputs for accuracy and safety.",
        "install": ["pip install nemoclaw", "python -m nemoclaw init"],
        "test": "python -c \"import nemoclaw; print('NemoClaw OK')\"",
        "url": "https://pypi.org/project/nemoclaw",
    },
    "autoclaw": {
        "name": "AutoClaw",
        "version": "2.0.3",
        "desc": "Automation claw - wraps PyAutoGUI for safe, logged PC control pipelines.",
        "install": [
            "pip install autoclaw pyautogui pillow",
            "python -m autoclaw setup --safe-mode",
        ],
        "test": "python -c \"import autoclaw; print('AutoClaw OK')\"",
        "url": "https://pypi.org/project/autoclaw",
    },
    "openclaw": {
        "name": "OpenClaw",
        "version": "0.5.0",
        "desc": "Open-source claw runtime - community plugins, skills, and tool packs.",
        "install": [
            "git clone https://github.com/babaclaw/openclaw /tmp/openclaw",
            "pip install -e /tmp/openclaw",
        ],
        "test": "python -c \"import openclaw; print('OpenClaw OK')\"",
        "url": "https://github.com/babaclaw/openclaw",
    },
    "visionclaw": {
        "name": "VisionClaw",
        "version": "1.0.0",
        "desc": "Vision pipeline manager - configures and routes Qwen2.5-VL for multimodal tasks.",
        "install": [
            "pip install visionclaw qwen-vl-utils Pillow",
            "python -m visionclaw connect --model qwen2.5-vl",
        ],
        "test": "python -c \"import visionclaw; print('VisionClaw OK')\"",
        "url": "https://pypi.org/project/visionclaw",
    },
    "memoryclaw": {
        "name": "MemoryClaw",
        "version": "0.7.2",
        "desc": "Persistent long-term memory across sessions using ChromaDB vector store.",
        "install": [
            "pip install memoryclaw chromadb",
            "python -m memoryclaw init --db ./data/brain_memory",
        ],
        "test": "python -c \"import memoryclaw; print('MemoryClaw OK')\"",
        "url": "https://pypi.org/project/memoryclaw",
    },
}


class ClawInstaller:
    """Manages claw runtime installation with approval gates and logging."""

    def __init__(self, install_dir: str = "src/claws/installed"):
        self.install_dir = Path(install_dir)
        self.install_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.install_dir / "installed.json"
        self.log_file = Path("logs") / "claw_installs.jsonl"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._state: Dict = self._load_state()

    def list_all(self) -> List[Dict]:
        result = []
        for claw_id, info in CLAWS_REGISTRY.items():
            installed = claw_id in self._state.get("installed", {})
            result.append(
                {
                    "id": claw_id,
                    "name": info["name"],
                    "version": info["version"],
                    "desc": info["desc"],
                    "url": info["url"],
                    "installed": installed,
                    "install_commands": info["install"],
                    "installed_at": self._state.get("installed", {})
                    .get(claw_id, {})
                    .get("ts"),
                }
            )
        return result

    def installed(self) -> List[str]:
        return list(self._state.get("installed", {}).keys())

    def install(self, claw_id: str, approved: bool = False) -> Dict[str, Any]:
        if not approved:
            info = CLAWS_REGISTRY.get(claw_id)
            if not info:
                return {"ok": False, "error": f"Unknown claw: {claw_id}"}
            return {
                "ok": False,
                "requires_approval": True,
                "claw_id": claw_id,
                "commands": info["install"],
                "message": f"Approve installation of {info['name']} v{info['version']}",
            }

        info = CLAWS_REGISTRY.get(claw_id)
        if not info:
            return {"ok": False, "error": f"Unknown claw: {claw_id}"}

        log_lines = []
        success = True

        for cmd in info["install"]:
            log_lines.append(f"$ {cmd}")
            try:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=120
                )
                log_lines.append(result.stdout.strip() or "(no output)")
                if result.returncode != 0:
                    log_lines.append(f"WARNING: exit code {result.returncode}")
                    log_lines.append(result.stderr.strip())
            except subprocess.TimeoutExpired:
                log_lines.append("TIMEOUT after 120s")
                success = False
                break
            except Exception as e:
                log_lines.append(f"ERROR: {e}")
                success = False
                break

        if success:
            test_cmd = info.get("test")
            if test_cmd:
                try:
                    r = subprocess.run(
                        test_cmd, shell=True, capture_output=True, text=True, timeout=30
                    )
                    log_lines.append(f"\nTest: {r.stdout.strip() or 'OK'}")
                    success = r.returncode == 0
                except Exception:
                    log_lines.append("Test skipped (optional)")

        if success:
            self._mark_installed(claw_id, info)

        self._log_install(claw_id, success, log_lines)

        return {
            "ok": success,
            "claw": info["name"],
            "log": "\n".join(log_lines),
            "message": f"{'Successfully installed' if success else 'Install failed'}: {info['name']} v{info['version']}",
        }

    def uninstall(self, claw_id: str, approved: bool = False) -> Dict:
        if not approved:
            return {"ok": False, "requires_approval": True, "claw_id": claw_id}
        state = self._state.setdefault("installed", {})
        if claw_id in state:
            del state[claw_id]
            self._save_state()
        return {"ok": True, "message": f"Unregistered {claw_id}"}

    def run_test(self, claw_id: str) -> Dict:
        info = CLAWS_REGISTRY.get(claw_id)
        if not info:
            return {"ok": False, "error": "Unknown claw"}
        try:
            r = subprocess.run(
                info["test"], shell=True, capture_output=True, text=True, timeout=30
            )
            return {
                "ok": r.returncode == 0,
                "output": r.stdout.strip() or r.stderr.strip(),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _load_state(self) -> Dict:
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {"installed": {}}

    def _save_state(self):
        with open(self.state_file, "w") as f:
            json.dump(self._state, f, indent=2)

    def _mark_installed(self, claw_id: str, info: Dict):
        self._state.setdefault("installed", {})[claw_id] = {
            "name": info["name"],
            "version": info["version"],
            "ts": datetime.now(UTC).isoformat(),
        }
        self._save_state()

    def _log_install(self, claw_id: str, success: bool, log_lines: List[str]):
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "claw_id": claw_id,
            "success": success,
            "log": "\n".join(log_lines),
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
