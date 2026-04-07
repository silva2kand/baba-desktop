"""
src/scheduler/scheduler.py
Task Scheduler - time-based and trigger-based automation.
"""

import json
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class TriggerType(Enum):
    TIME_DAILY = "daily"
    TIME_WEEKLY = "weekly"
    TIME_MONTHLY = "monthly"
    TIME_ONCE = "once"
    FILE_NEW = "file_new"
    FILE_CHANGED = "file_changed"
    EMAIL = "email"
    WEBHOOK = "webhook"
    MANUAL = "manual"


@dataclass
class ScheduledTask:
    task_id: str
    name: str
    instruction: str
    trigger: TriggerType
    trigger_cfg: Dict = field(default_factory=dict)
    enabled: bool = True
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    run_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: str = "scheduler"


BUILT_IN_SCHEDULES = [
    {
        "task_id": "daily_email_check",
        "name": "Daily email triage",
        "instruction": "Check inbox, summarise unread emails, extract tasks, flag urgent items. Draft replies for approval.",
        "trigger": TriggerType.TIME_DAILY,
        "trigger_cfg": {"time": "08:30"},
        "enabled": False,
    },
    {
        "task_id": "weekly_cashflow",
        "name": "Weekly cashflow report",
        "instruction": "Generate weekly cashflow report from Brain Index. Summarise bills, upcoming renewals, overdue invoices.",
        "trigger": TriggerType.TIME_WEEKLY,
        "trigger_cfg": {"time": "09:00", "days": ["monday"]},
        "enabled": False,
    },
    {
        "task_id": "weekly_slack_digest",
        "name": "Weekly Slack digest",
        "instruction": "Summarise all Slack messages from the past week. Extract key decisions, action items, and pending replies.",
        "trigger": TriggerType.TIME_WEEKLY,
        "trigger_cfg": {"time": "09:00", "days": ["monday"]},
        "enabled": False,
    },
    {
        "task_id": "daily_renewal_check",
        "name": "Daily renewal radar",
        "instruction": "Check Brain Index for renewals due in next 30 days. Alert if anything needs attention.",
        "trigger": TriggerType.TIME_DAILY,
        "trigger_cfg": {"time": "09:00"},
        "enabled": False,
    },
    {
        "task_id": "watch_bills_folder",
        "name": "Auto-ingest bills folder",
        "instruction": "New file detected in bills folder. Process with Vision Pipeline and add to Brain Index.",
        "trigger": TriggerType.FILE_NEW,
        "trigger_cfg": {"folder": "data/imports/bills"},
        "enabled": False,
    },
    {
        "task_id": "monthly_supplier_analysis",
        "name": "Monthly supplier analysis",
        "instruction": "Run full supplier analysis. Cluster by spend, identify renegotiation targets, flag price changes.",
        "trigger": TriggerType.TIME_MONTHLY,
        "trigger_cfg": {"day": 1, "time": "09:00"},
        "enabled": False,
    },
    {
        "task_id": "folder_organiser",
        "name": "Auto-organise downloads",
        "instruction": "Sort Downloads folder: move PDFs to docs/, images to assets/, rename by date. Report changes.",
        "trigger": TriggerType.TIME_DAILY,
        "trigger_cfg": {"time": "18:00"},
        "enabled": False,
    },
]


