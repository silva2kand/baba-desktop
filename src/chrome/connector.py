"""
src/chrome/connector.py
Chrome Extension Connector - HTTP bridge between Chrome extension and Baba Desktop.
"""

import json
import re
from pathlib import Path
from datetime import datetime, UTC
from typing import Dict, Any, Optional


class ChromeConnector:
    """Bridge between Chrome extension and Baba Desktop."""

    def __init__(self, dispatcher, brain, pool, port: int = 8768):
        self.dispatcher = dispatcher
        self.brain = brain
        self.pool = pool
        self.port = port
        self._log_path = Path("logs/chrome_connector.jsonl")
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def start(self):
        import threading

        t = threading.Thread(target=self._run_server, daemon=True)
        t.start()
        print(f"[Chrome] Connector on http://localhost:{self.port}")

    def _run_server(self):
        try:
            from fastapi import FastAPI, Request
            from fastapi.responses import JSONResponse
            from fastapi.middleware.cors import CORSMiddleware
            import uvicorn

            app = FastAPI(title="Baba Chrome Connector")
            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            )

            @app.post("/chrome/summarise")
            async def summarise(req: Request):
                data = await req.json()
                result = await self.summarise_page(
                    data.get("url", ""), data.get("text", ""), data.get("title", "")
                )
                return JSONResponse(result)

            @app.post("/chrome/extract")
            async def extract(req: Request):
                data = await req.json()
                result = await self.extract_page_data(
                    data.get("url", ""),
                    data.get("text", ""),
                    data.get("type", "general"),
                )
                return JSONResponse(result)

            @app.post("/chrome/pdf")
            async def pdf(req: Request):
                data = await req.json()
                result = await self.process_pdf(
                    data.get("url", ""), data.get("text", "")
                )
                return JSONResponse(result)

            @app.post("/chrome/contextual")
            async def contextual(req: Request):
                data = await req.json()
                result = await self.contextual_action(
                    data.get("selected_text", ""),
                    data.get("action", "summarise"),
                    data.get("page_url", ""),
                )
                return JSONResponse(result)

            @app.post("/chrome/dispatch")
            async def dispatch(req: Request):
                data = await req.json()
                result = self.dispatch_to_desktop(
                    data.get("instruction", ""), data.get("context", {})
                )
                return JSONResponse(result)

            @app.post("/chrome/session_guard")
            async def session_guard(req: Request):
                data = await req.json()
                result = self.detect_auth_gate(
                    data.get("url", ""),
                    data.get("title", ""),
                    data.get("text", ""),
                )
                return JSONResponse(result)

            @app.post("/chrome/index_page")
            async def index_page(req: Request):
                data = await req.json()
                result = await self.index_to_brain(
                    data.get("url", ""), data.get("text", ""), data.get("title", "")
                )
                return JSONResponse(result)

            @app.get("/chrome/health")
            async def health():
                return JSONResponse(
                    {"ok": True, "version": "9.0", "service": "Baba Chrome Connector"}
                )

            uvicorn.run(app, host="localhost", port=self.port, log_level="warning")
        except ImportError:
            print(
                "[Chrome] Install fastapi+uvicorn for Chrome connector: pip install fastapi uvicorn"
            )

    async def summarise_page(self, url: str, text: str, title: str = "") -> Dict:
        prompt = f"""Summarise this webpage concisely.

Title: {title}
URL: {url}
Content: {text[:3000]}

Provide:
1. One-sentence summary
2. Key points (3-5 bullets)
3. Any important data, dates, or numbers
4. Action items if any"""

        messages = [{"role": "user", "content": prompt}]
        try:
            reply = await self.pool.chat(
                "ollama", "qwen3.5:latest", messages, max_tokens=500
            )
            self._log("summarise", url)
            return {"ok": True, "summary": reply, "url": url}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def extract_page_data(
        self, url: str, text: str, data_type: str = "general"
    ) -> Dict:
        type_prompts = {
            "table": "Extract all tables from this page as JSON arrays",
            "contacts": "Extract all contact information (names, emails, phones, companies)",
            "prices": "Extract all prices, costs, and financial figures",
            "dates": "Extract all dates, deadlines, and time-sensitive information",
            "links": "Extract all meaningful links and their descriptions",
            "general": "Extract all key facts, figures, names, and structured data",
        }
        prompt = f"""{type_prompts.get(data_type, type_prompts["general"])}

URL: {url}
Content: {text[:3000]}

Return as JSON."""

        messages = [{"role": "user", "content": prompt}]
        try:
            reply = await self.pool.chat(
                "ollama", "qwen3.5:latest", messages, max_tokens=800
            )
            self._log("extract", url, {"type": data_type})
            return {"ok": True, "data": reply, "type": data_type, "url": url}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def process_pdf(self, url: str, text: str) -> Dict:
        prompt = f"""This is a PDF document. Analyse it completely.

URL: {url}
Content: {text[:4000]}

Provide:
1. Document type and purpose
2. Key information summary
3. Important dates and deadlines
4. Financial figures (if any)
5. Action items or requirements
6. Risk flags (if any)

Return as structured JSON."""

        messages = [{"role": "user", "content": prompt}]
        try:
            reply = await self.pool.chat(
                "groq", "llama-3.3-70b-versatile", messages, max_tokens=1000
            )
            await self.index_to_brain(url, text, f"PDF: {url.split('/')[-1]}")
            self._log("pdf", url)
            return {"ok": True, "analysis": reply, "indexed": True, "url": url}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def contextual_action(
        self, selected_text: str, action: str, page_url: str = ""
    ) -> Dict:
        action_prompts = {
            "summarise": f"Summarise this text concisely:\n\n{selected_text}",
            "rewrite": f"Rewrite this text more clearly and professionally:\n\n{selected_text}",
            "translate": f"Translate this text to English (or clarify language first):\n\n{selected_text}",
            "explain": f"Explain this text in plain English:\n\n{selected_text}",
            "email": f"Draft a professional email based on this text:\n\n{selected_text}\n\nSource: {page_url}",
            "post": f"Create a social media post based on this text:\n\n{selected_text}",
            "reply": f"Draft a professional reply to this:\n\n{selected_text}",
            "extract": f"Extract key facts, data, and entities from:\n\n{selected_text}",
            "improve": f"Improve the quality of this writing:\n\n{selected_text}",
            "shorten": f"Make this text 50% shorter while keeping the key points:\n\n{selected_text}",
        }
        prompt = action_prompts.get(
            action, f"Perform '{action}' on:\n\n{selected_text}"
        )
        messages = [{"role": "user", "content": prompt}]
        try:
            reply = await self.pool.chat(
                "ollama", "qwen3.5:latest", messages, max_tokens=600
            )
            self._log("contextual", page_url, {"action": action})
            return {"ok": True, "result": reply, "action": action}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def dispatch_to_desktop(self, instruction: str, context: Dict = None) -> Dict:
        if not self.dispatcher:
            return {"ok": False, "error": "Dispatcher not connected"}
        task = self.dispatcher.submit(
            instruction=instruction,
            source="chrome_extension",
            context=context or {},
        )
        self._log("dispatch", "", {"instruction": instruction[:60]})
        return {
            "ok": True,
            "task_id": task.task_id,
            "message": f"Task queued on desktop: {instruction[:60]}",
        }

    def detect_auth_gate(self, url: str, title: str, text: str) -> Dict[str, Any]:
        probe = f"{url}\n{title}\n{text[:3000]}".lower()
        login_terms = [
            "sign in",
            "log in",
            "login",
            "create account",
            "sign up",
            "register",
            "enter code",
            "two-factor",
            "2fa",
            "verify it's you",
            "security challenge",
            "captcha",
        ]
        matched = [term for term in login_terms if term in probe]
        needs_user = bool(matched)
        action = "user_login_required" if needs_user else "automation_allowed"
        if any(t in probe for t in ["captcha", "verify it's you", "two-factor", "2fa"]):
            action = "user_verification_required"
        return {
            "ok": True,
            "requires_user_action": needs_user,
            "action": action,
            "matched_terms": matched[:8],
            "message": (
                "Please complete sign-in/verification manually, then run automation."
                if needs_user
                else "No auth gate detected. Automation can continue."
            ),
        }

    async def index_to_brain(self, url: str, text: str, title: str = "") -> Dict:
        from src.brain.importers import EmailImporter

        ei = EmailImporter()
        item = {
            "source": "chrome",
            "counterparty": self._extract_domain(url),
            "type": ei._classify(text),
            "tags": ei._extract_tags(text) + ["web", "chrome"],
            "summary": f"{title or url}: {text[:80]}",
            "entities": {"url": url, "domain": self._extract_domain(url)},
            "amounts": ei._extract_amounts(text),
            "renewal_date": ei._extract_renewal_date(text),
            "raw_path": url,
            "raw_text": text[:3000],
        }
        item_id = self.brain.ingest(item)
        return {"ok": True, "item_id": item_id, "type": item["type"]}

    def _extract_domain(self, url: str) -> str:
        m = re.search(r"https?://([^/]+)", url)
        return m.group(1) if m else url

    def _log(self, action: str, url: str, extra: Dict = None):
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "action": action,
            "url": url[:100],
            **(extra or {}),
        }
        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")


