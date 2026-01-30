"""
BrainOS Build Manifest

Records metadata about each index build:
- When it was built
- What was extracted
- Statistics and errors
- Source commit and version info
"""

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class BuildManifest:
    """
    Build manifest for a BrainOS index build.

    Contains all metadata needed to understand what was built,
    when, and from what source.
    """
    graph_version: str              # "20260130-150432-6aa4aaa"
    source_commit: str              # "6aa4aaa" or full hash
    repo_path: str                  # Absolute path to repo
    started_at: str                 # ISO 8601 timestamp
    finished_at: str                # ISO 8601 timestamp
    duration_ms: int                # Build duration in milliseconds
    counts: Dict[str, int]          # {"entities": 150, "edges": 120, ...}
    enabled_extractors: List[str]   # ["git", "doc", ...]
    errors: List[str]               # Error messages (empty if successful)
    brainos_version: str            # "0.1.0-alpha"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BuildManifest':
        """Create from dictionary (deserialization)."""
        return cls(**data)

    def is_successful(self) -> bool:
        """Check if build was successful (no errors)."""
        return len(self.errors) == 0

    def summary(self) -> str:
        """Get human-readable summary."""
        status = "SUCCESS" if self.is_successful() else "FAILED"
        return (
            f"BrainOS Build {status}\n"
            f"  Version: {self.graph_version}\n"
            f"  Commit:  {self.source_commit}\n"
            f"  Repo:    {self.repo_path}\n"
            f"  Time:    {self.finished_at}\n"
            f"  Duration: {self.duration_ms}ms\n"
            f"  Entities: {self.counts.get('entities', 0)}\n"
            f"  Edges:    {self.counts.get('edges', 0)}\n"
            f"  Evidence: {self.counts.get('evidence', 0)}\n"
            f"  Extractors: {', '.join(self.enabled_extractors)}\n"
            + (f"  Errors: {len(self.errors)}\n" if not self.is_successful() else "")
        )


def save_manifest(manifest: BuildManifest, path: str) -> None:
    """
    Save build manifest to JSON file.

    Args:
        manifest: BuildManifest to save
        path: Output file path (usually <db_path>.manifest.json)
    """
    # Ensure parent directory exists
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)


def load_manifest(path: str) -> BuildManifest:
    """
    Load build manifest from JSON file.

    Args:
        path: Manifest file path

    Returns:
        BuildManifest instance

    Raises:
        FileNotFoundError: If manifest file doesn't exist
        ValueError: If manifest JSON is invalid
    """
    if not Path(path).exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return BuildManifest.from_dict(data)


def create_graph_version(commit_hash: str) -> str:
    """
    Create graph version string.

    Format: YYYYMMDD-HHMMSS-<short_commit>

    Args:
        commit_hash: Git commit hash (short or full)

    Returns:
        Graph version string
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    short_commit = commit_hash[:7] if len(commit_hash) > 7 else commit_hash
    return f"{timestamp}-{short_commit}"


def get_iso_timestamp() -> str:
    """Get current time as ISO 8601 timestamp."""
    return datetime.utcnow().isoformat() + 'Z'
