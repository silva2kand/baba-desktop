"""
src/ui/server.py — Baba Desktop v7
FastAPI server serving the full desktop UI + all real API endpoints.
"""

import json, asyncio
from pathlib import Path
from typing import Dict, Any

try:
    from fastapi import FastAPI, Request
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False


class UIServer:
    def __init__(self, services: Dict[str, Any]):
        self.services = services
        self.port = services["settings"].ui_port
        self.app  = self._build_app() if USE_FASTAPI else None

    def run(self):
        if USE_FASTAPI:
            print(f"\n  ✓ Open Baba Desktop: http://localhost:{self.port}/ui/")
            uvicorn.run(self.app, host="0.0.0.0", port=self.port, log_level="warning")
        else:
            print("  pip install fastapi uvicorn  then re-run")

    def _build_app(self):
        app = FastAPI(title="Baba Desktop v7 API")

        app.add_middleware(CORSMiddleware,
            allow_origins=["*"], allow_credentials=True,
            allow_methods=["*"], allow_headers=["*"])

        # Serve UI
        ui_dir = Path(__file__).parent / "static"
        if ui_dir.exists():
            app.mount("/ui", StaticFiles(directory=str(ui_dir), html=True), name="ui")

        @app.get("/")
        async def root():
            return {"status": "Baba Desktop v7 running", "ui": f"http://localhost:{self.port}/ui/"}

        # ── Chat ───────────────────────────────────────────────────────────
        @app.post("/api/chat")
        async def chat(req: Request):
            data     = await req.json()
            provider = data.get("provider", "ollama")
            model    = data.get("model", "qwen3.5:latest")
            messages = data.get("messages", [])
            system   = data.get("system", "")
            pool     = self.services["pool"]
            try:
                reply = await pool.chat(provider, model, messages, system=system)
                return JSONResponse({"ok": True, "reply": reply, "provider": provider, "model": model})
            except Exception as e:
                # Try fallback
                try:
                    reply, prov = await pool.chat_with_fallback(provider, model, messages, system=system)
                    return JSONResponse({"ok": True, "reply": reply, "provider": prov + " (fallback)", "model": model})
                except Exception as e2:
                    return JSONResponse({"ok": False, "error": str(e2)}, status_code=500)

        # ── Brain ──────────────────────────────────────────────────────────
        @app.get("/api/brain/stats")
        async def brain_stats():
            brain = self.services["brain"]
            return JSONResponse(brain.stats())

        @app.post("/api/brain/ingest")
        async def brain_ingest(req: Request):
            data  = await req.json()
            brain = self.services["brain"]
            item_id = brain.ingest(data)
            return JSONResponse({"ok": True, "id": item_id})

        @app.get("/api/brain/search")
        async def brain_search(q: str = ""):
            brain = self.services["brain"]
            items = brain.search(q)
            return JSONResponse({"ok": True, "items": items, "count": len(items)})

        # ── Agents ─────────────────────────────────────────────────────────
        @app.post("/api/agent/run")
        async def agent_run(req: Request):
            data     = await req.json()
            orch     = self.services["orchestrator"]
            agent_id = data.get("agent_id")
            task     = data.get("task")
            try:
                reply = await orch.run(agent_id, task)
                return JSONResponse({"ok": True, "reply": reply})
            except Exception as e:
                return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

        # ── Providers ──────────────────────────────────────────────────────
        @app.get("/api/providers/health")
        async def provider_health():
            pool   = self.services["pool"]
            status = pool.health_check_sync()
            return JSONResponse({"ok": True, "status": status})

        @app.get("/api/providers/detect")
        async def provider_detect():
            pool   = self.services["pool"]
            result = pool.detect_all()
            return JSONResponse({"ok": True, "providers": result})

        @app.get("/api/providers/models")
        async def provider_models(provider: str = "ollama"):
            pool   = self.services["pool"]
            models = pool.live_models(provider)
            return JSONResponse({"ok": True, "provider": provider, "models": models})

        # ── Claws ──────────────────────────────────────────────────────────
        @app.get("/api/claws")
        async def list_claws():
            claws = self.services["claws"]
            return JSONResponse({"ok": True, "claws": claws.list_all()})

        @app.post("/api/claws/install")
        async def install_claw(req: Request):
            data     = await req.json()
            claw_id  = data.get("claw_id")
            approved = data.get("approved", False)
            claws    = self.services["claws"]
            result   = claws.install(claw_id, approved=approved)
            return JSONResponse(result)

        # ── Vision ─────────────────────────────────────────────────────────
        @app.post("/api/vision/analyse")
        async def vision_analyse(req: Request):
            data   = await req.json()
            path   = data.get("path", "")
            b64    = data.get("data", "")   # base64 data URL from UI upload
            task   = data.get("task", "general")
            fname  = data.get("filename", "upload")
            vision = self.services["vision"]
            try:
                if b64:
                    result = await vision.analyse_b64(b64, fname, task)
                else:
                    result = await vision.analyse(path, task)
                return JSONResponse({"ok": True, "result": result})
            except Exception as e:
                return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

        # ── PC Control ─────────────────────────────────────────────────────
        @app.post("/api/pc/action")
        async def pc_action(req: Request):
            data   = await req.json()
            action = data.get("action", "")
            param  = data.get("param", "")
            # All PC actions require approval (handled in UI) — proxy to bridge
            pc = self.services.get("pc")
            if pc:
                try:
                    result = await pc.execute(action, param)
                    return JSONResponse({"ok": True, "result": str(result)})
                except Exception as e:
                    return JSONResponse({"ok": False, "error": str(e)})
            return JSONResponse({"ok": False, "message": "PC bridge not running. Start: python run_pc_bridge.py"})

        # ── Scheduler ──────────────────────────────────────────────────────
        @app.get("/api/scheduler/list")
        async def scheduler_list():
            sched = self.services.get("scheduler")
            if sched:
                return JSONResponse({"ok": True, "schedules": sched.list_schedules()})
            return JSONResponse({"ok": False, "error": "Scheduler not running"})

        @app.post("/api/scheduler/toggle")
        async def scheduler_toggle(req: Request):
            data  = await req.json()
            sched = self.services.get("scheduler")
            if sched:
                sched.toggle(data.get("id"), data.get("enabled", True))
                return JSONResponse({"ok": True})
            return JSONResponse({"ok": False})

        # ── Memory ─────────────────────────────────────────────────────────
        @app.get("/api/memory/stats")
        async def memory_stats():
            mem = self.services.get("memory")
            if mem:
                return JSONResponse({"ok": True, **mem.stats()})
            return JSONResponse({"ok": False, "error": "Memory not running"})

        # ── Dispatch ───────────────────────────────────────────────────────
        @app.post("/api/dispatch/task")
        async def dispatch_task(req: Request):
            data = await req.json()
            disp = self.services.get("dispatcher")
            if disp:
                task_id = await disp.submit(data)
                return JSONResponse({"ok": True, "task_id": task_id})
            return JSONResponse({"ok": False})

        # ── Cowork ─────────────────────────────────────────────────────────
        @app.post("/api/cowork/run")
        async def cowork_run(req: Request):
            data  = await req.json()
            cw    = self.services.get("cowork")
            goal  = data.get("goal", "")
            if cw:
                result = await cw.run(goal)
                return JSONResponse({"ok": True, "result": result})
            return JSONResponse({"ok": False, "error": "Cowork not running"})

        return app


if __name__ == "__main__":
    from config.settings import Settings
    from src.brain.index import BrainIndex
    from src.providers.pool import ProviderPool
    from src.agents.orchestrator import AgentOrchestrator
    from src.vision.pipeline import VisionPipeline
    from src.tools.registry import ToolRegistry
    from src.claws.installer import ClawInstaller

    settings = Settings.load()
    brain    = BrainIndex(settings.brain_db_path)
    pool     = ProviderPool(settings.providers)
    tools    = ToolRegistry()
    vision   = VisionPipeline(pool)
    claws    = ClawInstaller(settings.claws_dir)
    orch     = AgentOrchestrator(pool, brain, tools, vision)

    services = {
        "settings": settings, "brain": brain, "pool": pool,
        "tools": tools, "vision": vision, "claws": claws,
        "orchestrator": orch,
    }
    UIServer(services).run()
