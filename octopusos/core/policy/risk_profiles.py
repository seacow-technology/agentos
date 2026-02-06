"""Risk profile configurations."""

RISK_PROFILES = {
    "safe": {
        "max_files_per_commit": 5,
        "forbidden_operations": [
            "rm -rf /",
            "DROP TABLE",
            "DELETE FROM",
            "TRUNCATE",
            "DROP DATABASE",
        ],
        "require_verification": True,
        "allow_destructive": False,
        "allow_bulk_changes": False,
        "description": "Safe mode: minimal risk, small changes only",
    },
    "aggressive_safe": {
        "max_files_per_commit": 50,
        "forbidden_operations": [
            "rm -rf /",
            "DROP DATABASE",
        ],
        "require_verification": True,
        "allow_destructive": False,
        "allow_bulk_changes": True,
        "description": "Aggressive safe mode: larger changes allowed, but still safe",
    },
    "aggressive": {
        "max_files_per_commit": 999,
        "forbidden_operations": [
            "rm -rf /",
        ],
        "require_verification": False,
        "allow_destructive": True,
        "allow_bulk_changes": True,
        "description": "Aggressive mode: maximum flexibility, minimal restrictions",
    },
}


def get_risk_profile(profile_name: str) -> dict:
    """Get risk profile configuration by name."""
    return RISK_PROFILES.get(profile_name, RISK_PROFILES["safe"])


def list_risk_profiles() -> list[str]:
    """List available risk profile names."""
    return list(RISK_PROFILES.keys())
