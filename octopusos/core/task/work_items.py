"""Work Items Framework - Sequential Sub-Agent Execution

This module provides the work_items framework for Task #3: PR-C.
Work items represent sub-tasks that are executed by independent agents,
enabling complex tasks to be broken down and coordinated.

Phase 1: Sequential Execution (PR-C)
- Extract work_items from planning stage
- Execute work_items serially (one by one)
- Each work_item runs in an independent agent context
- Aggregate results and handle failures

Future: Parallel Execution (PR-D)
- Parallel execution of independent work_items
- Dependency-aware scheduling
- Resource management
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from enum import Enum
import json
from agentos.core.time import utc_now_iso



class WorkItemStatus(str, Enum):
    """Work item execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkItemOutput:
    """Structured output from a work item execution

    This schema defines what each sub-agent must produce.
    """
    files_changed: List[str] = field(default_factory=list)
    commands_run: List[str] = field(default_factory=list)
    tests_run: List[Dict[str, Any]] = field(default_factory=list)
    evidence: Optional[str] = None
    handoff_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "files_changed": self.files_changed,
            "commands_run": self.commands_run,
            "tests_run": self.tests_run,
            "evidence": self.evidence,
            "handoff_notes": self.handoff_notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkItemOutput":
        """Create from dictionary"""
        return cls(
            files_changed=data.get("files_changed", []),
            commands_run=data.get("commands_run", []),
            tests_run=data.get("tests_run", []),
            evidence=data.get("evidence"),
            handoff_notes=data.get("handoff_notes"),
        )


@dataclass
class WorkItem:
    """A single work item (sub-task) to be executed by an agent

    Work items are extracted from the planning stage and executed
    sequentially (PR-C) or in parallel (PR-D, future).

    Attributes:
        item_id: Unique identifier for this work item
        title: Short description (e.g., "Implement frontend UI")
        description: Detailed task description
        dependencies: List of work_item_ids this depends on
        status: Current execution status
        output: Execution output (populated after completion)
        started_at: When execution started
        completed_at: When execution completed
        error: Error message if failed
        metadata: Additional metadata
    """
    item_id: str
    title: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    status: WorkItemStatus = WorkItemStatus.PENDING
    output: Optional[WorkItemOutput] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "item_id": self.item_id,
            "title": self.title,
            "description": self.description,
            "dependencies": self.dependencies,
            "status": self.status.value if isinstance(self.status, WorkItemStatus) else self.status,
            "output": self.output.to_dict() if self.output else None,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkItem":
        """Create from dictionary"""
        output_data = data.get("output")
        output = WorkItemOutput.from_dict(output_data) if output_data else None

        return cls(
            item_id=data["item_id"],
            title=data["title"],
            description=data["description"],
            dependencies=data.get("dependencies", []),
            status=WorkItemStatus(data.get("status", "pending")),
            output=output,
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )

    def mark_running(self):
        """Mark work item as running"""
        self.status = WorkItemStatus.RUNNING
        self.started_at = utc_now_iso()

    def mark_completed(self, output: WorkItemOutput):
        """Mark work item as completed"""
        self.status = WorkItemStatus.COMPLETED
        self.output = output
        self.completed_at = utc_now_iso()

    def mark_failed(self, error: str):
        """Mark work item as failed"""
        self.status = WorkItemStatus.FAILED
        self.error = error
        self.completed_at = utc_now_iso()

    def mark_skipped(self, reason: str):
        """Mark work item as skipped"""
        self.status = WorkItemStatus.SKIPPED
        self.error = reason
        self.completed_at = utc_now_iso()


