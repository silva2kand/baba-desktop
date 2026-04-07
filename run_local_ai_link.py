#!/usr/bin/env python3
"""
run_local_ai_link.py
Link and verify local AI runtimes (Ollama, Jan, LM Studio).

Usage:
  python run_local_ai_link.py
  python run_local_ai_link.py --prompt "Reply with READY" --json
  python run_local_ai_link.py --providers ollama jan --no-test
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, Any, List

from config.settings import Settings
from src.providers.pool import ProviderPool

LOCAL_PROVIDERS = ["ollama", "jan", "lmstudio"]
STATE_PATH = Path("data/local_ai_link.json")


def _first_nonempty(values: List[str]) -> str:
    for v in values:
        if str(v).strip():
            return str(v)
    return ""


def _default_model(settings: Settings, provider: str) -> str:
    cfg_models = settings.providers.get(provider, {}).get("models", {})
    preferred = [
        cfg_models.get("default", ""),
        cfg_models.get("reasoning", ""),
        cfg_models.get("fast", ""),
    ]
    return _first_nonempty(preferred)


def _rank_score(provider: str, model: str) -> int:
    m = model.lower()
    score = 0
    if any(x in m for x in ("embed", "embedding", "nomic-embed", "rerank")):
        score -= 300
    if "cloud" in m:
        score -= 120
    if any(x in m for x in ("qwen", "llama", "gemma", "omnicoder", "bonsai")):
        score += 60
    if any(x in m for x in ("reason", "distill", "instruct", "it")):
        score += 20
    if provider == "ollama" and "qwen3.5:latest" in m:
        score += 140
    if provider == "lmstudio" and "omnicoder" in m:
        score += 80
    return score


def _candidate_models(settings: Settings, pool: ProviderPool, provider: str) -> List[str]:
    seen = set()
    out: List[str] = []

    cfg_models = settings.providers.get(provider, {}).get("models", {})
    preferred_order = ["default", "reasoning", "fast", "code", "coder", "coder_big"]
    for key in preferred_order:
        val = str(cfg_models.get(key, "")).strip()
        if val and val not in seen:
            seen.add(val)
            out.append(val)
    for val in cfg_models.values():
        sval = str(val).strip()
        if sval and sval not in seen:
            seen.add(sval)
            out.append(sval)

    live = pool.live_models(provider)
    ranked_live = sorted(live, key=lambda x: _rank_score(provider, x), reverse=True)
    for model in ranked_live:
        if model not in seen:
            seen.add(model)
            out.append(model)

    return out[:12]


async def _smoke_test_provider(
    pool: ProviderPool,
    settings: Settings,
    provider: str,
    prompt: str,
    max_tokens: int,
) -> Dict[str, Any]:
    candidates = _candidate_models(settings, pool, provider)
    if not candidates:
        return {
            "ok": False,
            "provider": provider,
            "error": "No model resolved",
            "model": "",
            "reply": "",
        }

    last_error = ""
    tried = []
    for model in candidates:
        tried.append(model)
        try:
            reply = await pool.chat(
                provider,
                model,
                [{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.2,
            )
            return {
                "ok": True,
                "provider": provider,
                "model": model,
                "reply": (reply or "")[:300],
                "error": "",
                "tried": tried,
            }
        except Exception as e:
            last_error = str(e)
            continue

    return {
        "ok": False,
        "provider": provider,
        "model": tried[0] if tried else "",
        "reply": "",
        "error": last_error or "No candidate model succeeded",
        "tried": tried,
    }


def _print_summary(
    selected: List[str],
    detected: Dict[str, Any],
    health: Dict[str, bool],
    smoke: List[Dict[str, Any]],
) -> None:
    print("=" * 64)
    print("Local AI Link Status")
    print("=" * 64)
    for p in selected:
        d = detected.get(p, {})
        online = bool(d.get("online", False))
        model_count = len(d.get("models", []) or [])
        health_ok = bool(health.get(p, False))
        status = "ONLINE" if online else "OFFLINE"
        print(f"- {p:<8} {status:<7} health={health_ok} models={model_count}")

    if smoke:
        print("\nSmoke Tests")
        for r in smoke:
            if r.get("ok"):
                print(f"- {r['provider']:<8} OK  model={r.get('model','')} reply={r.get('reply','')[:80]!r}")
            else:
                print(f"- {r['provider']:<8} FAIL model={r.get('model','')} err={r.get('error','')}")


def _save_state(payload: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Link and verify local AI runtimes")
    parser.add_argument(
        "--providers",
        nargs="*",
        default=LOCAL_PROVIDERS,
        help="Subset of local providers to link (ollama jan lmstudio)",
    )
    parser.add_argument(
        "--prompt",
        default="Reply with: READY",
        help="Prompt used for smoke test",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=128,
        help="Max tokens for smoke prompt",
    )
    parser.add_argument(
        "--no-test",
        action="store_true",
        help="Only detect providers and models, skip prompt smoke tests",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output",
    )
    args = parser.parse_args()

    selected = [p.lower().strip() for p in args.providers if p.lower().strip() in LOCAL_PROVIDERS]
    if not selected:
        print("No valid providers selected. Use: ollama jan lmstudio")
        return 1

    settings = Settings.load()
    pool = ProviderPool(settings.providers)

    detected = pool.detect_all()
    health = pool.health_check_sync()

    smoke_results: List[Dict[str, Any]] = []
    if not args.no_test:
        for provider in selected:
            if not bool(detected.get(provider, {}).get("online", False)):
                smoke_results.append(
                    {
                        "ok": False,
                        "provider": provider,
                        "model": "",
                        "reply": "",
                        "error": "Provider offline",
                    }
                )
                continue
            smoke_results.append(
                await _smoke_test_provider(
                    pool,
                    settings,
                    provider,
                    args.prompt,
                    args.max_tokens,
                )
            )

    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "selected": selected,
        "detected": {p: detected.get(p, {}) for p in selected},
        "health": {p: bool(health.get(p, False)) for p in selected},
        "smoke": smoke_results,
    }
    _save_state(payload)

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_summary(selected, detected, health, smoke_results)
        print(f"\nSaved: {STATE_PATH}")
        if any(not bool(detected.get(p, {}).get("online", False)) for p in selected):
            print("\nStart missing local runtimes first:")
            print("- Ollama: ollama serve")
            print("- Jan: open Jan app and enable local API server")
            print("- LM Studio: open app and start local server (port 1234)")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
