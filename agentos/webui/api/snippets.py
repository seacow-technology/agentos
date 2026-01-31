"""
Snippets API - Code snippets asset library

POST /api/snippets - Create snippet
GET /api/snippets - Search/list snippets
GET /api/snippets/{id} - Get snippet details
PATCH /api/snippets/{id} - Update snippet
DELETE /api/snippets/{id} - Delete snippet
POST /api/snippets/{id}/explain - Generate explanation prompt
"""

from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import json

from agentos.store import get_db
from agentos.core.time import utc_now
from agentos.core.audit import (
    log_audit_event,
    SNIPPET_USED_IN_PREVIEW,
    TASK_MATERIALIZED_FROM_SNIPPET,
)

router = APIRouter()


# Pydantic models

class SnippetSource(BaseModel):
    """Source information for snippet"""
    type: str  # chat | task | manual
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    model: Optional[str] = None


class CreateSnippetRequest(BaseModel):
    """Create snippet request"""
    title: Optional[str] = None
    language: str
    code: str
    tags: List[str] = []
    source: Optional[SnippetSource] = None
    summary: Optional[str] = None
    usage: Optional[str] = None


class UpdateSnippetRequest(BaseModel):
    """Update snippet request"""
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    summary: Optional[str] = None
    usage: Optional[str] = None


class SnippetDetail(BaseModel):
    """Snippet detail model"""
    id: str
    title: Optional[str]
    language: str
    code: str
    tags: List[str]
    source_type: Optional[str]
    source_session_id: Optional[str]
    source_message_id: Optional[str]
    source_model: Optional[str]
    created_at: int
    updated_at: int
    summary: Optional[str] = None
    usage: Optional[str] = None


class SnippetSummary(BaseModel):
    """Snippet summary for list view"""
    id: str
    title: Optional[str]
    language: str
    tags: List[str]
    created_at: int
    code_preview: str  # First 100 chars


class SnippetListResponse(BaseModel):
    """Response for list snippets"""
    snippets: List[SnippetSummary]


class ExplainPromptResponse(BaseModel):
    """Explain prompt response"""
    prompt: str


class CreatePreviewRequest(BaseModel):
    """Create preview from snippet"""
    preset: str = "html-basic"


class MaterializeRequest(BaseModel):
    """Materialize snippet to task"""
    target_path: str
    description: Optional[str] = None


# API endpoints

@router.post("")
async def create_snippet(req: CreateSnippetRequest) -> SnippetDetail:
    """
    Create a new code snippet

    Args:
        req: Create snippet request

    Returns:
        Created snippet details
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        snippet_id = str(uuid.uuid4())
        now = int(utc_now().timestamp())

        # Generate default title if not provided
        title = req.title or f"{req.language} snippet {datetime.now().strftime('%Y-%m-%d')}"

        # Serialize tags to JSON
        tags_json = json.dumps(req.tags)

        # Extract source info
        source_type = req.source.type if req.source else "manual"
        source_session_id = req.source.session_id if req.source else None
        source_message_id = req.source.message_id if req.source else None
        source_model = req.source.model if req.source else None

        # Insert snippet
        cursor.execute(
            """
            INSERT INTO snippets (
                id, title, language, code, tags_json,
                source_type, source_session_id, source_message_id, source_model,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snippet_id, title, req.language, req.code, tags_json,
                source_type, source_session_id, source_message_id, source_model,
                now, now
            )
        )

        # Insert notes if provided
        if req.summary or req.usage:
            cursor.execute(
                """
                INSERT INTO snippet_notes (snippet_id, summary, usage)
                VALUES (?, ?, ?)
                """,
                (snippet_id, req.summary, req.usage)
            )

        conn.commit()

        # Fetch and return created snippet
        return await get_snippet(snippet_id)

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create snippet: {str(e)}")
        # Do NOT close: get_db() returns shared thread-local connection


