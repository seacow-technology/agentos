"""
Authentication Profiles API Endpoints (Read-Only)

Provides read-only access to git auth configurations
Write operations are CLI-only as per requirements

Part of Agent-View-Answers delivery (Wave2-E2)

Endpoints:
- GET /api/auth/profiles - List auth profiles (read-only, data sanitized)
- GET /api/auth/profiles/{id} - Get profile details (read-only, data sanitized)
- POST /api/auth/profiles/{id}/validate - Test connection (no credential logging)
"""

import logging
from datetime import timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


from agentos.webui.api.time_format import iso_z
from agentos.core.time import utc_now

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Request/Response Models ====================

class AuthProfile(BaseModel):
    """Authentication profile (sanitized for display)"""
    id: str
    type: str  # ssh, pat, netrc
    host: Optional[str] = None
    repo: Optional[str] = None
    status: str  # valid, invalid, untested
    metadata: Dict  # Sanitized metadata (no sensitive data)
    created_at: str
    last_validated: Optional[str] = None


class ValidateResult(BaseModel):
    """Validation result for auth profile"""
    valid: bool
    message: str
    tested_at: str


# ==================== In-Memory Storage (Placeholder) ====================
# In production, this would read from ~/.ssh/config, ~/.gitconfig, ~/.netrc, etc.

_auth_profiles: Dict[str, Dict] = {
    "auth_ssh_001": {
        "id": "auth_ssh_001",
        "type": "ssh",
        "host": "github.com",
        "repo": None,
        "status": "valid",
        "metadata": {
            "fingerprint": "SHA256:nThbg6kXUpJWGl7E1IGOCspRomTxdCARLviKw6E5SY8",
            "key_path": "~/.ssh/id_rsa",
            "key_type": "RSA 4096"
        },
        "created_at": "2026-01-15T10:00:00Z",
        "last_validated": "2026-01-28T08:00:00Z"
    },
    "auth_pat_001": {
        "id": "auth_pat_001",
        "type": "pat",
        "host": "github.com",
        "repo": None,
        "status": "valid",
        "metadata": {
            "token_prefix": "ghp_****",  # Only show first 4 chars
            "scopes": ["repo", "read:org", "workflow"],
            "expires_at": "2027-01-15T00:00:00Z"
        },
        "created_at": "2026-01-20T12:00:00Z",
        "last_validated": "2026-01-28T09:00:00Z"
    },
    "auth_netrc_001": {
        "id": "auth_netrc_001",
        "type": "netrc",
        "host": "gitlab.company.com",
        "repo": None,
        "status": "untested",
        "metadata": {
            "machine": "gitlab.company.com",
            "login": "build-bot",
            # Password is NEVER included in response
        },
        "created_at": "2026-01-25T14:00:00Z",
        "last_validated": None
    }
}


# ==================== Helper Functions ====================

def sanitize_auth_profile(profile: Dict) -> Dict:
    """
    Sanitize auth profile for display

    - SSH: Show fingerprint only, never private key
    - PAT: Show first 4 chars + scopes, never full token
    - netrc: Show host + username, never password
    """
    sanitized = profile.copy()

    if profile["type"] == "ssh":
        # SSH: Keep fingerprint, remove any sensitive keys
        if "private_key" in sanitized.get("metadata", {}):
            del sanitized["metadata"]["private_key"]

    elif profile["type"] == "pat":
        # PAT: Ensure token is masked
        metadata = sanitized.get("metadata", {})
        if "token" in metadata:
            token = metadata["token"]
            metadata["token_prefix"] = token[:4] + "****"
            del metadata["token"]

    elif profile["type"] == "netrc":
        # netrc: Remove password
        metadata = sanitized.get("metadata", {})
        if "password" in metadata:
            del metadata["password"]

    return sanitized


# ==================== Endpoints ====================

