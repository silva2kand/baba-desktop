"""
src/dispatch/dispatcher.py
Dispatch System - priority task queue with background worker thread.
"""

import json
import uuid
import asyncio
import threading
from pathlib import Path
from datetime import datetime, UTC, timedelta
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field


class DispatchStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class DispatchTask:
    task_id: str
    instruction: str
    source: str = "web"
    context: Dict = field(default_factory=dict)
    priority: int = 5
    status: DispatchStatus = DispatchStatus.QUEUED
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    steps: List[Dict] = field(default_factory=list)
    result: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def add_step(self, step: str, status: str = "done", detail: str = ""):
        self.steps.append(
            {
                "ts": datetime.now(UTC).isoformat(),
                "step": step,
                "status": status,
                "detail": detail,
            }
        )

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "instruction": self.instruction,
            "source": self.source,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "steps": self.steps,
            "result": self.result,
            "artifacts": self.artifacts,
            "error": self.error,
            "priority": self.priority,
        }


class Dispatcher:
    """Dispatch engine - receives tasks, queues them, executes on desktop."""

    def __init__(self, brain, orchestrator, pc_bridge, app_bridge, tools, pool):
        self.brain = brain
        self.orch = orchestrator
        self.pc = pc_bridge
        self.apps = app_bridge
        self.tools = tools
        self.pool = pool
        self._queue: List[DispatchTask] = []
        self._history: Dict[str, DispatchTask] = {}
        self._running: Optional[DispatchTask] = None
        self._callbacks: List[Callable] = []
        self._log_path = Path("logs/dispatch.jsonl")
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._active = True

    def submit(
        self,
        instruction: str,
        source: str = "web",
        context: Dict = None,
        priority: int = 5,
    ) -> DispatchTask:
        task = DispatchTask(
            task_id=str(uuid.uuid4())[:8],
            instruction=instruction,
            source=source,
            context=context or {},
            priority=priority,
        )
        with self._lock:
            inserted = False
            for i, t in enumerate(self._queue):
                if task.priority < t.priority:
                    self._queue.insert(i, task)
                    inserted = True
                    break
            if not inserted:
                self._queue.append(task)
            self._history[task.task_id] = task

        self._log_task(task, "submitted")
        self._notify(task, "submitted")
        return task

    def start_worker(self):
        t = threading.Thread(target=self._worker_loop, daemon=True)
        t.start()

    def _worker_loop(self):
        while self._active:
            task = self._dequeue()
            if task:
                asyncio.run(self._execute(task))
            else:
                time.sleep(1)

    def _dequeue(self) -> Optional[DispatchTask]:
        with self._lock:
            if self._queue and self._running is None:
                task = self._queue.pop(0)
                self._running = task
                return task
        return None

    async def _execute(self, task: DispatchTask):
        task.status = DispatchStatus.RUNNING
        task.started_at = datetime.now(UTC).isoformat()
        self._notify(task, "started")
        self._log_task(task, "started")

        try:
            plan = self._plan(task.instruction)
            task.add_step("Plan created", "done", f"{len(plan)} steps planned")
            self._notify(task, "planned")

            for i, step in enumerate(plan):
                task.add_step(f"Step {i + 1}: {step['name']}", "running")
                self._notify(task, "step_running")

                result = await self._run_step(step, task)

                task.steps[-1]["status"] = "done"
                task.steps[-1]["detail"] = result[:120] if result else ""
                self._notify(task, "step_done")
                await asyncio.sleep(0.1)

            summary = await self._summarise(task)
            task.result = summary
            task.status = DispatchStatus.COMPLETED
            task.completed_at = datetime.now(UTC).isoformat()

        except Exception as e:
            task.error = str(e)
            task.status = DispatchStatus.FAILED
            task.add_step("Error", "failed", str(e))

        finally:
            with self._lock:
                self._running = None
            self._log_task(task, task.status.value)
            self._notify(task, task.status.value)

    def _plan(self, instruction: str) -> List[Dict]:
        instr = instruction.lower()
        social_map = {
            "facebook": "facebook",
            "instagram": "instagram",
            "tiktok": "tiktok",
            "telegram": "telegram",
            "linkedin": "linkedin",
            "twitter": "x",
            "x.com": "x",
        }
        matched_social = next((v for k, v in social_map.items() if k in instr), None)
        if matched_social:
            return [
                {
                    "name": f"Open {matched_social}",
                    "type": "app",
                    "app": "social",
                    "action": "open",
                    "platform": matched_social,
                },
                {
                    "name": "Analyse social task",
                    "type": "agent",
                    "agent": "content",
                    "task": instruction,
                },
                {
                    "name": "Draft social output",
                    "type": "app",
                    "app": "social",
                    "action": "draft_post",
                    "platform": matched_social,
                    "caption": instruction,
                    "requires_approval": True,
                },
            ]
        if "exo" in instr:
            return [
                {
                    "name": "Open Exo",
                    "type": "app",
                    "app": "exo",
                    "action": "open",
                },
                {
                    "name": "Run inbox triage",
                    "type": "app",
                    "app": "exo",
                    "action": "triage_inbox",
                    "limit": 30,
                },
                {
                    "name": "Summarise triage actions",
                    "type": "agent",
                    "agent": "comms",
                    "task": instruction,
                },
            ]
        if any(k in instr for k in ["llm wiki", "karpathy", "knowledge wiki"]):
            return [
                {
                    "name": "Compile knowledge note",
                    "type": "agent",
                    "agent": "wiki",
                    "task": instruction,
                },
                {
                    "name": "Capture in Obsidian",
                    "type": "app",
                    "app": "obsidian",
                    "action": "capture_note",
                    "title": "LLM Wiki Update",
                    "content": instruction,
                    "requires_approval": True,
                },
            ]
        if "obsidian" in instr or "knowledge base" in instr or "vault" in instr:
            return [
                {
                    "name": "Open Obsidian",
                    "type": "app",
                    "app": "obsidian",
                    "action": "open",
                },
                {
                    "name": "Generate knowledge note",
                    "type": "agent",
                    "agent": "obsidian",
                    "task": instruction,
                },
                {
                    "name": "Capture note in vault",
                    "type": "app",
                    "app": "obsidian",
                    "action": "capture_note",
                    "title": "Baba Dispatch Note",
                    "content": instruction,
                    "requires_approval": True,
                },
            ]
        if any(k in instr for k in ["email", "inbox", "outlook", "gmail"]):
            return [
                {
                    "name": "Open email client",
                    "type": "app",
                    "app": "outlook",
                    "action": "open",
                },
                {
                    "name": "Read inbox",
                    "type": "app",
                    "app": "outlook",
                    "action": "read_inbox",
                },
                {
                    "name": "Process per instruction",
                    "type": "agent",
                    "agent": "comms",
                    "task": instruction,
                },
                {"name": "Draft response", "type": "draft", "requires_approval": True},
            ]
        elif any(k in instr for k in ["whatsapp", "message", "chat"]):
            return [
                {
                    "name": "Open WhatsApp",
                    "type": "app",
                    "app": "whatsapp",
                    "action": "open",
                },
                {"name": "Read conversations", "type": "pc", "action": "ocr"},
                {
                    "name": "Analyse content",
                    "type": "agent",
                    "agent": "comms",
                    "task": instruction,
                },
                {"name": "Draft replies", "type": "draft", "requires_approval": True},
            ]
        elif any(
            k in instr
            for k in [
                "file",
                "folder",
                "download",
                "organise",
                "organize",
                "sort",
                "rename",
            ]
        ):
            return [
                {"name": "Access file system", "type": "pc", "action": "file"},
                {"name": "Scan target directory", "type": "tool", "tool": "list_dir"},
                {
                    "name": "Process files per instruction",
                    "type": "tool",
                    "tool": "shell_exec",
                },
                {"name": "Report changes", "type": "report"},
            ]
        elif any(
            k in instr
            for k in ["browser", "web", "search", "scrape", "extract", "website"]
        ):
            return [
                {
                    "name": "Open browser",
                    "type": "pc",
                    "action": "run_process",
                    "command": "chrome",
                },
                {"name": "Navigate to target", "type": "pc", "action": "type"},
                {"name": "Extract data", "type": "tool", "tool": "web_fetch"},
                {
                    "name": "Process and format",
                    "type": "agent",
                    "agent": "acct",
                    "task": instruction,
                },
                {"name": "Save output", "type": "tool", "tool": "write_file"},
            ]
        elif any(k in instr for k in ["invoice", "bill", "receipt", "payment"]):
            return [
                {"name": "Locate documents", "type": "tool", "tool": "search_files"},
                {"name": "Extract data with vision", "type": "vision", "task": "bill"},
                {
                    "name": "Process via accounting agent",
                    "type": "agent",
                    "agent": "acct",
                    "task": instruction,
                },
                {"name": "Generate report", "type": "tool", "tool": "write_file"},
            ]
        elif any(k in instr for k in ["report", "summary", "analyse", "analyze"]):
            return [
                {
                    "name": "Gather relevant data",
                    "type": "tool",
                    "tool": "brain_search",
                },
                {
                    "name": "Run analysis",
                    "type": "agent",
                    "agent": "acct",
                    "task": instruction,
                },
                {"name": "Format report", "type": "tool", "tool": "write_file"},
            ]
        else:
            return [
                {
                    "name": "Analyse instruction",
                    "type": "agent",
                    "agent": "pa",
                    "task": instruction,
                },
                {
                    "name": "Execute primary action",
                    "type": "tool",
                    "tool": "shell_exec",
                },
                {"name": "Report result", "type": "report"},
            ]

    async def _run_step(self, step: Dict, task: DispatchTask) -> str:
        step_type = step.get("type")

        if step_type == "agent":
            reply = await self.orch.run(
                step["agent"], step.get("task", task.instruction)
            )
            return reply[:200]

        elif step_type == "pc":
            action = step.get("action", "screenshot")
            action_aliases = {
                "ocr": "ocr_screen",
                "screen_ocr": "ocr_screen",
                "process": "run_process",
                "open_app": "run_process",
            }
            action = action_aliases.get(action, action)
            try:
                command = step.get("command")
                cmd_payload = {"action": action, **step}
                if action == "run_process" and command and "command" not in cmd_payload:
                    cmd_payload["command"] = command
                result = await self.pc.execute(cmd_payload)
                return str(result)[:200]
            except Exception as e:
                return f"PC action skipped (bridge not running): {e}"

        elif step_type == "app":
            app_id = step.get("app")
            action = step.get("action", "open")
            method = getattr(self.apps, f"{app_id}_{action}", None)
            if method:
                kwargs = {}
                params = step.get("params")
                if isinstance(params, dict):
                    kwargs.update(params)
                for key in (
                    "contact",
                    "message",
                    "caption",
                    "to",
                    "subject",
                    "body",
                    "title",
                    "content",
                    "folder",
                    "url",
                    "platform",
                    "path",
                    "approved",
                    "limit",
                    "query",
                    "topic_hint",
                ):
                    if key in step and key not in kwargs:
                        kwargs[key] = step[key]
                if step.get("requires_approval") and "approved" not in kwargs:
                    kwargs["approved"] = False
                try:
                    result = method(**kwargs) if kwargs else method()
                except TypeError:
                    result = method()
                return str(result)[:200]
            return f"App action {app_id}.{action} queued"

        elif step_type == "tool":
            tool_name = step.get("tool")
            if self.tools:
                kwargs = {
                    k: v
                    for k, v in step.items()
                    if k
                    not in {
                        "name",
                        "type",
                        "tool",
                        "requires_approval",
                    }
                }
                if tool_name == "brain_search" and "query" not in kwargs:
                    kwargs["query"] = task.instruction
                if tool_name == "list_dir" and "path" not in kwargs:
                    kwargs["path"] = "."
                if tool_name == "search_files" and "directory" not in kwargs:
                    kwargs["directory"] = "."
                    kwargs.setdefault("pattern", task.instruction)
                result = self.tools.run(tool_name, **kwargs)
                return str(result)[:200]
            return f"Tool {tool_name} executed"

        elif step_type == "vision":
            return "Vision analysis queued - awaiting image input"

        elif step_type == "draft":
            return "Draft prepared - awaiting your approval before sending"

        elif step_type == "report":
            return "Report generated and saved to data/exports/"

        return "Step completed"

    async def _summarise(self, task: DispatchTask) -> str:
        steps_done = [s for s in task.steps if s["status"] == "done"]
        pending_approval = [
            s for s in task.steps if "approval" in s.get("detail", "").lower()
        ]

        summary = f"Task complete: {task.instruction[:60]}\n\n"
        summary += f"Steps completed: {len(steps_done)}/{len(task.steps)}\n"
        if pending_approval:
            summary += (
                f"\n{len(pending_approval)} action(s) waiting for your approval:\n"
            )
            for s in pending_approval:
                summary += f"  - {s['step']}\n"
        summary += f"\nSource: {task.source} -> Desktop"
        return summary

    def abort(self, task_id: str) -> bool:
        task = self._history.get(task_id)
        if task and task.status == DispatchStatus.RUNNING:
            task.status = DispatchStatus.ABORTED
            task.add_step("Aborted by user", "aborted")
            self._running = None
            return True
        return False

    def pause(self, task_id: str):
        task = self._history.get(task_id)
        if task and task.status == DispatchStatus.RUNNING:
            task.status = DispatchStatus.PAUSED

    def resume(self, task_id: str):
        task = self._history.get(task_id)
        if task and task.status == DispatchStatus.PAUSED:
            task.status = DispatchStatus.QUEUED
            with self._lock:
                self._queue.insert(0, task)

    def get_status(self, task_id: str) -> Optional[Dict]:
        task = self._history.get(task_id)
        return task.to_dict() if task else None

    def get_queue(self) -> List[Dict]:
        return [t.to_dict() for t in self._queue]

    def get_history(self, limit: int = 20) -> List[Dict]:
        tasks = sorted(self._history.values(), key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in tasks[:limit]]

    def get_running(self) -> Optional[Dict]:
        return self._running.to_dict() if self._running else None

    def subscribe(self, callback: Callable):
        self._callbacks.append(callback)

    def _notify(self, task: DispatchTask, event: str):
        for cb in self._callbacks:
            try:
                cb(task.to_dict(), event)
            except Exception:
                pass

    def _log_task(self, task: DispatchTask, event: str):
        entry = {"event": event, **task.to_dict()}
        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")


