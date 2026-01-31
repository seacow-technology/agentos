"""
Share API - Preview Code Sharing

Provides endpoints to share HTML preview code and retrieve shared previews.

Phase 4: Advanced Features
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


from agentos.webui.api.time_format import iso_z
from agentos.core.time import utc_now

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage for shared previews
# TODO: Move to database for production use
shared_previews: Dict[str, Dict] = {}

# Configuration
MAX_SHARES = 1000  # Maximum number of shares to keep
SHARE_EXPIRY_DAYS = 30  # Shares expire after 30 days


class ShareRequest(BaseModel):
    """Request to create a share link"""
    code: str


class ShareResponse(BaseModel):
    """Response with share link information"""
    id: str
    url: str
    expires_at: str


class ShareData(BaseModel):
    """Shared preview data"""
    id: str
    code: str
    created_at: str
    expires_at: str


@router.post("/share", response_model=ShareResponse)
async def create_share(request: ShareRequest):
    """
    Create a shareable link for HTML preview code.

    Args:
        request: ShareRequest with HTML code

    Returns:
        ShareResponse with share ID and URL

    Example:
        POST /api/share
        {
            "code": "<html>...</html>"
        }

        Response:
        {
            "id": "abc123",
            "url": "/share/abc123",
            "expires_at": "2026-02-28T00:00:00Z"
        }
    """
    try:
        # Generate unique ID
        share_id = str(uuid.uuid4())[:8]

        # Ensure unique ID
        while share_id in shared_previews:
            share_id = str(uuid.uuid4())[:8]

        # Calculate expiry
        now = utc_now()
        expires_at = now + timedelta(days=SHARE_EXPIRY_DAYS)

        # Store share data
        shared_previews[share_id] = {
            'code': request.code,
            'created_at': iso_z(now),
            'expires_at': iso_z(expires_at)
        }

        # Clean up old shares if needed
        cleanup_expired_shares()

        # Limit total shares
        if len(shared_previews) > MAX_SHARES:
            # Remove oldest share
            oldest = min(shared_previews.keys(),
                        key=lambda k: shared_previews[k]['created_at'])
            del shared_previews[oldest]

        logger.info(f"Created share: {share_id}")

        return ShareResponse(
            id=share_id,
            url=f"/share/{share_id}",
            expires_at=iso_z(expires_at)
        )

    except Exception as e:
        logger.error(f"Failed to create share: {e}")
        raise HTTPException(status_code=500, detail="Failed to create share link")


@router.get("/share/{share_id}", response_model=ShareData)
async def get_share(share_id: str):
    """
    Retrieve shared preview code by ID.

    Args:
        share_id: Share identifier

    Returns:
        ShareData with HTML code

    Raises:
        404: Share not found or expired
    """
    if share_id not in shared_previews:
        raise HTTPException(status_code=404, detail="Share not found")

    share = shared_previews[share_id]

    # Check if expired
    expires_at = datetime.fromisoformat(share['expires_at'])
    if utc_now() > expires_at:
        del shared_previews[share_id]
        raise HTTPException(status_code=404, detail="Share has expired")

    return ShareData(
        id=share_id,
        code=share['code'],
        created_at=share['created_at'],
        expires_at=share['expires_at']
    )


@router.delete("/share/{share_id}")
async def delete_share(share_id: str):
    """
    Delete a shared preview.

    Args:
        share_id: Share identifier

    Returns:
        Success message

    Raises:
        404: Share not found
    """
    if share_id not in shared_previews:
        raise HTTPException(status_code=404, detail="Share not found")

    del shared_previews[share_id]
    logger.info(f"Deleted share: {share_id}")

    return {"message": "Share deleted successfully"}


@router.get("/shares/stats")
async def get_stats():
    """
    Get statistics about shares.

    Returns:
        Statistics object
    """
    cleanup_expired_shares()

    return {
        "total_shares": len(shared_previews),
        "max_shares": MAX_SHARES,
        "expiry_days": SHARE_EXPIRY_DAYS
    }


def cleanup_expired_shares():
    """Remove expired shares from storage"""
    now = utc_now()
    expired = [
        share_id
        for share_id, share in shared_previews.items()
        if datetime.fromisoformat(share['expires_at']) < now
    ]

    for share_id in expired:
        del shared_previews[share_id]

    if expired:
        logger.info(f"Cleaned up {len(expired)} expired shares")
