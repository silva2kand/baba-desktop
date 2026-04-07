"""
src/brain/importers.py
Importers for email (.eml), WhatsApp exports, PDFs, and folder watch.
Each importer returns a list of Brain Index items ready for ingestion.
"""

import os
import re
import json
import email
import email.message
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, UTC


class EmailImporter:
    """Import .eml files or directories of .eml files into Brain items."""

    BILL_KEYWORDS = ["invoice", "payment", "bill", "statement", "receipt", "due"]
    LEGAL_KEYWORDS = [
        "notice",
        "enforcement",
        "dispute",
        "claim",
        "legal",
        "solicitor",
        "court",
    ]
    SUPPLIER_KEYWORDS = ["order", "delivery", "stock", "supplier", "wholesale", "rep"]
    COUNCIL_KEYWORDS = ["council", "rates", "planning", "licence", "inspection"]
    INSURANCE_KEYWORDS = ["insurance", "policy", "premium", "renewal", "cover"]

    def import_file(self, path: str) -> Dict:
        with open(path, "rb") as f:
            msg = email.message_from_bytes(f.read())
        return self._parse_msg(msg, path)

    def import_directory(self, directory: str) -> List[Dict]:
        items = []
        for eml in Path(directory).glob("**/*.eml"):
            try:
                items.append(self.import_file(str(eml)))
            except Exception as e:
                print(f"[EmailImporter] skip {eml}: {e}")
        return items

    def _parse_msg(self, msg: email.message.Message, path: str) -> Dict:
        subject = msg.get("Subject", "")
        sender = msg.get("From", "")
        date_str = msg.get("Date", "")
        body = self._get_body(msg)
        full_text = f"{subject}\n{body}"

        return {
            "source": "email",
            "date": self._parse_date(date_str),
            "counterparty": self._extract_name(sender),
            "type": self._classify(full_text),
            "tags": self._extract_tags(full_text),
            "summary": f"{subject[:100]} - from {self._extract_name(sender)}",
            "entities": {"email": sender, "subject": subject},
            "amounts": self._extract_amounts(full_text),
            "renewal_date": self._extract_renewal_date(full_text),
            "risk_level": self._assess_risk(full_text),
            "raw_path": path,
            "raw_text": full_text[:5000],
        }

    def _get_body(self, msg) -> str:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        body += part.get_payload(decode=True).decode(
                            "utf-8", errors="ignore"
                        )
                    except Exception:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
            except Exception:
                body = str(msg.get_payload())
        return body[:5000]

    def _extract_name(self, sender: str) -> str:
        match = re.match(r'^"?([^"<]+)"?\s*<', sender)
        return match.group(1).strip() if match else sender.split("@")[0]

    def _parse_date(self, date_str: str) -> Optional[str]:
        try:
            from email.utils import parsedate_to_datetime

            return parsedate_to_datetime(date_str).strftime("%Y-%m-%d")
        except Exception:
            return None

    def _classify(self, text: str) -> str:
        t = text.lower()
        if any(k in t for k in self.LEGAL_KEYWORDS):
            return "legal"
        if any(k in t for k in self.INSURANCE_KEYWORDS):
            return "insurance"
        if any(k in t for k in self.COUNCIL_KEYWORDS):
            return "council"
        if any(k in t for k in self.BILL_KEYWORDS):
            return "bill"
        if any(k in t for k in self.SUPPLIER_KEYWORDS):
            return "supplier"
        return "personal"

    def _extract_tags(self, text: str) -> List[str]:
        t = text.lower()
        tags = []
        tag_map = {
            "invoice": "bill",
            "payment": "bill",
            "renewal": "renewal",
            "overdue": "overdue",
            "dispute": "dispute",
            "urgent": "urgent",
            "contract": "contract",
            "planning": "planning",
        }
        for kw, tag in tag_map.items():
            if kw in t and tag not in tags:
                tags.append(tag)
        return tags

    def _extract_amounts(self, text: str) -> List[Dict]:
        amounts = []
        for m in re.finditer(r"£\s*([\d,]+(?:\.\d{2})?)", text):
            try:
                amounts.append(
                    {"value": float(m.group(1).replace(",", "")), "currency": "GBP"}
                )
            except Exception:
                pass
        return amounts[:5]

    def _extract_renewal_date(self, text: str) -> Optional[str]:
        patterns = [
            r"renew(?:al|s)?\s+(?:date|due|on|by)?\s*:?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
            r"expires?\s+(?:on|:)?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
            r"due\s+(?:date|by|on)\s*:?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    def _assess_risk(self, text: str) -> str:
        t = text.lower()
        high = [
            "enforcement",
            "court",
            "legal action",
            "overdue",
            "final notice",
            "urgent",
        ]
        medium = ["dispute", "complaint", "notice", "reminder", "renewal"]
        if any(k in t for k in high):
            return "high"
        if any(k in t for k in medium):
            return "medium"
        return "none"


class WhatsAppImporter:
    """Import WhatsApp chat export (.zip or .txt) into Brain items."""

    def import_zip(self, zip_path: str) -> List[Dict]:
        with zipfile.ZipFile(zip_path) as z:
            txt_files = [n for n in z.namelist() if n.endswith(".txt")]
            items = []
            for fname in txt_files:
                text = z.read(fname).decode("utf-8", errors="ignore")
                items.extend(self._parse_chat(text, fname))
        return items

    def import_txt(self, txt_path: str) -> List[Dict]:
        with open(txt_path, encoding="utf-8", errors="ignore") as f:
            text = f.read()
        return self._parse_chat(text, txt_path)

    def _parse_chat(self, text: str, source_name: str) -> List[Dict]:
        lines = text.strip().split("\n")
        msg_pattern = re.compile(
            r"(\d{1,2}/\d{1,2}/\d{2,4}),?\s+\d{1,2}:\d{2}(?:\s*[ap]m)?\s*-\s+([^:]+):\s+(.*)",
            re.IGNORECASE,
        )
        messages_by_contact: Dict[str, List[str]] = {}
        for line in lines:
            m = msg_pattern.match(line.strip())
            if m:
                contact = m.group(2).strip()
                msg = m.group(3).strip()
                messages_by_contact.setdefault(contact, []).append(msg)

        items = []
        for contact, msgs in messages_by_contact.items():
            full_text = "\n".join(msgs[:50])
            items.append(
                {
                    "source": "whatsapp",
                    "counterparty": contact,
                    "type": "comms",
                    "tags": ["whatsapp", "comms"],
                    "summary": f"WhatsApp conversation with {contact} - {len(msgs)} messages",
                    "entities": {"contact": contact, "message_count": len(msgs)},
                    "raw_text": full_text[:3000],
                    "raw_path": source_name,
                }
            )
        return items


class PDFImporter:
    """Import PDFs - uses pdfminer.six or PyMuPDF if available."""

    def import_file(self, path: str) -> Dict:
        text = self._extract_text(path)
        email_imp = EmailImporter()
        return {
            "source": "pdf",
            "counterparty": self._guess_sender(text, path),
            "type": email_imp._classify(text),
            "tags": email_imp._extract_tags(text) + ["pdf"],
            "summary": f"PDF: {Path(path).name} - {text[:80]}",
            "entities": {},
            "amounts": email_imp._extract_amounts(text),
            "renewal_date": email_imp._extract_renewal_date(text),
            "risk_level": email_imp._assess_risk(text),
            "raw_path": path,
            "raw_text": text[:5000],
        }

    def import_directory(self, directory: str) -> List[Dict]:
        items = []
        for pdf in Path(directory).glob("**/*.pdf"):
            try:
                items.append(self.import_file(str(pdf)))
            except Exception as e:
                print(f"[PDFImporter] skip {pdf}: {e}")
        return items

    def _extract_text(self, path: str) -> str:
        try:
            from pdfminer.high_level import extract_text

            return extract_text(path)[:8000]
        except ImportError:
            pass
        try:
            import fitz

            doc = fitz.open(path)
            text = "".join(page.get_text() for page in doc)
            return text[:8000]
        except ImportError:
            pass
        return f"[PDF text extraction requires: pip install pdfminer.six OR pymupdf]\nFile: {path}"

    def _guess_sender(self, text: str, path: str) -> str:
        m = re.search(
            r"(?:from|sender|issued by|supplier|company):\s*([^\n]{2,60})",
            text,
            re.IGNORECASE,
        )
        return m.group(1).strip() if m else Path(path).stem


class FolderWatcher:
    """Watch a folder and ingest new files automatically."""

    def __init__(self, brain_index, folders: List[str]):
        self.brain = brain_index
        self.folders = [Path(f) for f in folders]
        self._seen = set()

    def scan_once(self) -> int:
        email_imp = EmailImporter()
        pdf_imp = PDFImporter()
        wa_imp = WhatsAppImporter()
        count = 0

        for folder in self.folders:
            if not folder.exists():
                continue
            for f in folder.iterdir():
                if str(f) in self._seen:
                    continue
                self._seen.add(str(f))
                try:
                    if f.suffix.lower() == ".eml":
                        item = email_imp.import_file(str(f))
                    elif f.suffix.lower() == ".pdf":
                        item = pdf_imp.import_file(str(f))
                    elif (
                        f.suffix.lower() in (".txt", ".zip")
                        and "whatsapp" in f.name.lower()
                    ):
                        items = (
                            wa_imp.import_zip(str(f))
                            if f.suffix == ".zip"
                            else wa_imp.import_txt(str(f))
                        )
                        for it in items:
                            self.brain.ingest(it)
                        count += len(items)
                        continue
                    else:
                        continue
                    self.brain.ingest(item)
                    count += 1
                except Exception as e:
                    print(f"[FolderWatcher] error on {f}: {e}")
        return count

    def watch(self, interval_seconds: int = 30):
        import time

        while True:
            n = self.scan_once()
            if n:
                print(f"[FolderWatcher] ingested {n} new items")
            time.sleep(interval_seconds)
