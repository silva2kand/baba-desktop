#!/usr/bin/env python3
"""
setup.py — Baba Desktop Business Brain OS v9 — ULTIMATE MERGED EDITION
One-shot setup: creates directories, installs dependencies, checks local AI, creates shortcuts.
Run: python setup.py
"""

import os
import sys
import subprocess
import json
import urllib.request
from pathlib import Path

BANNER = """
╔══════════════════════════════════════════════════════════╗
║     Baba Desktop — Business Brain OS v9 — Setup          ║
║     ULTIMATE MERGED EDITION — Everything Connected       ║
╚══════════════════════════════════════════════════════════╝
"""

DIRS = [
    "data/brain_index",
    "data/exports",
    "data/imports/bills",
    "data/imports/contracts",
    "data/imports/emails",
    "data/imports/pdfs",
    "data/screenshots",
    "data/claws",
    "logs",
    "src/tools_experimental",
    "src/claws/installed",
    "config",
    "assets",
]

CORE_PACKAGES = [
    "httpx",
    "websockets",
    "Pillow",
    "python-dotenv",
    "rich",
    "aiofiles",
]

OPTIONAL_PACKAGES = {
    "FastAPI (REST server)": ["fastapi", "uvicorn"],
    "PDF reading": ["pdfminer.six"],
    "PC Control": ["pyautogui", "pytesseract"],
    "Browser automation": ["playwright"],
    "Excel read/write": ["openpyxl"],
    "Word doc reading": ["python-docx"],
    "PDF handling": ["pypdf2"],
    "Web scraping": ["beautifulsoup4", "lxml"],
    "Folder watching": ["watchdog"],
    "Vector memory": ["chromadb"],
    "Task scheduling": ["schedule"],
    "CLI interface": ["click"],
}


def run(cmd: str, check: bool = False) -> int:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}")
    return result.returncode


def check_local_ai():
    """Check which local AI servers are running."""
    print("\n  Checking local AI providers...")
    checks = {
        "Ollama": "http://localhost:11434/api/tags",
        "Jan": "http://localhost:1337/v1/models",
        "LM Studio": "http://localhost:1234/v1/models",
    }
    results = {}
    for name, url in checks.items():
        try:
            urllib.request.urlopen(url, timeout=2)
            print(f"    ✓ {name} — online")
            results[name] = True
        except Exception:
            print(f"    ✗ {name} — not running (start it before using Baba)")
            results[name] = False
    return results


def create_env_template():
    """Create .env template for API keys."""
    env_path = Path(".env")
    if env_path.exists():
        print("  .env already exists — skipping")
        return
    env_path.write_text(
        """# Baba Desktop — API Keys
# Free keys available at:
#   Groq:        https://console.groq.com
#   Gemini:      https://aistudio.google.com
#   OpenRouter:  https://openrouter.ai
#   Qwen:        https://dashscope.console.aliyun.com
#   HuggingFace: https://huggingface.co/settings/tokens

GROQ_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
QWEN_API_KEY=
HF_TOKEN=
""",
        encoding="utf-8",
    )
    print("  Created .env — add your API keys there")


def create_gitignore():
    Path(".gitignore").write_text(
        """# Baba Desktop
.env
__pycache__/
*.pyc
*.pyo
*.db
*.db-journal
*.db-shm
*.db-wal
data/brain_index/*.db
data/exports/
logs/*.jsonl
logs/*.log
src/claws/installed/
node_modules/
.DS_Store
.venv/
"""
    )


