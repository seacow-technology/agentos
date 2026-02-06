"""Graph Builder - Construct ExecutionGraph from Intent and decisions (v0.9.2)"""

import hashlib
import json


class GraphBuilder:
    """Build ExecutionGraph (DAG) from Intent and rule decisions"""
    
    def __init__(self):
        self.graph = {"nodes": [], "edges": [], "swimlanes": []}
        self.node_counter = 0
        self.edge_counter = 0
    
    def build_graph(self, parsed_intent: dict, decisions: list, context: dict) -> dict:
        """
        Build complete ExecutionGraph
        
        Returns:
            ExecutionGraph with nodes, edges, swimlanes, lineage, checksum
        """
        intent = context["intent"]
        
        # Add phase nodes
        phase_nodes = self.add_phase_nodes(parsed_intent["workflows"])
        
        # Add action proposal nodes
        action_nodes = self.add_action_proposals(parsed_intent["commands"], decisions)
        
        # Build edges
        self.build_edges(phase_nodes, action_nodes)
        
        # Assign swimlanes
        swimlanes = self.assign_swimlanes(parsed_intent["agents"], self.graph["nodes"])
        self.graph["swimlanes"] = swimlanes
        
        # Build final graph structure
        execution_graph = {
            "graph_id": f"graph_{intent['id']}",
            "schema_version": "0.9.2",
            "intent_id": intent["id"],
            "created_at": context.get("timestamp", "2026-01-25T00:00:00Z"),
            "nodes": self.graph["nodes"],
            "edges": self.graph["edges"],
            "swimlanes": self.graph["swimlanes"],
            "lineage": self._build_lineage(intent),
            "checksum": self._calculate_checksum(self.graph)
        }
        
        return execution_graph
    
    def add_phase_nodes(self, workflows: list) -> list:
        """Add phase nodes from workflows"""
        phase_node_ids = []
        
        for workflow in workflows:
            for phase in workflow.get("phases", []):
                node_id = f"node_phase_{self.node_counter:03d}"
                self.node_counter += 1
                
                self.graph["nodes"].append({
                    "node_id": node_id,
                    "node_type": "phase",
                    "label": f"{phase.capitalize()} Phase",
                    "phase_ref": phase
                })
                phase_node_ids.append(node_id)
        
        return phase_node_ids
    
    def add_action_proposals(self, commands: list, decisions: list) -> list:
        """Add action_proposal nodes"""
        action_node_ids = []
        
        for cmd, decision in zip(commands, decisions):
            node_id = f"node_action_{self.node_counter:03d}"
            self.node_counter += 1
            
            self.graph["nodes"].append({
                "node_id": node_id,
                "node_type": "action_proposal",
                "label": cmd.get("intent", "Action"),
                "command_ref": cmd.get("command_id"),
                "effects": cmd.get("effects", []),
                "risk_level": cmd.get("risk_level", "low"),
                "evidence_refs": cmd.get("evidence_refs", [])
            })
            action_node_ids.append(node_id)
        
        return action_node_ids
    
    def build_edges(self, phase_nodes: list, action_nodes: list) -> list:
        """Build edges (sequential flow)"""
        all_nodes = phase_nodes + action_nodes
        
        for i in range(len(all_nodes) - 1):
            edge_id = f"edge_{self.edge_counter:03d}"
            self.edge_counter += 1
            
            self.graph["edges"].append({
                "edge_id": edge_id,
                "from_node": all_nodes[i],
                "to_node": all_nodes[i + 1],
                "edge_type": "sequential"
            })
        
        return self.graph["edges"]
    
    def assign_swimlanes(self, agents: list, nodes: list) -> list:
        """Assign nodes to agent swimlanes"""
        swimlanes = []
        
        for i, agent in enumerate(agents):
            swimlanes.append({
                "swimlane_id": f"swimlane_{i:03d}",
                "agent_id": agent.get("agent_id"),
                "role": agent.get("role"),
                "node_refs": [node["node_id"] for node in nodes]  # Simplified: all nodes to first agent
            })
        
        return swimlanes
    
    def validate_dag(self) -> tuple[bool, str]:
        """Validate graph is a DAG (no cycles)"""
        # Simplified: assume valid for skeleton
        return True, ""
    
    def _build_lineage(self, intent: dict) -> dict:
        """Build lineage metadata"""
        return {
            "derived_from_intent": intent["id"],
            "intent_checksum": intent.get("audit", {}).get("checksum", ""),
            "registry_versions": {"workflows": {}, "agents": {}, "commands": {}, "rules": {}},
            "coordinator_version": "0.9.2"
        }
    
    def _calculate_checksum(self, graph: dict) -> str:
        """Calculate SHA-256 checksum"""
        content = json.dumps(graph, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
