import json
from pathlib import Path

from octopusos.webui.api.product import analyze_repo, build_evidence_bundle, build_replay_payload, build_share_text


def test_product_replay_payload_has_three_sections(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("# TODO: x\n", encoding="utf-8")

    out_dir = tmp_path / "out"
    (out_dir / "artifacts").mkdir(parents=True, exist_ok=True)

    report, timeline = analyze_repo(repo, out_dir=out_dir, ui_task_ref="p_test")
    (out_dir / "artifacts" / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "artifacts" / "timeline.json").write_text(json.dumps(timeline, indent=2), encoding="utf-8")

    manifest = {
        "bundle_version": "1.1",
        "generated_at": "2026-02-15T00:00:00Z",
        "task_ref": "p_test",
        "task_id": "internal_optional",
        "action_id": "analyze_repo",
        "run_mode": "assisted",
        "policy": {"applied": True, "policy_id": "product_read_only_v1"},
        "inputs": {"repo_path": str(repo), "read_only": True, "audit_depth": report.get("audit_depth")},
        "outputs": {
            "report": {"path": "artifacts/report.json", "schema_version": report.get("schema_version")},
            "timeline": {"path": "artifacts/timeline.json", "schema_version": timeline.get("schema_version")},
            "diff": None,
        },
        "notes": ["missing_deep_checks: " + ", ".join(report.get("missing_deep_checks") or [])],
    }
    build_evidence_bundle(out_dir, manifest=manifest)

    rp = build_replay_payload(
        task_ref="p_test",
        task_id="t_internal",
        action_id="analyze_repo",
        out_dir=out_dir,
        tz="UTC",
        download_base="/api/product/tasks/p_test/evidence/download",
    )

    assert rp.get("replay_version") == 1
    assert rp.get("summary", {}).get("headline")
    assert rp.get("summary", {}).get("metrics_line")
    assert isinstance(rp.get("timeline"), list)
    assert isinstance(rp.get("evidence", {}).get("files"), list)
    assert len(rp.get("evidence", {}).get("files")) >= 4
    assert rp.get("evidence", {}).get("bundle", {}).get("download_url")

    # Share text must be stable and identical wherever it is exposed (Replay + Evidence).
    share = build_share_text(
        task_ref="p_test",
        task_id="t_internal",
        action_id="analyze_repo",
        out_dir=out_dir,
        tz="UTC",
        download_base="/api/product/tasks/p_test/evidence/download",
    )
    assert share == rp.get("copy_text")
