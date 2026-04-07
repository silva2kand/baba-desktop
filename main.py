"""Baba Desktop v9 — Business Brain OS ULTIMATE MERGED EDITION"""

import sys
import os
import argparse
import threading
import socket
from pathlib import Path

APP_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(APP_DIR))


def _port_available(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def main():
    # Always run relative paths from the app root, regardless of caller cwd.
    os.chdir(APP_DIR)

    parser = argparse.ArgumentParser(description="Baba Desktop v9 — Business Brain OS")
    parser.add_argument(
        "--ui",
        choices=["tkinter", "v13", "safe-shell"],
        default="tkinter",
        help="UI mode (tkinter = merged native desktop, v13 = legacy v13 interface, safe-shell = UI-only shell remap)",
    )
    parser.add_argument(
        "--no-backend", action="store_true", help="Skip backend service startup"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Baba Desktop v9 — Business Brain OS")
    print("  ULTIMATE MERGED EDITION")
    print("=" * 60)

    if not args.no_backend:
        print("\n  Starting backend services...")
        try:
            from config.settings import Settings

            settings = Settings.load()
            print("    [OK] Settings loaded")

            from src.brain.index import BrainIndex

            brain = BrainIndex(settings.brain_db_path)
            stats = brain.stats()
            print(f"    [OK] Brain Index: {stats.get('total', 0)} items")

            from src.providers.pool import ProviderPool

            pool = ProviderPool(settings.providers)
            print("    [OK] Provider pool created (7 providers)")

            from src.tools.registry import ToolRegistry

            tools = ToolRegistry(brain)
            print(f"    [OK] Tool registry: {len(tools.all())} tools")

            from src.vision.pipeline import VisionPipeline

            vision = VisionPipeline(pool, brain, settings)
            print("    [OK] Vision pipeline ready")

            from src.agents.orchestrator import AgentOrchestrator, MoneyEngine

            agents = AgentOrchestrator(pool, brain, tools)
            money = MoneyEngine(brain, pool)
            print("    [OK] Agents + Money Engine ready")

            from src.pc_bridge.bridge import PCBridge

            pc = None
            if _port_available(settings.pc_bridge_port):
                pc = PCBridge(port=settings.pc_bridge_port, safe_mode=True)
                pc_thread = threading.Thread(target=pc.serve, daemon=True)
                pc_thread.start()
                print(f"    [OK] PC Bridge on port {settings.pc_bridge_port}")
            else:
                print(
                    f"    [WARN] PC Bridge port {settings.pc_bridge_port} already in use; "
                    "reusing existing service"
                )

            from src.app_bridge.bridge import AppBridge

            apps = AppBridge(settings)
            print("    [OK] App Bridge ready")

            from src.memory.memory import Memory

            memory = Memory(settings.memory_dir)
            print("    [OK] Memory system ready")

            from src.dispatch.dispatcher import Dispatcher

            dispatcher = Dispatcher(brain, agents, pc, apps, tools, pool)
            disp_thread = threading.Thread(target=dispatcher.start_worker, daemon=True)
            disp_thread.start()
            print("    [OK] Dispatcher worker started")

            from src.scheduler.scheduler import Scheduler

            scheduler = Scheduler(dispatcher, settings)
            sched_thread = threading.Thread(target=scheduler.start, daemon=True)
            sched_thread.start()
            print("    [OK] Scheduler loop started")

            from src.cowork.cowork import Cowork

            cowork = Cowork(agents, pool, brain, tools, pc, apps)
            print("    [OK] Cowork system ready")

            from src.devtools.devtools import DevTools

            devtools = DevTools()
            print("    [OK] DevTools ready")

            from src.meetings.intelligence import MeetingIntelligence

            meetings = MeetingIntelligence(pool, brain, settings)
            print("    [OK] Meeting Intelligence ready")

            from src.chrome.connector import ChromeConnector

            chrome = ChromeConnector(dispatcher, brain, pool)
            if _port_available(8768):
                chrome_thread = threading.Thread(target=chrome.start, daemon=True)
                chrome_thread.start()
                print(f"    [OK] Chrome Connector on port 8768")
            else:
                print(
                    "    [WARN] Chrome Connector port 8768 already in use; "
                    "reusing existing service"
                )

            from src.claws.installer import ClawInstaller

            claws = ClawInstaller(settings.claws_dir)
            print("    [OK] Claw installer ready")

            from src.tools_experimental.builder import ToolBuilder

            tool_builder = ToolBuilder(pool, brain, settings, memory)
            print("    [OK] Tool Builder ready")

            print("\n  All backend services started!")

        except Exception as e:
            print(f"  [WARN] Backend init warning: {e}")
            import traceback

            traceback.print_exc()
            print("  Continuing with GUI-only mode...")

    print(f"\n  Launching {args.ui} UI...")

    try:
        if args.ui == "v13":
            from baba_gui_v13 import BabaGuiV13

            app = BabaGuiV13()
        elif args.ui == "safe-shell":
            from baba_gui_v13_safe_shell import BabaGuiV13SafeShell

            app = BabaGuiV13SafeShell()
        else:
            from baba_desktop import BabaDesktop

            app = BabaDesktop()
        app.mainloop()
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback

        traceback.print_exc()
        input("\n  Press Enter to exit...")


if __name__ == "__main__":
    main()
