"""
src/knowledge/wiki.py
Karpathy-style LLM Wiki compiler and maintainer.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional


class WikiCompiler:
    """
    File-first, persistent knowledge compiler:
    - raw/ for ingested sources
    - wiki/ for maintained markdown pages
    - lint + health checks for link integrity
    """

    TEXT_EXTS = {".md", ".txt", ".json", ".csv", ".py", ".js", ".ts", ".html", ".css"}

    def __init__(self, root_dir: str = "data/wiki", brain=None, pool=None):
        self.root = Path(root_dir)
        self.raw_dir = self.root / "raw"
        self.wiki_dir = self.root / "wiki"
        self.pages_dir = self.wiki_dir / "pages"
        self.index_dir = self.wiki_dir / "index"
        self.meta_dir = self.root / "meta"
        self.brain = brain
        self.pool = pool

        for d in (self.root, self.raw_dir, self.wiki_dir, self.pages_dir, self.index_dir, self.meta_dir):
            d.mkdir(parents=True, exist_ok=True)

        self.state_file = self.meta_dir / "state.json"
        self.state = self._load_state()

    def ingest_files(self, paths: List[str], source_tag: str = "manual") -> Dict[str, Any]:
        copied = []
        for p in paths:
            src = Path(p)
            if not src.exists() or src.is_dir():
                continue
            ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            safe_name = f"{ts}_{self._slug(src.stem)}{src.suffix.lower()}"
            dest = self.raw_dir / safe_name
            dest.write_bytes(src.read_bytes())
            copied.append(str(dest))
        evt = {
            "ts": datetime.now(UTC).isoformat(),
            "event": "ingest",
            "source_tag": source_tag,
            "count": len(copied),
            "paths": copied,
        }
        self._append_log(evt)
        return {"ok": True, "ingested": copied, "count": len(copied)}

    def compile_once(self, topic_hint: str = "") -> Dict[str, Any]:
        docs = self._read_raw_documents(limit=250)
        if not docs:
            return {"ok": True, "message": "No raw docs to compile", "pages_written": 0}

        summaries = []
        for doc in docs:
            summaries.append(
                {
                    "title": doc["title"],
                    "path": doc["path"],
                    "summary": self._summarize_text(doc["text"], max_sentences=5),
                    "keywords": self._keywords(doc["text"]),
                }
            )

        landing = self._build_landing_page(summaries, topic_hint)
        (self.wiki_dir / "README.md").write_text(landing, encoding="utf-8")

        page_count = 0
        for item in summaries:
            slug = self._slug(item["title"])[:80] or "untitled"
            p = self.pages_dir / f"{slug}.md"
            lines = [
                f"# {item['title']}",
                "",
                f"Source: `{item['path']}`",
                f"Updated: {datetime.now(UTC).isoformat()}",
                "",
                "## Summary",
                item["summary"] or "No summary available.",
                "",
                "## Keywords",
                ", ".join(item["keywords"][:20]),
                "",
                "## Backlinks",
                "- [[README]]",
            ]
            p.write_text("\n".join(lines), encoding="utf-8")
            page_count += 1

        concept_pages = self._write_concept_pages(summaries)
        lint = self.lint()
        self.state["last_compile_at"] = datetime.now(UTC).isoformat()
        self.state["last_compile_pages"] = page_count + concept_pages
        self._save_state()
        self._append_log(
            {
                "ts": datetime.now(UTC).isoformat(),
                "event": "compile",
                "topic_hint": topic_hint,
                "source_docs": len(summaries),
                "pages_written": page_count,
                "concept_pages_written": concept_pages,
                "lint": lint,
            }
        )
        return {
            "ok": True,
            "source_docs": len(summaries),
            "pages_written": page_count,
            "concept_pages_written": concept_pages,
            "lint": lint,
            "wiki_root": str(self.wiki_dir),
        }

    def lint(self) -> Dict[str, Any]:
        pages = list(self.pages_dir.glob("*.md")) + [self.wiki_dir / "README.md"]
        existing = {p.stem for p in pages if p.exists()}
        broken = []
        orphan = []
        link_pattern = re.compile(r"\[\[([^\]]+)\]\]")
        inbound: Dict[str, int] = {k: 0 for k in existing}

        for p in pages:
            if not p.exists():
                continue
            txt = p.read_text(encoding="utf-8", errors="ignore")
            links = [m.group(1).strip() for m in link_pattern.finditer(txt)]
            for target in links:
                target_stem = Path(target).stem
                if target_stem not in existing:
                    broken.append({"page": p.name, "target": target})
                else:
                    inbound[target_stem] = inbound.get(target_stem, 0) + 1

        for stem, count in inbound.items():
            if stem.lower() != "readme" and count == 0:
                orphan.append(stem)

        report = {
            "ok": True,
            "pages": len(existing),
            "broken_links": broken,
            "orphan_pages": orphan,
        }
        (self.meta_dir / "lint_latest.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        return report

    def stats(self) -> Dict[str, Any]:
        raw_count = len([p for p in self.raw_dir.iterdir() if p.is_file()])
        page_count = len(list(self.pages_dir.glob("*.md")))
        return {
            "raw_docs": raw_count,
            "wiki_pages": page_count,
            "last_compile_at": self.state.get("last_compile_at"),
            "last_compile_pages": self.state.get("last_compile_pages", 0),
            "root": str(self.root),
        }

    def suggest_tasks(self) -> List[Dict[str, str]]:
        lint = self.lint()
        tasks = []
        if lint["broken_links"]:
            tasks.append({"task": "Fix broken wiki links", "priority": "high"})
        if lint["orphan_pages"]:
            tasks.append({"task": "Integrate orphan pages into index", "priority": "medium"})
        if not tasks:
            tasks.append({"task": "Run weekly wiki maintenance compile", "priority": "low"})
        return tasks

    def _read_raw_documents(self, limit: int = 250) -> List[Dict[str, str]]:
        docs = []
        for p in sorted(self.raw_dir.iterdir(), reverse=True):
            if not p.is_file():
                continue
            if p.suffix.lower() in self.TEXT_EXTS:
                txt = p.read_text(encoding="utf-8", errors="ignore")
            else:
                # Keep binary assets indexed by filename metadata.
                txt = f"Binary asset: {p.name}"
            docs.append({"title": p.stem, "path": str(p), "text": txt[:30000]})
            if len(docs) >= limit:
                break
        return docs

    def _build_landing_page(self, summaries: List[Dict[str, Any]], topic_hint: str) -> str:
        title = topic_hint.strip() or "LLM Wiki"
        lines = [
            f"# {title}",
            "",
            f"Generated: {datetime.now(UTC).isoformat()}",
            "",
            "## Sources",
        ]
        for s in summaries[:200]:
            page = self._slug(s["title"])[:80] or "untitled"
            lines.append(f"- [[{page}]] - `{s['path']}`")
        lines.extend(
            [
                "",
                "## Concepts",
                "Concept pages are in `wiki/index/` and are auto-maintained.",
            ]
        )
        return "\n".join(lines)

    def _write_concept_pages(self, summaries: List[Dict[str, Any]]) -> int:
        keyword_map: Dict[str, List[str]] = {}
        for s in summaries:
            page = self._slug(s["title"])[:80] or "untitled"
            for kw in s["keywords"][:20]:
                keyword_map.setdefault(kw, []).append(page)

        count = 0
        for kw, pages in sorted(keyword_map.items(), key=lambda x: len(x[1]), reverse=True)[:150]:
            p = self.index_dir / f"{self._slug(kw)}.md"
            unique_pages = sorted(set(pages))[:120]
            lines = [
                f"# Concept: {kw}",
                "",
                f"Updated: {datetime.now(UTC).isoformat()}",
                "",
                "## Related Pages",
            ]
            lines.extend([f"- [[{pp}]]" for pp in unique_pages])
            p.write_text("\n".join(lines), encoding="utf-8")
            count += 1
        return count

    def _summarize_text(self, text: str, max_sentences: int = 5) -> str:
        # Deterministic summary fallback (works offline without cloud dependencies).
        parts = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
        parts = [p.strip() for p in parts if len(p.strip()) > 30]
        return " ".join(parts[:max_sentences])[:1400]

    def _keywords(self, text: str) -> List[str]:
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9_\-]{3,}", text.lower())
        stop = {
            "this",
            "that",
            "with",
            "from",
            "have",
            "into",
            "your",
            "their",
            "there",
            "about",
            "would",
            "could",
            "should",
            "these",
            "those",
            "which",
            "what",
            "when",
            "where",
            "while",
            "because",
            "been",
            "being",
        }
        freq: Dict[str, int] = {}
        for w in words:
            if w in stop:
                continue
            freq[w] = freq.get(w, 0) + 1
        return [w for w, _ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:35]]

    def _slug(self, s: str) -> str:
        out = re.sub(r"[^a-zA-Z0-9_\-]+", "_", s.strip().lower())
        return re.sub(r"_+", "_", out).strip("_")

    def _load_state(self) -> Dict[str, Any]:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"created_at": datetime.now(UTC).isoformat()}

    def _save_state(self):
        self.state_file.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def _append_log(self, event: Dict[str, Any]):
        log_file = self.meta_dir / "events.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

