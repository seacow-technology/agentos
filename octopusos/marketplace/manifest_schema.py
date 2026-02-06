"""
Capability Manifest Schema and Validation

This module provides the core data structures and validation logic for
AgentOS Marketplace Capability Manifests. Every capability (Extension/App/Pack)
must have an immutable manifest that declares its identity, permissions, and requirements.

Red Lines:
- No runtime extension of declarations
- No mismatch between declaration and behavior
- No unsigned publishing
"""

import re
import yaml
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional
from pathlib import Path

try:
    from nacl.signing import SigningKey, VerifyKey
    from nacl.encoding import Base64Encoder
    from nacl.exceptions import BadSignatureError
    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False


class CapabilityType(Enum):
    """Type of capability"""
    EXTENSION = "extension"
    APP = "app"
    PACK = "pack"


class DeclaredAction(Enum):
    """Actions that a capability can declare"""
    READ = "read"           # Read-only operations
    WRITE = "write"         # Write operations
    EXTERNAL = "external"   # External network calls
    SYSTEM = "system"       # System-level operations


class SandboxLevel(Enum):
    """Sandbox isolation level required"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TrustTier(Enum):
    """Maximum trust tier allowed"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class CapabilityMetadata:
    """Metadata for a capability"""
    name: str
    description: str
    author: str
    homepage: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class CapabilityManifest:
    """
    Immutable capability manifest.

    This is the core contract for any capability in the marketplace.
    Once created and signed, it cannot be modified at runtime.
    """
    capability_id: str
    capability_type: CapabilityType
    declared_actions: List[DeclaredAction]
    required_sandbox_level: SandboxLevel
    max_trust_tier_allowed: TrustTier
    publisher_id: str
    signature: str
    version: str
    created_at: datetime
    metadata: CapabilityMetadata

    def __post_init__(self):
        """Validate after initialization"""
        # Convert string enums if needed
        if isinstance(self.capability_type, str):
            self.capability_type = CapabilityType(self.capability_type)

        if isinstance(self.declared_actions, list) and self.declared_actions:
            if isinstance(self.declared_actions[0], str):
                self.declared_actions = [DeclaredAction(a) for a in self.declared_actions]

        if isinstance(self.required_sandbox_level, str):
            self.required_sandbox_level = SandboxLevel(self.required_sandbox_level)

        if isinstance(self.max_trust_tier_allowed, str):
            self.max_trust_tier_allowed = TrustTier(self.max_trust_tier_allowed)

        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at.replace('Z', '+00:00'))

        if isinstance(self.metadata, dict):
            self.metadata = CapabilityMetadata(**self.metadata)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'capability_id': self.capability_id,
            'capability_type': self.capability_type.value,
            'declared_actions': [a.value for a in self.declared_actions],
            'required_sandbox_level': self.required_sandbox_level.value,
            'max_trust_tier_allowed': self.max_trust_tier_allowed.value,
            'publisher_id': self.publisher_id,
            'signature': self.signature,
            'version': self.version,
            'created_at': self.created_at.isoformat().replace('+00:00', 'Z'),
            'metadata': self.metadata.to_dict()
        }

    def get_signing_payload(self) -> str:
        """
        Get the canonical payload for signing.
        This includes all fields except the signature itself.
        """
        payload_dict = self.to_dict()
        payload_dict.pop('signature', None)

        # Sort keys for deterministic output
        return yaml.dump(payload_dict, sort_keys=True, default_flow_style=False)


class ManifestValidator:
    """Validates capability manifests"""

    # Regex for capability_id: publisher.capability.version
    CAPABILITY_ID_PATTERN = re.compile(r'^[a-z0-9_]+\.[a-z0-9_]+\.v\d+\.\d+\.\d+$')

    # Semantic version pattern
    VERSION_PATTERN = re.compile(r'^\d+\.\d+\.\d+$')

    @staticmethod
    def validate(manifest: CapabilityManifest) -> tuple[bool, Optional[str]]:
        """
        Validate a capability manifest.

        Returns:
            (is_valid, error_message)
        """
        # Check capability_id format
        if not ManifestValidator.CAPABILITY_ID_PATTERN.match(manifest.capability_id):
            return False, f"Invalid capability_id format: {manifest.capability_id}. Expected: publisher.capability.vX.Y.Z"

        # Check version format
        if not ManifestValidator.VERSION_PATTERN.match(manifest.version):
            return False, f"Invalid version format: {manifest.version}. Expected: X.Y.Z"

        # Check capability_id matches version
        id_version = manifest.capability_id.split('.')[-3:]  # Get vX.Y.Z
        expected_version = f"{id_version[0][1:]}.{id_version[1]}.{id_version[2]}"
        if expected_version != manifest.version:
            return False, f"Version mismatch: capability_id has {expected_version} but version field is {manifest.version}"

        # Check declared_actions is not empty
        if not manifest.declared_actions:
            return False, "declared_actions cannot be empty"

        # Check publisher_id matches capability_id prefix
        if not manifest.capability_id.startswith(manifest.publisher_id + '.'):
            return False, f"publisher_id '{manifest.publisher_id}' does not match capability_id prefix"

        # Check signature exists
        if not manifest.signature or manifest.signature == "":
            return False, "signature is required"

        # Check metadata required fields
        if not manifest.metadata.name:
            return False, "metadata.name is required"
        if not manifest.metadata.description:
            return False, "metadata.description is required"
        if not manifest.metadata.author:
            return False, "metadata.author is required"

        return True, None

    @staticmethod
    def validate_against_behavior(manifest: CapabilityManifest, actual_actions: List[str]) -> tuple[bool, Optional[str]]:
        """
        Validate that declared actions match actual behavior.

        Args:
            manifest: The capability manifest
            actual_actions: List of actions actually performed

        Returns:
            (is_valid, error_message)
        """
        declared = set(a.value for a in manifest.declared_actions)
        actual = set(actual_actions)

        undeclared = actual - declared
        if undeclared:
            return False, f"Undeclared actions detected: {undeclared}"

        return True, None


