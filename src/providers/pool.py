"""
src/providers/pool.py
Provider Pool with live auto-detect + fuzzy model resolution.
Covers: Ollama, Jan, LM Studio, Groq, Gemini, OpenRouter, Qwen.
"""

import json, os, re, urllib.request
import httpx
import asyncio
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path


OLLAMA_KNOWN = [
    "qwen3.5:latest",
    "sorc/qwen3.5-claude-4.6-opus:0.8b",
    "sorc/qwen3.5-claude-4.6-opus:2b",
    "sorc/qwen3.5-claude-4.6-opus:4b",
    "huihui_ai/qwen3.5-abliterated:9b",
    "gemma3:12b",
    "gemma-3-12b-it:latest",
    "llama3.1:8b",
    "llama3.2:3b",
    "hf.co/prism-ml/Bonsai-8B-gguf:latest",
    "nomic-embed-text:latest",
    "minimax-m2.7:cloud",
    "nemotron-3-super:cloud",
]

JAN_KNOWN = [
    "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
    "unsloth/Qwen3.5-4B-GGUF",
    "Jackrong/Qwen3.5-4B-Claude-4.6-Opus-Reasoning-Distilled-GGUF",
    "Jackrong/Qwen3.5-4B-Claude-4.6-Opus-Reasoning-Distilled-v2-GGUF",
    "Jackrong/Qwen3.5-9B-Claude-4.6-Opus-Reasoning-Distilled-GGUF",
    "Jackrong/Qwen3.5-9B-Claude-4.6-Opus-Reasoning-Distilled-v2-GGUF",
    "Jackrong/Qwen3.5-9B-Gemini-3.1-Pro-Reasoning-Distill-GGUF",
    "Jackrong/Qwen3.5-9B-Neo-GGUF",
    "Jackrong/Qwopus3.5-9B-v3-GGUF",
    "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF",
]

LMS_KNOWN = [
    "ggml-org/gemma-4-e2b-it",
    "bartowski/prism-ml_bonsai-8b-unpacked",
    "prism-ml/bonsai-8b",
    "mradermacher/omnicoder-9b",
    "lmstudio-community/qwen/qwen3.5-9b",
    "lmstudio-community/zai-org/glm-4.6v-flash",
    "Jackrong/qwen3.5-9b-claude-4.6-opus-reasoning-distilled",
    "Jackrong/qwen3.5-4b-claude-4.6-opus-reasoning-distilled",
]


