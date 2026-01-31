"""
Graph Builder for Dry Executor

Builds an ExecutionGraph (planning DAG) from an ExecutionIntent.
Does NOT execute anything - only creates a plan structure.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .utils import compute_checksum, generate_id
from agentos.core.time import utc_now_iso



class GraphBuilder:
    """
    Builds execution graphs from intents without performing any execution.
    
    Red Line Enforcement:
    - DE1: No execution (pure data structure generation)
    - DE4: All nodes must have evidence_refs
    """
    
    def __init__(self, intent: Dict[str, Any], coordinator_graph: Optional[Dict[str, Any]] = None):
        """
        Initialize graph builder.
        
        Args:
            intent: ExecutionIntent (v0.9.1)
            coordinator_graph: Optional ExecutionGraph from coordinator (v0.9.2)
        """
        self.intent = intent
        self.coordinator_graph = coordinator_graph
        self.nodes: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, Any]] = []
        self.swimlanes: List[Dict[str, Any]] = []
        self.node_counter = 0
        self.edge_counter = 0
    
    def build(self) -> Dict[str, Any]:
        """
        Build the execution graph.
        
        Returns:
            ExecutionGraph dictionary matching execution_graph.schema.json
        """
        # If coordinator graph exists, use it as base
        if self.coordinator_graph:
            return self._adapt_coordinator_graph()
        
        # Otherwise, build from intent
        self._build_from_intent()
        
        # Construct graph object
        graph_data = {
            "graph_id": generate_id("graph", self.intent["id"]),
            "schema_version": "0.10.0",
            "intent_id": self.intent["id"],
            "created_at": utc_now_iso() + "Z",
            "nodes": self.nodes,
            "edges": self.edges,
            "swimlanes": self.swimlanes,
            "lineage": {
                "derived_from_intent": self.intent["id"],
                "intent_checksum": self.intent["audit"]["checksum"],
                "dry_executor_version": "0.10.0"
            }
        }
        
        # Compute checksum
        graph_data["checksum"] = compute_checksum({
            "nodes": self.nodes,
            "edges": self.edges,
            "swimlanes": self.swimlanes
        })
        
        return graph_data
    
    def _build_from_intent(self):
        """Build graph structure from intent."""
        # Create phase nodes from workflows
        phase_nodes = self._create_phase_nodes()
        
        # Create action nodes from planned commands
        action_nodes = self._create_action_nodes()
        
        # Create decision/review nodes based on risk
        control_nodes = self._create_control_nodes()
        
        # Link nodes with edges
        self._create_edges(phase_nodes, action_nodes, control_nodes)
        
        # Create swimlanes from agents
        self._create_swimlanes()
    
    def _create_phase_nodes(self) -> List[Dict[str, Any]]:
        """Create nodes for workflow phases."""
        phase_nodes = []
        
        for workflow in self.intent.get("selected_workflows", []):
            workflow_id = workflow["workflow_id"]
            phases = workflow["phases"]
            
            for idx, phase in enumerate(phases):
                node_id = self._next_node_id()
                node = {
                    "node_id": node_id,
                    "node_type": "phase",
                    "label": f"{workflow_id}: {phase}",
                    "description": f"Phase '{phase}' from workflow '{workflow_id}'",
                    "phase_ref": f"{workflow_id}.{phase}",
                    "evidence_refs": [
                        f"intent://{self.intent['id']}/selected_workflows/{workflow_id}",
                        workflow.get("reason", "workflow selection")
                    ]
                }
                self.nodes.append(node)
                phase_nodes.append(node)
        
        return phase_nodes
    
    def _create_action_nodes(self) -> List[Dict[str, Any]]:
        """Create action plan nodes from planned commands."""
        action_nodes = []
        
        for command in self.intent.get("planned_commands", []):
            node_id = self._next_node_id()
            node = {
                "node_id": node_id,
                "node_type": "action_plan",
                "label": f"Plan: {command['command_id']}",
                "description": command.get("intent", ""),
                "command_ref": command["command_id"],
                "effects": command["effects"],
                "risk_level": command["risk_level"],
                "evidence_refs": command["evidence_refs"]
            }
            self.nodes.append(node)
            action_nodes.append(node)
        
        return action_nodes
    
    def _create_control_nodes(self) -> List[Dict[str, Any]]:
        """Create decision points and review checkpoints based on risk."""
        control_nodes = []
        
        # Add review checkpoint if requires_review is specified
        requires_review = self.intent.get("risk", {}).get("requires_review", [])
        if requires_review:
            node_id = self._next_node_id()
            node = {
                "node_id": node_id,
                "node_type": "review_checkpoint",
                "label": "Pre-execution Review",
                "description": "Review checkpoint before execution",
                "review_criteria": requires_review,
                "evidence_refs": [
                    f"intent://{self.intent['id']}/risk/requires_review"
                ]
            }
            self.nodes.append(node)
            control_nodes.append(node)
        
        return control_nodes
    
    def _create_edges(self, phase_nodes: List, action_nodes: List, control_nodes: List):
        """Create edges connecting nodes."""
        # Connect phases sequentially
        for i in range(len(phase_nodes) - 1):
            self._add_edge(
                phase_nodes[i]["node_id"],
                phase_nodes[i + 1]["node_id"],
                "sequential"
            )
        
        # Connect actions to last phase (simplified)
        if phase_nodes and action_nodes:
            last_phase = phase_nodes[-1]
            for action in action_nodes:
                self._add_edge(
                    last_phase["node_id"],
                    action["node_id"],
                    "parallel"
                )
        
        # Connect review checkpoint after actions
        if control_nodes and action_nodes:
            review_node = control_nodes[0]
            for action in action_nodes:
                self._add_edge(
                    action["node_id"],
                    review_node["node_id"],
                    "sequential"
                )
    
    def _create_swimlanes(self):
        """Create swimlanes from selected agents."""
        for agent in self.intent.get("selected_agents", []):
            swimlane_id = f"swimlane_{agent['agent_id']}"
            
            # Assign nodes to this agent (simplified - assign all action nodes)
            node_refs = [
                node["node_id"] 
                for node in self.nodes 
                if node["node_type"] == "action_plan"
            ]
            
            swimlane = {
                "swimlane_id": swimlane_id,
                "agent_id": agent["agent_id"],
                "role": agent["role"],
                "node_refs": node_refs
            }
            self.swimlanes.append(swimlane)
    
    def _adapt_coordinator_graph(self) -> Dict[str, Any]:
        """Adapt coordinator graph for dry executor use."""
        # Copy coordinator graph and adjust for v0.10
        adapted = self.coordinator_graph.copy()
        adapted["schema_version"] = "0.10.0"
        adapted["lineage"]["dry_executor_version"] = "0.10.0"
        adapted["lineage"]["coordinator_run_id"] = adapted.get("intent_id")
        
        # Recompute checksum
        adapted["checksum"] = compute_checksum({
            "nodes": adapted["nodes"],
            "edges": adapted["edges"],
            "swimlanes": adapted["swimlanes"]
        })
        
        return adapted
    
    def _next_node_id(self) -> str:
        """Generate next node ID."""
        self.node_counter += 1
        return f"node_{self.node_counter:04d}"
    
    def _next_edge_id(self) -> str:
        """Generate next edge ID."""
        self.edge_counter += 1
        return f"edge_{self.edge_counter:04d}"
    
    def _add_edge(self, from_node: str, to_node: str, edge_type: str):
        """Add an edge to the graph."""
        edge = {
            "edge_id": self._next_edge_id(),
            "from_node": from_node,
            "to_node": to_node,
            "edge_type": edge_type
        }
        self.edges.append(edge)
