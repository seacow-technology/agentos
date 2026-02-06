"""
Evidence Link Graph for AgentOS v3

Builds and queries evidence chains linking related operations.

Core Responsibilities:
1. Create evidence chains: decision → action → memory → state_change
2. Build bidirectional links (forward and backward)
3. Query chains from any anchor point
4. Generate visualizations (graph format for UI)
5. Verify chain integrity

Design Principles:
- Bidirectional links (cause → effect, effect ← cause)
- Multi-hop traversal (find all related evidence)
- Fast queries (< 100ms for typical chains)
- Graph visualization ready (JSON format)

Example Chain:
    Decision (dec-123)
        ↓ caused_by
    Action (exec-456)
        ↓ resulted_in
    Memory (mem-789)
        ↓ modified
    State (state-999)

Schema: v51 (evidence_chains, evidence_chain_links)
"""

import logging
import json
import sqlite3
from typing import Dict, List, Optional, Set, Tuple
from ulid import ULID

from agentos.core.capability.domains.evidence.models import (
    EvidenceChain,
    EvidenceChainLink,
    ChainQueryResult,
    ChainRelationship,
    verify_evidence_chain,
)
from agentos.core.time import utc_now_ms
from agentos.core.db.registry_db import get_db

logger = logging.getLogger(__name__)


# ===================================================================
# Exceptions
# ===================================================================

class ChainNotFoundError(Exception):
    """Raised when evidence chain not found"""
    pass


class CircularChainError(Exception):
    """Raised when circular chain detected"""
    pass


class InvalidLinkError(Exception):
    """Raised when link is invalid"""
    pass


# ===================================================================
# Evidence Link Graph
# ===================================================================