class ProviderPool:
    """Real provider pool with live auto-detect + fuzzy model resolution."""

    LOCAL_ENDPOINTS = {
        "ollama": "http://localhost:11434/api/tags",
        "jan": "http://localhost:1337/v1/models",
        "lmstudio": "http://localhost:1234/v1/models",
    }

    KNOWN_FALLBACKS = {
        "ollama": OLLAMA_KNOWN,
        "jan": JAN_KNOWN,
        "lmstudio": LMS_KNOWN,
    }

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._live_models: Dict[str, List[str]] = {}
        self._detected: Dict[str, bool] = {}
        self._resolved_cache: Dict[tuple, str] = {}
        self._clients = {}

    def detect_all(self) -> Dict[str, Any]:
        results = {}
        for name, port, known in [
            ("ollama", 11434, OLLAMA_KNOWN),
            ("jan", 1337, JAN_KNOWN),
            ("lmstudio", 1234, LMS_KNOWN),
        ]:
            try:
                if name == "ollama":
                    r = urllib.request.urlopen(
                        "http://localhost:11434/api/tags", timeout=3
                    )
                    data = json.loads(r.read())
                    names = [m["name"] for m in data.get("models", [])]
                else:
                    r = urllib.request.urlopen(
                        f"http://localhost:{port}/v1/models", timeout=3
                    )
                    data = json.loads(r.read())
                    names = [m["id"] for m in data.get("data", [])]
                self._live_models[name] = names or known
                self._detected[name] = True
                results[name] = {"online": True, "models": self._live_models[name]}
            except Exception as e:
                self._detected[name] = False
                self._live_models[name] = known
                results[name] = {"online": False, "models": [], "error": str(e)}

        for cloud in ("groq", "gemini", "openrouter", "qwen"):
            env_key = self.config.get(cloud, {}).get("api_key_env", "")
            has_key = bool(os.getenv(env_key, ""))
            self._detected[cloud] = has_key
            results[cloud] = {"online": has_key, "key_set": has_key}

        self._resolved_cache.clear()
        return results

    def health_check_sync(self) -> Dict[str, bool]:
        out = {}
        for name, port in [("ollama", 11434), ("jan", 1337), ("lmstudio", 1234)]:
            try:
                urllib.request.urlopen(f"http://localhost:{port}", timeout=2)
                out[name] = True
            except Exception:
                try:
                    path = "/api/tags" if name == "ollama" else "/v1/models"
                    urllib.request.urlopen(f"http://localhost:{port}{path}", timeout=2)
                    out[name] = True
                except Exception:
                    out[name] = False
        for cloud in ("groq", "gemini", "openrouter", "qwen"):
            env_key = self.config.get(cloud, {}).get("api_key_env", "")
            out[cloud] = bool(os.getenv(env_key, ""))
        return out

    def live_models(self, provider: str) -> List[str]:
        if not self._live_models:
            self.detect_all()
        return self._live_models.get(provider, [])

    def get_local_model_catalog(self, refresh: bool = False) -> Dict[str, List[str]]:
        if refresh or not self._live_models:
            self.detect_all()
        return {name: list(models) for name, models in self._live_models.items()}

    def active_names(self) -> List[str]:
        return [
            k
            for k, v in self.config.items()
            if isinstance(v, dict) and v.get("enabled")
        ]

    def resolve_model(
        self, provider: str, requested: str, role: Optional[str] = None
    ) -> str:
        config_models = self.config.get(provider, {}).get("models", {})
        desired = config_models.get(requested, requested)
        if provider not in self.LOCAL_ENDPOINTS:
            return desired

        cache_key = (provider, desired)
        if cache_key in self._resolved_cache:
            return self._resolved_cache[cache_key]

        available = self._live_models.get(provider) or self._fetch_local_models(
            provider
        )
        if not available:
            self._resolved_cache[cache_key] = desired
            return desired

        if desired in available:
            self._resolved_cache[cache_key] = desired
            return desired

        resolved = self._match_model(
            provider, desired, available, role or self._infer_role(provider, requested)
        )
        self._resolved_cache[cache_key] = resolved
        return resolved

    def _fetch_local_models(self, provider: str) -> List[str]:
        url = self.LOCAL_ENDPOINTS.get(provider)
        if not url:
            return []
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8", errors="ignore"))
        except Exception:
            return []

        if provider == "ollama":
            models = [
                item.get("name") or item.get("model")
                for item in payload.get("models", [])
            ]
        else:
            models = [item.get("id") for item in payload.get("data", [])]

        unique = []
        seen = set()
        for model in models:
            if model and model not in seen:
                seen.add(model)
                unique.append(model)
        return unique

    def _match_model(
        self, provider: str, desired: str, available: List[str], role: Optional[str]
    ) -> str:
        normalized_desired = self._normalize(desired)
        desired_tokens = [
            token
            for token in re.split(r"[^a-z0-9]+", normalized_desired)
            if len(token) >= 2
        ]
        best_name = available[0]
        best_score = -1

        for name in available:
            normalized_name = self._normalize(name)
            score = 0

            if name == desired:
                return name
            if normalized_desired and normalized_desired in normalized_name:
                score += 300
            if normalized_name and normalized_name in normalized_desired:
                score += 200
            for token in desired_tokens:
                if token in normalized_name:
                    score += 20
            score += self._role_score(role, normalized_name)
            score += self._provider_score(provider, normalized_name)

            if score > best_score:
                best_score = score
                best_name = name

        if best_score <= 0:
            return desired
        return best_name

    def _infer_role(self, provider: str, requested: str) -> Optional[str]:
        for role, model in self.config.get(provider, {}).get("models", {}).items():
            if requested == role or requested == model:
                return role
        if requested in {
            "default",
            "small",
            "fast",
            "reasoning",
            "vision",
            "coder",
            "code",
            "coder_big",
        }:
            return requested
        return None

    def _role_score(self, role: Optional[str], normalized_name: str) -> int:
        if not role:
            return 0
        hints = {
            "default": ["qwen", "9b", "8b"],
            "small": ["4b", "3b", "2b", "1b", "lite", "mini"],
            "fast": ["0.8b", "1b", "2b", "4b", "flash", "lite"],
            "reasoning": ["reason", "opus", "distill", "think"],
            "vision": ["vl", "vision", "46v", "glm", "flash"],
            "coder": ["coder", "omnicoder", "code"],
            "code": ["coder", "omnicoder", "code"],
            "coder_big": ["14b", "coder", "omnicoder", "code"],
        }
        return sum(35 for hint in hints.get(role, []) if hint in normalized_name)

    def _provider_score(self, provider: str, normalized_name: str) -> int:
        if "embed" in normalized_name:
            return -200
        if provider == "ollama" and "qwen" in normalized_name:
            return 25
        if provider == "jan" and normalized_name.startswith("models"):
            return -120
        if provider == "jan" and "gemini" in normalized_name:
            return -150
        if provider == "lmstudio" and any(
            token in normalized_name for token in ("qwen", "omnicoder", "bonsai")
        ):
            return 15
        return 0

    def _normalize(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    async def chat(
        self,
        provider: str,
        model: str,
        messages: List[Dict],
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
    ) -> str:
        if system:
            messages = [{"role": "system", "content": system}] + messages

        if provider in self.LOCAL_ENDPOINTS:
            model = self.resolve_model(provider, model)

        try:
            if provider == "ollama":
                return await self._ollama(model, messages, temperature, stream)
            elif provider == "jan":
                return await self._openai_compat(
                    "jan",
                    "http://localhost:1337",
                    model,
                    messages,
                    temperature,
                    max_tokens,
                )
            elif provider == "lmstudio":
                return await self._openai_compat(
                    "lmstudio",
                    "http://localhost:1234",
                    model,
                    messages,
                    temperature,
                    max_tokens,
                )
            elif provider == "groq":
                return await self._openai_compat(
                    "groq",
                    "https://api.groq.com/openai/v1",
                    model,
                    messages,
                    temperature,
                    max_tokens,
                )
            elif provider == "gemini":
                return await self._gemini(
                    model, messages, system, temperature, max_tokens
                )
            elif provider in ("openrouter", "or"):
                return await self._openai_compat(
                    "openrouter",
                    "https://openrouter.ai/api/v1",
                    model,
                    messages,
                    temperature,
                    max_tokens,
                    extra_headers={
                        "HTTP-Referer": "http://localhost",
                        "X-Title": "BabaDesktop",
                    },
                )
            elif provider == "qwen":
                return await self._openai_compat(
                    "qwen",
                    "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    model,
                    messages,
                    temperature,
                    max_tokens,
                )
            else:
                raise ValueError(f"Unknown provider: {provider}")
        except Exception as e:
            raise RuntimeError(f"[{provider}/{model}] {e}") from e

    async def chat_with_fallback(
        self, primary_provider: str, primary_model: str, messages: List[Dict], **kwargs
    ) -> Tuple[str, str]:
        chain = [
            (primary_provider, primary_model),
            ("ollama", "qwen3.5:latest"),
            ("ollama", "sorc/qwen3.5-claude-4.6-opus:4b"),
            ("jan", "unsloth/Qwen3.5-4B-GGUF"),
            ("lmstudio", "lmstudio-community/qwen/qwen3.5-9b"),
            ("groq", "llama-3.3-70b-versatile"),
            ("openrouter", "mistralai/mistral-7b-instruct:free"),
        ]
        last_err = None
        for prov, mdl in chain:
            try:
                reply = await self.chat(prov, mdl, messages, **kwargs)
                return reply, prov
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(f"All providers failed. Last: {last_err}")

    async def _ollama(
        self, model: str, messages: List[Dict], temp: float, stream: bool
    ) -> str:
        async with httpx.AsyncClient(timeout=180) as c:
            r = await c.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temp},
                },
            )
            r.raise_for_status()
            return r.json()["message"]["content"]

    async def _openai_compat(
        self,
        provider: str,
        base_url: str,
        model: str,
        messages: List[Dict],
        temp: float,
        max_tokens: int,
        extra_headers: Optional[Dict] = None,
    ) -> str:
        api_key = self._get_api_key(provider)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        if extra_headers:
            headers.update(extra_headers)
        async with httpx.AsyncClient(timeout=180) as c:
            r = await c.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temp,
                    "max_tokens": max_tokens,
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    async def _gemini(
        self,
        model: str,
        messages: List[Dict],
        system: str,
        temp: float,
        max_tokens: int,
    ) -> str:
        api_key = self._get_api_key("gemini")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        contents = [
            {
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": [{"text": m["content"]}],
            }
            for m in messages
            if m["role"] != "system"
        ]
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temp},
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        async with httpx.AsyncClient(timeout=180) as c:
            r = await c.post(url, json=payload)
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    def _get_api_key(self, provider: str) -> str:
        env_var = self.config.get(provider, {}).get("api_key_env", "")
        return os.getenv(env_var, "no-key")
