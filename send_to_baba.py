#!/usr/bin/env python3
"""Send file/text context into Baba Desktop via local API."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path


def post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", errors="ignore"))


def main() -> int:
    api = os.getenv("BABA_INGEST_API", "http://localhost:8080/api/context/ingest")
    args = sys.argv[1:]
    if not args:
        print("Usage: send_to_baba.py <file-path-or-text>")
        return 1

    value = " ".join(args).strip().strip('"')
    p = Path(value)
    if p.exists():
        payload = {
            "source": "windows_context_menu",
            "kind": "file",
            "path": str(p.resolve()),
            "dispatch": True,
        }
    else:
        payload = {
            "source": "windows_context_menu",
            "kind": "text",
            "text": value,
            "dispatch": True,
        }

    try:
        result = post_json(api, payload)
        if result.get("ok"):
            print(
                f"Sent to Baba: item_id={result.get('item_id')} type={result.get('type')} "
                f"task={result.get('queued_task_id', '')}"
            )
            return 0
        print(f"Baba ingest failed: {result}")
        return 2
    except Exception as e:
        print(f"Cannot reach Baba API at {api}: {e}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
