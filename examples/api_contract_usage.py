#!/usr/bin/env python3
"""
API Contract Usage Examples

Demonstrates how to use the unified API contract in AgentOS WebUI.

Created for Agent-API-Contract demonstration
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any

# Import the standard contracts
from agentos.webui.api.contracts import (
    success,
    error,
    not_found_error,
    validation_error,
    bad_state_error,
    validate_admin_token,
    validate_user_token,
    ReasonCode,
)


# ============================================
# Example 1: Basic CRUD Endpoint
# ============================================

router = APIRouter(prefix="/api/example", tags=["example"])


@router.get("/resources/{resource_id}")
async def get_resource(resource_id: str) -> Dict[str, Any]:
    """
    Example GET endpoint with standard error handling

    Returns standard API response format:
    - Success: {"ok": true, "data": {...}}
    - Not Found: {"ok": false, "error": "...", "reason_code": "NOT_FOUND"}
    """
    # Validate input
    if not resource_id or len(resource_id) < 5:
        raise validation_error(
            "Invalid resource_id format",
            hint="resource_id must be at least 5 characters",
            details={"resource_id": resource_id}
        )

    # Simulate database lookup
    # In real code, use: resource = db.get_resource(resource_id)
    resource = None  # Simulate not found

    if not resource:
        raise not_found_error("Resource", resource_id)

    # Return success
    return success({
        "resource_id": resource_id,
        "name": "Example Resource",
        "status": "active",
    })


@router.post("/resources")
async def create_resource(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example POST endpoint with validation

    Returns standard API response format with created resource
    """
    # Validate required fields
    required_fields = ["name", "type"]
    missing_fields = [f for f in required_fields if f not in data]

    if missing_fields:
        raise validation_error(
            f"Missing required fields: {', '.join(missing_fields)}",
            hint="Include all required fields in the request body",
            details={"missing_fields": missing_fields}
        )

    # Create resource
    new_resource = {
        "resource_id": "res-123",
        "name": data["name"],
        "type": data["type"],
        "status": "created",
    }

    return success(new_resource)


# ============================================
# Example 2: State Machine Validation
# ============================================

@router.post("/resources/{resource_id}/activate")
async def activate_resource(resource_id: str) -> Dict[str, Any]:
    """
    Example state transition with validation

    Demonstrates BAD_STATE error for invalid transitions
    """
    # Get current resource state
    # In real code: resource = db.get_resource(resource_id)
    current_state = "archived"  # Simulate invalid state

    # Validate state transition
    allowed_states = ["created", "inactive"]
    if current_state not in allowed_states:
        raise bad_state_error(
            f"Cannot activate resource in {current_state} state",
            hint=f"Resource must be in one of: {', '.join(allowed_states)}",
            details={
                "current_state": current_state,
                "allowed_states": allowed_states,
            }
        )

    # Perform activation
    return success({
        "resource_id": resource_id,
        "status": "active",
        "previous_state": current_state,
    })


# ============================================
# Example 3: Protected Endpoint (Admin Only)
# ============================================

@router.delete("/resources/{resource_id}")
async def delete_resource(
    resource_id: str,
    _: bool = Depends(validate_admin_token)
) -> Dict[str, Any]:
    """
    Example protected endpoint requiring admin token

    Usage:
        curl -H "X-Admin-Token: secret" http://localhost:8000/api/example/resources/123

    Requires:
        export AGENTOS_ADMIN_TOKEN=secret
    """
    # Admin token validated by dependency
    # Proceed with deletion

    return success({
        "resource_id": resource_id,
        "status": "deleted",
        "message": "Resource deleted successfully"
    })


# ============================================
# Example 4: User-Scoped Endpoint
# ============================================

@router.post("/resources/{resource_id}/claim")
async def claim_resource(
    resource_id: str,
    user_id: str = Depends(validate_user_token)
) -> Dict[str, Any]:
    """
    Example user-scoped endpoint

    Usage:
        curl -H "X-User-Token: user-123" http://localhost:8000/api/example/resources/123/claim

    User authentication can be enabled with:
        export AGENTOS_REQUIRE_USER_AUTH=true
    """
    return success({
        "resource_id": resource_id,
        "claimed_by": user_id,
        "status": "claimed",
    })


# ============================================
# Example 5: Bulk Operations with Partial Success
# ============================================

@router.post("/resources/bulk-update")
async def bulk_update_resources(
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Example bulk operation with partial success reporting

    Returns both successful and failed items
    """
    resource_ids = data.get("resource_ids", [])

    if not resource_ids:
        raise validation_error(
            "resource_ids cannot be empty",
            hint="Provide at least one resource_id to update"
        )

    # Process each resource
    results = []
    errors = []

    for rid in resource_ids:
        try:
            # Simulate update
            if len(rid) < 5:
                raise ValueError("Invalid resource_id format")

            results.append({
                "resource_id": rid,
                "status": "updated",
            })
        except Exception as e:
            errors.append({
                "resource_id": rid,
                "error": str(e),
            })

    # Return partial success with details
    return success({
        "total": len(resource_ids),
        "succeeded": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    })


# ============================================
# Example 6: Custom Error Response
# ============================================

@router.get("/resources/{resource_id}/check")
async def check_resource(resource_id: str) -> Dict[str, Any]:
    """
    Example with custom error handling

    Demonstrates when to use error_response vs raising error
    """
    from agentos.webui.api.contracts import error_response

    # Validate resource
    is_valid = len(resource_id) >= 5

    if not is_valid:
        # Return error without raising exception (useful in batch operations)
        return error_response(
            "Resource validation failed",
            reason_code=ReasonCode.INVALID_INPUT,
            hint="Check the resource_id format",
        )

    # Return success
    return success({
        "resource_id": resource_id,
        "valid": True,
    })


# ============================================
# Testing the Examples
# ============================================

def demo_api_responses():
    """
    Demonstrate API response formats

    Run this to see example responses without starting the server
    """
    print("=" * 60)
    print("API Contract Response Examples")
    print("=" * 60)
    print()

    # Success response
    print("1. Success Response:")
    success_resp = success({"task_id": "123", "status": "running"})
    print(success_resp)
    print()

    # Not found error
    print("2. Not Found Error:")
    try:
        raise not_found_error("Task", "123")
    except Exception as e:
        print(f"Status Code: {e.status_code}")
        print(f"Detail: {e.detail}")
    print()

    # Validation error
    print("3. Validation Error:")
    try:
        raise validation_error(
            "Invalid task_id format",
            hint="task_id must be a valid ULID",
            details={"task_id": "short"}
        )
    except Exception as e:
        print(f"Status Code: {e.status_code}")
        print(f"Detail: {e.detail}")
    print()

    # Bad state error
    print("4. Bad State Error:")
    try:
        raise bad_state_error(
            "Cannot approve task in RUNNING state",
            hint="Task must be in DRAFT or QUEUED state",
            details={"current_state": "RUNNING"}
        )
    except Exception as e:
        print(f"Status Code: {e.status_code}")
        print(f"Detail: {e.detail}")
    print()


if __name__ == "__main__":
    demo_api_responses()
