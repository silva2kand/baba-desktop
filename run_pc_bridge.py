#!/usr/bin/env python3
"""
run_pc_bridge.py
Quick launcher for the Baba Desktop PC Control Bridge.

Usage:
    python run_pc_bridge.py [--port 8765] [--no-safe-mode]

The bridge must be running for PC Control features to work.
Baba connects to it automatically on startup.
"""

import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.pc_bridge.bridge import PCBridge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)

parser = argparse.ArgumentParser(description="Baba Desktop PC Control Bridge")
parser.add_argument("--port",         type=int, default=8765, help="WebSocket port (default: 8765)")
parser.add_argument("--no-safe-mode", action="store_true",    help="Disable safe mode (not recommended)")
args = parser.parse_args()

print("""
╔══════════════════════════════════════════════════════╗
║  Baba Desktop — PC Control Bridge                    ║
╚══════════════════════════════════════════════════════╝
""")
print(f"  Port:      ws://localhost:{args.port}")
print(f"  Safe mode: {'OFF ⚠️' if args.no_safe_mode else 'ON ✓'}")
print(f"  Failsafe:  Move mouse to screen corner to abort")
print(f"  Log:       logs/pc_actions.jsonl")
print(f"\n  Waiting for Baba to connect…  (Ctrl+C to stop)\n")

bridge = PCBridge(
    port      = args.port,
    safe_mode = not args.no_safe_mode,
    log_dir   = "logs",
)
bridge.serve()
