"""
src/tools_experimental/builder.py
Self-improvement engine for tools, skills, and knowledge updates.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_EXPERIMENTAL_DIR = Path("src/tools_experimental")
DEFAULT_ACTIVE_DIR = Path("src/tools")
SELF_IMPROVE_DIR = Path("data/self_improve")
SKILL_DRAFTS_DIR = SELF_IMPROVE_DIR / "skills_drafts"
SKILL_ACTIVE_DIR = SELF_IMPROVE_DIR / "skills_active"
KNOWLEDGE_DRAFTS_DIR = SELF_IMPROVE_DIR / "knowledge_drafts"
STATE_FILE = SELF_IMPROVE_DIR / "approval_queue.json"
TOOL_LOG = Path("logs/tool_builder.jsonl")
SELF_IMPROVE_LOG = Path("logs/self_improve.jsonl")


class ToolBuilder:
    """Builds and manages self-improvement drafts with human approval gates."""

    def __init__(self, pool, brain_index=None, settings=None, memory=None):
        self.pool = pool
        self.brain = brain_index
        self.settings = settings
        self.memory = memory

        self.experimental_dir = Path(
            getattr(settings, "tools_experimental_dir", DEFAULT_EXPERIMENTAL_DIR)
        )
        self.active_dir = Path(
            getattr(settings, "tools_active_dir", DEFAULT_ACTIVE_DIR)
        )

        for d in [
            self.experimental_dir,
            self.active_dir,
            SKILL_DRAFTS_DIR,
            SKILL_ACTIVE_DIR,
            KNOWLEDGE_DRAFTS_DIR,
            TOOL_LOG.parent,
            SELF_IMPROVE_LOG.parent,
            STATE_FILE.parent,
        ]:
            d.mkdir(parents=True, exist_ok=True)

        self._state = self._load_state()

    async def propose(self, brain_index=None) -> List[Dict[str, Any]]:
        """Backward-compatible tool proposal list."""
        index = brain_index or self.brain
        stats = index.stats() if index else {}
        existing = [f.stem for f in self.experimental_dir.glob("*.py")] + [
            f.stem for f in self.active_dir.glob("*.py")
        ]
        proposals = [
            {
                "name": "invoice_chaser",
                "desc": "Auto-generate invoice chaser emails from overdue Brain items",
                "priority": "high",
            },
            {
                "name": "renewal_alerter",
                "desc": "Watch indexed contracts/policies and alert before renewal dates",
                "priority": "high",
            },
            {
                "name": "cashflow_report",
                "desc": "Generate weekly cashflow snapshot from invoices and bills",
                "priority": "high",
            },
            {
                "name": "knowledge_digest",
                "desc": "Summarise new knowledge and unresolved decisions from memory",
                "priority": "medium",
            },
            {
                "name": "approval_audit",
                "desc": "Analyse approval history to find repeated manual steps",
                "priority": "medium",
            },
        ]
        if stats:
            proposals.append(
                {
                    "name": "brain_gap_report",
                    "desc": (
                        "Spot missing or low-coverage categories in the Brain Index "
                        f"(items currently: {stats.get('total', 0)})"
                    ),
                    "priority": "medium",
                }
            )
        proposals = [p for p in proposals if p["name"] not in existing]
        return proposals[:6]

    async def propose_self_improvements(
        self, goal: str = "", limit: int = 8
    ) -> List[Dict[str, Any]]:
        """Return cross-domain improvements for tools, skills, and knowledge."""
        mem_stats = self.memory.stats() if self.memory else {}
        brain_stats = self.brain.stats() if self.brain else {}
        proposals: List[Dict[str, Any]] = []

        proposals.append(
            {
                "kind": "skill",
                "name": "approval_gatekeeper",
                "summary": "Create a reusable skill for approval-driven change workflows.",
                "reason": "You requested self-improvements only with explicit approval.",
            }
        )

        if (mem_stats.get("knowledge", 0) or 0) < 20:
            proposals.append(
                {
                    "kind": "knowledge",
                    "name": "knowledge_capture_playbook",
                    "summary": "Add a structured capture template for reusable business knowledge.",
                    "reason": "Knowledge memory is still shallow and can be expanded.",
                }
            )

        if (brain_stats.get("total", 0) or 0) > 0:
            proposals.append(
                {
                    "kind": "tool",
                    "name": "brain_delta_report",
                    "summary": "Generate weekly deltas in indexed data and unresolved actions.",
                    "reason": "Supports continuous self-improvement from new data.",
                }
            )

        if goal.strip():
            prompt = f"""You are a self-improvement planner for Baba Desktop.
