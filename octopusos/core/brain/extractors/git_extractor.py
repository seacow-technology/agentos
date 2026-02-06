"""
BrainOS Git Extractor

Extracts information from Git history to build Commit and File entities,
as well as MODIFIES relationships.

Extracted content:
1. Commit entities (hash, author, date, message)
2. File entities (from git log)
3. MODIFIES relationships (Commit → File)

Evidence sources:
- source_type: "git"
- source_ref: commit hash
- span: commit metadata

Performance considerations:
- Large repos may have tens of thousands of commits
- Support max_commits limit (default: no limit for M1 HEAD-only)
- Support depth control (M1: depth=1 for HEAD only)
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from .base import BaseExtractor, ExtractionResult
from agentos.core.brain.models import Commit, File, Edge, EdgeType, Evidence


class GitExtractor(BaseExtractor):
    """
    Git history extractor.

    Extracts Commit and File entities, plus MODIFIES relationships.

    Config (M1):
        depth: Number of commits to process (default: 1 for HEAD only)
        commit: Specific commit to extract (default: "HEAD")

    Example:
        >>> extractor = GitExtractor(config={"depth": 1})
        >>> result = extractor.extract(Path("/path/to/repo"))
        >>> print(f"Extracted {len(result.entities)} entities")
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="GitExtractor",
            version="0.1.0",
            config=config or {}
        )
        self.depth = self.config.get("depth", 1)
        self.commit_ref = self.config.get("commit", "HEAD")

    def validate_git_repo(self, repo_path: Path) -> None:
        """
        Validate that path is a git repository.

        Raises:
            RuntimeError: If git is not available
            ValueError: If not a git repository
        """
        # Check git is available
        try:
            subprocess.run(
                ['git', '--version'],
                check=True,
                capture_output=True,
                timeout=5
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "Git is not available. Please install git:\n"
                "https://git-scm.com/downloads"
            )

        # Check this is a git repo
        if not (repo_path / '.git').exists():
            raise ValueError(
                f"'{repo_path}' is not a git repository. "
                "Please run this command in a git repository root."
            )

    def extract_commit_hash(self, repo_path: Path, commit_ref: str = "HEAD") -> str:
        """
        Get full commit hash for a reference.

        Args:
            repo_path: Repository root path
            commit_ref: Commit reference (default: "HEAD")

        Returns:
            Full commit hash

        Raises:
            RuntimeError: If git command fails
        """
        try:
            result = subprocess.run(
                ['git', 'rev-parse', commit_ref],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to resolve commit '{commit_ref}': {e.stderr}"
            )

    def extract_commit_info(
        self,
        repo_path: Path,
        commit_hash: str
    ) -> Dict[str, Any]:
        """
        Extract detailed information about a commit.

        Format: hash|author_name|author_email|timestamp|subject

        Args:
            repo_path: Repository root path
            commit_hash: Commit hash to extract

        Returns:
            Dict with commit metadata
        """
        try:
            # Get commit metadata
            result = subprocess.run(
                [
                    'git', 'show',
                    '--format=%H|%an|%ae|%at|%s',
                    '--name-status',
                    '--no-patch',
                    commit_hash
                ],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
                timeout=10
            )

            lines = result.stdout.strip().split('\n')
            if not lines:
                raise RuntimeError(f"Empty output for commit {commit_hash}")

            # Parse first line: hash|author|email|timestamp|subject
            parts = lines[0].split('|', 4)
            if len(parts) != 5:
                raise RuntimeError(f"Invalid commit format: {lines[0]}")

            commit_hash, author_name, author_email, timestamp, message = parts

            return {
                'hash': commit_hash,
                'author_name': author_name,
                'author_email': author_email,
                'timestamp': int(timestamp),
                'message': message
            }

        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to extract commit info for {commit_hash}: {e.stderr}"
            )

    def extract_modified_files(
        self,
        repo_path: Path,
        commit_hash: str
    ) -> List[Tuple[str, str]]:
        """
        Extract list of files modified in a commit.

        Args:
            repo_path: Repository root path
            commit_hash: Commit hash

        Returns:
            List of (status, file_path) tuples
            Status: A (added), M (modified), D (deleted)
        """
        try:
            result = subprocess.run(
                [
                    'git', 'show',
                    '--format=',
                    '--name-status',
                    commit_hash
                ],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
                timeout=10
            )

            modified_files = []
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if not line:
                    continue

                # Format: <status><tab><path>
                parts = line.split('\t', 1)
                if len(parts) != 2:
                    continue

                status, file_path = parts
                # Normalize to POSIX style
                file_path = Path(file_path).as_posix()
                modified_files.append((status, file_path))

            return modified_files

        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to extract modified files for {commit_hash}: {e.stderr}"
            )

    def extract_commit_message_terms(self, message: str) -> List[str]:
        """
        Extract key terms from commit message (simple implementation).

        M1 Implementation: Basic tokenization + stopword filtering

        Args:
            message: Commit message

        Returns:
            List of extracted terms
        """
        # Simple stopwords
        stopwords = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for',
            'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on',
            'that', 'the', 'to', 'was', 'will', 'with'
        }

        # Tokenize: split on whitespace and punctuation
        tokens = re.findall(r'\b[a-zA-Z]{3,}\b', message.lower())

        # Filter stopwords and duplicates
        terms = [t for t in tokens if t not in stopwords]

        # Return unique terms (preserve order)
        seen = set()
        unique_terms = []
        for term in terms:
            if term not in seen:
                seen.add(term)
                unique_terms.append(term)

        return unique_terms

    def extract(
        self,
        repo_path: Path,
        incremental: bool = False,
        **kwargs
    ) -> ExtractionResult:
        """
        Extract Git history information.

        Args:
            repo_path: Repository root path
            incremental: Whether to do incremental extraction (not supported in M1)
            **kwargs: Additional arguments

        Returns:
            ExtractionResult with Commit, File entities and MODIFIES edges

        Raises:
            RuntimeError: If git is not available
            ValueError: If not a git repository
        """
        # Validate git availability and repo
        self.validate_git_repo(repo_path)

        entities = []
        edges = []
        files_seen = set()

        # M1: Extract HEAD commit only (depth=1)
        commit_hash = self.extract_commit_hash(repo_path, self.commit_ref)
        short_hash = commit_hash[:7]

        # Get commit info
        commit_info = self.extract_commit_info(repo_path, commit_hash)

        # Create Commit entity
        commit_key = f"commit:{short_hash}"
        commit_entity = Commit(
            id=commit_key,
            key=commit_key,
            name=f"Commit {short_hash}",
            # Pass additional attributes as kwargs
            hash=commit_hash,
            short_hash=short_hash,
            author_name=commit_info['author_name'],
            author_email=commit_info['author_email'],
            timestamp=commit_info['timestamp'],
            message=commit_info['message']
        )
        entities.append(commit_entity)

        # Extract modified files
        modified_files = self.extract_modified_files(repo_path, commit_hash)

        for status, file_path in modified_files:
            # Create File entity if not seen
            file_key = f"file:{file_path}"

            if file_key not in files_seen:
                file_entity = File(
                    id=file_key,
                    key=file_key,
                    name=file_path,
                    # Pass additional attributes as kwargs
                    path=file_path,
                    file_type=Path(file_path).suffix.lstrip('.') or 'unknown'
                )
                entities.append(file_entity)
                files_seen.add(file_key)

            # Create MODIFIES edge with evidence
            edge_key = f"MODIFIES|{commit_key}|{file_key}"

            # Create Evidence
            evidence = Evidence(
                source_type="git",
                source_ref=commit_hash,
                span=f"{file_path}:{status}",  # "path/to/file:M"
                confidence=1.0
            )

            edge = Edge(
                id=edge_key,
                source=commit_key,
                target=file_key,
                type=EdgeType.MODIFIES,
                evidence=[evidence],  # Must have evidence list
                attrs={'status': status}  # A/M/D
            )

            # Store key for idempotence (custom attribute)
            edge.key = edge_key

            edges.append(edge)

        return ExtractionResult(
            entities=entities,
            edges=edges,
            stats={
                "commits_processed": 1,
                "files_discovered": len(files_seen),
                "modifies_edges": len(edges),
            },
            metadata=self.get_metadata()
        )
