"""Git Client with Authentication Support

Extends the base GitClient with credential injection for clone/pull/push operations.
"""

import os
import re
import subprocess
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict
from urllib.parse import urlparse, urlunparse

from agentos.core.infra.git_client import GitClient
from agentos.core.git.credentials import (
    AuthProfile,
    AuthProfileType,
    TokenProvider,
    ValidationStatus,
    CredentialsManager,
)

logger = logging.getLogger(__name__)


@dataclass
class ProbeResult:
    """Repository permission probe result"""
    can_read: bool
    can_write: bool
    error_message: Optional[str]
    remote_info: Dict[str, any]  # branches, tags, etc.
    probed_at: datetime


class GitClientWithAuth:
    """Git client with authentication support

    Provides methods for clone/pull/push with automatic credential injection.
    Supports SSH keys, PAT tokens, and environment variable fallback.
    """

    def __init__(self, credentials_manager: Optional[CredentialsManager] = None):
        self.credentials = credentials_manager or CredentialsManager()
        # Cache for probe results (remote_url -> ProbeResult)
        self._probe_cache: Dict[str, ProbeResult] = {}
        self._cache_ttl = timedelta(minutes=15)

    def _inject_token_to_url(self, url: str, token: str) -> str:
        """Inject PAT token into HTTPS URL

        Example:
            https://github.com/user/repo.git
            -> https://x-access-token:<token>@github.com/user/repo.git
        """
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Cannot inject token into non-HTTP URL: {url}")

        # Use x-access-token as username (GitHub/GitLab standard)
        netloc_with_auth = f"x-access-token:{token}@{parsed.netloc}"

        return urlunparse((
            parsed.scheme,
            netloc_with_auth,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        ))

    def _prepare_ssh_env(self, ssh_key_path: str) -> dict:
        """Prepare environment variables for SSH authentication

        Uses GIT_SSH_COMMAND to specify SSH key.
        """
        env = os.environ.copy()

        # Expand home directory
        key_path = Path(ssh_key_path).expanduser()

        if not key_path.exists():
            raise FileNotFoundError(f"SSH key not found: {key_path}")

        # Set GIT_SSH_COMMAND to use specific key
        # -i: identity file
        # -o StrictHostKeyChecking=no: disable host key checking (optional)
        env["GIT_SSH_COMMAND"] = f"ssh -i {key_path} -o StrictHostKeyChecking=accept-new"

        return env

    def clone(
        self,
        remote_url: str,
        dest_path: Path,
        auth_profile: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> GitClient:
        """Clone a repository with authentication

        Args:
            remote_url: Remote repository URL
            dest_path: Destination path
            auth_profile: Auth profile name (optional, falls back to env vars)
            branch: Branch to clone (optional)

        Returns:
            GitClient instance for the cloned repo
        """
        profile = None
        if auth_profile:
            profile = self.credentials.get_profile(auth_profile)
            if not profile:
                raise ValueError(f"Auth profile not found: {auth_profile}")

        # Prepare git clone command
        cmd = ["git", "clone"]

        if branch:
            cmd.extend(["-b", branch])

        # Apply authentication
        env = os.environ.copy()
        effective_url = remote_url

        if profile:
            if profile.profile_type == AuthProfileType.SSH_KEY:
                # SSH key authentication
                env = self._prepare_ssh_env(profile.ssh_key_path)
                logger.info(f"Cloning with SSH key: {profile.ssh_key_path}")

            elif profile.profile_type == AuthProfileType.PAT_TOKEN:
                # PAT token authentication
                effective_url = self._inject_token_to_url(remote_url, profile.token)
                logger.info(f"Cloning with PAT token (provider={profile.token_provider})")

            elif profile.profile_type == AuthProfileType.NETRC:
                # Netrc authentication (git uses .netrc automatically)
                logger.info(f"Cloning with netrc (machine={profile.netrc_machine})")
        else:
            # Try environment variable fallback
            parsed = urlparse(remote_url)
            if parsed.netloc:
                for provider in TokenProvider:
                    token = self.credentials.get_from_env(provider)
                    if token and provider.value in parsed.netloc:
                        effective_url = self._inject_token_to_url(remote_url, token)
                        logger.info(f"Cloning with env token (provider={provider})")
                        break

        cmd.extend([effective_url, str(dest_path)])

        # Execute clone
        try:
            result = subprocess.run(
                cmd,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            logger.info(f"Successfully cloned: {remote_url} -> {dest_path}")

            # Log usage
            if profile:
                self.credentials.log_usage(
                    profile_id=profile.profile_id,
                    operation="clone",
                    status="success",
                    metadata={"url": remote_url, "dest": str(dest_path)},
                )

            # Return GitClient for further operations
            return GitClient(dest_path)

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or str(e)
            logger.error(f"Clone failed: {error_msg}")

            # Log failure
            if profile:
                self.credentials.log_usage(
                    profile_id=profile.profile_id,
                    operation="clone",
                    status="failure",
                    error_message=error_msg,
                    metadata={"url": remote_url},
                )

            raise RuntimeError(f"Git clone failed: {error_msg}")

    def pull(
        self,
        repo_path: Path,
        auth_profile: Optional[str] = None,
        remote: str = "origin",
        branch: Optional[str] = None,
    ):
        """Pull updates from remote with authentication

        Args:
            repo_path: Local repository path
            auth_profile: Auth profile name (optional)
            remote: Remote name (default: origin)
            branch: Branch to pull (optional)
        """
        profile = None
        if auth_profile:
            profile = self.credentials.get_profile(auth_profile)
            if not profile:
                raise ValueError(f"Auth profile not found: {auth_profile}")

        # Prepare git pull command
        cmd = ["git", "-C", str(repo_path), "pull", remote]

        if branch:
            cmd.append(branch)

        # Apply authentication
        env = os.environ.copy()

        if profile:
            if profile.profile_type == AuthProfileType.SSH_KEY:
                env = self._prepare_ssh_env(profile.ssh_key_path)

            # Note: For PAT tokens, we need to set credential helper or modify remote URL
            # For simplicity, assume remote URL already has token or use SSH

        # Execute pull
        try:
            result = subprocess.run(
                cmd,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            logger.info(f"Successfully pulled: {repo_path}")

            if profile:
                self.credentials.log_usage(
                    profile_id=profile.profile_id,
                    operation="pull",
                    status="success",
                    metadata={"repo": str(repo_path)},
                )

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or str(e)
            logger.error(f"Pull failed: {error_msg}")

            if profile:
                self.credentials.log_usage(
                    profile_id=profile.profile_id,
                    operation="pull",
                    status="failure",
                    error_message=error_msg,
                    metadata={"repo": str(repo_path)},
                )

            raise RuntimeError(f"Git pull failed: {error_msg}")

    def push(
        self,
        repo_path: Path,
        auth_profile: Optional[str] = None,
        remote: str = "origin",
        branch: Optional[str] = None,
    ):
        """Push changes to remote with authentication

        Args:
            repo_path: Local repository path
            auth_profile: Auth profile name (optional)
            remote: Remote name (default: origin)
            branch: Branch to push (optional)
        """
        profile = None
        if auth_profile:
            profile = self.credentials.get_profile(auth_profile)
            if not profile:
                raise ValueError(f"Auth profile not found: {auth_profile}")

        # Prepare git push command
        cmd = ["git", "-C", str(repo_path), "push", remote]

        if branch:
            cmd.append(branch)

        # Apply authentication
        env = os.environ.copy()

        if profile:
            if profile.profile_type == AuthProfileType.SSH_KEY:
                env = self._prepare_ssh_env(profile.ssh_key_path)

        # Execute push
        try:
            result = subprocess.run(
                cmd,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            logger.info(f"Successfully pushed: {repo_path}")

            if profile:
                self.credentials.log_usage(
                    profile_id=profile.profile_id,
                    operation="push",
                    status="success",
                    metadata={"repo": str(repo_path)},
                )

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or str(e)
            logger.error(f"Push failed: {error_msg}")

            if profile:
                self.credentials.log_usage(
                    profile_id=profile.profile_id,
                    operation="push",
                    status="failure",
                    error_message=error_msg,
                    metadata={"repo": str(repo_path)},
                )

            raise RuntimeError(f"Git push failed: {error_msg}")

    def validate_credentials(
        self,
        auth_profile: str,
        test_url: Optional[str] = None,
    ) -> bool:
        """Validate credentials by attempting git ls-remote

        Args:
            auth_profile: Auth profile name
            test_url: URL to test (optional, uses default provider URL)

        Returns:
            True if credentials are valid
        """
        profile = self.credentials.get_profile(auth_profile)
        if not profile:
            raise ValueError(f"Auth profile not found: {auth_profile}")

        # Determine test URL
        if not test_url:
            if profile.profile_type == AuthProfileType.PAT_TOKEN:
                # Use default provider test URL
                provider_urls = {
                    TokenProvider.GITHUB: "https://github.com",
                    TokenProvider.GITLAB: "https://gitlab.com",
                    TokenProvider.BITBUCKET: "https://bitbucket.org",
                }
                test_url = provider_urls.get(profile.token_provider, "https://github.com")
            else:
                raise ValueError("test_url required for non-PAT profiles")

        # Prepare git ls-remote command (lightweight test)
        cmd = ["git", "ls-remote", "--exit-code"]

        env = os.environ.copy()
        effective_url = test_url

        if profile.profile_type == AuthProfileType.SSH_KEY:
            env = self._prepare_ssh_env(profile.ssh_key_path)

        elif profile.profile_type == AuthProfileType.PAT_TOKEN:
            effective_url = self._inject_token_to_url(test_url, profile.token)

        cmd.append(effective_url)

        # Execute validation
        try:
            result = subprocess.run(
                cmd,
                env=env,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )

            logger.info(f"Credentials validated: {auth_profile}")

            # Update validation status
            self.credentials.update_validation_status(
                profile_name=auth_profile,
                status=ValidationStatus.VALID,
                message="Validation successful",
            )

            # Log usage
            self.credentials.log_usage(
                profile_id=profile.profile_id,
                operation="validate",
                status="success",
                metadata={"test_url": test_url},
            )

            return True

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or str(e)
            logger.warning(f"Credentials validation failed: {error_msg}")

            # Update validation status
            self.credentials.update_validation_status(
                profile_name=auth_profile,
                status=ValidationStatus.INVALID,
                message=f"Validation failed: {error_msg}",
            )

            # Log usage
            self.credentials.log_usage(
                profile_id=profile.profile_id,
                operation="validate",
                status="failure",
                error_message=error_msg,
                metadata={"test_url": test_url},
            )

            return False

        except subprocess.TimeoutExpired:
            logger.warning(f"Credentials validation timeout: {auth_profile}")

            self.credentials.update_validation_status(
                profile_name=auth_profile,
                status=ValidationStatus.INVALID,
                message="Validation timeout",
            )

            return False

    def probe(
        self,
        remote_url: str,
        profile: Optional[AuthProfile] = None,
        use_cache: bool = True,
    ) -> ProbeResult:
        """Probe repository permissions (read/write)

        Args:
            remote_url: Remote repository URL
            profile: Auth profile (optional, falls back to env vars)
            use_cache: Use cached results if available (default: True)

        Returns:
            ProbeResult with read/write permissions and remote info
        """
        # Check cache first
        cache_key = f"{remote_url}:{profile.profile_id if profile else 'env'}"
        if use_cache and cache_key in self._probe_cache:
            cached = self._probe_cache[cache_key]
            age = datetime.now() - cached.probed_at
            if age < self._cache_ttl:
                logger.debug(f"Using cached probe result for {remote_url}")
                return cached

        # Probe read permission
        can_read, read_error, remote_info = self._probe_read_access(remote_url, profile)

        # Probe write permission (only if read succeeds)
        can_write = False
        write_error = None
        if can_read:
            can_write, write_error = self._probe_write_access(remote_url, profile)

        # Combine error messages
        error_message = None
        if not can_read:
            error_message = self._diagnose_error(remote_url, profile, read_error, "read")
        elif not can_write:
            error_message = self._diagnose_error(remote_url, profile, write_error, "write")

        result = ProbeResult(
            can_read=can_read,
            can_write=can_write,
            error_message=error_message,
            remote_info=remote_info,
            probed_at=datetime.now(),
        )

        # Cache the result
        self._probe_cache[cache_key] = result

        return result

    def _probe_read_access(
        self,
        remote_url: str,
        profile: Optional[AuthProfile],
    ) -> tuple[bool, Optional[str], Dict[str, any]]:
        """Probe read access using git ls-remote

        Returns:
            (can_read, error_message, remote_info)
        """
        cmd = ["git", "ls-remote", "--heads", "--tags"]

        # Apply authentication
        env = os.environ.copy()
        effective_url = remote_url

        if profile:
            if profile.profile_type == AuthProfileType.SSH_KEY:
                try:
                    env = self._prepare_ssh_env(profile.ssh_key_path)
                except FileNotFoundError as e:
                    return False, str(e), {}

            elif profile.profile_type == AuthProfileType.PAT_TOKEN:
                try:
                    effective_url = self._inject_token_to_url(remote_url, profile.token)
                except ValueError as e:
                    return False, str(e), {}
        else:
            # Try environment variable fallback
            parsed = urlparse(remote_url)
            if parsed.netloc:
                for provider in TokenProvider:
                    token = self.credentials.get_from_env(provider)
                    if token and provider.value in parsed.netloc:
                        try:
                            effective_url = self._inject_token_to_url(remote_url, token)
                        except ValueError:
                            pass
                        break

        cmd.append(effective_url)

        # Execute ls-remote
        try:
            result = subprocess.run(
                cmd,
                env=env,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Parse remote info (branches and tags)
            remote_info = self._parse_ls_remote_output(result.stdout)

            logger.info(f"Read access confirmed for {remote_url}")
            return True, None, remote_info

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or str(e)
            logger.warning(f"Read access denied for {remote_url}: {error_msg}")
            return False, error_msg, {}

        except subprocess.TimeoutExpired:
            error_msg = "Connection timeout"
            logger.warning(f"Read access timeout for {remote_url}")
            return False, error_msg, {}

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Unexpected error probing read access: {error_msg}")
            return False, error_msg, {}

    def _probe_write_access(
        self,
        remote_url: str,
        profile: Optional[AuthProfile],
    ) -> tuple[bool, Optional[str]]:
        """Probe write access using conservative strategy

        Strategy:
        1. For GitHub/GitLab: Use API to check permissions (recommended)
        2. For SSH: Assume write access if read succeeds (conservative)
        3. For HTTPS with PAT: Check token scopes (conservative)

        Note: We avoid creating test branches to prevent polluting remote repos.

        Returns:
            (can_write, error_message)
        """
        parsed = urlparse(remote_url)
        netloc = parsed.netloc.lower()

        # Strategy 1: For GitHub, check via PAT token scopes
        if "github.com" in netloc:
            if profile and profile.profile_type == AuthProfileType.PAT_TOKEN:
                # Check if token has 'repo' scope (write access)
                if profile.token_scopes and "repo" in profile.token_scopes:
                    logger.info(f"Write access inferred from GitHub PAT scopes")
                    return True, None
                else:
                    logger.warning(f"GitHub PAT lacks 'repo' scope")
                    return False, "GitHub PAT lacks 'repo' scope for write access"

        # Strategy 2: For GitLab, check via PAT token scopes
        if "gitlab.com" in netloc or "gitlab" in netloc:
            if profile and profile.profile_type == AuthProfileType.PAT_TOKEN:
                # GitLab tokens with 'write_repository' scope have write access
                if profile.token_scopes and any(
                    scope in ["write_repository", "api"] for scope in profile.token_scopes
                ):
                    logger.info(f"Write access inferred from GitLab PAT scopes")
                    return True, None
                else:
                    logger.warning(f"GitLab PAT lacks write scopes")
                    return False, "GitLab PAT lacks 'write_repository' or 'api' scope"

        # Strategy 3: For SSH, assume write access if read succeeds (conservative)
        if parsed.scheme in ("ssh", "git") or remote_url.startswith("git@"):
            if profile and profile.profile_type == AuthProfileType.SSH_KEY:
                logger.info(f"Write access assumed for SSH (conservative)")
                return True, None

        # Strategy 4: Conservative fallback - cannot determine write access
        logger.warning(f"Cannot determine write access for {remote_url}, assuming read-only")
        return False, "Write access cannot be determined (conservative strategy)"

    def _parse_ls_remote_output(self, output: str) -> Dict[str, any]:
        """Parse git ls-remote output to extract branches and tags

        Example output:
            abc123...  refs/heads/main
            def456...  refs/heads/develop
            789xyz...  refs/tags/v1.0.0
        """
        branches = []
        tags = []

        for line in output.strip().split("\n"):
            if not line:
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            ref = parts[1]

            if ref.startswith("refs/heads/"):
                branch_name = ref.replace("refs/heads/", "")
                branches.append(branch_name)
            elif ref.startswith("refs/tags/"):
                tag_name = ref.replace("refs/tags/", "")
                tags.append(tag_name)

        return {
            "branches": branches,
            "tags": tags,
            "total_refs": len(branches) + len(tags),
        }

    def _diagnose_error(
        self,
        remote_url: str,
        profile: Optional[AuthProfile],
        error_output: Optional[str],
        access_type: str,  # "read" or "write"
    ) -> str:
        """Diagnose permission error and provide actionable hint

        Returns:
            User-friendly error message with actionable hints
        """
        if not error_output:
            error_output = ""

        parsed = urlparse(remote_url)
        netloc = parsed.netloc.lower()

        # SSH authentication failure
        if "permission denied" in error_output.lower() or "publickey" in error_output.lower():
            if profile and profile.profile_type == AuthProfileType.SSH_KEY:
                return (
                    f"SSH key authentication failed for {remote_url}.\n"
                    f"Hints:\n"
                    f"  - Verify SSH key is added to your Git provider: {profile.ssh_key_path}\n"
                    f"  - Check key permissions: chmod 600 {profile.ssh_key_path}\n"
                    f"  - Test SSH connection: ssh -T git@{netloc}\n"
                    f"  - Verify ~/.ssh/config has correct settings"
                )
            else:
                return (
                    f"SSH key not configured or invalid for {remote_url}.\n"
                    f"Hints:\n"
                    f"  - Configure an SSH key auth profile\n"
                    f"  - Or use HTTPS with PAT token instead"
                )

        # PAT token authentication failure
        if "authentication failed" in error_output.lower() or "401" in error_output:
            if "github.com" in netloc:
                return (
                    f"GitHub authentication failed for {remote_url}.\n"
                    f"Hints:\n"
                    f"  - PAT token is invalid or expired\n"
                    f"  - Generate new token at: https://github.com/settings/tokens\n"
                    f"  - Required scopes: 'repo' (read + write) or 'read:org' (read only)\n"
                    f"  - Update auth profile with new token"
                )
            elif "gitlab.com" in netloc or "gitlab" in netloc:
                return (
                    f"GitLab authentication failed for {remote_url}.\n"
                    f"Hints:\n"
                    f"  - PAT token is invalid or expired\n"
                    f"  - Generate new token at: https://gitlab.com/-/profile/personal_access_tokens\n"
                    f"  - Required scopes: 'read_repository' (read) or 'write_repository' (write)\n"
                    f"  - Update auth profile with new token"
                )
            else:
                return (
                    f"Authentication failed for {remote_url}.\n"
                    f"Hints:\n"
                    f"  - PAT token is invalid or expired\n"
                    f"  - Check token has correct permissions\n"
                    f"  - Update auth profile with new token"
                )

        # Permission denied (403)
        if "403" in error_output or "forbidden" in error_output.lower():
            if access_type == "write":
                if "github.com" in netloc:
                    return (
                        f"Write access denied for {remote_url}.\n"
                        f"Hints:\n"
                        f"  - GitHub PAT token needs 'repo' scope for write access\n"
                        f"  - Verify at: https://github.com/settings/tokens\n"
                        f"  - You may have read-only access to this repository"
                    )
                elif "gitlab.com" in netloc or "gitlab" in netloc:
                    return (
                        f"Write access denied for {remote_url}.\n"
                        f"Hints:\n"
                        f"  - GitLab PAT token needs 'write_repository' or 'api' scope\n"
                        f"  - Verify at: https://gitlab.com/-/profile/personal_access_tokens\n"
                        f"  - Check you have Maintainer or Owner role in the project"
                    )
                else:
                    return (
                        f"Write access denied for {remote_url}.\n"
                        f"Hints:\n"
                        f"  - Token may lack write permissions\n"
                        f"  - Check repository access level\n"
                        f"  - You may need to request write access from repository owner"
                    )
            else:
                return (
                    f"Access denied for {remote_url}.\n"
                    f"Hints:\n"
                    f"  - Repository may be private\n"
                    f"  - Token may lack permissions\n"
                    f"  - Verify you have access to this repository"
                )

        # Repository not found (404)
        if "404" in error_output or "not found" in error_output.lower():
            return (
                f"Repository not found: {remote_url}.\n"
                f"Hints:\n"
                f"  - Verify URL is correct\n"
                f"  - Repository may be private (check authentication)\n"
                f"  - Repository may have been deleted or renamed"
            )

        # Network/connection error
        if "timeout" in error_output.lower() or "timed out" in error_output.lower():
            return (
                f"Connection timeout for {remote_url}.\n"
                f"Hints:\n"
                f"  - Check network connection\n"
                f"  - Repository server may be down\n"
                f"  - Try again later"
            )

        if "could not resolve" in error_output.lower() or "unknown host" in error_output.lower():
            return (
                f"Cannot resolve hostname for {remote_url}.\n"
                f"Hints:\n"
                f"  - Check URL is correct\n"
                f"  - Check DNS settings\n"
                f"  - Check network connection"
            )

        # Generic error
        return (
            f"{access_type.capitalize()} access failed for {remote_url}.\n"
            f"Error: {error_output}\n"
            f"Hints:\n"
            f"  - Check authentication configuration\n"
            f"  - Verify repository URL is correct\n"
            f"  - Test connection manually: git ls-remote {remote_url}"
        )
