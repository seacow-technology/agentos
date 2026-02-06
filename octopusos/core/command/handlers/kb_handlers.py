"""Knowledge Base (KB) command handlers."""

from __future__ import annotations

from agentos.core.command import (
    CommandCategory,
    CommandContext,
    CommandMetadata,
    CommandRegistry,
    CommandResult,
)


def kb_search_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle kb:search command."""
    from agentos.core.project_kb.service import ProjectKBService
    
    query = kwargs.get("query")
    if not query:
        return CommandResult.failure("Query is required")
    
    scope = kwargs.get("scope")
    doc_type = kwargs.get("doc_type")
    top_k = kwargs.get("top_k", 10)
    use_rerank = kwargs.get("use_rerank")
    
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
            explain=True,
            use_rerank=use_rerank,
        )
        
        summary = f"Found {len(results)} result(s) for: {query}"
        return CommandResult.success(
            data={"results": results, "query": query},
            summary=summary
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def kb_refresh_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle kb:refresh command."""
    from agentos.core.project_kb.service import ProjectKBService
    
    full = kwargs.get("full", False)
    
    try:
        kb_service = ProjectKBService()
        stats = kb_service.refresh(full=full)
        
        mode = "Full" if full else "Incremental"
        summary = f"{mode} refresh complete"
        return CommandResult.success(data=stats, summary=summary)
    except Exception as e:
        return CommandResult.failure(str(e))


