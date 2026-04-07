"""
src/memory/memory.py
Persistent Memory - cross-session context, proactive suggestions,
and long-term knowledge about the user's business and preferences.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional, Union


MASTER_MEMORY_FILE = Path("data/baba_master_memory.txt")
MASTER_MEMORY_DEFAULT = """# BABA MASTER MEMORY

This file is the canonical local master memory for Baba Desktop.
Rules:
- Keep updates additive.
- Do not overwrite prior approved memory.
- Persist changes locally on this machine.
"""


def _coerce_master_memory_path(path: Optional[Union[str, Path]] = None) -> Path:
    p = Path(path) if path else MASTER_MEMORY_FILE
    return p if p.is_absolute() else Path.cwd() / p


def ensure_master_memory_file(path: Optional[Union[str, Path]] = None) -> Path:
    target = _coerce_master_memory_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(MASTER_MEMORY_DEFAULT, encoding="utf-8")
    return target


def load_master_memory_text(path: Optional[Union[str, Path]] = None) -> str:
    target = ensure_master_memory_file(path)
    try:
        return target.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def append_master_memory_text(
    block: str, path: Optional[Union[str, Path]] = None
) -> Path:
    target = ensure_master_memory_file(path)
    text = (block or "").strip()
    if not text:
        return target
    with target.open("a", encoding="utf-8") as f:
        f.write("\n\n" + text + "\n")
    return target


class Memory:
    """Persistent memory across Baba Desktop sessions."""

    def __init__(self, db_path: str = "data/brain_memory"):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self._mem_file = self.db_path / "memory.json"
        self._use_chroma = False
        self._data: Dict[str, Any] = self._load()
        self._chroma = None
        self._collection = None
        self._try_init_chroma()

    def _try_init_chroma(self):
        try:
            import chromadb

            self._chroma = chromadb.PersistentClient(path=str(self.db_path / "chroma"))
            self._collection = self._chroma.get_or_create_collection("baba_memory")
            self._use_chroma = True
            print("[Memory] ChromaDB vector memory active")
        except ImportError:
            print(
                "[Memory] ChromaDB not installed - using JSON fallback (pip install chromadb)"
            )
        except Exception as e:
            print(f"[Memory] ChromaDB error: {e} - using JSON fallback")

    def remember(
        self, content: str, category: str = "general", metadata: Dict = None
    ) -> str:
        mem_id = hashlib.sha256(
            f"{content}{datetime.now(UTC).isoformat()}".encode()
        ).hexdigest()[:12]
        entry = {
            "id": mem_id,
            "content": content,
            "category": category,
            "metadata": metadata or {},
            "created_at": datetime.now(UTC).isoformat(),
            "recalled": 0,
        }

        self._data.setdefault("memories", {})[mem_id] = entry
        self._save()

        if self._use_chroma and self._collection:
            try:
                self._collection.add(
                    ids=[mem_id],
                    documents=[content],
                    metadatas=[{"category": category, **(metadata or {})}],
                )
            except Exception:
                pass

        return mem_id

    def remember_knowledge(
        self,
        topic: str,
        content: str,
        source: str = "manual",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        payload = {
            "topic": topic,
            "source": source,
            "tags": tags or [],
            **(metadata or {}),
        }
        body = f"Knowledge Topic: {topic}\n{content}"
        return self.remember(body, category="knowledge", metadata=payload)

    def update_preference(self, key: str, value: Any):
        self._data.setdefault("preferences", {})[key] = {
            "value": value,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        self._save()

    def record_decision(self, decision: str, outcome: str = "", context: str = ""):
        self.remember(
            content=f"Decision: {decision}\nOutcome: {outcome}\nContext: {context}",
            category="decision",
            metadata={"decision": decision, "outcome": outcome},
        )

    def record_approval(self, action: str, approved: bool, details: str = ""):
        self._data.setdefault("approval_patterns", []).append(
            {
                "action": action,
                "approved": approved,
                "details": details,
                "ts": datetime.now(UTC).isoformat(),
            }
        )
        self._data["approval_patterns"] = self._data["approval_patterns"][-200:]
        self._save()

    def recall(self, query: str, limit: int = 5) -> List[Dict]:
        if self._use_chroma and self._collection:
            try:
                results = self._collection.query(
                    query_texts=[query], n_results=min(limit, 10)
                )
                ids = results.get("ids", [[]])[0]
                mems = []
                for mid in ids:
                    m = self._data.get("memories", {}).get(mid)
                    if m:
                        m["recalled"] += 1
                        mems.append(m)
                self._save()
                return mems
            except Exception:
                pass

        memories = list(self._data.get("memories", {}).values())
        q = query.lower()
        scored = [
            (m, sum(1 for w in q.split() if w in m.get("content", "").lower()))
            for m in memories
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [m for m, score in scored[:limit] if score > 0]

    def get_preferences(self) -> Dict:
        return {k: v["value"] for k, v in self._data.get("preferences", {}).items()}

    def knowledge_items(self, limit: int = 20) -> List[Dict]:
        items = [
            m
            for m in self._data.get("memories", {}).values()
            if m.get("category") == "knowledge"
        ]
        items.sort(key=lambda m: m.get("created_at", ""), reverse=True)
        return items[:limit]

    def search_by_category(
        self, category: str, query: str = "", limit: int = 10
    ) -> List[Dict]:
        items = [
            m
            for m in self._data.get("memories", {}).values()
            if m.get("category") == category
        ]
        if not query.strip():
            items.sort(key=lambda m: m.get("created_at", ""), reverse=True)
            return items[:limit]
        q = query.lower()
        scored = [
            (
                m,
                sum(1 for w in q.split() if w in m.get("content", "").lower()),
            )
            for m in items
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [m for m, score in scored[:limit] if score > 0]

    def get_context_summary(self) -> str:
        prefs = self.get_preferences()
        recent = sorted(
            self._data.get("memories", {}).values(),
            key=lambda m: m["created_at"],
            reverse=True,
        )[:5]
        decisions = [
            m
            for m in self._data.get("memories", {}).values()
            if m.get("category") == "decision"
        ][-3:]

        lines = ["=== Persistent Memory Context ==="]

        if prefs:
            lines.append("User preferences:")
            for k, v in list(prefs.items())[:5]:
                lines.append(f"  {k}: {v}")

        if recent:
            lines.append("Recent memories:")
            for m in recent:
                lines.append(f"  [{m['category']}] {m['content'][:80]}")

        if decisions:
            lines.append("Recent decisions:")
            for d in decisions:
                lines.append(f"  {d['content'][:80]}")

        patterns = self._data.get("approval_patterns", [])
        always_approved = set()
        for p in patterns:
            if p.get("approved"):
                always_approved.add(p["action"])
        if always_approved:
            lines.append(
                f"Auto-approved actions: {', '.join(list(always_approved)[:5])}"
            )

        return "\n".join(lines)

    def proactive_suggestions(self) -> List[str]:
        suggestions = []
        memories = list(self._data.get("memories", {}).values())

        renewal_mems = [
            m for m in memories if "renewal" in m.get("content", "").lower()
        ]
        if renewal_mems:
            suggestions.append("You have upcoming renewals - want me to check them?")

        legal_mems = [m for m in memories if "legal" in m.get("category", "")]
        if legal_mems:
            suggestions.append(
                "There are unresolved legal items in your index - shall I review?"
            )

        pending = [
            m for m in memories if "awaiting approval" in m.get("content", "").lower()
        ]
        if pending:
            suggestions.append(f"{len(pending)} drafts are awaiting your approval")

        return suggestions[:3]

    def clear(self, category: str = None):
        if category:
            self._data["memories"] = {
                k: v
                for k, v in self._data.get("memories", {}).items()
                if v.get("category") != category
            }
        else:
            self._data["memories"] = {}
        self._save()

    def stats(self) -> Dict:
        return {
            "total_memories": len(self._data.get("memories", {})),
            "preferences": len(self._data.get("preferences", {})),
            "decisions": sum(
                1
                for m in self._data.get("memories", {}).values()
                if m.get("category") == "decision"
            ),
            "knowledge": sum(
                1
                for m in self._data.get("memories", {}).values()
                if m.get("category") == "knowledge"
            ),
            "approval_patterns": len(self._data.get("approval_patterns", [])),
            "chroma_active": self._use_chroma,
        }

    def get_master_memory(self, path: Optional[Union[str, Path]] = None) -> str:
        return load_master_memory_text(path)

    def append_master_memory(self, block: str, path: Optional[Union[str, Path]] = None):
        append_master_memory_text(block, path)

    def _load(self) -> Dict:
        if self._mem_file.exists():
            try:
                return json.loads(self._mem_file.read_text())
            except Exception:
                pass
        return {"memories": {}, "preferences": {}, "approval_patterns": []}

    def _save(self):
        self._mem_file.write_text(json.dumps(self._data, indent=2))
