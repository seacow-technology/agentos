"""Answer Pack storage and management.

Provides file-based storage for AnswerPacks with validation and retrieval.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from agentos.core.time import utc_now_iso



class AnswerStore:
    """Store and retrieve AnswerPacks from filesystem."""

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize AnswerStore.

        Args:
            base_path: Base directory for storing answer packs.
                      Defaults to outputs/answers/
        """
        self.base_path = base_path or Path("outputs/answers")
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(self, answer_pack: Dict[str, Any], output_path: Optional[Path] = None) -> Path:
        """
        Save an AnswerPack to disk.

        Args:
            answer_pack: The answer pack data
            output_path: Optional specific path. If None, auto-generate from pack_id

        Returns:
            Path where the answer pack was saved

        Raises:
            ValueError: If answer_pack is invalid
        """
        if not answer_pack.get("answer_pack_id"):
            raise ValueError("answer_pack_id is required")

        if output_path is None:
            pack_id = answer_pack["answer_pack_id"]
            output_path = self.base_path / f"{pack_id}.json"

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write with pretty formatting
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(answer_pack, f, indent=2, ensure_ascii=False)

        return output_path

    def load(self, pack_id_or_path: str | Path) -> Dict[str, Any]:
        """
        Load an AnswerPack from disk.

        Args:
            pack_id_or_path: Either a pack ID (e.g., 'apack_123') or full path

        Returns:
            The loaded answer pack data

        Raises:
            FileNotFoundError: If the answer pack doesn't exist
            json.JSONDecodeError: If the file is not valid JSON
        """
        if isinstance(pack_id_or_path, str) and pack_id_or_path.startswith("apack_"):
            # It's a pack ID
            file_path = self.base_path / f"{pack_id_or_path}.json"
        else:
            # It's a path
            file_path = Path(pack_id_or_path)

        if not file_path.exists():
            raise FileNotFoundError(f"AnswerPack not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def exists(self, pack_id: str) -> bool:
        """
        Check if an AnswerPack exists.

        Args:
            pack_id: The answer pack ID

        Returns:
            True if the pack exists, False otherwise
        """
        file_path = self.base_path / f"{pack_id}.json"
        return file_path.exists()

    def list_packs(self, question_pack_id: Optional[str] = None) -> list[Dict[str, Any]]:
        """
        List all AnswerPacks, optionally filtered by question_pack_id.

        Args:
            question_pack_id: Optional filter by question pack

        Returns:
            List of answer pack metadata
        """
        packs = []
        for file_path in self.base_path.glob("apack_*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if question_pack_id and data.get("question_pack_id") != question_pack_id:
                    continue

                packs.append({
                    "answer_pack_id": data.get("answer_pack_id"),
                    "question_pack_id": data.get("question_pack_id"),
                    "intent_id": data.get("intent_id"),
                    "provided_at": data.get("provided_at"),
                    "answer_count": len(data.get("answers", [])),
                    "path": str(file_path)
                })
            except (json.JSONDecodeError, KeyError):
                # Skip invalid files
                continue

        return sorted(packs, key=lambda x: x.get("provided_at", ""), reverse=True)

    def compute_checksum(self, answer_pack: Dict[str, Any]) -> str:
        """
        Compute SHA-256 checksum of answer pack (excluding checksum field).

        Args:
            answer_pack: The answer pack data

        Returns:
            Hex-encoded SHA-256 checksum
        """
        # Create a copy without the checksum field
        data_for_checksum = {k: v for k, v in answer_pack.items() if k != "checksum"}

        # Sort keys for consistent checksum
        json_str = json.dumps(data_for_checksum, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    def generate_pack_id(self, question_pack_id: str) -> str:
        """
        Generate a unique AnswerPack ID based on question pack and timestamp.

        Args:
            question_pack_id: The question pack being answered

        Returns:
            Generated answer pack ID (format: apack_<hash>)
        """
        timestamp = utc_now_iso()
        content = f"{question_pack_id}_{timestamp}"
        hash_value = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        return f"apack_{hash_value}"
