from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from octopusos.webui.api.docs_wiki import docs_wiki_entry, docs_wiki_index


# Backward-compatible Teams-only Wiki endpoints.
# Internally, Teams is a topic in the generic docs wiki system.
router = APIRouter(tags=["teams-wiki"])


@router.get("/api/teams-wiki/index")
def teams_wiki_index(lang: str = Query("en", min_length=2, max_length=8)) -> JSONResponse:
    return docs_wiki_index(lang=lang, topic="teams")


@router.get("/api/teams-wiki/entry")
def teams_wiki_entry(
    key: str = Query(..., min_length=1, max_length=128),
    lang: str = Query("en", min_length=2, max_length=8),
) -> PlainTextResponse:
    return docs_wiki_entry(key=key, lang=lang, topic="teams")
