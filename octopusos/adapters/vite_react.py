"""Vite + React adapter"""

import json
from pathlib import Path
from typing import Any

from agentos.adapters.base import BaseAdapter


class ViteReactAdapter(BaseAdapter):
    """Adapter for Vite + React projects"""
    
    @property
    def name(self) -> str:
        return "vite-react"
    
    @property
    def capabilities(self) -> dict[str, Any]:
        return {
            "project_type": ["frontend"],
            "framework": ["vite", "react"],
            "language": ["typescript", "javascript"],
            "build_system": ["vite"],
            "package_manager": ["npm", "yarn", "pnpm"],
            "features": ["hot_reload", "jsx", "tree_shaking"],
            "confidence": 0.95
        }
    
    def detect(self, repo_root: Path) -> bool:
        """Detect Vite + React project"""
        package_json = repo_root / "package.json"
        if not package_json.exists():
            return False
        
        # Check for vite.config.*
        vite_configs = list(repo_root.glob("vite.config.*"))
        if not vite_configs:
            return False
        
        # Check package.json for vite dependency
        try:
            with open(package_json, encoding="utf-8") as f:
                pkg_data = json.load(f)
                deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
                return "vite" in deps
        except Exception:
            return False
    
    def extract(self, repo_root: Path) -> dict[str, Any]:
        """Extract Vite + React project information"""
        result = {
            "detected_projects": [],
            "commands": {},
            "constraints": {},
            "governance": {},
            "evidence": []
        }
        
        evidence_id_counter = 1
        
        def next_ev_id():
            nonlocal evidence_id_counter
            ev_id = f"ev{evidence_id_counter:03d}"
            evidence_id_counter += 1
            return ev_id
        
        # Parse package.json
        package_json = repo_root / "package.json"
        if package_json.exists():
            with open(package_json, encoding="utf-8") as f:
                pkg_data = json.load(f)
            
            # Detected project
            framework_info = "vite-react"
            deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
            
            if "react" in deps:
                react_version = deps.get("react", "unknown")
                framework_info = f"vite-react-{react_version}"
            
            result["detected_projects"].append({
                "type": "frontend",
                "framework": framework_info,
                "root_path": ".",
                "language": "typescript" if "typescript" in deps else "javascript"
            })
            
            # Commands from scripts
            scripts = pkg_data.get("scripts", {})
            for script_name, script_cmd in scripts.items():
                result["commands"][script_name] = f"npm run {script_name}"
                
                # Add evidence for each script
                result["evidence"].append({
                    "id": next_ev_id(),
                    "source_file": "package.json",
                    "category": "script",
                    "snippet": f'"{script_name}": "{script_cmd}"',
                    "description": f"NPM script: {script_name}"
                })
            
            # Add evidence for vite dependency
            if "vite" in deps:
                result["evidence"].append({
                    "id": next_ev_id(),
                    "source_file": "package.json",
                    "category": "dependency",
                    "snippet": f'"vite": "{deps["vite"]}"',
                    "description": "Vite dependency detected"
                })
            
            # Add evidence for react
            if "react" in deps:
                result["evidence"].append({
                    "id": next_ev_id(),
                    "source_file": "package.json",
                    "category": "dependency",
                    "snippet": f'"react": "{deps["react"]}"',
                    "description": "React dependency detected"
                })
        
        # Check for vite.config.*
        for vite_config in repo_root.glob("vite.config.*"):
            result["constraints"]["vite_config"] = vite_config.name
            result["evidence"].append({
                "id": next_ev_id(),
                "source_file": vite_config.name,
                "category": "config",
                "snippet": "export default defineConfig({...})",
                "description": "Vite configuration file"
            })
            break
        
        # Check for tsconfig.json
        tsconfig = repo_root / "tsconfig.json"
        if tsconfig.exists():
            result["constraints"]["tsconfig"] = "tsconfig.json"
            result["evidence"].append({
                "id": next_ev_id(),
                "source_file": "tsconfig.json",
                "category": "config",
                "description": "TypeScript configuration"
            })
        
        # Check for eslint config
        for eslint_file in [".eslintrc.js", ".eslintrc.json", ".eslintrc.cjs"]:
            if (repo_root / eslint_file).exists():
                result["constraints"]["eslint_config"] = eslint_file
                result["evidence"].append({
                    "id": next_ev_id(),
                    "source_file": eslint_file,
                    "category": "config",
                    "description": "ESLint configuration"
                })
                break
        
        # Check for governance
        docs_dir = repo_root / "docs"
        if docs_dir.exists() and docs_dir.is_dir():
            result["governance"]["docs_root"] = "docs/"
            result["evidence"].append({
                "id": next_ev_id(),
                "source_file": "docs/",
                "category": "documentation",
                "description": "Documentation directory found"
            })
        
        # Check for gates
        gates_dir = repo_root / "scripts" / "gates"
        if gates_dir.exists() and gates_dir.is_dir():
            result["governance"]["gates"] = ["scripts/gates/"]
            result["evidence"].append({
                "id": next_ev_id(),
                "source_file": "scripts/gates/",
                "category": "documentation",
                "description": "Gates directory found"
            })
        
        # Check for CI
        ci_config = repo_root / ".github" / "workflows"
        if ci_config.exists() and ci_config.is_dir():
            result["governance"]["ci_config"] = ".github/workflows/"
            result["evidence"].append({
                "id": next_ev_id(),
                "source_file": ".github/workflows/",
                "category": "config",
                "description": "GitHub Actions workflows found"
            })
        
        return result
