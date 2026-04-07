"""
src/tools/registry.py
Tool Registry - manages active tools available to agents.
"""

import json
import re
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
        self._register_defaults()

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

    def _brain_search(self, query: str) -> List[Dict]:
        if self._brain:
            return self._brain.search(query)
        return []

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
