"""
src/dispatch/server.py — Dispatch Server
Mobile/web → desktop task handoff API.
Receive tasks from phone, execute on desktop, sync results back.
"""

import json, threading, time, uuid, asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Callable

DISPATCH_DIR = Path(__file__).parent.parent.parent / "data" / "dispatch"
DISPATCH_DIR.mkdir(parents=True, exist_ok=True)


class DispatchTask:
    def __init__(self, task_id, source, description, priority="normal"):
        self.id = task_id
        self.source = source  # "mobile", "web", "api"
        self.description = description
        self.priority = priority
        self.status = "queued"  # queued, running, completed, failed
        self.created_at = datetime.now().isoformat()
        self.started_at = None
        self.completed_at = None
        self.result = None
        self.error = None
        self.steps = []

    def to_dict(self):
        return {
            "id": self.id,
            "source": self.source,
            "description": self.description,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "steps": self.steps,
        }


class DispatchServer:
    """HTTP dispatch server + task queue for mobile→desktop handoff."""

    def __init__(self, port=8769, callback=None):
        self.port = port
        self.tasks: Dict[str, DispatchTask] = {}
        self.callback = callback  # Function to execute tasks
        self._running = False
        self._queue = []
        self._lock = threading.Lock()
        self._load_tasks()

    def _load_tasks(self):
        task_file = DISPATCH_DIR / "tasks.json"
        if task_file.exists():
            try:
                data = json.loads(task_file.read_text())
                for td in data:
                    t = DispatchTask(
                        td["id"],
                        td["source"],
                        td["description"],
                        td.get("priority", "normal"),
                    )
                    t.status = td.get("status", "queued")
                    t.result = td.get("result")
                    t.error = td.get("error")
                    t.steps = td.get("steps", [])
                    t.created_at = td.get("created_at", t.created_at)
                    self.tasks[t.id] = t
            except:
                pass

    def _save_tasks(self):
        task_file = DISPATCH_DIR / "tasks.json"
        data = [t.to_dict() for t in self.tasks.values()]
        task_file.write_text(json.dumps(data, indent=2))

    def receive_task(self, description, source="web", priority="normal"):
        """Receive a dispatched task from mobile/web."""
        task_id = str(uuid.uuid4())[:8]
        task = DispatchTask(task_id, source, description, priority)
        with self._lock:
            self.tasks[task_id] = task
            self._queue.append(task_id)
        self._save_tasks()
        return task_id

    def get_task(self, task_id):
        return self.tasks.get(task_id)

    def list_tasks(self, status=None):
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def process_queue(self):
        """Background worker that processes dispatched tasks."""
        while self._running:
            with self._lock:
                if not self._queue:
                    time.sleep(2)
                    continue
                task_id = self._queue.pop(0)
            task = self.tasks.get(task_id)
            if not task:
                continue

            task.status = "running"
            task.started_at = datetime.now().isoformat()
            self._save_tasks()

            try:
                if self.callback:
                    result = self.callback(task.description, task)
                    task.result = result
                    task.status = "completed"
                else:
                    task.result = f"Task executed: {task.description}"
                    task.status = "completed"
            except Exception as e:
                task.error = str(e)
                task.status = "failed"

            task.completed_at = datetime.now().isoformat()
            self._save_tasks()

    def start(self):
        """Start dispatch server + worker."""
        self._running = True
        # Start HTTP server
        threading.Thread(target=self._run_http, daemon=True).start()
        # Start task worker
        threading.Thread(target=self.process_queue, daemon=True).start()
        print(f"[Dispatch] Server on http://localhost:{self.port}")

    def _run_http(self):
        """Simple HTTP server for dispatch API."""
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class Handler(BaseHTTPRequestHandler):
            server = self

            def do_GET(self):
                if self.path == "/api/tasks":
                    self._json([t.to_dict() for t in self.server.list_tasks()])
                elif self.path.startswith("/api/tasks/"):
                    task_id = self.path.split("/")[-1]
                    task = self.server.get_task(task_id)
                    if task:
                        self._json(task.to_dict())
                    else:
                        self._error(404, "Task not found")
                else:
                    self._json(
                        {
                            "status": "ok",
                            "service": "Baba Dispatch",
                            "port": self.server.port,
                        }
                    )

            def do_POST(self):
                if self.path == "/api/dispatch":
                    length = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(length)) if length else {}
                    desc = body.get("description", "")
                    source = body.get("source", "web")
                    priority = body.get("priority", "normal")
                    if not desc:
                        self._error(400, "Description required")
                        return
                    task_id = self.server.receive_task(desc, source, priority)
                    self._json({"task_id": task_id, "status": "queued"})
                else:
                    self._error(404, "Not found")

            def _json(self, data):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def _error(self, code, msg):
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": msg}).encode())

            def log_message(self, format, *args):
                pass

        server = HTTPServer(("0.0.0.0", self.port), Handler)
        server.serve_forever()
