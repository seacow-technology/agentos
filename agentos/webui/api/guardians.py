"""
Guardians API - Guardian assignments and verdicts

Endpoints for querying Guardian verification workflow.

GET /api/guardians/tasks/{task_id}/assignments - List task assignments
GET /api/guardians/assignments/{assignment_id} - Get assignment details
GET /api/guardians/tasks/{task_id}/verdicts - List task verdicts
GET /api/guardians/verdicts/{verdict_id} - Get verdict details
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import json
import sqlite3

from agentos.store import get_db


router = APIRouter(prefix="/api/guardians", tags=["guardians"])


# Response Models
class GuardianAssignmentResponse(BaseModel):
    """Guardian assignment response"""
    assignment_id: str
    task_id: str
    guardian_code: str
    created_at: str
    reason: Dict[str, Any]
    status: str


class GuardianVerdictResponse(BaseModel):
    """Guardian verdict response"""
    verdict_id: str
    assignment_id: str
    task_id: str
    guardian_code: str
    status: str
    flags: List[Dict[str, Any]]
    evidence: Dict[str, Any]
    recommendations: List[str]
    created_at: str


class AssignmentsListResponse(BaseModel):
    """List of assignments response"""
    task_id: str
    assignments: List[GuardianAssignmentResponse]
    count: int


class VerdictsListResponse(BaseModel):
    """List of verdicts response"""
    task_id: str
    verdicts: List[GuardianVerdictResponse]
    count: int


@router.get("/tasks/{task_id}/assignments", response_model=AssignmentsListResponse)
async def list_task_assignments(
    task_id: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of assignments to return")
) -> AssignmentsListResponse:
    """
    List all Guardian assignments for a task

    Returns all assignments ordered by creation time (newest first).

    Args:
        task_id: Task ID
        limit: Maximum number of results (1-200, default 50)

    Returns:
        List of Guardian assignments

    Raises:
        HTTPException: 404 if task not found

    Example:
        ```bash
        curl http://localhost:8080/api/guardians/tasks/task-123/assignments
        ```
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Check if task exists
        cursor.execute("SELECT task_id FROM tasks WHERE task_id = ?", (task_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

        # Get assignments
        cursor.execute(
            """
            SELECT assignment_id, task_id, guardian_code, created_at, reason_json, status
            FROM guardian_assignments
            WHERE task_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (task_id, limit),
        )

        rows = cursor.fetchall()
        assignments = []

        for row in rows:
            try:
                reason = json.loads(row[4]) if row[4] else {}
            except json.JSONDecodeError:
                reason = {}

            assignments.append(
                GuardianAssignmentResponse(
                    assignment_id=row[0],
                    task_id=row[1],
                    guardian_code=row[2],
                    created_at=row[3],
                    reason=reason,
                    status=row[5],
                )
            )

        return AssignmentsListResponse(
            task_id=task_id,
            assignments=assignments,
            count=len(assignments)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        # Do NOT close: get_db() returns shared thread-local connection


@router.get("/assignments/{assignment_id}", response_model=GuardianAssignmentResponse)
async def get_assignment(assignment_id: str) -> GuardianAssignmentResponse:
    """
    Get Guardian assignment details

    Args:
        assignment_id: Assignment ID

    Returns:
        Guardian assignment details

    Raises:
        HTTPException: 404 if assignment not found

    Example:
        ```bash
        curl http://localhost:8080/api/guardians/assignments/assignment-123
        ```
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT assignment_id, task_id, guardian_code, created_at, reason_json, status
            FROM guardian_assignments
            WHERE assignment_id = ?
            """,
            (assignment_id,),
        )

        row = cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Assignment not found: {assignment_id}"
            )

        try:
            reason = json.loads(row[4]) if row[4] else {}
        except json.JSONDecodeError:
            reason = {}

        return GuardianAssignmentResponse(
            assignment_id=row[0],
            task_id=row[1],
            guardian_code=row[2],
            created_at=row[3],
            reason=reason,
            status=row[5],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        # Do NOT close: get_db() returns shared thread-local connection


@router.get("/tasks/{task_id}/verdicts", response_model=VerdictsListResponse)
async def list_task_verdicts(
    task_id: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of verdicts to return")
) -> VerdictsListResponse:
    """
    List all Guardian verdicts for a task

    Returns all verdicts ordered by creation time (newest first).

    Args:
        task_id: Task ID
        limit: Maximum number of results (1-200, default 50)

    Returns:
        List of Guardian verdicts

    Raises:
        HTTPException: 404 if task not found

    Example:
        ```bash
        curl http://localhost:8080/api/guardians/tasks/task-123/verdicts
        ```
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Check if task exists
        cursor.execute("SELECT task_id FROM tasks WHERE task_id = ?", (task_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

        # Get verdicts
        cursor.execute(
            """
            SELECT verdict_id, assignment_id, task_id, guardian_code, status, created_at, verdict_json
            FROM guardian_verdicts
            WHERE task_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (task_id, limit),
        )

        rows = cursor.fetchall()
        verdicts = []

        for row in rows:
            try:
                verdict_data = json.loads(row[6]) if row[6] else {}
                flags = verdict_data.get("flags", [])
                evidence = verdict_data.get("evidence", {})
                recommendations = verdict_data.get("recommendations", [])
            except json.JSONDecodeError:
                flags = []
                evidence = {}
                recommendations = []

            verdicts.append(
                GuardianVerdictResponse(
                    verdict_id=row[0],
                    assignment_id=row[1],
                    task_id=row[2],
                    guardian_code=row[3],
                    status=row[4],
                    created_at=row[5],
                    flags=flags,
                    evidence=evidence,
                    recommendations=recommendations,
                )
            )

        return VerdictsListResponse(
            task_id=task_id,
            verdicts=verdicts,
            count=len(verdicts)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        # Do NOT close: get_db() returns shared thread-local connection


@router.get("/verdicts/{verdict_id}", response_model=GuardianVerdictResponse)
async def get_verdict(verdict_id: str) -> GuardianVerdictResponse:
    """
    Get Guardian verdict details

    Args:
        verdict_id: Verdict ID

    Returns:
        Complete Guardian verdict

    Raises:
        HTTPException: 404 if verdict not found

    Example:
        ```bash
        curl http://localhost:8080/api/guardians/verdicts/verdict-123
        ```
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT verdict_id, assignment_id, task_id, guardian_code, status, created_at, verdict_json
            FROM guardian_verdicts
            WHERE verdict_id = ?
            """,
            (verdict_id,),
        )

        row = cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Verdict not found: {verdict_id}"
            )

        try:
            verdict_data = json.loads(row[6]) if row[6] else {}
            flags = verdict_data.get("flags", [])
            evidence = verdict_data.get("evidence", {})
            recommendations = verdict_data.get("recommendations", [])
        except json.JSONDecodeError:
            flags = []
            evidence = {}
            recommendations = []

        return GuardianVerdictResponse(
            verdict_id=row[0],
            assignment_id=row[1],
            task_id=row[2],
            guardian_code=row[3],
            status=row[4],
            created_at=row[5],
            flags=flags,
            evidence=evidence,
            recommendations=recommendations,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        # Do NOT close: get_db() returns shared thread-local connection
