from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal

TeamsConnectionStatus = Literal[
    "Disconnected",
    "Authorized",
    "AppUploaded",
    "Installed",
    "InstalledButUnverified",
    "Verified",
    "Blocked",
    "PartiallyConnected",
]
DeploymentStrategy = Literal["shared", "dedicated"]


@dataclass
class TeamsOrganizationConnection:
    tenant_id: str
    display_name: str = ""
    status: TeamsConnectionStatus = "Disconnected"
    teams_app_id: str = ""
    bot_id: str = ""
    deployment_strategy: DeploymentStrategy = "shared"
    token_ref: str = ""
    token_expires_at_ms: int = 0
    scopes: str = ""
    last_evidence_path: str = ""
    metadata_json: Dict[str, Any] = field(default_factory=dict)
    created_at_ms: int = 0
    updated_at_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "display_name": self.display_name,
            "status": self.status,
            "teams_app_id": self.teams_app_id,
            "bot_id": self.bot_id,
            "deployment_strategy": self.deployment_strategy,
            "token_ref": self.token_ref,
            "token_expires_at_ms": self.token_expires_at_ms,
            "scopes": self.scopes,
            "last_evidence_path": self.last_evidence_path,
            "metadata": dict(self.metadata_json or {}),
            "created_at_ms": self.created_at_ms,
            "updated_at_ms": self.updated_at_ms,
        }
