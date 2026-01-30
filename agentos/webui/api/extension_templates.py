"""
Extension Template API - Generate and download extension templates

Provides API endpoints for:
- List available template types
- Generate extension template with wizard inputs
- Download generated template as ZIP

Part of Task #13: Extension Template Wizard and Download
"""

import logging
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from agentos.core.extensions.template_generator import (
    ExtensionTemplateGenerator,
    create_template
)
from agentos.webui.api.contracts import ReasonCode

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# Request/Response Models
# ============================================

class TemplateType(BaseModel):
    """Template type information"""
    id: str
    name: str
    description: str
    icon: str


class CapabilityInput(BaseModel):
    """Capability configuration input"""
    type: str = Field(description="Capability type (slash_command, tool, agent, workflow)")
    name: str = Field(description="Capability name (e.g., '/mycommand')")
    description: str = Field(description="Capability description")
    config: Dict[str, Any] = Field(default_factory=dict, description="Additional configuration")


class GenerateTemplateRequest(BaseModel):
    """Request to generate extension template"""
    extension_id: str = Field(description="Extension ID (e.g., 'tools.myext')")
    extension_name: str = Field(description="Human-readable extension name")
    description: str = Field(description="Extension description")
    author: str = Field(description="Extension author")
    capabilities: List[CapabilityInput] = Field(description="List of capabilities")
    permissions: List[str] = Field(default_factory=list, description="Required permissions")

    @field_validator('extension_id')
    @classmethod
    def validate_extension_id(cls, v: str) -> str:
        """Validate extension ID format"""
        import re
        pattern = r'^[a-z0-9]+\.[a-z0-9]+$'
        if not re.match(pattern, v):
            raise ValueError(
                "Extension ID must be in format 'namespace.name' "
                "(lowercase alphanumeric only, e.g., 'tools.myext')"
            )
        return v

    @field_validator('extension_name')
    @classmethod
    def validate_extension_name(cls, v: str) -> str:
        """Validate extension name"""
        if not v or not v.strip():
            raise ValueError("Extension name cannot be empty")
        return v.strip()

    @field_validator('author')
    @classmethod
    def validate_author(cls, v: str) -> str:
        """Validate author"""
        if not v or not v.strip():
            raise ValueError("Author cannot be empty")
        return v.strip()

    @field_validator('capabilities')
    @classmethod
    def validate_capabilities(cls, v: List[CapabilityInput]) -> List[CapabilityInput]:
        """Validate capabilities"""
        if not v or len(v) == 0:
            raise ValueError("At least one capability is required")
        return v


class TemplateTypesResponse(BaseModel):
    """Response with available template types"""
    template_types: List[TemplateType]


# ============================================
# API Endpoints
# ============================================

@router.get("/api/extensions/templates", response_model=TemplateTypesResponse)
async def list_template_types():
    """
    List available extension template types

    Returns a list of template types that can be used as starting points.
    Currently returns a single "basic" template type.

    Returns:
    {
        "template_types": [
            {
                "id": "basic",
                "name": "Basic Extension",
                "description": "A simple extension with custom capabilities",
                "icon": "inventory_2"
            }
        ]
    }
    """
    template_types = [
        TemplateType(
            id="basic",
            name="Basic Extension",
            description="A simple extension with custom capabilities. Perfect for getting started with AgentOS extension development.",
            icon="inventory_2"
        ),
        TemplateType(
            id="slash_command",
            name="Slash Command Extension",
            description="Extension focused on slash commands for chat interface integration.",
            icon="bolt"
        ),
        TemplateType(
            id="tool",
            name="Tool Extension",
            description="Extension providing tools for agent task execution.",
            icon="build"
        ),
        TemplateType(
            id="agent",
            name="Agent Extension",
            description="Extension providing custom agent implementations.",
            icon="smart_toy"
        )
    ]

    return TemplateTypesResponse(template_types=template_types)


