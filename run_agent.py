#!/usr/bin/env python3
"""
run_agent.py — Run any domain agent from the command line.

Usage:
    python run_agent.py legal "Find all unresolved legal issues"
    python run_agent.py acct  "Tag all recurring bills"
    python run_agent.py supplier "Find renegotiation targets"
    python run_agent.py deals  "Find empty premises"
    python run_agent.py money  (runs full money engine)
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
from src.agents.orchestrator import AgentOrchestrator, MoneyEngine, AGENTS


async def main():
    if len(sys.argv) < 2:
        print("Usage: python run_agent.py <agent_id> [task]")
        print("Agents:", ", ".join(AGENTS.keys()))
        sys.exit(1)

    agent_id = sys.argv[1]
    task     = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None

    settings = Settings.load()
    brain    = BrainIndex(settings.brain_db_path)
    pool     = ProviderPool(settings.providers)
    tools    = ToolRegistry()
    vision   = VisionPipeline(pool, brain, settings)
    orch     = AgentOrchestrator(pool, brain, tools, vision)

    if agent_id == "money":
        engine = MoneyEngine(brain, pool)
        print("\n[Money Engine] Running full analysis…\n")
        result = await engine.full_analysis()
        print(result["analysis"])
        return

    agent = AGENTS.get(agent_id)
    if not agent:
        print(f"Unknown agent: {agent_id}")
        print("Available:", ", ".join(AGENTS.keys()))
        sys.exit(1)

    if not task:
        print(f"\n{agent['name']} — available tasks:")
        for i, t in enumerate(agent["tasks"], 1):
            print(f"  {i}. {t}")
        try:
            choice = int(input("\nChoose task number: ")) - 1
            task   = agent["tasks"][choice]
        except (ValueError, IndexError, KeyboardInterrupt):
            print("Cancelled")
            sys.exit(0)

    print(f"\n[{agent['name']}] Running: {task}\n")
    print("-" * 60)

    result = await orch.run(agent_id, task)
    print(result)
    print("\n" + "-" * 60)
    print("All recommended actions require your approval before execution.")


if __name__ == "__main__":
    asyncio.run(main())
