""".NET adapter"""

from pathlib import Path
from typing import Any

from agentos.adapters.base import BaseAdapter


class DotnetAdapter(BaseAdapter):
    """Adapter for .NET projects"""
    
    @property
    def name(self) -> str:
        return "dotnet"
    
    @property
    def capabilities(self) -> dict[str, Any]:
        return {
            "project_type": ["backend", "fullstack"],
            "framework": ["dotnet", "aspnetcore"],
            "language": ["csharp", "fsharp"],
            "build_system": ["dotnet"],
            "package_manager": ["nuget"],
            "features": ["aot_compilation", "dependency_injection"],
            "confidence": 0.90
        }
    
    def detect(self, repo_root: Path) -> bool:
        """Detect .NET project"""
        # Check for .csproj or .sln
        has_csproj = bool(list(repo_root.glob("*.csproj")))
        has_sln = bool(list(repo_root.glob("*.sln")))
        
        return has_csproj or has_sln
    
    def extract(self, repo_root: Path) -> dict[str, Any]:
        """Extract .NET project information"""
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
        
        # Check for .csproj files
        csproj_files = list(repo_root.glob("*.csproj"))
        if csproj_files:
            # Assume first csproj is main project
            main_csproj = csproj_files[0]
            
            result["detected_projects"].append({
                "type": "backend",
                "framework": "dotnet",
                "root_path": ".",
                "language": "csharp"
            })
            
            result["evidence"].append({
                "id": next_ev_id(),
                "source_file": main_csproj.name,
                "category": "config",
                "description": ".NET project file"
            })
            
            result["constraints"]["project_file"] = main_csproj.name
        
        # Check for .sln files
        sln_files = list(repo_root.glob("*.sln"))
        if sln_files:
            result["evidence"].append({
                "id": next_ev_id(),
                "source_file": sln_files[0].name,
                "category": "config",
                "description": ".NET solution file"
            })
        
        # Standard .NET commands
        result["commands"] = {
            "build": "dotnet build",
            "test": "dotnet test",
            "run": "dotnet run",
            "restore": "dotnet restore",
            "clean": "dotnet clean"
        }
        
        # Add evidence for commands
        for cmd_name in result["commands"]:
            result["evidence"].append({
                "id": next_ev_id(),
                "source_file": ".NET SDK",
                "category": "script",
                "description": f"Standard .NET command: {cmd_name}"
            })
        
        # Check for Program.cs
        program_cs = repo_root / "Program.cs"
        if program_cs.exists():
            result["evidence"].append({
                "id": next_ev_id(),
                "source_file": "Program.cs",
                "category": "code",
                "description": "Main program entry point"
            })
        
        # Check for appsettings.json
        appsettings = repo_root / "appsettings.json"
        if appsettings.exists():
            result["constraints"]["config_file"] = "appsettings.json"
            result["evidence"].append({
                "id": next_ev_id(),
                "source_file": "appsettings.json",
                "category": "config",
                "description": "Application settings"
            })
        
        # Check for docs
        docs_dir = repo_root / "docs"
        if docs_dir.exists() and docs_dir.is_dir():
            result["governance"]["docs_root"] = "docs/"
            result["evidence"].append({
                "id": next_ev_id(),
                "source_file": "docs/",
                "category": "documentation",
                "description": "Documentation directory"
            })
        
        return result