Generate up to 4 concise improvement proposals for this goal:
{goal}

Return strict JSON array. Each item must include:
- kind: one of "tool", "skill", "knowledge", "memory_preference"
- name: snake_case id
- summary: short sentence
- reason: short sentence

Return ONLY JSON."""
            try:
                raw = await self._chat(prompt, max_tokens=900)
                ai_items = self._extract_json_array(raw)
                for item in ai_items:
                    kind = str(item.get("kind", "")).strip()
                    if kind not in {
                        "tool",
                        "skill",
                        "knowledge",
                        "memory_preference",
                    }:
                        continue
                    proposals.append(
                        {
                            "kind": kind,
                            "name": self._safe_name(item.get("name", "improvement")),
                            "summary": str(item.get("summary", "")).strip(),
                            "reason": str(item.get("reason", "")).strip(),
                        }
                    )
            except Exception:
                pass

        dedup = {}
        for p in proposals:
            dedup[f"{p.get('kind')}::{p.get('name')}"] = p
        return list(dedup.values())[:limit]

    async def build_from_description(
        self, description: str, name: str = None
    ) -> Dict[str, Any]:
        name = self._safe_name(name or description)
        prompt = f"""Write a Python tool module for Baba Desktop Business Brain.

Tool description: {description}

Requirements:
1. Single file with a run(**kwargs) function as the main entry point
2. Include a test() function that verifies the tool works
3. Must be safe: no destructive operations and no sending/posting actions
4. Include docstrings
5. Return structured data (dict or list) when possible
6. Handle errors gracefully

Return ONLY the Python code, no markdown, no explanation."""

        code = await self._chat(prompt, max_tokens=2200)
        code = re.sub(r"```python\s*", "", code)
        code = re.sub(r"```\s*", "", code)
        code = code.strip()
        return await self.save_draft(name, description, code)

    async def build_skill_from_description(
        self, description: str, name: str = None
    ) -> Dict[str, Any]:
        name = self._safe_name(name or description)
        prompt = f"""Create a reusable Baba skill specification as strict JSON object.

Skill goal: {description}

Schema:
{{
  "name": "snake_case",
  "title": "short title",
  "purpose": "one short paragraph",
  "trigger_phrases": ["..."],
  "instructions": ["step 1", "step 2", "step 3"],
  "approval_required": true,
  "safety_notes": ["..."]
}}

