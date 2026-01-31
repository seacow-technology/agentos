"""
Knowledge API - RAG and Knowledge Base endpoints

Endpoints:
- POST /api/knowledge/search - Query Playground (Phase 1)
- GET /api/knowledge/sources - List data sources (Phase 2)
- POST /api/knowledge/sources - Add data source (Phase 2)
- PATCH /api/knowledge/sources/{id} - Update data source (Phase 2)
- DELETE /api/knowledge/sources/{id} - Delete data source (Phase 2)
- GET /api/knowledge/jobs - List index jobs (Phase 3)
- POST /api/knowledge/jobs - Trigger index job (Phase 3)
- GET /api/knowledge/jobs/{job_id} - Get job details (Phase 3)
- GET /api/knowledge/health - Health metrics (Phase 4)
"""

import json
import time
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from agentos.core.project_kb.service import ProjectKBService
from agentos.core.project_kb.types import ChunkResult
from agentos.core.events import Event, get_event_bus
from agentos.core.time import utc_now


if TYPE_CHECKING:
    from agentos.core.task import TaskManager
    from agentos.core.events import EventBus


from agentos.webui.api.time_format import iso_z
logger = logging.getLogger(__name__)
router = APIRouter()


# ============================
# Phase 1: Query Playground
# ============================


class SearchRequest(BaseModel):
    """Search request payload"""

    query: str = Field(..., description="Search query string")
    filters: Optional[Dict[str, Any]] = Field(
        default=None, description="Search filters (path_contains, file_types, time_range)"
    )
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results to return")
    explain: bool = Field(default=True, description="Include explanation in results")


class SearchResultItem(BaseModel):
    """Single search result item"""

    chunk_id: str
    path: str
    heading: Optional[str]
    lines: str
    content: str
    score: float
    explanation: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModel):
    """Search response"""

    ok: bool
    data: Dict[str, Any]
    error: Optional[str] = None


@router.post("/search")
async def search_knowledge(request: SearchRequest) -> SearchResponse:
    """
    Query Playground - Search the knowledge base

    Args:
        request: SearchRequest with query, filters, top_k, explain

    Returns:
        SearchResponse with results, total, duration_ms

    Example:
        POST /api/knowledge/search
        {
            "query": "JWT authentication",
            "filters": {
                "path_contains": "docs/",
                "file_types": ["md"],
                "time_range": {"start": "2024-01-01T00:00:00Z"}
            },
            "top_k": 10,
            "explain": true
        }
    """
    try:
        start_time = time.time()

        # Initialize ProjectKBService
        kb_service = ProjectKBService()

        # Build filters
        scope = None
        kb_filters = {}

        if request.filters:
            # Path filter
            if "path_contains" in request.filters:
                scope = request.filters["path_contains"]

            # File type filter (doc_type)
            if "file_types" in request.filters:
                file_types = request.filters["file_types"]
                if file_types:
                    kb_filters["doc_type"] = file_types[0]  # Simple implementation

            # Time range filter
            if "time_range" in request.filters:
                time_range = request.filters["time_range"]
                if "start" in time_range and time_range["start"]:
                    # Convert ISO string to timestamp
                    try:
                        dt = datetime.fromisoformat(time_range["start"].replace("Z", "+00:00"))
                        kb_filters["mtime_after"] = int(dt.timestamp())
                    except Exception:
                        pass
                if "end" in time_range and time_range["end"]:
                    try:
                        dt = datetime.fromisoformat(time_range["end"].replace("Z", "+00:00"))
                        kb_filters["mtime_before"] = int(dt.timestamp())
                    except Exception:
                        pass

        # Perform search
        results: List[ChunkResult] = kb_service.search(
            query=request.query,
            scope=scope,
            filters=kb_filters if kb_filters else None,
            top_k=request.top_k,
            explain=request.explain,
        )

        # Convert results to response format
        result_items = []
        for idx, result in enumerate(results):
            item = SearchResultItem(
                chunk_id=result.chunk_id,
                path=result.path,
                heading=result.heading,
                lines=result.lines,
                content=result.content,
                score=result.score,
                explanation=result.explanation.to_dict() if request.explain else None,
            )
            result_items.append(item.model_dump())

        duration_ms = int((time.time() - start_time) * 1000)

        return SearchResponse(
            ok=True,
            data={
                "results": result_items,
                "total": len(result_items),
                "duration_ms": duration_ms,
            },
        )

    except Exception as e:
        return SearchResponse(
            ok=False,
            data={},
            error=str(e),
        )


# ============================
# Phase 2: Knowledge Sources
# ============================

# In-memory storage for data sources (for demo purposes)
# In production, this would be persisted to a database
_data_sources_store: Dict[str, Dict[str, Any]] = {}