CHROME_EXTENSION_MANIFEST = {
    "manifest_version": 3,
    "name": "Baba Desktop - Chrome Connector",
    "version": "1.0.0",
    "description": "Connect Chrome to Baba Desktop Business Brain OS",
    "permissions": ["activeTab", "contextMenus", "storage", "scripting"],
    "host_permissions": ["http://localhost:8768/*"],
    "action": {
        "default_popup": "popup.html",
        "default_icon": {"16": "icon16.png", "48": "icon48.png"},
    },
    "background": {"service_worker": "background.js"},
    "content_scripts": [{"matches": ["<all_urls>"], "js": ["content.js"]}],
}

CHROME_EXTENSION_BACKGROUND_JS = """
// Baba Desktop Chrome Extension - background.js
const BABA_URL = 'http://localhost:8768';

chrome.contextMenus.create({
  id: 'baba-summarise',  title: 'Summarise with Baba',  contexts: ['selection', 'page']
});
chrome.contextMenus.create({
  id: 'baba-extract',    title: 'Extract data with Baba', contexts: ['selection']
});
chrome.contextMenus.create({
  id: 'baba-email',      title: 'Draft email with Baba', contexts: ['selection']
});
chrome.contextMenus.create({
  id: 'baba-post',       title: 'Create post with Baba', contexts: ['selection']
});
chrome.contextMenus.create({
  id: 'baba-dispatch',   title: 'Send task to Baba Desktop', contexts: ['page']
});
chrome.contextMenus.create({
  id: 'baba-index',      title: 'Add page to Baba Brain', contexts: ['page']
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const text = info.selectionText || '';
  const url  = tab.url || '';
  
  if (info.menuItemId === 'baba-summarise') {
    const resp = await fetch(`${BABA_URL}/chrome/contextual`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({selected_text: text, action: 'summarise', page_url: url})
    });
    const data = await resp.json();
    chrome.notifications.create({type:'basic', iconUrl:'icon48.png',
      title:'Baba Summary', message: data.result?.slice(0,200) || 'Done'});
  }
  
  if (info.menuItemId === 'baba-dispatch') {
    const instruction = prompt('Task for Baba Desktop:');
    if (instruction) {
      await fetch(`${BABA_URL}/chrome/dispatch`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({instruction, context: {page_url: url}})
      });
    }
  }
});
"""
