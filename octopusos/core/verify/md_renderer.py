"""Markdown renderer for AgentSpec"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader


class MarkdownRenderer:
    """Render AgentSpec to Markdown using Jinja2"""
    
    def __init__(self):
        template_dir = Path(__file__).parent.parent.parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def render(self, agent_spec: dict[str, Any]) -> str:
        """
        Render AgentSpec to Markdown
        
        Args:
            agent_spec: AgentSpec dictionary
            
        Returns:
            Rendered Markdown string
        """
        template = self.env.get_template("agent.md.j2")
        return template.render(**agent_spec)
    
    def render_to_file(self, agent_spec: dict[str, Any], output_path: Path):
        """
        Render AgentSpec to Markdown file
        
        Args:
            agent_spec: AgentSpec dictionary
            output_path: Path to output file
        """
        markdown = self.render(agent_spec)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown)
