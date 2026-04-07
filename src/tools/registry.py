"""
src/tools/registry.py
Tool Registry - manages active tools available to agents.
"""

import json
import re
import importlib.util
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime, UTC, date


class Tool:
    def __init__(self, name: str, description: str, fn: Callable, schema: Dict = None):
        self.name = name
        self.description = description
        self.fn = fn
        self.schema = schema or {}

    def run(self, **kwargs) -> Any:
        return self.fn(**kwargs)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "schema": self.schema,
        }


class ToolRegistry:
    """Registry of active tools available to Baba agents."""

    def __init__(self, brain=None):
        self._tools: Dict[str, Tool] = {}
        self._brain = brain
        self._runtime_dir = Path("data/skills_runtime")
        self._proposal_dir = Path("data/skills_proposals")
        self._registry_file = Path("data/skills_registry.json")
        self._runtime_tool_names = set()
        self._ensure_runtime_layout()
        self._register_defaults()
        self.load_runtime_skills()

    def _ensure_runtime_layout(self):
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        self._proposal_dir.mkdir(parents=True, exist_ok=True)
        self._registry_file.parent.mkdir(parents=True, exist_ok=True)
        if not self._registry_file.exists():
            self._registry_file.write_text(
                json.dumps({"skills": [], "updated_at": ""}, indent=2), encoding="utf-8"
            )

    def _register_defaults(self):
        self.register(
            "web_fetch", "Fetch content from a URL", self._web_fetch, {"url": "string"}
        )
        self.register(
            "web_search",
            "Search the web for current information",
            self._web_search,
            {"query": "string"},
        )
        self.register(
            "read_file",
            "Read contents of a local file",
            self._read_file,
            {"path": "string"},
        )
        self.register(
            "write_file",
            "Write content to a local file (requires approval)",
            self._write_file,
            {"path": "string", "content": "string"},
        )
        self.register(
            "list_dir",
            "List contents of a directory",
            self._list_dir,
            {"path": "string"},
        )
        self.register(
            "search_files",
            "Search files for text pattern",
            self._search_files,
            {"directory": "string", "pattern": "string"},
        )
        self.register(
            "shell_exec",
            "Execute a shell command (requires approval)",
            self._shell_exec,
            {"command": "string"},
        )
        self.register(
            "brain_search",
            "Search the Business Brain Index",
            self._brain_search,
            {"query": "string"},
        )
        self.register(
            "draft_email",
            "Draft an email (does NOT send)",
            self._draft_email,
            {"to": "string", "subject": "string", "body": "string"},
        )
        self.register(
            "draft_letter",
            "Draft a formal letter",
            self._draft_letter,
            {"to": "string", "subject": "string", "body": "string"},
        )
        self.register(
            "current_date", "Get the current date and time", self._current_date, {}
        )

    def register(self, name: str, description: str, fn: Callable, schema: Dict = None):
        self._tools[name] = Tool(name, description, fn, schema)

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def all(self) -> List[Dict]:
        return [t.to_dict() for t in self._tools.values()]

    def run(self, name: str, **kwargs) -> Any:
        tool = self.get(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")
        return tool.run(**kwargs)

    def list_tools(self) -> List[Dict]:
        return self.all()

    def load_runtime_skills(self) -> Dict[str, Any]:
        for name in list(self._runtime_tool_names):
            self._tools.pop(name, None)
        self._runtime_tool_names.clear()

        registry = self._load_runtime_registry_data()
        loaded = []
        failed = []
        for entry in registry.get("skills", []):
            if not isinstance(entry, dict) or not entry.get("enabled", True):
                continue
            try:
                tool_name = self._load_runtime_tool_entry(entry)
                if tool_name:
                    loaded.append(tool_name)
            except Exception as e:
                failed.append(
                    {"name": entry.get("name", "unknown"), "error": str(e)}
                )

        return {"loaded": loaded, "failed": failed, "count": len(loaded)}

    def save_runtime_proposal(
        self,
        name: str,
        reason: str,
        code: str,
        risk_text: str = "",
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        safe_name = self._safe_tool_name(name)
        proposal_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        proposal_path = self._proposal_dir / f"{proposal_id}_{safe_name}.json"
        payload = {
            "id": proposal_id,
            "name": safe_name,
            "reason": (reason or "").strip(),
            "code": (code or "").rstrip(),
            "risk": (risk_text or "").strip(),
            "metadata": metadata or {},
            "created_at": datetime.now(UTC).isoformat(),
        }
        proposal_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"ok": True, "proposal_id": proposal_id, "path": str(proposal_path)}

    def list_runtime_proposals(self) -> List[Dict[str, Any]]:
        proposals = []
        for path in sorted(self._proposal_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["path"] = str(path)
                proposals.append(data)
            except Exception:
                continue
        return proposals

    def approve_runtime_proposal(
        self,
        proposal_id: str,
        approved: bool = False,
        schema: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        match = None
        for path in sorted(self._proposal_dir.glob("*.json")):
            if proposal_id in path.name:
                match = path
                break
        if not match:
            return {"ok": False, "error": f"Proposal not found: {proposal_id}"}

        payload = json.loads(match.read_text(encoding="utf-8"))
        if not approved:
            match.unlink(missing_ok=True)
            return {
                "ok": True,
                "status": "rejected",
                "name": payload.get("name", ""),
            }

        code = (payload.get("code", "") or "").strip()
        if not code:
            return {"ok": False, "error": "Proposal has no code"}

        name = self._safe_tool_name(payload.get("name", "runtime_tool"))
        runtime_file = self._runtime_dir / f"{name}.py"
        runtime_file.write_text(code + "\n", encoding="utf-8")

        self._upsert_runtime_registry_entry(
            {
                "name": name,
                "description": payload.get("reason", "") or f"Runtime tool: {name}",
                "file": runtime_file.name,
                "entrypoint": "run",
                "schema": schema or {},
                "enabled": True,
                "approved_at": datetime.now(UTC).isoformat(),
            }
        )
        match.unlink(missing_ok=True)
        load_res = self.load_runtime_skills()
        return {
            "ok": True,
            "status": "approved",
            "name": name,
            "runtime_file": str(runtime_file),
            "loaded": name in load_res.get("loaded", []),
        }

    def _brain_search(self, query: str) -> List[Dict]:
        if self._brain:
            return self._brain.search(query)
        return []

    def _load_runtime_registry_data(self) -> Dict[str, Any]:
        try:
            data = json.loads(self._registry_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("skills", [])
                return data
        except Exception:
            pass
        return {"skills": [], "updated_at": ""}

    def _save_runtime_registry_data(self, data: Dict[str, Any]):
        data["updated_at"] = datetime.now(UTC).isoformat()
        self._registry_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _upsert_runtime_registry_entry(self, entry: Dict[str, Any]):
        data = self._load_runtime_registry_data()
        skills = [s for s in data.get("skills", []) if isinstance(s, dict)]
        name = self._safe_tool_name(entry.get("name", "runtime_tool"))
        replaced = False
        for i, item in enumerate(skills):
            if self._safe_tool_name(item.get("name", "")) == name:
                skills[i] = entry
                replaced = True
                break
        if not replaced:
            skills.append(entry)
        data["skills"] = skills
        self._save_runtime_registry_data(data)

    def _load_runtime_tool_entry(self, entry: Dict[str, Any]) -> Optional[str]:
        name = self._safe_tool_name(entry.get("name", ""))
        if not name:
            return None

        file_name = entry.get("file") or f"{name}.py"
        path = self._runtime_dir / file_name
        if not path.exists():
            raise FileNotFoundError(f"Runtime tool file missing: {path}")

        module_name = f"baba_runtime_{name}_{int(path.stat().st_mtime)}"
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        if not spec or not spec.loader:
            raise RuntimeError(f"Unable to load module for runtime tool: {name}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        entrypoint = str(entry.get("entrypoint", "run") or "run")
        fn = getattr(module, entrypoint, None)
        if not callable(fn):
            raise AttributeError(
                f"Runtime tool '{name}' missing callable entrypoint '{entrypoint}'"
            )

        description = (
            str(entry.get("description", "")).strip()
            or getattr(module, "TOOL_DESCRIPTION", "")
            or f"Runtime tool: {name}"
        )
        schema = entry.get("schema")
        if not isinstance(schema, dict):
            schema = getattr(module, "TOOL_SCHEMA", {}) or {}

        wrapped_fn = self._make_runtime_wrapper(name, path, fn)
        self.register(name, description, wrapped_fn, schema)
        self._runtime_tool_names.add(name)
        return name

    def _make_runtime_wrapper(self, name: str, path: Path, fn: Callable) -> Callable:
        def _run(**kwargs):
            try:
                return fn(**kwargs)
            except Exception as e:
                return {
                    "ok": False,
                    "tool": name,
                    "error": str(e),
                    "source": str(path),
                }

        return _run

    def _safe_tool_name(self, raw: str) -> str:
        text = (raw or "").strip().lower()
        text = re.sub(r"[^a-z0-9_]+", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        return text[:64] or "runtime_tool"

    def _web_fetch(self, url: str) -> str:
        import urllib.request, re

        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                html = r.read().decode("utf-8", errors="ignore")
            text = re.sub(r"<[^>]+>", " ", html)
            return re.sub(r"\s+", " ", text).strip()[:3000]
        except Exception as e:
            return f"Error fetching {url}: {e}"

    def _web_search(self, query: str) -> str:
        import urllib.request, urllib.parse, re

        q = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={q}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read().decode("utf-8", errors="ignore")
            snippets = re.findall(
                r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL
            )
            titles = re.findall(
                r'class="result__title"[^>]*>.*?<a[^>]*>(.*?)</a>', html, re.DOTALL
            )
            results = []
            for t, s in zip(titles[:5], snippets[:5]):
                t_clean = re.sub(r"<[^>]+>", "", t).strip()
                s_clean = re.sub(r"<[^>]+>", "", s).strip()
                results.append(f"- {t_clean}: {s_clean}")
            return "\n".join(results) if results else "No results found"
        except Exception as e:
            return f"Search error: {e}"

    def _read_file(self, path: str) -> str:
        try:
            return Path(path).read_text(encoding="utf-8", errors="ignore")[:5000]
        except Exception as e:
            return f"Error reading {path}: {e}"

    def _write_file(self, path: str, content: str) -> str:
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(content, encoding="utf-8")
            return f"Written {len(content)} chars to {path}"
        except Exception as e:
            return f"Error writing {path}: {e}"

    def _list_dir(self, path: str) -> str:
        try:
            p = Path(path)
            items = [
                f"{'[D]' if x.is_dir() else '[F]'} {x.name}"
                for x in sorted(p.iterdir())
            ]
            return "\n".join(items[:50])
        except Exception as e:
            return f"Error listing {path}: {e}"

    def _search_files(self, directory: str, pattern: str) -> str:
        results = []
        try:
            for f in Path(directory).rglob("*"):
                if f.is_file():
                    try:
                        text = f.read_text(encoding="utf-8", errors="ignore")
                        if re.search(pattern, text, re.IGNORECASE):
                            results.append(str(f))
                    except Exception:
                        pass
        except Exception as e:
            return f"Error: {e}"
        return "\n".join(results[:20]) if results else "No matches found"

    def _shell_exec(self, command: str) -> str:
        import subprocess

        blocked = ["rm -rf", "format", "del /f /s", "shutdown", "mkfs", "dd if="]
        if any(b in command.lower() for b in blocked):
            return f"BLOCKED: Dangerous command not allowed in safe mode: {command}"
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=30
            )
            out = result.stdout or ""
            err = result.stderr or ""
            return f"Exit code: {result.returncode}\n{out}\n{err}".strip()[:2000]
        except Exception as e:
            return f"Error: {e}"

    def _draft_email(self, to: str, subject: str, body: str) -> str:
        draft = f"TO: {to}\nSUBJECT: {subject}\n\n{body}"
        safe_subject = "".join(
            c if c.isalnum() or c == "_" else "_" for c in subject[:20]
        )
        draft_path = Path("data/exports") / f"draft_email_{safe_subject}.txt"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(draft)
        return f"Draft saved to {draft_path}\n\n{draft}"

    def _draft_letter(self, to: str, subject: str, body: str) -> str:
        safe_subject = "".join(
            c if c.isalnum() or c == "_" else "_" for c in subject[:20]
        )
        letter = f"""[YOUR NAME]
[YOUR ADDRESS]
[DATE: {date.today().strftime("%d %B %Y")}]

{to}

Re: {subject}

{body}

Yours sincerely,

[YOUR SIGNATURE]
"""
        letter_path = Path("data/exports") / f"draft_letter_{safe_subject}.txt"
        letter_path.parent.mkdir(parents=True, exist_ok=True)
        letter_path.write_text(letter)
        return f"Letter draft saved to {letter_path}\n\n{letter}"

    def _current_date(self) -> str:
        return datetime.now(UTC).strftime("%A %d %B %Y, %H:%M")
