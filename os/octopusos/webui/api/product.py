"""Product Adapter API (Electron Product Shell).

This is intentionally small and user-facing:
- no provider/policy/store concepts
- default read-only actions
- evidence-first outputs (timeline + report + bundle)
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from octopusos.core.task import TaskManager
from octopusos.store import get_db
from octopusos.version import RELEASE_VERSION


router = APIRouter(prefix="/api/product", tags=["product"])
logger = logging.getLogger(__name__)
_LEGACY_MODE_BANNER_PRINTED = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _outputs_root() -> Path:
    # In packaged desktop, CWD is a writable data dir. In dev, it's repo root.
    return Path.cwd() / "outputs"


def _task_out_dir(task_id: str) -> Path:
    return _outputs_root() / task_id


def _short_ui_ref() -> str:
    # Human-facing, but still opaque.
    return f"p_{uuid4().hex[:10]}"


def _safe_relpath(p: Path, base: Path) -> str:
    try:
        return str(p.resolve().relative_to(base.resolve()))
    except Exception:
        return str(p)


def _load_task_by_ref(task_ref: str) -> Optional[Dict[str, Any]]:
    """Resolve ui_task_ref (preferred) or raw task_id to a task row dict."""
    task_ref = (task_ref or "").strip()
    if not task_ref:
        return None

    conn = get_db()
    conn.row_factory = getattr(conn, "row_factory", None) or None
    cursor = conn.cursor()

    # 1) Direct task_id hit.
    row = cursor.execute("SELECT * FROM tasks WHERE task_id = ? LIMIT 1", (task_ref,)).fetchone()
    if row:
        return dict(row)

    # 2) ui_task_ref hit inside metadata JSON.
    # NOTE: We keep this as a best-effort string match to avoid schema changes in v1.
    like = f'%\"ui_task_ref\": \"{task_ref}\"%'
    row = cursor.execute("SELECT * FROM tasks WHERE metadata LIKE ? ORDER BY created_at DESC LIMIT 1", (like,)).fetchone()
    if row:
        return dict(row)
    return None


def _task_card_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    metadata = {}
    try:
        metadata = json.loads(row.get("metadata") or "") if row.get("metadata") else {}
    except Exception:
        metadata = {}

    ui_ref = metadata.get("ui_task_ref") or row.get("task_id")
    out_dir = metadata.get("product_out_dir") or str(_task_out_dir(row.get("task_id", "")))
    preview = metadata.get("result_preview") or ""

    return {
        "ui_task_ref": ui_ref,
        "title": row.get("title") or "Task",
        "status": row.get("status") or "unknown",
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "result_preview": preview,
        "risk": metadata.get("risk") or {"tier": "read_only"},
        "action_id": metadata.get("product_action_id"),
        "out_dir": out_dir,
    }


def _merge_task_metadata(task_id: str, patch: Dict[str, Any]) -> None:
    """Best-effort JSON merge into tasks.metadata without introducing a new table in v1."""
    if not task_id:
        return
    conn = get_db()
    cur = conn.cursor()
    row = cur.execute("SELECT metadata FROM tasks WHERE task_id = ? LIMIT 1", (task_id,)).fetchone()
    base: Dict[str, Any] = {}
    try:
        if row and row["metadata"]:
            base = json.loads(row["metadata"]) or {}
    except Exception:
        base = {}
    try:
        base.update(patch or {})
    except Exception:
        return
    cur.execute("UPDATE tasks SET metadata = ?, updated_at = ? WHERE task_id = ?", (json.dumps(base, ensure_ascii=False), _now_iso(), task_id))
    conn.commit()


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _read_artifact_bytes(out_dir: Path, *, rel_new: str, legacy: str) -> Optional[bytes]:
    """Read artifact bytes using new path first, then legacy path."""
    p_new = out_dir / rel_new
    p_old = out_dir / legacy
    if p_new.exists() and p_new.is_file():
        return p_new.read_bytes()
    if p_old.exists() and p_old.is_file():
        return p_old.read_bytes()
    return None


def _artifact_exists(out_dir: Path, *, rel_new: str, legacy: str) -> bool:
    p_new = out_dir / rel_new
    if p_new.exists() and p_new.is_file():
        return True
    p_old = out_dir / legacy
    return p_old.exists() and p_old.is_file()


def _legacy_write_mode() -> str:
    """Three-state compatibility knob for evidence artifacts.

    Env:
      OCTOPUSOS_PRODUCT_LEGACY_WRITE_MODE=off|mirror|legacy_only

    - off: write new paths only (target steady state)
    - mirror: write new + legacy root (temporary migration default)
    - legacy_only: write legacy root only (emergency rollback)
    """
    global _LEGACY_MODE_BANNER_PRINTED
    raw = (os.getenv("OCTOPUSOS_PRODUCT_LEGACY_WRITE_MODE") or "").strip().lower()
    mode = raw or "mirror"
    if mode not in {"off", "mirror", "legacy_only"}:
        mode = "mirror"
    if not _LEGACY_MODE_BANNER_PRINTED:
        _LEGACY_MODE_BANNER_PRINTED = True
        if mode == "mirror":
            logger.warning(
                "Product evidence legacy write mode: mirror (temporary). "
                "Set OCTOPUSOS_PRODUCT_LEGACY_WRITE_MODE=off to disable legacy root mirrors."
            )
        else:
            logger.info("Product evidence legacy write mode: %s", mode)
    return mode


def _write_artifact(out_dir: Path, *, name: str, content: bytes) -> None:
    mode = _legacy_write_mode()
    if mode in {"off", "mirror"}:
        _ensure_dir(out_dir / "artifacts")
        (out_dir / "artifacts" / name).write_bytes(content)
    if mode in {"mirror", "legacy_only"}:
        (out_dir / name).write_bytes(content)


@router.post("/actions/run")
def run_action(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    action_id = (payload.get("action_id") or "").strip()
    action_payload = payload.get("payload") or {}
    if action_id != "analyze_repo":
        raise HTTPException(status_code=400, detail=f"unknown_action_id: {action_id}")

    repo_path = str((action_payload.get("repo_path") or "")).strip()
    if not repo_path:
        raise HTTPException(status_code=400, detail="missing repo_path")

    repo = Path(repo_path).expanduser()
    if not repo.exists() or not repo.is_dir():
        raise HTTPException(status_code=400, detail="repo_path must be an existing directory")

    ui_ref = _short_ui_ref()
    title = f"Analyze repo: {repo.name}"
    tm = TaskManager()
    task = tm.create_task(
        title=title,
        created_by="product",
        metadata={
            "product": True,
            "product_action_id": "analyze_repo",
            "ui_task_ref": ui_ref,
            "read_only": True,
            "repo_path": str(repo),
            "result_preview": "",
        },
    )
    tm.update_task_status(task.task_id, "executing")

    out_dir = _task_out_dir(task.task_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Persist out dir for UI (so Product doesn't need to compute it).
    _merge_task_metadata(task.task_id, {"product_out_dir": str(out_dir)})

    def worker() -> None:
        try:
            report, timeline = analyze_repo(repo, out_dir=out_dir, ui_task_ref=ui_ref)
            report_bytes = json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8")
            timeline_bytes = json.dumps(timeline, indent=2, ensure_ascii=False).encode("utf-8")

            # P0.2: write new layout; optionally mirror legacy root files (env controlled).
            _write_artifact(out_dir, name="report.json", content=report_bytes)
            _write_artifact(out_dir, name="timeline.json", content=timeline_bytes)
            manifest = {
                "bundle_version": "1.1",
                "generated_at": _now_iso(),
                "task_ref": ui_ref,
                "task_id": task.task_id,
                "action_id": "analyze_repo",
                "run_mode": "assisted",
                "policy": {"applied": True, "policy_id": "product_read_only_v1"},
                "inputs": {
                    "repo_path": str(repo),
                    "read_only": True,
                    "audit_depth": report.get("audit_depth") or "heuristic_v1",
                },
                "outputs": {
                    "report": {"path": "artifacts/report.json", "schema_version": report.get("schema_version")},
                    "timeline": {"path": "artifacts/timeline.json", "schema_version": timeline.get("schema_version")},
                    "diff": None,
                },
                "notes": [
                    "missing_deep_checks: " + ", ".join(report.get("missing_deep_checks") or []),
                ],
            }

            bundle_path = build_evidence_bundle(out_dir, manifest=manifest)

            _merge_task_metadata(
                task.task_id,
                {
                    "result_preview": report.get("result_preview") or "Report ready",
                    "product_artifacts": {
                        "report": "report.json",
                        "timeline": "timeline.json",
                        "bundle": bundle_path.name,
                    },
                    "product_bundle_version": "1.1",
                },
            )
            tm.update_task_status(task.task_id, "succeeded")
        except Exception as e:
            _merge_task_metadata(task.task_id, {"result_preview": f"Failed: {e}"})
            tm.update_task_status(task.task_id, "failed")

    threading.Thread(target=worker, name=f"product-analyze-{task.task_id[:8]}", daemon=True).start()

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "action_id": action_id,
            "task_id": task.task_id,     # internal
            "ui_task_ref": ui_ref,       # for Product
        },
    )


@router.get("/tasks")
def list_tasks(limit: int = Query(20, ge=1, le=200)) -> JSONResponse:
    conn = get_db()
    conn.row_factory = getattr(conn, "row_factory", None) or None
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT * FROM tasks WHERE json_extract(metadata, '$.product') = 1 ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    tasks = [_task_card_from_row(dict(r)) for r in rows]
    return JSONResponse(status_code=200, content={"ok": True, "tasks": tasks})


@router.get("/tasks/{task_ref}/plan")
def get_plan(task_ref: str) -> JSONResponse:
    row = _load_task_by_ref(task_ref)
    if not row:
        raise HTTPException(status_code=404, detail="task not found")
    metadata = {}
    try:
        metadata = json.loads(row.get("metadata") or "") if row.get("metadata") else {}
    except Exception:
        metadata = {}

    action_id = metadata.get("product_action_id") or "unknown"
    if action_id == "analyze_repo":
        plan = {
            "title": "Analyze a repo (read-only)",
            "summary": [
                "Scan module structure + language fingerprint",
                "Collect TODO/FIXME",
                "Heuristic dependency risk (pinned/unpinned + lockfile presence)",
                "Git hotspot files (commit touch frequency)",
                "Secret risk scan (masked, never prints raw values)",
            ],
            "writes": [
                "outputs/<task_id>/report.json",
                "outputs/<task_id>/timeline.json",
                "outputs/<task_id>/evidence_bundle.zip",
            ],
            "approval_required": False,
        }
        return JSONResponse(status_code=200, content={"ok": True, "plan": plan})

    return JSONResponse(status_code=200, content={"ok": True, "plan": {"title": "Plan", "summary": [], "approval_required": True}})


@router.post("/tasks/{task_ref}/approve")
def approve_task(task_ref: str) -> JSONResponse:
    # v1: allow the Product to trigger approval without exposing internal semantics.
    row = _load_task_by_ref(task_ref)
    if not row:
        raise HTTPException(status_code=404, detail="task not found")
    _merge_task_metadata(row["task_id"], {"product_approved_at": _now_iso()})
    return JSONResponse(status_code=200, content={"ok": True})


@router.post("/tasks/{task_ref}/cancel")
def cancel_task(task_ref: str) -> JSONResponse:
    row = _load_task_by_ref(task_ref)
    if not row:
        raise HTTPException(status_code=404, detail="task not found")
    tm = TaskManager()
    tm.update_task_status(row["task_id"], "canceled")
    _merge_task_metadata(row["task_id"], {"result_preview": "Canceled"})
    return JSONResponse(status_code=200, content={"ok": True})


@router.get("/tasks/{task_ref}/evidence")
def get_evidence(task_ref: str, tz: str = Query("UTC")) -> JSONResponse:
    row = _load_task_by_ref(task_ref)
    if not row:
        raise HTTPException(status_code=404, detail="task not found")
    metadata = {}
    try:
        metadata = json.loads(row.get("metadata") or "") if row.get("metadata") else {}
    except Exception:
        metadata = {}

    task_id = row.get("task_id") or ""
    out_dir = Path(metadata.get("product_out_dir") or _task_out_dir(task_id))
    artifacts = (metadata.get("product_artifacts") or {}) if isinstance(metadata.get("product_artifacts"), dict) else {}

    def exists(name: str) -> bool:
        return bool(name) and (out_dir / name).exists()

    bundle_name = str(artifacts.get("bundle") or "evidence_bundle.zip")
    report_name = str(artifacts.get("report") or "report.json")
    timeline_name = str(artifacts.get("timeline") or "timeline.json")

    bundle_meta = _file_meta(out_dir, bundle_name) if exists(bundle_name) else None
    manifest_preview = None
    bundle_version = None
    try:
        mp = out_dir / "manifest.json"
        if mp.exists():
            m = json.loads(mp.read_text(encoding="utf-8"))
            bundle_version = m.get("bundle_version")
            # Small, stable subset for UI (avoid leaking internal system details).
            manifest_preview = {
                "bundle_version": m.get("bundle_version"),
                "generated_at": m.get("generated_at"),
                "task_ref": m.get("task_ref"),
                "action_id": m.get("action_id"),
                "inputs": m.get("inputs"),
                "outputs": m.get("outputs"),
                "notes": m.get("notes"),
            }
    except Exception:
        manifest_preview = None

    evidence = {
        "task": _task_card_from_row(row),
        "out_dir": str(out_dir),
        "files": {
            # Keep Product download stable: legacy filenames are still present for now.
            # If legacy files are removed in future, download endpoint supports nested paths.
            "report": report_name if (exists(report_name) or _artifact_exists(out_dir, rel_new="artifacts/report.json", legacy=report_name)) else None,
            "timeline": timeline_name if (exists(timeline_name) or _artifact_exists(out_dir, rel_new="artifacts/timeline.json", legacy=timeline_name)) else None,
            "bundle": bundle_name if exists(bundle_name) else None,
        },
        "bundle_meta": bundle_meta,
        "bundle_version": bundle_version,
        "manifest_preview": manifest_preview,
        "legacy_write_mode": _legacy_write_mode(),
        "download_base": f"/api/product/tasks/{task_ref}/evidence/download",
    }
    try:
        evidence["copy_text"] = build_share_text(
            task_ref=str(metadata.get("ui_task_ref") or task_id or task_ref),
            task_id=str(task_id),
            action_id=str(metadata.get("product_action_id") or "unknown"),
            out_dir=out_dir,
            tz=str(tz or "UTC"),
            download_base=str(evidence["download_base"]),
        )
    except Exception:
        evidence["copy_text"] = ""
    return JSONResponse(status_code=200, content={"ok": True, "evidence": evidence})


def _load_json_bytes(b: Optional[bytes]) -> Optional[Dict[str, Any]]:
    if not b:
        return None
    try:
        return json.loads(b.decode("utf-8"))
    except Exception:
        try:
            return json.loads(b.decode("utf-8", errors="ignore"))
        except Exception:
            return None


def _stage_label(step: str) -> str:
    m = {
        "structure": "Scanned repository structure",
        "todo_fixme": "Extracted TODO/FIXME",
        "dependency_risk": "Checked dependency risk (heuristics)",
        "git_hotspots": "Computed git hotspots",
        "secret_risk": "Scanned secret risks (masked)",
    }
    return m.get(step, step.replace("_", " ").strip() or "step")


def _build_copy_summary(payload: Dict[str, Any], *, tz: str) -> str:
    task_ref = payload.get("task_ref") or ""
    action_id = payload.get("action_id") or ""
    generated_at = payload.get("generated_at") or ""
    summary = payload.get("summary") or {}
    metrics_line = summary.get("metrics_line") or ""
    notes = summary.get("notes") or []
    evidence = payload.get("evidence") or {}
    bundle = evidence.get("bundle") or {}
    bfile = bundle.get("filename") or ""
    bsha = bundle.get("sha256") or ""
    nline = "; ".join([str(x) for x in notes if str(x).strip()][:4])
    return (
        f"OctopusOS Replay — {task_ref}\n"
        f"Action: {action_id} (read-only)\n"
        f"Result: {metrics_line}\n"
        f"Bundle: {bfile}\n"
        f"SHA256: {bsha}\n"
        f"Generated: {generated_at} ({tz})\n"
        f"Notes: {nline or '(none)'}\n"
    )


def build_share_text(
    *,
    task_ref: str,
    task_id: str,
    action_id: str,
    out_dir: Path,
    tz: str,
    download_base: str,
) -> str:
    """Return the exact share text used by Product UI (stable template)."""
    rp = build_replay_payload(
        task_ref=task_ref,
        task_id=task_id,
        action_id=action_id,
        out_dir=out_dir,
        tz=tz,
        download_base=download_base,
    )
    return str(rp.get("copy_text") or "")


def build_replay_payload(
    *,
    task_ref: str,
    task_id: str,
    action_id: str,
    out_dir: Path,
    tz: str,
    download_base: str,
) -> Dict[str, Any]:
    """Build a product-facing replay pack. Offline-only (no network calls)."""
    # Load report + timeline using "new first, legacy fallback".
    report = _load_json_bytes(_read_artifact_bytes(out_dir, rel_new="artifacts/report.json", legacy="report.json")) or {}
    timeline_raw = _load_json_bytes(_read_artifact_bytes(out_dir, rel_new="artifacts/timeline.json", legacy="timeline.json")) or {}

    manifest = None
    try:
        mp = out_dir / "manifest.json"
        if mp.exists():
            manifest = json.loads(mp.read_text(encoding="utf-8"))
    except Exception:
        manifest = None

    checksums = None
    try:
        cp = out_dir / "checksums.json"
        if cp.exists():
            checksums = json.loads(cp.read_text(encoding="utf-8"))
    except Exception:
        checksums = None

    # Evidence bundle meta (zip file itself).
    bundle_meta = _file_meta(out_dir, "evidence_bundle.zip")
    bundle = {
        "filename": "evidence_bundle.zip",
        "sha256": (bundle_meta or {}).get("sha256"),
        "bytes": (bundle_meta or {}).get("bytes"),
        "download_url": f"{download_base}/evidence_bundle.zip",
    }

    # Files included: use checksums.json when available; fall back to reading disk.
    included: List[Dict[str, Any]] = []
    include_paths = ["manifest.json", "checksums.json", "artifacts/report.json", "artifacts/timeline.json"]

    # Optional reserved paths: only include if present in checksums files map.
    try:
        files_map = (checksums or {}).get("files") or {}
        if "artifacts/diff.patch" in files_map:
            include_paths.append("artifacts/diff.patch")
        if "artifacts/changes.json" in files_map:
            include_paths.append("artifacts/changes.json")
        if "logs/run.log" in files_map:
            include_paths.append("logs/run.log")
    except Exception:
        pass

    for p in include_paths:
        if p == "manifest.json":
            b = json.dumps(manifest or {}, indent=2, ensure_ascii=False).encode("utf-8") if manifest is not None else None
            if b is None:
                # Fallback: bundle manifest is always written during bundling; read disk.
                try:
                    b = (out_dir / "manifest.json").read_bytes()
                except Exception:
                    b = None
            if b is None:
                continue
            included.append({"path": p, "bytes": len(b), "sha256": _sha256_bytes(b)})
            continue
        if p == "checksums.json":
            try:
                b = (out_dir / "checksums.json").read_bytes()
                included.append({"path": p, "bytes": len(b), "sha256": _sha256_bytes(b)})
            except Exception:
                continue
            continue
        if p == "artifacts/report.json":
            b = _read_artifact_bytes(out_dir, rel_new="artifacts/report.json", legacy="report.json")
            if b is None:
                continue
            included.append({"path": p, "bytes": len(b), "sha256": _sha256_bytes(b)})
            continue
        if p == "artifacts/timeline.json":
            b = _read_artifact_bytes(out_dir, rel_new="artifacts/timeline.json", legacy="timeline.json")
            if b is None:
                continue
            included.append({"path": p, "bytes": len(b), "sha256": _sha256_bytes(b)})
            continue
        # Optional files: best-effort read from disk (new preferred).
        try:
            b = (out_dir / p).read_bytes()
            included.append({"path": p, "bytes": len(b), "sha256": _sha256_bytes(b)})
        except Exception:
            continue

    # Build product timeline.
    steps = (timeline_raw or {}).get("steps") or []
    timeline: List[Dict[str, Any]] = []
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            continue
        st = str(s.get("step") or "")
        timeline.append(
            {
                "index": i + 1,
                "stage": st or "step",
                "label": _stage_label(st),
                "ok": bool(s.get("ok", True)),
                "detail": (str(s.get("error") or "").strip() or None),
                "duration_ms": int(s.get("duration_ms") or 0),
            }
        )

    # Summary (user-facing, no system jargon).
    metrics_line = str(report.get("result_preview") or "").strip()
    stats = (report.get("summary") or {}) if isinstance(report.get("summary"), dict) else {}
    notes = [
        f"audit_depth: {report.get('audit_depth') or 'unknown'}",
        "missing_deep_checks: " + ", ".join(report.get("missing_deep_checks") or []),
    ]
    headline = "Repo analyzed (read-only)" if action_id == "analyze_repo" else "Task completed"

    generated_at = None
    if manifest and isinstance(manifest, dict) and manifest.get("generated_at"):
        generated_at = manifest.get("generated_at")
    if not generated_at:
        generated_at = report.get("generated_at") or timeline_raw.get("generated_at") or _now_iso()

    payload = {
        "replay_version": 1,
        "task_ref": task_ref,
        "task_id": task_id,
        "action_id": action_id,
        "generated_at": generated_at,
        "summary": {
            "headline": headline,
            "metrics_line": metrics_line or "Report not ready yet",
            "stats": stats,
            "notes": notes,
            "inputs": {
                "repo_path": (manifest or {}).get("inputs", {}).get("repo_path") if isinstance(manifest, dict) else report.get("repo", {}).get("path"),
                "read_only": True,
                "audit_depth": report.get("audit_depth"),
            },
        },
        "timeline": timeline,
        "evidence": {
            "bundle": bundle,
            "files": included,
        },
    }
    payload["copy_text"] = _build_copy_summary(payload, tz=tz)
    return payload


@router.get("/tasks/{task_ref}/replay")
def get_replay(task_ref: str, tz: str = Query("UTC")) -> JSONResponse:
    row = _load_task_by_ref(task_ref)
    if not row:
        raise HTTPException(status_code=404, detail="task not found")
    metadata = {}
    try:
        metadata = json.loads(row.get("metadata") or "") if row.get("metadata") else {}
    except Exception:
        metadata = {}

    task_id = row.get("task_id") or ""
    action_id = metadata.get("product_action_id") or "unknown"
    ui_ref = metadata.get("ui_task_ref") or task_id
    out_dir = Path(metadata.get("product_out_dir") or _task_out_dir(task_id))
    download_base = f"/api/product/tasks/{task_ref}/evidence/download"

    payload = build_replay_payload(
        task_ref=str(ui_ref),
        task_id=str(task_id),
        action_id=str(action_id),
        out_dir=out_dir,
        tz=str(tz or "UTC"),
        download_base=download_base,
    )
    # Hide internal task_id by default; keep it for technical details only.
    payload.pop("task_id", None)
    return JSONResponse(status_code=200, content={"ok": True, "replay": payload})


@router.get("/tasks/{task_ref}/evidence/download/{filename:path}")
def download_evidence_file(task_ref: str, filename: str) -> FileResponse:
    row = _load_task_by_ref(task_ref)
    if not row:
        raise HTTPException(status_code=404, detail="task not found")
    metadata = {}
    try:
        metadata = json.loads(row.get("metadata") or "") if row.get("metadata") else {}
    except Exception:
        metadata = {}

    task_id = row.get("task_id") or ""
    out_dir = Path(metadata.get("product_out_dir") or _task_out_dir(task_id)).resolve()
    target = (out_dir / filename).resolve()
    if out_dir not in target.parents and target != out_dir:
        raise HTTPException(status_code=400, detail="invalid filename")
    if not target.exists() or not target.is_file():
        # P0.2 compatibility: map legacy report/timeline to new artifacts path if needed.
        if filename in {"report.json", "timeline.json"}:
            mapped = (out_dir / "artifacts" / filename).resolve()
            if out_dir in mapped.parents and mapped.exists() and mapped.is_file():
                target = mapped
            else:
                raise HTTPException(status_code=404, detail="file not found")
        else:
            raise HTTPException(status_code=404, detail="file not found")

    # User-facing filename for evidence bundle should be stable and shareable.
    dl_name = target.name
    if target.name == "evidence_bundle.zip":
        ui_ref = None
        try:
            ui_ref = (json.loads(row.get("metadata") or "{}") or {}).get("ui_task_ref")
        except Exception:
            ui_ref = None
        dl_name = f"octopusos_evidence_{(ui_ref or row.get('task_id') or 'task')}.zip"
    media = "application/zip" if target.suffix.lower() == ".zip" else None
    return FileResponse(path=str(target), filename=dl_name, media_type=media)


# -------------------------
# Analyze Repo (read-only)
# -------------------------

_DEFAULT_IGNORES = {
    ".git",
    "node_modules",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".next",
    ".turbo",
    ".idea",
    ".vscode",
    "outputs",
    "output",
    "tmp",
}


def _iter_text_files(root: Path, deadline: float) -> Tuple[List[Path], bool]:
    files: List[Path] = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root):
        if time.monotonic() > deadline:
            truncated = True
            break
        # mutate in place for os.walk pruning
        dirnames[:] = [d for d in dirnames if d not in _DEFAULT_IGNORES and not d.startswith(".")]
        for name in filenames:
            if time.monotonic() > deadline:
                truncated = True
                break
            if name.startswith("."):
                continue
            p = Path(dirpath) / name
            try:
                if p.is_symlink():
                    continue
                if p.stat().st_size > 512 * 1024:
                    continue
            except Exception:
                continue
            files.append(p)
        if truncated:
            break
        if len(files) > 5000:
            truncated = True
            break
    return files, truncated


def analyze_repo(repo: Path, out_dir: Path, ui_task_ref: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    started = time.monotonic()
    deadline = started + 8.5  # target: <10s end-to-end including zipping

    timeline: List[Dict[str, Any]] = []

    def step(name: str, fn):
        t0 = time.monotonic()
        try:
            out = fn()
            ok = True
            err = None
        except Exception as e:
            out = None
            ok = False
            err = str(e)
        timeline.append(
            {
                "step": name,
                "ok": ok,
                "error": err,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            }
        )
        return out

    def structure() -> Dict[str, Any]:
        # "Modules" is a product-facing heuristic: top-level non-hidden dirs excluding common ignores.
        module_dirs: List[str] = []
        try:
            for child in repo.iterdir():
                if not child.is_dir():
                    continue
                name = child.name
                if name.startswith("."):
                    continue
                if name in _DEFAULT_IGNORES:
                    continue
                module_dirs.append(name)
        except Exception:
            module_dirs = []

        entries = {
            "package.json": (repo / "package.json").exists(),
            "pyproject.toml": (repo / "pyproject.toml").exists(),
            "requirements.txt": (repo / "requirements.txt").exists(),
            "Cargo.toml": (repo / "Cargo.toml").exists(),
            "go.mod": (repo / "go.mod").exists(),
            "docker-compose.yml": (repo / "docker-compose.yml").exists() or (repo / "docker-compose.yaml").exists(),
        }
        # Languages by extension (best-effort).
        exts: Dict[str, int] = {}
        files, truncated = _iter_text_files(repo, deadline)
        for p in files:
            ext = (p.suffix.lower() or "<noext>")
            exts[ext] = exts.get(ext, 0) + 1
        top_exts = sorted(exts.items(), key=lambda x: x[1], reverse=True)[:12]
        entrypoints = []
        for cand in ("main.py", "app.py", "server.py", "index.ts", "index.js", "src/main.ts", "src/index.ts", "src/index.js"):
            if (repo / cand).exists():
                entrypoints.append(cand)
        return {
            "module_dirs": sorted(module_dirs)[:80],
            "module_count": len(module_dirs),
            "signals": entries,
            "top_extensions": top_exts,
            "entrypoints": entrypoints,
            "truncated": truncated,
        }

    def todos() -> Dict[str, Any]:
        rx = re.compile(r"\b(TODO|FIXME)\b", re.IGNORECASE)
        items: List[Dict[str, Any]] = []
        count = 0
        files, truncated = _iter_text_files(repo, deadline)
        for p in files:
            if time.monotonic() > deadline:
                truncated = True
                break
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if rx.search(line):
                    count += 1
                    if len(items) < 250:
                        items.append(
                            {
                                "file": _safe_relpath(p, repo),
                                "line": i,
                                "text": (line.strip()[:220]),
                            }
                        )
        return {"count": count, "items": items, "truncated": truncated or (count > len(items))}

    def deps_risk() -> Dict[str, Any]:
        findings: List[Dict[str, Any]] = []
        pkg = repo / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text(encoding="utf-8"))
                deps = {}
                deps.update(data.get("dependencies") or {})
                deps.update(data.get("devDependencies") or {})
                for name, ver in deps.items():
                    v = str(ver)
                    if v.strip() in {"*", "latest"} or v.strip().startswith(("^", "~")):
                        findings.append({"ecosystem": "npm", "package": name, "version": v, "risk": "unpinned"})
                if not (repo / "package-lock.json").exists() and not (repo / "pnpm-lock.yaml").exists() and not (repo / "yarn.lock").exists():
                    findings.append({"ecosystem": "npm", "package": "*", "version": "", "risk": "missing_lockfile"})
            except Exception:
                pass
        pyproj = repo / "pyproject.toml"
        if pyproj.exists():
            try:
                import tomllib  # py>=3.11
                data = tomllib.loads(pyproj.read_text(encoding="utf-8"))
                deps = (data.get("project") or {}).get("dependencies") or []
                for spec in deps:
                    s = str(spec)
                    if "==" not in s:
                        findings.append({"ecosystem": "python", "package": s.split()[0], "version": s, "risk": "unpinned"})
            except Exception:
                pass
        req = repo / "requirements.txt"
        if req.exists():
            try:
                for line in req.read_text(encoding="utf-8", errors="ignore").splitlines():
                    s = line.strip()
                    if not s or s.startswith("#"):
                        continue
                    if "==" not in s and not s.startswith(("-e ", "git+", "http")):
                        findings.append({"ecosystem": "python", "package": s.split()[0], "version": s, "risk": "unpinned"})
            except Exception:
                pass
        return {
            "mode": "static_heuristics",
            "findings": findings[:200],
            "note": "v1: fast static heuristics only (no network CVE lookup). Run audits in System Console for deeper checks.",
        }

    def git_hotspots() -> Dict[str, Any]:
        if not (repo / ".git").exists():
            return {"available": False, "hotspots": []}
        import subprocess

        try:
            p = subprocess.run(
                ["git", "-C", str(repo), "log", "--name-only", "--pretty=format:"],
                capture_output=True,
                text=True,
                timeout=3.5,
                check=False,
            )
            if p.returncode != 0:
                return {"available": False, "hotspots": [], "error": (p.stderr or "git log failed")[:200]}
            counts: Dict[str, int] = {}
            for line in (p.stdout or "").splitlines():
                f = line.strip()
                if not f:
                    continue
                counts[f] = counts.get(f, 0) + 1
            top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:12]
            return {"available": True, "hotspots": [{"file": f, "touches": n} for f, n in top]}
        except Exception as e:
            return {"available": False, "hotspots": [], "error": str(e)[:200]}

    def secret_risk() -> Dict[str, Any]:
        # Only emit masked evidence; never raw values.
        patterns = [
            ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
            ("GitHub Token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
            ("OpenAI Key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
            ("Slack Token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
            ("Generic API Key", re.compile(r"(?i)\b(api[_-]?key|secret|token)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]")),
        ]
        findings: List[Dict[str, Any]] = []
        files, truncated = _iter_text_files(repo, deadline)
        for p in files:
            if time.monotonic() > deadline:
                truncated = True
                break
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for (label, rx) in patterns:
                for m in rx.finditer(text):
                    if len(findings) >= 120:
                        truncated = True
                        break
                    raw = m.group(0)
                    masked = raw
                    if len(raw) > 10:
                        masked = raw[:4] + "…" + raw[-4:]
                    findings.append(
                        {
                            "kind": label,
                            "file": _safe_relpath(p, repo),
                            "preview": masked,
                        }
                    )
                if truncated:
                    break
        return {"count": len(findings), "findings": findings, "truncated": truncated}

    s = step("structure", structure) or {}
    t = step("todo_fixme", todos) or {}
    d = step("dependency_risk", deps_risk) or {}
    g = step("git_hotspots", git_hotspots) or {}
    sec = step("secret_risk", secret_risk) or {}

    elapsed_ms = int((time.monotonic() - started) * 1000)
    # Product-facing summary used for task cards without requiring a click.
    module_count = int((s or {}).get("module_count") or 0)
    todo_count = int((t or {}).get("count") or 0)
    secrets_count = int((sec or {}).get("count") or 0)
    hotspots_count = int(len((g or {}).get("hotspots") or []))
    report = {
        "schema_version": "product.analyze_repo.v1",
        "audit_depth": "heuristic_v1",
        "missing_deep_checks": ["cve_lookup", "license_scan", "full_dependency_tree", "lockfile_resolution"],
        "generated_at": _now_iso(),
        "runtime_version": RELEASE_VERSION,
        "analysis_ms": elapsed_ms,
        "ui_task_ref": ui_task_ref,
        "repo": {"path": str(repo), "name": repo.name},
        "summary": {
            "modules": module_count,
            "todo_fixme": todo_count,
            "secret_risks": secrets_count,
            "git_hotspots": hotspots_count,
        },
        "structure": s,
        "todo_fixme": t,
        "dependency_risk": d,
        "git": g,
        "secret_risk": sec,
        "result_preview": f"Modules: {module_count} · TODO: {todo_count} · Secrets: {secrets_count} (masked)",
    }
    return report, {"schema_version": "product.timeline.v1", "generated_at": _now_iso(), "steps": timeline}


def build_evidence_bundle(
    out_dir: Path,
    *,
    manifest: Dict[str, Any],
) -> Path:
    """Create evidence bundle zip with stable, verifiable structure (v1.1)."""
    bundle = out_dir / "evidence_bundle.zip"
    tmp = out_dir / ".evidence_bundle.tmp.zip"

    manifest_json = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")

    # Build file payloads for the zip (content-addressed via checksums.json).
    payloads: Dict[str, bytes] = {}
    payloads["manifest.json"] = manifest_json
    report_bytes = _read_artifact_bytes(out_dir, rel_new="artifacts/report.json", legacy="report.json")
    timeline_bytes = _read_artifact_bytes(out_dir, rel_new="artifacts/timeline.json", legacy="timeline.json")
    if report_bytes is None or timeline_bytes is None:
        raise RuntimeError("Missing required artifacts: report.json and timeline.json (new or legacy paths)")
    payloads["artifacts/report.json"] = report_bytes
    payloads["artifacts/timeline.json"] = timeline_bytes

    # Optional future artifacts (pre-reserved by contract).
    # Prefer new layout, fallback to legacy roots.
    diff_p = out_dir / "artifacts" / "diff.patch"
    changes_p = out_dir / "artifacts" / "changes.json"
    runlog_p = out_dir / "logs" / "run.log"
    if diff_p.exists():
        payloads["artifacts/diff.patch"] = diff_p.read_bytes()
    else:
        legacy = out_dir / "diff.patch"
        if legacy.exists():
            payloads["artifacts/diff.patch"] = legacy.read_bytes()
    if changes_p.exists():
        payloads["artifacts/changes.json"] = changes_p.read_bytes()
    else:
        legacy = out_dir / "changes.json"
        if legacy.exists():
            payloads["artifacts/changes.json"] = legacy.read_bytes()
    if runlog_p.exists():
        payloads["logs/run.log"] = runlog_p.read_bytes()
    else:
        legacy = out_dir / "run.log"
        if legacy.exists():
            payloads["logs/run.log"] = legacy.read_bytes()

    # checksums.json covers every file in the bundle except itself (avoid recursion).
    checksums = {
        "algorithm": "sha256",
        "files": {k: _sha256_bytes(v) for k, v in sorted(payloads.items(), key=lambda x: x[0])},
    }
    checksums_json = json.dumps(checksums, indent=2, ensure_ascii=False).encode("utf-8")

    # Write sidecar files to the task output dir for easy inspection (optional but useful).
    (out_dir / "manifest.json").write_bytes(manifest_json)
    (out_dir / "checksums.json").write_bytes(checksums_json)

    # Write zip deterministically.
    if tmp.exists():
        try:
            tmp.unlink()
        except Exception:
            pass
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, content in sorted(payloads.items(), key=lambda x: x[0]):
            z.writestr(name, content)
        z.writestr("checksums.json", checksums_json)
    tmp.replace(bundle)
    return bundle


def _sha256_bytes(b: bytes) -> str:
    import hashlib

    h = hashlib.sha256()
    h.update(b or b"")
    return h.hexdigest()


def _sha256_file(p: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 256), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_meta(out_dir: Path, filename: str) -> Optional[Dict[str, Any]]:
    if not filename:
        return None
    p = (out_dir / filename)
    if not p.exists() or not p.is_file():
        return None
    try:
        st = p.stat()
        return {
            "filename": filename,
            "bytes": int(st.st_size),
            "sha256": _sha256_file(p),
        }
    except Exception:
        return {"filename": filename}


@router.get("/insights/week")
def insights_week(tz: str = Query("UTC")) -> JSONResponse:
    """Weekly insights for Product Home.

    Contract:
    - Always include confidence + notes so Product never "lies with numbers".
    - Prefer stable, queryable sources (llm_usage_events) over UI-local estimates.
    """
    from zoneinfo import ZoneInfo

    tz_raw = (tz or "").strip() or "UTC"
    notes: List[str] = []
    try:
        zone = ZoneInfo(tz_raw)
    except Exception:
        zone = ZoneInfo("UTC")
        notes.append(f"Invalid tz '{tz_raw}', falling back to UTC.")

    now_local = datetime.now(timezone.utc).astimezone(zone)
    # Week starts Monday (00:00) in local timezone.
    start_local = (now_local.replace(hour=0, minute=0, second=0, microsecond=0) -
                   timedelta(days=now_local.weekday()))
    end_local = start_local + timedelta(days=7)

    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    start_ms = int(start_utc.timestamp() * 1000)
    end_ms = int(end_utc.timestamp() * 1000)

    # Completed tasks in this week (product only).
    tm = TaskManager()
    tasks = tm.list_tasks(limit=500)
    completed: List[Dict[str, Any]] = []
    for t in tasks:
        try:
            md = t.metadata or {}
            if not md.get("product"):
                continue
            if str(t.status) not in {"succeeded", "failed", "canceled"}:
                continue
            # updated_at stored as ISO-ish UTC string in most codepaths.
            updated = datetime.fromisoformat(str(t.updated_at).replace("Z", "+00:00"))
        except Exception:
            continue
        if updated < start_utc or updated >= end_utc:
            continue
        completed.append({"task_id": t.task_id, "status": t.status, "action_id": md.get("product_action_id")})

    tasks_completed = sum(1 for x in completed if x["status"] == "succeeded")

    # Token/cost from llm_usage_events if available.
    tokens_used: Optional[int] = None
    cost_amount: Optional[float] = None
    cost_conf = "none"
    tokens_conf = "none"
    try:
        conn = get_db()
        row = conn.execute(
            """
            SELECT
              SUM(COALESCE(total_tokens, COALESCE(prompt_tokens,0) + COALESCE(completion_tokens,0))) AS tokens,
              SUM(cost_usd) AS cost_usd
            FROM llm_usage_events
            WHERE created_at_ms >= ? AND created_at_ms < ?
            """,
            (start_ms, end_ms),
        ).fetchone()
        if row:
            if row["tokens"] is not None:
                tokens_used = int(row["tokens"])
                tokens_conf = "high"
            if row["cost_usd"] is not None:
                cost_amount = float(row["cost_usd"])
                cost_conf = "partial"
    except Exception:
        notes.append("LLM usage events not available; tokens/cost unavailable.")

    # Conservative time saved: only count fixed baselines for stable hero actions.
    baseline_minutes = {"analyze_repo": 15}
    time_saved = 0
    for x in completed:
        if x["status"] != "succeeded":
            continue
        time_saved += int(baseline_minutes.get(str(x.get("action_id") or ""), 0))
    time_conf = "low" if time_saved else "none"
    if time_saved:
        notes.append("Time saved is an estimate based on conservative per-action baselines.")

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "week_start": start_local.date().isoformat(),
            "week_end": (end_local.date() - timedelta(days=1)).isoformat(),
            "tz": tz_raw,
            "tasks_completed": tasks_completed,
            "tokens_used": tokens_used,
            "tokens_used_confidence": tokens_conf,
            "cost_estimated": {"currency": "USD", "amount": cost_amount, "confidence": cost_conf},
            "time_saved_minutes": {"amount": time_saved if time_saved else None, "confidence": time_conf, "basis": "action_baseline"},
            "notes": notes,
        },
    )
