"""Git .gitignore Management

This module provides automatic .gitignore management for AgentOS projects.
It ensures that runtime artifacts and sensitive files are not committed to Git.

Key Features:
1. Automatic .gitignore creation with AgentOS default rules
2. Smart merge (preserves user rules, adds AgentOS block)
3. Idempotent operations (safe to run multiple times)
4. Support for --no-gitignore flag in CLI

Created for Phase 4: .gitignore and change boundary control
"""

import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class GitignoreManager:
    """Manages .gitignore files for AgentOS projects

    Provides automatic creation and intelligent merging of .gitignore rules.
    Ensures AgentOS runtime artifacts are never committed to Git.
    """

    # Markers for AgentOS rules block
    AGENTOS_MARKER_START = "# --- AgentOS Generated Rules (Start) ---"
    AGENTOS_MARKER_END = "# --- AgentOS Generated Rules (End) ---"

    @classmethod
    def get_default_rules(cls) -> List[str]:
        """Get AgentOS default .gitignore rules

        These rules cover:
        - AgentOS runtime directories (.agentos/, task_runs/, diagnostics/)
        - Temporary files (*.agentos.tmp)
        - Python artifacts (__pycache__/, *.pyc, *.pyo, *.egg-info/)
        - Local secrets (local_secrets/, .env.local)
        - OS artifacts (.DS_Store, Thumbs.db)

        Returns:
            List of gitignore patterns
        """
        return [
            # AgentOS directories
            ".agentos/",
            "task_runs/",
            "diagnostics/",
            "local_secrets/",

            # AgentOS temporary files
            "*.agentos.tmp",
            "*.agentos.log",

            # Python artifacts
            "__pycache__/",
            "*.pyc",
            "*.pyo",
            "*.egg-info/",
            ".pytest_cache/",
            ".coverage",
            "htmlcov/",

            # Environment files (local only)
            ".env.local",
            "secrets.local.yaml",

            # OS artifacts
            ".DS_Store",
            "Thumbs.db",

            # Editor artifacts
            ".vscode/",
            ".idea/",
            "*.swp",
            "*.swo",
            "*~",
        ]

    def ensure_gitignore(
        self,
        repo_path: Path,
        *,
        force: bool = False,
        dry_run: bool = False,
    ) -> bool:
        """Ensure .gitignore exists and contains AgentOS rules

        This method is idempotent - safe to call multiple times.

        Args:
            repo_path: Path to repository root
            force: If True, overwrite existing AgentOS block
            dry_run: If True, don't write changes (for testing)

        Returns:
            True if .gitignore was modified, False otherwise

        Raises:
            ValueError: If repo_path is not a directory
        """
        if not repo_path.is_dir():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        gitignore_path = repo_path / ".gitignore"

        # If .gitignore doesn't exist, create it
        if not gitignore_path.exists():
            logger.info(f"Creating new .gitignore at {gitignore_path}")
            if not dry_run:
                self._create_gitignore(gitignore_path)
            return True

        # If .gitignore exists, check if AgentOS rules are present
        content = gitignore_path.read_text(encoding="utf-8")

        has_agentos_block = (
            self.AGENTOS_MARKER_START in content and
            self.AGENTOS_MARKER_END in content
        )

        if has_agentos_block and not force:
            logger.debug(f".gitignore already has AgentOS rules: {gitignore_path}")
            return False

        # Merge AgentOS rules
        logger.info(f"Merging AgentOS rules into {gitignore_path}")
        if not dry_run:
            self._merge_rules(gitignore_path, content, force=force)
        return True

    def merge_rules(
        self,
        repo_path: Path,
        new_rules: List[str],
        *,
        marker_prefix: str = "Custom",
        dry_run: bool = False,
    ) -> bool:
        """Merge custom rules into existing .gitignore

        Unlike ensure_gitignore(), this allows merging arbitrary rules.

        Args:
            repo_path: Path to repository root
            new_rules: List of gitignore patterns to add
            marker_prefix: Prefix for marker comments (e.g., "Custom", "Project")
            dry_run: If True, don't write changes

        Returns:
            True if .gitignore was modified, False otherwise

        Raises:
            ValueError: If repo_path is not a directory or .gitignore doesn't exist
        """
        if not repo_path.is_dir():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        gitignore_path = repo_path / ".gitignore"

        if not gitignore_path.exists():
            raise ValueError(f".gitignore does not exist: {gitignore_path}")

        content = gitignore_path.read_text(encoding="utf-8")

        # Create markers for custom rules
        start_marker = f"# --- {marker_prefix} Rules (Start) ---"
        end_marker = f"# --- {marker_prefix} Rules (End) ---"

        # Check if custom block already exists
        if start_marker in content and end_marker in content:
            logger.warning(f"{marker_prefix} rules block already exists in {gitignore_path}")
            return False

        # Append custom rules block
        new_block = self._create_rules_block(new_rules, start_marker, end_marker)

        if not dry_run:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                if not content.endswith("\n"):
                    f.write("\n")
                f.write("\n")
                f.write(new_block)
                f.write("\n")

        logger.info(f"Merged {len(new_rules)} custom rules into {gitignore_path}")
        return True

    def remove_agentos_rules(
        self,
        repo_path: Path,
        *,
        dry_run: bool = False,
    ) -> bool:
        """Remove AgentOS rules block from .gitignore

        Useful for uninstalling or cleaning up.

        Args:
            repo_path: Path to repository root
            dry_run: If True, don't write changes

        Returns:
            True if .gitignore was modified, False otherwise
        """
        gitignore_path = repo_path / ".gitignore"

        if not gitignore_path.exists():
            logger.debug(f".gitignore does not exist: {gitignore_path}")
            return False

        content = gitignore_path.read_text(encoding="utf-8")

        if self.AGENTOS_MARKER_START not in content:
            logger.debug(f"No AgentOS rules found in {gitignore_path}")
            return False

        # Remove AgentOS block
        new_content = self._remove_rules_block(
            content,
            self.AGENTOS_MARKER_START,
            self.AGENTOS_MARKER_END,
        )

        if not dry_run:
            gitignore_path.write_text(new_content, encoding="utf-8")

        logger.info(f"Removed AgentOS rules from {gitignore_path}")
        return True

    def _create_gitignore(self, gitignore_path: Path) -> None:
        """Create new .gitignore with AgentOS rules"""
        rules = self.get_default_rules()
        block = self._create_rules_block(
            rules,
            self.AGENTOS_MARKER_START,
            self.AGENTOS_MARKER_END,
        )

        gitignore_path.write_text(block + "\n", encoding="utf-8")

    def _merge_rules(
        self,
        gitignore_path: Path,
        existing_content: str,
        force: bool = False,
    ) -> None:
        """Merge AgentOS rules into existing .gitignore

        Strategy:
        1. If AgentOS block exists and force=True, replace it
        2. Otherwise, append AgentOS block to end of file
        """
        if force and self.AGENTOS_MARKER_START in existing_content:
            # Remove old AgentOS block
            new_content = self._remove_rules_block(
                existing_content,
                self.AGENTOS_MARKER_START,
                self.AGENTOS_MARKER_END,
            )
        else:
            new_content = existing_content

        # Append AgentOS block
        rules = self.get_default_rules()
        block = self._create_rules_block(
            rules,
            self.AGENTOS_MARKER_START,
            self.AGENTOS_MARKER_END,
        )

        # Ensure trailing newline before appending
        if not new_content.endswith("\n"):
            new_content += "\n"

        new_content += "\n" + block + "\n"

        gitignore_path.write_text(new_content, encoding="utf-8")

    def _create_rules_block(
        self,
        rules: List[str],
        start_marker: str,
        end_marker: str,
    ) -> str:
        """Create a rules block with markers

        Format:
            # --- Start Marker ---
            rule1
            rule2
            # --- End Marker ---
        """
        lines = [start_marker]
        lines.extend(rules)
        lines.append(end_marker)
        return "\n".join(lines)

    def _remove_rules_block(
        self,
        content: str,
        start_marker: str,
        end_marker: str,
    ) -> str:
        """Remove a rules block from content

        Removes everything between start_marker and end_marker (inclusive).
        """
        lines = content.split("\n")
        new_lines = []

        in_block = False
        for line in lines:
            if start_marker in line:
                in_block = True
                continue

            if end_marker in line:
                in_block = False
                continue

            if not in_block:
                new_lines.append(line)

        # Clean up extra blank lines
        result = "\n".join(new_lines)

        # Replace multiple consecutive blank lines with single blank line
        while "\n\n\n" in result:
            result = result.replace("\n\n\n", "\n\n")

        return result.strip() + "\n" if result.strip() else ""
