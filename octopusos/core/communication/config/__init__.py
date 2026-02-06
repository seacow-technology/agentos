"""Configuration utilities for CommunicationOS.

This module provides utilities for loading and managing configuration
files used by the communication system.
"""

import os
from pathlib import Path
from typing import Dict, List

import yaml


def load_trusted_sources() -> Dict[str, List[str]]:
    """Load trusted sources configuration from YAML file.

    Returns:
        Dictionary with 'official_policy' and 'recognized_ngo' keys,
        each containing a list of trusted domain names.

    Raises:
        FileNotFoundError: If trusted_sources.yaml is not found
        yaml.YAMLError: If YAML parsing fails
    """
    config_dir = Path(__file__).parent
    config_path = config_dir / "trusted_sources.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Trusted sources configuration not found: {config_path}"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Normalize keys to lowercase for consistency
    return {
        "official_policy": config.get("OFFICIAL_POLICY_SOURCES", []),
        "recognized_ngo": config.get("RECOGNIZED_NGO", []),
    }


def get_trusted_sources_path() -> Path:
    """Get path to trusted sources configuration file.

    Returns:
        Path to trusted_sources.yaml
    """
    return Path(__file__).parent / "trusted_sources.yaml"


__all__ = [
    "load_trusted_sources",
    "get_trusted_sources_path",
]
