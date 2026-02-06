"""Memory command handlers."""

from __future__ import annotations

from agentos.core.command import (
    CommandCategory,
    CommandContext,
    CommandMetadata,
    CommandRegistry,
    CommandResult,
)


def memory_add_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle memory:add command."""
    from agentos.core.memory import MemoryService
    
    memory_item = kwargs.get("memory_item")
    if not memory_item:
        return CommandResult.failure("memory_item is required")
    
    try:
        service = MemoryService()
        memory_id = service.upsert(memory_item)
        
        return CommandResult.success(
            data={"memory_id": memory_id},
            summary=f"Memory added: {memory_id}"
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def memory_list_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle memory:list command."""
    from agentos.core.memory import MemoryService
    
    scope = kwargs.get("scope")
    project_id = kwargs.get("project_id")
    tags = kwargs.get("tags")
    mem_type = kwargs.get("type")
    limit = kwargs.get("limit", 50)
    
    try:
        service = MemoryService()
        memories = service.list(
            scope=scope,
            project_id=project_id,
            tags=tags,
            mem_type=mem_type,
            limit=limit
        )
        
        summary = f"Found {len(memories)} memories"
        return CommandResult.success(
            data={"memories": memories},
            summary=summary
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def memory_search_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle memory:search command."""
    from agentos.core.memory import MemoryService
    
    query = kwargs.get("query")
    if not query:
        return CommandResult.failure("Query is required")
    
    scope = kwargs.get("scope")
    project_id = kwargs.get("project_id")
    limit = kwargs.get("limit", 20)
    
    try:
        service = MemoryService()
        results = service.search(
            query=query,
            scope=scope,
            project_id=project_id,
            limit=limit
        )
        
        summary = f"Found {len(results)} matching memories"
        return CommandResult.success(
            data={"results": results, "query": query},
            summary=summary
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def memory_get_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle memory:get command."""
    from agentos.core.memory import MemoryService
    
    memory_id = kwargs.get("memory_id")
    if not memory_id:
        return CommandResult.failure("memory_id is required")
    
    try:
        service = MemoryService()
        memory = service.get(memory_id)
        
        if not memory:
            return CommandResult.failure(f"Memory not found: {memory_id}")
        
        return CommandResult.success(
            data=memory,
            summary=f"Memory: {memory_id}"
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def memory_delete_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle memory:delete command."""
    from agentos.core.memory import MemoryService
    
    memory_id = kwargs.get("memory_id")
    if not memory_id:
        return CommandResult.failure("memory_id is required")
    
    try:
        service = MemoryService()
        service.delete(memory_id)
        
        return CommandResult.success(
            summary=f"Memory deleted: {memory_id}"
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def memory_gc_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle memory:gc command."""
    from agentos.jobs.memory_gc import MemoryGCJob
    
    try:
        job = MemoryGCJob()
        result = job.run()
        
        return CommandResult.success(
            data=result,
            summary="Memory garbage collection completed"
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def memory_health_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle memory:health command."""
    from agentos.core.memory import MemoryService
    
    try:
        service = MemoryService()
        health = service.health()
        
        return CommandResult.success(
            data=health,
            summary="Memory health report"
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def memory_compact_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle memory:compact command - merge similar memories."""
    from agentos.core.memory import MemoryService
    from agentos.core.memory.compactor import MemoryCompactor
    
    scope = kwargs.get("scope")
    project_id = kwargs.get("project_id")
    task_id = kwargs.get("task_id")
    dry_run = kwargs.get("dry_run", False)
    
    try:
        service = MemoryService()
        compactor = MemoryCompactor(service)
        
        result = compactor.compact(
            scope=scope,
            project_id=project_id,
            task_id=task_id,
            dry_run=dry_run
        )
        
        summary = f"Compacted {result['memories_merged']} memories into {result['summaries_created']} summaries"
        if dry_run:
            summary = f"[Dry run] Would compact {result.get('memories_per_cluster', [])} memories"
        
        return CommandResult.success(
            data=result,
            summary=summary
        )
    except Exception as e:
        return CommandResult.failure(str(e))


def memory_scope_handler(context: CommandContext, **kwargs) -> CommandResult:
    """Handle memory:scope command - set/get current memory scope."""
    action = kwargs.get("action", "get")  # get or set
    scope = kwargs.get("scope")
    
    if action == "set":
        if not scope:
            return CommandResult.failure("scope is required for 'set' action")
        
        # Store scope in context
        context.scope = scope
        
        return CommandResult.success(
            data={"scope": scope},
            summary=f"Memory scope set to: {scope}"
        )
    
    elif action == "get":
        current_scope = context.scope or "global"
        
        return CommandResult.success(
            data={"scope": current_scope},
            summary=f"Current memory scope: {current_scope}"
        )
    
    else:
        return CommandResult.failure(f"Unknown action: {action}")


def register_memory_commands(registry: CommandRegistry) -> None:
    """Register all Memory commands to the registry.
    
    Args:
        registry: CommandRegistry instance
    """
    commands = [
        CommandMetadata(
            id="memory:add",
            title="Add memory",
            hint="Add a new memory item",
            category=CommandCategory.MEMORY,
            handler=memory_add_handler,
        ),
        CommandMetadata(
            id="memory:list",
            title="List memories",
            hint="List memory items",
            category=CommandCategory.MEMORY,
            handler=memory_list_handler,
        ),
        CommandMetadata(
            id="memory:search",
            title="Search memories",
            hint="Full-text search in memories",
            category=CommandCategory.MEMORY,
            handler=memory_search_handler,
            needs_arg=True,
        ),
        CommandMetadata(
            id="memory:get",
            title="Get memory",
            hint="Get a specific memory item",
            category=CommandCategory.MEMORY,
            handler=memory_get_handler,
            needs_arg=True,
        ),
        CommandMetadata(
            id="memory:delete",
            title="Delete memory",
            hint="Delete a memory item",
            category=CommandCategory.MEMORY,
            handler=memory_delete_handler,
            needs_arg=True,
            dangerous=True,
        ),
        CommandMetadata(
            id="memory:gc",
            title="Memory GC",
            hint="Run memory garbage collection",
            category=CommandCategory.MEMORY,
            handler=memory_gc_handler,
        ),
        CommandMetadata(
            id="memory:health",
            title="Memory health",
            hint="Show memory system health",
            category=CommandCategory.MEMORY,
            handler=memory_health_handler,
        ),
        CommandMetadata(
            id="memory:compact",
            title="Compact memories",
            hint="Merge similar memories into summaries",
            category=CommandCategory.MEMORY,
            handler=memory_compact_handler,
        ),
        CommandMetadata(
            id="memory:scope",
            title="Memory scope",
            hint="Get or set current memory scope",
            category=CommandCategory.MEMORY,
            handler=memory_scope_handler,
        ),
    ]
    
    registry.register_multiple(commands)
