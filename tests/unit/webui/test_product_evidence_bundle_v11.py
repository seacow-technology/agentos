import json
import hashlib
import zipfile
from pathlib import Path

from octopusos.webui.api.product import analyze_repo, build_evidence_bundle


def _sha256(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def test_evidence_bundle_v11_has_stable_structure(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# demo\n", encoding="utf-8")
    (repo / "main.py").write_text("print('hi')  # TODO: refactor\n", encoding="utf-8")

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    report, timeline = analyze_repo(repo, out_dir=out_dir, ui_task_ref="p_test")
    artifacts = out_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    # New layout (preferred)
    (artifacts / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (artifacts / "timeline.json").write_text(json.dumps(timeline, indent=2), encoding="utf-8")

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

    bundle = build_evidence_bundle(out_dir, manifest=manifest)
    assert bundle.exists()

    with zipfile.ZipFile(bundle, "r") as z:
        names = set(z.namelist())
        assert "manifest.json" in names
        assert "checksums.json" in names
        assert "artifacts/report.json" in names
        assert "artifacts/timeline.json" in names
        assert "artifacts/diff.patch" not in names  # read-only action must not emit diffs

        m = json.loads(z.read("manifest.json").decode("utf-8"))
        assert m.get("bundle_version") == "1.1"
        assert m.get("action_id") == "analyze_repo"

        c = json.loads(z.read("checksums.json").decode("utf-8"))
        assert c.get("algorithm") == "sha256"
        files = c.get("files") or {}
        # checksums.json must not checksum itself
        assert "checksums.json" not in files
        for p in ("manifest.json", "artifacts/report.json", "artifacts/timeline.json"):
            assert p in files
            assert files[p] == _sha256(z.read(p))
