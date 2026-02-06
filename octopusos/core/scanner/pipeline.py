"""Scanner pipeline"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentos.adapters import get_adapters
from agentos.core.time import utc_now_iso



class ScannerPipeline:
    """Main scanner pipeline"""
    
    IGNORE_DIRS = {
        "node_modules", ".git", "dist", "build", "__pycache__",
        ".pytest_cache", ".venv", "venv", "env", ".uv"
    }
    
    IGNORE_EXTENSIONS = {
        ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe"
    }
    
    def __init__(self, project_id: str, repo_root: Path):
        self.project_id = project_id
        self.repo_root = Path(repo_root).resolve()
        self.evidence_counter = 0
    
    def scan(self) -> dict[str, Any]:
        """Run full scan pipeline"""
        factpack = {
            "schema_version": "1.0.0",
            "project_id": self.project_id,
            "repo_root": str(self.repo_root),
            "scanned_at": utc_now_iso(),
        }
        
        # Step 1: Fingerprint
        factpack["repo_fingerprint"] = self._compute_fingerprint()
        
        # Step 2: Index files
        file_list = self._index_files()
        
        # Step 3: Detect projects using adapters
        detected_results = self._detect_projects()
        
        # Merge adapter results
        factpack["detected_projects"] = []
        factpack["commands"] = {}
        factpack["constraints"] = {}
        factpack["governance"] = {}
        factpack["evidence"] = []
        
        for result in detected_results:
            if "detected_projects" in result:
                factpack["detected_projects"].extend(result["detected_projects"])
            if "commands" in result:
                factpack["commands"].update(result["commands"])
            if "constraints" in result:
                factpack["constraints"].update(result["constraints"])
            if "governance" in result:
                # Merge governance (last one wins for now)
                factpack["governance"].update(result["governance"])
            if "evidence" in result:
                factpack["evidence"].extend(result["evidence"])
        
        # If no evidence, add at least one
        if not factpack["evidence"]:
            factpack["evidence"].append({
                "id": self._next_evidence_id(),
                "source_file": ".",
                "category": "documentation",
                "description": "Repository root"
            })
        
        return factpack
    
    def _compute_fingerprint(self) -> dict[str, str]:
        """Compute repository fingerprint"""
        fingerprint = {}
        
        # Try to get git commit
        git_head = self.repo_root / ".git" / "HEAD"
        if git_head.exists():
            try:
                head_content = git_head.read_text().strip()
                if head_content.startswith("ref:"):
                    ref_path = self.repo_root / ".git" / head_content.split()[1]
                    if ref_path.exists():
                        fingerprint["git_commit"] = ref_path.read_text().strip()[:8]
            except Exception:
                pass
        
        # Compute hash of file structure
        file_list = []
        for file_path in self.repo_root.rglob("*"):
            if file_path.is_file() and not self._should_ignore(file_path):
                rel_path = file_path.relative_to(self.repo_root)
                size = file_path.stat().st_size
                file_list.append(f"{rel_path}:{size}")
        
        file_list.sort()
        hash_input = "\n".join(file_list).encode()
        fingerprint["hash"] = hashlib.sha256(hash_input).hexdigest()[:16]
        
        return fingerprint
    
    def _index_files(self) -> list[Path]:
        """Index all files in repository"""
        files = []
        for file_path in self.repo_root.rglob("*"):
            if file_path.is_file() and not self._should_ignore(file_path):
                files.append(file_path)
        return files
    
    def _should_ignore(self, path: Path) -> bool:
        """Check if path should be ignored"""
        # Check if any parent is in ignore list
        for parent in path.parents:
            if parent.name in self.IGNORE_DIRS:
                return True
        
        # Check extension
        if path.suffix in self.IGNORE_EXTENSIONS:
            return True
        
        return False
    
    def _detect_projects(self) -> list[dict[str, Any]]:
        """Detect projects using adapters"""
        results = []
        adapters = get_adapters()
        
        for adapter in adapters:
            if adapter.detect(self.repo_root):
                result = adapter.extract(self.repo_root)
                results.append(result)
        
        return results
    
    def _next_evidence_id(self) -> str:
        """Generate next evidence ID"""
        self.evidence_counter += 1
        return f"ev{self.evidence_counter:03d}"
