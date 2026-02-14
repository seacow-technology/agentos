"""Compatibility router for models endpoints expected by apps/webui.

This router powers the WebUI /models page.

Goals:
- Split model management by local provider (ollama / lmstudio / llamacpp)
- Download/delete are executed via CLI (best-effort)
- Download progress is tracked via compat_entities in the main DB
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from octopusos.providers import platform_utils
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

router = APIRouter(prefix="/api/models", tags=["compat"])

LOCAL_MODEL_PROVIDERS = ("ollama", "lmstudio", "llamacpp")


def _model_entity_id(provider_id: str, model_name: str) -> str:
    return f"{provider_id}:{model_name}"


def _parse_percent(text: str) -> Optional[int]:
    m = re.search(r"(\d{1,3})%", text)
    if not m:
        return None
    try:
        val = int(m.group(1))
        if 0 <= val <= 100:
            return val
    except Exception:
        return None
    return None


def _run_cmd_lines(cmd: List[str], env: Optional[Dict[str, str]] = None) -> List[str]:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=20)
    except Exception:
        return []
    if res.returncode != 0:
        return []
    out = (res.stdout or "").splitlines()
    return [line.rstrip() for line in out if line.strip()]


def _list_ollama_models() -> List[str]:
    # `ollama list` output includes a header line.
    lines = _run_cmd_lines(["ollama", "list"])
    if len(lines) <= 1:
        return []
    names: List[str] = []
    for line in lines[1:]:
        parts = line.split()
        if parts:
            names.append(parts[0])
    return sorted(set(names))


def _list_dir_models(provider_id: str) -> List[str]:
    models_dir = platform_utils.get_models_dir(provider_id)
    if not models_dir or not models_dir.exists() or not models_dir.is_dir():
        return []
    names: List[str] = []
    for p in models_dir.iterdir():
        if provider_id == "llamacpp":
            if p.is_file() and p.name.lower().endswith(".gguf"):
                names.append(p.name)
        else:
            names.append(p.name)
    return sorted(set(names))


def _discover_models(provider_id: str) -> List[Dict[str, Any]]:
    if provider_id == "ollama":
        names = _list_ollama_models()
    else:
        names = _list_dir_models(provider_id)
    out: List[Dict[str, Any]] = []
    for name in names:
        out.append(
            {
                "id": _model_entity_id(provider_id, name),
                "name": name,
                "size": None,
                "status": "installed",
                "provider_id": provider_id,
                "provider": provider_id,
                "modified": now_iso(),
                "digest": "",
                "family": provider_id,
                "parameters": "",
            }
        )
    return out


def _build_models() -> List[Dict[str, Any]]:
    # Start from discovered models (best-effort), then overlay DB entities.
    models: List[Dict[str, Any]] = []
    for pid in LOCAL_MODEL_PROVIDERS:
        models.extend(_discover_models(pid))

    conn = db_connect()
    try:
        ensure_schema(conn)
        for item in list_entities(conn, namespace="models", include_deleted=False):
            model_id = item.get("id") or item.get("_entity_id")
            if not model_id:
                continue
            provider_id = str(item.get("provider_id") or "ollama")
            model = {
                "id": model_id,
                "name": item.get("name") or model_id,
                "size": item.get("size"),
                "status": item.get("status") or "installed",
                "provider_id": provider_id,
                "provider": provider_id,
                "modified": item.get("modified") or item.get("_updated_at") or now_iso(),
                "digest": item.get("digest") or "",
                "family": item.get("family") or provider_id,
                "parameters": item.get("parameters") or "",
                "last_error": item.get("last_error"),
            }
            models = [m for m in models if m["id"] != model_id]
            models.append(model)
    finally:
        conn.close()
    return models


@router.get("/list")
def list_models(provider_id: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
    models = _build_models()
    if provider_id:
        models = [m for m in models if m["provider_id"] == provider_id]
    if status:
        models = [m for m in models if m["status"] == status]
    return {"models": models, "total": len(models), "source": "compat"}


@router.post("/pull")
async def pull_model(request: Request) -> Dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid JSON payload")
    source = str(payload.get("model_name") or "").strip()
    if not source:
        raise HTTPException(status_code=400, detail="model_name is required")

    provider_id = str(payload.get("provider_id") or "ollama").strip()
    if provider_id not in LOCAL_MODEL_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider_id: {provider_id}")

    artifact_name = source
    if provider_id == "lmstudio":
        if source.startswith("http://") or source.startswith("https://"):
            artifact_name = source.split("/")[-1] or f"model_{uuid4().hex[:8]}"
        elif "/" in source:
            artifact_name = source.replace("/", "_")
        else:
            raise HTTPException(status_code=400, detail="LM Studio download requires a URL or HuggingFace repo id (org/name)")
    elif provider_id == "llamacpp":
        if source.startswith("http://") or source.startswith("https://"):
            artifact_name = source.split("/")[-1] or f"model_{uuid4().hex[:8]}.gguf"
        else:
            raise HTTPException(status_code=400, detail="llama.cpp download currently requires a direct URL to a .gguf file")

    installed = _list_ollama_models() if provider_id == "ollama" else _list_dir_models(provider_id)
    if artifact_name in installed:
        raise HTTPException(status_code=409, detail="Model already exists")

    task_id = f"pull_{uuid4().hex[:12]}"
    entity_id = _model_entity_id(provider_id, artifact_name)
    task = {
        "task_id": task_id,
        "model_name": artifact_name,
        "source": source,
        "provider_id": provider_id,
        "created_at": datetime.now(timezone.utc).timestamp(),
        "status": "running",
        "progress": 0,
        "indeterminate": False,
        "message": f"Pulling {artifact_name}",
        "error": None,
    }

    conn = db_connect()
    try:
        ensure_schema(conn)
        upsert_entity(conn, namespace="model_pull_tasks", entity_id=task_id, data=task, status="running")
        upsert_entity(
            conn,
            namespace="models",
            entity_id=entity_id,
            data={
                "id": entity_id,
                "name": artifact_name,
                "source": source,
                "status": "downloading",
                "provider_id": provider_id,
                "modified": now_iso(),
            },
            status="downloading",
        )
        audit_event(
            conn,
            event_type="model_pull_start",
            endpoint="/api/models/pull",
            actor="admin",
            payload=payload,
            result={"task_id": task_id, "model_name": artifact_name, "provider_id": provider_id, "source": source},
        )
        conn.commit()
    finally:
        conn.close()

    def _worker():
        started_at = time.time()
        progress = 0
        indeterminate = False
        last_update = 0.0

        def update_task(status: str, *, progress_val: int, message: str, error: Optional[str] = None):
            nonlocal last_update
            now = time.time()
            if status == "running" and now - last_update < 0.35:
                return
            last_update = now
            conn2 = db_connect()
            try:
                ensure_schema(conn2)
                task_row = get_entity(conn2, namespace="model_pull_tasks", entity_id=task_id) or {}
                data = dict(task_row)
                data.update(
                    {
                        "task_id": task_id,
                        "model_name": artifact_name,
                        "source": source,
                        "provider_id": provider_id,
                        "status": status,
                        "progress": int(progress_val),
                        "indeterminate": bool(indeterminate),
                        "message": message,
                        "error": error,
                    }
                )
                upsert_entity(conn2, namespace="model_pull_tasks", entity_id=task_id, data=data, status=status)
                if status == "completed":
                    upsert_entity(
                        conn2,
                        namespace="models",
                        entity_id=entity_id,
                        data={
                            "id": entity_id,
                            "name": artifact_name,
                            "source": source,
                            "status": "installed",
                            "provider_id": provider_id,
                            "modified": now_iso(),
                        },
                        status="installed",
                    )
                elif status == "failed":
                    upsert_entity(
                        conn2,
                        namespace="models",
                        entity_id=entity_id,
                        data={
                            "id": entity_id,
                            "name": artifact_name,
                            "source": source,
                            "status": "error",
                            "provider_id": provider_id,
                            "modified": now_iso(),
                            "last_error": error or message,
                        },
                        status="error",
                    )
            finally:
                conn2.close()

        env = os.environ.copy()
        cmd: List[str]

        if provider_id == "ollama":
            cmd = ["ollama", "pull", source]
        else:
            models_dir = platform_utils.get_models_dir(provider_id)
            if not models_dir:
                update_task("failed", progress_val=0, message="Download failed", error="Models directory not available")
                return
            models_dir.mkdir(parents=True, exist_ok=True)

            if source.startswith("http://") or source.startswith("https://"):
                curl = shutil.which("curl")
                if not curl:
                    update_task("failed", progress_val=0, message="Download failed", error="curl not found")
                    return
                dest_path = str(models_dir / artifact_name)
                cmd = [curl, "-L", "--progress-bar", source, "-o", dest_path]
            else:
                # LM Studio: HuggingFace repo id (org/name) into a folder.
                if provider_id != "lmstudio":
                    update_task("failed", progress_val=0, message="Download failed", error="Unsupported download source")
                    return
                hf = shutil.which("huggingface-cli")
                if not hf:
                    update_task("failed", progress_val=0, message="Download failed", error="huggingface-cli not found")
                    return
                local_dir = str(models_dir / artifact_name)
                cmd = [hf, "download", source, "--local-dir", local_dir]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
        except Exception as exc:
            update_task("failed", progress_val=0, message="Download failed", error=str(exc))
            return

        try:
            while True:
                line = proc.stdout.readline() if proc.stdout else ""
                if not line:
                    if proc.poll() is not None:
                        break
                    # No output: smooth progress for better UX (caps at 95%)
                    pseudo = int(min(95, (time.time() - started_at) * 3))
                    if pseudo > progress:
                        progress = pseudo
                        update_task("running", progress_val=progress, message=f"Pulling {artifact_name}")
                    time.sleep(0.1)
                    continue

                s = line.strip()
                if not s:
                    continue
                pct = _parse_percent(s)
                if pct is not None:
                    progress = max(progress, pct)
                else:
                    indeterminate = True
                update_task("running", progress_val=progress, message=s)

            proc.wait()
            if proc.returncode == 0:
                update_task("completed", progress_val=100, message="Completed")
            else:
                update_task(
                    "failed",
                    progress_val=max(0, min(progress, 99)),
                    message="Download failed",
                    error=f"exit={proc.returncode}",
                )
        finally:
            try:
                if proc.stdout:
                    proc.stdout.close()
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True).start()

    return {
        "model": {
            "id": entity_id,
            "name": artifact_name,
            "status": "downloading",
            "provider_id": provider_id,
        },
        "task_id": task_id,
        "source": "compat",
    }


@router.get("/pull/{task_id}/progress")
def pull_model_progress(task_id: str) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        task = get_entity(conn, namespace="model_pull_tasks", entity_id=task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Pull task not found")
        return {
            "progress": int(task.get("progress") or 0),
            "status": str(task.get("status") or "running"),
            "message": str(task.get("message") or f"Pulling {task.get('model_name')}"),
            "indeterminate": bool(task.get("indeterminate") or False),
            "error": task.get("error"),
            "source": "compat",
        }
    finally:
        conn.close()


@router.delete("/{model_id}")
def delete_model(model_id: str) -> Dict[str, Any]:
    provider_id: Optional[str] = None
    model_name = model_id
    if ":" in model_id:
        provider_id, model_name = model_id.split(":", 1)
        provider_id = provider_id.strip()
        model_name = model_name.strip()

    if provider_id and provider_id not in LOCAL_MODEL_PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported provider_id")

    # Best-effort actual deletion.
    if provider_id == "ollama":
        try:
            subprocess.run(["ollama", "rm", model_name], capture_output=True, text=True, timeout=30)
        except Exception:
            pass
    elif provider_id in ("lmstudio", "llamacpp"):
        models_dir = platform_utils.get_models_dir(provider_id)
        if models_dir:
            target = models_dir / model_name
            try:
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
            except Exception:
                pass

    conn = db_connect()
    try:
        ensure_schema(conn)
        soft_delete_entity(conn, namespace="models", entity_id=model_id)
        audit_event(
            conn,
            event_type="model_delete",
            endpoint=f"/api/models/{model_id}",
            actor="admin",
            payload={"model_id": model_id},
            result={"ok": True},
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "model_id": model_id, "source": "compat"}