class ManifestSigner:
    """Signs and verifies capability manifests using Ed25519"""

    def __init__(self):
        if not NACL_AVAILABLE:
            raise ImportError("PyNaCl is required for signing. Install with: pip install pynacl")

    @staticmethod
    def generate_keypair() -> tuple[str, str]:
        """
        Generate a new Ed25519 keypair.

        Returns:
            (private_key, public_key) as base64-encoded strings
        """
        if not NACL_AVAILABLE:
            raise ImportError("PyNaCl is required for signing. Install with: pip install pynacl")

        signing_key = SigningKey.generate()
        private_key = signing_key.encode(encoder=Base64Encoder).decode('utf-8')
        public_key = signing_key.verify_key.encode(encoder=Base64Encoder).decode('utf-8')

        return private_key, public_key

    @staticmethod
    def sign_manifest(manifest: CapabilityManifest, private_key: str) -> str:
        """
        Sign a manifest with a private key.

        Args:
            manifest: The manifest to sign
            private_key: Base64-encoded Ed25519 private key

        Returns:
            Signature as "ed25519:<base64_signature>"
        """
        if not NACL_AVAILABLE:
            raise ImportError("PyNaCl is required for signing. Install with: pip install pynacl")

        payload = manifest.get_signing_payload()
        signing_key = SigningKey(private_key, encoder=Base64Encoder)
        signed = signing_key.sign(payload.encode('utf-8'))
        signature = signed.signature

        return f"ed25519:{Base64Encoder.encode(signature).decode('utf-8')}"

    @staticmethod
    def verify_signature(manifest: CapabilityManifest, public_key: str) -> bool:
        """
        Verify a manifest signature.

        Args:
            manifest: The manifest to verify
            public_key: Base64-encoded Ed25519 public key

        Returns:
            True if signature is valid, False otherwise
        """
        if not NACL_AVAILABLE:
            raise ImportError("PyNaCl is required for signing. Install with: pip install pynacl")

        if not manifest.signature.startswith('ed25519:'):
            return False

        try:
            signature_b64 = manifest.signature.split(':', 1)[1]
            signature = Base64Encoder.decode(signature_b64)

            payload = manifest.get_signing_payload()
            verify_key = VerifyKey(public_key, encoder=Base64Encoder)
            verify_key.verify(payload.encode('utf-8'), signature)

            return True
        except (BadSignatureError, Exception):
            return False


class ManifestParser:
    """Parses and serializes capability manifests from/to YAML"""

    @staticmethod
    def parse_yaml(yaml_path: Path) -> CapabilityManifest:
        """
        Parse a manifest from a YAML file.

        Args:
            yaml_path: Path to YAML file

        Returns:
            CapabilityManifest instance

        Raises:
            ValueError: If parsing fails
            FileNotFoundError: If file doesn't exist
        """
        if not yaml_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {yaml_path}")

        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError("Empty manifest file")

        # Check required fields
        required_fields = [
            'capability_id', 'capability_type', 'declared_actions',
            'required_sandbox_level', 'max_trust_tier_allowed',
            'publisher_id', 'signature', 'version', 'created_at', 'metadata'
        ]

        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")

        try:
            return CapabilityManifest(**data)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid manifest data: {e}")

    @staticmethod
    def parse_yaml_string(yaml_content: str) -> CapabilityManifest:
        """
        Parse a manifest from a YAML string.

        Args:
            yaml_content: YAML content as string

        Returns:
            CapabilityManifest instance
        """
        data = yaml.safe_load(yaml_content)

        if not data:
            raise ValueError("Empty manifest content")

        required_fields = [
            'capability_id', 'capability_type', 'declared_actions',
            'required_sandbox_level', 'max_trust_tier_allowed',
            'publisher_id', 'signature', 'version', 'created_at', 'metadata'
        ]

        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")

        try:
            return CapabilityManifest(**data)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid manifest data: {e}")

    @staticmethod
    def to_yaml(manifest: CapabilityManifest, output_path: Path):
        """
        Serialize a manifest to a YAML file.

        Args:
            manifest: The manifest to serialize
            output_path: Path to output YAML file
        """
        with open(output_path, 'w') as f:
            yaml.dump(manifest.to_dict(), f, sort_keys=False, default_flow_style=False)

    @staticmethod
    def to_yaml_string(manifest: CapabilityManifest) -> str:
        """
        Serialize a manifest to a YAML string.

        Args:
            manifest: The manifest to serialize

        Returns:
            YAML string
        """
        return yaml.dump(manifest.to_dict(), sort_keys=False, default_flow_style=False)