@router.post("/api/extensions/templates/generate")
async def generate_template(request: GenerateTemplateRequest):
    """
    Generate and download extension template as ZIP

    Takes wizard inputs and generates a complete extension template package
    with manifest.json, handlers.py, README.md, and other necessary files.

    Request Body:
    {
        "extension_id": "tools.myext",
        "extension_name": "My Extension",
        "description": "My custom extension",
        "author": "Your Name",
        "capabilities": [
            {
                "type": "slash_command",
                "name": "/mycommand",
                "description": "My custom command",
                "config": {}
            }
        ],
        "permissions": ["network", "exec"]
    }

    Returns:
    ZIP file download with extension template
    """
    try:
        logger.info(f"Generating extension template for: {request.extension_id}")

        # Convert Pydantic models to dicts for template generator
        capabilities = [
            {
                "type": cap.type,
                "name": cap.name,
                "description": cap.description,
                "config": cap.config
            }
            for cap in request.capabilities
        ]

        # Generate template ZIP
        generator = ExtensionTemplateGenerator()
        zip_content = generator.generate_template(
            extension_id=request.extension_id,
            extension_name=request.extension_name,
            description=request.description,
            author=request.author,
            capabilities=capabilities,
            permissions=request.permissions
        )

        # Return as downloadable file
        filename = f"{request.extension_id}.zip"

        return Response(
            content=zip_content,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except ValueError as e:
        logger.error(f"Validation error generating template: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "data": None,
                "error": f"Invalid input: {str(e)}",
                "hint": "Check your input values and try again",
                "reason_code": ReasonCode.INVALID_INPUT
            }
        )
    except Exception as e:
        logger.error(f"Failed to generate extension template: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "data": None,
                "error": f"Failed to generate template: {str(e)}",
                "hint": "Check server logs for details",
                "reason_code": ReasonCode.INTERNAL_ERROR
            }
        )


@router.get("/api/extensions/templates/permissions")
async def list_available_permissions():
    """
    List available permission types for extensions

    Returns a list of all available permission types that can be
    requested by extensions.

    Returns:
    {
        "permissions": [
            {
                "id": "network",
                "name": "Network Access",
                "description": "Allow extension to make network requests"
            },
            ...
        ]
    }
    """
    permissions = [
        {
            "id": "network",
            "name": "Network Access",
            "description": "Allow extension to make HTTP/HTTPS requests to external services"
        },
        {
            "id": "exec",
            "name": "Execute Commands",
            "description": "Allow extension to execute system commands and external programs"
        },
        {
            "id": "filesystem.read",
            "name": "Filesystem Read",
            "description": "Allow extension to read files from the filesystem"
        },
        {
            "id": "filesystem.write",
            "name": "Filesystem Write",
            "description": "Allow extension to write files to the filesystem"
        },
        {
            "id": "database",
            "name": "Database Access",
            "description": "Allow extension to access AgentOS database"
        },
        {
            "id": "secrets",
            "name": "Secrets Access",
            "description": "Allow extension to access secrets and credentials"
        },
        {
            "id": "sessions",
            "name": "Session Access",
            "description": "Allow extension to access and modify chat sessions"
        },
        {
            "id": "tasks",
            "name": "Task Management",
            "description": "Allow extension to create and manage tasks"
        }
    ]

    return {"permissions": permissions}


@router.get("/api/extensions/templates/capability-types")
async def list_capability_types():
    """
    List available capability types for extensions

    Returns a list of all capability types that extensions can provide.

    Returns:
    {
        "capability_types": [
            {
                "id": "slash_command",
                "name": "Slash Command",
                "description": "Chat interface command (e.g., /mycommand)"
            },
            ...
        ]
    }
    """
    capability_types = [
        {
            "id": "slash_command",
            "name": "Slash Command",
            "description": "Command that can be invoked in the chat interface (e.g., /mycommand)",
            "example": "/mycommand"
        },
        {
            "id": "tool",
            "name": "Tool",
            "description": "Tool that can be used by agents during task execution",
            "example": "web_search"
        },
        {
            "id": "agent",
            "name": "Agent",
            "description": "Custom agent implementation for specialized tasks",
            "example": "code_reviewer"
        },
        {
            "id": "workflow",
            "name": "Workflow",
            "description": "Pre-defined workflow for complex task orchestration",
            "example": "data_pipeline"
        }
    ]

    return {"capability_types": capability_types}
