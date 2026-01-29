"""Trace Builder: Build task traces with lazy expansion"""

import json
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from agentos.core.task.models import TaskTrace, TaskLineageEntry

logger = logging.getLogger(__name__)


class TraceBuilder:
    """Build task traces with lazy content loading"""
    
    def __init__(self, outputs_dir: Optional[Path] = None):
        """
        Initialize Trace Builder
        
        Args:
            outputs_dir: Base directory for outputs (defaults to ./outputs)
        """
        self.outputs_dir = Path(outputs_dir or "outputs")
    
    def expand_content(
        self,
        trace: TaskTrace,
        kind: str,
        ref_id: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Expand content for a specific kind
        
        Args:
            trace: Task trace
            kind: Kind to expand (intent|plan|coordinator_run|execution_request|...)
            ref_id: Optional specific ref_id (defaults to latest)
            
        Returns:
            Expanded content or None
        """
        # Get ref_id if not provided
        if not ref_id:
            ref_id = trace.get_latest_ref(kind)
        
        if not ref_id:
            logger.warning(f"No {kind} found in trace for task {trace.task.task_id}")
            return None
        
        # Check if already expanded
        cache_key = f"{kind}:{ref_id}"
        if cached := trace.expand(cache_key):
            return cached
        
        # Load content based on kind
        content = self._load_content(kind, ref_id)
        
        if content:
            trace.set_expanded(cache_key, content)
        
        return content
    
    def _load_content(self, kind: str, ref_id: str) -> Optional[Any]:
        """
        Load content from filesystem or database
        
        Args:
            kind: Content kind
            ref_id: Reference ID
            
        Returns:
            Content or None
        """
        if kind == "intent":
            return self._load_intent(ref_id)
        elif kind == "coordinator_run":
            return self._load_coordinator_run(ref_id)
        elif kind == "execution_request":
            return self._load_execution_request(ref_id)
        elif kind == "dry_result":
            return self._load_dry_result(ref_id)
        elif kind == "commit":
            return self._load_commit_info(ref_id)
        elif kind == "tape":
            return self._load_tape(ref_id)
        else:
            logger.warning(f"Unknown kind for expansion: {kind}")
            return None
    
    def _load_intent(self, intent_id: str) -> Optional[Dict[str, Any]]:
        """Load intent JSON"""
        # Search in common locations
        patterns = [
            self.outputs_dir / "pipeline" / "*" / "01_intent" / "intent.json",
            self.outputs_dir / "pipeline" / "*" / "01_intent" / f"{intent_id}.json",
        ]
        
        for pattern in patterns:
            for path in Path(pattern.parent.parent.parent).glob(pattern.name):
                if path.exists():
                    try:
                        with open(path, encoding="utf-8") as f:
                            data = json.load(f)
                            if data.get("id") == intent_id:
                                return data
                    except Exception as e:
                        logger.error(f"Failed to load intent from {path}: {e}")
        
        return None
    
    def _load_coordinator_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Load coordinator run output"""
        patterns = [
            self.outputs_dir / "pipeline" / "*" / "02_coordinator" / "coordinator_run_tape.json",
        ]
        
        for pattern in patterns:
            for path in Path(pattern.parent.parent.parent).glob(str(pattern.relative_to(pattern.parent.parent.parent))):
                if path.exists():
                    try:
                        with open(path, encoding="utf-8") as f:
                            return json.load(f)
                    except Exception as e:
                        logger.error(f"Failed to load coordinator run from {path}: {e}")
        
        return None
    
    def _load_execution_request(self, exec_req_id: str) -> Optional[Dict[str, Any]]:
        """Load execution request"""
        # Typically in executor output dir
        exec_dir = self.outputs_dir / exec_req_id
        if exec_dir.exists():
            exec_req_file = exec_dir / "execution_request.json"
            if exec_req_file.exists():
                try:
                    with open(exec_req_file, encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load execution request: {e}")
        
        return None
    
    def _load_dry_result(self, dry_result_id: str) -> Optional[Dict[str, Any]]:
        """Load dry executor result"""
        patterns = [
            self.outputs_dir / "pipeline" / "*" / "03_dry_executor" / "dry_execution_result.json",
        ]
        
        for pattern in patterns:
            for path in Path(pattern.parent.parent.parent).glob(str(pattern.relative_to(pattern.parent.parent.parent))):
                if path.exists():
                    try:
                        with open(path, encoding="utf-8") as f:
                            data = json.load(f)
                            if data.get("result_id") == dry_result_id:
                                return data
                    except Exception as e:
                        logger.error(f"Failed to load dry result: {e}")
        
        return None
    
    def _load_commit_info(self, commit_hash: str) -> Optional[Dict[str, Any]]:
        """Load commit information"""
        # Commit info is typically in git, just return hash for now
        return {"commit_hash": commit_hash, "note": "Use git show for details"}
    
    def _load_tape(self, tape_ref: str) -> Optional[Any]:
        """Load run tape"""
        # Tape files are typically run_tape.jsonl
        tape_path = Path(tape_ref)
        if tape_path.exists():
            try:
                events = []
                with open(tape_path, encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            events.append(json.loads(line))
                return {"tape_path": str(tape_path), "events": events}
            except Exception as e:
                logger.error(f"Failed to load tape: {e}")
        
        return None
