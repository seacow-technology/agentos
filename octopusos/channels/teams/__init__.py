"""Teams integration package (Phase B local multi-organization support)."""

from octopusos.channels.teams.models import (
    DeploymentStrategy,
    TeamsConnectionStatus,
    TeamsOrganizationConnection,
)
from octopusos.channels.teams.store import TeamsConnectionStore

__all__ = [
    "DeploymentStrategy",
    "TeamsConnectionStatus",
    "TeamsOrganizationConnection",
    "TeamsConnectionStore",
]
