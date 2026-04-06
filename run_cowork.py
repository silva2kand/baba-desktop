#!/usr/bin/env python3
"""
run_cowork.py — Run a Cowork autonomous task from the command line.

Usage:
    python run_cowork.py "Download all invoices from the last month and create a summary report"
    python run_cowork.py "Read WhatsApp chats and extract all pending tasks"
    python run_cowork.py "Organise my Downloads folder by file type"
    python run_cowork.py "Check all supplier emails and find renegotiation opportunities"
    python run_cowork.py --list   (show recent sessions)
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings
from src.brain.index import BrainIndex
from src.providers.pool import ProviderPool
from src.tools.registry import ToolRegistry
from src.vision.pipeline import VisionPipeline
from src.pc_bridge.bridge import PCBridge
from src.app_bridge.bridge import AppBridge
from src.cowork.cowork import Cowork


def progress_cb(session_data: dict, event: str):
    status = session_data.get("status", "")
    plan   = session_data.get("plan", [])
    if event == "plan_ready":
        print(f"\n  Plan ({len(plan)} steps):")
        for s in plan:
            approval = " [APPROVAL REQUIRED]" if s.get("requires_approval") else ""
            print(f"    {s['name']}{approval}")
        print()
    elif event.startswith("step_") and event.endswith("_started"):
        step_i = int(event.split("_")[1])
        if step_i < len(plan):
            print(f"  ▶ {plan[step_i]['name']}...", end=" ", flush=True)
    elif event.startswith("step_") and event.endswith("_done"):
        print("✓")
    elif event.startswith("step_") and event.endswith("_failed"):
        print("✗")
    elif event == "needs_approval":
        pending = session_data.get("pending_approvals", [])
        if pending:
            pa = pending[-1]
            print(f"\n  ⚠️  APPROVAL REQUIRED: {pa['step']}")


async def main():
    if "--list" in sys.argv:
        # Show recent sessions (would need persistence)
        print("No saved sessions yet — run a task first")
        return

    if len(sys.argv) < 2:
        print("Usage: python run_cowork.py \"<goal>\"")
        print("Example goals:")
        print('  "Check my inbox and summarise unread emails"')
        print('  "Find all overdue invoices and draft chasers"')
        print('  "Organise Downloads folder by file type"')
        print('  "Analyse all suppliers and find savings"')
        sys.exit(0)

    goal = " ".join(sys.argv[1:])
    if goal.startswith('"') and goal.endswith('"'):
        goal = goal[1:-1]

    print(f"\n  Cowork — Autonomous Agent")
    print(f"  Goal: {goal}")
    print(f"  {'─'*60}")

    settings     = Settings.load()
    brain        = BrainIndex(settings.brain_db_path)
    pool         = ProviderPool(settings.providers)
    tools        = ToolRegistry()
    vision       = VisionPipeline(pool)
    pc           = PCBridge(settings.pc_bridge_port)
    apps         = AppBridge()
    cowork       = Cowork(pool, brain, tools, vision, pc, apps)

    cowork.subscribe_progress(progress_cb)

    print("\n  Generating plan...\n")
    session = await cowork.run(goal, auto_approve_safe=True)

    print(f"\n  {'─'*60}")
    print(f"  Status: {session.status}")
    print(f"\n  Result:\n{session.final_result}")

    if session.artifacts:
        print(f"\n  Artifacts saved:")
        for a in session.artifacts:
            print(f"    {a}")

    if session.pending_approvals:
        unapproved = [p for p in session.pending_approvals if p.get("approved") is None]
        if unapproved:
            print(f"\n  ⚠️  {len(unapproved)} actions waiting approval:")
            for p in unapproved:
                print(f"    • {p['step']}")
            print("  Open the UI to review and approve.")


if __name__ == "__main__":
    asyncio.run(main())
