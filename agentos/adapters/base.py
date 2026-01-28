"""Base adapter interface"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseAdapter(ABC):
    """Base class for all technology stack adapters"""
    
    @abstractmethod
    def detect(self, repo_root: Path) -> bool:
        """
        Detect if this adapter applies to the given repository
        
        Args:
            repo_root: Path to repository root
            
        Returns:
            True if this adapter can handle the repo
        """
        pass
    
    @abstractmethod
    def extract(self, repo_root: Path) -> dict[str, Any]:
        """
        Extract information from the repository
        
        Args:
            repo_root: Path to repository root
            
        Returns:
            Dictionary with detected_projects, commands, constraints, governance, evidence
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Adapter name"""
        pass
    
    @property
    def capabilities(self) -> dict[str, Any]:
        """
        Adapter capabilities declaration
        
        Returns:
            Dictionary describing what this adapter can handle
        """
        return {
            "project_type": [],
            "framework": [],
            "language": [],
            "build_system": [],
            "package_manager": [],
            "features": [],
            "confidence": 0.5  # 0.0 to 1.0
        }