def create_windows_shortcuts():
    """Create desktop and Start Menu shortcuts on Windows."""
    if os.name != "nt":
        return []

    launcher = (Path.cwd() / "start_windows.bat").resolve()
    if not launcher.exists():
        print("  start_windows.bat not found — skipping shortcut creation")
        return []

    desktop_dir = Path.home() / "Desktop"
    start_menu_dir = (
        Path(os.environ.get("APPDATA", ""))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
    )
    shortcut_targets = [
        desktop_dir / "Baba Desktop.lnk",
        start_menu_dir / "Baba Desktop.lnk",
    ]

    created = []
    for shortcut_path in shortcut_targets:
        shortcut_path.parent.mkdir(parents=True, exist_ok=True)
        sp = str(shortcut_path).replace("'", "''")
        lp = str(launcher).replace("'", "''")
        ld = str(launcher.parent).replace("'", "''")
        ps_command = (
            "$shell = New-Object -ComObject WScript.Shell; "
            f"$shortcut = $shell.CreateShortcut('{sp}'); "
            f"$shortcut.TargetPath = '{lp}'; "
            f"$shortcut.WorkingDirectory = '{ld}'; "
            "$shortcut.IconLocation = '%SystemRoot%\\System32\\SHELL32.dll,220'; "
            "$shortcut.Save()"
        )
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_command,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            created.append(shortcut_path)
        else:
            err = result.stderr.strip() or result.stdout.strip() or "unknown error"
            print(f"  Shortcut creation failed for {shortcut_path.name}: {err}")
    return created


def main():
    print(BANNER)

    # 1. Create directories
    print("  Creating directories...")
    for d in DIRS:
        Path(d).mkdir(parents=True, exist_ok=True)
    print(f"  Created {len(DIRS)} directories")

    # 2. Create __init__.py files
    for pkg in [
        "src",
        "src/agents",
        "src/brain",
        "src/providers",
        "src/tools",
        "src/tools_experimental",
        "src/vision",
        "src/pc_bridge",
        "src/app_bridge",
        "src/claws",
        "src/cowork",
        "src/memory",
        "src/dispatch",
        "src/scheduler",
        "src/devtools",
        "src/meetings",
        "src/chrome",
        "src/browser",
        "src/whatsapp",
        "config",
    ]:
        init = Path(pkg) / "__init__.py"
        if not init.exists():
            init.write_text("")

    # 3. Install core packages
    print("\n  Installing core packages...")
    for pkg in CORE_PACKAGES:
        rc = run(f'"{sys.executable}" -m pip install {pkg} -q')
        status = "✓" if rc == 0 else "✗"
        print(f"    {status} {pkg}")

    # 4. Optional packages
    print("\n  Optional package groups (y/n to install each):")
    for group, packages in OPTIONAL_PACKAGES.items():
        try:
            choice = (
                input(f"    Install {group}? [{', '.join(packages)}] (y/n): ")
                .strip()
                .lower()
            )
        except (EOFError, KeyboardInterrupt):
            choice = "n"
        if choice == "y":
            for pkg in packages:
                rc = run(f'"{sys.executable}" -m pip install {pkg} -q')
                print(f"    {'✓' if rc == 0 else '✗'} {pkg}")
            if "playwright" in packages:
                run(f'"{sys.executable}" -m playwright install chromium')

    # 5. Create .env and .gitignore
    print("\n  Creating config files...")
    create_env_template()
    create_gitignore()

    # 6. Create Windows shortcuts
    shortcuts = []
    if os.name == "nt":
        print("\n  Creating Windows shortcuts...")
        shortcuts = create_windows_shortcuts()
        if shortcuts:
            for shortcut in shortcuts:
                print(f"    ✓ {shortcut}")
        else:
            print("    No shortcuts created")

    # 7. Check local AI
    ai_status = check_local_ai()

    # 8. Summary
    print("\n" + "=" * 62)
    print("  Setup complete!")
    print("=" * 62)
    online = [k for k, v in ai_status.items() if v]
    if online:
        print(f"  Local AI online: {', '.join(online)}")
    else:
        print("  No local AI detected — start Ollama, Jan, or LM Studio")
    if shortcuts:
        print("  Shortcuts ready:")
        for shortcut in shortcuts:
            print(f"    {shortcut}")
    print("\n  Next steps:")
    print("  1. Add API keys to .env (Groq/Gemini are free)")
    print("  2. Start your local AI (ollama serve)")
    print("  3. Start Baba Desktop:")
    print("     python main.py")
    print("     or double-click start_windows.bat")
    print("=" * 62)


if __name__ == "__main__":
    main()
