"""
BrainOS Index Build Job

Orchestrates the full index build process:
1. Validate repository
2. Extract entities/edges (Git, Doc, Code extractors)
3. Write to SQLite store
4. Generate manifest and report

Features:
- Idempotent: Same commit can be re-indexed without duplication
- Observable: Tracks counts, duration, errors
- Fail-soft: Handles missing Git gracefully
"""

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any

from ..store import (
    SQLiteStore,
    BuildManifest,
    save_manifest,
    create_graph_version,
    get_iso_timestamp
)
from ..extractors.git_extractor import GitExtractor
from ..extractors.doc_extractor import DocExtractor
from ..extractors.code_extractor import CodeExtractor


BRAINOS_VERSION = "0.1.0-alpha"


@dataclass
class BuildResult:
    """Result of an index build job."""
    manifest: BuildManifest
    stats: Dict[str, Any]
    errors: List[str]

    def is_successful(self) -> bool:
        """Check if build was successful."""
        return len(self.errors) == 0


class BrainIndexJob:
    """
    BrainOS Index Build Job.

    Orchestrates extraction and storage of knowledge graph.
    """

    @staticmethod
    def run(
        repo_path: str,
        commit: str = "HEAD",
        db_path: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> BuildResult:
        """
        Run index build job.

        Args:
            repo_path: Path to repository (absolute or relative)
            commit: Commit reference to index (default: "HEAD")
            db_path: Path to output database (default: <repo>/.brainos/index.db)
            config: Optional configuration dict

        Returns:
            BuildResult with manifest, stats, and errors

        Raises:
            RuntimeError: If git is not available
            ValueError: If not a git repository
        """
        config = config or {}
        errors = []

        # Resolve paths
        repo_path = str(Path(repo_path).resolve())

        if db_path is None:
            db_path = os.path.join(repo_path, '.brainos', 'index.db')

        manifest_path = db_path + '.manifest.json'

        # Record start time
        started_at = get_iso_timestamp()
        start_time = time.time()

        # Step 1: Initialize database
        store = SQLiteStore(db_path, auto_init=True)

        try:
            # Step 2: Extract from Git
            enabled_extractors = []
            all_entities = []
            all_edges = []

            if config is None or config.get("enable_git_extractor", True):
                git_extractor = GitExtractor(config={"commit": commit, "depth": 1})
                git_result = git_extractor.extract(Path(repo_path))
                all_entities.extend(git_result.entities)
                all_edges.extend(git_result.edges)
                enabled_extractors.append("git")

                # Get commit hash for graph version
                commit_hash = git_extractor.extract_commit_hash(Path(repo_path), commit)
                short_hash = commit_hash[:7]
            else:
                # Default commit hash if git extractor is disabled
                short_hash = "no-git"

            # Step 2b: Extract from Docs
            if config is None or config.get("enable_doc_extractor", True):
                doc_extractor = DocExtractor(config=config.get("doc_config", {}) if config else {})
                doc_result = doc_extractor.extract(Path(repo_path))
                all_entities.extend(doc_result.entities)
                all_edges.extend(doc_result.edges)
                errors.extend(doc_result.errors)
                enabled_extractors.append("doc")

            # Step 2c: Extract from Code (M3-P1)
            if config is None or config.get("enable_code_extractor", True):
                code_extractor = CodeExtractor(config=config.get("code_config", {}) if config else {})
                code_result = code_extractor.extract(Path(repo_path))
                all_entities.extend(code_result.entities)
                all_edges.extend(code_result.edges)
                errors.extend(code_result.errors)
                enabled_extractors.append("code")

            # Step 3: Write entities to store
            entity_id_map = {}  # key -> id mapping

            for entity in all_entities:
                # Convert EntityType enum to string
                entity_type_str = entity.type.value if hasattr(entity.type, 'value') else str(entity.type)

                entity_id = store.upsert_entity(
                    entity_type=entity_type_str,
                    key=entity.key,
                    name=entity.name,
                    attrs=entity.attrs
                )
                entity_id_map[entity.key] = entity_id

                # If this is a commit, add to FTS
                if entity_type_str == "commit":
                    # Get hash and message from attrs
                    commit_hash = entity.attrs.get('hash', '')
                    commit_message = entity.attrs.get('message', '')

                    if commit_hash and commit_message:
                        store.insert_fts_commit(
                            commit_hash=commit_hash,
                            message=commit_message
                        )

            # Step 4: Write edges and evidence
            for edge in all_edges:
                src_id = entity_id_map.get(edge.source)
                dst_id = entity_id_map.get(edge.target)

                if src_id is None or dst_id is None:
                    errors.append(
                        f"Edge references missing entity: {edge.source} -> {edge.target}"
                    )
                    continue

                # Get edge key (custom attribute or construct from ID)
                edge_key = getattr(edge, 'key', edge.id)

                edge_id = store.upsert_edge(
                    src_entity_id=src_id,
                    dst_entity_id=dst_id,
                    edge_type=str(edge.type.value),  # Convert enum to string
                    key=edge_key,
                    attrs=edge.attrs,
                    confidence=getattr(edge, 'confidence', 1.0)
                )

                # Write evidence (evidence is a list in Edge model)
                if hasattr(edge, 'evidence') and edge.evidence:
                    for evidence in edge.evidence:
                        # Convert span to dict if it's a string
                        span_dict = {}
                        if isinstance(evidence.span, str):
                            span_dict = {'text': evidence.span}
                        elif isinstance(evidence.span, dict):
                            span_dict = evidence.span
                        elif evidence.span is not None:
                            span_dict = {'value': str(evidence.span)}

                        store.insert_evidence(
                            edge_id=edge_id,
                            source_type=evidence.source_type,
                            source_ref=evidence.source_ref,
                            span=span_dict,
                            attrs=evidence.metadata if hasattr(evidence, 'metadata') else {}
                        )

            # Step 5: Get final counts
            stats = store.get_stats()

            # Step 6: Record build metadata
            finished_at = get_iso_timestamp()
            duration_ms = int((time.time() - start_time) * 1000)
            graph_version = create_graph_version(short_hash)

            store.save_build_metadata(
                graph_version=graph_version,
                source_commit=short_hash,
                repo_path=repo_path,
                built_at=time.time(),
                duration_ms=duration_ms,
                entity_count=stats['entities'],
                edge_count=stats['edges'],
                evidence_count=stats['evidence'],
                enabled_extractors=enabled_extractors,
                errors=errors
            )

            # Commit transaction
            if store.conn:
                store.conn.commit()

            # Step 7: Generate manifest
            manifest = BuildManifest(
                graph_version=graph_version,
                source_commit=short_hash,
                repo_path=repo_path,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                counts={
                    'entities': stats['entities'],
                    'edges': stats['edges'],
                    'evidence': stats['evidence']
                },
                enabled_extractors=enabled_extractors,
                errors=errors,
                brainos_version=BRAINOS_VERSION
            )

            save_manifest(manifest, manifest_path)

            return BuildResult(
                manifest=manifest,
                stats=stats,
                errors=errors
            )

        finally:
            store.close()
