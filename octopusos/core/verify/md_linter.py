"""Markdown linter for generated agent docs"""

import re
from pathlib import Path
from typing import Any, Optional


class MarkdownLinter:
    """Lint Markdown files generated from AgentSpec"""
    
    REQUIRED_SECTIONS = [
        "# ",  # Title
        "## Identity",
        "## Access Control",
        "## Workflows",
        "## Commands",
        "## Verification",
        "## Escalation Rules",
        "## Provenance"
    ]
    
    FORBIDDEN_KEYWORDS = [
        "TODO",
        "FIXME",
        "placeholder",
        "TBD",
        "XXX"
    ]
    
    def lint(self, markdown_content: str, factpack: Optional[dict] = None) -> tuple:
        """
        Lint Markdown content
        
        Args:
            markdown_content: Markdown text to lint
            factpack: Optional FactPack for provenance checking
            
        Returns:
            (is_valid, errors): Tuple of validation result and error messages
        """
        errors = []
        
        # Check required sections
        for section in self.REQUIRED_SECTIONS:
            if section not in markdown_content:
                errors.append(f"Missing required section: {section}")
        
        # Check for forbidden keywords
        for keyword in self.FORBIDDEN_KEYWORDS:
            if keyword in markdown_content:
                errors.append(f"Found forbidden keyword: {keyword}")
        
        # Check command code blocks format
        if "## Commands" in markdown_content:
            # Find commands section
            commands_match = re.search(
                r'## Commands\n(.*?)(?=\n## |\Z)',
                markdown_content,
                re.DOTALL
            )
            if commands_match:
                commands_section = commands_match.group(1)
                # Check that commands have code blocks
                if "```bash" not in commands_section and "```" in commands_section:
                    errors.append("Commands should use ```bash code blocks")
        
        # Check provenance references if FactPack provided
        if factpack:
            errors.extend(self._check_provenance(markdown_content, factpack))
        
        return len(errors) == 0, errors
    
    def lint_file(self, markdown_path: Path, factpack: Optional[dict] = None) -> tuple:
        """
        Lint Markdown file
        
        Args:
            markdown_path: Path to Markdown file
            factpack: Optional FactPack for provenance checking
            
        Returns:
            (is_valid, errors): Tuple of validation result and error messages
        """
        try:
            with open(markdown_path, encoding="utf-8") as f:
                content = f.read()
            return self.lint(content, factpack)
        except Exception as e:
            return False, [f"Error reading file: {str(e)}"]
    
    def _check_provenance(self, markdown_content: str, factpack: dict[str, Any]) -> list[str]:
        """Check that provenance evidence IDs exist in FactPack"""
        errors = []
        
        # Extract evidence IDs from markdown
        provenance_match = re.search(
            r'\*\*Evidence IDs\*\*:\s*([^\n]+)',
            markdown_content
        )
        
        if not provenance_match:
            return errors
        
        evidence_ids_str = provenance_match.group(1).strip()
        if evidence_ids_str.lower() == 'none':
            errors.append("Provenance is 'None' - should reference real evidence")
            return errors
        
        # Parse evidence IDs
        markdown_ev_ids = {
            ev_id.strip()
            for ev_id in evidence_ids_str.split(",")
            if ev_id.strip()
        }
        
        # Get FactPack evidence IDs
        factpack_ev_ids = {
            ev.get("id")
            for ev in factpack.get("evidence", [])
            if ev.get("id")
        }
        
        # Check for invalid references
        invalid_ids = markdown_ev_ids - factpack_ev_ids
        if invalid_ids:
            errors.append(
                f"Provenance references non-existent evidence IDs: {invalid_ids}"
            )
        
        return errors
