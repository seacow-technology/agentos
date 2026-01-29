"""Review pack generator for audit trail."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader
from rich.console import Console

from agentos.core.orchestrator.patch_tracker import PatchTracker

console = Console()


class ReviewPackGenerator:
    """Generates review packs for completed task runs."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize review pack generator."""
        if db_path is None:
            db_path = Path.home() / ".agentos" / "store.db"
        self.db_path = db_path
        self.patch_tracker = PatchTracker(db_path)

        # Setup Jinja2 environment
        template_dir = Path(__file__).parent.parent.parent / "templates"
        self.jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def generate(self, run_id: int, output_dir: Optional[Path] = None) -> dict:
        """
        Generate review pack for a run.

        Args:
            run_id: Task run ID
            output_dir: Directory to save review pack (optional)

        Returns:
            review_pack: ReviewPack dict
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get run info
        cursor.execute("SELECT * FROM task_runs WHERE id = ?", (run_id,))
        run_row = cursor.fetchone()

        if not run_row:
            raise ValueError(f"Run not found: {run_id}")

        # Get steps
        cursor.execute(
            """
            SELECT * FROM run_steps WHERE run_id = ? ORDER BY started_at
        """,
            (run_id,),
        )
        steps = [dict(row) for row in cursor.fetchall()]

        conn.close()

        # Get patches
        patches = self.patch_tracker.get_patches_for_run(run_id)

        # Get commits
        commits = self.patch_tracker.get_commits_for_run(run_id)

        # Build changed files list
        changed_files = self._build_changed_files_list(patches)

        # Build plan summary
        plan_summary = self._build_plan_summary(steps)

        # Build verification results
        verification_results = self._build_verification_results(steps)

        # Build risk assessment
        risk_assessment = self._build_risk_assessment(patches, changed_files)

        # Build rollback guide
        rollback_guide = self._build_rollback_guide(commits)

        # Build review pack
        review_pack = {
            "schema_version": "1.0.0",
            "task_id": run_row["task_id"],
            "run_id": run_id,
            "execution_mode": run_row["execution_mode"],
            "plan_summary": plan_summary,
            "changed_files": changed_files,
            "patches": [
                {
                    "patch_id": p["patch_id"],
                    "intent": p["intent"],
                    "files": p["files"],
                    "diff_hash": p["diff_hash"],
                }
                for p in patches
            ],
            "verification_results": verification_results,
            "risk_assessment": risk_assessment,
            "commits": [
                {
                    "hash": c["commit_hash"],
                    "message": c["commit_message"],
                    "timestamp": c["committed_at"],
                }
                for c in commits
            ],
            "rollback_guide": rollback_guide,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "started_at": run_row["started_at"],
                "completed_at": run_row["completed_at"],
                "duration_seconds": self._calculate_duration(
                    run_row["started_at"], run_row["completed_at"]
                ),
            },
        }

        # Save JSON
        if output_dir:
            self._save_json(review_pack, output_dir)
            self._render_markdown(review_pack, output_dir)

        return review_pack

    def _build_changed_files_list(self, patches: list[dict]) -> list[dict]:
        """Build list of changed files with metadata."""
        files_map = {}

        for patch in patches:
            for file_path in patch["files"]:
                if file_path not in files_map:
                    files_map[file_path] = {
                        "path": file_path,
                        "status": "modified",  # Would detect add/delete/rename in real impl
                        "lines_changed": 0,  # Would calculate from diff in real impl
                        "module": self._infer_module(file_path),
                    }

        return list(files_map.values())

    def _build_plan_summary(self, steps: list[dict]) -> dict:
        """Build plan summary from steps."""
        plan_step = next((s for s in steps if s["step_type"] == "plan"), None)

        if plan_step and plan_step.get("output_summary"):
            try:
                output = json.loads(plan_step["output_summary"])
                return {
                    "objective": output.get("objective", "N/A"),
                    "approach": output.get("approach", "N/A"),
                    "risks": output.get("risks", []),
                }
            except:
                pass

        return {"objective": "N/A", "approach": "N/A", "risks": []}

    def _build_verification_results(self, steps: list[dict]) -> dict:
        """Build verification results from steps."""
        verify_step = next((s for s in steps if s["step_type"] == "verify"), None)

        if verify_step:
            status = "passed" if verify_step["status"] == "SUCCEEDED" else "failed"
            return {
                "gates": status,
                "build": status,
                "tests": status,
                "details": [],
            }

        return {
            "gates": "skipped",
            "build": "skipped",
            "tests": "skipped",
            "details": [],
        }

    def _build_risk_assessment(self, patches: list[dict], changed_files: list[dict]) -> dict:
        """Build risk assessment."""
        # Simple heuristic based on number of files
        file_count = len(changed_files)

        if file_count <= 3:
            risk_level = "low"
        elif file_count <= 10:
            risk_level = "medium"
        else:
            risk_level = "high"

        factors = [f"{file_count} files changed"]

        return {"overall_risk": risk_level, "factors": factors}

    def _build_rollback_guide(self, commits: list[dict]) -> str:
        """Build rollback guide."""
        if not commits:
            return "No commits to rollback."

        first_commit = commits[0]["hash"]
        return f"To rollback, run: git revert {first_commit}^..HEAD"

    def _infer_module(self, file_path: str) -> str:
        """Infer module from file path (Windows 兼容)."""
        from pathlib import Path
        parts = Path(file_path).parts
        if len(parts) > 1:
            return parts[0]
        return "root"

    def _calculate_duration(self, started_at: str, completed_at: Optional[str]) -> Optional[float]:
        """Calculate duration in seconds."""
        if not completed_at:
            return None

        try:
            start = datetime.fromisoformat(started_at)
            end = datetime.fromisoformat(completed_at)
            return (end - start).total_seconds()
        except:
            return None

    def _save_json(self, review_pack: dict, output_dir: Path):
        """Save review pack as JSON."""
        output_dir.mkdir(parents=True, exist_ok=True)

        run_id = review_pack["run_id"]
        json_path = output_dir / f"review_pack_run_{run_id}.json"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(review_pack, f, indent=2)

        console.print(f"[green]✓ Review pack JSON saved:[/green] {json_path}")

    def _render_markdown(self, review_pack: dict, output_dir: Path):
        """Render review pack as Markdown."""
        try:
            template = self.jinja_env.get_template("review_pack.md.j2")

            # Prepare template variables
            files_by_module = {}
            for file in review_pack["changed_files"]:
                module = file.get("module", "unknown")
                if module not in files_by_module:
                    files_by_module[module] = []
                files_by_module[module].append(file)

            rendered = template.render(
                task_id=review_pack["task_id"],
                run_id=review_pack["run_id"],
                execution_mode=review_pack["execution_mode"],
                plan_summary=review_pack["plan_summary"],
                changed_files=review_pack["changed_files"],
                files_by_module=files_by_module,
                patches=review_pack["patches"],
                verification_results=review_pack["verification_results"],
                commits=review_pack["commits"],
                rollback_guide=review_pack["rollback_guide"],
                started_at=review_pack["metadata"].get("started_at", "N/A"),
                completed_at=review_pack["metadata"].get("completed_at", "N/A"),
            )

            run_id = review_pack["run_id"]
            md_path = output_dir / f"review_pack_run_{run_id}.md"

            with open(md_path, "w", encoding="utf-8") as f:
                f.write(rendered)

            console.print(f"[green]✓ Review pack Markdown saved:[/green] {md_path}")

        except Exception as e:
            console.print(f"[yellow]Warning: Failed to render Markdown: {e}[/yellow]")
