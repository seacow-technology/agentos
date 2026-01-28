"""ProjectKB CLI - Project Knowledge Base Command Line Tool

Provides commands:
- agentos kb search <query>  - Search documents
- agentos kb refresh         - Refresh index
- agentos kb explain <chunk_id> - Explain results
- agentos kb stats           - Show statistics
"""

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from agentos.core.project_kb.service import ProjectKBService

console = Console()


@click.group()
def kb():
    """ProjectKB - Project Knowledge Base retrieval"""
    pass


@kb.command()
@click.argument("query")
@click.option("--scope", help="Path prefix filter (e.g. docs/architecture/)")
@click.option("--doc-type", help="Document type filter (adr/runbook/spec/guide)")
@click.option("--top-k", default=10, help="Number of results to return")
@click.option("--explain/--no-explain", default=True, help="Show explanation")
@click.option("--json", "output_json", is_flag=True, help="JSON format output")
@click.option("--rerank/--no-rerank", default=None, help="Use vector rerank (override config)")
def search(query, scope, doc_type, top_k, explain, output_json, rerank):
    """Search documents

    Examples:
        agentos kb search "JWT authentication"
        agentos kb search "API design" --scope docs/architecture/
        agentos kb search "deployment" --doc-type runbook
        agentos kb search "authentication" --rerank  # Force use rerank
    """
    try:
        kb_service = ProjectKBService()

        filters = {}
        if doc_type:
            filters["doc_type"] = doc_type

        results = kb_service.search(
            query=query,
            scope=scope,
            filters=filters,
            top_k=top_k,
            explain=explain,
            use_rerank=rerank,
        )

        if output_json:
            # JSON 输出
            output = {
                "query": query,
                "results": [r.to_dict() for r in results],
            }
            console.print_json(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            # 人类可读输出
            if not results:
                console.print(f"[yellow]No results found for: {query}[/yellow]")
                return

            console.print(f"\n[bold]🔍 Search:[/bold] {query}")
            console.print(f"[dim]Found {len(results)} result(s)[/dim]\n")

            for i, result in enumerate(results, start=1):
                console.print(f"[bold cyan][{i}][/bold cyan] {result.path}")
                if result.heading:
                    console.print(f"    Section: [green]{result.heading}[/green]")
                console.print(f"    Lines: {result.lines}")
                console.print(f"    Score: [yellow]{result.score:.2f}[/yellow]")

                if explain:
                    exp = result.explanation
                    console.print(f"    Matched: {', '.join(exp.matched_terms)}")
                    
                    # P2: 显示向量评分 (如果有)
                    if exp.vector_score is not None:
                        console.print(f"    [dim]Vector: {exp.vector_score:.3f}, "
                                    f"Alpha: {exp.alpha:.2f}, "
                                    f"Rerank Δ: {exp.rerank_delta:+d}[/dim]")

                # 显示片段预览 (前 200 chars)
                preview = result.content[:200].replace("\n", " ")
                if len(result.content) > 200:
                    preview += "..."
                console.print(f"    [dim]{preview}[/dim]")
                console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


@kb.command()
@click.option("--changed-only/--full", default=True, help="Incremental/full refresh")
@click.option("--verbose", is_flag=True, help="Show detailed information")
def refresh(changed_only, verbose):
    """Refresh index (scan documents and update)

    Examples:
        agentos kb refresh              # Incremental refresh
        agentos kb refresh --full       # Full refresh
        agentos kb refresh --verbose    # Show detailed information
    """
    try:
        kb_service = ProjectKBService()

        console.print("[bold]Refreshing ProjectKB index...[/bold]")

        with console.status("[cyan]Scanning documents...[/cyan]"):
            report = kb_service.refresh(changed_only=changed_only)

        # 显示结果
        console.print("\n[bold green]✓ Refresh complete![/bold green]\n")

        table = Table(show_header=False)
        table.add_row("Total files", str(report.total_files))
        table.add_row("Changed files", str(report.changed_files))
        if report.deleted_files > 0:
            table.add_row("Deleted files", str(report.deleted_files))
        table.add_row("Total chunks", str(report.total_chunks))
        table.add_row("New chunks", str(report.new_chunks))
        table.add_row("Duration", f"{report.duration_seconds:.2f}s")

        console.print(table)

        if report.errors and verbose:
            console.print("\n[yellow]Errors:[/yellow]")
            for error in report.errors:
                console.print(f"  • {error}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


@kb.command()
@click.argument("chunk_id")
def explain(chunk_id):
    """Explain a single result

    Examples:
        agentos kb explain chunk_abc123
    """
    try:
        kb_service = ProjectKBService()

        chunk = kb_service.get(chunk_id)
        if not chunk:
            console.print(f"[red]Chunk not found:[/red] {chunk_id}")
            return

        console.print(f"\n[bold]Chunk:[/bold] {chunk_id}")
        console.print(f"[bold]Path:[/bold] {chunk['path']}")
        if chunk["heading"]:
            console.print(f"[bold]Section:[/bold] {chunk['heading']}")
        console.print(f"[bold]Lines:[/bold] L{chunk['start_line']}-L{chunk['end_line']}")
        console.print(f"[bold]Type:[/bold] {chunk['doc_type']}")
        console.print(f"\n[bold]Content:[/bold]")
        console.print(f"[dim]{chunk['content']}[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


@kb.command()
def stats():
    """Show statistics

    Examples:
        agentos kb stats
    """
    try:
        kb_service = ProjectKBService()

        # 获取统计信息
        total_chunks = kb_service.indexer.get_chunk_count()
        last_refresh = kb_service.indexer.get_meta("last_refresh")
        schema_version = kb_service.indexer.get_meta("schema_version")

        console.print("\n[bold]ProjectKB Statistics[/bold]\n")

        table = Table(show_header=False)
        table.add_row("Total chunks", str(total_chunks))
        table.add_row("Schema version", schema_version or "N/A")

        if last_refresh:
            from datetime import datetime
            refresh_time = datetime.fromtimestamp(int(last_refresh))
            table.add_row("Last refresh", refresh_time.strftime("%Y-%m-%d %H:%M:%S"))

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


@kb.command()
@click.argument("chunk_id")
def inspect(chunk_id):
    """Inspect chunk details (inspect command)

    Examples:
        agentos kb inspect chunk_abc123
    """
    try:
        from agentos.core.command import get_registry, CommandContext
        
        registry = get_registry()
        context = CommandContext()
        result = registry.execute("kb:inspect", context, chunk_id=chunk_id)
        
        if not result.is_success():
            console.print(f"[red]Error:[/red] {result.error}")
            return
        
        chunk = result.data
        console.print(f"\n[bold]Chunk:[/bold] {chunk_id}")
        console.print(f"[bold]Path:[/bold] {chunk['path']}")
        if chunk.get("heading"):
            console.print(f"[bold]Section:[/bold] {chunk['heading']}")
        console.print(f"[bold]Lines:[/bold] L{chunk['start_line']}-L{chunk['end_line']}")
        console.print(f"[bold]Type:[/bold] {chunk['doc_type']}")
        console.print(f"[bold]Tokens:[/bold] {chunk.get('token_count', 'N/A')}")
        
        # Show metadata
        console.print(f"\n[bold]Metadata:[/bold]")
        console.print(f"  Source ID: {chunk['source_id']}")
        console.print(f"  Chunk ID: {chunk_id}")
        console.print(f"  Content Hash: {chunk.get('content_hash', 'N/A')[:12]}...")
        
        console.print(f"\n[bold]Content:[/bold]")
        console.print(f"[dim]{chunk['content']}[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


@kb.command()
@click.argument("queries_file")
@click.option("--k-values", default="1,3,5,10", help="K values for recall@k (comma-separated)")
@click.option("--rerank/--no-rerank", default=None, help="Use vector rerank")
@click.option("--json", "output_json", is_flag=True, help="JSON format output")
def eval(queries_file, k_values, rerank, output_json):
    """Evaluate retrieval quality

    queries_file format (JSONL):
    {"query": "JWT auth", "expected_chunk_ids": ["chunk_abc", "chunk_def"]}

    Examples:
        agentos kb eval queries.jsonl
        agentos kb eval queries.jsonl --k-values 1,5,10
        agentos kb eval queries.jsonl --rerank
    """
    try:
        from agentos.core.command import get_registry, CommandContext
        
        # Parse k values
        k_vals = [int(k.strip()) for k in k_values.split(",")]
        
        registry = get_registry()
        context = CommandContext()
        result = registry.execute(
            "kb:eval", 
            context, 
            queries_file=queries_file,
            k_values=k_vals,
            use_rerank=rerank
        )
        
        if not result.is_success():
            console.print(f"[red]Error:[/red] {result.error}")
            return
        
        metrics = result.data
        
        if output_json:
            console.print_json(json.dumps(metrics, indent=2))
        else:
            console.print(f"\n[bold]KB Evaluation Results[/bold]\n")
            
            table = Table(show_header=True)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Total Queries", str(metrics["total_queries"]))
            table.add_row("Hit Rate", f"{metrics['hit_rate']:.2%}")
            table.add_row("MRR", f"{metrics['mrr']:.3f}")
            
            console.print(table)
            
            console.print("\n[bold]Recall@K:[/bold]")
            recall_table = Table(show_header=True)
            recall_table.add_column("K", style="cyan")
            recall_table.add_column("Recall", style="green")
            
            for k, recall in sorted(metrics["recall_at_k"].items(), key=lambda x: int(x[0])):
                recall_table.add_row(str(k), f"{recall:.2%}")
            
            console.print(recall_table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


@kb.command()
@click.option("--confirm", is_flag=True, help="Confirm dangerous operation")
def reindex(confirm):
    """Full index rebuild (dangerous operation)

    Warning: This operation will clear all chunks and embeddings, then rebuild the index.

    Examples:
        agentos kb reindex --confirm
    """
    if not confirm:
        console.print("[red]Error:[/red] This is a dangerous operation.")
        console.print("Use --confirm to proceed: agentos kb reindex --confirm")
        return
    
    try:
        from agentos.core.command import get_registry, CommandContext
        
        console.print("[yellow]⚠️  Warning:[/yellow] This will clear all chunks and embeddings!")
        console.print("Press Ctrl+C to cancel...\n")
        
        import time
        time.sleep(2)
        
        registry = get_registry()
        context = CommandContext()
        
        with console.status("[cyan]Clearing index and rebuilding...[/cyan]"):
            result = registry.execute("kb:reindex", context, confirmed=True)
        
        if not result.is_success():
            console.print(f"[red]Error:[/red] {result.error}")
            return
        
        console.print("\n[bold green]✓ Reindex complete![/bold green]")
        console.print(f"Summary: {result.summary}")

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


@kb.command()
def stats():
    """Show statistics

    Examples:
        agentos kb stats
    """
    try:
        kb_service = ProjectKBService()

        # 获取统计信息
        total_chunks = kb_service.indexer.get_chunk_count()
        last_refresh = kb_service.indexer.get_meta("last_refresh")
        schema_version = kb_service.indexer.get_meta("schema_version")

        console.print("\n[bold]ProjectKB Statistics[/bold]\n")

        table = Table(show_header=False)
        table.add_row("Total chunks", str(total_chunks))
        table.add_row("Schema version", schema_version or "N/A")
        if last_refresh:
            import datetime
            dt = datetime.datetime.fromtimestamp(int(last_refresh))
            table.add_row("Last refresh", dt.strftime("%Y-%m-%d %H:%M:%S"))
        table.add_row("Database", str(kb_service.db_path))

        console.print(table)
        
        # P2: 显示 embedding 统计 (如果启用)
        if kb_service.embedding_manager:
            embed_stats = kb_service.embedding_manager.get_stats()
            console.print("\n[bold]Embedding Statistics[/bold]\n")
            
            embed_table = Table(show_header=False)
            embed_table.add_row("Total embeddings", str(embed_stats["total"]))
            for model, count in embed_stats["by_model"].items():
                embed_table.add_row(f"  Model: {model}", str(count))
            if embed_stats["latest_built_at"]:
                import datetime
                dt = datetime.datetime.fromtimestamp(embed_stats["latest_built_at"])
                embed_table.add_row("Latest built", dt.strftime("%Y-%m-%d %H:%M:%S"))
            
            console.print(embed_table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


@kb.command()
@click.option("--rebuild-fts", is_flag=True, help="Rebuild FTS index")
@click.option("--allow-drift", is_flag=True, help="Allow <5% drift tolerance (concurrent mode)")
@click.option("--cleanup-orphans", is_flag=True, default=True, help="Cleanup orphan chunks (default enabled)")
@click.option("--explain/--no-explain", default=True, help="Show detailed report")
def repair(rebuild_fts, allow_drift, cleanup_orphans, explain):
    """Repair ProjectKB (self-healing command)

    Check and repair:
    - FTS tables and triggers
    - Orphan chunks cleanup
    - Index consistency
    - Schema version signature

    Examples:
        agentos kb repair                     # 基础检查
        agentos kb repair --rebuild-fts       # 重建 FTS（强一致性）
        agentos kb repair --rebuild-fts --allow-drift  # 重建（容忍并发差异）
    """
    try:
        console.print("\n[bold]🔧 ProjectKB Repair[/bold]\n")
        
        kb_service = ProjectKBService()
        
        # 1. 检查 FTS 健康状态
        console.print("[cyan]Step 1/5:[/cyan] Checking FTS integrity...")
        fts_healthy = True
        try:
            conn = kb_service.indexer._get_connection()
            conn.execute("SELECT COUNT(*) FROM kb_chunks_fts WHERE kb_chunks_fts MATCH 'test'")
            console.print("  ✓ FTS queries working")
            conn.close()
        except Exception as e:
            console.print(f"  ✗ FTS error: {e}")
            fts_healthy = False
            rebuild_fts = True
        
        # 2. 检查触发器
        console.print("\n[cyan]Step 2/5:[/cyan] Checking triggers...")
        conn = kb_service.indexer._get_connection()
        triggers = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'kb_chunks_a%'"
        ).fetchall()
        conn.close()
        
        if len(triggers) < 3:
            console.print(f"  ✗ Missing triggers (found {len(triggers)}/3)")
            rebuild_fts = True
        else:
            console.print("  ✓ All triggers present (ai, au, ad)")
        
        # 3. 清理孤儿 chunks
        console.print("\n[cyan]Step 3/5:[/cyan] Cleaning orphan chunks...")
        if cleanup_orphans:
            cleanup_stats = kb_service.indexer.cleanup_orphan_chunks()
            if cleanup_stats["orphan_chunks_removed"] > 0:
                console.print(f"  ✓ Removed {cleanup_stats['orphan_chunks_removed']} orphan chunks")
            if cleanup_stats["orphan_embeddings_removed"] > 0:
                console.print(f"  ✓ Removed {cleanup_stats['orphan_embeddings_removed']} orphan embeddings")
            if cleanup_stats["orphan_chunks_removed"] == 0 and cleanup_stats["orphan_embeddings_removed"] == 0:
                console.print("  ✓ No orphans found")
        else:
            console.print("  ⊘ Skipped (disabled)")
        
        # 4. 重建 FTS（如果需要）
        console.print("\n[cyan]Step 4/5:[/cyan] Rebuilding FTS index...")
        if rebuild_fts:
            mode_desc = "concurrent mode" if allow_drift else "strict mode"
            console.print(f"  Rebuilding in {mode_desc}...")
            
            rebuild_stats = kb_service.indexer.rebuild_fts(allow_drift=allow_drift)
            
            console.print(f"  ✓ FTS rebuilt: {rebuild_stats['fts_count']} rows")
            
            if explain:
                if rebuild_stats["drift_ratio"] > 0:
                    console.print(f"  [yellow]⚠️  Drift detected: {rebuild_stats['drift_ratio']:.2%}[/yellow]")
                    console.print(f"     FTS: {rebuild_stats['fts_count']}, Valid chunks: {rebuild_stats['valid_chunk_count']}")
                else:
                    console.print(f"  ✓ 0 drift (perfect consistency)")
        else:
            console.print("  ⊘ Skipped (FTS is healthy)")
        
        # 5. 记录 FTS 版本签名
        console.print("\n[cyan]Step 5/5:[/cyan] Recording FTS signature...")
        kb_service.indexer.record_fts_signature(migration_version="14")
        signature = kb_service.indexer.get_fts_signature()
        console.print(f"  ✓ Signature recorded:")
        console.print(f"     Mode: {signature['fts_mode']}")
        console.print(f"     Columns: {signature['fts_columns']}")
        console.print(f"     Triggers: {signature['trigger_set']}")
        console.print(f"     Migration: v{signature['migration_version']}")
        
        # 最终验证
        if explain:
            console.print("\n[bold]Final Report:[/bold]")
            total_chunks = kb_service.indexer.get_chunk_count()
            
            table = Table(show_header=False)
            table.add_row("Total chunks", str(total_chunks))
            table.add_row("FTS status", "✓ Healthy" if fts_healthy or rebuild_fts else "✗ Unhealthy")
            table.add_row("Triggers", "✓ Complete" if len(triggers) == 3 or rebuild_fts else "✗ Incomplete")
            if cleanup_orphans:
                table.add_row("Orphans cleaned", str(cleanup_stats.get("orphan_chunks_removed", 0)))
            
            console.print(table)
        
        console.print("\n[green]✅ Repair complete![/green]")
        
    except Exception as e:
        console.print(f"\n[red]❌ Repair failed: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise click.Abort()


# P2: Embedding management subcommand group
@kb.group()
def embed():
    """Embedding management commands (vector retrieval)"""
    pass


@embed.command()
@click.option("--batch-size", default=32, help="Batch size")
@click.option("--verbose", is_flag=True, help="Show detailed progress")
def build(batch_size, verbose):
    """Generate embeddings for all chunks

    Install first: pip install agentos[vector]

    Examples:
        agentos kb embed build
        agentos kb embed build --batch-size 64
    """
    try:
        kb_service = ProjectKBService()

        if not kb_service.embedding_manager:
            console.print(
                "[red]Error:[/red] Vector rerank not enabled or dependencies not installed."
            )
            console.print("Enable in config: vector_rerank.enabled = true")
            console.print("Install deps: pip install agentos[vector]")
            return

        console.print("[bold]Building embeddings for all chunks...[/bold]\n")

        # 获取所有 chunks
        chunks = kb_service._get_chunks_for_embedding(changed_only=False)

        if not chunks:
            console.print("[yellow]No chunks found.[/yellow]")
            return

        console.print(f"Total chunks: {len(chunks)}\n")

        # 生成 embeddings
        with console.status("[cyan]Generating embeddings...[/cyan]"):
            stats = kb_service.embedding_manager.build_embeddings(
                chunks, batch_size=batch_size, show_progress=verbose
            )

        console.print("\n[bold green]✓ Build complete![/bold green]\n")

        table = Table(show_header=False)
        table.add_row("Total", str(stats["total"]))
        table.add_row("Processed", str(stats["processed"]))
        table.add_row("Skipped", str(stats["skipped"]))
        if stats["errors"] > 0:
            table.add_row("[red]Errors[/red]", f"[red]{stats['errors']}[/red]")

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


@embed.command()
def refresh():
    """Incremental refresh embeddings (changed chunks only)

    Examples:
        agentos kb embed refresh
    """
    try:
        kb_service = ProjectKBService()

        if not kb_service.embedding_manager:
            console.print(
                "[red]Error:[/red] Vector rerank not enabled or dependencies not installed."
            )
            return

        console.print("[bold]Refreshing embeddings (incremental)...[/bold]\n")

        # 获取变更的 chunks
        chunks = kb_service._get_chunks_for_embedding(changed_only=True)

        if not chunks:
            console.print("[green]✓ All embeddings are up to date.[/green]")
            return

        console.print(f"Chunks to update: {len(chunks)}\n")

        # 刷新 embeddings
        with console.status("[cyan]Updating embeddings...[/cyan]"):
            stats = kb_service.embedding_manager.refresh_embeddings(chunks)

        console.print("\n[bold green]✓ Refresh complete![/bold green]\n")

        table = Table(show_header=False)
        table.add_row("Processed", str(stats["processed"]))
        table.add_row("Skipped", str(stats["skipped"]))

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


@embed.command()
def stats():
    """Show embedding statistics

    Examples:
        agentos kb embed stats
    """
    try:
        kb_service = ProjectKBService()

        if not kb_service.embedding_manager:
            console.print(
                "[red]Error:[/red] Vector rerank not enabled or dependencies not installed."
            )
            return

        embed_stats = kb_service.embedding_manager.get_stats()

        console.print("\n[bold]Embedding Statistics[/bold]\n")

        table = Table(show_header=False)
        table.add_row("Total embeddings", str(embed_stats["total"]))

        if embed_stats["by_model"]:
            for model, count in embed_stats["by_model"].items():
                table.add_row(f"  Model: {model}", str(count))

        if embed_stats["latest_built_at"]:
            import datetime

            dt = datetime.datetime.fromtimestamp(embed_stats["latest_built_at"])
            table.add_row("Latest built", dt.strftime("%Y-%m-%d %H:%M:%S"))

        console.print(table)

        # 计算覆盖率
        total_chunks = kb_service.indexer.get_chunk_count()
        total_embeddings = embed_stats["total"]
        coverage = (total_embeddings / total_chunks * 100) if total_chunks > 0 else 0

        console.print(f"\n[bold]Coverage:[/bold] {coverage:.1f}% ({total_embeddings}/{total_chunks})")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise


if __name__ == "__main__":
    kb()