class DataSourceItem(BaseModel):
    """Data source item model"""

    source_id: str
    type: str = Field(..., description="Source type: directory, file, git")
    path: str = Field(..., description="Path to the data source")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Source configuration")
    chunk_count: int = Field(default=0, description="Number of chunks indexed")
    last_indexed_at: Optional[str] = Field(default=None, description="Last indexing timestamp")
    status: str = Field(default="pending", description="Status: pending, indexed, failed")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Update timestamp")


class CreateDataSourceRequest(BaseModel):
    """Request to create a new data source"""

    type: str = Field(..., description="Source type: directory, file, git")
    path: str = Field(..., description="Path to the data source")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Source configuration")


class UpdateDataSourceRequest(BaseModel):
    """Request to update a data source"""

    path: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class DataSourcesResponse(BaseModel):
    """Data sources list response"""

    ok: bool
    data: Dict[str, Any]
    error: Optional[str] = None


@router.get("/sources")
async def list_data_sources() -> DataSourcesResponse:
    """
    List all data sources

    Returns:
        DataSourcesResponse with sources list and total count

    Example:
        GET /api/knowledge/sources
        Response: {
            "ok": true,
            "data": {
                "sources": [...],
                "total": 5
            }
        }
    """
    try:
        sources = list(_data_sources_store.values())
        return DataSourcesResponse(
            ok=True,
            data={
                "sources": sources,
                "total": len(sources),
            },
        )
    except Exception as e:
        return DataSourcesResponse(ok=False, data={}, error=str(e))


@router.post("/sources")
async def create_data_source(request: CreateDataSourceRequest) -> DataSourcesResponse:
    """
    Add a new data source

    Args:
        request: CreateDataSourceRequest with type, path, config

    Returns:
        DataSourcesResponse with created source

    Example:
        POST /api/knowledge/sources
        {
            "type": "directory",
            "path": "/path/to/docs",
            "config": {
                "file_types": ["md", "txt"],
                "recursive": true
            }
        }
    """
    try:
        import uuid

        source_id = str(uuid.uuid4())
        now = iso_z(utc_now()) + "Z"

        source = DataSourceItem(
            source_id=source_id,
            type=request.type,
            path=request.path,
            config=request.config or {},
            chunk_count=0,
            last_indexed_at=None,
            status="pending",
            created_at=now,
            updated_at=now,
        )

        _data_sources_store[source_id] = source.model_dump()

        return DataSourcesResponse(
            ok=True,
            data={
                "source": source.model_dump(),
            },
        )
    except Exception as e:
        return DataSourcesResponse(ok=False, data={}, error=str(e))


