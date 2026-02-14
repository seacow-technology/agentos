from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from octopusos.channels.teams.store import TeamsConnectionStore
from octopusos.webui.secrets import SecretStore


GRAPH_ROOT = "https://graph.microsoft.com/v1.0"


@dataclass
class GraphCallResult:
    ok: bool
    status_code: int
    data: Dict[str, Any]
    error: str = ""


class TeamsGraphClient:
    def __init__(self, tenant_id: str, token_ref: str):
        self.tenant_id = str(tenant_id)
        self.token_ref = str(token_ref)
        self._access_token: Optional[str] = None

    def _load_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        raw = SecretStore().get(self.token_ref)
        if not raw:
            raise ValueError("missing_oauth_token")
        try:
            payload = json.loads(raw)
        except Exception as exc:
            raise ValueError(f"invalid_oauth_token_payload:{exc}") from exc
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise ValueError("oauth_access_token_empty")
        self._access_token = token
        return token

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
    ) -> GraphCallResult:
        token = self._load_access_token()
        req_headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)
        url = GRAPH_ROOT + path
        resp = requests.request(
            method=method,
            url=url,
            headers=req_headers,
            params=params,
            json=json_body,
            files=files,
            timeout=timeout,
        )
        data: Dict[str, Any]
        try:
            data = resp.json() if resp.text else {}
        except Exception:
            data = {"raw": resp.text[:1000]}
        ok = 200 <= resp.status_code < 300
        err = "" if ok else str(data.get("error") or resp.text[:300])
        return GraphCallResult(ok=ok, status_code=int(resp.status_code), data=data, error=err)

    def get_organization(self) -> Dict[str, Any]:
        res = self._request("GET", "/organization")
        if not res.ok:
            raise ValueError(f"graph_organization_failed:{res.status_code}:{res.error}")
        items = res.data.get("value") if isinstance(res.data, dict) else None
        if isinstance(items, list) and items:
            return items[0] if isinstance(items[0], dict) else {}
        return {}

    def list_catalog_apps(self) -> List[Dict[str, Any]]:
        res = self._request("GET", "/appCatalogs/teamsApps", params={"$expand": "appDefinitions"})
        if not res.ok:
            raise ValueError(f"graph_list_apps_failed:{res.status_code}:{res.error}")
        value = res.data.get("value")
        return value if isinstance(value, list) else []

    def upload_app_package(self, zip_path: str) -> Dict[str, Any]:
        p = Path(zip_path)
        if not p.exists():
            raise ValueError(f"zip_not_found:{zip_path}")
        with p.open("rb") as f:
            content = f.read()
        res = self._request(
            "POST",
            "/appCatalogs/teamsApps",
            headers={"Content-Type": "application/zip"},
            timeout=60,
            files=None,
        )
        # Some Graph tenants reject raw zip without multipart via requests.request(json/files split).
        # Retry with raw data request.
        if not res.ok:
            token = self._load_access_token()
            resp = requests.post(
                GRAPH_ROOT + "/appCatalogs/teamsApps",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/zip",
                    "Accept": "application/json",
                },
                data=content,
                timeout=90,
            )
            try:
                data = resp.json() if resp.text else {}
            except Exception:
                data = {"raw": resp.text[:1000]}
            if resp.status_code < 200 or resp.status_code >= 300:
                if resp.status_code == 409:
                    reused = self._reuse_existing_from_conflict(data)
                    if reused:
                        return reused
                raise ValueError(f"graph_upload_failed:{resp.status_code}:{data}")
            return data
        return res.data

    def install_app_for_user(self, *, user_id: str, teams_app_catalog_id: str, external_app_id: str = "") -> Dict[str, Any]:
        body = {
            "teamsApp@odata.bind": f"https://graph.microsoft.com/v1.0/appCatalogs/teamsApps/{teams_app_catalog_id}"
        }
        res = self._request(
            "POST",
            f"/users/{user_id}/teamwork/installedApps",
            json_body=body,
        )
        if not res.ok:
            if res.status_code == 409:
                return {"ok": True, "already_installed": True, "id": teams_app_catalog_id}
            if res.status_code == 404 and external_app_id:
                resolved = self.find_catalog_app_id_by_external_id(external_app_id)
                if resolved and resolved != teams_app_catalog_id:
                    body = {
                        "teamsApp@odata.bind": f"https://graph.microsoft.com/v1.0/appCatalogs/teamsApps/{resolved}"
                    }
                    retry = self._request(
                        "POST",
                        f"/users/{user_id}/teamwork/installedApps",
                        json_body=body,
                    )
                    if retry.ok:
                        return retry.data
                    if retry.status_code == 409:
                        return {"ok": True, "already_installed": True, "id": resolved}
            raise ValueError(f"graph_install_for_user_failed:{res.status_code}:{res.error}")
        return res.data

    def get_me(self) -> Dict[str, Any]:
        res = self._request("GET", "/me")
        if not res.ok:
            raise ValueError(f"graph_me_failed:{res.status_code}:{res.error}")
        return res.data if isinstance(res.data, dict) else {}

    def uninstall_catalog_app(self, catalog_app_id: str) -> bool:
        res = self._request("DELETE", f"/appCatalogs/teamsApps/{catalog_app_id}")
        return res.ok

    def find_catalog_app_id_by_external_id(self, external_app_id: str) -> str:
        target = str(external_app_id or "").strip().lower()
        if not target:
            return ""
        apps = self.list_catalog_apps()
        for app in apps:
            if not isinstance(app, dict):
                continue
            ext = str(app.get("externalId") or "").strip().lower()
            if ext and ext == target:
                return str(app.get("id") or "").strip()
            defs = app.get("appDefinitions")
            if not isinstance(defs, list):
                continue
            for d in defs:
                if not isinstance(d, dict):
                    continue
                teams_app_id = str(d.get("teamsAppId") or "").strip().lower()
                if teams_app_id and teams_app_id == target:
                    return str(app.get("id") or "").strip()
                ext_d = str(d.get("externalId") or "").strip().lower()
                if ext_d and ext_d == target:
                    return str(app.get("id") or "").strip()
        return ""

    @staticmethod
    def _reuse_existing_from_conflict(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        message = ""
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                message = str(err.get("message") or "")
                inner = err.get("innerError")
                if not message and isinstance(inner, dict):
                    message = str(inner.get("message") or "")
        if not message:
            return None

        # Conflict payload usually contains:
        # AppId: '<catalog-id>', ExternalId: '<manifest-id>'
        app_match = re.search(r"AppId:\s*'([0-9a-fA-F-]{8,})'", message)
        ext_match = re.search(r"ExternalId:\s*'([0-9a-fA-F-]{8,})'", message)
        app_id = app_match.group(1) if app_match else ""
        ext_id = ext_match.group(1) if ext_match else ""
        if not app_id:
            return None
        return {
            "id": app_id,
            "externalId": ext_id,
            "reused": True,
            "reason": "already_exists",
        }
