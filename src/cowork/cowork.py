"""
src/cowork/cowork.py
Cowork - Autonomous Agent Mode.
"""

import asyncio
import json
import uuid
from pathlib import Path
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class CoworkStep:
    name: str
    action_type: str
    params: Dict = field(default_factory=dict)
    status: str = "pending"
    result: str = ""
    retries: int = 0
    requires_approval: bool = False


@dataclass
class CoworkSession:
    session_id: str
    goal: str
    plan: List[CoworkStep] = field(default_factory=list)
    status: str = "planning"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: Optional[str] = None
    final_result: str = ""
    pending_approvals: List[Dict] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    context: Dict = field(default_factory=dict)


class Cowork:
    """Autonomous agent mode - completes work without step-by-step prompting."""

    MAX_RETRIES = 3
    MAX_STEPS = 20

    def __init__(self, orchestrator, pool, brain, tools, pc_bridge, app_bridge):
        self.orchestrator = orchestrator
        self.pool = pool
        self.brain = brain
        self.tools = tools
        self.pc = pc_bridge
        self.apps = app_bridge
        self._sessions: Dict[str, CoworkSession] = {}
        self._progress_cbs: List[Callable] = []
        self._log_path = Path("logs/cowork.jsonl")
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def subscribe_progress(self, cb: Callable):
        self._progress_cbs.append(cb)

    async def run(
        self, goal: str, context: Dict = None, auto_approve_safe: bool = True
    ) -> CoworkSession:
        session = CoworkSession(
            session_id=str(uuid.uuid4())[:8],
            goal=goal,
            context=context or {},
        )
        self._sessions[session.session_id] = session
        self._emit(session, "session_started")

        session.status = "planning"
        plan = await self._generate_plan(goal, context or {})
        session.plan = plan
        self._emit(session, "plan_ready")
        self._log(session, "plan_ready")

        session.status = "running"
        await self._execute_plan(session, auto_approve_safe)

        if session.status == "running":
            session.final_result = await self._generate_summary(session)
            session.status = "completed"
            session.completed_at = datetime.now(UTC).isoformat()

        self._emit(session, session.status)
        self._log(session, session.status)
        return session

    def run_sync(self, goal: str, context: Dict = None) -> CoworkSession:
        return asyncio.run(self.run(goal, context))

    def get_session(self, session_id: str) -> Optional[Dict]:
        s = self._sessions.get(session_id)
        return self._session_to_dict(s) if s else None

    def list_sessions(self, limit: int = 20) -> List[Dict]:
        sessions = sorted(
            self._sessions.values(), key=lambda s: s.created_at, reverse=True
        )
        return [self._session_to_dict(s) for s in sessions[:limit]]

    def abort(self, session_id: str):
        s = self._sessions.get(session_id)
        if s and s.status == "running":
            s.status = "aborted"

    def approve_action(self, session_id: str, approval_id: str, approved: bool):
        s = self._sessions.get(session_id)
        if not s:
            return
        for i, pa in enumerate(s.pending_approvals):
            if pa.get("id") == approval_id:
                pa["approved"] = approved
                pa["decided_at"] = datetime.now(UTC).isoformat()
                break

    async def _generate_plan(self, goal: str, context: Dict) -> List[CoworkStep]:
        brain_stats = self.brain.stats()
        prompt = f"""You are a planning agent. Create a step-by-step plan to achieve this goal.

GOAL: {goal}

AVAILABLE CAPABILITIES:
- brain_search: search Business Brain Index ({brain_stats["total"]} items indexed)
- web_fetch: fetch a URL
- web_search: search the web
- read_file / write_file: file operations
- shell_exec: run terminal commands
- vision_analyse: analyse images/PDFs
- outlook_read / outlook_draft: email operations
- whatsapp_open / whatsapp_send: WhatsApp
- pc_screenshot / pc_ocr: capture and read screen
- pc_click / pc_type / pc_hotkey: control mouse and keyboard
- agent_legal / agent_acct / agent_supplier / agent_deals / agent_content / agent_comms / agent_pa: domain agents

SAFETY RULES:
- Mark any step that sends/writes/posts/modifies as requires_approval=true
- Never move money, sign documents, or install software
- Max {self.MAX_STEPS} steps

Return a JSON array of steps:
[{{"name": "step name", "action_type": "tool|agent|pc|app|vision|draft|approve|report",
  "params": {{}}, "requires_approval": false}}]
Return ONLY the JSON array, no explanation."""

        messages = [{"role": "user", "content": prompt}]
        try:
            reply = await self.pool.chat(
                "groq", "llama-3.3-70b-versatile", messages, max_tokens=1500
            )
        except Exception:
            reply = await self._fallback_plan(goal)

        steps = self._parse_plan(reply, goal)
        return steps

    def _parse_plan(self, reply: str, goal: str) -> List[CoworkStep]:
        import re

        try:
            m = re.search(r"\[[\s\S]+\]", reply)
            if m:
                raw = json.loads(m.group())
                steps = []
                for s in raw[: self.MAX_STEPS]:
                    steps.append(
                        CoworkStep(
                            name=s.get("name", "Step"),
                            action_type=s.get("action_type", "tool"),
                            params=s.get("params", {}),
                            requires_approval=s.get("requires_approval", False),
                        )
                    )
                return steps
        except Exception:
            pass
        return [
            CoworkStep("Analyse goal", "agent", {"agent": "pa", "task": goal}),
            CoworkStep(
                "Execute primary", "tool", {"tool": "brain_search", "query": goal}
            ),
            CoworkStep("Generate report", "report", {}),
        ]

    async def _fallback_plan(self, goal: str) -> str:
        g = goal.lower()
        if "email" in g:
            return (
                '[{"name":"Read inbox","action_type":"app","params":{"app":"outlook","action":"read_inbox"}},{"name":"Process","action_type":"agent","params":{"agent":"comms","task":"'
                + goal
                + '"}},{"name":"Draft reply","action_type":"draft","params":{},"requires_approval":true}]'
            )
        if "whatsapp" in g:
            return (
                '[{"name":"Open WhatsApp","action_type":"app","params":{"app":"whatsapp","action":"open"}},{"name":"Analyse","action_type":"agent","params":{"agent":"comms","task":"'
                + goal
                + '"}}]'
            )
        if "file" in g:
            return '[{"name":"Search files","action_type":"tool","params":{"tool":"list_dir","path":"."}},{"name":"Process","action_type":"tool","params":{"tool":"shell_exec","command":"ls"}},{"name":"Report","action_type":"report","params":{}}]'
        return (
            '[{"name":"Research","action_type":"tool","params":{"tool":"brain_search","query":"'
            + goal
            + '"}},{"name":"Analyse","action_type":"agent","params":{"agent":"pa","task":"'
            + goal
            + '"}},{"name":"Report","action_type":"report","params":{}}]'
        )

    async def _execute_plan(self, session: CoworkSession, auto_approve_safe: bool):
        for i, step in enumerate(session.plan):
            if session.status in ("aborted", "failed"):
                break

            step.status = "running"
            self._emit(session, f"step_{i}_started")

            if step.requires_approval and not auto_approve_safe:
                step.status = "needs_approval"
                approval = {
                    "id": f"appr_{i}",
                    "step": step.name,
                    "params": step.params,
                    "approved": None,
                }
                session.pending_approvals.append(approval)
                self._emit(session, "needs_approval")

                for _ in range(300):
                    if approval.get("approved") is not None:
                        break
                    await asyncio.sleep(1)

                if not approval.get("approved"):
                    step.status = "skipped"
                    step.result = "Skipped - approval denied or timed out"
                    continue

            for attempt in range(self.MAX_RETRIES):
                try:
                    result = await self._execute_step(step, session)
                    step.result = result[:300] if result else "Done"
                    step.status = "done"
                    break
                except Exception as e:
                    step.retries += 1
                    if attempt < self.MAX_RETRIES - 1:
                        await asyncio.sleep(2**attempt)
                    else:
                        step.status = "failed"
                        step.result = f"Failed after {self.MAX_RETRIES} attempts: {e}"

            self._emit(session, f"step_{i}_{step.status}")
            await asyncio.sleep(0.1)

    async def _execute_step(self, step: CoworkStep, session: CoworkSession) -> str:
        at = step.action_type
        p = step.params

        if at == "tool":
            tool_name = p.get("tool", "brain_search")
            try:
                kwargs = {k: v for k, v in p.items() if k != "tool"}
                result = self.tools.run(tool_name, **kwargs)
                return str(result)[:300]
            except Exception as e:
                return f"Tool {tool_name} error: {e}"

        elif at == "agent":
            task = p.get("task", session.goal)
            ag = p.get("agent", "pa")
            reply = await self.orchestrator.run(ag, task)
            return reply[:300]

        elif at == "pc":
            action = p.get("action", "screenshot")
            action_aliases = {
                "ocr": "ocr_screen",
                "screen_ocr": "ocr_screen",
                "process": "run_process",
                "open_app": "run_process",
            }
            action = action_aliases.get(action, action)
            try:
                result = await self.pc.execute({"action": action, **p})
                return str(result)[:300]
            except Exception as e:
                return f"PC action {action} skipped (bridge needed): {e}"

        elif at == "app":
            app_id = p.get("app", "chrome")
            action = p.get("action", "open")
            method = getattr(self.apps, f"{app_id}_{action}", None)
            if method:
                result = method(
                    **{k: v for k, v in p.items() if k not in ("app", "action")}
                )
                return str(result)[:300]
            return f"App action unavailable: {app_id}.{action}"

        elif at == "vision":
            path = p.get("path", "")
            task = p.get("task", "general")
            if path:
                result = await self.vision.analyse(path, task)
                return json.dumps(result)[:300]
            return "Vision: no path provided"

        elif at == "draft":
            content = p.get("content", session.goal)
            draft_path = Path(f"data/exports/cowork_draft_{session.session_id}.txt")
            draft_path.parent.mkdir(parents=True, exist_ok=True)
            draft_path.write_text(f"DRAFT (requires approval):\n\n{content}")
            session.artifacts.append(str(draft_path))
            return f"Draft saved to {draft_path} - awaiting approval"

        elif at == "report":
            return f"Report generated for: {session.goal[:60]}"

        return "Step completed"

    async def _generate_summary(self, session: CoworkSession) -> str:
        done = [s for s in session.plan if s.status == "done"]
        failed = [s for s in session.plan if s.status == "failed"]
        pending = [s for s in session.plan if s.status == "needs_approval"]

        summary = f"**Cowork Complete: {session.goal[:60]}**\n\n"
        summary += f"Steps: {len(done)} done"
        if failed:
            summary += f" - {len(failed)} failed"
        if pending:
            summary += f" - {len(pending)} awaiting approval"
        summary += "\n\n"

        if done:
            summary += "**Completed:**\n"
            for s in done[:5]:
                summary += f"  - {s.name}\n"
        if failed:
            summary += "\n**Failed:**\n"
            for s in failed:
                summary += f"  X {s.name}: {s.result[:60]}\n"
        if pending:
            summary += "\n**Awaiting your approval:**\n"
            for s in pending:
                summary += f"  ! {s.name}\n"
        if session.artifacts:
            summary += f"\n**Artifacts saved:** {len(session.artifacts)} files"

        return summary

    def _emit(self, session: CoworkSession, event: str):
        data = self._session_to_dict(session)
        for cb in self._progress_cbs:
            try:
                cb(data, event)
            except Exception:
                pass

    def _session_to_dict(self, session: CoworkSession) -> Dict:
        return {
            "session_id": session.session_id,
            "goal": session.goal,
            "status": session.status,
            "created_at": session.created_at,
            "completed_at": session.completed_at,
            "final_result": session.final_result,
            "plan": [
                {
                    "name": s.name,
                    "action_type": s.action_type,
                    "status": s.status,
                    "result": s.result[:100],
                    "requires_approval": s.requires_approval,
                }
                for s in session.plan
            ],
            "pending_approvals": session.pending_approvals,
            "artifacts": session.artifacts,
        }

    def _log(self, session: CoworkSession, event: str):
        entry = {
            "event": event,
            "ts": datetime.now(UTC).isoformat(),
            "session_id": session.session_id,
            "goal": session.goal[:60],
            "status": session.status,
        }
        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