Return ONLY JSON."""
        raw = await self._chat(prompt, max_tokens=1300)

        try:
            payload = self._extract_json_object(raw)
        except Exception:
            payload = {
                "name": name,
                "title": name.replace("_", " ").title(),
                "purpose": description,
                "trigger_phrases": [description[:80]],
                "instructions": [
                    "Analyse request",
                    "Draft safe execution plan",
                    "Require explicit user approval before applying updates",
                ],
                "approval_required": True,
                "safety_notes": [
                    "Never execute destructive actions automatically.",
                    "Always surface pending changes for human approval.",
                ],
            }

        payload["name"] = self._safe_name(payload.get("name", name))
        path = SKILL_DRAFTS_DIR / f"{payload['name']}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        meta = {
            "ok": True,
            "name": payload["name"],
            "path": str(path),
            "status": "draft",
            "created_at": datetime.now(UTC).isoformat(),
            "description": description,
        }
        self._log("skill_draft_saved", meta)
        return meta

    def draft_knowledge_note(
        self, topic: str, content: str, source: str = "user", tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        name = self._safe_name(topic) or f"knowledge_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
        payload = {
            "topic": topic.strip(),
            "content": content.strip(),
            "source": source.strip() or "user",
            "tags": tags or [],
            "created_at": datetime.now(UTC).isoformat(),
        }
        path = KNOWLEDGE_DRAFTS_DIR / f"{name}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._log("knowledge_draft_saved", {"name": name, "path": str(path)})
        return {"ok": True, "name": name, "path": str(path), "status": "draft"}

    async def save_draft(
        self, name: str, description: str, code: str
    ) -> Dict[str, Any]:
        path = self.experimental_dir / f"{name}.py"

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
        path = self.experimental_dir / f"{name}.py"
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

        src = self.experimental_dir / f"{name}.py"
        dest = self.active_dir / f"{name}.py"
        if not src.exists():
            return {"ok": False, "error": f"Tool not found: {name}"}

        self.active_dir.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        self._log("promoted", {"name": name, "from": str(src), "to": str(dest)})
        return {
            "ok": True,
            "name": name,
            "active_path": str(dest),
            "message": f"Tool '{name}' promoted to active tools",
        }

    def promote_skill(self, name: str, approved: bool = False) -> Dict[str, Any]:
        if not approved:
            return {
                "ok": False,
                "requires_approval": True,
                "name": name,
                "message": f"Approve promotion of skill '{name}'?",
            }
        src = SKILL_DRAFTS_DIR / f"{name}.json"
        dest = SKILL_ACTIVE_DIR / f"{name}.json"
        if not src.exists():
            return {"ok": False, "error": f"Skill draft not found: {name}"}
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        self._log("skill_promoted", {"name": name, "from": str(src), "to": str(dest)})
        return {
            "ok": True,
            "name": name,
            "active_path": str(dest),
            "message": f"Skill '{name}' promoted to active skills",
        }

    def queue_update(
        self, kind: str, title: str, payload: Dict[str, Any], summary: str = ""
    ) -> Dict[str, Any]:
        request = {
            "id": str(uuid.uuid4())[:8],
            "kind": kind,
            "title": title.strip() or kind,
            "payload": payload or {},
            "summary": summary.strip(),
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._state.setdefault("pending", []).append(request)
        self._save_state()
        self._log_self("queued", request)
        return {"ok": True, **request}

    def list_pending_updates(self) -> List[Dict[str, Any]]:
        return list(self._state.get("pending", []))

    def list_update_history(self, limit: int = 30) -> List[Dict[str, Any]]:
        history = list(self._state.get("history", []))
        history.sort(key=lambda x: x.get("decided_at", ""), reverse=True)
        return history[:limit]

    def decide_update(self, request_id: str, approved: bool = False) -> Dict[str, Any]:
        pending = self._state.get("pending", [])
        idx = next((i for i, item in enumerate(pending) if item.get("id") == request_id), -1)
        if idx < 0:
            return {"ok": False, "error": f"Update request not found: {request_id}"}

        req = pending.pop(idx)
        req["decided_at"] = datetime.now(UTC).isoformat()
        req["approved"] = bool(approved)

        if not approved:
            req["status"] = "denied"
            self._state.setdefault("history", []).append(req)
            self._save_state()
            self._log_self("denied", req)
            if self.memory:
                self.memory.record_approval(req.get("kind", "update"), False, req.get("title", ""))
            return {"ok": True, "status": "denied", "request": req}

        apply_result = self._apply_update(req)
        req["status"] = "applied" if apply_result.get("ok") else "failed"
        req["result"] = apply_result
        self._state.setdefault("history", []).append(req)
        self._save_state()
        self._log_self("approved", req)
        if self.memory:
            self.memory.record_approval(req.get("kind", "update"), True, req.get("title", ""))
        return {"ok": bool(apply_result.get("ok")), "status": req["status"], "request": req}

    def self_improve_status(self) -> Dict[str, Any]:
        return {
            "pending_updates": len(self._state.get("pending", [])),
            "history_items": len(self._state.get("history", [])),
            "tool_drafts": len(list(self.experimental_dir.glob("*.py"))),
            "active_tools": len([p for p in self.active_dir.glob("*.py") if not p.name.startswith("_")]),
            "skill_drafts": len(list(SKILL_DRAFTS_DIR.glob("*.json"))),
            "active_skills": len(list(SKILL_ACTIVE_DIR.glob("*.json"))),
            "knowledge_drafts": len(list(KNOWLEDGE_DRAFTS_DIR.glob("*.json"))),
        }

    def delete(self, name: str, approved: bool = False) -> Dict[str, Any]:
        if not approved:
            return {"ok": False, "requires_approval": True, "name": name}
        path = self.experimental_dir / f"{name}.py"
        if path.exists():
            path.unlink()
        self._log("deleted", {"name": name})
        return {"ok": True, "message": f"Tool '{name}' deleted"}

    def list_all(self) -> List[Dict]:
        tools = []
        for path in sorted(self.experimental_dir.glob("*.py")):
            if path.name.startswith("_"):
                continue
            code = path.read_text(encoding="utf-8", errors="ignore")
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
        for path in sorted(self.active_dir.glob("*.py")):
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

    def _apply_update(self, request: Dict[str, Any]) -> Dict[str, Any]:
        kind = request.get("kind", "")
        payload = request.get("payload", {}) or {}

        if kind == "promote_tool":
            return self.promote(str(payload.get("name", "")), approved=True)

        if kind == "promote_skill":
            return self.promote_skill(str(payload.get("name", "")), approved=True)

        if kind == "save_knowledge":
            topic = str(payload.get("topic", "")).strip()
            content = str(payload.get("content", "")).strip()
            source = str(payload.get("source", "user")).strip() or "user"
            tags = payload.get("tags") or []
            if not topic or not content:
                return {"ok": False, "error": "Knowledge payload missing topic/content"}
            if self.memory:
                mem_id = self.memory.remember_knowledge(topic, content, source=source, tags=tags)
                return {"ok": True, "memory_id": mem_id, "message": "Knowledge saved to memory"}
            out = {
                "topic": topic,
                "content": content,
                "source": source,
                "tags": tags,
                "saved_at": datetime.now(UTC).isoformat(),
            }
            out_path = SKILL_ACTIVE_DIR.parent / "knowledge_active" / f"{self._safe_name(topic)}.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
            return {"ok": True, "path": str(out_path), "message": "Knowledge saved to file"}

        if kind == "memory_preference":
            key = str(payload.get("key", "")).strip()
            value = payload.get("value")
            if not key:
                return {"ok": False, "error": "memory_preference missing key"}
            if not self.memory:
                return {"ok": False, "error": "Memory service not available"}
            self.memory.update_preference(key, value)
            return {"ok": True, "message": f"Memory preference updated: {key}"}

        return {"ok": False, "error": f"Unsupported update kind: {kind}"}

    async def _chat(self, prompt: str, max_tokens: int = 2000) -> str:
        provider = "lmstudio"
        model = "omnicoder-9b"

        if self.settings and getattr(self.settings, "routing", None):
            route = self.settings.routing.get("tool_building", {})
            provider = route.get("provider", provider)
            model_key = route.get("model", "omnicoder")
            provider_cfg = self.settings.providers.get(provider, {})
            model = provider_cfg.get("models", {}).get(model_key, model)

        messages = [{"role": "user", "content": prompt}]
        try:
            return await self.pool.chat(provider, model, messages, max_tokens=max_tokens)
        except Exception:
            return await self.pool.chat(
                "groq", "llama-3.3-70b-versatile", messages, max_tokens=max_tokens
            )

    def _load_state(self) -> Dict[str, Any]:
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    data.setdefault("pending", [])
                    data.setdefault("history", [])
                    return data
            except Exception:
                pass
        return {"pending": [], "history": [], "updated_at": ""}

    def _save_state(self):
        self._state["updated_at"] = datetime.now(UTC).isoformat()
        STATE_FILE.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def _extract_json_array(self, text: str) -> List[Dict[str, Any]]:
        m = re.search(r"\[[\s\S]*\]", text)
        if not m:
            raise ValueError("No JSON array found")
        data = json.loads(m.group(0))
        if not isinstance(data, list):
            raise ValueError("Response is not a JSON array")
        return [item for item in data if isinstance(item, dict)]

    def _extract_json_object(self, text: str) -> Dict[str, Any]:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise ValueError("No JSON object found")
        data = json.loads(m.group(0))
        if not isinstance(data, dict):
            raise ValueError("Response is not a JSON object")
        return data

    def _safe_name(self, raw: str) -> str:
        text = (raw or "").strip().lower()
        text = re.sub(r"[^a-z0-9_]+", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        return text[:40] or "custom_item"

    def _log(self, action: str, data: Dict[str, Any]):
        entry = {"ts": datetime.now(UTC).isoformat(), "action": action, **data}
        with open(TOOL_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def _log_self(self, action: str, data: Dict[str, Any]):
        entry = {"ts": datetime.now(UTC).isoformat(), "action": action, **data}
        with open(SELF_IMPROVE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
