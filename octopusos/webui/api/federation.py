"""Federation (Federated Nodes) API.

This page was historically backed by compat stubs; implement a real, interactive
MVP to support:
- CRUD for nodes
- connect/disconnect semantics
- probe/refresh (real HTTP to remote node) to populate capabilities + heartbeat

Storage:
- Node records: sqlite compat_entities namespace "federation_nodes"
- Optional per-node admin token: ~/.octopusos/secrets/federation_nodes.json
"""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse

import httpx
import asyncio
import re
import subprocess

from fastapi import APIRouter, Body, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from octopusos.core.capabilities.admin_token import validate_admin_token
from octopusos.webui.api.compat_state import (
    audit_event,
    db_connect,
    ensure_schema,
    get_entity,
    list_entities,
    now_iso,
    soft_delete_entity,
    upsert_entity,
)

router = APIRouter(prefix="/api/federation", tags=["federation"])


def _require_admin_token(token: Optional[str]) -> str:
    if not token:
        raise HTTPException(status_code=401, detail="Admin token required")
    if not validate_admin_token(token):
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return "admin"


FederatedNodeStatus = Literal["connected", "disconnected", "pending", "error"]


class FederatedNodeModel(BaseModel):
    id: str
    name: str
    address: str
    status: FederatedNodeStatus = "disconnected"
    trust_level: float = Field(default=0.5, ge=0.0, le=1.0)
    last_heartbeat: Optional[str] = None
    connected_at: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ListFederatedNodesResponse(BaseModel):
    nodes: List[FederatedNodeModel]
    total: int


class CreateFederatedNodeRequest(BaseModel):
    node_id: Optional[str] = Field(default=None, description="Optional stable id")
    name: str = Field(min_length=1)
    address: str = Field(min_length=1, description="Base URL, e.g. http://127.0.0.1:52006")
    trust_level: float = Field(default=0.5, ge=0.0, le=1.0)
    admin_token: Optional[str] = Field(default=None, description="Optional remote admin token (stored locally)")


class UpdateFederatedNodeRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    address: Optional[str] = Field(default=None, min_length=1)
    trust_level: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    admin_token: Optional[str] = Field(default=None, description="Optional remote admin token (stored locally)")


class ProbeResponse(BaseModel):
    node: FederatedNodeModel
    source: Literal["live"] = "live"


def _normalize_address(raw: str) -> str:
    addr = (raw or "").strip()
    if not addr:
        raise HTTPException(status_code=422, detail="address required")
    if "://" not in addr:
        addr = f"http://{addr}"
    addr = addr.rstrip("/")
    parsed = urlparse(addr)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=422, detail="invalid address")
    return addr


def _is_blocked_ip(ip: str) -> bool:
    # Block cloud metadata and link-local. Allow loopback/private for LAN clusters.
    if ip == "169.254.169.254":
        return True
    try:
        import ipaddress

        addr = ipaddress.ip_address(ip)
        if addr.is_multicast or addr.is_unspecified:
            return True
        if addr.is_link_local:
            return True
    except Exception:
        # If parsing fails, be conservative.
        return True
    return False


def _validate_address_ssrf_safe(address: str) -> None:
    parsed = urlparse(address)
    host = parsed.hostname
    if not host:
        raise HTTPException(status_code=422, detail="invalid address host")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror:
        raise HTTPException(status_code=422, detail="address host not resolvable")
    for info in infos:
        ip = info[4][0]
        if _is_blocked_ip(ip):
            raise HTTPException(status_code=422, detail=f"address blocked: {ip}")


@dataclass(frozen=True)
class _FederationSecretsStore:
    path: Path

    @staticmethod
    def default() -> "_FederationSecretsStore":
        return _FederationSecretsStore(path=Path.home() / ".octopusos" / "secrets" / "federation_nodes.json")

    def _ensure_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read_all(self) -> Dict[str, Dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text("utf-8"))
        except Exception:
            return {}

    def write_all(self, data: Dict[str, Dict[str, Any]]) -> None:
        self._ensure_parent()
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", "utf-8")
        try:
            self.path.chmod(0o600)
        except Exception:
            pass

    def set_admin_token(self, node_id: str, token: Optional[str]) -> None:
        data = self.read_all()
        entry = data.get(node_id) or {}
        if token:
            entry["admin_token"] = token
        else:
            entry.pop("admin_token", None)
        if entry:
            data[node_id] = entry
        else:
            data.pop(node_id, None)
        self.write_all(data)

    def get_admin_token(self, node_id: str) -> Optional[str]:
        return (self.read_all().get(node_id) or {}).get("admin_token")


