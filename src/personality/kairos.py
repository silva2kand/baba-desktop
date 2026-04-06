"""
src/personality/kairos.py
Kairos-style behavioral memory and growth signals.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from datetime import datetime, UTC
from typing import Dict, Any, List


class KairosMemory:
    """Track user interaction signals and generate adaptive style guidance."""

    def __init__(self, path: str = "data/personality/kairos_profile.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def record_interaction(self, user_text: str, assistant_text: str = "") -> Dict[str, Any]:
        signal = self._extract_signal(user_text)
        signal["assistant_excerpt"] = assistant_text[:240]
        signal["ts"] = datetime.now(UTC).isoformat()
        self.data.setdefault("history", []).append(signal)
        self._apply_signal(signal)
        self._save()
        return {"ok": True, "signal": signal}

    def build_prompt_context(self) -> str:
        pref = self.data.get("preferences", {})
        tone = pref.get("tone", "professional")
        verbosity = pref.get("verbosity", "balanced")
        strictness = pref.get("strictness", "high")
        directives = self.data.get("directives", [])
        lines = [
            "Kairos profile guidance:",
            f"- Preferred tone: {tone}",
            f"- Preferred verbosity: {verbosity}",
            f"- Feature strictness: {strictness}",
        ]
        if directives:
            lines.append("- Standing directives:")
            lines.extend([f"  - {d}" for d in directives[-8:]])
        return "\n".join(lines)

    def stats(self) -> Dict[str, Any]:
        hist = self.data.get("history", [])
        pref = self.data.get("preferences", {})
        return {
            "signals": len(hist),
            "tone": pref.get("tone", "professional"),
            "verbosity": pref.get("verbosity", "balanced"),
            "strictness": pref.get("strictness", "high"),
            "directives_count": len(self.data.get("directives", [])),
            "last_updated": self.data.get("last_updated"),
        }

    def recent_signals(self, limit: int = 20) -> List[Dict[str, Any]]:
        return list(self.data.get("history", []))[-limit:]

    def _extract_signal(self, text: str) -> Dict[str, Any]:
        t = text.strip()
        low = t.lower()
        signal = {
            "text": t[:1200],
            "type": "general",
            "intensity": 0.4,
            "tags": [],
        }
        if any(k in low for k in ("don't remove", "do not remove", "keep all", "must have", "dont miss", "no dummy", "no placeholder")):
            signal["type"] = "constraint"
            signal["intensity"] = 0.95
            signal["tags"].append("feature-preservation")
        if any(k in low for k in ("short answer", "quick answer", "brief")):
            signal["type"] = "preference"
            signal["tags"].append("verbosity-short")
        if any(k in low for k in ("full", "detailed", "step-by-step", "all everything")):
            signal["type"] = "preference"
            signal["tags"].append("verbosity-detailed")
            signal["intensity"] = max(signal["intensity"], 0.75)
        if any(k in low for k in ("friendly", "kind", "supportive")):
            signal["tags"].append("tone-warm")
        if "approval" in low:
            signal["tags"].append("approval-gating")
        return signal

    def _apply_signal(self, signal: Dict[str, Any]):
        pref = self.data.setdefault("preferences", {})
        directives = self.data.setdefault("directives", [])
        tags = signal.get("tags", [])
        if "verbosity-short" in tags:
            pref["verbosity"] = "short"
        if "verbosity-detailed" in tags:
            pref["verbosity"] = "detailed"
        if "tone-warm" in tags:
            pref["tone"] = "warm-professional"
        if signal.get("type") == "constraint" and signal.get("intensity", 0) >= 0.9:
            pref["strictness"] = "very-high"
            text = signal.get("text", "")
            # Keep only concise directive text.
            directive = re.sub(r"\s+", " ", text).strip()[:220]
            if directive and directive not in directives:
                directives.append(directive)
        self.data["last_updated"] = datetime.now(UTC).isoformat()

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "created_at": datetime.now(UTC).isoformat(),
            "preferences": {
                "tone": "professional",
                "verbosity": "balanced",
                "strictness": "high",
            },
            "directives": [],
            "history": [],
        }

    def _save(self):
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