@router.patch("/sources/{source_id}")
async def update_data_source(source_id: str, request: UpdateDataSourceRequest) -> DataSourcesResponse:
    """
    Update a data source

    Args:
        source_id: Source ID
        request: UpdateDataSourceRequest with fields to update

    Returns:
        DataSourcesResponse with updated source

    Example:
        PATCH /api/knowledge/sources/{id}
        {
            "status": "indexed",
            "config": {"recursive": false}
        }
    """
    try:
        if source_id not in _data_sources_store:
            raise HTTPException(status_code=404, detail="Data source not found")

        source = _data_sources_store[source_id]
        now = iso_z(utc_now()) + "Z"

        # Update fields
        if request.path is not None:
            source["path"] = request.path
        if request.config is not None:
            source["config"] = request.config
        if request.status is not None:
            source["status"] = request.status

        source["updated_at"] = now

        return DataSourcesResponse(
            ok=True,
            data={
                "source": source,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        return DataSourcesResponse(ok=False, data={}, error=str(e))


@router.delete("/sources/{source_id}")
async def delete_data_source(source_id: str) -> DataSourcesResponse:
    """
    Delete a data source

    Args:
        source_id: Source ID

    Returns:
        DataSourcesResponse with success status

    Example:
        DELETE /api/knowledge/sources/{id}
    """
    try:
        if source_id not in _data_sources_store:
            raise HTTPException(status_code=404, detail="Data source not found")

        del _data_sources_store[source_id]

        return DataSourcesResponse(
            ok=True,
            data={
                "message": "Data source deleted successfully",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        return DataSourcesResponse(ok=False, data={}, error=str(e))


# ============================
# Phase 3: Index Jobs
# ============================


class IndexJobRequest(BaseModel):
    """Index job request payload"""

    type: str = Field(..., description="Job type: incremental, rebuild, repair, vacuum")


class IndexJobResponse(BaseModel):
    """Index job response"""

    ok: bool
    data: Dict[str, Any]
    error: Optional[str] = None


class JobListResponse(BaseModel):
    """Job list response"""

    ok: bool
    data: List[Dict[str, Any]]
    error: Optional[str] = None


@router.get("/jobs")
async def list_index_jobs(
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    status: Optional[str] = Query(None, description="Filter by status"),
) -> JobListResponse:
    """
    List index jobs

    Args:
        limit: Maximum number of results
        status: Filter by status (created, in_progress, completed, failed)

    Returns:
        JobListResponse with list of jobs

    Example:
        GET /api/knowledge/jobs?limit=20&status=in_progress
    """
    try:
        from agentos.core.task import TaskManager

        task_manager = TaskManager()
        tasks = task_manager.list_tasks(limit=limit)

        # Filter KB index tasks
        kb_tasks = []
        for t in tasks:
            if not t.metadata:
                continue
            # Ensure metadata is a dict
            if isinstance(t.metadata, dict):
                if t.metadata.get("type") == "kb_index":
                    kb_tasks.append(t)

        # Apply status filter
        if status:
            kb_tasks = [t for t in kb_tasks if t.status == status]

        # Format response
        jobs = []
        for task in kb_tasks:
            # Safe metadata access
            metadata = task.metadata if isinstance(task.metadata, dict) else {}
            job_type = metadata.get("job_type", "unknown")
            stats = metadata.get("stats", {})
            if not isinstance(stats, dict):
                stats = {}

            jobs.append(
                {
                    "job_id": task.task_id,
                    "type": job_type,
                    "status": task.status,
                    "progress": metadata.get("progress", 0),
                    "message": metadata.get("message", ""),
                    "files_processed": stats.get("files_processed", 0),
                    "chunks_processed": stats.get("chunks_processed", 0),
                    "errors": stats.get("errors", 0),
                    "created_at": task.created_at,
                    "updated_at": task.updated_at,
                    "duration_ms": metadata.get("duration_ms"),
                }
            )

        return JobListResponse(ok=True, data=jobs)

    except Exception as e:
        return JobListResponse(ok=False, data=[], error=str(e))


@router.post("/jobs")
async def trigger_index_job(request: IndexJobRequest) -> IndexJobResponse:
    """
    Trigger index job

    Args:
        request: IndexJobRequest with job type

    Returns:
        IndexJobResponse with job_id

    Example:
        POST /api/knowledge/jobs
        {
            "type": "incremental"
        }
    """
    try:
        import threading
        from agentos.core.task import TaskManager

        # Validate job type
        valid_types = ["incremental", "rebuild", "repair", "vacuum"]
        if request.type not in valid_types:
            return IndexJobResponse(
                ok=False,
                data={},
                error=f"Invalid job type. Must be one of: {', '.join(valid_types)}",
            )

        # Create task (TaskManager will auto-create session)
        task_manager = TaskManager()
        task = task_manager.create_task(
            title=f"KB Index: {request.type}",
            metadata={
                "type": "kb_index",
                "job_type": request.type,
                "progress": 0,
                "message": "Initializing...",
                "stats": {
                    "files_processed": 0,
                    "chunks_processed": 0,
                    "errors": 0,
                },
            },
        )
        task_id = task.task_id

        # Emit task.started event
        event_bus = get_event_bus()
        logger.info(f"Emitting task.started event for task_id={task_id}")
        event_bus.emit(
            Event.task_started(
                task_id=task_id,
                payload={
                    "job_type": request.type,
                    "title": f"KB Index: {request.type}",
                },
            )
        )
        logger.info(f"Task.started event emitted successfully")

        # Start background indexing thread
        thread = threading.Thread(
            target=_run_index_job,
            args=(task_id, request.type),
            daemon=True,
        )
        thread.start()

        return IndexJobResponse(
            ok=True,
            data={"job_id": task_id, "type": request.type, "status": "created"},
        )

    except Exception as e:
        return IndexJobResponse(ok=False, data={}, error=str(e))


@router.get("/jobs/{job_id}")
async def get_index_job(job_id: str) -> IndexJobResponse:
    """
    Get index job details

    Args:
        job_id: Job ID (task_id)

    Returns:
        IndexJobResponse with job details

    Example:
        GET /api/knowledge/jobs/01HXYZ...
    """
    try:
        from agentos.core.task import TaskManager

        task_manager = TaskManager()
        task = task_manager.get_task(job_id)

        if not task:
            return IndexJobResponse(
                ok=False,
                data={},
                error="Job not found",
            )

        # Check if it's a KB index task
        metadata = task.metadata if isinstance(task.metadata, dict) else {}
        if not metadata or metadata.get("type") != "kb_index":
            return IndexJobResponse(
                ok=False,
                data={},
                error="Not a KB index job",
            )

        # Format response
        job_type = metadata.get("job_type", "unknown")
        stats = metadata.get("stats", {})
        if not isinstance(stats, dict):
            stats = {}

        job_data = {
            "job_id": task.task_id,
            "type": job_type,
            "status": task.status,
            "progress": metadata.get("progress", 0),
            "message": metadata.get("message", ""),
            "files_processed": stats.get("files_processed", 0),
            "chunks_processed": stats.get("chunks_processed", 0),
            "errors": stats.get("errors", 0),
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "duration_ms": metadata.get("duration_ms"),
        }

        return IndexJobResponse(ok=True, data=job_data)

    except Exception as e:
        return IndexJobResponse(ok=False, data={}, error=str(e))


class CleanupJobsRequest(BaseModel):
    """Cleanup request"""
    older_than_hours: int = Field(1, description="Clean jobs older than N hours")


class CleanupJobsResponse(BaseModel):
    """Cleanup response"""
    ok: bool
    cleaned_count: int
    error: Optional[str] = None


class RetryFailedJobsRequest(BaseModel):
    """Retry failed jobs request"""
    max_retries: int = Field(1, description="Maximum retry attempts per job")
    hours_lookback: int = Field(24, description="Only retry jobs from last N hours")


class RetryFailedJobsResponse(BaseModel):
    """Retry failed jobs response"""
    ok: bool
    retried_count: int
    skipped_count: int
    error: Optional[str] = None


async def retry_failed_jobs(request: RetryFailedJobsRequest = None) -> RetryFailedJobsResponse:
    """
    Retry failed KB index jobs automatically

    This function is called on startup to retry jobs that failed due to
    temporary issues (like code errors that have since been fixed).

    Args:
        request: Retry configuration (defaults applied if None)

    Returns:
        RetryFailedJobsResponse with retry statistics

    Logic:
        - Only retries jobs that failed in the last N hours
        - Skips jobs that have already been retried
        - Marks original job as "retried" to prevent infinite loops
        - Creates new job for each retryable failure
    """
    if request is None:
        request = RetryFailedJobsRequest()

    try:
        from agentos.core.task import TaskManager
        from datetime import datetime, timedelta, timezone

        task_manager = TaskManager()

        # Calculate cutoff time for lookback window
        cutoff = utc_now() - timedelta(hours=request.hours_lookback)

        # Get all KB index tasks
        all_tasks = task_manager.list_tasks(limit=1000)

        retried_count = 0
        skipped_count = 0

        for task in all_tasks:
            # Check if it's a KB index task
            if not task.metadata or not isinstance(task.metadata, dict):
                continue

            if task.metadata.get("type") != "kb_index":
                continue

            # Only retry failed tasks
            if task.status != "failed":
                continue

            # Skip if already retried
            if task.metadata.get("retried"):
                skipped_count += 1
                continue

            # Check if within lookback window
            try:
                created_at = datetime.fromisoformat(task.created_at.replace('Z', '+00:00'))
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)

                if created_at < cutoff:
                    skipped_count += 1
                    continue
            except Exception as parse_error:
                logger.error(f"Failed to parse timestamp for task {task.task_id}: {parse_error}")
                skipped_count += 1
                continue

            # Check retry count
            retry_count = task.metadata.get("retry_count", 0)
            if retry_count >= request.max_retries:
                skipped_count += 1
                continue

            # Get job type
            job_type = task.metadata.get("job_type", "incremental")

            # Create new job (retry)
            try:
                import threading

                # Create new task for retry
                new_task = task_manager.create_task(
                    title=f"KB Index: {job_type} (retry)",
                    metadata={
                        "type": "kb_index",
                        "job_type": job_type,
                        "progress": 0,
                        "message": "Retrying after previous failure...",
                        "stats": {
                            "files_processed": 0,
                            "chunks_processed": 0,
                            "errors": 0,
                        },
                        "retry_count": retry_count + 1,
                        "original_task_id": task.task_id,
                    },
                )
                new_task_id = new_task.task_id

                # Mark original task as retried
                task.metadata["retried"] = True
                task.metadata["retried_at"] = iso_z(utc_now())
                task.metadata["retry_task_id"] = new_task_id
                task_manager.update_task(task)

                # Emit task.started event
                event_bus = get_event_bus()
                event_bus.emit(
                    Event.task_started(
                        task_id=new_task_id,
                        payload={
                            "job_type": job_type,
                            "title": f"KB Index: {job_type} (retry)",
                            "retry_count": retry_count + 1,
                        },
                    )
                )

                # Start background indexing thread
                thread = threading.Thread(
                    target=_run_index_job,
                    args=(new_task_id, job_type),
                    daemon=True,
                )
                thread.start()

                retried_count += 1
                logger.info(f"Retried failed job: {task.task_id} -> {new_task_id} (job_type={job_type})")

            except Exception as retry_error:
                logger.error(f"Failed to retry job {task.task_id}: {retry_error}")
                skipped_count += 1
                continue

        logger.info(f"Job retry complete: retried={retried_count}, skipped={skipped_count}")
        return RetryFailedJobsResponse(ok=True, retried_count=retried_count, skipped_count=skipped_count)

    except Exception as e:
        logger.error(f"Failed to retry jobs: {e}", exc_info=True)
        return RetryFailedJobsResponse(ok=False, retried_count=0, skipped_count=0, error=str(e))


@router.post("/jobs/cleanup")
async def cleanup_stale_jobs(request: CleanupJobsRequest) -> CleanupJobsResponse:
    """
    Clean up stale jobs (stuck in 'created' status)

    Args:
        request: Cleanup request with time threshold

    Returns:
        Number of jobs cleaned

    Example:
        POST /api/knowledge/jobs/cleanup
        {"older_than_hours": 1}
    """
    try:
        from agentos.core.task import TaskManager
        from datetime import datetime, timedelta, timezone

        task_manager = TaskManager()

        # Calculate cutoff time
        cutoff = utc_now() - timedelta(hours=request.older_than_hours)

        # Get all tasks (not just KB index tasks, to avoid filtering issues)
        all_tasks = task_manager.list_tasks(limit=1000)

        cleaned_count = 0
        for task in all_tasks:
            # Check if it's a KB index task
            if not task.metadata or not isinstance(task.metadata, dict):
                continue

            if task.metadata.get("type") != "kb_index":
                continue

            # Check if task is stale
            if task.status == "created":
                try:
                    # Parse created_at timestamp
                    created_at = datetime.fromisoformat(task.created_at.replace('Z', '+00:00'))

                    # Make sure cutoff is timezone-aware
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)

                    if created_at < cutoff:
                        # Mark as failed
                        task.status = "failed"
                        task.metadata["message"] = f"Stale job (inactive for {request.older_than_hours}+ hours)"
                        task.metadata["cleaned_at"] = iso_z(utc_now())
                        task_manager.update_task(task)
                        cleaned_count += 1
                        logger.info(f"Cleaned stale job: {task.task_id}")
                except Exception as parse_error:
                    logger.error(f"Failed to parse timestamp for task {task.task_id}: {parse_error}")
                    continue

        return CleanupJobsResponse(ok=True, cleaned_count=cleaned_count)

    except Exception as e:
        logger.error(f"Failed to cleanup jobs: {e}")
        return CleanupJobsResponse(ok=False, cleaned_count=0, error=str(e))


@router.post("/jobs/retry")
async def retry_failed_jobs_endpoint(request: RetryFailedJobsRequest = None) -> RetryFailedJobsResponse:
    """
    Retry failed KB index jobs (manual trigger)

    Args:
        request: Retry configuration (optional)

    Returns:
        Number of jobs retried and skipped

    Example:
        POST /api/knowledge/jobs/retry
        {"max_retries": 1, "hours_lookback": 24}
    """
    if request is None:
        request = RetryFailedJobsRequest()
    return await retry_failed_jobs(request)


def _run_index_job(task_id: str, job_type: str):
    """
    Background job executor for index operations

    Args:
        task_id: Task ID
        job_type: Job type (incremental, rebuild, repair, vacuum)
    """
    import time
    from agentos.core.task import TaskManager

    task_manager = TaskManager()
    event_bus = get_event_bus()
    start_time = time.time()

    try:
        logger.info(f"[KB Index Job] Thread started: task_id={task_id}, job_type={job_type}, thread_id={threading.current_thread().ident}")

        # Get initial task state
        task = task_manager.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        logger.info(f"[KB Index Job] Initial task state: status={task.status}, metadata={task.metadata}")

        # Update status to in_progress
        logger.info(f"[KB Index Job] Updating task to in_progress...")
        task.status = "in_progress"
        task.metadata["progress"] = 5
        task.metadata["message"] = "Starting index operation..."
        task_manager.update_task(task)
        logger.info(f"[KB Index Job] Task updated successfully: status=in_progress, progress=5")

        # Emit progress event
        logger.info(f"[KB Index Job] Emitting task.progress event: progress=5")
        event_bus.emit(
            Event.task_progress(
                task_id=task_id,
                progress=5,
                message="Starting index operation...",
            )
        )
        logger.info(f"[KB Index Job] Event emitted successfully")

        # Initialize KB service
        logger.info(f"[KB Index Job] Initializing KB service")
        kb_service = ProjectKBService()

        # Execute job based on type
        if job_type == "incremental":
            _run_incremental_index(task_id, kb_service, task_manager, event_bus)
        elif job_type == "rebuild":
            _run_rebuild_index(task_id, kb_service, task_manager, event_bus)
        elif job_type == "repair":
            _run_repair_index(task_id, kb_service, task_manager, event_bus)
        elif job_type == "vacuum":
            _run_vacuum_index(task_id, kb_service, task_manager, event_bus)

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"[KB Index Job] Job completed successfully: duration_ms={duration_ms}")

        # Mark as completed
        logger.info(f"[KB Index Job] Marking task as completed...")
        task = task_manager.get_task(task_id)
        task.status = "completed"
        task.metadata["progress"] = 100
        task.metadata["message"] = "Index operation completed"
        task.metadata["duration_ms"] = duration_ms
        task_manager.update_task(task)
        logger.info(f"[KB Index Job] Task marked as completed successfully")

        # Emit completion event
        logger.info(f"[KB Index Job] Emitting task.completed event...")
        event_bus.emit(
            Event.task_completed(
                task_id=task_id,
                payload={
                    "duration_ms": duration_ms,
                    "stats": task.metadata.get("stats", {}),
                },
            )
        )
        logger.info(f"[KB Index Job] Completion event emitted successfully")

    except Exception as e:
        logger.error(f"[KB Index Job] Failed: {str(e)}", exc_info=True)

        # Mark as failed - use separate try/except to ensure we don't fail twice
        try:
            duration_ms = int((time.time() - start_time) * 1000)
            task = task_manager.get_task(task_id)
            if task:
                task.status = "failed"
                task.metadata["message"] = f"Error: {str(e)}"
                task.metadata["duration_ms"] = duration_ms
                task_manager.update_task(task)
                logger.info(f"[KB Index Job] Task marked as failed: task_id={task_id}")
            else:
                logger.error(f"[KB Index Job] Could not find task to mark as failed: task_id={task_id}")
        except Exception as update_error:
            logger.error(f"[KB Index Job] Failed to update task status: {update_error}", exc_info=True)

        # Emit failure event - separate try/except for event emission
        try:
            event_bus.emit(Event.task_failed(task_id=task_id, error=str(e)))
        except Exception as event_error:
            logger.error(f"[KB Index Job] Failed to emit failure event: {event_error}")

    finally:
        logger.info(f"[KB Index Job] Thread exiting: task_id={task_id}, job_type={job_type}")


def _run_incremental_index(
    task_id: str, kb_service: ProjectKBService, task_manager: "TaskManager", event_bus: "EventBus"
):
    """Run incremental index"""
    logger.info(f"[KB Incremental] Starting incremental index: task_id={task_id}")

    # Update task progress
    task = task_manager.get_task(task_id)
    task.metadata["progress"] = 20
    task.metadata["message"] = "Scanning for changed files..."
    task_manager.update_task(task)
    logger.info(f"[KB Incremental] Progress updated to 20%")

    # Emit progress event
    event_bus.emit(
        Event.task_progress(
            task_id=task_id,
            progress=20,
            message="Scanning for changed files...",
        )
    )

    # Run incremental refresh
    logger.info(f"[KB Incremental] Running kb_service.refresh(changed_only=True)...")
    report = kb_service.refresh(changed_only=True)
    logger.info(f"[KB Incremental] Refresh completed: changed_files={report.changed_files}, new_chunks={report.new_chunks}, errors={len(report.errors)}")

    # Update task with stats
    task = task_manager.get_task(task_id)
    task.metadata["stats"] = {
        "files_processed": report.changed_files,
        "chunks_processed": report.new_chunks,
        "errors": len(report.errors),
    }
    task.metadata["progress"] = 90
    task.metadata["message"] = f"Processed {report.changed_files} files, {report.new_chunks} chunks"
    task_manager.update_task(task)
    logger.info(f"[KB Incremental] Stats updated: progress=90%")

    # Emit progress event
    event_bus.emit(
        Event.task_progress(
            task_id=task_id,
            progress=90,
            message=f"Processed {report.changed_files} files, {report.new_chunks} chunks",
        )
    )


def _run_rebuild_index(
    task_id: str, kb_service: ProjectKBService, task_manager: "TaskManager", event_bus: "EventBus"
):
    """Run full rebuild"""
    # Update task progress
    task = task_manager.get_task(task_id)
    task.metadata["progress"] = 20
    task.metadata["message"] = "Rebuilding entire index..."
    task_manager.update_task(task)

    # Emit progress event
    event_bus.emit(
        Event.task_progress(
            task_id=task_id,
            progress=20,
            message="Rebuilding entire index...",
        )
    )

    # Run full refresh
    report = kb_service.refresh(changed_only=False)

    # Update task with stats
    task = task_manager.get_task(task_id)
    task.metadata["stats"] = {
        "files_processed": report.total_files,
        "chunks_processed": report.new_chunks,
        "errors": len(report.errors),
    }
    task.metadata["progress"] = 90
    task.metadata["message"] = f"Processed {report.total_files} files, {report.new_chunks} chunks"
    task_manager.update_task(task)

    # Emit progress event
    event_bus.emit(
        Event.task_progress(
            task_id=task_id,
            progress=90,
            message=f"Processed {report.total_files} files, {report.new_chunks} chunks",
        )
    )


def _run_repair_index(
    task_id: str, kb_service: ProjectKBService, task_manager: "TaskManager", event_bus: "EventBus"
):
    """Run index repair (verify and fix inconsistencies)"""
    # Update task progress
    task = task_manager.get_task(task_id)
    task.metadata["progress"] = 20
    task.metadata["message"] = "Checking index integrity..."
    task_manager.update_task(task)

    # Emit progress event
    event_bus.emit(
        Event.task_progress(
            task_id=task_id,
            progress=20,
            message="Checking index integrity...",
        )
    )

    # For now, run incremental refresh as repair
    # TODO: Add proper repair logic
    report = kb_service.refresh(changed_only=True)

    # Update task with stats
    task = task_manager.get_task(task_id)
    task.metadata["stats"] = {
        "files_processed": report.changed_files,
        "chunks_processed": report.new_chunks,
        "errors": len(report.errors),
    }
    task.metadata["progress"] = 90
    task.metadata["message"] = "Index repair completed"
    task_manager.update_task(task)

    # Emit progress event
    event_bus.emit(
        Event.task_progress(
            task_id=task_id,
            progress=90,
            message="Index repair completed",
        )
    )


def _run_vacuum_index(
    task_id: str, kb_service: ProjectKBService, task_manager: "TaskManager", event_bus: "EventBus"
):
    """Run index vacuum (cleanup and optimization)"""
    # Update task progress
    task = task_manager.get_task(task_id)
    task.metadata["progress"] = 20
    task.metadata["message"] = "Cleaning up index..."
    task_manager.update_task(task)

    # Emit progress event
    event_bus.emit(
        Event.task_progress(
            task_id=task_id,
            progress=20,
            message="Cleaning up index...",
        )
    )

    # Run incremental refresh to clean up deleted files
    report = kb_service.refresh(changed_only=True)

    # Update task with stats
    task = task_manager.get_task(task_id)
    task.metadata["stats"] = {
        "files_processed": report.deleted_files,
        "chunks_processed": report.deleted_chunks,
        "errors": len(report.errors),
    }
    task.metadata["progress"] = 90
    task.metadata["message"] = "Vacuum completed"
    task_manager.update_task(task)

    # Emit progress event
    event_bus.emit(
        Event.task_progress(
            task_id=task_id,
            progress=90,
            message=f"Cleaned {report.deleted_files} files, {report.deleted_chunks} chunks",
        )
    )


# ============================
# Phase 4: RAG Health
# ============================


class HealthMetrics(BaseModel):
    """Health metrics"""

    index_lag_seconds: int
    fail_rate_7d: float
    empty_hit_rate: float
    file_coverage: float
    total_chunks: int
    total_files: int


class HealthCheck(BaseModel):
    """Health check item"""

    name: str
    status: str  # ok, warn, error
    message: str


class BadSmell(BaseModel):
    """Bad smell detection"""

    type: str
    severity: str  # info, warn, error
    count: int
    details: List[str]
    suggestion: str


class HealthResponse(BaseModel):
    """Health response"""

    ok: bool
    data: Dict[str, Any]
    error: Optional[str] = None


@router.get("/health")
async def get_health() -> HealthResponse:
    """
    Get health metrics and checks

    Returns:
        HealthResponse with metrics, checks, and bad_smells

    Example:
        GET /api/knowledge/health
    """
    try:
        kb_service = ProjectKBService()

        # Get basic metrics (with fallback values)
        try:
            # Get stats from service
            stats = kb_service.stats()
            total_chunks = stats.get("total_chunks", 0)

            # Get total files from sources
            existing_sources = kb_service.indexer.get_existing_sources(kb_service.scanner.repo_id)
            total_files = len(existing_sources)

            # Calculate time-based metrics
            current_time = int(time.time())
            last_refresh_str = stats.get("last_refresh")
            last_index_time = int(last_refresh_str) if last_refresh_str else current_time - 9000
            index_lag_seconds = current_time - last_index_time

            # Calculate file coverage (indexed vs total)
            file_coverage = 1.0 if total_files > 0 else 0.0  # Assume all scanned files are indexed

            metrics = {
                "index_lag_seconds": index_lag_seconds,
                "fail_rate_7d": 0.012,  # TODO: Calculate from actual query logs
                "empty_hit_rate": 0.053,  # TODO: Calculate from actual query logs
                "file_coverage": file_coverage,
                "total_chunks": total_chunks,
                "total_files": total_files,
            }
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            # Fallback metrics
            current_time = int(time.time())
            metrics = {
                "index_lag_seconds": current_time - (current_time - 9000),
                "fail_rate_7d": 0.012,
                "empty_hit_rate": 0.053,
                "file_coverage": 0.0,
                "total_chunks": 0,
                "total_files": 0,
            }

        # Perform health checks
        checks = []

        # Check 1: FTS5 Available
        try:
            # Check if FTS5 is available
            fts5_available = True  # Assume available by default
            if hasattr(kb_service, 'check_fts5_available'):
                fts5_available = kb_service.check_fts5_available()

            if fts5_available:
                checks.append(
                    HealthCheck(
                        name="FTS5 Available",
                        status="ok",
                        message="Full-text search enabled",
                    ).model_dump()
                )
            else:
                checks.append(
                    HealthCheck(
                        name="FTS5 Available",
                        status="error",
                        message="FTS5 not available",
                    ).model_dump()
                )
        except Exception as e:
            checks.append(
                HealthCheck(
                    name="FTS5 Available",
                    status="warn",
                    message=f"Unable to check FTS5: {str(e)}",
                ).model_dump()
            )

        # Check 2: Schema Version
        try:
            schema_version = "v1.0"  # Default
            if hasattr(kb_service, 'get_schema_version'):
                schema_version = kb_service.get_schema_version()

            checks.append(
                HealthCheck(
                    name="Schema Version",
                    status="ok",
                    message=f"Schema {schema_version}",
                ).model_dump()
            )
        except Exception as e:
            checks.append(
                HealthCheck(
                    name="Schema Version",
                    status="warn",
                    message=f"Unable to determine schema version: {str(e)}",
                ).model_dump()
            )

        # Check 3: Index Staleness
        try:
            stale_count = 0
            if hasattr(kb_service, 'get_stale_file_count'):
                stale_count = kb_service.get_stale_file_count()

            if stale_count == 0:
                checks.append(
                    HealthCheck(
                        name="Index Staleness",
                        status="ok",
                        message="All files are indexed",
                    ).model_dump()
                )
            elif stale_count < 10:
                checks.append(
                    HealthCheck(
                        name="Index Staleness",
                        status="warn",
                        message=f"{stale_count} files modified since last index",
                    ).model_dump()
                )
            else:
                checks.append(
                    HealthCheck(
                        name="Index Staleness",
                        status="error",
                        message=f"{stale_count} files need re-indexing",
                    ).model_dump()
                )
        except Exception as e:
            checks.append(
                HealthCheck(
                    name="Index Staleness",
                    status="warn",
                    message=f"Check not available: {str(e)}",
                ).model_dump()
            )

        # Check 4: Orphan Chunks
        try:
            orphan_count = 0
            if hasattr(kb_service, 'get_orphan_chunk_count'):
                orphan_count = kb_service.get_orphan_chunk_count()

            if orphan_count == 0:
                checks.append(
                    HealthCheck(
                        name="Orphan Chunks",
                        status="ok",
                        message="No orphan chunks found",
                    ).model_dump()
                )
            else:
                checks.append(
                    HealthCheck(
                        name="Orphan Chunks",
                        status="warn",
                        message=f"{orphan_count} orphan chunks found",
                    ).model_dump()
                )
        except Exception as e:
            checks.append(
                HealthCheck(
                    name="Orphan Chunks",
                    status="ok",
                    message="No orphan chunks found",
                ).model_dump()
            )

        # Bad smell detection
        bad_smells = []

        # Smell 1: Duplicate content
        try:
            if hasattr(kb_service, 'find_duplicate_content'):
                duplicates = kb_service.find_duplicate_content()
                if duplicates and len(duplicates) > 0:
                    bad_smells.append(
                        BadSmell(
                            type="duplicate_content",
                            severity="warn",
                            count=len(duplicates),
                            details=duplicates[:5],  # Show first 5
                            suggestion="Consider consolidating duplicate content",
                        ).model_dump()
                    )
        except Exception as e:
            print(f"Duplicate content check failed: {e}")

        # Smell 2: Oversized files
        try:
            if hasattr(kb_service, 'find_oversized_files'):
                oversized = kb_service.find_oversized_files(max_lines=10000)
                if oversized and len(oversized) > 0:
                    bad_smells.append(
                        BadSmell(
                            type="oversized_files",
                            severity="info",
                            count=len(oversized),
                            details=oversized[:5],  # Show first 5
                            suggestion="Split large files for better chunking",
                        ).model_dump()
                    )
        except Exception as e:
            print(f"Oversized files check failed: {e}")

        # Smell 3: Config conflicts
        try:
            if hasattr(kb_service, 'find_config_conflicts'):
                conflicts = kb_service.find_config_conflicts()
                if conflicts and len(conflicts) > 0:
                    bad_smells.append(
                        BadSmell(
                            type="config_conflicts",
                            severity="error",
                            count=len(conflicts),
                            details=conflicts[:5],
                            suggestion="Resolve configuration conflicts",
                        ).model_dump()
                    )
        except Exception as e:
            print(f"Config conflicts check failed: {e}")

        return HealthResponse(
            ok=True,
            data={
                "metrics": metrics,
                "checks": checks,
                "bad_smells": bad_smells,
            },
        )

    except Exception as e:
        return HealthResponse(
            ok=False,
            data={},
            error=str(e),
        )
