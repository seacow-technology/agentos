from __future__ import annotations

import os
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from octopusos.channels.teams.graph_client import TeamsGraphClient
from octopusos.channels.teams.models import TeamsOrganizationConnection
from octopusos.channels.teams.provisioning.evidence import write_deploy_evidence
from octopusos.channels.teams.provisioning.governance import cleanup_duplicates, scan_duplicate_identities
from octopusos.channels.teams.provisioning.packager import build_teams_app_package
from octopusos.channels.teams.provisioning.verifier import wait_for_trace_chain
from octopusos.channels.teams.store import TeamsConnectionStore


@dataclass
class ProvisionResult:
    ok: bool
    tenant_id: str
    status: str
    teams_app_id: str = ""
    evidence_path: str = ""
    message: str = ""
    details: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "tenant_id": self.tenant_id,
            "status": self.status,
            "teams_app_id": self.teams_app_id,
            "evidence_path": self.evidence_path,
            "message": self.message,
            "details": self.details or {},
        }


class TeamsProvisionOrchestrator:
    def __init__(self, store: Optional[TeamsConnectionStore] = None):
        self.store = store or TeamsConnectionStore()

    @staticmethod
    def _step(steps: List[Dict[str, Any]], step: str, status: str, message: str, **extra: Any) -> None:
        row = {"step": step, "status": status, "message": message}
        if extra:
            row.update(extra)
        steps.append(row)

    def reconcile_teams_connection(self, tenant_id: str) -> ProvisionResult:
        tenant_id = str(tenant_id or "").strip()
        if not tenant_id:
            raise ValueError("tenant_id_required")

        conn_obj = self.store.get_connection(tenant_id)
        if not conn_obj:
            raise ValueError("tenant_not_connected")
        if not conn_obj.token_ref:
            raise ValueError("tenant_missing_token_ref")

        steps: List[Dict[str, Any]] = []
        result_details: Dict[str, Any] = {}
        lock_owner = f"reconcile-{uuid.uuid4()}"
        if not self.store.acquire_reconcile_lock(tenant_id, owner=lock_owner, ttl_ms=120_000):
            return ProvisionResult(
                ok=False,
                tenant_id=tenant_id,
                status=(conn_obj.status if conn_obj else "Blocked"),
                teams_app_id=(conn_obj.teams_app_id if conn_obj else ""),
                evidence_path=(conn_obj.last_evidence_path if conn_obj else ""),
                message="reconcile_already_running",
                details={"reason": "lock_not_acquired"},
            )

        try:
            graph = TeamsGraphClient(tenant_id=tenant_id, token_ref=conn_obj.token_ref)

            org = graph.get_organization()
            display_name = str(org.get("displayName") or conn_obj.display_name or tenant_id)
            conn_obj.display_name = display_name
            conn_obj.status = "Authorized"
            conn_obj = self.store.upsert_connection(conn_obj)
            self._step(steps, "organization", "PASS", f"resolved organization {display_name}")

            global_bot_id = str(os.getenv("OCTOPUSOS_TEAMS_GLOBAL_BOT_ID", conn_obj.bot_id or "")).strip()
            if not global_bot_id:
                raise ValueError("missing_global_bot_id:OCTOPUSOS_TEAMS_GLOBAL_BOT_ID")

            governance = scan_duplicate_identities(graph=graph, bot_id=global_bot_id, name_prefix="OctopusOS")
            result_details["governance_scan"] = {
                "matches": len(governance.get("all_matches") or []),
                "duplicates": len(governance.get("duplicates") or []),
            }
            if governance.get("has_conflict"):
                safe_mode = str(os.getenv("OCTOPUSOS_TEAMS_GOVERNANCE_SAFE_MODE", "false")).strip().lower() in {"1", "true", "yes", "on"}
                cleanup = cleanup_duplicates(
                    graph=graph,
                    duplicate_apps=governance.get("duplicates") or [],
                    safe_mode=safe_mode,
                )
                result_details["governance_cleanup"] = cleanup
                if cleanup.get("ok"):
                    self._step(steps, "governance", "PASS", "duplicate identities handled", safe_mode=safe_mode)
                else:
                    self._step(steps, "governance", "FAIL", "duplicate cleanup failed")
                    conn_obj.status = "Blocked"
                    conn_obj = self.store.upsert_connection(conn_obj)
                    evidence = write_deploy_evidence(
                        tenant_id=tenant_id,
                        result={"ok": False, "error": "governance_cleanup_failed", "details": result_details},
                        steps=steps,
                    )
                    conn_obj.last_evidence_path = evidence["dir"]
                    self.store.upsert_connection(conn_obj)
                    return ProvisionResult(
                        ok=False,
                        tenant_id=tenant_id,
                        status="Blocked",
                        teams_app_id=conn_obj.teams_app_id,
                        evidence_path=evidence["dir"],
                        message="governance cleanup failed",
                        details=result_details,
                    )
            else:
                self._step(steps, "governance", "PASS", "no duplicate identities detected")

            module_root = Path(__file__).resolve().parents[1]
            template_path = module_root / "templates" / "manifest.template.json"
            color_icon = module_root / "templates" / "icons" / "color.png"
            outline_icon = module_root / "templates" / "icons" / "outline.png"

            app_id = str(os.getenv("OCTOPUSOS_TEAMS_APP_ID", "")).strip()
            if not app_id:
                raise ValueError("missing_env:OCTOPUSOS_TEAMS_APP_ID")
            app_name = str(os.getenv("OCTOPUSOS_TEAMS_APP_NAME", "OctopusOS Bot")).strip()
            app_short = str(os.getenv("OCTOPUSOS_TEAMS_APP_SHORT_NAME", "OctopusOS")).strip()
            app_desc = str(os.getenv("OCTOPUSOS_TEAMS_APP_DESC", "OctopusOS bot for Teams personal chat and shared contexts.")).strip()
            app_version = str(os.getenv("OCTOPUSOS_TEAMS_APP_VERSION", "1.0.0")).strip()
            valid_domain = str(os.getenv("OCTOPUSOS_TEAMS_VALID_DOMAIN", "teams.octopusos.dev")).strip()
            bot_id = global_bot_id

            package = build_teams_app_package(
                template_path=str(template_path),
                output_dir="reports/teams_deploy/packages",
                values={
                    "APP_ID": app_id,
                    "APP_SHORT_NAME": app_short,
                    "APP_NAME": app_name,
                    "APP_DESC": app_desc,
                    "VERSION": app_version,
                    "BOT_ID": bot_id,
                    "VALID_DOMAIN": valid_domain,
                },
                color_icon_path=str(color_icon),
                outline_icon_path=str(outline_icon),
            )
            self._step(steps, "package", "PASS", f"package built: {package['zip_path']}")

            uploaded = graph.upload_app_package(package["zip_path"])
            manifest_app_id = app_id
            teams_app_id = str(uploaded.get("teamsAppId") or uploaded.get("id") or "").strip()
            if manifest_app_id:
                resolved_catalog_id = graph.find_catalog_app_id_by_external_id(manifest_app_id)
                if resolved_catalog_id:
                    teams_app_id = resolved_catalog_id
            if not teams_app_id:
                raise ValueError("upload_missing_catalog_app_id")
            conn_obj.teams_app_id = teams_app_id
            conn_obj.bot_id = bot_id
            conn_obj.status = "AppUploaded"
            conn_obj = self.store.upsert_connection(conn_obj)
            self._step(steps, "upload", "PASS", f"uploaded app: {teams_app_id}")

            me = graph.get_me()
            user_id = str(me.get("id") or "").strip()
            if not user_id:
                raise ValueError("cannot_resolve_admin_user_id")
            graph.install_app_for_user(
                user_id=user_id,
                teams_app_catalog_id=teams_app_id,
                external_app_id=manifest_app_id,
            )
            conn_obj.status = "Installed"
            conn_obj = self.store.upsert_connection(conn_obj)
            self._step(steps, "install", "PASS", f"installed for user: {user_id}")

            log_path = str(os.getenv("OCTOPUSOS_TEAMS_VERIFY_LOG_PATH", "")).strip()
            verify_timeout = int(str(os.getenv("OCTOPUSOS_TEAMS_VERIFY_TIMEOUT_SEC", "30")).strip() or "30")
            verification = (
                wait_for_trace_chain(log_path, timeout_sec=verify_timeout, poll_interval_sec=1.0)
                if log_path
                else {"ok": False, "error": "verify_log_path_not_configured", "checks": {}, "timed_out": False, "waited_sec": 0}
            )
            result_details["verification"] = verification
            if bool(verification.get("ok")):
                conn_obj.status = "Verified"
                self._step(steps, "verify", "PASS", "trace chain verified")
            else:
                conn_obj.status = "InstalledButUnverified"
                self._step(
                    steps,
                    "verify",
                    "FAIL",
                    str(verification.get("error") or "trace chain not complete"),
                    timeout_sec=verify_timeout,
                    timed_out=bool(verification.get("timed_out")),
                )
            conn_obj = self.store.upsert_connection(conn_obj)

            final_ok = conn_obj.status == "Verified"
            evidence = write_deploy_evidence(
                tenant_id=tenant_id,
                result={
                    "ok": final_ok,
                    "status": conn_obj.status,
                    "teams_app_id": conn_obj.teams_app_id,
                    "details": result_details,
                },
                steps=steps,
            )
            conn_obj.last_evidence_path = evidence["dir"]
            conn_obj = self.store.upsert_connection(conn_obj)

            return ProvisionResult(
                ok=final_ok,
                tenant_id=tenant_id,
                status=conn_obj.status,
                teams_app_id=conn_obj.teams_app_id,
                evidence_path=evidence["dir"],
                message="reconcile completed",
                details=result_details,
            )

        except Exception as exc:
            self._step(steps, "error", "FAIL", str(exc))
            result_details["traceback"] = traceback.format_exc(limit=8)
            evidence = write_deploy_evidence(
                tenant_id=tenant_id,
                result={"ok": False, "status": "Blocked", "error": str(exc), "details": result_details},
                steps=steps,
            )
            self.store.update_status(
                tenant_id,
                status="Blocked",
                last_evidence_path=evidence["dir"],
            )
            return ProvisionResult(
                ok=False,
                tenant_id=tenant_id,
                status="Blocked",
                teams_app_id=(conn_obj.teams_app_id if conn_obj else ""),
                evidence_path=evidence["dir"],
                message=str(exc),
                details=result_details,
            )
        finally:
            self.store.release_reconcile_lock(tenant_id, owner=lock_owner)
