"""DAG-based operation scheduler for parallel execution."""

import asyncio
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class OperationStatus(Enum):
    """Operation execution status."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Operation:
    """Operation node in DAG."""
    op_id: str
    op_type: str
    op_data: Dict
    depends_on: List[str] = field(default_factory=list)
    status: OperationStatus = OperationStatus.PENDING
    result: Optional[Dict] = None
    error: Optional[str] = None
    
    def __hash__(self):
        return hash(self.op_id)


class DAGScheduler:
    """
    DAG-based scheduler for parallel operation execution.
    
    Features:
    - Dependency resolution
    - Parallel execution of independent operations
    - Cycle detection
    - Error propagation
    """
    
    def __init__(self, operations: List[Dict]):
        """
        Initialize DAG scheduler.
        
        Args:
            operations: List of operation dictionaries with:
                - op_id: Operation identifier
                - op_type: Operation type
                - depends_on: List of operation IDs this depends on
                - ... other operation data
        """
        self.operations: Dict[str, Operation] = {}
        self._build_dag(operations)
        self._validate_dag()
    
    def _build_dag(self, operations: List[Dict]) -> None:
        """Build DAG from operation list."""
        for op_data in operations:
            op = Operation(
                op_id=op_data["op_id"],
                op_type=op_data.get("op_type", "unknown"),
                op_data=op_data,
                depends_on=op_data.get("depends_on", [])
            )
            self.operations[op.op_id] = op
    
    def _validate_dag(self) -> None:
        """Validate DAG structure."""
        # Check all dependencies exist
        for op in self.operations.values():
            for dep_id in op.depends_on:
                if dep_id not in self.operations:
                    raise ValueError(
                        f"Operation {op.op_id} depends on non-existent operation {dep_id}"
                    )
        
        # Check for cycles
        if self._has_cycle():
            raise ValueError("DAG contains cycles - cannot execute")
    
    def _has_cycle(self) -> bool:
        """Detect cycles using DFS."""
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        
        def dfs(op_id: str) -> bool:
            visited.add(op_id)
            rec_stack.add(op_id)
            
            op = self.operations[op_id]
            for dep_id in op.depends_on:
                if dep_id not in visited:
                    if dfs(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True
            
            rec_stack.remove(op_id)
            return False
        
        for op_id in self.operations:
            if op_id not in visited:
                if dfs(op_id):
                    return True
        
        return False
    
    def get_ready_operations(self) -> List[Operation]:
        """
        Get operations that are ready to execute.
        
        Ready = pending + all dependencies completed successfully
        """
        ready = []
        
        for op in self.operations.values():
            if op.status != OperationStatus.PENDING:
                continue
            
            # Check if all dependencies are completed
            all_deps_complete = True
            for dep_id in op.depends_on:
                dep = self.operations[dep_id]
                if dep.status != OperationStatus.COMPLETED:
                    all_deps_complete = False
                    break
            
            if all_deps_complete:
                op.status = OperationStatus.READY
                ready.append(op)
        
        return ready
    
    async def execute_parallel(
        self,
        executor_func,
        max_concurrency: int = 5
    ) -> Tuple[bool, List[Dict]]:
        """
        Execute operations in parallel respecting dependencies.
        
        Args:
            executor_func: Async function to execute single operation
            max_concurrency: Maximum concurrent operations
        
        Returns:
            Tuple of (success, results)
        """
        semaphore = asyncio.Semaphore(max_concurrency)
        results = []
        
        async def execute_op(op: Operation) -> None:
            """Execute single operation with concurrency control."""
            async with semaphore:
                op.status = OperationStatus.RUNNING
                
                try:
                    result = await executor_func(op)
                    op.result = result
                    op.status = OperationStatus.COMPLETED
                    results.append({
                        "op_id": op.op_id,
                        "status": "completed",
                        "result": result
                    })
                except Exception as e:
                    op.error = str(e)
                    op.status = OperationStatus.FAILED
                    results.append({
                        "op_id": op.op_id,
                        "status": "failed",
                        "error": str(e)
                    })
        
        # Execute in waves
        while True:
            ready_ops = self.get_ready_operations()
            
            if not ready_ops:
                # Check if done or blocked
                pending_count = sum(
                    1 for op in self.operations.values() 
                    if op.status == OperationStatus.PENDING
                )
                
                if pending_count > 0:
                    # Some operations are blocked by failures
                    self._mark_blocked_as_skipped()
                
                break
            
            # Execute ready operations in parallel
            tasks = [execute_op(op) for op in ready_ops]
            await asyncio.gather(*tasks)
        
        # Check overall success
        all_success = all(
            op.status in [OperationStatus.COMPLETED, OperationStatus.SKIPPED]
            for op in self.operations.values()
        )
        
        return all_success, results
    
    def _mark_blocked_as_skipped(self) -> None:
        """Mark operations blocked by failures as skipped."""
        for op in self.operations.values():
            if op.status == OperationStatus.PENDING:
                # Check if any dependency failed
                has_failed_dep = any(
                    self.operations[dep_id].status == OperationStatus.FAILED
                    for dep_id in op.depends_on
                )
                
                if has_failed_dep:
                    op.status = OperationStatus.SKIPPED
                    op.error = "Skipped due to failed dependency"
    
    def get_execution_order(self) -> List[List[str]]:
        """
        Get topological execution order in waves.
        
        Returns:
            List of operation ID lists, each inner list can execute in parallel
        """
        order = []
        remaining = set(self.operations.keys())
        
        while remaining:
            # Find operations with no dependencies in remaining
            wave = []
            for op_id in remaining:
                op = self.operations[op_id]
                if all(dep_id not in remaining for dep_id in op.depends_on):
                    wave.append(op_id)
            
            if not wave:
                raise ValueError("Circular dependency detected")
            
            order.append(wave)
            remaining -= set(wave)
        
        return order
    
    def visualize_dag(self) -> str:
        """Generate ASCII visualization of DAG."""
        lines = ["DAG Visualization:", "=" * 50]
        
        execution_order = self.get_execution_order()
        
        for wave_num, wave in enumerate(execution_order, 1):
            lines.append(f"\nWave {wave_num} (parallel):")
            for op_id in wave:
                op = self.operations[op_id]
                deps_str = f" <- {', '.join(op.depends_on)}" if op.depends_on else ""
                status_icon = {
                    OperationStatus.PENDING: "⏸",
                    OperationStatus.READY: "▶",
                    OperationStatus.RUNNING: "⏩",
                    OperationStatus.COMPLETED: "✓",
                    OperationStatus.FAILED: "✗",
                    OperationStatus.SKIPPED: "⊘"
                }.get(op.status, "?")
                
                lines.append(f"  {status_icon} {op_id} ({op.op_type}){deps_str}")
        
        return "\n".join(lines)
    
    def get_statistics(self) -> Dict:
        """Get execution statistics."""
        return {
            "total_operations": len(self.operations),
            "completed": sum(1 for op in self.operations.values() 
                           if op.status == OperationStatus.COMPLETED),
            "failed": sum(1 for op in self.operations.values() 
                         if op.status == OperationStatus.FAILED),
            "skipped": sum(1 for op in self.operations.values() 
                          if op.status == OperationStatus.SKIPPED),
            "max_parallelism": max(len(wave) for wave in self.get_execution_order()),
            "total_waves": len(self.get_execution_order())
        }


def build_dag_from_execution_request(execution_request: Dict) -> DAGScheduler:
    """
    Build DAG from execution request.
    
    Args:
        execution_request: Execution request with operations
    
    Returns:
        DAGScheduler instance
    """
    operations = []
    allowed_ops = execution_request.get("allowed_operations", [])
    
    for i, op in enumerate(allowed_ops):
        # Infer dependencies from operation data
        # For now, simple sequential dependency (can be enhanced)
        depends_on = []
        if i > 0 and op.get("type") != "file_write":
            # Non-write operations depend on previous operation
            depends_on = [allowed_ops[i-1].get("op_id", f"op_{i-1}")]
        
        op_dict = {
            "op_id": op.get("op_id", f"op_{i}"),
            "op_type": op.get("type", "unknown"),
            "depends_on": depends_on,
            **op
        }
        operations.append(op_dict)
    
    return DAGScheduler(operations)
