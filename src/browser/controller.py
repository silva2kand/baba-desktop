"""
src/browser/controller.py — Browser Controller
Playwright-based browser automation for web scraping, form filling,
data extraction, and web app interaction.
"""

import json, time, threading
from pathlib import Path
from typing import Dict, List, Optional, Any

BROWSER_DATA = Path(__file__).parent.parent.parent / "data" / "browser"
BROWSER_DATA.mkdir(parents=True, exist_ok=True)


class BrowserController:
    """Playwright-based browser automation."""

    def __init__(self):
        self._browser = None
        self._context = None
        self._page = None
        self._available = False
        self._screenshots = []
        self._init()

    def _init(self):
        try:
            from playwright.sync_api import sync_playwright

            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=False)
            self._context = self._browser.new_context()
            self._page = self._context.new_page()
            self._available = True
        except Exception as e:
            self._available = False
            print(f"[Browser] Playwright not available: {e}")

    def is_available(self):
        return self._available

    def navigate(self, url, wait_until="domcontentloaded", timeout=30000):
        """Navigate to URL."""
        if not self._available:
            return {"error": "Browser not available"}
        try:
            self._page.goto(url, wait_until=wait_until, timeout=timeout)
            return {"status": "ok", "url": self._page.url, "title": self._page.title()}
        except Exception as e:
            return {"error": str(e)}

    def click(self, selector):
        """Click element by CSS selector."""
        if not self._available:
            return {"error": "Browser not available"}
        try:
            self._page.click(selector)
            return {"status": "ok"}
        except Exception as e:
            return {"error": str(e)}

    def fill(self, selector, text):
        """Fill input field."""
        if not self._available:
            return {"error": "Browser not available"}
        try:
            self._page.fill(selector, text)
            return {"status": "ok"}
        except Exception as e:
            return {"error": str(e)}

    def get_text(self, selector=None):
        """Extract text from page or specific element."""
        if not self._available:
            return {"error": "Browser not available"}
        try:
            if selector:
                return {"text": self._page.text_content(selector)}
            return {"text": self._page.inner_text("body")}
        except Exception as e:
            return {"error": str(e)}

    def get_links(self):
        """Extract all links from page."""
        if not self._available:
            return {"error": "Browser not available"}
        try:
            links = self._page.eval_on_selector_all(
                "a", "els => els.map(e => ({text:e.innerText,href:e.href}))"
            )
            return {"links": links}
        except Exception as e:
            return {"error": str(e)}

    def get_tables(self):
        """Extract tables from page."""
        if not self._available:
            return {"error": "Browser not available"}
        try:
            tables = self._page.eval_on_selector_all(
                "table",
                """els => els.map(t => {
                const rows = t.querySelectorAll('tr');
                return Array.from(rows).map(r => Array.from(r.querySelectorAll('th,td')).map(c => c.innerText));
            })""",
            )
            return {"tables": tables}
        except Exception as e:
            return {"error": str(e)}

    def screenshot(self, path=None):
        """Take screenshot."""
        if not self._available:
            return {"error": "Browser not available"}
        try:
            if not path:
                path = str(BROWSER_DATA / f"screenshot_{int(time.time())}.png")
            self._page.screenshot(path=path)
            self._screenshots.append(path)
            return {"status": "ok", "path": path}
        except Exception as e:
            return {"error": str(e)}

    def execute_js(self, script):
        """Execute JavaScript on page."""
        if not self._available:
            return {"error": "Browser not available"}
        try:
            result = self._page.evaluate(script)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

    def get_page_info(self):
        """Get current page info."""
        if not self._available:
            return {"error": "Browser not available"}
        try:
            return {"url": self._page.url, "title": self._page.title(), "status": "ok"}
        except Exception as e:
            return {"error": str(e)}

    def close(self):
        """Close browser."""
        if self._browser:
            self._browser.close()
            self._available = False

    def run_workflow(self, steps):
        """Run a sequence of browser steps."""
        results = []
        for step in steps:
            action = step.get("action")
            if action == "navigate":
                results.append(self.navigate(step.get("url", "")))
            elif action == "click":
                results.append(self.click(step.get("selector", "")))
            elif action == "fill":
                results.append(
                    self.fill(step.get("selector", ""), step.get("text", ""))
                )
            elif action == "extract":
                results.append(self.get_text(step.get("selector")))
            elif action == "screenshot":
                results.append(self.screenshot(step.get("path")))
            elif action == "js":
                results.append(self.execute_js(step.get("script", "")))
            time.sleep(step.get("delay", 1))
        return results