@router.get("")
async def list_snippets(
    query: Optional[str] = Query(None, description="Search query (FTS5)"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    language: Optional[str] = Query(None, description="Filter by language"),
    limit: int = Query(50, ge=1, le=10000, description="Max results"),
) -> SnippetListResponse:
    """
    Search and list snippets

    Args:
        query: Full-text search query (searches title, code, tags, summary)
        tag: Filter by tag
        language: Filter by language
        limit: Maximum number of results

    Returns:
        List of snippet summaries
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        if query:
            # Use FTS5 for full-text search
            fts_query = query.replace('"', '""')  # Escape quotes for FTS5

            sql = """
                SELECT s.id, s.title, s.language, s.code, s.tags_json, s.created_at
                FROM snippets s
                JOIN snippets_fts fts ON s.id = fts.snippet_id
                WHERE snippets_fts MATCH ?
            """
            params = [fts_query]

            # Add filters
            if tag:
                sql += " AND s.tags_json LIKE ?"
                params.append(f'%"{tag}"%')
            if language:
                sql += " AND s.language = ?"
                params.append(language)

            sql += " ORDER BY s.created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(sql, params)

        else:
            # Regular query without FTS
            sql = "SELECT id, title, language, code, tags_json, created_at FROM snippets WHERE 1=1"
            params = []

            if tag:
                sql += " AND tags_json LIKE ?"
                params.append(f'%"{tag}"%')
            if language:
                sql += " AND language = ?"
                params.append(language)

            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(sql, params)

        rows = cursor.fetchall()

        # Convert to summaries
        summaries = []
        for row in rows:
            tags = json.loads(row["tags_json"]) if row["tags_json"] else []
            code_preview = row["code"][:100] if len(row["code"]) > 100 else row["code"]

            summaries.append(
                SnippetSummary(
                    id=row["id"],
                    title=row["title"],
                    language=row["language"],
                    tags=tags,
                    created_at=row["created_at"],
                    code_preview=code_preview,
                )
            )

        return SnippetListResponse(snippets=summaries)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search snippets: {str(e)}")
        # Do NOT close: get_db() returns shared thread-local connection


@router.get("/{snippet_id}")
async def get_snippet(snippet_id: str) -> SnippetDetail:
    """
    Get snippet details by ID

    Args:
        snippet_id: Snippet ID

    Returns:
        Snippet details
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Fetch snippet
        cursor.execute(
            """
            SELECT s.*, n.summary, n.usage
            FROM snippets s
            LEFT JOIN snippet_notes n ON s.id = n.snippet_id
            WHERE s.id = ?
            """,
            (snippet_id,)
        )

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Snippet not found")

        tags = json.loads(row["tags_json"]) if row["tags_json"] else []

        return SnippetDetail(
            id=row["id"],
            title=row["title"],
            language=row["language"],
            code=row["code"],
            tags=tags,
            source_type=row["source_type"],
            source_session_id=row["source_session_id"],
            source_message_id=row["source_message_id"],
            source_model=row["source_model"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            summary=row["summary"],
            usage=row["usage"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get snippet: {str(e)}")
        # Do NOT close: get_db() returns shared thread-local connection


@router.patch("/{snippet_id}")
async def update_snippet(snippet_id: str, req: UpdateSnippetRequest) -> SnippetDetail:
    """
    Update snippet metadata

    Args:
        snippet_id: Snippet ID
        req: Update request

    Returns:
        Updated snippet details
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Check if snippet exists
        cursor.execute("SELECT id FROM snippets WHERE id = ?", (snippet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Snippet not found")

        now = int(utc_now().timestamp())

        # Update snippet fields
        updates = []
        params = []

        if req.title is not None:
            updates.append("title = ?")
            params.append(req.title)

        if req.tags is not None:
            updates.append("tags_json = ?")
            params.append(json.dumps(req.tags))

        if updates:
            updates.append("updated_at = ?")
            params.append(now)
            params.append(snippet_id)

            sql = f"UPDATE snippets SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, params)

        # Update notes
        if req.summary is not None or req.usage is not None:
            # Check if notes exist
            cursor.execute(
                "SELECT snippet_id FROM snippet_notes WHERE snippet_id = ?",
                (snippet_id,)
            )
            notes_exist = cursor.fetchone() is not None

            if notes_exist:
                # Update existing notes
                note_updates = []
                note_params = []

                if req.summary is not None:
                    note_updates.append("summary = ?")
                    note_params.append(req.summary)

                if req.usage is not None:
                    note_updates.append("usage = ?")
                    note_params.append(req.usage)

                if note_updates:
                    note_params.append(snippet_id)
                    sql = f"UPDATE snippet_notes SET {', '.join(note_updates)} WHERE snippet_id = ?"
                    cursor.execute(sql, note_params)
            else:
                # Insert new notes
                cursor.execute(
                    """
                    INSERT INTO snippet_notes (snippet_id, summary, usage)
                    VALUES (?, ?, ?)
                    """,
                    (snippet_id, req.summary, req.usage)
                )

        conn.commit()

        # Return updated snippet
        return await get_snippet(snippet_id)

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update snippet: {str(e)}")
        # Do NOT close: get_db() returns shared thread-local connection


@router.delete("/{snippet_id}")
async def delete_snippet(snippet_id: str) -> Dict[str, str]:
    """
    Delete snippet

    Args:
        snippet_id: Snippet ID

    Returns:
        Success message
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Check if snippet exists
        cursor.execute("SELECT id FROM snippets WHERE id = ?", (snippet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Snippet not found")

        # Delete snippet (CASCADE will handle notes and FTS via triggers)
        cursor.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))

        conn.commit()

        return {"message": "Snippet deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete snippet: {str(e)}")
        # Do NOT close: get_db() returns shared thread-local connection


@router.post("/{snippet_id}/explain")
async def explain_snippet(
    snippet_id: str,
    lang: Optional[str] = Query("zh", description="Language for prompt: zh or en")
) -> ExplainPromptResponse:
    """
    Generate explanation prompt for snippet

    This returns a prompt that can be sent to Chat, not the actual explanation.
    This follows AgentOS's design pattern of keeping Chat as the control center.

    Args:
        snippet_id: Snippet ID
        lang: Language for prompt (zh or en)

    Returns:
        Prompt to be sent to Chat
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Fetch snippet
        cursor.execute(
            "SELECT language, code, title FROM snippets WHERE id = ?",
            (snippet_id,)
        )

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Snippet not found")

        title = row["title"] or "this code"
        language = row["language"]
        code = row["code"]

        # Generate prompt based on language
        if lang == "en":
            prompt = f"""Please explain the following code line by line, and describe applicable scenarios and precautions:

**Title**: {title}

```{language}
{code}
```

Please provide:
1. Overall functionality description
2. Detailed line-by-line or block-by-block explanation
3. Applicable scenarios
4. Precautions when using
5. Possible improvement suggestions (if any)
"""
        else:  # zh (default)
            prompt = f"""请逐行解释以下代码，并说明适用场景与注意事项：

**标题**: {title}

```{language}
{code}
```

请提供：
1. 代码的整体功能说明
2. 逐行或逐块的详细解释
3. 适用场景
4. 使用时需要注意的事项
5. 可能的改进建议（如有）
"""

        return ExplainPromptResponse(prompt=prompt)
        # Do NOT close: get_db() returns shared thread-local connection

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to explain snippet: {str(e)}")


@router.post("/{snippet_id}/preview")
async def create_snippet_preview(snippet_id: str, req: CreatePreviewRequest, request: Request):
    """
    Create preview session from snippet

    Args:
        snippet_id: Snippet ID
        req: Preview request (contains preset)
        request: FastAPI request object

    Returns:
        preview_session_id, url, preset, deps_injected, expires_at

    Raises:
        404: Snippet not found
        500: Preview API call failed
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 1. Fetch snippet
        cursor.execute("SELECT code, language FROM snippets WHERE id = ?", (snippet_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Snippet not found")

        code = row["code"]
        language = row["language"]

        # 2. Construct HTML based on language
        if language == "html":
            # Use HTML directly
            html = code
        elif language == "javascript":
            # Wrap JavaScript in HTML
            html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Preview: {snippet_id}</title>
    <style>
        body {{ margin: 0; padding: 20px; font-family: sans-serif; }}
        canvas {{ display: block; }}
    </style>
</head>
<body>
    <script>
{code}
    </script>
</body>
</html>"""
        else:
            # Wrap other languages in code block
            html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Preview: {snippet_id}</title>
    <style>
        body {{ margin: 0; padding: 20px; font-family: monospace; }}
        pre {{ background: #f5f5f5; padding: 15px; border-radius: 5px; }}
    </style>
</head>
<body>
    <pre><code>{code}</code></pre>
</body>
</html>"""

        # 3. Call Preview API (internal function to avoid HTTP overhead)
        from agentos.webui.api.preview import create_preview_session_internal

        preview_data = create_preview_session_internal(
            html=html,
            preset=req.preset,
            snippet_id=snippet_id
        )

        # 4. Update snippet metadata (record last_preview timestamp)
        cursor.execute(
            """
            UPDATE snippets
            SET updated_at = ?
            WHERE id = ?
            """,
            (int(utc_now().timestamp()), snippet_id)
        )

        conn.commit()

        # 5. Record audit event
        log_audit_event(
            SNIPPET_USED_IN_PREVIEW,
            snippet_id=snippet_id,
            preview_id=preview_data["session_id"],
            metadata={
                "preset": req.preset,
                "language": language
            }
        )

        return {
            "snippet_id": snippet_id,
            "preview_session_id": preview_data["session_id"],
            "url": preview_data["url"],
            "preset": preview_data["preset"],
            "deps_injected": preview_data.get("deps_injected", []),
            "expires_at": preview_data.get("expires_at")
        }

    except HTTPException:
        raise
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Failed to create preview: {str(e)}")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create preview: {str(e)}")
        # Do NOT close: get_db() returns shared thread-local connection


@router.post("/{snippet_id}/materialize")
async def materialize_snippet(snippet_id: str, req: MaterializeRequest):
    """
    Create task draft from snippet

    P0.5 simplified version: Only generates task draft, does not execute file write.
    Returns task plan that can be viewed and executed in TasksView.

    Args:
        snippet_id: Snippet ID
        req: Materialize request with target_path and optional description

    Returns:
        task_draft containing plan, files, and actions

    Security:
        Requires admin token in production, skipped in development

    Raises:
        404: Snippet not found
        422: Invalid target path
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 1. Fetch snippet
        cursor.execute(
            """
            SELECT title, language, code, tags_json
            FROM snippets
            WHERE id = ?
            """,
            (snippet_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Snippet not found")

        title = row["title"]
        language = row["language"]
        code = row["code"]
        tags = json.loads(row["tags_json"]) if row["tags_json"] else []

        # 2. Validate target path
        if not req.target_path or req.target_path.startswith("/"):
            raise HTTPException(
                status_code=422,
                detail="target_path must be a relative path (e.g., examples/demo.html)"
            )

        # 3. Generate task draft (not creating actual task yet)
        task_draft = {
            "source": "snippet",
            "snippet_id": snippet_id,
            "title": f"Materialize: {title}",
            "description": req.description or f"Write snippet to {req.target_path}",
            "target_path": req.target_path,
            "language": language,
            "tags": tags,
            "plan": {
                "action": "write_file",
                "path": req.target_path,
                "content": code,
                "create_dirs": True
            },
            "files_affected": [req.target_path],
            "risk_level": "MEDIUM",  # File write is medium risk
            "requires_admin_token": True
        }

        # 4. Record audit event (ORPHAN task since no real task created yet)
        log_audit_event(
            TASK_MATERIALIZED_FROM_SNIPPET,
            snippet_id=snippet_id,
            metadata={
                "target_path": req.target_path,
                "language": language,
                "status": "draft"
            }
        )

        return {
            "task_draft": task_draft,
            "message": "Task draft created. Execute in TasksView to write file."
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to materialize snippet: {str(e)}")
        # Do NOT close: get_db() returns shared thread-local connection