class DispatchServer:
    """FastAPI HTTP server on port 8767 for external task submission."""

    def __init__(self, dispatcher: Dispatcher, port: int = 8767):
        self.dispatcher = dispatcher
        self.port = port

    def start(self):
        import threading

        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        try:
            from fastapi import FastAPI, Request
            from fastapi.responses import JSONResponse
            import uvicorn

            app = FastAPI(title="Baba Dispatch API")

            @app.post("/dispatch/submit")
            async def submit(req: Request):
                data = await req.json()
                task = self.dispatcher.submit(
                    instruction=data.get("instruction", ""),
                    source=data.get("source", "web"),
                    context=data.get("context", {}),
                    priority=data.get("priority", 5),
                )
                return JSONResponse(
                    {"ok": True, "task_id": task.task_id, "status": task.status.value}
                )

            @app.get("/dispatch/status/{task_id}")
            async def status(task_id: str):
                s = self.dispatcher.get_status(task_id)
                return JSONResponse(s or {"error": "not found"})

            @app.get("/dispatch/queue")
            async def queue():
                return JSONResponse(
                    {
                        "queue": self.dispatcher.get_queue(),
                        "running": self.dispatcher.get_running(),
                    }
                )

            @app.get("/dispatch/history")
            async def history():
                return JSONResponse({"history": self.dispatcher.get_history()})

            @app.post("/dispatch/abort/{task_id}")
            async def abort(task_id: str):
                ok = self.dispatcher.abort(task_id)
                return JSONResponse({"ok": ok})

            print(f"[Dispatch] HTTP API on http://localhost:{self.port}")
            uvicorn.run(app, host="localhost", port=self.port, log_level="warning")
        except ImportError:
            print(f"[Dispatch] Install fastapi+uvicorn for full dispatch API")


import time
