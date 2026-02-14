from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict


def _read_template(template_path: Path) -> str:
    return template_path.read_text(encoding="utf-8")


def render_manifest(template_path: str, values: Dict[str, Any]) -> Dict[str, Any]:
    content = _read_template(Path(template_path))
    for key, value in values.items():
        content = content.replace(f"__{key}__", str(value))
    obj = json.loads(content)
    if not isinstance(obj, dict):
        raise ValueError("manifest_template_not_object")
    return obj


def build_teams_app_package(
    *,
    template_path: str,
    output_dir: str,
    values: Dict[str, Any],
    color_icon_path: str,
    outline_icon_path: str,
) -> Dict[str, Any]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_obj = render_manifest(template_path, values)

    app_id = str(manifest_obj.get("id") or values.get("APP_ID") or "teams-app")
    version = str(manifest_obj.get("version") or values.get("VERSION") or "1.0.0")
    zip_name = f"teams-app-{app_id}-{version}.zip".replace("/", "_")
    zip_path = out_dir / zip_name

    with tempfile.TemporaryDirectory(prefix="teams_app_pkg_") as tmp:
        tmp_dir = Path(tmp)
        (tmp_dir / "manifest.json").write_text(json.dumps(manifest_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        shutil.copyfile(color_icon_path, tmp_dir / "color.png")
        shutil.copyfile(outline_icon_path, tmp_dir / "outline.png")

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp_dir / "manifest.json", arcname="manifest.json")
            zf.write(tmp_dir / "color.png", arcname="color.png")
            zf.write(tmp_dir / "outline.png", arcname="outline.png")

    return {
        "zip_path": str(zip_path),
        "manifest": manifest_obj,
    }
