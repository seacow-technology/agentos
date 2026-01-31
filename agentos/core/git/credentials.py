"""Git Credentials Manager - Secure credential storage and management

This module provides:
1. AuthProfile data class for credential storage
2. CredentialsManager for CRUD operations
3. Encryption/decryption utilities for sensitive data
4. Environment variable fallback support
"""

import os
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any
from ulid import ULID

from cryptography.fernet import Fernet

from agentos.store import get_db

logger = logging.getLogger(__name__)


class AuthProfileType(str, Enum):
    """Authentication profile types"""
    SSH_KEY = "ssh_key"
    PAT_TOKEN = "pat_token"
    NETRC = "netrc"


class TokenProvider(str, Enum):
    """Git service providers"""
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    GITEA = "gitea"
    OTHER = "other"


class ValidationStatus(str, Enum):
    """Credential validation status"""
    UNKNOWN = "unknown"
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"


@dataclass
class AuthProfile:
    """Auth Profile for Git credential management"""
    profile_id: str
    profile_name: str
    profile_type: AuthProfileType

    # SSH Key fields
    ssh_key_path: Optional[str] = None
    ssh_passphrase: Optional[str] = None  # Decrypted in memory

    # PAT Token fields
    token: Optional[str] = None  # Decrypted in memory
    token_provider: Optional[TokenProvider] = None
    token_scopes: Optional[List[str]] = None

    # Netrc fields
    netrc_machine: Optional[str] = None
    netrc_login: Optional[str] = None
    netrc_password: Optional[str] = None  # Decrypted in memory

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_validated_at: Optional[datetime] = None
    validation_status: ValidationStatus = ValidationStatus.UNKNOWN
    validation_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert to dictionary (exclude sensitive data by default)"""
        data = {
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "profile_type": self.profile_type.value,
            "ssh_key_path": self.ssh_key_path,
            "token_provider": self.token_provider.value if self.token_provider else None,
            "token_scopes": self.token_scopes,
            "netrc_machine": self.netrc_machine,
            "netrc_login": self.netrc_login,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_validated_at": self.last_validated_at.isoformat() if self.last_validated_at else None,
            "validation_status": self.validation_status.value,
            "validation_message": self.validation_message,
            "metadata": self.metadata,
        }

        if include_sensitive:
            data["ssh_passphrase"] = self.ssh_passphrase
            data["token"] = self.token
            data["netrc_password"] = self.netrc_password

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuthProfile":
        """Create from dictionary"""
        return cls(
            profile_id=data["profile_id"],
            profile_name=data["profile_name"],
            profile_type=AuthProfileType(data["profile_type"]),
            ssh_key_path=data.get("ssh_key_path"),
            ssh_passphrase=data.get("ssh_passphrase"),
            token=data.get("token"),
            token_provider=TokenProvider(data["token_provider"]) if data.get("token_provider") else None,
            token_scopes=data.get("token_scopes"),
            netrc_machine=data.get("netrc_machine"),
            netrc_login=data.get("netrc_login"),
            netrc_password=data.get("netrc_password"),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.now()),
            updated_at=datetime.fromisoformat(data["updated_at"]) if isinstance(data.get("updated_at"), str) else data.get("updated_at", datetime.now()),
            last_validated_at=datetime.fromisoformat(data["last_validated_at"]) if data.get("last_validated_at") else None,
            validation_status=ValidationStatus(data.get("validation_status", "unknown")),
            validation_message=data.get("validation_message"),
            metadata=data.get("metadata", {}),
        )


class EncryptionManager:
    """Manages encryption/decryption of sensitive credential data

    Security notes:
    - Uses Fernet (symmetric encryption with AES-128-CBC)
    - Master key derived from system-specific entropy
    - For production: consider using system keyring (keyring library)
    """

    def __init__(self):
        self._fernet = None
        self._key_file = Path.home() / ".agentos" / "credentials.key"
        self._initialize_encryption()

    def _initialize_encryption(self):
        """Initialize or load encryption key"""
        self._key_file.parent.mkdir(parents=True, exist_ok=True)

        if self._key_file.exists():
            # Load existing key
            key = self._key_file.read_bytes()
        else:
            # Generate new key
            key = Fernet.generate_key()
            self._key_file.write_bytes(key)
            # Secure the key file (Unix only)
            if os.name != 'nt':  # Not Windows
                os.chmod(self._key_file, 0o600)

        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string"""
        if not plaintext:
            return ""
        encrypted_bytes = self._fernet.encrypt(plaintext.encode())
        return encrypted_bytes.decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext string"""
        if not ciphertext:
            return ""
        decrypted_bytes = self._fernet.decrypt(ciphertext.encode())
        return decrypted_bytes.decode()


class CredentialsManager:
    """Manages auth profiles in database with secure storage"""

    def __init__(self):
        self.encryption = EncryptionManager()

    def create_profile(
        self,
        profile_name: str,
        profile_type: AuthProfileType,
        ssh_key_path: Optional[str] = None,
        ssh_passphrase: Optional[str] = None,
        token: Optional[str] = None,
        token_provider: Optional[TokenProvider] = None,
        token_scopes: Optional[List[str]] = None,
        netrc_machine: Optional[str] = None,
        netrc_login: Optional[str] = None,
        netrc_password: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuthProfile:
        """Create a new auth profile"""
        profile_id = str(ULID())

        # Encrypt sensitive fields
        ssh_passphrase_enc = self.encryption.encrypt(ssh_passphrase) if ssh_passphrase else None
        token_enc = self.encryption.encrypt(token) if token else None
        netrc_password_enc = self.encryption.encrypt(netrc_password) if netrc_password else None

        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO auth_profiles (
                    profile_id, profile_name, profile_type,
                    ssh_key_path, ssh_passphrase_encrypted,
                    token_encrypted, token_provider, token_scopes,
                    netrc_machine, netrc_login, netrc_password_encrypted,
                    created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile_id,
                profile_name,
                profile_type.value,
                ssh_key_path,
                ssh_passphrase_enc,
                token_enc,
                token_provider.value if token_provider else None,
                json.dumps(token_scopes) if token_scopes else None,
                netrc_machine,
                netrc_login,
                netrc_password_enc,
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                json.dumps(metadata or {}),
            ))
            conn.commit()

            logger.info(f"Created auth profile: {profile_name} (type={profile_type.value})")

            # Return profile with decrypted fields
            return AuthProfile(
                profile_id=profile_id,
                profile_name=profile_name,
                profile_type=profile_type,
                ssh_key_path=ssh_key_path,
                ssh_passphrase=ssh_passphrase,
                token=token,
                token_provider=token_provider,
                token_scopes=token_scopes,
                netrc_machine=netrc_machine,
                netrc_login=netrc_login,
                netrc_password=netrc_password,
                metadata=metadata or {},
            )

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create auth profile: {e}")
            raise
        finally:
            # Do NOT close: get_db() returns shared thread-local connection
            pass

    def get_profile(self, profile_name: str) -> Optional[AuthProfile]:
        """Get profile by name (with decrypted credentials)"""
        conn = get_db()
        cursor = conn.cursor()

        try:
            row = cursor.execute("""
                SELECT
                    profile_id, profile_name, profile_type,
                    ssh_key_path, ssh_passphrase_encrypted,
                    token_encrypted, token_provider, token_scopes,
                    netrc_machine, netrc_login, netrc_password_encrypted,
                    created_at, updated_at, last_validated_at,
                    validation_status, validation_message, metadata
                FROM auth_profiles
                WHERE profile_name = ?
            """, (profile_name,)).fetchone()

            if not row:
                return None

            # Decrypt sensitive fields
            ssh_passphrase = self.encryption.decrypt(row["ssh_passphrase_encrypted"]) if row["ssh_passphrase_encrypted"] else None
            token = self.encryption.decrypt(row["token_encrypted"]) if row["token_encrypted"] else None
            netrc_password = self.encryption.decrypt(row["netrc_password_encrypted"]) if row["netrc_password_encrypted"] else None

            return AuthProfile(
                profile_id=row["profile_id"],
                profile_name=row["profile_name"],
                profile_type=AuthProfileType(row["profile_type"]),
                ssh_key_path=row["ssh_key_path"],
                ssh_passphrase=ssh_passphrase,
                token=token,
                token_provider=TokenProvider(row["token_provider"]) if row["token_provider"] else None,
                token_scopes=json.loads(row["token_scopes"]) if row["token_scopes"] else None,
                netrc_machine=row["netrc_machine"],
                netrc_login=row["netrc_login"],
                netrc_password=netrc_password,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                last_validated_at=datetime.fromisoformat(row["last_validated_at"]) if row["last_validated_at"] else None,
                validation_status=ValidationStatus(row["validation_status"]),
                validation_message=row["validation_message"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )

        finally:
            # Do NOT close: get_db() returns shared thread-local connection
            pass

    def get_profile_by_id(self, profile_id: str) -> Optional[AuthProfile]:
        """Get profile by ID"""
        conn = get_db()
        cursor = conn.cursor()

        try:
            row = cursor.execute("""
                SELECT profile_name FROM auth_profiles WHERE profile_id = ?
            """, (profile_id,)).fetchone()

            if not row:
                return None

            return self.get_profile(row["profile_name"])

        finally:
            # Do NOT close: get_db() returns shared thread-local connection
            pass

    def list_profiles(self, include_sensitive: bool = False) -> List[AuthProfile]:
        """List all profiles"""
        conn = get_db()
        cursor = conn.cursor()

        try:
            rows = cursor.execute("""
                SELECT
                    profile_id, profile_name, profile_type,
                    ssh_key_path, ssh_passphrase_encrypted,
                    token_encrypted, token_provider, token_scopes,
                    netrc_machine, netrc_login, netrc_password_encrypted,
                    created_at, updated_at, last_validated_at,
                    validation_status, validation_message, metadata
                FROM auth_profiles
                ORDER BY created_at DESC
            """).fetchall()

            profiles = []
            for row in rows:
                if include_sensitive:
                    # Decrypt sensitive fields
                    ssh_passphrase = self.encryption.decrypt(row["ssh_passphrase_encrypted"]) if row["ssh_passphrase_encrypted"] else None
                    token = self.encryption.decrypt(row["token_encrypted"]) if row["token_encrypted"] else None
                    netrc_password = self.encryption.decrypt(row["netrc_password_encrypted"]) if row["netrc_password_encrypted"] else None
                else:
                    ssh_passphrase = None
                    token = None
                    netrc_password = None

                profiles.append(AuthProfile(
                    profile_id=row["profile_id"],
                    profile_name=row["profile_name"],
                    profile_type=AuthProfileType(row["profile_type"]),
                    ssh_key_path=row["ssh_key_path"],
                    ssh_passphrase=ssh_passphrase,
                    token=token,
                    token_provider=TokenProvider(row["token_provider"]) if row["token_provider"] else None,
                    token_scopes=json.loads(row["token_scopes"]) if row["token_scopes"] else None,
                    netrc_machine=row["netrc_machine"],
                    netrc_login=row["netrc_login"],
                    netrc_password=netrc_password,
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    last_validated_at=datetime.fromisoformat(row["last_validated_at"]) if row["last_validated_at"] else None,
                    validation_status=ValidationStatus(row["validation_status"]),
                    validation_message=row["validation_message"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                ))

            return profiles

        finally:
            # Do NOT close: get_db() returns shared thread-local connection
            pass

    def delete_profile(self, profile_name: str) -> bool:
        """Delete a profile by name"""
        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM auth_profiles WHERE profile_name = ?", (profile_name,))
            deleted = cursor.rowcount > 0
            conn.commit()

            if deleted:
                logger.info(f"Deleted auth profile: {profile_name}")
            else:
                logger.warning(f"Auth profile not found: {profile_name}")

            return deleted

        finally:
            # Do NOT close: get_db() returns shared thread-local connection
            pass

    def update_validation_status(
        self,
        profile_name: str,
        status: ValidationStatus,
        message: Optional[str] = None
    ):
        """Update profile validation status"""
        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE auth_profiles
                SET validation_status = ?,
                    validation_message = ?,
                    last_validated_at = ?,
                    updated_at = ?
                WHERE profile_name = ?
            """, (
                status.value,
                message,
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                profile_name,
            ))
            conn.commit()

        finally:
            # Do NOT close: get_db() returns shared thread-local connection
            pass

    def log_usage(
        self,
        profile_id: str,
        operation: str,
        status: str,
        repo_id: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log credential usage for audit trail"""
        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO auth_profile_usage (
                    profile_id, repo_id, operation, status,
                    error_message, used_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                profile_id,
                repo_id,
                operation,
                status,
                error_message,
                datetime.now().isoformat(),
                json.dumps(metadata or {}),
            ))
            conn.commit()

        except Exception as e:
            logger.warning(f"Failed to log auth usage: {e}")

        finally:
            # Do NOT close: get_db() returns shared thread-local connection
            pass

    def get_from_env(self, provider: TokenProvider) -> Optional[str]:
        """Get token from environment variables (fallback mechanism)"""
        env_mapping = {
            TokenProvider.GITHUB: ["GITHUB_TOKEN", "GH_TOKEN"],
            TokenProvider.GITLAB: ["GITLAB_TOKEN", "CI_JOB_TOKEN"],
            TokenProvider.BITBUCKET: ["BITBUCKET_TOKEN"],
            TokenProvider.GITEA: ["GITEA_TOKEN"],
        }

        for env_var in env_mapping.get(provider, []):
            token = os.getenv(env_var)
            if token:
                logger.info(f"Using token from environment variable: {env_var}")
                return token

        return None
