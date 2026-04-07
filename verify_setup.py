#!/usr/bin/env python3
"""
verify_setup.py — Comprehensive verification of Baba Desktop v9 setup.
Checks all local AI providers, models, services, and dependencies.
"""

import sys
import json
import socket
import subprocess
from pathlib import Path
from datetime import datetime, UTC

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings


def check_port(port, service_name):
    """Check if a port is open."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(("localhost", port))
        s.close()
        return result == 0
    except Exception:
        return False


def check_ollama_models():
    """Check installed Ollama models."""
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[1:]
            models = []
            for line in lines:
                if line.strip() and not line.startswith("NAME"):
                    parts = line.split()
                    if parts:
                        models.append(parts[0])
            return models
    except Exception:
        pass
    return []


def check_jan_models():
    """Check Jan AI models via API."""
    import urllib.request

    try:
        with urllib.request.urlopen("http://localhost:1337/v1/models", timeout=3) as r:
            data = json.loads(r.read())
            return [m.get("id", m.get("name", "")) for m in data.get("data", [])]
    except Exception:
        return []


def check_lmstudio_models():
    """Check LM Studio models via API."""
    import urllib.request

    try:
        with urllib.request.urlopen("http://localhost:1234/v1/models", timeout=3) as r:
            data = json.loads(r.read())
            return [m.get("id", m.get("name", "")) for m in data.get("data", [])]
    except Exception:
        return []


def check_dependencies():
    """Check if required Python packages are installed."""
    required = {
        "httpx": "httpx",
        "websockets": "websockets",
        "Pillow": "PIL",
        "python-dotenv": "dotenv",
        "rich": "rich",
    }
    optional = {
        "FastAPI/uvicorn (REST server)": {"fastapi": "fastapi", "uvicorn": "uvicorn"},
        "PDF reading": {"pdfminer.six": "pdfminer", "PyPDF2": "PyPDF2"},
        "PC Control": {"pyautogui": "pyautogui", "pytesseract": "pytesseract"},
        "Browser automation": ["playwright"],
        "Excel": ["openpyxl"],
        "Word docs": ["docx"],
        "Web scraping": ["bs4", "lxml"],
        "Vector memory": ["chromadb"],
        "Folder watching": ["watchdog"],
        "Task scheduling": ["schedule"],
    }

    optional_status = {}
    import importlib
    import importlib.util

    installed = {}
    for pkg_name, module_name in required.items():
        installed[pkg_name] = importlib.util.find_spec(module_name) is not None

    for group, pkgs in optional.items():
        if isinstance(pkgs, dict):
            specs = pkgs.values()
        else:
            specs = [p.replace("-", "_") for p in pkgs]
        optional_status[group] = all(importlib.util.find_spec(spec) is not None for spec in specs)

    return installed, optional_status


def main():
    print("=" * 70)
    print("  Baba Desktop Business Brain OS v9 — Setup Verification")
    print(f"  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Load config
    settings = Settings.load()

    # Check local AI providers
    print("\n[AI] Local AI Providers:")
    print("-" * 70)

    ollama_online = check_port(11434, "Ollama")
    jan_online = check_port(1337, "Jan")
    lmstudio_online = check_port(1234, "LM Studio")

    print(f"  Ollama (11434):    {'ONLINE' if ollama_online else 'OFFLINE'}")
    print(f"  Jan (1337):        {'ONLINE' if jan_online else 'OFFLINE'}")
    print(f"  LM Studio (1234):  {'ONLINE' if lmstudio_online else 'OFFLINE'}")

    # Check models
    if ollama_online:
        models = check_ollama_models()
        print(f"\n  Ollama Models ({len(models)}):")
        for m in models[:8]:
            print(f"    - {m}")
        if len(models) > 8:
            print(f"    ... and {len(models) - 8} more")

    if jan_online:
        models = check_jan_models()
        print(f"\n  Jan Models ({len(models)}):")
        for m in models[:6]:
            print(f"    - {m}")

    if lmstudio_online:
        models = check_lmstudio_models()
        print(f"\n  LM Studio Models ({len(models)}):")
        for m in models[:6]:
            print(f"    - {m}")

    # Check services ports
    print("\n\n[PORTS] Service Ports:")
    print("-" * 70)
    services = {
        8765: "PC Bridge (WebSocket)",
        8767: "Dispatch API (HTTP)",
        8768: "Chrome Connector (HTTP)",
        8080: "UI Server (HTTP)",
    }
    for port, name in services.items():
        status = check_port(port, name)
        print(f"  {name:30} :{port}  {'OK' if status else '  '}")

    # Check Brain Index
    print("\n\n[BRAIN] Brain Index:")
    print("-" * 70)
    try:
        from src.brain.index import BrainIndex

        brain = BrainIndex(settings.brain_db_path)
        stats = brain.stats()
        print(f"  Database: {settings.brain_db_path}")
        print(f"  Total items: {stats.get('total', 0)}")
        print(f"  By type: {json.dumps(stats.get('by_type', {}), indent=4)}")
        print(f"  High-risk: {stats.get('high_risk', 0)}")
        print(f"  With renewals: {stats.get('with_renewals', 0)}")
    except Exception as e:
        print(f"  ⚠ Brain Index check failed: {e}")

    # Check dependencies
    print("\n\n[DEPS] Dependencies:")
    print("-" * 70)
    required, optional = check_dependencies()

    print("  Required:")
    for pkg, status in required.items():
        print(f"    {'OK' if status else 'MISSING'} {pkg}")

    print("\n  Optional:")
    for group, status in optional.items():
        print(f"    {'OK' if status else '     '} {group}")

    # Check directories
    print("\n\n[DIRS] Directories:")
    print("-" * 70)
    dirs = [
        "data/brain_index",
        "data/exports",
        "data/imports/bills",
        "data/imports/contracts",
        "data/imports/emails",
        "data/imports/pdfs",
        "data/screenshots",
        "data/claws",
        "logs",
        "src/claws/installed",
    ]
    for d in dirs:
        path = Path(d)
        exists = path.exists()
        print(f"    {'OK' if exists else 'MISSING'} {d}")

    # Summary
    print("\n\n" + "=" * 70)
    print("  VERIFICATION COMPLETE")
    print("=" * 70)

    issues = []
    if not ollama_online and not jan_online and not lmstudio_online:
        issues.append("No local AI providers online — start Ollama, Jan, or LM Studio")

    missing_required = [pkg for pkg, status in required.items() if not status]
    if missing_required:
        issues.append(f"Missing required packages: {', '.join(missing_required)}")

    if issues:
        print("\n  WARNING — ISSUES FOUND:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("\n  ALL OK — All systems operational!")

    print("\n  Quick start:")
    print("    python main.py              # Start everything + GUI")
    print("    python run_cowork.py        # Run autonomous tasks")
    print("    python run_agent.py legal   # Run domain agent")
    print("    python run_import.py stats  # View brain stats")
    print("=" * 70)


if __name__ == "__main__":
    main()
