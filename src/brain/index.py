"""
src/brain/index.py
Business Brain Index - SQLite-backed local index for all
ingested emails, PDFs, WhatsApp messages, vision scans, etc.
"""

import sqlite3
import json
import hashlib
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import List, Dict, Optional, Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS brain_items (
    id             TEXT PRIMARY KEY,
    source         TEXT NOT NULL,
    date           TEXT,
    counterparty   TEXT,
    type           TEXT,
    tags           TEXT DEFAULT '[]',
    summary        TEXT,
    entities       TEXT DEFAULT '{}',
    amounts        TEXT DEFAULT '[]',
    renewal_date   TEXT,
    risk_level     TEXT DEFAULT 'none',
    opportunities  TEXT DEFAULT '[]',
    status         TEXT DEFAULT 'new',
    priority       INTEGER DEFAULT 0,
    linked_ids     TEXT DEFAULT '[]',
    raw_path       TEXT,
    raw_text       TEXT,
    ingested_at    TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_type          ON brain_items(type);
CREATE INDEX IF NOT EXISTS idx_source        ON brain_items(source);
CREATE INDEX IF NOT EXISTS idx_counterparty  ON brain_items(counterparty);
CREATE INDEX IF NOT EXISTS idx_risk_level    ON brain_items(risk_level);
CREATE INDEX IF NOT EXISTS idx_renewal_date  ON brain_items(renewal_date);
CREATE INDEX IF NOT EXISTS idx_status        ON brain_items(status);
CREATE INDEX IF NOT EXISTS idx_ingested_at   ON brain_items(ingested_at);

CREATE TABLE IF NOT EXISTS brain_stats (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


class BrainIndex:
    """Local SQLite Business Brain Index."""

    def __init__(self, db_path: str = "data/brain_index/brain.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _make_id(self, source: str, content: str) -> str:
        return hashlib.sha256(f"{source}:{content}".encode()).hexdigest()[:16]

    def ingest(self, item: Dict[str, Any]) -> str:
        now = datetime.now(UTC).isoformat()
        item_id = item.get("id") or self._make_id(
            item.get("source", ""), item.get("summary", now)
        )

        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO brain_items
                (id, source, date, counterparty, type, tags, summary, entities,
                 amounts, renewal_date, risk_level, opportunities, status,
                 priority, linked_ids, raw_path, raw_text, ingested_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
                (
                    item_id,
                    item.get("source", "manual"),
                    item.get("date"),
                    item.get("counterparty"),
                    item.get("type", "personal"),
                    json.dumps(item.get("tags", [])),
                    item.get("summary", ""),
                    json.dumps(item.get("entities", {})),
                    json.dumps(item.get("amounts", [])),
                    item.get("renewal_date"),
                    item.get("risk_level", "none"),
                    json.dumps(item.get("opportunities", [])),
                    item.get("status", "new"),
                    item.get("priority", 0),
                    json.dumps(item.get("linked_ids", [])),
                    item.get("raw_path"),
                    item.get("raw_text", ""),
                    now,
                    now,
                ),
            )
        return item_id

    def ingest_batch(self, items: List[Dict]) -> List[str]:
        return [self.ingest(item) for item in items]

    def update_status(self, item_id: str, status: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE brain_items SET status=?, updated_at=? WHERE id=?",
                (status, datetime.now(UTC).isoformat(), item_id),
            )

    def all(self, limit: int = 500) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM brain_items ORDER BY ingested_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def by_type(self, item_type: str, limit: int = 100) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM brain_items WHERE type=? ORDER BY ingested_at DESC LIMIT ?",
                (item_type, limit),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def by_risk(self, risk_level: str = "high") -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM brain_items WHERE risk_level=? ORDER BY priority DESC",
                (risk_level,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def renewals_due(self, days: int = 90) -> List[Dict]:
        cutoff = (datetime.now(UTC) + timedelta(days=days)).strftime("%Y-%m-%d")
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM brain_items WHERE renewal_date IS NOT NULL AND renewal_date <= ? ORDER BY renewal_date",
                (cutoff,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def search(self, query: str, limit: int = 50) -> List[Dict]:
        like = f"%{query}%"
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM brain_items
                WHERE summary LIKE ? OR counterparty LIKE ? OR tags LIKE ? OR raw_text LIKE ?
                ORDER BY priority DESC, ingested_at DESC
                LIMIT ?
            """,
                (like, like, like, like, limit),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def stats(self) -> Dict[str, int]:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM brain_items").fetchone()[0]
            emails = conn.execute(
                "SELECT COUNT(*) FROM brain_items WHERE source='email'"
            ).fetchone()[0]
            docs = conn.execute(
                "SELECT COUNT(*) FROM brain_items WHERE source IN ('pdf','whatsapp','vision','folder')"
            ).fetchone()[0]
            high_r = conn.execute(
                "SELECT COUNT(*) FROM brain_items WHERE risk_level='high'"
            ).fetchone()[0]
            renewals = conn.execute(
                "SELECT COUNT(*) FROM brain_items WHERE renewal_date IS NOT NULL"
            ).fetchone()[0]
        return {
            "total": total,
            "emails": emails,
            "docs": docs,
            "high_risk": high_r,
            "with_renewals": renewals,
        }

    def suppliers(self) -> List[Dict]:
        return self.by_type("supplier")

    def legal_items(self) -> List[Dict]:
        return self.by_type("legal")

    def bills(self) -> List[Dict]:
        return self.by_type("bill")

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        d = dict(row)
        for field in ("tags", "entities", "amounts", "opportunities", "linked_ids"):
            try:
                d[field] = json.loads(d.get(field) or "[]")
            except Exception:
                pass
        return d

    def export_json(self, path: str = "data/exports/brain_export.json"):
        items = self.all()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(items, f, indent=2)
        return path
