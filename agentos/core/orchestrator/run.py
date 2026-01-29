"""Orchestrator for running tasks"""

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rich.console import Console

from agentos.core.generator import AgentSpecBuilder
from agentos.core.scanner import ScannerPipeline
from agentos.core.verify import MarkdownRenderer, validate_factpack
from agentos.store import get_db

console = Console()


class Orchestrator:
    """System orchestrator for task execution"""
    
    def __init__(self, once: bool = False):
        self.once = once
        self.queue_dir = Path("queue")
        self.queue_dir.mkdir(exist_ok=True)
    
    def run(self):
        """Run orchestrator (loop or once)"""
        console.print("🚀 [cyan]AgentOS Orchestrator started[/cyan]")
        
        if self.once:
            console.print("ℹ️  Running in once mode")
            self._process_tasks()
        else:
            console.print("ℹ️  Running in loop mode (every 30s)")
            console.print("   Press Ctrl+C to stop")
            try:
                while True:
                    self._process_tasks()
                    time.sleep(30)
            except KeyboardInterrupt:
                console.print("\n✋ Orchestrator stopped")
    
    def _process_tasks(self):
        """Process all pending tasks"""
        # Detect tasks from queue files
        tasks_from_files = self._detect_queue_files()
        
        # Detect tasks from database
        tasks_from_db = self._detect_db_tasks()
        
        all_tasks = tasks_from_files + tasks_from_db
        
        if not all_tasks:
            console.print("💤 No pending tasks")
            return
        
        console.print(f"📋 Found {len(all_tasks)} task(s)")
        
        for task in all_tasks:
            self._execute_task(task)
    
    def _detect_queue_files(self) -> list[dict]:
        """Detect tasks from queue/*.task.json files"""
        tasks = []
        for task_file in self.queue_dir.glob("*.task.json"):
            try:
                with open(task_file, encoding="utf-8") as f:
                    task_data = json.load(f)
                
                task_data["source"] = "file"
                task_data["source_file"] = str(task_file)
                tasks.append(task_data)
            except Exception as e:
                console.print(f"⚠️  [yellow]Failed to load {task_file}: {e}[/yellow]")
        
        return tasks
    
    def _detect_db_tasks(self) -> list[dict]:
        """Detect tasks from database (status=QUEUED)"""
        tasks = []
        
        try:
            db = get_db()
            cursor = db.cursor()
            
            # Find QUEUED tasks without active lease
            now = datetime.now(timezone.utc).isoformat()
            rows = cursor.execute("""
                SELECT id, project_id, type
                FROM runs
                WHERE status = 'QUEUED'
                  AND (lease_until IS NULL OR lease_until < ?)
            """, (now,)).fetchall()
            
            for row in rows:
                tasks.append({
                    "source": "db",
                    "run_id": row["id"],
                    "project_id": row["project_id"],
                    "type": row["type"],
                })
            
            db.close()
        except Exception as e:
            console.print(f"⚠️  [yellow]Failed to query database: {e}[/yellow]")
        
        return tasks
    
    def _execute_task(self, task: dict):
        """Execute a single task"""
        project_id = task.get("project_id")
        agent_type = task.get("agent_type", "default-agent")
        
        console.print(f"\n🔄 Processing task: [cyan]{project_id}[/cyan]")
        
        try:
            # Full pipeline: Scan → Generate → Render → Verify → Publish
            
            # 1. Scan
            console.print("  1️⃣  Scanning...")
            factpack = self._run_scan(project_id)
            
            # 2. Generate
            console.print("  2️⃣  Generating AgentSpec...")
            agent_spec = self._run_generate(project_id, agent_type, factpack)
            
            # 3. Render
            console.print("  3️⃣  Rendering Markdown...")
            self._run_render(project_id, agent_type, agent_spec)
            
            # 4. Publish
            console.print("  4️⃣  Publishing...")
            self._run_publish(project_id, agent_type)
            
            console.print(f"  ✅ Task completed: [green]{project_id}[/green]")
            
            # Clean up
            if task.get("source") == "file":
                source_file = Path(task["source_file"])
                source_file.unlink()
                console.print(f"  🗑️  Removed task file: {source_file.name}")
        
        except Exception as e:
            console.print(f"  ❌ [red]Task failed: {e}[/red]")
    
    def _run_scan(self, project_id: str) -> dict:
        """Run scan phase"""
        db = get_db()
        cursor = db.cursor()
        
        # Get project path
        project = cursor.execute(
            "SELECT path FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        
        if not project:
            db.close()
            raise ValueError(f"Project '{project_id}' not found")
        
        project_path = Path(project["path"])
        
        # Create run
        cursor.execute(
            "INSERT INTO runs (project_id, type, status) VALUES (?, 'orchestrate', 'RUNNING')",
            (project_id,)
        )
        run_id = cursor.lastrowid
        db.commit()
        
        # Scan
        scanner = ScannerPipeline(project_id, project_path)
        factpack = scanner.scan()
        
        # Validate
        is_valid, errors = validate_factpack(factpack)
        if not is_valid:
            cursor.execute(
                "UPDATE runs SET status = 'FAILED', error = ? WHERE id = ?",
                (f"Invalid FactPack: {errors[0]}", run_id)
            )
            db.commit()
            db.close()
            raise ValueError(f"Invalid FactPack: {errors}")
        
        # Save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = Path("reports") / project_id / timestamp
        report_dir.mkdir(parents=True, exist_ok=True)
        
        factpack_path = report_dir / "factpack.json"
        with open(factpack_path, "w", encoding="utf-8") as f:
            json.dump(factpack, f, indent=2)
        
        cursor.execute(
            "INSERT INTO artifacts (run_id, type, path) VALUES (?, 'factpack', ?)",
            (run_id, str(factpack_path))
        )
        db.commit()
        db.close()
        
        return factpack
    
    def _run_generate(self, project_id: str, agent_type: str, factpack: dict) -> dict:
        """Run generate phase"""
        builder = AgentSpecBuilder()
        agent_spec = builder.generate(factpack, agent_type)
        
        # Save
        artifacts_dir = Path("artifacts") / project_id / "spec"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        spec_path = artifacts_dir / f"{agent_type}.json"
        with open(spec_path, "w", encoding="utf-8") as f:
            json.dump(agent_spec, f, indent=2)
        
        return agent_spec
    
    def _run_render(self, project_id: str, agent_type: str, agent_spec: dict):
        """Run render phase"""
        renderer = MarkdownRenderer()
        md_dir = Path("artifacts") / project_id / "agents"
        md_path = md_dir / f"{agent_type}.md"
        renderer.render_to_file(agent_spec, md_path)
    
    def _run_publish(self, project_id: str, agent_type: str):
        """Run publish phase"""
        # Default: already published to artifacts/
        # Optional: could copy to project root if configured
        console.print(f"    📦 Published to artifacts/{project_id}/")
