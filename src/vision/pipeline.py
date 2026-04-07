"""
src/vision/pipeline.py
Vision Pipeline - routes images/PDFs through vision models
for OCR, data extraction, and Brain Index ingestion.
"""

import base64
import json
import asyncio
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, UTC


class VisionPipeline:
    """Multimodal vision pipeline using local or cloud vision models."""

    SUPPORTED_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".pdf"}

    PROMPTS = {
        "bill": "Extract all data from this bill/invoice: supplier name, invoice number, date, due date, line items, subtotal, VAT, total. Return as structured JSON.",
        "contract": "Review this contract. Extract: parties involved, key obligations, dates, termination clauses, renewal terms, risk clauses. Return as JSON.",
        "receipt": "Extract receipt data: merchant, date, items purchased with prices, total, payment method. Return as JSON.",
        "screenshot": "Describe what you see in this screenshot. Extract any text, data tables, error messages, or important information. Return as JSON.",
        "product": "Identify this product. Extract: name, brand, SKU/barcode, price if visible, specifications. Return as JSON.",
        "general": "Analyse this image. Extract all relevant text, data, entities, amounts, dates. Classify what type of document this is. Return as JSON.",
    }

    def __init__(self, provider_pool, brain=None, settings=None):
        self.pool = provider_pool
        self.brain = brain
        self.settings = settings

    async def analyse(
        self, image_path: str, task: str = "general", extra_prompt: str = ""
    ) -> Dict[str, Any]:
        path = Path(image_path)
        if not path.exists():
            return {"error": f"File not found: {image_path}"}

        suffix = path.suffix.lower()
        if suffix not in self.SUPPORTED_TYPES:
            return {"error": f"Unsupported file type: {suffix}"}

        if suffix == ".pdf":
            return await self._analyse_pdf(path, task)

        image_b64 = self._encode_image(path)
        prompt = self.PROMPTS.get(task, self.PROMPTS["general"])
        if extra_prompt:
            prompt += f"\n\n{extra_prompt}"

        result = None
        for provider, model in [
            ("jan", "Qwen2_5-VL-7B-Instruct"),
            ("lmstudio", "qwen2.5-vl-7b-instruct"),
            ("gemini", "gemini-2.0-flash-exp"),
        ]:
            try:
                result = await self._send_vision_request(
                    provider, model, image_b64, prompt, suffix
                )
                result["_provider"] = provider
                result["_model"] = model
                break
            except Exception as e:
                print(f"[VisionPipeline] {provider} failed: {e}, trying next...")

        if not result:
            return {"error": "All vision providers failed", "task": task}

        result["_source_path"] = str(path)
        result["_task"] = task
        return result

    async def analyse_and_index(self, image_path: str, task: str = "general") -> str:
        data = await self.analyse(image_path, task)
        if "error" in data:
            return ""

        if self.brain:
            brain_item = self._to_brain_item(data, image_path)
            item_id = self.brain.ingest(brain_item)
            return item_id
        return ""

    def analyse_sync(self, image_path: str, task: str = "general") -> Dict[str, Any]:
        return asyncio.run(self.analyse(image_path, task))

    def _encode_image(self, path: Path) -> str:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    def _get_mime_type(self, suffix: str) -> str:
        return {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "bmp": "image/bmp",
        }.get(suffix.lstrip("."), "image/jpeg")

    async def _send_vision_request(
        self, provider: str, model: str, image_b64: str, prompt: str, suffix: str
    ) -> Dict:
        if provider in ("jan", "lmstudio"):
            return await self._openai_vision(
                provider, model, image_b64, prompt, self._get_mime_type(suffix)
            )
        elif provider == "gemini":
            return await self._gemini_vision(
                model, image_b64, prompt, self._get_mime_type(suffix)
            )
        raise ValueError(f"No vision support for {provider}")

    async def _openai_vision(
        self, provider: str, model: str, b64: str, prompt: str, mime: str
    ) -> Dict:
        import httpx

        urls = {"jan": "http://localhost:1337", "lmstudio": "http://localhost:1234"}
        url = urls[provider] + "/v1/chat/completions"
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                url, json={"model": model, "messages": messages, "max_tokens": 1024}
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
            return self._parse_json_response(text)

    async def _gemini_vision(
        self, model: str, b64: str, prompt: str, mime: str
    ) -> Dict:
        import httpx

        api_key = (
            self.pool._get_api_key("gemini")
            if hasattr(self.pool, "_get_api_key")
            else ""
        )
        if not api_key:
            raise ValueError("Gemini API key not set")
        payload = {
            "contents": [
                {
                    "parts": [
                        {"inline_data": {"mime_type": mime, "data": b64}},
                        {"text": prompt},
                    ]
                }
            ],
            "generationConfig": {"maxOutputTokens": 1024},
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return self._parse_json_response(text)

    async def _analyse_pdf(self, path: Path, task: str) -> Dict:
        try:
            from pdfminer.high_level import extract_text

            text = extract_text(str(path))[:4000]
        except ImportError:
            try:
                import fitz

                doc = fitz.open(str(path))
                text = "".join(p.get_text() for p in doc)[:4000]
            except ImportError:
                return {
                    "error": "Install pdfminer.six or pymupdf: pip install pdfminer.six"
                }

        prompt = self.PROMPTS.get(task, self.PROMPTS["general"])
        messages = [{"role": "user", "content": f"{prompt}\n\nDocument text:\n{text}"}]
        try:
            reply = await self.pool.chat("jan", "Qwen3_5-9B_Q4_K_M", messages)
            return self._parse_json_response(reply)
        except Exception:
            reply = await self.pool.chat("groq", "llama-3.3-70b-versatile", messages)
            return self._parse_json_response(reply)

    def _parse_json_response(self, text: str) -> Dict:
        try:
            return json.loads(text)
        except Exception:
            pass
        m = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        return {"raw_text": text, "parsed": False}

    def _to_brain_item(self, data: Dict, image_path: str) -> Dict:
        from src.brain.importers import EmailImporter

        ei = EmailImporter()
        raw = json.dumps(data)
        return {
            "source": "vision",
            "counterparty": data.get("supplier")
            or data.get("merchant")
            or data.get("party")
            or "",
            "type": data.get("document_type") or ei._classify(raw),
            "tags": ["vision-extracted"] + ei._extract_tags(raw),
            "summary": f"Vision scan: {Path(image_path).name} - {str(data)[:80]}",
            "entities": data,
            "amounts": self._extract_amounts_from_data(data),
            "renewal_date": data.get("renewal_date")
            or data.get("due_date")
            or data.get("expiry_date"),
            "risk_level": "none",
            "raw_path": image_path,
            "raw_text": json.dumps(data)[:3000],
        }

    def _extract_amounts_from_data(self, data: Dict) -> List[Dict]:
        amounts = []
        for key in ("total", "amount", "subtotal", "vat", "price"):
            v = data.get(key)
            if v is not None:
                try:
                    amounts.append(
                        {
                            "value": float(str(v).replace("GBP", "").replace(",", "")),
                            "currency": "GBP",
                            "label": key,
                        }
                    )
                except Exception:
                    pass
        return amounts

    async def analyse_b64(
        self, data_url: str, filename: str, task: str = "general"
    ) -> str:
        import tempfile, os

        try:
            header, b64data = data_url.split(",", 1)
        except ValueError:
            b64data = data_url
            header = ""

        ext = ".png"
        if "pdf" in header:
            ext = ".pdf"
        elif filename:
            ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ".png"

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(base64.b64decode(b64data))
            tmp_path = f.name

        try:
            result = await self.analyse(tmp_path, task)
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
        return result
