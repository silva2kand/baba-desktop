"""Baba Desktop v9 — Business Brain OS ULTIMATE MERGED EDITION"""

import sys
import os
import argparse
import threading
import socket
import time
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
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run backend services only (no desktop UI window)",
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
            try:
                print(f"    [OK] OAuth redirect: {settings.get_localhost_redirect_uri()}")
            except Exception:
                pass

            from src.brain.index import BrainIndex

            brain = BrainIndex(settings.brain_db_path)
            stats = brain.stats()
            print(f"    [OK] Brain Index: {stats.get('total', 0)} items")

            from src.providers.pool import ProviderPool
            from src.memory.memory import load_master_memory_text, ensure_master_memory_file

            ensure_master_memory_file("data/baba_master_memory.txt")
            master_memory = load_master_memory_text("data/baba_master_memory.txt")
            pool = ProviderPool(
                settings.providers,
                master_memory_text=master_memory,
                master_memory_path="data/baba_master_memory.txt",
            )
            print("    [OK] Provider pool created (7 providers)")

            from src.tools.registry import ToolRegistry

            tools = ToolRegistry(brain)
            runtime_count = len(getattr(tools, "_runtime_tool_names", []))
            print(
                f"    [OK] Tool registry: {len(tools.all())} tools "
                f"({runtime_count} runtime)"
            )

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
            try:
                oauth_status = apps.outlook_oauth_status()
                print(
                    "    [OK] Outlook OAuth: "
                    f"{'connected' if oauth_status.get('connected') else 'not connected'} "
                    f"(redirect {oauth_status.get('redirect_uri', '')})"
                )
            except Exception:
                pass

            from src.memory.memory import Memory

            memory = Memory(settings.memory_dir)
            print("    [OK] Memory system ready")

            from src.dispatch.dispatcher import Dispatcher

            dispatcher = Dispatcher(brain, agents, pc, apps, tools, pool)
            disp_thread = threading.Thread(target=dispatcher.start_worker, daemon=True)
            disp_thread.start()
            print("    [OK] Dispatcher worker started")

            from src.sentinel.sentinel import Sentinel

            def _on_sentinel_event(task):
                event_type = str(task.get("event_type", "")).strip()
                payload = task.get("payload", {}) or {}
                priority = 4 if str(task.get("priority", "normal")) == "high" else 5
                instruction = "Analyze sentinel event and suggest next actions."
                if event_type == "hotkey_context":
                    instruction = "Analyze hotkey context from active window and clipboard."
                elif event_type == "file_event":
                    instruction = f"Analyze watched file event for path: {payload.get('path', '')}"
                elif event_type == "clipboard_signal":
                    instruction = "Analyze clipboard signal and propose actions."
                queued = dispatcher.submit(
                    instruction=instruction,
                    source=f"sentinel_{task.get('source', 'sentinel')}",
                    context={"sentinel_task": task},
                    priority=priority,
                )
                return {"accepted": True, "queued_task_id": queued.task_id}

            sentinel = Sentinel(pc_bridge=pc, on_event=_on_sentinel_event)
            sentinel.start()
            print("    [OK] Sentinel ready")

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

            # Start unified UI/API server with the same live backend services
            # so context-menu, sentinel, auth, and dispatch share one runtime.
            if _port_available(settings.ui_port):
                try:
                    from src.ui.server import UIServer

                    services = {
                        "settings": settings,
                        "brain": brain,
                        "pool": pool,
                        "tools": tools,
                        "vision": vision,
                        "claws": claws,
                        "orchestrator": agents,
                        "memory": memory,
                        "tool_builder": tool_builder,
                        "apps": apps,
                        "dispatcher": dispatcher,
                        "scheduler": scheduler,
                        "cowork": cowork,
                        "pc": pc,
                        "sentinel": sentinel,
                    }
                    ui_server = UIServer(services)
                    ui_thread = threading.Thread(target=ui_server.run, daemon=True)
                    ui_thread.start()
                    print(f"    [OK] UI/API server on port {settings.ui_port}")
                except Exception as e:
                    print(f"    [WARN] UI/API server start failed: {e}")
            else:
                print(
                    f"    [WARN] UI/API port {settings.ui_port} already in use; "
                    "reusing existing service"
                )

            print("\n  All backend services started!")

        except Exception as e:
            print(f"  [WARN] Backend init warning: {e}")
            import traceback

            traceback.print_exc()
            print("  Continuing with GUI-only mode...")

    if args.headless:
        if args.no_backend:
            print("\n  Headless mode + --no-backend: nothing to run.")
            return
        print("\n  Headless mode active: backend services running, desktop UI disabled.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\n  Stopping headless backend...")
        return

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
