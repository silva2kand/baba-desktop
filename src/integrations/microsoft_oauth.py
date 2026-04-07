"""
src/integrations/microsoft_oauth.py
Local Microsoft OAuth2 helper for desktop/loopback apps.
Stores tokens on disk and supports refresh for long-lived sessions.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from datetime import datetime, UTC, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode

import httpx


DEFAULT_SCOPES = [
    "offline_access",
    "openid",
    "profile",
    "User.Read",
    "IMAP.AccessAsUser.All",
    "SMTP.Send",
    "Mail.Read",
    "Mail.ReadWrite",
    "Mail.Send",
]


class MicrosoftOAuthManager:
    def __init__(self, settings=None, token_path: str = "data/oauth_tokens/microsoft.json"):
        self.settings = settings
        self.token_path = Path(token_path)
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load()

    def get_config(self) -> Dict[str, Any]:
        raw = getattr(self.settings, "_raw", {}) if self.settings else {}
        integrations = raw.get("integrations", {}) if isinstance(raw, dict) else {}
        oauth_cfg = integrations.get("oauth", {}) if isinstance(integrations, dict) else {}
        ms_cfg = oauth_cfg.get("microsoft", {}) if isinstance(oauth_cfg, dict) else {}

        redirect_uri = (
            os.getenv("REDIRECT_URI", "").strip()
            or oauth_cfg.get("redirect_uri", "")
            or (
                self.settings.get_localhost_redirect_uri()
                if self.settings and hasattr(self.settings, "get_localhost_redirect_uri")
                else "http://localhost:8080/oauth/callback"
            )
        )
        tenant_id = (
            os.getenv("AZURE_TENANT_ID", "").strip()
            or str(ms_cfg.get("tenant_id", "")).strip()
            or "common"
        )
        client_id = (
            os.getenv("AZURE_CLIENT_ID", "").strip()
            or str(ms_cfg.get("client_id", "")).strip()
        )
        client_secret = (
            os.getenv("AZURE_CLIENT_SECRET", "").strip()
            or str(ms_cfg.get("client_secret", "")).strip()
        )
        email_address = (
            os.getenv("IMAP_USER", "").strip()
            or os.getenv("OUTLOOK_EMAIL", "").strip()
            or os.getenv("AZURE_EMAIL", "").strip()
            or str(ms_cfg.get("email", "")).strip()
        )
        scopes = ms_cfg.get("scopes") if isinstance(ms_cfg, dict) else None
        if not isinstance(scopes, list) or not scopes:
            scopes = list(DEFAULT_SCOPES)

        return {
            "tenant_id": tenant_id,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "email": email_address,
            "scopes": scopes,
            "auth_url": f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize",
            "token_url": f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        }

    def is_configured(self) -> bool:
        cfg = self.get_config()
        return bool(cfg["client_id"] and cfg["redirect_uri"])

    def get_authorization_url(self, state: Optional[str] = None) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "ok": False,
                "error": "Missing AZURE_CLIENT_ID or REDIRECT_URI",
                "status": self.status(),
            }

        cfg = self.get_config()
        state_value = state or secrets.token_urlsafe(24)
        code_verifier = secrets.token_urlsafe(64)
        challenge_raw = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(challenge_raw).decode("utf-8").rstrip("=")

        self._state["pending_auth"] = {
            "state": state_value,
            "code_verifier": code_verifier,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._save()

        query = urlencode(
            {
                "client_id": cfg["client_id"],
                "response_type": "code",
                "redirect_uri": cfg["redirect_uri"],
                "response_mode": "query",
                "scope": " ".join(cfg["scopes"]),
                "state": state_value,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return {
            "ok": True,
            "auth_url": f"{cfg['auth_url']}?{query}",
            "state": state_value,
            "redirect_uri": cfg["redirect_uri"],
            "scopes": cfg["scopes"],
        }

    def exchange_code(self, code: str, state: str = "") -> Dict[str, Any]:
        code = (code or "").strip()
        if not code:
            return {"ok": False, "error": "Authorization code is required"}
        if not self.is_configured():
            return {"ok": False, "error": "OAuth not configured"}

        pending = self._state.get("pending_auth", {}) or {}
        if state and pending.get("state") and state != pending.get("state"):
            return {"ok": False, "error": "OAuth state mismatch"}

        cfg = self.get_config()
        payload = {
            "client_id": cfg["client_id"],
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": cfg["redirect_uri"],
            "scope": " ".join(cfg["scopes"]),
        }
        verifier = pending.get("code_verifier")
        if verifier:
            payload["code_verifier"] = verifier
        if cfg["client_secret"]:
            payload["client_secret"] = cfg["client_secret"]

        try:
            with httpx.Client(timeout=30) as c:
                r = c.post(
                    cfg["token_url"],
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                data = r.json()
                if r.status_code >= 400:
                    return {
                        "ok": False,
                        "error": data.get("error_description")
                        or data.get("error")
                        or f"Token exchange failed ({r.status_code})",
                    }
        except Exception as e:
            return {"ok": False, "error": str(e)}

        self._store_token_response(data)
        self._state.pop("pending_auth", None)
        self._save()
        return {"ok": True, "status": self.status()}

    def refresh_access_token(self) -> Dict[str, Any]:
        cfg = self.get_config()
        token = self._state.get("token", {}) or {}
        refresh_token = token.get("refresh_token", "")
        if not refresh_token:
            return {"ok": False, "error": "No refresh token available"}

        payload = {
            "client_id": cfg["client_id"],
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "redirect_uri": cfg["redirect_uri"],
            "scope": " ".join(cfg["scopes"]),
        }
        if cfg["client_secret"]:
            payload["client_secret"] = cfg["client_secret"]

        try:
            with httpx.Client(timeout=30) as c:
                r = c.post(
                    cfg["token_url"],
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                data = r.json()
                if r.status_code >= 400:
                    return {
                        "ok": False,
                        "error": data.get("error_description")
                        or data.get("error")
                        or f"Refresh failed ({r.status_code})",
                    }
        except Exception as e:
            return {"ok": False, "error": str(e)}

        self._store_token_response(data)
        self._save()
        return {"ok": True, "status": self.status()}

    def get_access_token(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "error": "OAuth not configured"}
        token = self._state.get("token", {}) or {}
        if token and self._token_valid(token):
            return {"ok": True, "access_token": token.get("access_token", "")}
        refresh = self.refresh_access_token()
        if not refresh.get("ok"):
            return refresh
        token = self._state.get("token", {}) or {}
        if token and token.get("access_token"):
            return {"ok": True, "access_token": token.get("access_token", "")}
        return {"ok": False, "error": "No usable access token"}

    def clear_tokens(self) -> Dict[str, Any]:
        self._state.pop("token", None)
        self._state.pop("pending_auth", None)
        self._save()
        return {"ok": True}

    def status(self) -> Dict[str, Any]:
        cfg = self.get_config()
        token = self._state.get("token", {}) or {}
        connected = bool(token.get("refresh_token") or token.get("access_token"))
        expires_at = token.get("expires_at", "")
        seconds_left = 0
        if expires_at:
            try:
                exp = datetime.fromisoformat(expires_at)
                seconds_left = int((exp - datetime.now(UTC)).total_seconds())
            except Exception:
                seconds_left = 0
        return {
            "configured": self.is_configured(),
            "connected": connected,
            "token_present": bool(token),
            "expires_at": expires_at,
            "seconds_left": seconds_left,
            "email": cfg.get("email", ""),
            "tenant_id": cfg.get("tenant_id", ""),
            "client_id": cfg.get("client_id", ""),
            "redirect_uri": cfg.get("redirect_uri", ""),
            "scopes": cfg.get("scopes", []),
            "pending_auth": bool(self._state.get("pending_auth")),
        }

    def _store_token_response(self, data: Dict[str, Any]):
        token = self._state.get("token", {}) or {}
        token["access_token"] = data.get("access_token", token.get("access_token", ""))
        token["refresh_token"] = data.get("refresh_token", token.get("refresh_token", ""))
        token["scope"] = data.get("scope", token.get("scope", ""))
        expires_in = int(data.get("expires_in", 3600) or 3600)
        token["obtained_at"] = datetime.now(UTC).isoformat()
        token["expires_at"] = (datetime.now(UTC) + timedelta(seconds=expires_in)).isoformat()
        self._state["token"] = token

    def _token_valid(self, token: Dict[str, Any], skew_seconds: int = 120) -> bool:
        if not token.get("access_token"):
            return False
        expires_at = token.get("expires_at")
        if not expires_at:
            return False
        try:
            exp = datetime.fromisoformat(expires_at)
        except Exception:
            return False
        return exp > (datetime.now(UTC) + timedelta(seconds=skew_seconds))

    def _load(self) -> Dict[str, Any]:
        if self.token_path.exists():
            try:
                data = json.loads(self.token_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {}

    def _save(self):
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
