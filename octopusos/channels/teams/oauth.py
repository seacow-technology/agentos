from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from octopusos.channels.teams.store import TeamsConnectionStore
from octopusos.store.timestamp_utils import now_ms
from octopusos.webui.secrets import SecretStore


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _pkce_challenge(verifier: str) -> str:
    return _b64url(hashlib.sha256(verifier.encode("utf-8")).digest())


@dataclass
class TeamsOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: str
    authority_tenant: str = "organizations"


class TeamsOAuthService:
    def __init__(self, store: Optional[TeamsConnectionStore] = None):
        self.store = store or TeamsConnectionStore()

    @staticmethod
    def from_env() -> "TeamsOAuthService":
        return TeamsOAuthService()

    @staticmethod
    def read_config_from_env() -> TeamsOAuthConfig:
        client_id = str(os.getenv("OCTOPUSOS_TEAMS_OAUTH_CLIENT_ID", "")).strip()
        client_secret = str(os.getenv("OCTOPUSOS_TEAMS_OAUTH_CLIENT_SECRET", "")).strip()
        redirect_uri = str(os.getenv("OCTOPUSOS_TEAMS_OAUTH_REDIRECT_URI", "")).strip()
        authority_tenant = str(os.getenv("OCTOPUSOS_TEAMS_OAUTH_AUTHORITY_TENANT", "organizations")).strip() or "organizations"
        scopes = str(
            os.getenv(
                "OCTOPUSOS_TEAMS_OAUTH_SCOPES",
                "openid profile offline_access User.Read Organization.Read.All AppCatalog.ReadWrite.All TeamsAppInstallation.ReadWriteForUser",
            )
        ).strip()
        if not client_id:
            raise ValueError("missing_env:OCTOPUSOS_TEAMS_OAUTH_CLIENT_ID")
        if not client_secret:
            raise ValueError("missing_env:OCTOPUSOS_TEAMS_OAUTH_CLIENT_SECRET")
        if not redirect_uri:
            raise ValueError("missing_env:OCTOPUSOS_TEAMS_OAUTH_REDIRECT_URI")
        return TeamsOAuthConfig(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=scopes,
            authority_tenant=authority_tenant,
        )

    def build_auth_url(self, *, tenant_hint: str = "") -> Dict[str, Any]:
        cfg = self.read_config_from_env()
        state = secrets.token_urlsafe(24)
        verifier = _b64url(secrets.token_bytes(32))
        challenge = _pkce_challenge(verifier)

        self.store.save_oauth_state(
            state=state,
            tenant_hint=str(tenant_hint or ""),
            code_verifier=verifier,
            redirect_uri=cfg.redirect_uri,
            scopes=cfg.scopes,
            ttl_ms=10 * 60_000,
        )

        authorize_url = f"https://login.microsoftonline.com/{cfg.authority_tenant}/oauth2/v2.0/authorize"
        params = {
            "client_id": cfg.client_id,
            "response_type": "code",
            "redirect_uri": cfg.redirect_uri,
            "response_mode": "query",
            "scope": cfg.scopes,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        return {
            "ok": True,
            "state": state,
            "auth_url": authorize_url + "?" + urlencode(params),
            "redirect_uri": cfg.redirect_uri,
            "scopes": cfg.scopes.split(),
        }

    def exchange_code(self, *, code: str, state: str) -> Dict[str, Any]:
        if not code or not state:
            raise ValueError("missing_code_or_state")
        saved = self.store.consume_oauth_state(state)
        if not saved:
            raise ValueError("invalid_or_expired_state")

        cfg = self.read_config_from_env()
        token_url = f"https://login.microsoftonline.com/{cfg.authority_tenant}/oauth2/v2.0/token"
        data = {
            "client_id": cfg.client_id,
            "client_secret": cfg.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": saved["redirect_uri"],
            "code_verifier": saved["code_verifier"],
            "scope": saved["scopes"],
        }
        resp = requests.post(token_url, data=data, timeout=25)
        if resp.status_code >= 400:
            raise ValueError(f"token_exchange_failed:{resp.status_code}:{resp.text[:400]}")
        payload = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if not isinstance(payload, dict) or not payload.get("access_token"):
            raise ValueError("token_exchange_invalid_response")

        access_token = str(payload.get("access_token") or "")
        tenant_id = self._extract_tid(access_token)
        if not tenant_id:
            tenant_id = str(saved.get("tenant_hint") or "").strip()
        if not tenant_id:
            raise ValueError("cannot_resolve_tenant_id")

        token_ref = f"secret://teams/oauth/{tenant_id}/token"
        SecretStore().set(token_ref, json.dumps(payload, ensure_ascii=False))
        expires_in = int(payload.get("expires_in") or 3600)
        return {
            "tenant_id": tenant_id,
            "token_ref": token_ref,
            "token_expires_at_ms": int(now_ms() + (expires_in * 1000)),
            "scopes": str(saved.get("scopes") or ""),
            "token": payload,
        }

    @staticmethod
    def _extract_tid(jwt_token: str) -> str:
        parts = jwt_token.split(".")
        if len(parts) < 2:
            return ""
        payload_b64 = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
        try:
            raw = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
            obj = json.loads(raw.decode("utf-8"))
            return str(obj.get("tid") or "").strip()
        except Exception:
            return ""
