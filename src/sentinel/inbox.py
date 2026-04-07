"""
src/sentinel/inbox.py
Central sentinel task inbox persisted to local JSON.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, Any, List, Optional


class SentinelInbox:
    def __init__(self, path: str = "data/sentinel/inbox.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._data = self._load()

    def enqueue(
        self,
        source: str,
        event_type: str,
        payload: Dict[str, Any],
        priority: str = "normal",
    ) -> Dict[str, Any]:
        task = {
            "id": str(uuid.uuid4())[:8],
            "source": str(source or "sentinel"),
            "event_type": str(event_type or "event"),
            "payload": payload or {},
            "priority": str(priority or "normal"),
            "status": "queued",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "result": {},
            "error": "",
        }
        with self._lock:
            self._data.setdefault("tasks", []).append(task)
            self._save_unlocked()
        return task

    def update(
        self,
        task_id: str,
        status: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: str = "",
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            for task in self._data.get("tasks", []):
                if task.get("id") == task_id:
                    if status:
                        task["status"] = status
                    if result is not None:
                        task["result"] = result
                    if error:
                        task["error"] = error
                    task["updated_at"] = datetime.now(UTC).isoformat()
                    self._save_unlocked()
                    return dict(task)
        return None

    def list(self, limit: int = 100, status: str = "") -> List[Dict[str, Any]]:
        items = list(self._data.get("tasks", []))
        if status:
            items = [t for t in items if t.get("status") == status]
        items.sort(key=lambda t: t.get("created_at", ""), reverse=True)
        return items[: max(1, int(limit))]

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        for task in self._data.get("tasks", []):
            if task.get("id") == task_id:
                return dict(task)
        return None

    def stats(self) -> Dict[str, Any]:
        items = self._data.get("tasks", [])
        counts: Dict[str, int] = {}
        for task in items:
            status = task.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
        return {
            "total": len(items),
            "by_status": counts,
        }

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    data.setdefault("tasks", [])
                    return data
            except Exception:
                pass
        return {"tasks": []}

    def _save_unlocked(self):
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

