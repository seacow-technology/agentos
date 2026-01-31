"""Interactive CLI: Main loop for AgentOS CLI Control Plane"""

import sys
import subprocess
from typing import Optional
from pathlib import Path
from datetime import datetime, timezone

from agentos.core.task import TaskManager, RunMode, ModelPolicy, TaskMetadata
from agentos.config import load_settings, save_settings, CLISettings
from agentos.i18n import set_language, t, get_available_languages
from agentos.core.time import utc_now_iso



class InteractiveCLI:
    """Interactive CLI: Task Control Plane"""
    
    def __init__(self):
        """Initialize interactive CLI"""
        self.task_manager = TaskManager()
        self.settings = load_settings()
        self.running = True
        
        # Initialize language from settings
        set_language(self.settings.language)
    
    def run(self):
        """Run interactive loop"""
        self.print_welcome()
        
        while self.running:
            try:
                self.print_menu()
                choice = input("\n" + t("cli.interactive.menu.prompt")).strip()
                self.handle_choice(choice)
            except KeyboardInterrupt:
                print("\n\n" + t("cli.interactive.interrupt"))
                continue
            except EOFError:
                print("\n\n" + t("cli.interactive.exiting"))
                break
            except Exception as e:
                print(f"\n{t('cli.interactive.error', error=e)}")
                print(t("cli.interactive.returning"))
    
    def print_welcome(self):
        """Print welcome message"""
        print("\n" + "="*60)
        print("  " + t("cli.interactive.welcome.title"))
        print("="*60)
        print("\n" + t("cli.interactive.welcome.description"))
        print(t("cli.interactive.welcome.actions") + "\n")
    
    def print_menu(self):
        """Print main menu"""
        print("\n" + "-"*60)
        print(t("cli.interactive.menu.title"))
        print("-"*60)
        print("1) " + t("cli.interactive.menu.new_task"))
        print("2) " + t("cli.interactive.menu.list_tasks"))
        print("3) " + t("cli.interactive.menu.resume_task"))
        print("4) " + t("cli.interactive.menu.inspect_task"))
        print("5) " + t("cli.interactive.menu.settings"))
        print("q) " + t("cli.interactive.menu.quit"))
        print("-"*60)
    
    def handle_choice(self, choice: str):
        """Handle user choice"""
        if choice == '1':
            self.handle_new_task()
        elif choice == '2':
            self.handle_list_tasks()
        elif choice == '3':
            self.handle_resume_task()
        elif choice == '4':
            self.handle_inspect_task()
        elif choice == '5':
            self.handle_settings()
        elif choice.lower() == 'q':
            print("\n" + t("cli.interactive.goodbye"))
            self.running = False
        else:
            print(f"\n{t('cli.interactive.invalid_choice', choice=choice)}")
    
    def handle_new_task(self):
        """Handle: Create new task"""
        print("\n" + "="*60)
        print(t("cli.task.new.title"))
        print("="*60)
        print("\n" + t("cli.task.new.hint"))
        print(t("cli.task.new.example") + "\n")
        
        nl_request = input(t("cli.task.new.prompt")).strip()
        
        if not nl_request:
            print("\n" + t("cli.task.new.empty"))
            return
        
        # Create task with metadata
        task_metadata = TaskMetadata(
            run_mode=self.settings.get_run_mode(),
            model_policy=self.settings.get_model_policy(),
            nl_request=nl_request,
            current_stage="created"
        )
        
        task = self.task_manager.create_task(
            title=nl_request[:100],  # Truncate title
            metadata=task_metadata.to_dict(),
            created_by="interactive_cli"
        )
        
        # Record lineage
        self.task_manager.add_lineage(
            task_id=task.task_id,
            kind="nl_request",
            ref_id=task.task_id,
            phase="creation",
            metadata={"request": nl_request}
        )
        
        print(f"\n{t('cli.task.new.created')}")
        print(t("cli.task.new.task_id", task_id=task.task_id))
        print(t("cli.task.new.run_mode", run_mode=task.get_run_mode()))
        print(t("cli.task.new.status", status=task.status))
        
        # P1: Ask if user wants to use real pipeline
        print(f"\n{t('cli.task.new.exec_mode')}")
        print(t("cli.task.new.exec_mode_simulated"))
        print(t("cli.task.new.exec_mode_real"))
        
        exec_mode = input("\n" + t("cli.task.new.exec_mode_prompt")).strip() or "1"
        use_real_pipeline = (exec_mode == "2")
        
        # Ask if user wants to start execution now
        start_now = input("\n" + t("cli.task.new.start_now")).strip().lower()
        
        if start_now != 'n':
            self.start_task_runner(task.task_id, use_real_pipeline=use_real_pipeline)
        else:
            print(f"\n{t('cli.task.new.resume_hint')}")
    
    def start_task_runner(self, task_id: str, use_real_pipeline: bool = False):
        """Start background task runner as subprocess
        
        Args:
            task_id: Task ID to run
            use_real_pipeline: If True, use real ModePipelineRunner (P1)
        """
        print(f"\n{t('cli.task.runner.starting')}")
        
        # P1: Check if user wants to use real pipeline
        if use_real_pipeline:
            print(t("cli.task.runner.mode_real"))
        else:
            print(t("cli.task.runner.mode_simulated"))
        
        try:
            # Start runner as subprocess
            # P1: Pass --real-pipeline flag if needed
            cmd = [sys.executable, "-m", "agentos.core.runner.task_runner", task_id]
            if use_real_pipeline:
                cmd.append("--real-pipeline")
            
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Detach from parent
            )
            
            print(t("cli.task.runner.started"))
            print(t("cli.task.runner.background"))
            print(t("cli.task.runner.check_hint"))
            
        except Exception as e:
            print(f"\n{t('cli.task.runner.error', error=e)}")
            print(t("cli.task.runner.manual_hint", task_id=task_id))
    
    def handle_list_tasks(self):
        """Handle: List tasks"""
        print("\n" + "="*60)
        print(t("cli.task.list.title"))
        print("="*60)
        
        # Get filters
        print("\n" + t("cli.task.list.filter"))
        print(t("cli.task.list.filter_all"))
        print(t("cli.task.list.filter_status"))
        print(t("cli.task.list.filter_orphan"))
        
        filter_choice = input("\n" + t("cli.task.list.filter_prompt")).strip() or "1"
        
        status_filter = None
        orphan_only = False
        
        if filter_choice == "2":
            status_filter = input(t("cli.task.list.status_prompt")).strip()
        elif filter_choice == "3":
            orphan_only = True
        
        # List tasks
        tasks = self.task_manager.list_tasks(
            limit=20,
            status_filter=status_filter,
            orphan_only=orphan_only
        )
        
        if not tasks:
            print("\n" + t("cli.task.list.not_found"))
            return
        
        print(f"\n{t('cli.task.list.found', count=len(tasks))}\n")
        print(f"{t('cli.task.list.header_id'):<20} {t('cli.task.list.header_status'):<15} {t('cli.task.list.header_title'):<50}")
        print("-" * 85)
        
        for task in tasks:
            task_id_short = task.task_id[:18] + ".."
            status = task.status
            title = task.title[:47] + "..." if len(task.title) > 50 else task.title
            print(f"{task_id_short:<20} {status:<15} {title:<50}")
    
    def handle_resume_task(self):
        """Handle: Resume/start task"""
        print("\n" + "="*60)
        print(t("cli.task.resume.title"))
        print("="*60)
        print("\n" + t("cli.task.resume.hint") + "\n")
        
        task_id = input(t("cli.task.resume.task_id_prompt")).strip()
        
        if task_id.lower() == 'list':
            self.handle_list_tasks()
            return
        
        if not task_id:
            print("\n" + t("cli.task.resume.empty"))
            return
        
        # Get task
        try:
            task = self.task_manager.get_task(task_id)
        except Exception as e:
            print(f"\n{t('cli.task.resume.not_found', task_id=task_id)}")
            return
        
        print(f"\n{t('cli.task.resume.info')}")
        print(t("cli.task.resume.id", task_id=task.task_id))
        print(t("cli.task.resume.title_label", title=task.title))
        print(t("cli.task.resume.status", status=task.status))
        print(t("cli.task.resume.run_mode", run_mode=task.get_run_mode()))
        
        # Check status and show appropriate actions
        if task.status == "awaiting_approval":
            self.show_approval_menu(task)
        elif task.status in ["created", "failed"]:
            print(f"\n{t('cli.task.resume.current_status', status=task.status)}")
            start = input("\n" + t("cli.task.resume.start_prompt")).strip().lower()
            if start == 'y':
                # Reset status if failed
                if task.status == "failed":
                    self.task_manager.update_task_status(task_id, "created")
                self.start_task_runner(task_id)
        elif task.status == "succeeded":
            print("\n" + t("cli.task.resume.succeeded"))
        else:
            print(f"\n{t('cli.task.resume.current_status', status=task.status)}")
            print(t("cli.task.resume.executing"))
    
    def show_approval_menu(self, task):
        """Show approval menu for awaiting_approval tasks"""
        print("\n" + "-"*60)
        print(t("cli.task.approval.title"))
        print("-"*60)
        print("\n" + t("cli.task.approval.approve"))
        print(t("cli.task.approval.view_plan"))
        print(t("cli.task.approval.abort"))
        print(t("cli.task.approval.back"))
        
        choice = input("\n" + t("cli.task.approval.prompt")).strip()
        
        if choice == "1":
            self.approve_task(task.task_id)
        elif choice == "2":
            self.view_plan_details(task.task_id)
        elif choice == "3":
            self.abort_task(task.task_id)
    
    def approve_task(self, task_id: str):
        """Approve task and continue execution
        
        P2-2: Records approval event in lineage and audit
        """
        try:
            # P2-2: Record approval lineage BEFORE updating status
            self.task_manager.add_lineage(
                task_id=task_id,
                kind="approval",
                ref_id="approved",
                phase="awaiting_approval",
                metadata={
                    "action": "approved",
                    "approved_by": "cli_user",  # Could be enhanced with actual user ID
                    "approved_at": utc_now_iso()
                }
            )
            
            # Also add audit log
            self.task_manager.add_audit(
                task_id=task_id,
                event_type="task_approved",
                level="info",
                payload={
                    "action": "approved",
                    "checkpoint": "open_plan",
                    "approved_by": "cli_user"
                }
            )
            
            # Update status to executing
            self.task_manager.update_task_status(task_id, "executing")
            print(f"\n{t('cli.task.approval.approved')}")
            print(t("cli.task.approval.lineage_recorded"))
            
            # Restart runner
            print(t("cli.task.approval.restarting"))
            self.start_task_runner(task_id)
            
        except Exception as e:
            print(f"\n{t('cli.interactive.error', error=e)}")
    
    def abort_task(self, task_id: str):
        """Abort task"""
        try:
            self.task_manager.update_task_status(task_id, "canceled")
            print(f"\n{t('cli.task.approval.aborted')}")
        except Exception as e:
            print(f"\n{t('cli.interactive.error', error=e)}")
    
    def view_plan_details(self, task_id: str):
        """View plan details
        
        P2-C1: Show open_plan proposal from artifact file
        """
        print("\n" + "-"*60)
        print(t("cli.task.plan.title"))
        print("-"*60)
        
        try:
            trace = self.task_manager.get_trace(task_id)
            
            # P2-C1: Find artifact in lineage
            artifact_entries = [
                entry for entry in trace.timeline
                if entry.kind == "artifact" and 
                entry.metadata and 
                entry.metadata.get("artifact_kind") == "open_plan"
            ]
            
            if not artifact_entries:
                print("\n" + t("cli.task.plan.not_found"))
                print(t("cli.task.plan.not_found_detail"))
                
                # Fallback: Show lineage entries (for backward compatibility)
                open_plan_entries = [
                    entry for entry in trace.timeline
                    if 'open_plan' in entry.kind or 'open_plan' in entry.phase
                ]
                
                if open_plan_entries:
                    print(f"\n{t('cli.task.plan.old_format', count=len(open_plan_entries))}")
                    for i, entry in enumerate(open_plan_entries[:3], 1):
                        print(f"{i}. [{entry.kind}] {entry.ref_id} @ {entry.timestamp}")
                
                return
            
            # Get the latest artifact
            latest_artifact = artifact_entries[-1]
            artifact_path_rel = latest_artifact.ref_id
            
            print(f"\n{t('cli.task.plan.artifact', path=artifact_path_rel)}")
            print(t("cli.task.plan.generated", timestamp=latest_artifact.timestamp))
            
            # Read artifact file
            from pathlib import Path
            import json
            
            artifact_path = Path("store") / artifact_path_rel
            
            if not artifact_path.exists():
                print(f"\n{t('cli.task.plan.file_missing', path=artifact_path)}")
                return
            
            with open(artifact_path, 'r', encoding='utf-8') as f:
                artifact_data = json.load(f)
            
            # Display summary (first 30 lines or key fields)
            print("\n" + "="*60)
            print(t("cli.task.plan.summary_title"))
            print("="*60)
            
            print(f"\n{t('cli.task.plan.task_id', task_id=artifact_data.get('task_id'))}")
            print(t("cli.task.plan.generated_at", generated_at=artifact_data.get('generated_at')))
            print(t("cli.task.plan.pipeline_status", status=artifact_data.get('pipeline_status')))
            print(t("cli.task.plan.pipeline_summary", summary=artifact_data.get('pipeline_summary')))
            
            stages = artifact_data.get('stages', [])
            if stages:
                print(f"\n{t('cli.task.plan.stages_count', count=len(stages))}")
                for i, stage in enumerate(stages[:3], 1):  # Show first 3 stages
                    print(f"\n{i}. {stage.get('stage')}")
                    print(t("cli.task.plan.stage_status", status=stage.get('status')))
                    summary = stage.get('summary', '')
                    if summary:
                        # Truncate long summaries
                        if len(summary) > 200:
                            summary = summary[:200] + "..."
                        print(t("cli.task.plan.stage_summary", summary=summary))
                
                if len(stages) > 3:
                    print(f"\n{t('cli.task.plan.stages_more', count=len(stages) - 3)}")
            
            print("\n" + "="*60)
            print(f"\n{t('cli.task.plan.full_content', path=artifact_path)}")
            print(t("cli.task.plan.file_size", size=artifact_path.stat().st_size))
            
        except Exception as e:
            print(f"\n{t('cli.interactive.error', error=e)}")
            import traceback
            traceback.print_exc()
    
    def handle_inspect_task(self):
        """Handle: Inspect task details"""
        print("\n" + "="*60)
        print(t("cli.task.inspect.title"))
        print("="*60)
        
        task_id = input("\n" + t("cli.task.inspect.task_id_prompt")).strip()
        
        if not task_id:
            print("\n" + t("cli.task.inspect.empty"))
            return
        
        try:
            task = self.task_manager.get_task(task_id)
            trace = self.task_manager.get_trace(task_id)
        except Exception as e:
            print(f"\n{t('cli.interactive.error', error=e)}")
            return
        
        # Print task details
        print(f"\n{t('cli.task.inspect.details')}")
        print(t("cli.task.inspect.id", task_id=task.task_id))
        print(t("cli.task.inspect.title_label", title=task.title))
        print(t("cli.task.inspect.status", status=task.status))
        print(t("cli.task.inspect.run_mode", run_mode=task.get_run_mode()))
        print(t("cli.task.inspect.created_at", created_at=task.created_at))
        print(t("cli.task.inspect.updated_at", updated_at=task.updated_at))
        print(t("cli.task.inspect.created_by", created_by=task.created_by))
        
        if task.metadata.get("nl_request"):
            print(f"\n{t('cli.task.inspect.nl_request')}")
            print(f"  {task.metadata['nl_request']}")
        
        # Print timeline
        if trace.timeline:
            print(f"\n{t('cli.task.inspect.timeline')}")
            for entry in trace.timeline[-5:]:
                print(f"  [{entry.kind}] {entry.ref_id} (phase: {entry.phase})")
        
        # Print audits
        if trace.audits:
            print(f"\n{t('cli.task.inspect.audits')}")
            for audit in trace.audits[-5:]:
                level = audit.get("level", "info")
                message = audit.get("message", "")
                print(f"  [{level}] {message}")
    
    def handle_settings(self):
        """Handle: Settings management"""
        print("\n" + "="*60)
        print(t("cli.settings.title"))
        print("="*60)
        
        while True:
            print(f"\n{t('cli.settings.current')}")
            print(t("cli.settings.run_mode", mode=self.settings.default_run_mode))
            print(t("cli.settings.model_policy"))
            print(t("cli.settings.executor_limits"))
            
            # Get current language display name
            available_langs = get_available_languages()
            current_lang_display = available_langs.get(self.settings.language, self.settings.language)
            print(t("cli.settings.language", language=current_lang_display))
            
            print(t("cli.settings.back"))
            
            choice = input("\n" + t("cli.settings.prompt")).strip()
            
            if choice == "1":
                self.update_run_mode()
            elif choice == "2":
                self.update_model_policy()
            elif choice == "3":
                self.update_executor_limits()
            elif choice == "4":
                self.update_language()
            elif choice == "5":
                break
            else:
                print(f"\n{t('cli.interactive.invalid_choice', choice=choice)}")
    
    def update_run_mode(self):
        """Update default run mode"""
        print("\n" + t("cli.settings.run_mode.title"))
        print(t("cli.settings.run_mode.interactive"))
        print(t("cli.settings.run_mode.assisted"))
        print(t("cli.settings.run_mode.autonomous"))
        
        choice = input("\n" + t("cli.settings.run_mode.prompt")).strip()
        
        mode_map = {
            "1": "interactive",
            "2": "assisted",
            "3": "autonomous"
        }
        
        if choice in mode_map:
            self.settings.default_run_mode = mode_map[choice]
            save_settings(self.settings)
            print(f"\n{t('cli.settings.run_mode.updated', mode=self.settings.default_run_mode)}")
        else:
            print(f"\n{t('cli.settings.run_mode.invalid', choice=choice)}")
    
    def update_model_policy(self):
        """Update model policy"""
        print(f"\n{t('cli.settings.model_policy.current')}")
        for stage, model in self.settings.default_model_policy.items():
            print(f"  {stage}: {model}")
        
        print(f"\n{t('cli.settings.model_policy.hint')}")
        print(t("cli.settings.model_policy.config_path"))
    
    def update_executor_limits(self):
        """Update executor limits"""
        print(f"\n{t('cli.settings.executor_limits.current')}")
        for key, value in self.settings.executor_limits.items():
            print(f"  {key}: {value}")
        
        print(f"\n{t('cli.settings.executor_limits.hint')}")
        print(t("cli.settings.executor_limits.config_path"))
    
    def update_language(self):
        """Update language setting"""
        print("\n" + "="*60)
        print(t("cli.settings.language.title"))
        print("="*60)
        
        # Get available languages
        available_langs = get_available_languages()
        lang_list = list(available_langs.items())
        
        print()
        for i, (code, name) in enumerate(lang_list, 1):
            current_marker = " ✓" if code == self.settings.language else ""
            print(f"{i}) {name}{current_marker}")
        
        choice = input("\n" + t("cli.settings.language.prompt", count=len(lang_list))).strip()
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(lang_list):
                lang_code = lang_list[idx][0]
                lang_name = lang_list[idx][1]
                
                # Update settings
                self.settings.set_language(lang_code)
                save_settings(self.settings)
                
                # Apply language change immediately
                set_language(lang_code)
                
                print(f"\n{t('cli.settings.language.updated', language=lang_name)}")
                print(t("cli.settings.language.restart_hint"))
            else:
                print(f"\n{t('cli.settings.language.invalid', choice=choice)}")
        except ValueError:
            print(f"\n{t('cli.settings.language.invalid', choice=choice)}")


def interactive_main():
    """Main entry point for interactive CLI"""
    cli = InteractiveCLI()
    cli.run()


if __name__ == "__main__":
    interactive_main()
