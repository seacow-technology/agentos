from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse


router = APIRouter(tags=["docs-wiki"])
SUPPORTED_LANGS = {"en", "zh"}


def _repo_root() -> Path:
    # os/octopusos/webui/api/docs_wiki.py -> api -> webui -> octopusos -> os -> repo_root
    here = Path(__file__).resolve()
    return here.parents[4]


def _wiki_dir() -> Path:
    return _repo_root() / "docs" / "wiki"


def _lang_dir(lang: str) -> Path:
    return _wiki_dir() / "lang" / lang


def _index_path_for_lang(lang: str) -> Path:
    return _lang_dir(lang) / "index.json"


def _load_index(lang: str) -> dict:
    p = _index_path_for_lang(lang)
    if not p.exists():
        return {"ok": True, "topics": [], "sections": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="DOCS_WIKI_INDEX_INVALID_JSON")
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="DOCS_WIKI_INDEX_INVALID")

    topics = data.get("topics") or []
    sections = data.get("sections") or []
    if not isinstance(topics, list) or not isinstance(sections, list):
        raise HTTPException(status_code=500, detail="DOCS_WIKI_INDEX_INVALID_SHAPE")
    return {"ok": True, "topics": topics, "sections": sections}


def _filter_index(*, idx: Dict[str, Any], topic: str) -> Dict[str, Any]:
    topic = str(topic or "").strip()
    if not topic:
        return idx
    sections: List[Dict[str, Any]] = []
    for row in idx.get("sections") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("topic") or "").strip() != topic:
            continue
        sections.append(row)
    topics: List[Dict[str, Any]] = []
    for t in idx.get("topics") or []:
        if not isinstance(t, dict):
            continue
        if str(t.get("key") or "").strip() != topic:
            continue
        topics.append(t)
    return {"ok": True, "topics": topics, "sections": sections}


def _entry_path_for_key(*, key: str, lang: str, topic: str = "") -> Optional[Path]:
    idx = _filter_index(idx=_load_index(lang), topic=topic)
    for row in idx.get("sections") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("key") or "") != key:
            continue
        md_path = str(row.get("md_path") or "").strip()
        if not md_path:
            return None
        p = (_repo_root() / md_path).resolve()
        base = _lang_dir(lang).resolve()
        try:
            p.relative_to(base)
        except Exception:
            return None
        if p.suffix.lower() != ".md":
            return None
        return p
    return None


@router.get("/api/docs-wiki/index")
def docs_wiki_index(
    lang: str = Query("en", min_length=2, max_length=8),
    topic: str = Query("", min_length=0, max_length=64),
) -> JSONResponse:
    if lang not in SUPPORTED_LANGS:
        raise HTTPException(status_code=400, detail="DOCS_WIKI_LANG_UNSUPPORTED")
    idx = _load_index(lang)
    return JSONResponse(status_code=200, content=_filter_index(idx=idx, topic=topic))


@router.get("/api/docs-wiki/entry")
def docs_wiki_entry(
    key: str = Query(..., min_length=1, max_length=128),
    lang: str = Query("en", min_length=2, max_length=8),
    topic: str = Query("", min_length=0, max_length=64),
) -> PlainTextResponse:
    if lang not in SUPPORTED_LANGS:
        raise HTTPException(status_code=400, detail="DOCS_WIKI_LANG_UNSUPPORTED")
    p = _entry_path_for_key(key=key, lang=lang, topic=topic)
    if p is None:
        raise HTTPException(status_code=404, detail="DOCS_WIKI_ENTRY_NOT_FOUND")
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="DOCS_WIKI_ENTRY_MISSING")
    return PlainTextResponse(status_code=200, content=p.read_text(encoding="utf-8"), media_type="text/markdown")

