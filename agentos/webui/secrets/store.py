"""
Secret Store - Secure API Key Storage

Sprint B Task #6: Cloud API Key Configuration

Security Requirements:
1. File stored at ~/.agentos/secrets.json
2. File permissions must be 0600 (owner read/write only)
3. API keys never appear in logs, errors, or events
4. Only last-4 digits exposed to API responses
5. Atomic write operations (tmp file + rename)
"""

import json
import os
import stat
import logging
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class SecretInfo:
    """
    Secret metadata (never includes the actual key)

    Used for API responses and status display
    """
    provider: str
    configured: bool
    last4: Optional[str] = None  # Last 4 chars of key (for UI verification)
    updated_at: Optional[str] = None


class SecretStore:
    """
    Secure storage for provider API keys

    Architecture:
    - Single JSON file at ~/.agentos/secrets.json
    - 0600 permissions enforced
    - Atomic writes via tmp file
    - Key redaction in all logs/errors
    """

    def __init__(self, secrets_file: Optional[str] = None):
        """
        Initialize SecretStore

        Args:
            secrets_file: Path to secrets file (default: ~/.agentos/secrets.json)
        """
        if secrets_file:
            self.secrets_file = Path(secrets_file)
        else:
            self.secrets_file = Path.home() / ".agentos" / "secrets.json"

        # Ensure parent directory exists
        self.secrets_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize file if not exists
        if not self.secrets_file.exists():
            self._write_secrets({})
            logger.info(f"Initialized secrets file: {self.secrets_file}")

        # Verify permissions
        self._verify_permissions()

    def _verify_permissions(self):
        """
        Verify file has 0600 permissions

        Raises:
            PermissionError: If permissions are too open
        """
        if not self.secrets_file.exists():
            return

        file_stat = self.secrets_file.stat()
        file_mode = stat.S_IMODE(file_stat.st_mode)

        # Expected: 0600 (owner read/write only)
        expected_mode = stat.S_IRUSR | stat.S_IWUSR

        if file_mode != expected_mode:
            # Try to fix permissions automatically
            try:
                self.secrets_file.chmod(expected_mode)
                logger.warning(f"Fixed secrets file permissions: {oct(expected_mode)}")
            except Exception as e:
                error_msg = (
                    f"Secrets file has insecure permissions: {oct(file_mode)}. "
                    f"Expected: {oct(expected_mode)}. "
                    f"Fix with: chmod 600 {self.secrets_file}"
                )
                logger.error(error_msg)
                raise PermissionError(error_msg) from e

    def _read_secrets(self) -> Dict[str, Dict]:
        """
        Read secrets from file

        Returns:
            Dict mapping provider -> {api_key, updated_at}
        """
        try:
            self._verify_permissions()

            with open(self.secrets_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Log access (without keys)
            logger.debug(f"Loaded secrets for providers: {list(data.keys())}")
            return data

        except json.JSONDecodeError as e:
            logger.error(f"Corrupted secrets file: {e}")
            return {}

        except Exception as e:
            logger.error(f"Failed to read secrets: {e}")
            return {}

    def _write_secrets(self, secrets: Dict[str, Dict]):
        """
        Write secrets to file (atomic operation)

        Uses tmp file + rename for atomic write
        """
        try:
            # Write to tmp file first
            tmp_file = self.secrets_file.with_suffix('.tmp')

            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(secrets, f, indent=2)

            # Set permissions before rename
            tmp_file.chmod(stat.S_IRUSR | stat.S_IWUSR)

            # Atomic rename
            tmp_file.rename(self.secrets_file)

            # Log write (without keys)
            logger.debug(f"Saved secrets for providers: {list(secrets.keys())}")

        except Exception as e:
            logger.error(f"Failed to write secrets: {e}")
            raise

    def save_secret(self, provider: str, api_key: str) -> SecretInfo:
        """
        Save or update API key for provider

        Args:
            provider: Provider ID (e.g., "openai", "anthropic")
            api_key: API key to store

        Returns:
            SecretInfo with metadata (no actual key)
        """
        # Validate inputs
        if not provider:
            raise ValueError("Provider ID cannot be empty")

        if not api_key or len(api_key) < 8:
            raise ValueError("API key too short (minimum 8 characters)")

        # Redact key in logs
        redacted_key = self._redact_key(api_key)
        logger.info(f"Saving secret for provider: {provider} (key: {redacted_key})")

        # Read existing secrets
        secrets = self._read_secrets()

        # Update provider entry
        secrets[provider] = {
            "api_key": api_key,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Write back
        self._write_secrets(secrets)

        # Return metadata only
        return SecretInfo(
            provider=provider,
            configured=True,
            last4=api_key[-4:],
            updated_at=secrets[provider]["updated_at"],
        )

    def get_secret(self, provider: str) -> Optional[str]:
        """
        Get API key for provider

        Args:
            provider: Provider ID

        Returns:
            API key if configured, None otherwise
        """
        secrets = self._read_secrets()

        if provider not in secrets:
            logger.debug(f"No secret configured for provider: {provider}")
            return None

        api_key = secrets[provider].get("api_key")

        if api_key:
            redacted = self._redact_key(api_key)
            logger.debug(f"Retrieved secret for provider: {provider} (key: {redacted})")

        return api_key

    def delete_secret(self, provider: str) -> SecretInfo:
        """
        Delete API key for provider

        Args:
            provider: Provider ID

        Returns:
            SecretInfo with configured=False
        """
        logger.info(f"Deleting secret for provider: {provider}")

        secrets = self._read_secrets()

        if provider in secrets:
            del secrets[provider]
            self._write_secrets(secrets)

        return SecretInfo(
            provider=provider,
            configured=False,
            last4=None,
            updated_at=None,
        )

    def get_status(self, provider: str) -> SecretInfo:
        """
        Get secret status for provider (no actual key)

        Args:
            provider: Provider ID

        Returns:
            SecretInfo with metadata
        """
        secrets = self._read_secrets()

        if provider not in secrets:
            return SecretInfo(
                provider=provider,
                configured=False,
            )

        entry = secrets[provider]
        api_key = entry.get("api_key", "")

        return SecretInfo(
            provider=provider,
            configured=True,
            last4=api_key[-4:] if len(api_key) >= 4 else None,
            updated_at=entry.get("updated_at"),
        )

    def get_all_status(self) -> List[SecretInfo]:
        """
        Get status for all configured providers

        Returns:
            List of SecretInfo (no actual keys)
        """
        secrets = self._read_secrets()

        return [
            self.get_status(provider)
            for provider in secrets.keys()
        ]

    @staticmethod
    def _redact_key(api_key: str) -> str:
        """
        Redact API key for logging

        Shows only last 4 characters

        Args:
            api_key: Full API key

        Returns:
            Redacted string like "***a1b2"
        """
        if len(api_key) <= 4:
            return "***"

        return f"***{api_key[-4:]}"
