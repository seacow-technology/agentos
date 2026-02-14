from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_deploy_evidence(
    *,
    tenant_id: str,
    result: Dict[str, Any],
    steps: List[Dict[str, Any]],
    base_reports_dir: str = "reports/teams_deploy",
) -> Dict[str, str]:
    stamp = _utc_stamp()
    out_dir = Path(base_reports_dir) / str(tenant_id) / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "deploy_report.json"
    md_path = out_dir / "deploy_report.md"

    payload = {
        "tenant_id": tenant_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "steps": steps,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# Teams Deploy Report - {tenant_id}",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Overall: {'PASS' if bool(result.get('ok')) else 'FAIL'}",
        "",
        "## Steps",
    ]
    for s in steps:
        lines.append(f"- [{s.get('status', 'UNKNOWN')}] {s.get('step', '')}: {s.get('message', '')}")

    lines.extend(
        [
            "",
            "## Result",
            "```json",
            json.dumps(result, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "dir": str(out_dir),
        "json": str(json_path),
        "md": str(md_path),
    }
