#!/usr/bin/env python3
"""
v0.9.2 Gate H: Graph Topology Validation

Validates:
- ExecutionGraph is a DAG (no cycles)
- All nodes are reachable from start
- Swimlanes cover all nodes
"""

import json
import sys
from pathlib import Path
from collections import defaultdict, deque

EXAMPLES_DIR = Path("examples/coordinator/outputs")

GRAPHS_TO_CHECK = [
    "execution_graph_low_risk.json",
    "execution_graph_high_risk_interactive.json",
    "execution_graph_full_auto_readonly.json"
]


def check_dag(nodes, edges):
    """Check if graph is a Directed Acyclic Graph"""
    # Build adjacency list
    adj = defaultdict(list)
    in_degree = {node["node_id"]: 0 for node in nodes}
    
    for edge in edges:
        adj[edge["from_node"]].append(edge["to_node"])
        in_degree[edge["to_node"]] = in_degree.get(edge["to_node"], 0) + 1
    
    # Topological sort (Kahn's algorithm)
    queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
    visited_count = 0
    
    while queue:
        node = queue.popleft()
        visited_count += 1
        
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    # If visited all nodes, it's a DAG
    return visited_count == len(nodes)


def check_reachability(nodes, edges):
    """Check if all nodes are reachable from entry nodes"""
    if not nodes:
        return True
    
    # Build adjacency list
    adj = defaultdict(list)
    for edge in edges:
        adj[edge["from_node"]].append(edge["to_node"])
    
    # Find entry nodes (nodes with no incoming edges)
    incoming = {edge["to_node"] for edge in edges}
    entry_nodes = [node["node_id"] for node in nodes if node["node_id"] not in incoming]
    
    if not entry_nodes:
        return False  # No entry point
    
    # BFS from all entry nodes
    visited = set()
    queue = deque(entry_nodes)
    
    while queue:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)
        
        for neighbor in adj[node]:
            if neighbor not in visited:
                queue.append(neighbor)
    
    # Check if all nodes visited
    all_nodes = {node["node_id"] for node in nodes}
    unreachable = all_nodes - visited
    
    if unreachable:
        return False, unreachable
    return True, set()


def check_swimlane_coverage(nodes, swimlanes):
    """Check if all nodes are assigned to swimlanes"""
    all_nodes = {node["node_id"] for node in nodes}
    covered_nodes = set()
    
    for swimlane in swimlanes:
        covered_nodes.update(swimlane["node_refs"])
    
    uncovered = all_nodes - covered_nodes
    return len(uncovered) == 0, uncovered


def main():
    print("=" * 70)
    print("v0.9.2 Gate H: Graph Topology Validation")
    print("=" * 70)

    all_valid = True

    for graph_file in GRAPHS_TO_CHECK:
        graph_path = EXAMPLES_DIR / graph_file
        print(f"\nValidating {graph_file}...")

        if not graph_path.exists():
            print(f"  ❌ Graph not found")
            all_valid = False
            continue

        with open(graph_path, "r", encoding="utf-8") as f:
            graph = json.load(f)

        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        swimlanes = graph.get("swimlanes", [])

        # Check DAG
        if check_dag(nodes, edges):
            print(f"  ✅ Graph is a DAG (no cycles)")
        else:
            print(f"  ❌ Graph contains cycles")
            all_valid = False

        # Check reachability
        reachable, unreachable = check_reachability(nodes, edges)
        if reachable:
            print(f"  ✅ All nodes are reachable")
        else:
            print(f"  ❌ Unreachable nodes: {unreachable}")
            all_valid = False

        # Check swimlane coverage
        covered, uncovered = check_swimlane_coverage(nodes, swimlanes)
        if covered:
            print(f"  ✅ All nodes covered by swimlanes")
        else:
            print(f"  ❌ Uncovered nodes: {uncovered}")
            all_valid = False

    print("\n" + "=" * 70)
    if all_valid:
        print("✅ Gate H: PASSED")
        print("=" * 70)
        return True
    else:
        print("❌ Gate H: FAILED")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