class Scheduler:
    """Manages scheduled and trigger-based tasks."""

    def __init__(self, dispatcher, settings=None):
        self.dispatcher = dispatcher
        self.settings = settings
        self._tasks: Dict[str, ScheduledTask] = {}
        self._file_watch: Dict[str, float] = {}
        self._active = True
        self._log_path = Path("logs/scheduler.jsonl")
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path = Path("config/scheduler_state.json")
        self._load_state()
        self._register_builtins()

    def _register_builtins(self):
        for cfg in BUILT_IN_SCHEDULES:
            if cfg["task_id"] not in self._tasks:
                self._tasks[cfg["task_id"]] = ScheduledTask(**cfg)
        self._save_state()

    def add(
        self,
        task_id: str,
        name: str,
        instruction: str,
        trigger: TriggerType,
        trigger_cfg: Dict = None,
        enabled: bool = True,
    ) -> ScheduledTask:
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            instruction=instruction,
            trigger=trigger,
            trigger_cfg=trigger_cfg or {},
            enabled=enabled,
        )
        self._tasks[task_id] = task
        self._save_state()
        self._log(task_id, "added")
        return task

    def enable(self, task_id: str):
        if task_id in self._tasks:
            self._tasks[task_id].enabled = True
            self._save_state()

    def disable(self, task_id: str):
        if task_id in self._tasks:
            self._tasks[task_id].enabled = False
            self._save_state()

    def run_now(self, task_id: str) -> Optional[str]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        dispatch_task = self.dispatcher.submit(
            instruction=task.instruction,
            source="scheduler_manual",
        )
        task.last_run = datetime.now(UTC).isoformat()
        task.run_count += 1
        self._save_state()
        return dispatch_task.task_id

    def list_tasks(self) -> List[Dict]:
        return [
            {
                "task_id": t.task_id,
                "name": t.name,
                "trigger": t.trigger.value,
                "trigger_cfg": t.trigger_cfg,
                "enabled": t.enabled,
                "last_run": t.last_run,
                "next_run": self._compute_next_run(t),
                "run_count": t.run_count,
            }
            for t in self._tasks.values()
        ]

    def delete(self, task_id: str):
        self._tasks.pop(task_id, None)
        self._save_state()

    def start(self):
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        print("[Scheduler] Started - checking every 60s")
        while self._active:
            now = datetime.now(UTC)
            for task in list(self._tasks.values()):
                if not task.enabled:
                    continue
                try:
                    if self._should_run(task, now):
                        print(f"[Scheduler] Triggering: {task.name}")
                        self._trigger(task)
                except Exception as e:
                    print(f"[Scheduler] Error checking {task.task_id}: {e}")
            time.sleep(60)

    def _should_run(self, task: ScheduledTask, now: datetime) -> bool:
        last = datetime.fromisoformat(task.last_run) if task.last_run else None
        cfg = task.trigger_cfg

        if task.trigger == TriggerType.TIME_DAILY:
            scheduled_time = cfg.get("time", "09:00")
            h, m = map(int, scheduled_time.split(":"))
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if now >= target and (last is None or last.date() < now.date()):
                return True

        elif task.trigger == TriggerType.TIME_WEEKLY:
            scheduled_time = cfg.get("time", "09:00")
            scheduled_days = cfg.get("days", ["monday"])
            day_names = [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ]
            if day_names[now.weekday()] in scheduled_days:
                h, m = map(int, scheduled_time.split(":"))
                target = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if now >= target and (last is None or last.date() < now.date()):
                    return True

        elif task.trigger == TriggerType.TIME_MONTHLY:
            scheduled_day = cfg.get("day", 1)
            scheduled_time = cfg.get("time", "09:00")
            if now.day == scheduled_day:
                h, m = map(int, scheduled_time.split(":"))
                target = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if now >= target and (
                    last is None or (last.year, last.month) < (now.year, now.month)
                ):
                    return True

        elif task.trigger == TriggerType.FILE_NEW:
            folder = Path(cfg.get("folder", "data/imports"))
            if folder.exists():
                current_mtime = max(
                    (f.stat().st_mtime for f in folder.iterdir() if f.is_file()),
                    default=0,
                )
                prev_mtime = self._file_watch.get(str(folder), 0)
                if current_mtime > prev_mtime:
                    self._file_watch[str(folder)] = current_mtime
                    return True

        return False

    def _trigger(self, task: ScheduledTask):
        self.dispatcher.submit(
            instruction=task.instruction,
            source=f"scheduler_{task.trigger.value}",
        )
        task.last_run = datetime.now(UTC).isoformat()
        task.run_count += 1
        self._save_state()
        self._log(task.task_id, "triggered")

    def _compute_next_run(self, task: ScheduledTask) -> Optional[str]:
        now = datetime.now(UTC)
        cfg = task.trigger_cfg
        if task.trigger == TriggerType.TIME_DAILY:
            h, m = map(int, cfg.get("time", "09:00").split(":"))
            candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if candidate <= now:
                candidate += timedelta(days=1)
            return candidate.isoformat()
        return None

    def _save_state(self):
        state = {}
        for tid, t in self._tasks.items():
            state[tid] = {
                "task_id": t.task_id,
                "name": t.name,
                "instruction": t.instruction,
                "trigger": t.trigger.value,
                "trigger_cfg": t.trigger_cfg,
                "enabled": t.enabled,
                "last_run": t.last_run,
                "run_count": t.run_count,
                "created_at": t.created_at,
            }
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(state, indent=2))

    def _load_state(self):
        if not self._state_path.exists():
            return
        try:
            state = json.loads(self._state_path.read_text())
            for tid, d in state.items():
                self._tasks[tid] = ScheduledTask(
                    task_id=d["task_id"],
                    name=d["name"],
                    instruction=d["instruction"],
                    trigger=TriggerType(d["trigger"]),
                    trigger_cfg=d.get("trigger_cfg", {}),
                    enabled=d.get("enabled", False),
                    last_run=d.get("last_run"),
                    run_count=d.get("run_count", 0),
                    created_at=d.get("created_at", datetime.now(UTC).isoformat()),
                )
        except Exception as e:
            print(f"[Scheduler] state load error: {e}")

    def _log(self, task_id: str, event: str):
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "task_id": task_id,
            "event": event,
        }
        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
