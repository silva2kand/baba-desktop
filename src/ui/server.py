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

try:
    from src.tools_experimental.builder import ToolBuilder
except Exception:
    ToolBuilder = None


class UIServer:
    def __init__(self, services: Dict[str, Any]):
        self.services = services
        self.port = services["settings"].ui_port
        self.app  = self._build_app() if USE_FASTAPI else None

    def run(self):
        if USE_FASTAPI:
            print(f"\n  [OK] Open Baba Desktop: http://localhost:{self.port}/ui/")
            uvicorn.run(self.app, host="0.0.0.0", port=self.port, log_level="warning")
        else:
            print("  pip install fastapi uvicorn  then re-run")

    def _build_app(self):
        app = FastAPI(title="Baba Desktop v7 API")

        app.add_middleware(CORSMiddleware,
            allow_origins=["*"], allow_credentials=True,
            allow_methods=["*"], allow_headers=["*"])

        def get_tool_builder():
            builder = self.services.get("tool_builder")
            if builder:
                return builder
            if ToolBuilder is None:
                return None
            pool = self.services.get("pool")
            if not pool:
                return None
            try:
                builder = ToolBuilder(
                    pool,
                    self.services.get("brain"),
                    self.services.get("settings"),
                    self.services.get("memory"),
                )
                self.services["tool_builder"] = builder
                return builder
            except Exception:
                return None

        # Serve UI
        ui_dir = Path(__file__).parent / "static"
        if ui_dir.exists():
            app.mount("/ui", StaticFiles(directory=str(ui_dir), html=True), name="ui")

        @app.get("/")
        async def root():
            return {"status": "Baba Desktop v7 running", "ui": f"http://localhost:{self.port}/ui/"}

        @app.get("/oauth/callback", response_class=HTMLResponse)
        async def oauth_callback(req: Request):
            qp = req.query_params
            code = qp.get("code", "")
            state = qp.get("state", "")
            error = qp.get("error", "")
            apps = self.services.get("apps")
            if error:
                return HTMLResponse(
                    f"""
                    <html><body style="font-family:Segoe UI,Arial;padding:24px;background:#111;color:#eee;">
                    <h2>Baba OAuth Callback</h2>
                    <p>OAuth returned an error.</p>
                    <pre style="background:#1b1b1b;padding:12px;border-radius:8px;">error={error}</pre>
                    <p>You can close this tab and return to Baba Desktop.</p>
                    </body></html>
                    """,
                    status_code=400,
                )

            if code and apps and hasattr(apps, "outlook_oauth_exchange"):
                exchange = apps.outlook_oauth_exchange(code=code, state=state)
                if exchange.get("ok"):
                    return HTMLResponse(
                        """
                        <html><body style="font-family:Segoe UI,Arial;padding:24px;background:#111;color:#eee;">
                        <h2>Baba OAuth Connected</h2>
                        <p>Microsoft account connected successfully.</p>
                        <p>You can close this tab and return to Baba Desktop.</p>
                        </body></html>
                        """
                    )
                return HTMLResponse(
                    f"""
                    <html><body style="font-family:Segoe UI,Arial;padding:24px;background:#111;color:#eee;">
                    <h2>Baba OAuth Exchange Failed</h2>
                    <pre style="background:#1b1b1b;padding:12px;border-radius:8px;">{exchange.get('error', 'Unknown error')}</pre>
                    <p>You can close this tab and retry from Baba Desktop.</p>
                    </body></html>
                    """,
                    status_code=400,
                )

            return HTMLResponse(
                f"""
                <html><body style="font-family:Segoe UI,Arial;padding:24px;background:#111;color:#eee;">
                <h2>Baba OAuth Callback Received</h2>
                <p>Authorization response captured on localhost.</p>
                <pre style="background:#1b1b1b;padding:12px;border-radius:8px;">code={code}\nstate={state}</pre>
                <p>You can close this tab and return to Baba Desktop.</p>
                </body></html>
                """
            )

        @app.get("/api/auth/redirect_url")
        async def auth_redirect_url():
            settings = self.services.get("settings")
            configured = (
                settings.get_localhost_redirect_uri()
                if settings and hasattr(settings, "get_localhost_redirect_uri")
                else f"http://localhost:{self.port}/oauth/callback"
            )
            return JSONResponse(
                {
                    "ok": True,
                    "redirect_uri": configured,
                    "backup_redirect_uri": f"http://localhost:{self.port}/oauth/callback",
                }
            )

        @app.get("/api/auth/microsoft/status")
        async def auth_ms_status():
            apps = self.services.get("apps")
            if not apps or not hasattr(apps, "outlook_oauth_status"):
                return JSONResponse(
                    {"ok": False, "error": "App bridge not available"},
                    status_code=503,
                )
            return JSONResponse(apps.outlook_oauth_status())

        @app.post("/api/auth/microsoft/start")
        async def auth_ms_start(req: Request):
            apps = self.services.get("apps")
            if not apps or not hasattr(apps, "outlook_oauth_start"):
                return JSONResponse(
                    {"ok": False, "error": "App bridge not available"},
                    status_code=503,
                )
            try:
                data = await req.json()
            except Exception:
                data = {}
            open_browser = bool(data.get("open_browser", True))
            result = apps.outlook_oauth_start(open_browser=open_browser)
            code = 200 if result.get("ok") else 400
            return JSONResponse(result, status_code=code)

        @app.post("/api/auth/microsoft/exchange")
        async def auth_ms_exchange(req: Request):
            apps = self.services.get("apps")
            if not apps or not hasattr(apps, "outlook_oauth_exchange"):
                return JSONResponse(
                    {"ok": False, "error": "App bridge not available"},
                    status_code=503,
                )
            data = await req.json()
            code_value = str(data.get("code", "")).strip()
            state = str(data.get("state", "")).strip()
            if not code_value:
                return JSONResponse(
                    {"ok": False, "error": "code is required"},
                    status_code=400,
                )
            result = apps.outlook_oauth_exchange(code=code_value, state=state)
            status_code = 200 if result.get("ok") else 400
            return JSONResponse(result, status_code=status_code)

        @app.post("/api/auth/microsoft/disconnect")
        async def auth_ms_disconnect():
            apps = self.services.get("apps")
            if not apps or not hasattr(apps, "outlook_oauth_disconnect"):
                return JSONResponse(
                    {"ok": False, "error": "App bridge not available"},
                    status_code=503,
                )
            return JSONResponse(apps.outlook_oauth_disconnect())

        @app.get("/api/email/outlook/read")
        async def email_outlook_read(limit: int = 20, folder: str = "Inbox"):
            apps = self.services.get("apps")
            if not apps or not hasattr(apps, "outlook_read_inbox"):
                return JSONResponse(
                    {"ok": False, "error": "App bridge not available"},
                    status_code=503,
                )
            items = apps.outlook_read_inbox(limit=limit, folder=folder)
            return JSONResponse(
                {"ok": True, "items": items, "count": len(items), "folder": folder}
            )

        @app.post("/api/email/outlook/send")
        async def email_outlook_send(req: Request):
            apps = self.services.get("apps")
            if not apps or not hasattr(apps, "outlook_send"):
                return JSONResponse(
                    {"ok": False, "error": "App bridge not available"},
                    status_code=503,
                )
            data = await req.json()
            result = apps.outlook_send(
                to=str(data.get("to", "")).strip(),
                subject=str(data.get("subject", "")).strip(),
                body=str(data.get("body", "")),
                approved=bool(data.get("approved", False)),
            )
            status_code = 200 if result.get("ok") else 400
            return JSONResponse(result, status_code=status_code)

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

        @app.post("/api/context/ingest")
        async def context_ingest(req: Request):
            data = await req.json()
            brain = self.services["brain"]
            sentinel = self.services.get("sentinel")
            source = str(data.get("source", "context_menu")).strip() or "context_menu"
            kind = str(data.get("kind", "text")).strip().lower()
            path = str(data.get("path", "")).strip()
            text = str(data.get("text", "")).strip()
            url = str(data.get("url", "")).strip()
            note = str(data.get("note", "")).strip()
            dispatch_after = bool(data.get("dispatch", False))

            try:
                from src.brain.importers import EmailImporter, PDFImporter

                email_imp = EmailImporter()
                pdf_imp = PDFImporter()
            except Exception:
                email_imp = None
                pdf_imp = None

            item = None
            if path:
                p = Path(path)
                if not p.exists():
                    return JSONResponse(
                        {"ok": False, "error": f"Path not found: {path}"},
                        status_code=404,
                    )
                suffix = p.suffix.lower()
                if suffix == ".eml" and email_imp:
                    item = email_imp.import_file(str(p))
                elif suffix == ".pdf" and pdf_imp:
                    item = pdf_imp.import_file(str(p))
                else:
                    raw = p.read_text(encoding="utf-8", errors="ignore")[:8000]
                    full_text = f"{p.name}\n{raw}"
                    inferred_type = email_imp._classify(full_text) if email_imp else "personal"
                    tags = email_imp._extract_tags(full_text) if email_imp else []
                    item = {
                        "source": source,
                        "counterparty": p.parent.name,
                        "type": inferred_type,
                        "tags": tags + ["context_menu", "file"],
                        "summary": f"{p.name}: {full_text[:120]}",
                        "raw_path": str(p),
                        "raw_text": full_text,
                    }
            else:
                base = text or note or url
                if not base:
                    return JSONResponse(
                        {"ok": False, "error": "Provide one of path/text/url"},
                        status_code=400,
                    )
                full_text = f"{url}\n{text}\n{note}".strip()
                inferred_type = email_imp._classify(full_text) if email_imp else "personal"
                tags = email_imp._extract_tags(full_text) if email_imp else []
                item = {
                    "source": source,
                    "counterparty": "browser" if url else "desktop",
                    "type": inferred_type,
                    "tags": tags + (["web"] if url else ["text"]),
                    "summary": (full_text[:140] or "context item"),
                    "raw_path": url or None,
                    "raw_text": full_text[:8000],
                }

            item_id = brain.ingest(item)

            queued_task_id = ""
            if dispatch_after:
                dispatcher = self.services.get("dispatcher")
                if dispatcher:
                    dispatch_task = dispatcher.submit(
                        instruction=f"Analyse newly ingested context item {item_id} and suggest next actions",
                        source="context_ingest",
                        context={"item_id": item_id},
                        priority=4,
                    )
                    queued_task_id = dispatch_task.task_id

            sentinel_task_id = ""
            if sentinel and hasattr(sentinel, "push_event"):
                try:
                    ev = sentinel.push_event(
                        source=source,
                        event_type="context_ingest",
                        payload={
                            "item_id": item_id,
                            "path": path,
                            "text": text[:4000],
                            "url": url,
                            "note": note[:1000],
                            "kind": kind,
                        },
                        priority="normal",
                    )
                    sentinel_task_id = ev.get("id", "")
                except Exception:
                    pass

            return JSONResponse(
                {
                    "ok": True,
                    "item_id": item_id,
                    "type": item.get("type", ""),
                    "source": item.get("source", ""),
                    "queued_task_id": queued_task_id,
                    "sentinel_task_id": sentinel_task_id,
                }
            )

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

        @app.get("/api/sentinel/status")
        async def sentinel_status():
            sentinel = self.services.get("sentinel")
            if not sentinel:
                return JSONResponse(
                    {"ok": False, "error": "Sentinel not running"}, status_code=503
                )
            return JSONResponse(sentinel.status())

        @app.post("/api/sentinel/start")
        async def sentinel_start():
            sentinel = self.services.get("sentinel")
            if not sentinel:
                return JSONResponse(
                    {"ok": False, "error": "Sentinel not running"}, status_code=503
                )
            if not hasattr(sentinel, "start"):
                return JSONResponse(
                    {"ok": False, "error": "Sentinel start method unavailable"},
                    status_code=500,
                )
            return JSONResponse(sentinel.start())

        @app.post("/api/sentinel/stop")
        async def sentinel_stop():
            sentinel = self.services.get("sentinel")
            if not sentinel:
                return JSONResponse(
                    {"ok": False, "error": "Sentinel not running"}, status_code=503
                )
            if not hasattr(sentinel, "stop"):
                return JSONResponse(
                    {"ok": False, "error": "Sentinel stop method unavailable"},
                    status_code=500,
                )
            return JSONResponse(sentinel.stop())

        @app.post("/api/sentinel/enabled")
        async def sentinel_enabled(req: Request):
            sentinel = self.services.get("sentinel")
            if not sentinel:
                return JSONResponse(
                    {"ok": False, "error": "Sentinel not running"}, status_code=503
                )
            data = await req.json()
            enabled = bool(data.get("enabled", True))
            return JSONResponse(sentinel.set_enabled(enabled))

        @app.post("/api/sentinel/allow_screenshot")
        async def sentinel_allow_screenshot(req: Request):
            sentinel = self.services.get("sentinel")
            if not sentinel:
                return JSONResponse(
                    {"ok": False, "error": "Sentinel not running"}, status_code=503
                )
            data = await req.json()
            allow = bool(data.get("allow", False))
            if not hasattr(sentinel, "set_allow_screenshot"):
                return JSONResponse(
                    {"ok": False, "error": "Sentinel screenshot setting unavailable"},
                    status_code=500,
                )
            return JSONResponse(sentinel.set_allow_screenshot(allow))

        @app.post("/api/sentinel/watch_apps")
        async def sentinel_watch_apps(req: Request):
            sentinel = self.services.get("sentinel")
            if not sentinel:
                return JSONResponse(
                    {"ok": False, "error": "Sentinel not running"}, status_code=503
                )
            data = await req.json()
            apps = data.get("apps", [])
            return JSONResponse(sentinel.set_watch_apps(apps if isinstance(apps, list) else []))

        @app.post("/api/sentinel/watch_folders")
        async def sentinel_watch_folders(req: Request):
            sentinel = self.services.get("sentinel")
            if not sentinel:
                return JSONResponse(
                    {"ok": False, "error": "Sentinel not running"}, status_code=503
                )
            data = await req.json()
            folders = data.get("folders", [])
            return JSONResponse(
                sentinel.set_watch_folders(folders if isinstance(folders, list) else [])
            )

        @app.post("/api/sentinel/hotkey")
        async def sentinel_hotkey(req: Request):
            sentinel = self.services.get("sentinel")
            if not sentinel:
                return JSONResponse(
                    {"ok": False, "error": "Sentinel not running"}, status_code=503
                )
            data = await req.json()
            hotkey = str(data.get("hotkey", "")).strip()
            if not hotkey:
                return JSONResponse(
                    {"ok": False, "error": "hotkey is required"}, status_code=400
                )
            if not hasattr(sentinel, "set_hotkey"):
                return JSONResponse(
                    {"ok": False, "error": "Sentinel hotkey update unavailable"},
                    status_code=500,
                )
            return JSONResponse(sentinel.set_hotkey(hotkey))

        @app.post("/api/sentinel/clipboard_mode")
        async def sentinel_clipboard_mode(req: Request):
            sentinel = self.services.get("sentinel")
            if not sentinel:
                return JSONResponse(
                    {"ok": False, "error": "Sentinel not running"}, status_code=503
                )
            data = await req.json()
            mode = str(data.get("mode", "")).strip().lower()
            if not hasattr(sentinel, "set_clipboard_mode"):
                return JSONResponse(
                    {"ok": False, "error": "Sentinel clipboard mode update unavailable"},
                    status_code=500,
                )
            return JSONResponse(sentinel.set_clipboard_mode(mode))

        @app.post("/api/sentinel/capture")
        async def sentinel_capture(req: Request):
            sentinel = self.services.get("sentinel")
            if not sentinel:
                return JSONResponse(
                    {"ok": False, "error": "Sentinel not running"}, status_code=503
                )
            try:
                data = await req.json()
            except Exception:
                data = {}
            include_screenshot = bool(data.get("include_screenshot", False))
            captured = sentinel.capture_context(include_screenshot=include_screenshot)
            if not captured.get("ok"):
                return JSONResponse(captured, status_code=400)

            context = captured.get("context", {})
            ingest_payload = {
                "source": "sentinel_capture",
                "kind": "text",
                "text": context.get("clipboard", ""),
                "note": (
                    f"Active window: {context.get('active_window', {}).get('title', '')} | "
                    f"Process: {context.get('active_window', {}).get('process_name', '')}"
                ),
                "dispatch": False,
            }
            try:
                brain = self.services.get("brain")
                if brain and (ingest_payload["text"] or ingest_payload["note"]):
                    item = {
                        "source": ingest_payload["source"],
                        "counterparty": "desktop",
                        "type": "ops",
                        "tags": ["sentinel", "context"],
                        "summary": ingest_payload["note"][:180],
                        "raw_text": f"{ingest_payload['note']}\n\n{ingest_payload['text']}"[:8000],
                    }
                    item_id = brain.ingest(item)
                    captured["item_id"] = item_id
            except Exception:
                pass

            if hasattr(sentinel, "push_event"):
                try:
                    evt = sentinel.push_event(
                        source="sentinel_capture",
                        event_type="manual_capture",
                        payload=captured.get("context", {}),
                        priority="high",
                    )
                    captured["sentinel_task_id"] = evt.get("id", "")
                except Exception:
                    pass

            return JSONResponse(captured)

        @app.post("/api/sentinel/hotkey_trigger")
        async def sentinel_hotkey_trigger(req: Request):
            sentinel = self.services.get("sentinel")
            if not sentinel:
                return JSONResponse(
                    {"ok": False, "error": "Sentinel not running"}, status_code=503
                )
            try:
                data = await req.json()
            except Exception:
                data = {}
            include_screenshot = bool(data.get("include_screenshot", False))
            if not hasattr(sentinel, "trigger_hotkey_capture"):
                return JSONResponse(
                    {"ok": False, "error": "Sentinel hotkey trigger unavailable"},
                    status_code=500,
                )
            out = sentinel.trigger_hotkey_capture(
                include_screenshot=include_screenshot
            )
            code = 200 if out.get("ok") else 400
            return JSONResponse(out, status_code=code)

        @app.get("/api/sentinel/inbox")
        async def sentinel_inbox(limit: int = 100, status: str = ""):
            sentinel = self.services.get("sentinel")
            if not sentinel:
                return JSONResponse(
                    {"ok": False, "error": "Sentinel not running"}, status_code=503
                )
            if not hasattr(sentinel, "list_inbox"):
                return JSONResponse(
                    {"ok": False, "error": "Sentinel inbox unavailable"},
                    status_code=500,
                )
            items = sentinel.list_inbox(limit=limit, status=status)
            stats = {}
            if hasattr(sentinel, "inbox") and hasattr(sentinel.inbox, "stats"):
                stats = sentinel.inbox.stats()
            return JSONResponse({"ok": True, "items": items, "stats": stats})

        @app.get("/api/runtime_skills/proposals")
        async def runtime_skill_proposals():
            tools = self.services.get("tools")
            if not tools or not hasattr(tools, "list_runtime_proposals"):
                return JSONResponse(
                    {"ok": False, "error": "Runtime skills are not available"},
                    status_code=503,
                )
            return JSONResponse({"ok": True, "items": tools.list_runtime_proposals()})

        @app.post("/api/runtime_skills/propose")
        async def runtime_skill_propose(req: Request):
            tools = self.services.get("tools")
            if not tools or not hasattr(tools, "save_runtime_proposal"):
                return JSONResponse(
                    {"ok": False, "error": "Runtime skills are not available"},
                    status_code=503,
                )
            data = await req.json()
            name = str(data.get("name", "")).strip()
            reason = str(data.get("reason", "")).strip()
            code = str(data.get("code", "")).strip()
            risk = str(data.get("risk", "")).strip()
            if not name or not code:
                return JSONResponse(
                    {"ok": False, "error": "name and code are required"},
                    status_code=400,
                )
            result = tools.save_runtime_proposal(
                name=name,
                reason=reason,
                code=code,
                risk_text=risk,
                metadata={"source": "api"},
            )
            return JSONResponse(result)

        @app.post("/api/runtime_skills/approve")
        async def runtime_skill_approve(req: Request):
            tools = self.services.get("tools")
            if not tools or not hasattr(tools, "approve_runtime_proposal"):
                return JSONResponse(
                    {"ok": False, "error": "Runtime skills are not available"},
                    status_code=503,
                )
            data = await req.json()
            proposal_id = str(data.get("proposal_id", "")).strip()
            approved = bool(data.get("approved", False))
            schema = data.get("schema")
            if not proposal_id:
                return JSONResponse(
                    {"ok": False, "error": "proposal_id is required"},
                    status_code=400,
                )
            result = tools.approve_runtime_proposal(
                proposal_id=proposal_id, approved=approved, schema=schema
            )
            code = 200 if result.get("ok") else 400
            return JSONResponse(result, status_code=code)

        @app.get("/api/runtime_skills/list")
        async def runtime_skill_list():
            tools = self.services.get("tools")
            if not tools:
                return JSONResponse(
                    {"ok": False, "error": "Tools service unavailable"},
                    status_code=503,
                )
            items = [t for t in tools.all() if not t["name"] in {
                "web_fetch",
                "web_search",
                "read_file",
                "write_file",
                "list_dir",
                "search_files",
                "shell_exec",
                "brain_search",
                "draft_email",
                "draft_letter",
                "current_date",
            }]
            return JSONResponse({"ok": True, "items": items, "count": len(items)})

        @app.get("/api/self_improve/status")
        async def self_improve_status():
            builder = get_tool_builder()
            if not builder:
                return JSONResponse(
                    {"ok": False, "error": "Tool builder not running"}, status_code=503
                )
            return JSONResponse({"ok": True, **builder.self_improve_status()})

        @app.get("/api/self_improve/pending")
        async def self_improve_pending():
            builder = get_tool_builder()
            if not builder:
                return JSONResponse(
                    {"ok": False, "error": "Tool builder not running"}, status_code=503
                )
            return JSONResponse({"ok": True, "items": builder.list_pending_updates()})

        @app.post("/api/self_improve/propose")
        async def self_improve_propose(req: Request):
            builder = get_tool_builder()
            if not builder:
                return JSONResponse(
                    {"ok": False, "error": "Tool builder not running"}, status_code=503
                )
            data = await req.json()
            goal = data.get("goal", "")
            limit = int(data.get("limit", 8))
            items = await builder.propose_self_improvements(goal=goal, limit=limit)
            return JSONResponse({"ok": True, "items": items})

        @app.post("/api/self_improve/build_tool")
        async def self_improve_build_tool(req: Request):
            builder = get_tool_builder()
            if not builder:
                return JSONResponse(
                    {"ok": False, "error": "Tool builder not running"}, status_code=503
                )
            data = await req.json()
            description = str(data.get("description", "")).strip()
            name = str(data.get("name", "")).strip() or None
            queue = bool(data.get("queue", True))
            if not description:
                return JSONResponse({"ok": False, "error": "description is required"}, status_code=400)
            draft = await builder.build_from_description(description, name=name)
            if not queue or not draft.get("ok"):
                return JSONResponse(draft)
            req_item = builder.queue_update(
                "promote_tool",
                f"Promote tool '{draft['name']}'",
                {"name": draft["name"]},
                summary=description,
            )
            return JSONResponse({"ok": True, "draft": draft, "approval_request": req_item})

        @app.post("/api/self_improve/build_skill")
        async def self_improve_build_skill(req: Request):
            builder = get_tool_builder()
            if not builder:
                return JSONResponse(
                    {"ok": False, "error": "Tool builder not running"}, status_code=503
                )
            data = await req.json()
            description = str(data.get("description", "")).strip()
            name = str(data.get("name", "")).strip() or None
            queue = bool(data.get("queue", True))
            if not description:
                return JSONResponse({"ok": False, "error": "description is required"}, status_code=400)
            draft = await builder.build_skill_from_description(description, name=name)
            if not queue or not draft.get("ok"):
                return JSONResponse(draft)
            req_item = builder.queue_update(
                "promote_skill",
                f"Promote skill '{draft['name']}'",
                {"name": draft["name"]},
                summary=description,
            )
            return JSONResponse({"ok": True, "draft": draft, "approval_request": req_item})

        @app.post("/api/self_improve/knowledge")
        async def self_improve_knowledge(req: Request):
            builder = get_tool_builder()
            if not builder:
                return JSONResponse(
                    {"ok": False, "error": "Tool builder not running"}, status_code=503
                )
            data = await req.json()
            topic = str(data.get("topic", "")).strip()
            content = str(data.get("content", "")).strip()
            source = str(data.get("source", "manual")).strip() or "manual"
            tags = data.get("tags") or []
            queue = bool(data.get("queue", True))
            if not topic or not content:
                return JSONResponse(
                    {"ok": False, "error": "topic and content are required"}, status_code=400
                )
            draft = builder.draft_knowledge_note(topic, content, source=source, tags=tags)
            if not queue:
                req_item = builder.queue_update(
                    "save_knowledge",
                    f"Save knowledge '{topic}'",
                    {"topic": topic, "content": content, "source": source, "tags": tags},
                    summary=content[:160],
                )
                applied = builder.decide_update(req_item.get("id", ""), approved=True)
                return JSONResponse({"ok": bool(applied.get("ok")), "draft": draft, "result": applied})
            req_item = builder.queue_update(
                "save_knowledge",
                f"Save knowledge '{topic}'",
                {"topic": topic, "content": content, "source": source, "tags": tags},
                summary=content[:160],
            )
            return JSONResponse({"ok": True, "draft": draft, "approval_request": req_item})

        @app.post("/api/self_improve/decision")
        async def self_improve_decision(req: Request):
            builder = get_tool_builder()
            if not builder:
                return JSONResponse(
                    {"ok": False, "error": "Tool builder not running"}, status_code=503
                )
            data = await req.json()
            request_id = str(data.get("request_id", "")).strip()
            approved = bool(data.get("approved", False))
            if not request_id:
                return JSONResponse(
                    {"ok": False, "error": "request_id is required"}, status_code=400
                )
            result = builder.decide_update(request_id, approved=approved)
            code = 200 if result.get("ok") else 400
            return JSONResponse(result, status_code=code)

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
    from src.memory.memory import Memory, ensure_master_memory_file, load_master_memory_text
    from src.app_bridge.bridge import AppBridge
    from src.sentinel.sentinel import Sentinel

    settings = Settings.load()
    brain    = BrainIndex(settings.brain_db_path)
    ensure_master_memory_file("data/baba_master_memory.txt")
    master_memory = load_master_memory_text("data/baba_master_memory.txt")
    pool     = ProviderPool(
        settings.providers,
        master_memory_text=master_memory,
        master_memory_path="data/baba_master_memory.txt",
    )
    tools    = ToolRegistry()
    vision   = VisionPipeline(pool)
    claws    = ClawInstaller(settings.claws_dir)
    memory   = Memory(settings.memory_dir)
    apps     = AppBridge(settings)
    sentinel = Sentinel()
    sentinel.start()
    tool_builder = ToolBuilder(pool, brain, settings, memory) if ToolBuilder else None
    orch     = AgentOrchestrator(pool, brain, tools, vision)

    services = {
        "settings": settings, "brain": brain, "pool": pool,
        "tools": tools, "vision": vision, "claws": claws,
        "orchestrator": orch, "memory": memory, "tool_builder": tool_builder,
        "apps": apps,
        "sentinel": sentinel,
    }
    UIServer(services).run()
