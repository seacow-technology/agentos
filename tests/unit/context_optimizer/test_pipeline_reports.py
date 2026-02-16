from __future__ import annotations

import json
from pathlib import Path

from octopusos.core.context_optimizer.pipeline import generate_all_reports


def test_generate_all_reports_writes_artifacts(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    aggregate = generate_all_reports(repo_root=repo_root, model="gpt-4o", output_dir=tmp_path)
    assert "weighted_average_percent" in aggregate

    for name in ["cli_report.json", "ui_report.json", "tool_report.json", "aggregate_report.json"]:
        p = tmp_path / name
        assert p.exists()
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data

