"""Channel Manifest data model for CommunicationOS.

This module defines the data structure for channel manifests that describe
the capabilities, configuration requirements, and metadata for each channel adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


class SessionScope(str, Enum):
    """Scope of session management for a channel.

    USER: One session per user (channel_id + user_key)
    USER_CONVERSATION: One session per user-conversation pair (channel_id + user_key + conversation_key)
    """
    USER = "user"
    USER_CONVERSATION = "user_conversation"


class ChannelCapability(str, Enum):
    """Capabilities that a channel adapter can provide."""
    INBOUND_TEXT = "inbound_text"              # Receive text messages
    OUTBOUND_TEXT = "outbound_text"            # Send text messages
    INBOUND_IMAGE = "inbound_image"            # Receive image attachments
    OUTBOUND_IMAGE = "outbound_image"          # Send image attachments
    INBOUND_AUDIO = "inbound_audio"            # Receive audio messages
    OUTBOUND_AUDIO = "outbound_audio"          # Send audio messages
    INBOUND_FILE = "inbound_file"              # Receive file attachments
    OUTBOUND_FILE = "outbound_file"            # Send file attachments
    INTERACTIVE = "interactive"                 # Support interactive elements (buttons, menus)
    THREADING = "threading"                     # Support conversation threads/rooms
    REACTIONS = "reactions"                     # Support message reactions
    TYPING_INDICATOR = "typing_indicator"       # Support typing indicators


class SecurityMode(str, Enum):
    """Security modes for channel operation.

    CHAT_ONLY: Only allow chat operations (default, safest)
    CHAT_EXEC_RESTRICTED: Allow execution with admin token validation
    """
    CHAT_ONLY = "chat_only"
    CHAT_EXEC_RESTRICTED = "chat_exec_restricted"


@dataclass
class ConfigField:
    """Definition of a configuration field required by a channel.

    Attributes:
        name: Internal field name (e.g., "api_key")
        label: Human-readable label for UI (e.g., "API Key")
        type: Field type (text, password, url, select, etc.)
        required: Whether this field is required
        default: Default value
        placeholder: Placeholder text for input
        help_text: Help text to display
        secret: Whether this field contains secret data (will be encrypted)
        validation_regex: Optional regex pattern for validation
        validation_error: Error message for validation failure
        options: List of options for select type fields
    """
    name: str
    label: str
    type: str = "text"  # text, password, url, select, number, textarea
    required: bool = True
    default: Optional[str] = None
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    secret: bool = False
    validation_regex: Optional[str] = None
    validation_error: Optional[str] = None
    options: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "required": self.required,
            "default": self.default,
            "placeholder": self.placeholder,
            "help_text": self.help_text,
            "secret": self.secret,
            "validation_regex": self.validation_regex,
            "validation_error": self.validation_error,
            "options": self.options,
        }


@dataclass
class SetupStep:
    """A step in the setup wizard.

    Attributes:
        title: Step title
        description: Step description
        instruction: Detailed instruction text
        animation_url: Optional URL to animation/video guide
        checklist: List of checklist items for this step
        auto_check: Whether this step can be auto-verified
    """
    title: str
    description: str
    instruction: Optional[str] = None
    animation_url: Optional[str] = None
    checklist: List[str] = field(default_factory=list)
    auto_check: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "title": self.title,
            "description": self.description,
            "instruction": self.instruction,
            "animation_url": self.animation_url,
            "checklist": self.checklist,
            "auto_check": self.auto_check,
        }


@dataclass
class SecurityDefaults:
    """Default security settings for a channel.

    Attributes:
        mode: Default security mode
        allow_execute: Whether to allow execution (requires mode=CHAT_EXEC_RESTRICTED)
        allowed_commands: List of allowed command prefixes
        rate_limit_per_minute: Rate limit for incoming messages
        retention_days: Number of days to retain message logs (0 = don't persist)
        require_signature: Whether webhook signature validation is required
    """
    mode: SecurityMode = SecurityMode.CHAT_ONLY
    allow_execute: bool = False
    allowed_commands: List[str] = field(default_factory=lambda: ["/session", "/help"])
    rate_limit_per_minute: int = 20
    retention_days: int = 7
    require_signature: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "mode": self.mode.value,
            "allow_execute": self.allow_execute,
            "allowed_commands": self.allowed_commands,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "retention_days": self.retention_days,
            "require_signature": self.require_signature,
        }


@dataclass
class ChannelManifest:
    """Manifest describing a channel adapter.

    This is the core data model that drives the UI, configuration, and behavior
    of each channel. New channels are added by creating a manifest and adapter.

    Attributes:
        id: Unique channel identifier (e.g., "whatsapp_twilio", "telegram")
        name: Human-readable name (e.g., "WhatsApp (Twilio)")
        icon: Icon identifier or URL (e.g., "whatsapp", "https://...")
        description: Short description of the channel
        long_description: Detailed description with setup information
        version: Manifest version for compatibility tracking
        provider: Provider name (e.g., "Twilio", "Meta", "Telegram")
        docs_url: URL to official documentation
        required_config_fields: List of configuration fields needed
        webhook_paths: List of webhook paths this channel registers
        session_scope: How sessions are scoped for this channel
        capabilities: List of capabilities this channel supports
        security_defaults: Default security settings
        setup_steps: Steps for the setup wizard
        privacy_badges: Privacy/security badges to display
        metadata: Additional metadata for the channel
    """
    id: str
    name: str
    icon: str
    description: str
    long_description: Optional[str] = None
    version: str = "1.0.0"
    provider: Optional[str] = None
    docs_url: Optional[str] = None
    required_config_fields: List[ConfigField] = field(default_factory=list)
    webhook_paths: List[str] = field(default_factory=list)
    session_scope: SessionScope = SessionScope.USER
    capabilities: List[ChannelCapability] = field(default_factory=list)
    security_defaults: SecurityDefaults = field(default_factory=SecurityDefaults)
    setup_steps: List[SetupStep] = field(default_factory=list)
    privacy_badges: List[str] = field(default_factory=lambda: [
        "No Auto Provisioning",
        "Chat-only",
        "Local Storage",
        "Secrets Encrypted"
    ])
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "description": self.description,
            "long_description": self.long_description,
            "version": self.version,
            "provider": self.provider,
            "docs_url": self.docs_url,
            "required_config_fields": [f.to_dict() for f in self.required_config_fields],
            "webhook_paths": self.webhook_paths,
            "session_scope": self.session_scope.value,
            "capabilities": [c.value for c in self.capabilities],
            "security_defaults": self.security_defaults.to_dict(),
            "setup_steps": [s.to_dict() for s in self.setup_steps],
            "privacy_badges": self.privacy_badges,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ChannelManifest:
        """Create manifest from dictionary representation.

        Args:
            data: Dictionary containing manifest data

        Returns:
            ChannelManifest instance
        """
        # Parse config fields
        config_fields = [
            ConfigField(**field_data)
            for field_data in data.get("required_config_fields", [])
        ]

        # Parse setup steps
        setup_steps = [
            SetupStep(**step_data)
            for step_data in data.get("setup_steps", [])
        ]

        # Parse security defaults
        security_data = data.get("security_defaults", {})
        security_defaults = SecurityDefaults(
            mode=SecurityMode(security_data.get("mode", "chat_only")),
            allow_execute=security_data.get("allow_execute", False),
            allowed_commands=security_data.get("allowed_commands", ["/session", "/help"]),
            rate_limit_per_minute=security_data.get("rate_limit_per_minute", 20),
            retention_days=security_data.get("retention_days", 7),
            require_signature=security_data.get("require_signature", True),
        )

        # Parse capabilities
        capabilities = [
            ChannelCapability(cap)
            for cap in data.get("capabilities", [])
        ]

        return cls(
            id=data["id"],
            name=data["name"],
            icon=data["icon"],
            description=data["description"],
            long_description=data.get("long_description"),
            version=data.get("version", "1.0.0"),
            provider=data.get("provider"),
            docs_url=data.get("docs_url"),
            required_config_fields=config_fields,
            webhook_paths=data.get("webhook_paths", []),
            session_scope=SessionScope(data.get("session_scope", "user")),
            capabilities=capabilities,
            security_defaults=security_defaults,
            setup_steps=setup_steps,
            privacy_badges=data.get("privacy_badges", [
                "No Auto Provisioning",
                "Chat-only",
                "Local Storage",
                "Secrets Encrypted"
            ]),
            metadata=data.get("metadata", {}),
        )

    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate a configuration against this manifest.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        import re

        for field in self.required_config_fields:
            # Check required fields
            if field.required and field.name not in config:
                return False, f"Missing required field: {field.label}"

            # Skip validation if field not provided and not required
            if field.name not in config:
                continue

            value = config[field.name]

            # Validate regex if provided
            if field.validation_regex and value:
                if not re.match(field.validation_regex, str(value)):
                    error_msg = field.validation_error or f"Invalid format for {field.label}"
                    return False, error_msg

        return True, None
