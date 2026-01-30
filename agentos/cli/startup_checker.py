"""
Startup Environment Checker

启动前环境检查和准备:
- Python 环境检测
- 本地 AI Provider 检测
- 依赖包检测
- 数据库初始化和迁移
"""

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from rich import print as rprint
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from agentos.cli.provider_checker import ProviderChecker

logger = logging.getLogger(__name__)


class StartupChecker:
    """启动环境检查器"""

    def __init__(self, auto_fix: bool = False):
        """
        初始化检查器

        Args:
            auto_fix: 是否自动修复问题（非交互模式）
        """
        self.auto_fix = auto_fix
        self.provider_checker = ProviderChecker()

    def check_environment(self) -> bool:
        """
        检查 Python 环境

        Returns:
            检查是否通过
        """
        rprint("\n[cyan]═══ 环境检测 ═══[/cyan]")

        # Python 版本
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        rprint(f"[green]✓[/green] Python 版本: {python_version}")

        # uv 工具
        has_uv = shutil.which("uv") is not None
        if has_uv:
            try:
                result = subprocess.run(
                    ["uv", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                uv_version = result.stdout.strip() if result.returncode == 0 else "unknown"
                rprint(f"[green]✓[/green] uv 工具: {uv_version}")
            except Exception:
                rprint(f"[green]✓[/green] uv 工具: 已安装")
        else:
            rprint(f"[yellow]⚠[/yellow] uv 工具: 未安装 (可选)")

        return True

    def check_providers(self) -> bool:
        """
        检测本地 AI Provider (交互式)

        Returns:
            检查是否通过
        """
        rprint("\n[cyan]═══ 检查本地 AI Provider ═══[/cyan]")

        # 获取所有 Provider 状态
        status = self.provider_checker.get_provider_status()

        # 显示检测结果
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Provider", style="cyan", width=20)
        table.add_column("状态", style="green", width=30)
        table.add_column("信息", style="dim", width=30)

        available_providers = []
        installed_providers = []

        for key, info in status.items():
            if info["available"]:
                table.add_row(
                    info["name"],
                    "[green]✓ Available[/green]",
                    info["info"]
                )
                available_providers.append(key)
                installed_providers.append(key)
            else:
                table.add_row(
                    info["name"],
                    "[red]✗ Not Available[/red]",
                    info["info"]
                )

        rprint(table)

        # 如果有多个Available的 Provider，让用户选择
        if len(available_providers) > 1:
            rprint("\n[yellow]检测到多个Available的 Provider[/yellow]")

            if self.auto_fix:
                selected = "ollama"  # 默认选择 Ollama
            else:
                # 显示选项
                provider_names = {
                    "ollama": "Ollama",
                    "lm_studio": "LM Studio",
                    "llama_cpp": "llama.cpp"
                }

                options_text = "\n".join([
                    f"  {i+1}. {provider_names.get(p, p)}"
                    for i, p in enumerate(available_providers)
                ])

                rprint(f"\n请选择默认使用的 Provider:\n{options_text}")
                choice = Prompt.ask(
                    "请输入编号",
                    choices=[str(i+1) for i in range(len(available_providers))],
                    default="1"
                )
                selected = available_providers[int(choice) - 1]

            rprint(f"[green]✓ 已选择: {status[selected]['name']}[/green]")

            # 配置选中的 provider
            return self._configure_provider(selected, installed_providers)

        # 如果有一个Available的 Provider
        elif len(available_providers) == 1:
            provider = available_providers[0]
            rprint(f"\n[green]✓ 使用 Provider: {status[provider]['name']}[/green]")

            # 配置该 provider
            return self._configure_provider(provider, installed_providers)

        # 如果没有Available的 Provider，询问是否安装 Ollama
        else:
            rprint("\n[yellow]⚠️  未检测到本地 AI Provider[/yellow]")
            rprint("[dim]建议安装 Ollama 以使用本地模型[/dim]")
            rprint("[dim]您也可以跳过安装，稍后使用云端 API (OpenAI/Anthropic 等)[/dim]")

            if self.auto_fix:
                install = True
            else:
                install = Confirm.ask("\n是否安装 Ollama?", default=True)

            if install:
                if self._install_ollama():
                    # 安装成功后配置
                    return self._configure_provider("ollama", ["ollama"])
                else:
                    return False
            else:
                rprint("[yellow]⚠️  跳过 Ollama 安装[/yellow]")
                rprint("[dim]您可以稍后在 WebUI 中配置云端 API[/dim]")
                return True

    def _configure_provider(self, provider_id: str, installed_providers: list) -> bool:
        """
        配置 Provider（启动服务、配置端口、更新配置）

        Args:
            provider_id: Provider ID (ollama, lm_studio, llama_cpp)
            installed_providers: 已安装的 provider 列表

        Returns:
            是否配置成功
        """
        if provider_id == "ollama":
            return self._configure_ollama()
        elif provider_id == "lm_studio":
            return self._configure_lm_studio()
        elif provider_id == "llama_cpp":
            return self._configure_llama_cpp()
        else:
            rprint(f"[yellow]⚠️  暂不支持自动配置 {provider_id}[/yellow]")
            return True

    def _configure_ollama(self) -> bool:
        """
        配置 Ollama

        Returns:
            是否配置成功
        """
        rprint("\n[cyan]配置 Ollama...[/cyan]")

        # 默认端口
        default_port = 11434

        # 检查服务是否运行
        is_available, info = self.provider_checker.check_ollama()

        # 判断服务是否正在运行 (check for English status)
        service_running = "Running" in info

        if not service_running:
            rprint(f"[yellow]⚠️  Ollama 服务Not Running[/yellow]")
            rprint(f"[dim]当前状态: {info}[/dim]")

            # 询问端口
            if self.auto_fix:
                port = default_port
            else:
                port_input = Prompt.ask(
                    f"请输入 Ollama 服务端口",
                    default=str(default_port)
                )
                try:
                    port = int(port_input)
                except ValueError:
                    rprint("[red]✗ 无效的端口号[/red]")
                    return False

            # 询问是否启动
            if self.auto_fix:
                start = True
            else:
                start = Confirm.ask(f"是否启动 Ollama 服务 (端口 {port})?", default=True)

            if start:
                rprint(f"\n[blue]正在启动 Ollama 服务 (端口 {port})...[/blue]")

                if self.provider_checker.start_ollama(port):
                    rprint("[green]✓ Ollama 服务启动成功[/green]")
                else:
                    rprint("[red]✗ Ollama 服务启动失败[/red]")
                    return False
            else:
                rprint("[yellow]⚠️  跳过启动 Ollama 服务[/yellow]")
                rprint("[dim]您需要手动启动: ollama serve[/dim]")

                if self.auto_fix:
                    # 非交互模式，必须启动服务
                    rprint("[red]✗ 非交互模式要求服务必须启动[/red]")
                    return False

                # 询问是否继续启动 WebUI
                continue_anyway = Confirm.ask(
                    "是否仍要继续启动 WebUI? (稍后可手动启动 Ollama)",
                    default=False
                )

                if continue_anyway:
                    rprint("[yellow]⚠️  跳过 Ollama 配置，继续启动 WebUI[/yellow]")
                    rprint("[dim]提示: 启动 Ollama 后需手动在 WebUI 中配置[/dim]")
                    return True
                else:
                    rprint("[red]✗ 已取消启动[/red]")
                    return False
        else:
            # 服务已运行
            port = default_port  # 默认端口
            rprint(f"[green]✓ Ollama 服务已运行[/green]")
            rprint(f"[dim]状态: {info}[/dim]")

        # 验证连接
        rprint("\n[cyan]验证 Ollama 连接...[/cyan]")
        success, message = self.provider_checker.verify_ollama_connection(port)

        if success:
            rprint(f"[green]✓ {message}[/green]")

            # 检查是否有模型
            if "未安装模型" in message:
                rprint("\n[yellow]⚠️  Ollama 未安装任何模型[/yellow]")
                rprint("[dim]没有模型，Chat 功能将无法使用[/dim]")

                # 提供模型下载选项
                if not self._download_ollama_models(port):
                    # 用户选择跳过或下载失败
                    if not self.auto_fix:
                        continue_anyway = Confirm.ask(
                            "是否仍要继续启动 WebUI? (稍后可手动下载模型)",
                            default=True
                        )
                        if not continue_anyway:
                            return False

            # 更新配置
            return self._update_provider_config("ollama", port)
        else:
            rprint(f"[red]✗ {message}[/red]")
            return False

    def _download_ollama_models(self, port: int = 11434) -> bool:
        """
        交互式下载 Ollama 模型

        Args:
            port: Ollama 服务端口

        Returns:
            是否下载成功
        """
        # 推荐的模型列表
        recommended_models = [
            ("llama3.2:3b", "Llama 3.2 (3B) - 快速，适合日常对话", "~2GB"),
            ("qwen2.5:7b", "Qwen 2.5 (7B) - 中文优化，推荐", "~4.7GB"),
            ("llama3.2:1b", "Llama 3.2 (1B) - 超轻量，快速响应", "~1.3GB"),
            ("gemma2:2b", "Gemma 2 (2B) - Google 开源模型", "~1.6GB"),
            ("qwen2.5-coder:7b", "Qwen 2.5 Coder (7B) - 代码专用", "~4.7GB"),
        ]

        if self.auto_fix:
            # 非交互模式，自动下载第一个推荐模型
            model_to_download = "qwen2.5:7b"
            rprint(f"\n[blue]自动下载推荐模型: {model_to_download}[/blue]")
            return self._pull_model_with_progress(model_to_download, port)

        # 交互模式
        rprint("\n[cyan]推荐的模型:[/cyan]")
        for i, (name, desc, size) in enumerate(recommended_models, 1):
            rprint(f"  {i}. [bold]{name}[/bold] - {desc} ([dim]{size}[/dim])")
        rprint("  0. 跳过，稍后手动下载")

        choice = Prompt.ask(
            "\n请选择要下载的模型",
            choices=[str(i) for i in range(len(recommended_models) + 1)],
            default="2"  # 默认选择 qwen2.5
        )

        if choice == "0":
            rprint("[yellow]⚠️  跳过模型下载[/yellow]")
            rprint("[dim]您可以稍后使用以下命令下载:[/dim]")
            rprint("[dim]  ollama pull llama3.2[/dim]")
            rprint("[dim]  ollama pull qwen2.5[/dim]")
            return False

        # 下载选中的模型
        selected_model = recommended_models[int(choice) - 1][0]
        return self._pull_model_with_progress(selected_model, port)

    def _pull_model_with_progress(self, model_name: str, port: int) -> bool:
        """
        下载模型并显示进度

        Args:
            model_name: 模型名称
            port: Ollama 服务端口

        Returns:
            是否下载成功
        """
        rprint(f"\n[blue]正在下载模型 {model_name}...[/blue]")
        rprint("[dim]这可能需要几分钟，取决于网络速度[/dim]")

        # 使用 subprocess 实时显示输出
        import subprocess

        env = os.environ.copy()
        env["OLLAMA_HOST"] = f"127.0.0.1:{port}"

        try:
            process = subprocess.Popen(
                ["ollama", "pull", model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env
            )

            # 实时显示输出
            for line in process.stdout:
                line = line.strip()
                if line:
                    # 过滤进度条的输出，只显示关键信息
                    if "pulling" in line.lower() or "success" in line.lower() or "error" in line.lower():
                        rprint(f"  [dim]{line}[/dim]")

            process.wait()

            if process.returncode == 0:
                rprint(f"[green]✓ 模型 {model_name} 下载成功[/green]")

                # 验证模型是否真的Available
                models = self.provider_checker.get_ollama_models(port)
                if model_name in models or any(model_name in m for m in models):
                    return True
                else:
                    rprint("[yellow]⚠️  模型下载完成，但未在列表中找到[/yellow]")
                    return False
            else:
                rprint(f"[red]✗ 模型 {model_name} 下载失败[/red]")
                return False

        except Exception as e:
            rprint(f"[red]✗ 下载过程出错: {e}[/red]")
            logger.error("Model download failed", exc_info=True)
            return False

    def _configure_lm_studio(self) -> bool:
        """
        配置 LM Studio

        Returns:
            是否配置成功
        """
        rprint("\n[cyan]配置 LM Studio...[/cyan]")
        rprint("[yellow]⚠️  LM Studio 需要手动启动[/yellow]")
        rprint("[dim]请启动 LM Studio 应用并加载模型[/dim]")
        rprint("[dim]默认端口: 1234[/dim]")

        # LM Studio 是手动启动的，只更新配置即可
        return self._update_provider_config("lm_studio", 1234)

    def _configure_llama_cpp(self) -> bool:
        """
        配置 llama.cpp

        Returns:
            是否配置成功
        """
        rprint("\n[cyan]配置 llama.cpp...[/cyan]")
        rprint("[yellow]⚠️  llama.cpp 需要手动启动[/yellow]")
        rprint("[dim]请运行: llama-server -m <model_path>[/dim]")
        rprint("[dim]默认端口: 8080[/dim]")

        # llama.cpp 是手动启动的，只更新配置即可
        return self._update_provider_config("llama_cpp", 8080)

    def _update_provider_config(self, provider_id: str, port: int) -> bool:
        """
        更新 Provider 配置到 ~/.agentos/config/providers.json

        Args:
            provider_id: Provider ID
            port: 端口号

        Returns:
            是否更新成功
        """
        try:
            from agentos.providers.providers_config import ProvidersConfigManager

            rprint(f"\n[cyan]更新 Provider 配置...[/cyan]")

            config_manager = ProvidersConfigManager()

            # 映射 provider_id
            config_id_map = {
                "ollama": "ollama",
                "lm_studio": "lmstudio",  # 配置文件中使用 lmstudio
                "llama_cpp": "llamacpp"   # 配置文件中使用 llamacpp
            }

            config_id = config_id_map.get(provider_id, provider_id)
            base_url = f"http://127.0.0.1:{port}"

            # 更新 instance 配置
            config_manager.update_instance(
                provider_id=config_id,
                instance_id="default",
                base_url=base_url,
                enabled=True
            )

            rprint(f"[green]✓ 已更新配置: {config_id} -> {base_url}[/green]")
            rprint(f"[dim]配置文件: ~/.agentos/config/providers.json[/dim]")

            return True

        except Exception as e:
            rprint(f"[red]✗ 更新配置失败: {e}[/red]")
            logger.error("Failed to update provider config", exc_info=True)
            return False

    def _install_ollama(self) -> bool:
        """
        安装 Ollama

        Returns:
            是否安装成功
        """
        rprint("\n[blue]正在安装 Ollama...[/blue]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task(description="下载并安装 Ollama...", total=None)

            if self.provider_checker.install_ollama():
                rprint("[green]✓ Ollama 安装成功[/green]")
                rprint("\n[dim]提示: 您可以运行以下命令下载模型:[/dim]")
                rprint("[dim]  ollama pull llama3.2[/dim]")
                rprint("[dim]  ollama pull qwen2.5[/dim]")
                return True
            else:
                rprint("[red]✗ Ollama 安装失败[/red]")
                rprint("[dim]请访问 https://ollama.com 手动安装[/dim]")
                return False

    def check_dependencies(self) -> bool:
        """
        检测 Python 依赖 (交互式)

        Returns:
            检查是否通过
        """
        rprint("\n[cyan]═══ 检查 Python 依赖 ═══[/cyan]")

        # 关键依赖包
        required_packages = [
            "fastapi",
            "uvicorn",
            "click",
            "rich",
            "websockets",
            "openai",
            "anthropic",
        ]

        missing_packages = []
        installed_packages = []

        # 检查每个包
        for pkg in required_packages:
            try:
                __import__(pkg)
                installed_packages.append(pkg)
            except ImportError:
                missing_packages.append(pkg)

        # 显示结果
        if installed_packages:
            rprint(f"[green]✓ 已安装 {len(installed_packages)} 个依赖包[/green]")

        if missing_packages:
            rprint(f"[yellow]⚠️  发现 {len(missing_packages)} 个缺失的依赖包:[/yellow]")
            for pkg in missing_packages:
                rprint(f"  [red]✗[/red] {pkg}")

            # 检查 uv 是否Available
            has_uv = shutil.which("uv") is not None

            if has_uv:
                if self.auto_fix:
                    install = True
                else:
                    install = Confirm.ask("\n是否执行 'uv sync' 安装依赖?", default=True)

                if install:
                    return self._install_dependencies_uv()
                else:
                    rprint("[red]✗ 已取消，无法继续启动[/red]")
                    return False
            else:
                rprint("\n[red]✗ 未检测到 uv 工具[/red]")
                rprint("[dim]请运行以下命令安装依赖:[/dim]")
                rprint("[dim]  pip install -e .[/dim]")
                return False
        else:
            rprint("[green]✓ 所有依赖包已安装[/green]")
            return True

    def _install_dependencies_uv(self) -> bool:
        """
        使用 uv 安装依赖

        Returns:
            是否安装成功
        """
        rprint("\n[blue]正在安装依赖...[/blue]")

        try:
            result = subprocess.run(
                ["uv", "sync"],
                capture_output=True,
                text=True,
                timeout=300  # 5 分钟超时
            )

            if result.returncode == 0:
                rprint("[green]✓ 依赖安装成功[/green]")
                return True
            else:
                rprint(f"[red]✗ 依赖安装失败:[/red]")
                rprint(f"[dim]{result.stderr}[/dim]")
                return False

        except subprocess.TimeoutExpired:
            rprint("[red]✗ 安装超时[/red]")
            return False
        except Exception as e:
            rprint(f"[red]✗ 安装失败: {e}[/red]")
            return False

    def prepare_database(self) -> bool:
        """
        准备数据库 (交互式)

        Returns:
            是否准备成功
        """
        rprint("\n[cyan]═══ 检查数据库 ═══[/cyan]")

        try:
            from agentos.store import get_db_path, init_db, get_migration_status

            db_path = get_db_path()

            # 检查数据库是否存在
            if not db_path.exists():
                rprint(f"[yellow]✗ 数据库文件不存在: {db_path}[/yellow]")

                if self.auto_fix:
                    create = True
                else:
                    create = Confirm.ask("是否创建数据库?", default=True)

                if create:
                    return self._create_database(db_path)
                else:
                    rprint("[red]✗ 已取消，无法继续启动[/red]")
                    return False
            else:
                rprint(f"[green]✓ 数据库文件存在: {db_path}[/green]")

            # 检查迁移状态
            return self._check_migrations(db_path)

        except Exception as e:
            rprint(f"[red]✗ 数据库检查失败: {e}[/red]")
            logger.error("Database check failed", exc_info=True)
            return False

    def _create_database(self, db_path: Path) -> bool:
        """
        创建数据库

        Args:
            db_path: 数据库路径

        Returns:
            是否创建成功
        """
        rprint("\n[blue]正在创建数据库...[/blue]")

        try:
            from agentos.store import init_db

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                progress.add_task(description="初始化数据库...", total=None)
                init_db(auto_migrate_after_init=False)

            rprint(f"[green]✓ 数据库已创建: {db_path}[/green]")
            return self._check_migrations(db_path)

        except Exception as e:
            rprint(f"[red]✗ 数据库创建失败: {e}[/red]")
            logger.error("Database creation failed", exc_info=True)
            return False

    def _check_migrations(self, db_path: Path) -> bool:
        """
        检查并执行数据库迁移

        Args:
            db_path: 数据库路径

        Returns:
            是否成功
        """
        rprint("\n[cyan]检查数据库迁移...[/cyan]")

        try:
            from agentos.store import get_migration_status, ensure_migrations

            status = get_migration_status(db_path)
            pending = status.get("pending_migrations", [])

            if pending:
                rprint(f"\n[yellow]发现 {len(pending)} 个待执行的迁移:[/yellow]")
                for migration in pending:
                    rprint(f"  - {migration}")

                if self.auto_fix:
                    migrate = True
                else:
                    migrate = Confirm.ask("\n是否执行数据库迁移?", default=True)

                if migrate:
                    return self._run_migrations(db_path)
                else:
                    rprint("[red]✗ 已取消，无法继续启动[/red]")
                    rprint("[dim]跳过迁移可能导致功能异常[/dim]")
                    return False
            else:
                rprint("[green]✓ 数据库已是最新版本[/green]")
                return True

        except Exception as e:
            rprint(f"[red]✗ 迁移检查失败: {e}[/red]")
            logger.error("Migration check failed", exc_info=True)
            return False

    def _run_migrations(self, db_path: Path) -> bool:
        """
        执行数据库迁移

        Args:
            db_path: 数据库路径

        Returns:
            是否执行成功
        """
        rprint("\n[blue]正在执行迁移...[/blue]")

        try:
            from agentos.store import ensure_migrations

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                progress.add_task(description="应用数据库迁移...", total=None)
                count = ensure_migrations(db_path)

            rprint(f"[green]✓ 成功应用 {count} 个迁移[/green]")
            return True

        except Exception as e:
            rprint(f"[red]✗ 迁移执行失败: {e}[/red]")
            logger.error("Migration execution failed", exc_info=True)
            return False

    def run_all_checks(self) -> bool:
        """
        执行所有检查

        Returns:
            是否全部通过
        """
        # Phase 1: 环境检测
        if not self.check_environment():
            rprint("\n[red]✗ 环境检测失败，已中止[/red]")
            return False

        # Phase 2: Provider 检测
        if not self.check_providers():
            rprint("\n[red]✗ Provider 检测失败，已中止[/red]")
            return False

        # Phase 3: 依赖检测
        if not self.check_dependencies():
            rprint("\n[red]✗ 依赖检测失败，已中止[/red]")
            return False

        # Phase 4: 数据库准备
        if not self.prepare_database():
            rprint("\n[red]✗ 数据库准备失败，已中止[/red]")
            return False

        # 所有检查通过
        rprint("\n[green]✓ 所有检查通过，准备启动 WebUI[/green]")
        return True