@dataclass
class WorkItemsSummary:
    """Summary of work items execution

    Aggregates results from all work items and provides
    overall status and statistics.
    """
    total_items: int
    completed_count: int
    failed_count: int
    skipped_count: int
    overall_status: str  # "success", "partial", "failed"
    work_items: List[WorkItem]
    execution_order: List[str] = field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_items": self.total_items,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "overall_status": self.overall_status,
            "work_items": [item.to_dict() for item in self.work_items],
            "execution_order": self.execution_order,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration_seconds": self.total_duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkItemsSummary":
        """Create from dictionary"""
        return cls(
            total_items=data["total_items"],
            completed_count=data["completed_count"],
            failed_count=data["failed_count"],
            skipped_count=data["skipped_count"],
            overall_status=data["overall_status"],
            work_items=[WorkItem.from_dict(item) for item in data.get("work_items", [])],
            execution_order=data.get("execution_order", []),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            total_duration_seconds=data.get("total_duration_seconds", 0.0),
        )

    @property
    def all_succeeded(self) -> bool:
        """Check if all work items succeeded"""
        return self.overall_status == "success" and self.failed_count == 0

    @property
    def any_failed(self) -> bool:
        """Check if any work item failed"""
        return self.failed_count > 0

    def get_failure_summary(self) -> str:
        """Get summary of failed work items"""
        if not self.any_failed:
            return "No failures"

        failed_items = [item for item in self.work_items if item.status == WorkItemStatus.FAILED]
        summary_parts = []
        for item in failed_items:
            msg = f"- {item.title} ({item.item_id}): {item.error or 'Unknown error'}"
            summary_parts.append(msg)

        return "\n".join(summary_parts)


def extract_work_items_from_pipeline(pipeline_result: Any) -> List[WorkItem]:
    """Extract work items from pipeline result

    This function parses the planning stage output and extracts
    work items for execution.

    Args:
        pipeline_result: Pipeline result from planning stage

    Returns:
        List of WorkItem objects

    Example pipeline output structure:
        {
            "work_items": [
                {
                    "item_id": "wi_001",
                    "title": "Implement frontend UI",
                    "description": "Create React components...",
                    "dependencies": []
                },
                {
                    "item_id": "wi_002",
                    "title": "Implement backend API",
                    "description": "Create REST endpoints...",
                    "dependencies": []
                }
            ]
        }
    """
    work_items = []

    # Try to extract from pipeline result stages
    if hasattr(pipeline_result, 'stages') and pipeline_result.stages:
        for stage in pipeline_result.stages:
            # Look for work_items in stage output
            if hasattr(stage, 'output') and isinstance(stage.output, dict):
                work_items_data = stage.output.get("work_items")
                if work_items_data:
                    for item_data in work_items_data:
                        work_items.append(WorkItem.from_dict(item_data))
                    break  # Found work_items, stop searching

    # Fallback: Try to extract from pipeline metadata
    if not work_items and hasattr(pipeline_result, 'metadata'):
        work_items_data = pipeline_result.metadata.get("work_items")
        if work_items_data:
            for item_data in work_items_data:
                work_items.append(WorkItem.from_dict(item_data))

    return work_items


def create_work_items_summary(work_items: List[WorkItem]) -> WorkItemsSummary:
    """Create summary from work items

    Args:
        work_items: List of work items

    Returns:
        WorkItemsSummary object
    """
    completed_count = sum(1 for item in work_items if item.status == WorkItemStatus.COMPLETED)
    failed_count = sum(1 for item in work_items if item.status == WorkItemStatus.FAILED)
    skipped_count = sum(1 for item in work_items if item.status == WorkItemStatus.SKIPPED)

    # Determine overall status
    if failed_count > 0:
        overall_status = "failed"
    elif completed_count == len(work_items):
        overall_status = "success"
    else:
        overall_status = "partial"

    # Calculate total duration
    total_duration = 0.0
    started_at = None
    completed_at = None

    for item in work_items:
        if item.started_at and item.completed_at:
            try:
                start = datetime.fromisoformat(item.started_at.replace('Z', '+00:00'))
                end = datetime.fromisoformat(item.completed_at.replace('Z', '+00:00'))
                duration = (end - start).total_seconds()
                total_duration += duration

                # Track earliest start and latest completion
                if not started_at or item.started_at < started_at:
                    started_at = item.started_at
                if not completed_at or item.completed_at > completed_at:
                    completed_at = item.completed_at
            except Exception:
                pass

    return WorkItemsSummary(
        total_items=len(work_items),
        completed_count=completed_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        overall_status=overall_status,
        work_items=work_items,
        started_at=started_at,
        completed_at=completed_at,
        total_duration_seconds=total_duration,
    )
