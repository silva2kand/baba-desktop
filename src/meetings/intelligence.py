"""
src/meetings/intelligence.py
Meeting Intelligence - process recordings, transcripts, extract action items.
"""

import re
import json
from pathlib import Path
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional


class MeetingIntelligence:
    """Process meeting recordings/transcripts into structured data."""

    TRANSCRIPT_EXTS = {".txt", ".vtt", ".srt", ".docx", ".pdf", ".md"}
    AUDIO_EXTS = {".mp3", ".mp4", ".wav", ".m4a", ".ogg", ".webm"}

    def __init__(self, pool, brain, settings=None):
        self.pool = pool
        self.brain = brain
        self.settings = settings

    async def process_transcript(self, path: str) -> Dict:
        p = Path(path)
        if p.suffix.lower() not in self.TRANSCRIPT_EXTS:
            return {"ok": False, "error": f"Unsupported transcript format: {p.suffix}"}

        text = self._read_transcript(path)
        if not text:
            return {"ok": False, "error": "Could not read transcript"}

        result = await self._analyse_meeting(text, str(p.name))
        if self.brain:
            self.brain.ingest(
                {
                    "source": "meeting",
                    "type": "comms",
                    "tags": ["meeting", "transcript", "action-items"],
                    "summary": result.get("summary", "Meeting notes"),
                    "entities": {
                        "attendees": result.get("attendees", []),
                        "decisions": result.get("decisions", []),
                    },
                    "raw_text": text[:3000],
                    "raw_path": path,
                }
            )
        return {"ok": True, **result}

    async def process_audio(self, path: str) -> Dict:
        try:
            transcript_text = await self._transcribe_audio(path)
            return await self._analyse_meeting(transcript_text, Path(path).name)
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "install": "pip install openai-whisper for local transcription",
            }

    async def quick_summary(
        self, transcript_text: str, meeting_name: str = "Meeting"
    ) -> Dict:
        return await self._analyse_meeting(transcript_text, meeting_name)

    async def _analyse_meeting(self, text: str, meeting_name: str) -> Dict:
        prompt = f"""Analyse this meeting transcript and extract structured data.

Meeting: {meeting_name}
Transcript (excerpt):
{text[:4000]}

Extract and return as JSON:
{{
  "summary": "2-3 sentence executive summary",
  "attendees": ["name1", "name2"],
  "duration_minutes": 0,
  "key_topics": ["topic1", "topic2"],
  "decisions": ["decision1", "decision2"],
  "action_items": [
    {{"owner": "name", "task": "what to do", "due_date": "YYYY-MM-DD or null", "priority": "high|medium|low"}}
  ],
  "follow_up_emails": [
    {{"to": "name/role", "subject": "...", "body": "..."}}
  ],
  "risks_flagged": ["risk1"],
  "next_meeting": "date if mentioned or null",
  "sentiment": "positive|neutral|negative|mixed"
}}

Return ONLY valid JSON."""

        messages = [{"role": "user", "content": prompt}]
        try:
            reply = await self.pool.chat(
                "groq", "llama-3.3-70b-versatile", messages, max_tokens=2000
            )
        except Exception:
            try:
                reply = await self.pool.chat(
                    "ollama", "qwen3.5:latest", messages, max_tokens=2000
                )
            except Exception as e:
                return {"ok": False, "error": str(e)}

        try:
            m = re.search(r"\{[\s\S]+\}", reply)
            if m:
                data = json.loads(m.group())
                data["meeting_name"] = meeting_name
                data["processed_at"] = datetime.now(UTC).isoformat()
                data["ok"] = True
                self._save_outputs(data, meeting_name)
                return data
        except Exception:
            pass

        return {
            "ok": True,
            "summary": self._extract_sentences(text, 2),
            "action_items": self._extract_action_items_simple(text),
            "raw_analysis": reply[:500],
            "meeting_name": meeting_name,
        }

    async def _transcribe_audio(self, path: str) -> str:
        try:
            import whisper

            model = whisper.load_model("base")
            result = model.transcribe(path)
            return result.get("text", "")
        except ImportError:
            return f"[Audio transcription requires: pip install openai-whisper]\nFile: {path}"

    def _save_outputs(self, data: Dict, meeting_name: str):
        out_dir = Path("data/exports/meetings")
        out_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]", "_", meeting_name.lower())[:30]
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M")

        json_path = out_dir / f"{slug}_{ts}.json"
        json_path.write_text(json.dumps(data, indent=2))

        actions_path = out_dir / f"{slug}_{ts}_actions.txt"
        lines = [f"ACTION ITEMS - {meeting_name}", f"Generated: {ts}", "=" * 50]
        for a in data.get("action_items", []):
            priority = a.get("priority", "medium").upper()
            owner = a.get("owner", "TBD")
            task = a.get("task", "")
            due = a.get("due_date", "No date")
            lines.append(f"[{priority}] {owner}: {task} (Due: {due})")
        actions_path.write_text("\n".join(lines))

        for i, email in enumerate(data.get("follow_up_emails", [])[:3]):
            email_path = out_dir / f"{slug}_{ts}_email_{i + 1}.txt"
            content = f"TO: {email.get('to', '')}\nSUBJECT: {email.get('subject', '')}\n\n{email.get('body', '')}\n\n- DRAFT - Requires approval before sending -"
            email_path.write_text(content)

    def _read_transcript(self, path: str) -> str:
        p = Path(path)
        ext = p.suffix.lower()
        if ext == ".txt" or ext == ".md":
            return p.read_text(encoding="utf-8", errors="ignore")[:8000]
        elif ext == ".vtt":
            raw = p.read_text(encoding="utf-8", errors="ignore")
            text = re.sub(
                r"\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}", "", raw
            )
            text = re.sub(r"<[^>]+>", "", text)
            return " ".join(text.split())[:8000]
        elif ext == ".srt":
            raw = p.read_text(encoding="utf-8", errors="ignore")
            text = re.sub(
                r"\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n", "", raw
            )
            return " ".join(text.split())[:8000]
        elif ext == ".pdf":
            try:
                from pdfminer.high_level import extract_text

                return extract_text(path)[:8000]
            except ImportError:
                return f"[PDF reading requires: pip install pdfminer.six]"
        return ""

    def _extract_sentences(self, text: str, n: int = 3) -> str:
        sentences = [
            s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20
        ]
        return " ".join(sentences[:n])

    def _extract_action_items_simple(self, text: str) -> List[Dict]:
        actions = []
        patterns = [
            r"(?:action|todo|to-do|task|follow.?up)[:\s]+(.{10,80})",
            r"(?:will|should|needs? to|going to)\s+(.{10,60})",
            r"\[\s*\]\s*(.{10,80})",
        ]
        for pattern in patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                actions.append(
                    {"task": m.group(1).strip(), "owner": "TBD", "priority": "medium"}
                )
        return actions[:10]

    def list_exports(self) -> List[Dict]:
        out_dir = Path("data/exports/meetings")
        if not out_dir.exists():
            return []
        files = []
        for f in sorted(out_dir.iterdir(), reverse=True):
            if f.is_file():
                files.append(
                    {
                        "name": f.name,
                        "path": str(f),
                        "size_kb": round(f.stat().st_size / 1024, 1),
                    }
                )
        return files[:20]