@router.get("/api/auth/profiles")
async def list_auth_profiles(
    type: Optional[str] = None,
    host: Optional[str] = None,
    status: Optional[str] = None
):
    """
    List all authentication profiles (read-only, sanitized)

    Query params:
    - type: Filter by type (ssh, pat, netrc)
    - host: Filter by host
    - status: Filter by status (valid, invalid, untested)

    NOTE: All sensitive data is sanitized before returning
    """
    try:
        profiles = list(_auth_profiles.values())

        # Apply filters
        if type:
            profiles = [p for p in profiles if p["type"] == type]

        if host:
            profiles = [p for p in profiles if p.get("host") == host]

        if status:
            profiles = [p for p in profiles if p["status"] == status]

        # Sanitize all profiles
        profiles = [sanitize_auth_profile(p) for p in profiles]

        # Sort by created_at desc
        profiles.sort(key=lambda x: x["created_at"], reverse=True)

        return {
            "ok": True,
            "data": profiles,
            "cli_hint": "To add or modify auth profiles, use: agentos auth add --type ssh --key ~/.ssh/id_rsa"
        }

    except Exception as e:
        logger.error(f"Failed to list auth profiles: {e}")
        return {"ok": False, "error": str(e)}


@router.get("/api/auth/profiles/{profile_id}")
async def get_auth_profile(profile_id: str):
    """Get detailed information about an auth profile (read-only, sanitized)"""
    try:
        if profile_id not in _auth_profiles:
            raise HTTPException(status_code=404, detail="Auth profile not found")

        profile = _auth_profiles[profile_id]
        sanitized = sanitize_auth_profile(profile)

        return {
            "ok": True,
            "data": sanitized,
            "cli_hint": "To modify this profile, use: agentos auth update " + profile_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get auth profile {profile_id}: {e}")
        return {"ok": False, "error": str(e)}


@router.post("/api/auth/profiles/{profile_id}/validate")
async def validate_auth_profile(profile_id: str):
    """
    Test authentication profile connection

    This is a read-only operation that tests connectivity.
    No credentials are logged or stored during validation.
    """
    try:
        if profile_id not in _auth_profiles:
            raise HTTPException(status_code=404, detail="Auth profile not found")

        profile = _auth_profiles[profile_id]

        # Mock validation (in production: actually test the connection)
        # For SSH: try ssh -T git@{host}
        # For PAT: try API call with token
        # For netrc: try git ls-remote

        import random
        from datetime import datetime

        # Simulate validation with 90% success rate
        is_valid = random.random() < 0.9

        if is_valid:
            message = f"Successfully authenticated to {profile.get('host', 'host')}"
            _auth_profiles[profile_id]["status"] = "valid"
            _auth_profiles[profile_id]["last_validated"] = iso_z(utc_now()) + "Z"
        else:
            message = f"Authentication failed: Connection timeout to {profile.get('host', 'host')}"
            _auth_profiles[profile_id]["status"] = "invalid"

        logger.info(f"Validated auth profile: {profile_id} -> {'valid' if is_valid else 'invalid'}")

        return {
            "ok": True,
            "data": {
                "valid": is_valid,
                "message": message,
                "tested_at": iso_z(utc_now()) + "Z"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate auth profile {profile_id}: {e}")
        return {"ok": False, "error": str(e)}


# ==================== CLI-Only Operations ====================
# These are intentionally NOT exposed via API endpoints.
# They can only be performed via CLI.

"""
CLI-ONLY operations (not exposed in WebUI):

agentos auth add --type ssh --key ~/.ssh/id_rsa
agentos auth add --type pat --token ghp_xxx --scopes repo,workflow
agentos auth add --type netrc --machine gitlab.com --login user --password xxx
agentos auth remove {profile_id}
agentos auth update {profile_id} --key ~/.ssh/new_key

These operations are intentionally CLI-only for security reasons:
1. Prevents accidental exposure of credentials via web interface
2. Ensures credentials are handled in trusted environment (local terminal)
3. Avoids risk of credential interception via browser/network
"""
