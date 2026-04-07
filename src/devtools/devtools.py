"""
src/devtools/devtools.py
Developer Tools - browser DevTools, Git, VS Code, terminal, code analysis.
"""

import subprocess
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional


class DevTools:
    """Developer-focused tools: git, terminal, VS Code, browser devtools."""

    def open_devtools(self) -> Dict:
        try:
            from src.pc_bridge.bridge import PCBridgeClient

            client = PCBridgeClient()
            result = client.run_sync("hotkey", keys=["F12"])
            return {"ok": True, "message": "DevTools opened (F12)"}
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "manual": "Press F12 in Chrome to open DevTools",
            }

    def read_console_logs(self, url: str = None) -> Dict:
        try:
            import urllib.request

            debug_url = "http://localhost:9222/json"
            with urllib.request.urlopen(debug_url, timeout=3) as r:
                tabs = json.loads(r.read())
            return {"ok": True, "tabs": tabs[:5], "count": len(tabs)}
        except Exception:
            return {
                "ok": False,
                "message": "Start Chrome with --remote-debugging-port=9222",
                "command": "chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug",
            }

    def inspect_element(self, selector: str) -> Dict:
        return {
            "ok": True,
            "message": f"Inspect '{selector}' - use run_cdp_command for full DevTools Protocol access",
            "cdp_command": f'document.querySelector("{selector}").getBoundingClientRect()',
        }

    def run_cdp_command(self, command: str, tab_id: str = None) -> Dict:
        try:
            import urllib.request

            with urllib.request.urlopen("http://localhost:9222/json", timeout=3) as r:
                tabs = json.loads(r.read())
            if not tabs:
                return {"ok": False, "error": "No Chrome tabs found"}
            ws_url = tabs[0].get("webSocketDebuggerUrl", "")
            return {
                "ok": True,
                "ws_url": ws_url,
                "command": command,
                "note": "Connect via websocket to execute CDP commands",
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def git_status(self, repo_path: str = ".") -> Dict:
        return self._run_git(["status", "--short"], repo_path)

    def git_log(self, repo_path: str = ".", limit: int = 10) -> Dict:
        return self._run_git(["log", f"--oneline", f"-{limit}"], repo_path)

    def git_diff(self, repo_path: str = ".", file: str = None) -> Dict:
        args = ["diff"]
        if file:
            args.append(file)
        return self._run_git(args, repo_path)

    def git_add(
        self, paths: List[str], repo_path: str = ".", approved: bool = False
    ) -> Dict:
        if not approved:
            return {"ok": False, "requires_approval": True, "paths": paths}
        return self._run_git(["add"] + paths, repo_path)

    def git_commit(
        self, message: str, repo_path: str = ".", approved: bool = False
    ) -> Dict:
        if not approved:
            return {"ok": False, "requires_approval": True, "message": message}
        return self._run_git(["commit", "-m", message], repo_path)

    def git_push(self, repo_path: str = ".", approved: bool = False) -> Dict:
        if not approved:
            return {
                "ok": False,
                "requires_approval": True,
                "warning": "This will push to remote - requires explicit approval",
            }
        return self._run_git(["push"], repo_path)

    def git_clone(self, url: str, dest: str = ".", approved: bool = False) -> Dict:
        if not approved:
            return {"ok": False, "requires_approval": True, "url": url, "dest": dest}
        return self._run_cmd(["git", "clone", url, dest])

    def git_branch_list(self, repo_path: str = ".") -> Dict:
        return self._run_git(["branch", "-a"], repo_path)

    def git_checkout(
        self, branch: str, repo_path: str = ".", approved: bool = False
    ) -> Dict:
        if not approved:
            return {"ok": False, "requires_approval": True, "branch": branch}
        return self._run_git(["checkout", branch], repo_path)

    def _run_git(self, args: List[str], cwd: str = ".") -> Dict:
        return self._run_cmd(["git"] + args, cwd=cwd)

    def vscode_open_file(self, path: str) -> Dict:
        return self._run_cmd(["code", path])

    def vscode_open_folder(self, path: str = ".") -> Dict:
        return self._run_cmd(["code", path])

    def vscode_install_extension(self, ext_id: str, approved: bool = False) -> Dict:
        if not approved:
            return {"ok": False, "requires_approval": True, "extension": ext_id}
        return self._run_cmd(["code", "--install-extension", ext_id])

    def vscode_list_extensions(self) -> Dict:
        return self._run_cmd(["code", "--list-extensions"])

    def run_command(
        self, command: str, cwd: str = ".", approved: bool = False, timeout: int = 30
    ) -> Dict:
        if not approved:
            return {"ok": False, "requires_approval": True, "command": command}
        blocked = [
            "rm -rf /",
            "format c:",
            "mkfs",
            "dd if=/dev/zero",
            ":(){ :|: & };:",
            "del /f /s /q c:\\",
        ]
        cmd_lower = command.lower()
        if any(b in cmd_lower for b in blocked):
            return {"ok": False, "error": f"BLOCKED: dangerous command - {command}"}
        return self._run_cmd(command, cwd=cwd, shell=True, timeout=timeout)

    def run_python(self, script: str, cwd: str = ".", approved: bool = False) -> Dict:
        if not approved:
            return {"ok": False, "requires_approval": True, "script": script[:100]}
        return self._run_cmd([sys.executable, "-c", script], cwd=cwd)

    def run_python_file(self, path: str, approved: bool = False) -> Dict:
        if not approved:
            return {"ok": False, "requires_approval": True, "path": path}
        return self._run_cmd([sys.executable, path])

    def run_tests(
        self, test_path: str = ".", framework: str = "pytest", approved: bool = False
    ) -> Dict:
        if not approved:
            return {"ok": False, "requires_approval": True, "path": test_path}
        if framework == "pytest":
            return self._run_cmd(["python", "-m", "pytest", test_path, "-v"])
        elif framework == "unittest":
            return self._run_cmd(["python", "-m", "unittest", "discover", test_path])
        return {"ok": False, "error": f"Unknown test framework: {framework}"}

    def pip_install(self, packages: List[str], approved: bool = False) -> Dict:
        if not approved:
            return {"ok": False, "requires_approval": True, "packages": packages}
        return self._run_cmd([sys.executable, "-m", "pip", "install"] + packages)

    def pip_list(self) -> Dict:
        return self._run_cmd([sys.executable, "-m", "pip", "list", "--format=json"])

    def analyse_file(self, path: str) -> Dict:
        try:
            content = Path(path).read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")
            return {
                "ok": True,
                "path": path,
                "lines": len(lines),
                "size_kb": round(len(content) / 1024, 1),
                "language": self._detect_lang(path),
                "content": content[:3000],
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def analyse_repo(self, repo_path: str = ".") -> Dict:
        p = Path(repo_path)
        files_by_ext: Dict[str, int] = {}
        total_lines = 0
        file_count = 0

        for f in p.rglob("*"):
            if f.is_file() and not any(
                skip in str(f)
                for skip in [".git", "__pycache__", "node_modules", ".venv"]
            ):
                ext = f.suffix.lower()
                files_by_ext[ext] = files_by_ext.get(ext, 0) + 1
                file_count += 1
                try:
                    total_lines += len(f.read_text(errors="ignore").split("\n"))
                except Exception:
                    pass

        return {
            "ok": True,
            "repo_path": str(p.absolute()),
            "total_files": file_count,
            "total_lines": total_lines,
            "by_extension": dict(
                sorted(files_by_ext.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "has_git": (p / ".git").exists(),
            "has_tests": any(p.rglob("test_*.py")) or any(p.rglob("*.test.js")),
            "has_docker": (p / "Dockerfile").exists()
            or (p / "docker-compose.yml").exists(),
            "has_ci": (p / ".github").exists() or (p / ".gitlab-ci.yml").exists(),
        }

    def list_repo_files(self, repo_path: str = ".", limit: int = 50) -> Dict:
        p = Path(repo_path)
        files = []
        for f in sorted(p.rglob("*"))[:limit]:
            if f.is_file() and ".git" not in str(f) and "__pycache__" not in str(f):
                files.append(str(f.relative_to(p)))
        return {"ok": True, "files": files, "count": len(files)}

    def _detect_lang(self, path: str) -> str:
        ext_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".rs": "Rust",
            ".go": "Go",
            ".java": "Java",
            ".cs": "C#",
            ".cpp": "C++",
            ".c": "C",
            ".rb": "Ruby",
            ".php": "PHP",
            ".html": "HTML",
            ".css": "CSS",
            ".json": "JSON",
            ".yaml": "YAML",
            ".sh": "Shell",
            ".bat": "Batch",
            ".ps1": "PowerShell",
        }
        return ext_map.get(Path(path).suffix.lower(), "Unknown")

    def _run_cmd(
        self, cmd, cwd: str = ".", shell: bool = False, timeout: int = 60
    ) -> Dict:
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "ok": result.returncode == 0,
                "stdout": result.stdout.strip()[:3000],
                "stderr": result.stderr.strip()[:1000],
                "returncode": result.returncode,
                "command": cmd if isinstance(cmd, str) else " ".join(cmd),
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"Timed out after {timeout}s"}
        except FileNotFoundError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": str(e)}
