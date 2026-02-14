from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from octopusos.channels.teams.graph_client import TeamsGraphClient


def _semver_tuple(v: str) -> tuple[int, int, int]:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", str(v or "0.0.0").strip())
    if not m:
        return (0, 0, 0)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _extract_bot_ids(app_obj: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    defs = app_obj.get("appDefinitions")
    if not isinstance(defs, list):
        return out
    for d in defs:
        if not isinstance(d, dict):
            continue
        bots = d.get("bots")
        if not isinstance(bots, list):
            continue
        for b in bots:
            if isinstance(b, dict):
                bid = str(b.get("botId") or "").strip()
                if bid:
                    out.append(bid)
    return list(dict.fromkeys(out))


def scan_duplicate_identities(*, graph: TeamsGraphClient, bot_id: str, name_prefix: str = "OctopusOS") -> Dict[str, Any]:
    apps = graph.list_catalog_apps()
    matches: List[Dict[str, Any]] = []
    for app in apps:
        if not isinstance(app, dict):
            continue
        display_name = str(app.get("displayName") or "")
        bot_ids = _extract_bot_ids(app)
        if bot_id and bot_id in bot_ids:
            matches.append(app)
            continue
        if name_prefix and display_name.lower().startswith(name_prefix.lower()):
            matches.append(app)

    keep: Dict[str, Any] | None = None
    keep_ver = (0, 0, 0)
    for app in matches:
        defs = app.get("appDefinitions") if isinstance(app.get("appDefinitions"), list) else []
        latest = (0, 0, 0)
        for d in defs:
            if isinstance(d, dict):
                latest = max(latest, _semver_tuple(str(d.get("version") or "0.0.0")))
        if latest >= keep_ver:
            keep_ver = latest
            keep = app

    duplicates = [a for a in matches if keep and str(a.get("id")) != str(keep.get("id"))]
    return {
        "all_matches": matches,
        "keep": keep,
        "duplicates": duplicates,
        "has_conflict": len(matches) > 1,
    }


def cleanup_duplicates(*, graph: TeamsGraphClient, duplicate_apps: List[Dict[str, Any]], safe_mode: bool = False) -> Dict[str, Any]:
    actions: List[Dict[str, Any]] = []
    for app in duplicate_apps:
        app_id = str(app.get("id") or "").strip()
        if not app_id:
            continue
        if safe_mode:
            actions.append({"app_id": app_id, "action": "warn_only", "ok": True})
            continue
        ok = graph.uninstall_catalog_app(app_id)
        actions.append({"app_id": app_id, "action": "delete", "ok": bool(ok)})
    return {
        "ok": all(bool(a.get("ok")) for a in actions) if actions else True,
        "actions": actions,
    }
