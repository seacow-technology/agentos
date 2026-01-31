"""Answers Service - Answer pack management and application

This service provides answer pack management:
1. Create and validate answer packs
2. Generate application proposals (no direct apply)
3. Track answer pack usage
4. Query related tasks/intents

Created for Wave 1-A6 & Wave 3-E3: Answers management API
Updated for Agent-DB-Answers: Real database integration
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from agentos.store.answers_store import AnswersRepo, AnswerPack, AnswerPackLink
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


class AnswersServiceError(Exception):
    """Base error for answers service"""
    pass


class AnswerPackNotFoundError(AnswersServiceError):
    """Answer pack not found"""
    pass


class AnswerPackValidationError(AnswersServiceError):
    """Answer pack validation failed"""
    pass


class AnswersService:
    """Answer pack management service

    Handles:
    - Answer pack CRUD
    - Validation (structure and content)
    - Apply proposals (not direct application)
    - Link tracking (pack -> task/intent relationships)
    """

    def __init__(self, repo: AnswersRepo):
        """Initialize service

        Args:
            repo: AnswersRepo instance for database access
        """
        self.repo = repo

    def list_packs(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[AnswerPack], int]:
        """List answer packs with filtering

        Args:
            status: Filter by validation status
            search: Search query (name/description)
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (packs list, total count)
        """
        return self.repo.list(
            status=status,
            q=search,
            limit=limit,
            offset=offset
        )

    def get_pack(self, pack_id: str) -> AnswerPack:
        """Get single answer pack

        Args:
            pack_id: Pack ID

        Returns:
            AnswerPack

        Raises:
            AnswerPackNotFoundError: Pack not found
        """
        pack = self.repo.get(pack_id)
        if not pack:
            raise AnswerPackNotFoundError(f"Answer pack {pack_id} not found")
        return pack

    def create_pack(
        self,
        name: str,
        items: List[Dict[str, Any]],
        metadata: Optional[Dict] = None
    ) -> AnswerPack:
        """Create new answer pack (initial status: draft)

        Args:
            name: Pack name
            items: List of Q&A items [{"question": "...", "answer": "...", "type": "..."}]
            metadata: Optional metadata dict

        Returns:
            Created AnswerPack

        Raises:
            AnswerPackValidationError: Invalid items structure
        """
        # Basic validation
        self._validate_items(items)

        pack = AnswerPack(
            id=str(uuid.uuid4()),
            name=name,
            status="draft",
            items_json=json.dumps(items),
            metadata_json=json.dumps(metadata) if metadata else None,
            created_at=utc_now_iso() + "Z",
            updated_at=utc_now_iso() + "Z"
        )

        return self.repo.create(pack)

    def validate_pack(self, pack_id: str) -> Dict[str, Any]:
        """Validate answer pack structure and content

        Args:
            pack_id: Pack ID

        Returns:
            Validation result dict:
            {
                "valid": true/false,
                "errors": [...],
                "warnings": [...]
            }
        """
        pack = self.get_pack(pack_id)

        errors = []
        warnings = []

        try:
            items = json.loads(pack.items_json)

            # Validate structure
            if not isinstance(items, list):
                errors.append("items must be a list")
            else:
                for i, item in enumerate(items):
                    if not isinstance(item, dict):
                        errors.append(f"Item {i}: must be an object")
                        continue

                    # Check required fields
                    if "question" not in item:
                        errors.append(f"Item {i}: missing 'question' field")
                    if "answer" not in item:
                        errors.append(f"Item {i}: missing 'answer' field")

                    # Check types
                    if "type" in item and item["type"] not in ["security_answer", "config_answer", "general"]:
                        warnings.append(f"Item {i}: unknown type '{item['type']}'")

                    # Check for empty content
                    if item.get("question", "").strip() == "":
                        errors.append(f"Item {i}: question is empty")
                    if item.get("answer", "").strip() == "":
                        errors.append(f"Item {i}: answer is empty")

        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON: {str(e)}")

        # If validation passes, update status
        if not errors and pack.status == "draft":
            self.repo.set_status(pack_id, "validated")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def update_pack(
        self,
        pack_id: str,
        items: Optional[List[Dict]] = None,
        metadata: Optional[Dict] = None
    ) -> AnswerPack:
        """Update answer pack (only draft/validated packs can be updated)

        Args:
            pack_id: Pack ID
            items: New items list (optional)
            metadata: New metadata (optional)

        Returns:
            Updated AnswerPack

        Raises:
            AnswersServiceError: If pack is frozen or deprecated
        """
        pack = self.get_pack(pack_id)

        if pack.status in ["frozen", "deprecated"]:
            raise AnswersServiceError(
                f"Cannot update {pack.status} pack. Current status: {pack.status}"
            )

        items_json = json.dumps(items) if items is not None else pack.items_json
        metadata_json = json.dumps(metadata) if metadata is not None else pack.metadata_json

        return self.repo.update(pack_id, items_json, metadata_json)

    def set_status(self, pack_id: str, new_status: str) -> AnswerPack:
        """Change pack status (draft/validated/deprecated/frozen)

        Args:
            pack_id: Pack ID
            new_status: New status

        Returns:
            Updated AnswerPack

        Raises:
            AnswersServiceError: If transition is invalid
        """
        pack = self.get_pack(pack_id)

        # Validate transitions
        if pack.status == "frozen":
            raise AnswersServiceError("Cannot change status of frozen pack")

        return self.repo.set_status(pack_id, new_status)

    def create_apply_proposal(
        self,
        pack_id: str,
        target_intent_id: str,
        field_mappings: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Generate proposal to apply answer pack to intent

        CRITICAL: This does NOT directly apply answers.
        It creates a proposal that requires approval (Guardian review).

        Args:
            pack_id: Pack ID
            target_intent_id: Target intent ID
            field_mappings: Optional field mappings

        Returns:
            Proposal dict:
            {
                "proposal_id": "...",
                "pack_id": "...",
                "target_intent_id": "...",
                "preview": {...},  # What would be applied
                "status": "pending_review"
            }
        """
        pack = self.get_pack(pack_id)
        items = json.loads(pack.items_json)

        # Create proposal (would be stored in proposals table or task_audits)
        proposal = {
            "proposal_id": str(uuid.uuid4()),
            "proposal_type": "answer_pack_application",
            "pack_id": pack_id,
            "target_intent_id": target_intent_id,
            "field_mappings": field_mappings or {},
            "preview": {
                "pack_name": pack.name,
                "items_count": len(items),
                "items_sample": items[:3]  # First 3 for preview
            },
            "status": "pending_review",
            "requires_guardian": True
        }

        # TODO: Write to proposals table or audit table
        # For now, just return the proposal object

        logger.info(f"Created apply proposal {proposal['proposal_id']} for pack {pack_id}")

        return proposal

    def link_to_entity(
        self,
        pack_id: str,
        entity_type: str,
        entity_id: str
    ) -> AnswerPackLink:
        """Create link between pack and task/intent

        Args:
            pack_id: Answer pack ID
            entity_type: "task" or "intent"
            entity_id: Task/Intent ID

        Returns:
            Created link
        """
        pack = self.get_pack(pack_id)  # Validates pack exists

        return self.repo.link(pack_id, entity_type, entity_id)

    def get_related_entities(self, pack_id: str) -> List[Dict[str, Any]]:
        """Get all tasks/intents that reference this pack

        Args:
            pack_id: Pack ID

        Returns:
            List of related entities:
            [
                {"type": "task", "id": "...", "name": "...", "status": "..."},
                {"type": "intent", "id": "...", "name": "...", "status": "..."}
            ]
        """
        pack = self.get_pack(pack_id)  # Validates pack exists

        links = self.repo.list_links(pack_id)

        # Enrich with entity details (would need to join with tasks/intents tables)
        # For now, return basic link info
        return [
            {
                "type": link.entity_type,
                "id": link.entity_id,
                "linked_at": link.created_at
                # TODO: Fetch name/status from tasks/intents if available
            }
            for link in links
        ]

    def _validate_items(self, items: List[Dict]) -> None:
        """Basic validation for items structure

        Args:
            items: Items list to validate

        Raises:
            AnswerPackValidationError: If items are invalid
        """
        if not isinstance(items, list):
            raise AnswerPackValidationError("items must be a list")

        if len(items) == 0:
            raise AnswerPackValidationError("items must not be empty")

        for i, item in enumerate(items):
            if not isinstance(item, dict):
                raise AnswerPackValidationError(f"Item {i} must be an object")

            if "question" not in item or "answer" not in item:
                raise AnswerPackValidationError(
                    f"Item {i} must have 'question' and 'answer' fields"
                )
