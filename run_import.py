#!/usr/bin/env python3
"""
run_import.py — Import emails, WhatsApp, PDFs into the Business Brain Index.

Usage:
    python run_import.py emails   /path/to/emails/folder
    python run_import.py whatsapp /path/to/WhatsApp Export.zip
    python run_import.py pdfs     /path/to/pdfs/folder
    python run_import.py folder   /path/to/watch/folder
    python run_import.py stats    (show current index stats)
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings
from src.brain.index import BrainIndex
from src.brain.importers import EmailImporter, WhatsAppImporter, PDFImporter, FolderWatcher


def main():
    settings = Settings.load()
    brain    = BrainIndex(settings.brain_db_path)

    if len(sys.argv) < 2 or sys.argv[1] == "stats":
        stats = brain.stats()
        print("\n Business Brain Index — Stats")
        print("─" * 40)
        for k, v in stats.items():
            print(f"  {k:<20} {v}")
        print("─" * 40)
        renewals = brain.renewals_due(90)
        print(f"\n  Renewals due in 90 days: {len(renewals)}")
        for r in renewals[:5]:
            print(f"    • {r['summary'][:50]} — {r['renewal_date']}")
        high_risk = brain.by_risk("high")
        print(f"\n  High-risk items: {len(high_risk)}")
        for r in high_risk[:3]:
            print(f"    ⚠ {r['summary'][:60]}")
        return

    mode = sys.argv[1].lower()
    path = sys.argv[2] if len(sys.argv) > 2 else None

    if not path:
        print(f"Usage: python run_import.py {mode} <path>")
        sys.exit(1)

    if mode == "emails":
        imp   = EmailImporter()
        print(f"\nImporting emails from {path}…")
        items = imp.import_directory(path)
        ids   = brain.ingest_batch(items)
        print(f"Indexed {len(ids)} emails")

    elif mode == "whatsapp":
        imp = WhatsAppImporter()
        print(f"\nImporting WhatsApp export from {path}…")
        if path.endswith(".zip"):
            items = imp.import_zip(path)
        else:
            items = imp.import_txt(path)
        ids = brain.ingest_batch(items)
        print(f"Indexed {len(ids)} conversation threads")

    elif mode == "pdfs":
        imp   = PDFImporter()
        print(f"\nImporting PDFs from {path}…")
        items = imp.import_directory(path)
        ids   = brain.ingest_batch(items)
        print(f"Indexed {len(ids)} PDFs")

    elif mode == "folder":
        watcher = FolderWatcher(brain, [path])
        print(f"\nScanning folder: {path}…")
        count = watcher.scan_once()
        print(f"Indexed {count} new items")

    else:
        print(f"Unknown mode: {mode}")
        print("Modes: emails, whatsapp, pdfs, folder, stats")
        sys.exit(1)

    # Show updated stats
    stats = brain.stats()
    print(f"\n Updated Brain Index: {stats['total']} total items")


if __name__ == "__main__":
    main()
