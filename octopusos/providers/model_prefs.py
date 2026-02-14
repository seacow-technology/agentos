"""Provider model preferences (e.g. "used" flags) persisted on disk.

This is intentionally NOT stored in secrets, because it is not sensitive.
Default location: ~/.octopusos/config/model_prefs.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Set


class ProviderModelPrefsManager:
    def __init__(self, prefs_file: Path | None = None):
        if prefs_file is None:
            home = Path.home()
            cfg_dir = home / ".octopusos" / "config"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            prefs_file = cfg_dir / "model_prefs.json"
        self.prefs_file = prefs_file
        self._data = self._load()

    def _load(self) -> Dict[str, Dict[str, List[str]]]:
        if not self.prefs_file.exists():
            return {"providers": {}}
        try:
            with open(self.prefs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"providers": {}}
            if "providers" not in data or not isinstance(data.get("providers"), dict):
                data["providers"] = {}
            return data
        except Exception:
            return {"providers": {}}

    def _save(self) -> None:
        self.prefs_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.prefs_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        tmp.replace(self.prefs_file)

    def get_used_models(self, provider_id: str) -> Set[str]:
        providers = self._data.get("providers", {})
        entry = providers.get(provider_id) or {}
        used = entry.get("used_models") or []
        if not isinstance(used, list):
            return set()
        return {str(x) for x in used if x}

    def set_model_used(self, provider_id: str, model_id: str, used: bool) -> Set[str]:
        providers = self._data.setdefault("providers", {})
        entry = providers.setdefault(provider_id, {})
        used_set = self.get_used_models(provider_id)
        if used:
            used_set.add(str(model_id))
        else:
            used_set.discard(str(model_id))
        entry["used_models"] = sorted(used_set)
        self._save()
        return used_set

