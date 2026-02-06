"""
Standard Reason Codes for AgentOS

Unified reason codes across providers, context, and self-check.
Each code has a standard hint for user guidance.

v0.3.2 Closeout - Status explanation standardization
"""

from enum import Enum
from typing import Dict


class ReasonCode(str, Enum):
    """Standard reason codes for status explanation"""

    # Configuration issues
    NO_CONFIG = "NO_CONFIG"
    INVALID_CONFIG = "INVALID_CONFIG"

    # Network/connectivity issues
    CONN_REFUSED = "CONN_REFUSED"
    TIMEOUT = "TIMEOUT"
    DNS_FAILURE = "DNS_FAILURE"

    # HTTP error codes
    HTTP_401 = "HTTP_401"
    HTTP_403 = "HTTP_403"
    HTTP_404 = "HTTP_404"
    HTTP_429 = "HTTP_429"
    HTTP_5XX = "HTTP_5XX"

    # Response/parsing issues
    INVALID_RESPONSE = "INVALID_RESPONSE"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"

    # Security/permissions
    PERMISSION_NOT_600 = "PERMISSION_NOT_600"
    PERMISSION_DENIED = "PERMISSION_DENIED"

    # State/lifecycle issues
    STALE_REFRESH = "STALE_REFRESH"
    REFRESH_IN_PROGRESS = "REFRESH_IN_PROGRESS"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"

    # Service-specific
    CLI_NOT_FOUND = "CLI_NOT_FOUND"
    SERVICE_NOT_RUNNING = "SERVICE_NOT_RUNNING"

    # Provider fingerprint issues (Sprint B+)
    PORT_OCCUPIED_BY_OTHER_PROVIDER = "PORT_OCCUPIED_BY_OTHER_PROVIDER"
    FINGERPRINT_MISMATCH = "FINGERPRINT_MISMATCH"
    SERVICE_CONFLICT = "SERVICE_CONFLICT"

    # Success/OK states
    OK = "OK"
    DEGRADED = "DEGRADED"


# Standard hints for each reason code
REASON_HINTS: Dict[ReasonCode, str] = {
    # Configuration
    ReasonCode.NO_CONFIG: "Configuration not provided. Add credentials in Settings.",
    ReasonCode.INVALID_CONFIG: "Configuration is invalid. Check settings and try again.",

    # Network
    ReasonCode.CONN_REFUSED: "Connection refused. Check if service is running.",
    ReasonCode.TIMEOUT: "Request timed out. Check network connection or service availability.",
    ReasonCode.DNS_FAILURE: "DNS resolution failed. Check network connection.",

    # HTTP errors
    ReasonCode.HTTP_401: "Authentication failed. Check your API key or credentials.",
    ReasonCode.HTTP_403: "Access forbidden. Check your API key permissions.",
    ReasonCode.HTTP_404: "Service endpoint not found. Check configuration or service version.",
    ReasonCode.HTTP_429: "Rate limit exceeded. Wait a moment and try again.",
    ReasonCode.HTTP_5XX: "Service error. The provider may be experiencing issues.",

    # Response
    ReasonCode.INVALID_RESPONSE: "Received invalid response from service.",
    ReasonCode.EMPTY_RESPONSE: "Service returned empty response.",

    # Security
    ReasonCode.PERMISSION_NOT_600: "Secrets file has insecure permissions. Run: chmod 600 ~/.agentos/secrets/providers.json",
    ReasonCode.PERMISSION_DENIED: "Permission denied. Check file/directory permissions.",

    # State
    ReasonCode.STALE_REFRESH: "Context not refreshed recently. Click Refresh to update.",
    ReasonCode.REFRESH_IN_PROGRESS: "Refresh is currently in progress. Please wait.",
    ReasonCode.NOT_IMPLEMENTED: "Feature not yet implemented in this version.",

    # Service
    ReasonCode.CLI_NOT_FOUND: "CLI tool not found. Install the required software.",
    ReasonCode.SERVICE_NOT_RUNNING: "Service is not running. Start the service to continue.",

    # Provider fingerprint (Sprint B+)
    ReasonCode.PORT_OCCUPIED_BY_OTHER_PROVIDER: "Port is occupied by a different service. Change endpoint or stop conflicting service.",
    ReasonCode.FINGERPRINT_MISMATCH: "Service fingerprint doesn't match expected provider. Check endpoint configuration.",
    ReasonCode.SERVICE_CONFLICT: "Multiple services detected on same endpoint. Resolve port conflict.",

    # OK
    ReasonCode.OK: None,  # No hint needed for OK state
    ReasonCode.DEGRADED: "Service is partially available. Some features may not work.",
}


def get_hint(reason_code: ReasonCode) -> str:
    """Get standard hint for a reason code"""
    return REASON_HINTS.get(reason_code, "")