def kb_stats_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle kb:stats command."""
    from agentos.core.project_kb.service import ProjectKBService
    
    try:
        kb_service = ProjectKBService()
        stats = kb_service.stats()
        
        summary = f"Total chunks: {stats.get('total_chunks', 0)}"
        return CommandResult.success(data=stats, summary=summary)
    except Exception as e:
        return CommandResult.failure(str(e))


def kb_explain_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle kb:explain command."""
    from agentos.core.project_kb.service import ProjectKBService
    
    chunk_id = kwargs.get("chunk_id")
    if not chunk_id:
        return CommandResult.failure("chunk_id is required")
    
    try:
        kb_service = ProjectKBService()
        explanation = kb_service.explain(chunk_id)
        
        return CommandResult.success(
            data=explanation,
            summary=f"Explanation for chunk {chunk_id}"
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def kb_repair_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle kb:repair command."""
    from agentos.core.project_kb.service import ProjectKBService
    
    rebuild_fts = kwargs.get("rebuild_fts", False)
    cleanup_orphans = kwargs.get("cleanup_orphans", False)
    
    try:
        kb_service = ProjectKBService()
        result = kb_service.repair(
            rebuild_fts=rebuild_fts,
            cleanup_orphans=cleanup_orphans
        )
        
        return CommandResult.success(
            data=result,
            summary="Repair completed"
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def kb_inspect_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle kb:inspect command - view chunk details."""
    from agentos.core.project_kb.service import ProjectKBService
    
    chunk_id = kwargs.get("chunk_id")
    if not chunk_id:
        return CommandResult.failure("chunk_id is required")
    
    try:
        kb_service = ProjectKBService()
        chunk = kb_service.get(chunk_id)
        
        if not chunk:
            return CommandResult.failure(f"Chunk not found: {chunk_id}")
        
        return CommandResult.success(
            data=chunk,
            summary=f"Chunk: {chunk.get('path', 'unknown')}"
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def kb_eval_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle kb:eval command - evaluate search quality."""
    from pathlib import Path
    from agentos.core.project_kb.service import ProjectKBService
    from agentos.core.project_kb.evaluator import KBEvaluator
    
    queries_file = kwargs.get("queries_file")
    if not queries_file:
        return CommandResult.failure("queries_file is required")
    
    queries_path = Path(queries_file)
    if not queries_path.exists():
        return CommandResult.failure(f"Queries file not found: {queries_file}")
    
    k_values = kwargs.get("k_values", [1, 3, 5, 10])
    use_rerank = kwargs.get("use_rerank")
    
    try:
        kb_service = ProjectKBService()
        evaluator = KBEvaluator(kb_service)
        
        queries = evaluator.load_queries_from_file(queries_path)
        metrics = evaluator.evaluate(queries, k_values=k_values, use_rerank=use_rerank)
        
        return CommandResult.success(
            data=metrics.to_dict(),
            summary=f"Evaluated {metrics.total_queries} queries"
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def kb_reindex_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle kb:reindex command - full rebuild of index."""
    from agentos.core.project_kb.service import ProjectKBService
    
    # This is a dangerous operation, should be confirmed
    confirmed = kwargs.get("confirmed", False)
    if not confirmed:
        return CommandResult.failure(
            "Reindex is a dangerous operation. Use confirmed=True to proceed."
        )
    
    try:
        kb_service = ProjectKBService()
        
        # Clear all chunks and embeddings
        kb_service.indexer.clear_all_chunks(kb_service.scanner.repo_id)
        
        # Clear embeddings if available
        if kb_service.embedding_manager:
            kb_service.embedding_manager.clear_all_embeddings()
        
        # Full refresh
        stats = kb_service.refresh(changed_only=False)
        
        return CommandResult.success(
            data=stats.__dict__,
            summary=f"Reindex complete: {stats.total_chunks} chunks"
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def register_kb_commands(registry: CommandRegistry) -> None:
    """Register all KB commands to the registry.
    
    Args:
        registry: CommandRegistry instance
    """
    commands = [
        CommandMetadata(
            id="kb:search",
            title="Search knowledge base",
            hint="Usage: kb:search <query> [--scope PATH] [--doc-type TYPE] [--top-k N]",
            category=CommandCategory.KB,
            handler=kb_search_handler,
            needs_arg=True,
            help_text="""Search documents and code in the knowledge base.

Arguments:
  query       Search query text (required)
  
Options:
  --scope     Filter by path prefix (e.g. "docs/architecture/")
  --doc-type  Filter by document type (adr/runbook/spec/guide)
  --top-k     Number of results to return (default: 10)
  --rerank    Enable vector reranking for better relevance

Examples:
  kb:search "JWT authentication"
  kb:search "API design" --scope docs/architecture/
  kb:search "deployment" --doc-type runbook --top-k 5""",
        ),
        CommandMetadata(
            id="kb:refresh",
            title="Refresh KB index",
            hint="Usage: kb:refresh [--full]",
            category=CommandCategory.KB,
            handler=kb_refresh_handler,
            help_text="""Incrementally update the knowledge base index.

Options:
  --full      Perform full refresh instead of incremental

Examples:
  kb:refresh              # Incremental refresh (only changed files)
  kb:refresh --full       # Full refresh (all files)""",
        ),
        CommandMetadata(
            id="kb:stats",
            title="KB statistics",
            hint="Show knowledge base statistics (no arguments needed)",
            category=CommandCategory.KB,
            handler=kb_stats_handler,
            help_text="""Show statistics about the knowledge base.

Displays:
  - Total number of chunks
  - Schema version
  - Last refresh time
  - Embedding statistics (if vector rerank enabled)

Example:
  kb:stats""",
        ),
        CommandMetadata(
            id="kb:explain",
            title="Explain KB result",
            hint="Usage: kb:explain <chunk_id>",
            category=CommandCategory.KB,
            handler=kb_explain_handler,
            needs_arg=True,
            help_text="""Show detailed explanation for a specific chunk.

Arguments:
  chunk_id    The ID of the chunk to explain (required)
              Get chunk_id from search results

Example:
  kb:explain chunk_abc123def456
  
Note: Run kb:search first to get chunk IDs from results""",
        ),
        CommandMetadata(
            id="kb:repair",
            title="Repair KB index",
            hint="Usage: kb:repair [--rebuild-fts] [--cleanup-orphans]",
            category=CommandCategory.KB,
            handler=kb_repair_handler,
            help_text="""Fix and optimize the knowledge base index.

Options:
  --rebuild-fts      Rebuild full-text search index
  --cleanup-orphans  Remove orphaned chunks (default: true)

Examples:
  kb:repair                      # Basic health check
  kb:repair --rebuild-fts        # Rebuild FTS index""",
        ),
        CommandMetadata(
            id="kb:inspect",
            title="Inspect KB chunk",
            hint="Usage: kb:inspect <chunk_id>",
            category=CommandCategory.KB,
            handler=kb_inspect_handler,
            needs_arg=True,
            help_text="""View detailed information about a chunk.

Arguments:
  chunk_id    The ID of the chunk to inspect (required)

Displays:
  - Chunk content
  - Source file path
  - Line numbers
  - Document type
  - Token count
  - Metadata

Example:
  kb:inspect chunk_abc123def456""",
        ),
        CommandMetadata(
            id="kb:eval",
            title="Evaluate KB search",
            hint="Usage: kb:eval <queries_file> [--k-values K1,K2,...]",
            category=CommandCategory.KB,
            handler=kb_eval_handler,
            needs_arg=True,
            help_text="""Measure search quality with test queries.

Arguments:
  queries_file    Path to JSONL file with test queries (required)
                  Format: {"query": "...", "expected_chunk_ids": [...]}

Options:
  --k-values      Comma-separated K values for recall@K (default: 1,3,5,10)
  --rerank        Enable vector reranking

Examples:
  kb:eval queries.jsonl
  kb:eval queries.jsonl --k-values 1,5,10
  kb:eval queries.jsonl --rerank""",
        ),
        CommandMetadata(
            id="kb:reindex",
            title="Reindex KB (full rebuild)",
            hint="⚠️  Dangerous: Usage: kb:reindex --confirm",
            category=CommandCategory.KB,
            handler=kb_reindex_handler,
            dangerous=True,
            help_text="""Clear and rebuild entire KB index (DANGEROUS).

⚠️  WARNING: This will delete all chunks and embeddings!

Options:
  --confirm    Required flag to confirm this dangerous operation

Example:
  kb:reindex --confirm

Note: This operation cannot be undone. Use kb:refresh for normal updates.""",
        ),
    ]
    
    registry.register_multiple(commands)