def _entity_to_node(entity_id: str, data: Dict[str, Any]) -> FederatedNodeModel:
    # Accept legacy fields ("state") and normalize to contract.
    status = data.get("status") or data.get("state") or "disconnected"
    if status not in {"connected", "disconnected", "pending", "error"}:
        status = "disconnected"
    return FederatedNodeModel(
        id=entity_id,
        name=str(data.get("name") or entity_id),
        address=str(data.get("address") or ""),
        status=status,  # type: ignore[arg-type]
        trust_level=float(data.get("trust_level") if data.get("trust_level") is not None else 0.5),
        last_heartbeat=data.get("last_heartbeat"),
        connected_at=data.get("connected_at"),
        capabilities=list(data.get("capabilities") or []),
        metadata=dict(data.get("metadata") or {}),
    )


def _get_node_or_404(conn, node_id: str) -> Dict[str, Any]:
    existing = get_entity(conn, namespace="federation_nodes", entity_id=node_id)
    if not existing or existing.get("_deleted"):
        raise HTTPException(status_code=404, detail="Node not found")
    return existing


@router.get("/nodes", response_model=ListFederatedNodesResponse)
def list_federation_nodes(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        raw = list_entities(conn, namespace="federation_nodes")
        nodes = []
        for n in raw:
            node = _entity_to_node(n.get("_entity_id") or "", n)
            if status and node.status != status:
                continue
            nodes.append(node.model_dump())
        nodes = nodes[:limit]
        return {"nodes": nodes, "total": len(nodes)}
    finally:
        conn.close()


@router.get("/nodes/{node_id}", response_model=Dict[str, FederatedNodeModel])
def get_federated_node(node_id: str) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        existing = _get_node_or_404(conn, node_id)
        node = _entity_to_node(node_id, existing)
        return {"node": node.model_dump()}
    finally:
        conn.close()


@router.post("/nodes", response_model=Dict[str, FederatedNodeModel])
def create_federated_node(
    payload: CreateFederatedNodeRequest,
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    address = _normalize_address(payload.address)
    _validate_address_ssrf_safe(address)

    node_id = (payload.node_id or "").strip()
    if not node_id:
        # Stable-ish id derived from address.
        import hashlib

        node_id = f"node_{hashlib.sha1(address.encode('utf-8')).hexdigest()[:10]}"

    data = {
        "id": node_id,
        "name": payload.name,
        "address": address,
        "status": "disconnected",
        "trust_level": payload.trust_level,
        "capabilities": [],
        "metadata": {},
        "last_heartbeat": None,
        "connected_at": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }

    conn = db_connect()
    try:
        ensure_schema(conn)
        upsert_entity(conn, namespace="federation_nodes", entity_id=node_id, data=data, status="disconnected")
        audit_event(conn, event_type="federation_node_create", endpoint="/api/federation/nodes", actor=actor, payload=payload.model_dump(), result={"id": node_id})
    finally:
        conn.close()

    # Store optional remote token separately (local secret).
    _FederationSecretsStore.default().set_admin_token(node_id, payload.admin_token)

    node = _entity_to_node(node_id, data)
    return {"node": node.model_dump()}


@router.put("/nodes/{node_id}", response_model=Dict[str, FederatedNodeModel])
def update_federated_node(
    node_id: str,
    payload: UpdateFederatedNodeRequest,
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        existing = _get_node_or_404(conn, node_id)
        updated = dict(existing)

        if payload.name is not None:
            updated["name"] = payload.name
        if payload.address is not None:
            address = _normalize_address(payload.address)
            _validate_address_ssrf_safe(address)
            updated["address"] = address
        if payload.trust_level is not None:
            updated["trust_level"] = payload.trust_level

        updated["updated_at"] = now_iso()
        upsert_entity(conn, namespace="federation_nodes", entity_id=node_id, data=updated, status=str(updated.get("status") or "disconnected"))
        audit_event(conn, event_type="federation_node_update", endpoint=f"/api/federation/nodes/{node_id}", actor=actor, payload=payload.model_dump(), result={"id": node_id})
        node = _entity_to_node(node_id, updated)
    finally:
        conn.close()

    _FederationSecretsStore.default().set_admin_token(node_id, payload.admin_token)
    return {"node": node.model_dump()}


@router.delete("/nodes/{node_id}")
def delete_federated_node(
    node_id: str,
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        _get_node_or_404(conn, node_id)
        soft_delete_entity(conn, namespace="federation_nodes", entity_id=node_id)
        audit_event(conn, event_type="federation_node_delete", endpoint=f"/api/federation/nodes/{node_id}", actor=actor, payload={}, result={"id": node_id})
    finally:
        conn.close()
    _FederationSecretsStore.default().set_admin_token(node_id, None)
    return {"ok": True}


async def _probe_remote_node(address: str, remote_admin_token: Optional[str]) -> Dict[str, Any]:
    headers: Dict[str, str] = {}
    if remote_admin_token:
        headers["X-Admin-Token"] = remote_admin_token
    timeout = httpx.Timeout(connect=3.0, read=5.0, write=5.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
        overview = await client.get(f"{address}/api/overview")
        overview.raise_for_status()
        providers = await client.get(f"{address}/api/providers")
        providers.raise_for_status()
        tools = await client.get(f"{address}/api/tools")
        tools.raise_for_status()
        return {
            "overview": overview.json(),
            "providers": providers.json(),
            "tools": tools.json(),
        }


def _capabilities_from_probe(probe: Dict[str, Any]) -> List[str]:
    caps = ["api/overview", "api/providers", "api/tools"]
    # Add coarse capability hints when present.
    if isinstance(probe.get("providers"), dict) and "providers" in probe["providers"]:
        caps.append("providers:list")
    if isinstance(probe.get("tools"), dict) and "tools" in probe["tools"]:
        caps.append("tools:list")
    return caps


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/self")
def federation_self(request: Request) -> Dict[str, Any]:
    base = str(request.base_url).rstrip("/")
    node_id = f"self_{base.replace('://', '_').replace(':', '_').replace('/', '_')}"
    return {"ok": True, "node": {"id": node_id, "address": base}}


def _list_local_listen_ports() -> List[int]:
    # Best effort: use lsof when available (macOS/Linux). If missing, return empty.
    try:
        out = subprocess.check_output(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"], text=True)
    except Exception:
        return []

    ports: set[int] = set()
    # Typical lsof line ends with "TCP *:52006 (LISTEN)" or "TCP 127.0.0.1:52006 (LISTEN)"
    m = re.compile(r"TCP\\s+[^:]+:(\\d+)\\s*\\(LISTEN\\)")
    for line in out.splitlines():
        mm = m.search(line)
        if not mm:
            continue
        try:
            p = int(mm.group(1))
        except Exception:
            continue
        if 1024 <= p <= 65535:
            ports.add(p)
    return sorted(list(ports))


@router.get("/discover/local")
async def discover_local_nodes(limit: int = Query(default=40, ge=1, le=200)) -> Dict[str, Any]:
    ports = _list_local_listen_ports()
    if not ports:
        return {"ok": True, "nodes": [], "source": "none"}

    ports = ports[: max(limit * 3, limit)]
    sem = asyncio.Semaphore(25)

    async def probe_port(port: int) -> Optional[Dict[str, Any]]:
        address = f"http://127.0.0.1:{port}"
        async with sem:
            try:
                timeout = httpx.Timeout(connect=0.25, read=0.5, write=0.5, pool=0.5)
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    r = await client.get(f"{address}/api/overview")
                    if r.status_code != 200:
                        return None
                    data = r.json()
                    if not isinstance(data, dict):
                        return None
                    # Minimal fingerprint: overview returns metrics + source.
                    if "metrics" not in data:
                        return None
                    name = f"OctopusOS localhost:{port}"
                    node_id = f"node_{port}"
                    return {"id": node_id, "name": name, "address": address, "overview": data}
            except Exception:
                return None

    tasks = [probe_port(p) for p in ports]
    results = await asyncio.gather(*tasks)
    nodes = [r for r in results if r]
    nodes = nodes[:limit]
    return {"ok": True, "nodes": nodes, "total": len(nodes), "source": "live"}


@router.post("/nodes/{node_id}/probe", response_model=ProbeResponse)
async def probe_federated_node(
    node_id: str,
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    secrets = _FederationSecretsStore.default()
    conn = db_connect()
    try:
        ensure_schema(conn)
        existing = _get_node_or_404(conn, node_id)
        address = _normalize_address(str(existing.get("address") or ""))
        _validate_address_ssrf_safe(address)

        try:
            probe = await _probe_remote_node(address, secrets.get_admin_token(node_id))
            capabilities = _capabilities_from_probe(probe)
            existing["capabilities"] = capabilities
            existing["metadata"] = {
                **dict(existing.get("metadata") or {}),
                "probe": {
                    "ok": True,
                    "at": _now_utc_iso(),
                    "overview": probe.get("overview"),
                },
            }
            existing["last_heartbeat"] = _now_utc_iso()
            # Keep status unless it was pending/error.
            if existing.get("status") in {"pending", "error"}:
                existing["status"] = "disconnected"
        except Exception as exc:
            existing["status"] = "error"
            existing["metadata"] = {
                **dict(existing.get("metadata") or {}),
                "probe": {
                    "ok": False,
                    "at": _now_utc_iso(),
                    "error": str(exc),
                },
            }

        existing["updated_at"] = now_iso()
        upsert_entity(conn, namespace="federation_nodes", entity_id=node_id, data=existing, status=str(existing.get("status") or "disconnected"))
        audit_event(conn, event_type="federation_node_probe", endpoint=f"/api/federation/nodes/{node_id}/probe", actor=actor, payload={}, result={"id": node_id, "status": existing.get("status")})
        node = _entity_to_node(node_id, existing)
        return {"node": node.model_dump(), "source": "live"}
    finally:
        conn.close()


@router.post("/nodes/{node_id}/connect", response_model=Dict[str, FederatedNodeModel])
async def connect_federation_node(
    node_id: str,
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    secrets = _FederationSecretsStore.default()
    try:
        ensure_schema(conn)
        existing = get_entity(conn, namespace="federation_nodes", entity_id=node_id)
        # Allow connect to create a node "on the fly" (UI may only have address).
        address = payload.get("address") if isinstance(payload, dict) else None
        if not existing:
            if not address:
                raise HTTPException(status_code=404, detail="Node not found")
            address_norm = _normalize_address(str(address))
            _validate_address_ssrf_safe(address_norm)
            existing = {
                "id": node_id,
                "name": str(payload.get("name") or node_id),
                "address": address_norm,
                "status": "pending",
                "trust_level": float(payload.get("trust_level") or 0.5),
                "capabilities": [],
                "metadata": {},
                "last_heartbeat": None,
                "connected_at": None,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
        else:
            existing["status"] = "pending"
            existing["updated_at"] = now_iso()
            if address:
                address_norm = _normalize_address(str(address))
                _validate_address_ssrf_safe(address_norm)
                existing["address"] = address_norm

        upsert_entity(conn, namespace="federation_nodes", entity_id=node_id, data=existing, status="pending")

        # Probe to validate connectivity and populate metadata.
        ok = False
        try:
            address_norm = _normalize_address(str(existing.get("address") or ""))
            _validate_address_ssrf_safe(address_norm)
            probe = await _probe_remote_node(address_norm, secrets.get_admin_token(node_id))
            existing["capabilities"] = _capabilities_from_probe(probe)
            existing["metadata"] = {
                **dict(existing.get("metadata") or {}),
                "probe": {"ok": True, "at": _now_utc_iso(), "overview": probe.get("overview")},
            }
            existing["last_heartbeat"] = _now_utc_iso()
            ok = True
        except Exception as exc:
            existing["metadata"] = {
                **dict(existing.get("metadata") or {}),
                "probe": {"ok": False, "at": _now_utc_iso(), "error": str(exc)},
            }

        if ok:
            existing["status"] = "connected"
            existing["connected_at"] = existing.get("connected_at") or _now_utc_iso()
        else:
            existing["status"] = "error"

        existing["updated_at"] = now_iso()
        upsert_entity(conn, namespace="federation_nodes", entity_id=node_id, data=existing, status=str(existing.get("status") or "disconnected"))
        audit_event(conn, event_type="federation_connect", endpoint=f"/api/federation/nodes/{node_id}/connect", actor=actor, payload=payload, result={"id": node_id, "status": existing.get("status")})
        node = _entity_to_node(node_id, existing)
        return {"node": node.model_dump()}
    finally:
        conn.close()


@router.post("/nodes/{node_id}/disconnect", response_model=Dict[str, FederatedNodeModel])
def disconnect_federation_node(
    node_id: str,
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        existing = _get_node_or_404(conn, node_id)
        existing["status"] = "disconnected"
        existing["updated_at"] = now_iso()
        upsert_entity(conn, namespace="federation_nodes", entity_id=node_id, data=existing, status="disconnected")
        audit_event(conn, event_type="federation_disconnect", endpoint=f"/api/federation/nodes/{node_id}/disconnect", actor=actor, payload={}, result={"id": node_id, "status": "disconnected"})
        node = _entity_to_node(node_id, existing)
        return {"node": node.model_dump()}
    finally:
        conn.close()
