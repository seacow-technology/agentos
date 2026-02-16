import json
import zipfile
from pathlib import Path

from octopusos.webui.api.product import analyze_repo, build_evidence_bundle
from octopusos.webui.api import product as product_api


def _base_manifest(*, repo: Path) -> dict:
    return {
        "bundle_version": "1.1",
        "generated_at": "2026-02-15T00:00:00Z",
        "task_ref": "p_test",
        "task_id": "internal_optional",
        "action_id": "analyze_repo",
        "run_mode": "assisted",
        "policy": {"applied": True, "policy_id": "product_read_only_v1"},
        "inputs": {"repo_path": str(repo), "read_only": True, "audit_depth": "heuristic_v1"},
        "outputs": {
            "report": {"path": "artifacts/report.json", "schema_version": "product.analyze_repo.v1"},
            "timeline": {"path": "artifacts/timeline.json", "schema_version": "product.timeline.v1"},
            "diff": None,
        },
        "notes": ["missing_deep_checks: cve_lookup"],
    }


def test_p02_new_layout_written_and_zipped(tmp_path: Path, monkeypatch) -> None:
    # Force off: new-only writes (no legacy root mirror).
    monkeypatch.setenv("OCTOPUSOS_PRODUCT_LEGACY_WRITE_MODE", "off")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("# TODO: x\n", encoding="utf-8")

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    report, timeline = analyze_repo(repo, out_dir=out_dir, ui_task_ref="p_test")
    report_bytes = json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8")
    timeline_bytes = json.dumps(timeline, indent=2, ensure_ascii=False).encode("utf-8")
    product_api._write_artifact(out_dir, name="report.json", content=report_bytes)
    product_api._write_artifact(out_dir, name="timeline.json", content=timeline_bytes)

    # Red line: new layout exists on disk
    assert (out_dir / "artifacts" / "report.json").exists()
    assert (out_dir / "artifacts" / "timeline.json").exists()
    assert not (out_dir / "report.json").exists()
    assert not (out_dir / "timeline.json").exists()

    bundle = build_evidence_bundle(out_dir, manifest=_base_manifest(repo=repo))
    with zipfile.ZipFile(bundle, "r") as z:
        names = set(z.namelist())
        assert "artifacts/report.json" in names
        assert "artifacts/timeline.json" in names
        assert "report.json" not in names
        assert "timeline.json" not in names


def test_p02_legacy_layout_is_accepted(tmp_path: Path, monkeypatch) -> None:
    # Force legacy_only: legacy root writes only.
    monkeypatch.setenv("OCTOPUSOS_PRODUCT_LEGACY_WRITE_MODE", "legacy_only")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("# TODO: x\n", encoding="utf-8")

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    report, timeline = analyze_repo(repo, out_dir=out_dir, ui_task_ref="p_test")
    report_bytes = json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8")
    timeline_bytes = json.dumps(timeline, indent=2, ensure_ascii=False).encode("utf-8")
    product_api._write_artifact(out_dir, name="report.json", content=report_bytes)
    product_api._write_artifact(out_dir, name="timeline.json", content=timeline_bytes)
    assert (out_dir / "report.json").exists()
    assert (out_dir / "timeline.json").exists()
    assert not (out_dir / "artifacts" / "report.json").exists()
    assert not (out_dir / "artifacts" / "timeline.json").exists()

    bundle = build_evidence_bundle(out_dir, manifest=_base_manifest(repo=repo))
    with zipfile.ZipFile(bundle, "r") as z:
        names = set(z.namelist())
        assert "artifacts/report.json" in names
        assert "artifacts/timeline.json" in names
