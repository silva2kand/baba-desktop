"""
src/tools_experimental/builder.py
Self-Tool Builder - proposes, writes, tests, and promotes new Python tools.
"""

import ast
import json
import subprocess
import sys
import re
from pathlib import Path
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional


EXPERIMENTAL_DIR = Path("src/tools_experimental")
ACTIVE_DIR = Path("src/tools")
TOOL_LOG = Path("logs/tool_builder.jsonl")


class ToolBuilder:
    """Builds and manages experimental tools using the LLM."""

    def __init__(self, pool):
        self.pool = pool
        EXPERIMENTAL_DIR.mkdir(parents=True, exist_ok=True)
        TOOL_LOG.parent.mkdir(parents=True, exist_ok=True)

    async def propose(self, brain_index) -> List[Dict]:
        stats = brain_index.stats()
        existing = [f.stem for f in EXPERIMENTAL_DIR.glob("*.py")] + [
            f.stem for f in ACTIVE_DIR.glob("*.py")
        ]
        proposals = [
            {
                "name": "invoice_chaser",
                "desc": "Auto-generate invoice chaser emails from Brain Index overdue data",
                "priority": "high",
            },
            {
                "name": "renewal_alerter",
                "desc": "Monitor Brain Index for upcoming renewals and generate alerts",
                "priority": "high",
            },
            {
                "name": "supplier_pricer",
                "desc": "Scrape supplier websites for price changes and compare to indexed data",
                "priority": "medium",
            },
            {
                "name": "deal_monitor",
                "desc": "Monitor auction/property listing feeds for matching deals",
                "priority": "medium",
            },
            {
                "name": "cashflow_report",
                "desc": "Generate weekly cashflow report from bill and invoice data",
                "priority": "high",
            },
        ]
        proposals = [p for p in proposals if p["name"] not in existing]
        return proposals[:5]

    async def build_from_description(
        self, description: str, name: str = None
    ) -> Dict[str, Any]:
        if not name:
            name = description.lower().replace(" ", "_")[:30].strip("_")

        prompt = f"""Write a Python tool module for Baba Desktop Business Brain.

Tool description: {description}

Requirements:
1. Single file with a run(**kwargs) function as the main entry point
2. Include a test() function that verifies the tool works
3. Must be safe - no destructive operations, no network writes without flagging
4. Include docstrings
5. Return structured data (dict or list) when possible
6. Handle errors gracefully - never crash silently

Return ONLY the Python code, no markdown, no explanation."""

        messages = [{"role": "user", "content": prompt}]
        try:
            code = await self.pool.chat(
                "lmstudio", "omnicoder-9b", messages, max_tokens=2000
            )
        except Exception:
            code = await self.pool.chat(
                "groq", "llama-3.3-70b-versatile", messages, max_tokens=2000
            )

        code = re.sub(r"```python\s*", "", code)
        code = re.sub(r"```\s*", "", code)
        code = code.strip()

        return await self.save_draft(name, description, code)

    async def save_draft(
        self, name: str, description: str, code: str
    ) -> Dict[str, Any]:
        path = EXPERIMENTAL_DIR / f"{name}.py"

        try:
            ast.parse(code)
            syntax_ok = True
        except SyntaxError as e:
            syntax_ok = False
            return {"ok": False, "error": f"Syntax error: {e}", "code": code}

        path.write_text(code, encoding="utf-8")
        meta = {
            "name": name,
            "description": description,
            "path": str(path),
            "status": "draft",
            "syntax_ok": syntax_ok,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._log("draft_saved", meta)
        return {"ok": True, **meta}

    def test_tool(self, name: str) -> Dict[str, Any]:
        path = EXPERIMENTAL_DIR / f"{name}.py"
        if not path.exists():
            return {"ok": False, "error": f"Tool not found: {name}"}

        try:
            result = subprocess.run(
                [sys.executable, str(path)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(Path.cwd()),
            )
            ok = result.returncode == 0
            out = result.stdout.strip()
            err = result.stderr.strip()
            self._log("test_run", {"name": name, "ok": ok, "output": out, "error": err})
            return {"ok": ok, "output": out, "error": err, "name": name}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Test timed out after 30s"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def promote(self, name: str, approved: bool = False) -> Dict[str, Any]:
        if not approved:
            return {
                "ok": False,
                "requires_approval": True,
                "name": name,
                "message": f"Approve promotion of '{name}' to active tools?",
            }

        src = EXPERIMENTAL_DIR / f"{name}.py"
        dest = ACTIVE_DIR / f"{name}.py"
        if not src.exists():
            return {"ok": False, "error": f"Tool not found: {name}"}

        ACTIVE_DIR.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text())
        self._log("promoted", {"name": name, "from": str(src), "to": str(dest)})
        return {
            "ok": True,
            "name": name,
            "active_path": str(dest),
            "message": f"Tool '{name}' promoted to active tools",
        }

    def delete(self, name: str, approved: bool = False) -> Dict[str, Any]:
        if not approved:
            return {"ok": False, "requires_approval": True, "name": name}
        path = EXPERIMENTAL_DIR / f"{name}.py"
        if path.exists():
            path.unlink()
        self._log("deleted", {"name": name})
        return {"ok": True, "message": f"Tool '{name}' deleted"}

    def list_all(self) -> List[Dict]:
        tools = []
        for path in sorted(EXPERIMENTAL_DIR.glob("*.py")):
            if path.name.startswith("_"):
                continue
            code = path.read_text(errors="ignore")
            desc = ""
            m = re.search(r'"""[\s\S]*?Description:\s*(.+)', code)
            if m:
                desc = m.group(1).strip()
            tools.append(
                {
                    "name": path.stem,
                    "description": desc,
                    "path": str(path),
                    "status": "experimental",
                    "size": len(code),
                }
            )
        for path in sorted(ACTIVE_DIR.glob("*.py")):
            if path.name.startswith("_") or path.stem in [t["name"] for t in tools]:
                continue
            tools.append(
                {
                    "name": path.stem,
                    "path": str(path),
                    "status": "active",
                    "description": "",
                }
            )
        return tools

    def _log(self, action: str, data: Dict):
        entry = {"ts": datetime.now(UTC).isoformat(), "action": action, **data}
        with open(TOOL_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
