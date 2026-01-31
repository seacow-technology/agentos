"""
Preview API - Serve HTML content for iframe preview

Provides a real URL endpoint for iframe to load HTML content,
allowing external CDN resources to load properly.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agentos.core.time import utc_now
from agentos.core.audit import (
    log_audit_event,
    PREVIEW_SESSION_CREATED,
    PREVIEW_SESSION_OPENED,
    PREVIEW_SESSION_EXPIRED,
    PREVIEW_RUNTIME_SELECTED,
    PREVIEW_DEP_INJECTED,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@dataclass
class PreviewSession:
    """Preview session with metadata and TTL."""
    session_id: str
    html: str
    preset: str
    deps_injected: List[str]
    snippet_id: Optional[str]
    created_at: int
    expires_at: int


# In-memory storage for preview sessions
preview_sessions: Dict[str, PreviewSession] = {}


class PreviewRequest(BaseModel):
    """Request to create a preview session"""
    html: str
    preset: Optional[str] = "html-basic"
    snippet_id: Optional[str] = None


def detect_three_deps(code: str) -> List[str]:
    """
    Detect Three.js dependencies needed by the code.

    Args:
        code: HTML/JavaScript code to analyze

    Returns:
        List of dependency identifiers (e.g., ["three-core", "three-fontloader"])
    """
    deps = ["three-core"]  # Core is always needed

    # Detect loaders
    if re.search(r'\bFontLoader\b', code):
        deps.append("three-fontloader")
    if re.search(r'\bGLTFLoader\b', code):
        deps.append("three-gltf-loader")
    if re.search(r'\bOBJLoader\b', code):
        deps.append("three-obj-loader")

    # Detect geometries
    if re.search(r'\bTextGeometry\b', code):
        deps.append("three-text-geometry")

    # Detect controls
    if re.search(r'\bOrbitControls\b', code):
        deps.append("three-orbit-controls")
    if re.search(r'\bTransformControls\b', code):
        deps.append("three-transform-controls")

    # Detect postprocessing
    if re.search(r'\bEffectComposer\b', code):
        deps.append("three-effect-composer")
    if re.search(r'\bRenderPass\b', code):
        deps.append("three-render-pass")

    return deps


def inject_three_deps(html: str, deps: List[str]) -> str:
    """
    Inject Three.js dependencies into HTML.

    Args:
        html: Original HTML content
        deps: List of dependency identifiers to inject

    Returns:
        HTML with injected script tags
    """
    # Three.js v0.180.0 CDN URLs (using jsDelivr)
    dep_urls = {
        "three-core": "https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.min.js",
        "three-fontloader": "https://cdn.jsdelivr.net/npm/three@0.180.0/examples/js/loaders/FontLoader.js",
        "three-text-geometry": "https://cdn.jsdelivr.net/npm/three@0.180.0/examples/js/geometries/TextGeometry.js",
        "three-orbit-controls": "https://cdn.jsdelivr.net/npm/three@0.180.0/examples/js/controls/OrbitControls.js",
        "three-transform-controls": "https://cdn.jsdelivr.net/npm/three@0.180.0/examples/js/controls/TransformControls.js",
        "three-gltf-loader": "https://cdn.jsdelivr.net/npm/three@0.180.0/examples/js/loaders/GLTFLoader.js",
        "three-obj-loader": "https://cdn.jsdelivr.net/npm/three@0.180.0/examples/js/loaders/OBJLoader.js",
        "three-effect-composer": "https://cdn.jsdelivr.net/npm/three@0.180.0/examples/js/postprocessing/EffectComposer.js",
        "three-render-pass": "https://cdn.jsdelivr.net/npm/three@0.180.0/examples/js/postprocessing/RenderPass.js",
    }

    # Build script tags in dependency order
    scripts = []
    for dep in deps:
        if dep in dep_urls:
            scripts.append(f'    <script src="{dep_urls[dep]}"></script>')

    if not scripts:
        return html

    script_block = '\n'.join(scripts)

    # Find injection point
    # Priority: before </head>, before <body>, or at the beginning
    head_close = html.find('</head>')
    if head_close != -1:
        return html[:head_close] + script_block + '\n' + html[head_close:]

    body_open = html.find('<body>')
    if body_open != -1:
        return html[:body_open] + script_block + '\n' + html[body_open:]

    # No head or body tags, inject at the beginning
    return script_block + '\n' + html


def create_preview_session_internal(html: str, preset: str = "html-basic", snippet_id: Optional[str] = None) -> Dict:
    """
    Core logic to create a preview session (can be called internally).

    Args:
        html: HTML content
        preset: Preset name ("html-basic" or "three-webgl-umd")
        snippet_id: Optional snippet ID

    Returns:
        Dictionary with session_id, url, preset, deps_injected, expires_at
    """
    import uuid

    session_id = str(uuid.uuid4())
    deps_injected = []

    # Apply preset processing
    if preset == "three-webgl-umd":
        # Detect and inject Three.js dependencies
        deps = detect_three_deps(html)
        html = inject_three_deps(html, deps)
        deps_injected = deps

        # Log audit events
        log_audit_event(
            PREVIEW_RUNTIME_SELECTED,
            preview_id=session_id,
            snippet_id=snippet_id,
            metadata={"preset": "three-webgl-umd"}
        )
        log_audit_event(
            PREVIEW_DEP_INJECTED,
            preview_id=session_id,
            snippet_id=snippet_id,
            metadata={"deps": deps}
        )

    # Create session with TTL (1 hour)
    now = int(utc_now().timestamp())
    session = PreviewSession(
        session_id=session_id,
        html=html,
        preset=preset,
        deps_injected=deps_injected,
        snippet_id=snippet_id,
        created_at=now,
        expires_at=now + 3600  # 1 hour TTL
    )
    preview_sessions[session_id] = session

    # Log creation event
    log_audit_event(
        PREVIEW_SESSION_CREATED,
        preview_id=session_id,
        snippet_id=snippet_id,
        metadata={
            "preset": preset,
            "deps_count": len(deps_injected)
        }
    )

    logger.info(f"Created preview session: {session_id} (preset: {preset}, deps: {deps_injected})")

    return {
        "session_id": session_id,
        "url": f"/api/preview/{session_id}",
        "preset": preset,
        "deps_injected": deps_injected,
        "expires_at": session.expires_at
    }


@router.post("/preview")
async def create_preview_session(request: PreviewRequest):
    """
    Create a temporary preview session and return session ID.

    Supports presets:
    - html-basic: Plain HTML (no processing)
    - three-webgl-umd: Three.js with automatic dependency detection and injection

    Args:
        request: Preview request with HTML and optional preset

    Returns:
        session_id: Unique ID to access the preview
        url: URL to load the preview
        preset: Applied preset name
        deps_injected: List of injected dependencies (for three-webgl-umd)
        expires_at: Unix timestamp when session expires
    """
    return create_preview_session_internal(
        html=request.html,
        preset=request.preset,
        snippet_id=request.snippet_id
    )


@router.get("/preview/{session_id}", response_class=HTMLResponse)
async def get_preview(session_id: str):
    """
    Retrieve HTML content for a preview session.

    Args:
        session_id: Preview session ID

    Returns:
        HTML content

    Raises:
        404: Session not found
        410: Session expired
    """
    if session_id not in preview_sessions:
        raise HTTPException(status_code=404, detail="Preview session not found")

    session = preview_sessions[session_id]
    now = int(utc_now().timestamp())

    # Check TTL expiration
    if now > session.expires_at:
        del preview_sessions[session_id]
        log_audit_event(PREVIEW_SESSION_EXPIRED, preview_id=session_id, snippet_id=session.snippet_id)
        raise HTTPException(status_code=410, detail="Preview session expired")

    # Log open event
    log_audit_event(PREVIEW_SESSION_OPENED, preview_id=session_id, snippet_id=session.snippet_id)

    # Return HTML with proper headers
    return HTMLResponse(
        content=session.html,
        headers={
            "Content-Type": "text/html; charset=utf-8",
            "X-Frame-Options": "SAMEORIGIN",  # Only allow same-origin framing
        }
    )


@router.get("/preview/{session_id}/meta")
async def get_preview_meta(session_id: str):
    """
    Get metadata for a preview session.

    Args:
        session_id: Preview session ID

    Returns:
        Session metadata including preset, dependencies, and TTL info

    Raises:
        404: Session not found
        410: Session expired
    """
    if session_id not in preview_sessions:
        raise HTTPException(status_code=404, detail="Preview session not found")

    session = preview_sessions[session_id]
    now = int(utc_now().timestamp())

    # Check TTL expiration
    if now > session.expires_at:
        del preview_sessions[session_id]
        log_audit_event(PREVIEW_SESSION_EXPIRED, preview_id=session_id, snippet_id=session.snippet_id)
        raise HTTPException(status_code=410, detail="Preview session expired")

    return {
        "session_id": session.session_id,
        "preset": session.preset,
        "deps_injected": session.deps_injected,
        "snippet_id": session.snippet_id,
        "created_at": session.created_at,
        "expires_at": session.expires_at,
        "ttl_remaining": session.expires_at - now
    }


@router.delete("/preview/{session_id}")
async def delete_preview_session(session_id: str):
    """
    Delete a preview session.

    Args:
        session_id: Preview session ID

    Returns:
        Success message
    """
    if session_id in preview_sessions:
        del preview_sessions[session_id]
        logger.info(f"Deleted preview session: {session_id}")

    return {"message": "Preview session deleted"}