class EvidenceLinkGraph:
    """
    Evidence chain graph builder and query engine.

    Manages evidence chains linking related operations.

    Example:
        graph = EvidenceLinkGraph()

        # Create chain
        chain_id = graph.link(
            decision_id="dec-123",
            action_id="exec-456",
            memory_id="mem-789"
        )

        # Query chain
        result = graph.query_chain(
            anchor_id="exec-456",
            anchor_type="action"
        )

        # Get full chain
        chain = graph.get_chain(chain_id)

        # Visualize
        viz = graph.visualize(chain_id)
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize evidence link graph.

        Args:
            db_path: Optional database path
        """
        self.db_path = db_path
        self._db_conn = None
        self._ensure_tables()
        logger.debug("EvidenceLinkGraph initialized")

    def _get_db(self):
        """Get database connection"""
        if self.db_path:
            if not self._db_conn:
                self._db_conn = sqlite3.connect(self.db_path)
                self._db_conn.row_factory = sqlite3.Row
            return self._db_conn
        else:
            return get_db()

    def _execute_sql(self, sql: str, params=None):
        """Execute SQL with parameters"""
        conn = self._get_db()
        if params:
            return conn.execute(sql, params)
        else:
            return conn.execute(sql)

    def _ensure_tables(self):
        """Ensure evidence chain tables exist"""
        try:
            self._execute_sql("SELECT 1 FROM evidence_chains LIMIT 1")
        except Exception as e:
            logger.warning(f"evidence_chains table may not exist: {e}")
            self._create_minimal_schema()

    def _create_minimal_schema(self):
        """Create minimal evidence chain schema for testing"""
        logger.info("Creating minimal evidence chain schema")
        conn = self._get_db()

        # Evidence chains table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence_chains (
                chain_id TEXT PRIMARY KEY,
                links_json TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL,
                created_by TEXT NOT NULL
            )
        """)

        # Evidence chain links table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence_chain_links (
                link_id INTEGER PRIMARY KEY AUTOINCREMENT,
                chain_id TEXT NOT NULL,
                from_type TEXT NOT NULL,
                from_id TEXT NOT NULL,
                to_type TEXT NOT NULL,
                to_id TEXT NOT NULL,
                relationship TEXT NOT NULL,
                FOREIGN KEY (chain_id) REFERENCES evidence_chains(chain_id)
            )
        """)

        # Create indexes
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chain_created "
            "ON evidence_chains(created_at_ms DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_link_chain "
            "ON evidence_chain_links(chain_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_link_from "
            "ON evidence_chain_links(from_type, from_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_link_to "
            "ON evidence_chain_links(to_type, to_id)"
        )

        conn.commit()
        logger.info("Minimal evidence chain schema created")

    # ===================================================================
    # Chain Creation
    # ===================================================================

    def link(
        self,
        decision_id: Optional[str] = None,
        action_id: Optional[str] = None,
        memory_id: Optional[str] = None,
        state_id: Optional[str] = None,
        created_by: str = "system",
        custom_links: Optional[List[Tuple[str, str, str, str, ChainRelationship]]] = None,
    ) -> str:
        """
        Create evidence chain linking related operations.

        Automatically creates standard links:
        - decision → action (caused_by)
        - action → memory (resulted_in)
        - memory → state (modified)

        Args:
            decision_id: Optional decision ID
            action_id: Optional action ID
            memory_id: Optional memory ID
            state_id: Optional state ID
            created_by: Agent creating the chain
            custom_links: Optional custom links [(from_type, from_id, to_type, to_id, relationship), ...]

        Returns:
            chain_id: Unique chain identifier

        Example:
            chain_id = graph.link(
                decision_id="dec-123",
                action_id="exec-456",
                memory_id="mem-789"
            )
        """
        chain_id = f"chain-{ULID()}"
        created_at_ms = utc_now_ms()

        # Build links
        links = []

        # Standard links
        if decision_id and action_id:
            links.append(
                EvidenceChainLink(
                    from_type="decision",
                    from_id=decision_id,
                    to_type="action",
                    to_id=action_id,
                    relationship=ChainRelationship.CAUSED_BY,
                )
            )

        if action_id and memory_id:
            links.append(
                EvidenceChainLink(
                    from_type="action",
                    from_id=action_id,
                    to_type="memory",
                    to_id=memory_id,
                    relationship=ChainRelationship.RESULTED_IN,
                )
            )

        if memory_id and state_id:
            links.append(
                EvidenceChainLink(
                    from_type="memory",
                    from_id=memory_id,
                    to_type="state",
                    to_id=state_id,
                    relationship=ChainRelationship.MODIFIED,
                )
            )

        # Custom links
        if custom_links:
            for from_type, from_id, to_type, to_id, relationship in custom_links:
                links.append(
                    EvidenceChainLink(
                        from_type=from_type,
                        from_id=from_id,
                        to_type=to_type,
                        to_id=to_id,
                        relationship=relationship,
                    )
                )

        # Create chain
        chain = EvidenceChain(
            chain_id=chain_id,
            links=links,
            created_at_ms=created_at_ms,
            created_by=created_by,
        )

        # Verify chain
        if not verify_evidence_chain(chain):
            raise CircularChainError("Evidence chain contains circular references")

        # Store chain
        self._store_chain(chain)

        logger.info(f"Created evidence chain {chain_id} with {len(links)} links")

        return chain_id

    def _store_chain(self, chain: EvidenceChain):
        """
        Store evidence chain in database.

        Args:
            chain: Evidence chain to store
        """
        conn = self._get_db()

        # Store chain
        links_json = json.dumps([link.model_dump() for link in chain.links])

        conn.execute(
            """
            INSERT INTO evidence_chains (
                chain_id, links_json, created_at_ms, created_by
            ) VALUES (?, ?, ?, ?)
            """,
            (chain.chain_id, links_json, chain.created_at_ms, chain.created_by),
        )

        # Store individual links
        for link in chain.links:
            conn.execute(
                """
                INSERT INTO evidence_chain_links (
                    chain_id, from_type, from_id, to_type, to_id, relationship
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    chain.chain_id,
                    link.from_type,
                    link.from_id,
                    link.to_type,
                    link.to_id,
                    link.relationship.value,
                ),
            )

        conn.commit()

    # ===================================================================
    # Chain Retrieval
    # ===================================================================

    def get_chain(self, chain_id: str) -> Optional[EvidenceChain]:
        """
        Get evidence chain by ID.

        Args:
            chain_id: Chain identifier

        Returns:
            EvidenceChain if found, None otherwise
        """
        conn = self._get_db()
        cursor = conn.execute(
            """
            SELECT chain_id, links_json, created_at_ms, created_by
            FROM evidence_chains
            WHERE chain_id = ?
            """,
            (chain_id,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        # Parse links
        links_json = json.loads(row["links_json"])
        links = [EvidenceChainLink(**link_data) for link_data in links_json]

        return EvidenceChain(
            chain_id=row["chain_id"],
            links=links,
            created_at_ms=row["created_at_ms"],
            created_by=row["created_by"],
        )

    # ===================================================================
    # Chain Queries
    # ===================================================================

    def query_chain(
        self,
        anchor_id: str,
        anchor_type: str,
        max_depth: int = 10,
    ) -> ChainQueryResult:
        """
        Query evidence chain from an anchor point.

        Traverses the graph to find all related evidence.

        Args:
            anchor_id: Starting entity ID
            anchor_type: Starting entity type (decision|action|memory|state)
            max_depth: Maximum traversal depth

        Returns:
            ChainQueryResult with complete chain

        Example:
            # Find all evidence related to an action
            result = graph.query_chain(
                anchor_id="exec-456",
                anchor_type="action"
            )

            # Result contains:
            # - Complete chain
            # - All entities (decision, action, memory, state)
            # - Traversal depth
        """
        # Find all links involving anchor
        forward_links = self._find_links_from(anchor_id, anchor_type)
        backward_links = self._find_links_to(anchor_id, anchor_type)

        # Traverse forward and backward
        visited = set()
        all_links = []
        entities = []

        # Breadth-first traversal
        queue = [(anchor_id, anchor_type, 0)]
        visited.add((anchor_type, anchor_id))

        while queue and len(visited) < 100:  # Safety limit
            entity_id, entity_type, depth = queue.pop(0)

            if depth >= max_depth:
                continue

            # Add entity
            entities.append({"type": entity_type, "id": entity_id, "depth": depth})

            # Find forward links
            for link in self._find_links_from(entity_id, entity_type):
                all_links.append(link)
                if (link.to_type, link.to_id) not in visited:
                    visited.add((link.to_type, link.to_id))
                    queue.append((link.to_id, link.to_type, depth + 1))

            # Find backward links
            for link in self._find_links_to(entity_id, entity_type):
                all_links.append(link)
                if (link.from_type, link.from_id) not in visited:
                    visited.add((link.from_type, link.from_id))
                    queue.append((link.from_id, link.from_type, depth + 1))

        # Build chain
        chain_id = f"query-{ULID()}"
        chain = EvidenceChain(
            chain_id=chain_id,
            links=all_links,
            created_at_ms=utc_now_ms(),
            created_by="query",
        )

        # Calculate max depth
        max_entity_depth = max([e["depth"] for e in entities]) if entities else 0

        return ChainQueryResult(
            anchor_id=anchor_id,
            anchor_type=anchor_type,
            chain=chain,
            entities=entities,
            depth=max_entity_depth,
        )

    def _find_links_from(self, entity_id: str, entity_type: str) -> List[EvidenceChainLink]:
        """
        Find all links where entity is source.

        Args:
            entity_id: Entity ID
            entity_type: Entity type

        Returns:
            List of links
        """
        conn = self._get_db()
        cursor = conn.execute(
            """
            SELECT from_type, from_id, to_type, to_id, relationship
            FROM evidence_chain_links
            WHERE from_type = ? AND from_id = ?
            """,
            (entity_type, entity_id),
        )

        links = []
        for row in cursor.fetchall():
            link = EvidenceChainLink(
                from_type=row["from_type"],
                from_id=row["from_id"],
                to_type=row["to_type"],
                to_id=row["to_id"],
                relationship=ChainRelationship(row["relationship"]),
            )
            links.append(link)

        return links

    def _find_links_to(self, entity_id: str, entity_type: str) -> List[EvidenceChainLink]:
        """
        Find all links where entity is target.

        Args:
            entity_id: Entity ID
            entity_type: Entity type

        Returns:
            List of links
        """
        conn = self._get_db()
        cursor = conn.execute(
            """
            SELECT from_type, from_id, to_type, to_id, relationship
            FROM evidence_chain_links
            WHERE to_type = ? AND to_id = ?
            """,
            (entity_type, entity_id),
        )

        links = []
        for row in cursor.fetchall():
            link = EvidenceChainLink(
                from_type=row["from_type"],
                from_id=row["from_id"],
                to_type=row["to_type"],
                to_id=row["to_id"],
                relationship=ChainRelationship(row["relationship"]),
            )
            links.append(link)

        return links

    # ===================================================================
    # Visualization
    # ===================================================================

    def visualize(self, chain_id: str) -> Dict[str, Any]:
        """
        Generate visualization data for evidence chain.

        Returns graph in D3/Cytoscape-compatible format.

        Args:
            chain_id: Chain to visualize

        Returns:
            Graph data with nodes and edges

        Example:
            viz = graph.visualize("chain-123")

            # viz = {
            #     "nodes": [
            #         {"id": "dec-123", "type": "decision", "label": "Decision"},
            #         {"id": "exec-456", "type": "action", "label": "Action"},
            #     ],
            #     "edges": [
            #         {"from": "dec-123", "to": "exec-456", "label": "caused_by"}
            #     ]
            # }
        """
        chain = self.get_chain(chain_id)
        if not chain:
            raise ChainNotFoundError(f"Chain {chain_id} not found")

        # Build nodes
        nodes = {}
        for link in chain.links:
            # Add source node
            if link.from_id not in nodes:
                nodes[link.from_id] = {
                    "id": link.from_id,
                    "type": link.from_type,
                    "label": f"{link.from_type.capitalize()} {link.from_id[:8]}",
                }

            # Add target node
            if link.to_id not in nodes:
                nodes[link.to_id] = {
                    "id": link.to_id,
                    "type": link.to_type,
                    "label": f"{link.to_type.capitalize()} {link.to_id[:8]}",
                }

        # Build edges
        edges = []
        for link in chain.links:
            edges.append(
                {
                    "from": link.from_id,
                    "to": link.to_id,
                    "label": link.relationship.value,
                    "relationship": link.relationship.value,
                }
            )

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "chain_id": chain_id,
            "created_at_ms": chain.created_at_ms,
        }

    # ===================================================================
    # Statistics
    # ===================================================================

    def get_stats(self) -> Dict[str, int]:
        """
        Get evidence chain statistics.

        Returns:
            Statistics dict
        """
        conn = self._get_db()

        # Count chains
        cursor = conn.execute("SELECT COUNT(*) as count FROM evidence_chains")
        chain_count = cursor.fetchone()["count"]

        # Count links
        cursor = conn.execute("SELECT COUNT(*) as count FROM evidence_chain_links")
        link_count = cursor.fetchone()["count"]

        return {
            "total_chains": chain_count,
            "total_links": link_count,
            "avg_links_per_chain": link_count / chain_count if chain_count > 0 else 0,
        }


# ===================================================================
# Global Singleton
# ===================================================================

_graph_instance: Optional[EvidenceLinkGraph] = None


def get_evidence_link_graph(db_path: Optional[str] = None) -> EvidenceLinkGraph:
    """
    Get global EvidenceLinkGraph singleton.

    Args:
        db_path: Optional database path

    Returns:
        Singleton EvidenceLinkGraph instance
    """
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = EvidenceLinkGraph(db_path=db_path)
    return _graph_instance
