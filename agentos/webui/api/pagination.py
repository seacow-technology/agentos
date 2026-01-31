"""
API Pagination Models - Unified pagination for M-02 API Contract Consistency

This module provides standardized pagination models and utilities to ensure
consistent pagination behavior across all list endpoints.

Created for BACKLOG M-02: Pagination Parameter Consistency
"""

from typing import Generic, TypeVar, List, Any, Dict
from pydantic import BaseModel, Field


# Generic type for paginated items
T = TypeVar('T')


class PaginationParams(BaseModel):
    """
    Standardized pagination parameters

    Use this as a query parameter model for all list endpoints to ensure
    consistent pagination behavior.

    Example:
        @router.get("/api/tasks")
        async def list_tasks(
            pagination: PaginationParams = Depends()
        ):
            # Use pagination.limit and pagination.offset
            pass
    """

    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of items to return (1-1000)"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of items to skip (0 or greater)"
    )

    def apply_to_query(self, items: List[T]) -> List[T]:
        """
        Apply pagination to a list of items

        Args:
            items: Full list of items

        Returns:
            Paginated slice of items
        """
        return items[self.offset:self.offset + self.limit]

    def get_sql_clause(self) -> tuple[int, int]:
        """
        Get SQL LIMIT/OFFSET values

        Returns:
            Tuple of (limit, offset) for use in SQL queries
        """
        return (self.limit, self.offset)


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standardized paginated response wrapper

    Use this as the response model for all list endpoints to ensure
    consistent pagination metadata.

    Example:
        @router.get("/api/tasks", response_model=PaginatedResponse[TaskSummary])
        async def list_tasks():
            items = get_tasks()
            total = get_total_count()
            return PaginatedResponse(
                items=items,
                total=total,
                limit=100,
                offset=0
            )
    """

    ok: bool = Field(default=True, description="Operation success status")
    items: List[T] = Field(description="List of items in current page")
    total: int = Field(description="Total number of items across all pages")
    limit: int = Field(description="Maximum items per page")
    offset: int = Field(description="Number of items skipped")
    has_more: bool = Field(description="Whether more items exist beyond current page")

    class Config:
        json_schema_extra = {
            "example": {
                "ok": True,
                "items": [{"id": "1", "name": "Item 1"}],
                "total": 150,
                "limit": 100,
                "offset": 0,
                "has_more": True
            }
        }

    def __init__(self, items: List[T], total: int, limit: int, offset: int, **kwargs):
        """
        Initialize paginated response with automatic has_more calculation

        Args:
            items: List of items in current page
            total: Total number of items
            limit: Maximum items per page
            offset: Number of items skipped
        """
        has_more = (offset + len(items)) < total
        super().__init__(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
            **kwargs
        )


class PaginationMeta(BaseModel):
    """
    Pagination metadata (alternative format)

    Some APIs may prefer separate data and meta structure.
    """

    total: int = Field(description="Total number of items")
    limit: int = Field(description="Maximum items per page")
    offset: int = Field(description="Number of items skipped")
    page: int = Field(description="Current page number (1-indexed)")
    total_pages: int = Field(description="Total number of pages")
    has_previous: bool = Field(description="Whether previous page exists")
    has_next: bool = Field(description="Whether next page exists")

    @staticmethod
    def from_params(total: int, limit: int, offset: int) -> "PaginationMeta":
        """
        Create pagination metadata from parameters

        Args:
            total: Total number of items
            limit: Maximum items per page
            offset: Number of items skipped

        Returns:
            PaginationMeta instance
        """
        page = (offset // limit) + 1
        total_pages = (total + limit - 1) // limit if limit > 0 else 0
        has_previous = offset > 0
        has_next = (offset + limit) < total

        return PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            page=page,
            total_pages=total_pages,
            has_previous=has_previous,
            has_next=has_next
        )


class PaginatedResponseWithMeta(BaseModel, Generic[T]):
    """
    Paginated response with separate metadata

    Alternative format that separates data and pagination metadata.

    Example:
        {
            "ok": true,
            "data": [...],
            "pagination": {
                "total": 150,
                "limit": 100,
                "offset": 0,
                "page": 1,
                "total_pages": 2,
                "has_previous": false,
                "has_next": true
            }
        }
    """

    ok: bool = Field(default=True, description="Operation success status")
    data: List[T] = Field(description="List of items")
    pagination: PaginationMeta = Field(description="Pagination metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "ok": True,
                "data": [{"id": "1", "name": "Item 1"}],
                "pagination": {
                    "total": 150,
                    "limit": 100,
                    "offset": 0,
                    "page": 1,
                    "total_pages": 2,
                    "has_previous": False,
                    "has_next": True
                }
            }
        }


# Utility functions

def paginate_list(
    items: List[T],
    total: int,
    pagination: PaginationParams
) -> PaginatedResponse[T]:
    """
    Helper function to create paginated response from a list

    Args:
        items: List of items (already sliced)
        total: Total count before pagination
        pagination: Pagination parameters

    Returns:
        PaginatedResponse instance
    """
    return PaginatedResponse(
        items=items,
        total=total,
        limit=pagination.limit,
        offset=pagination.offset
    )


def paginate_with_meta(
    items: List[T],
    total: int,
    pagination: PaginationParams
) -> PaginatedResponseWithMeta[T]:
    """
    Helper function to create paginated response with metadata

    Args:
        items: List of items (already sliced)
        total: Total count before pagination
        pagination: Pagination parameters

    Returns:
        PaginatedResponseWithMeta instance
    """
    meta = PaginationMeta.from_params(
        total=total,
        limit=pagination.limit,
        offset=pagination.offset
    )

    return PaginatedResponseWithMeta(
        data=items,
        pagination=meta
    )
