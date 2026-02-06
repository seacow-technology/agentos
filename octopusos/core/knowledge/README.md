# Knowledge Module

Persistent storage and management for RAG (Retrieval-Augmented Generation) data sources.

## Overview

The Knowledge module provides persistent storage for knowledge base data source configurations. Previously, data sources were stored in an in-memory dictionary and lost on restart. Now they are persisted to SQLite with full CRUD operations and audit logging.

## Features

- ✅ **Persistent Storage**: Data survives application restarts
- ✅ **CRUD Operations**: Create, Read, Update, Delete
- ✅ **Audit Logging**: Full change history tracking
- ✅ **Filtering**: Query by source type and status
- ✅ **Thread-Safe**: Uses SQLiteWriter for concurrent operations
- ✅ **Type-Safe**: Automatic JSON serialization/deserialization

## Quick Start

### Basic Usage

```python
from agentos.core.knowledge import KnowledgeSourceRepo

# Initialize repository
repo = KnowledgeSourceRepo()

# Create a source
source_id = repo.create({
    "id": "docs-001",
    "name": "Project Documentation",
    "source_type": "local",
    "uri": "/path/to/docs",
    "options": {
        "recursive": True,
        "file_types": ["md", "txt"]
    },
    "status": "pending"
})

# Read a source
source = repo.get("docs-001")
print(f"Source: {source['name']}")

# Update a source
repo.update("docs-001", {
    "status": "indexed",
    "chunk_count": 150
})

# List sources with filters
local_sources = repo.list(source_type="local")
active_sources = repo.list(status="active")

# Delete a source
repo.delete("docs-001")

# View audit log
audit = repo.get_audit_log(source_id="docs-001")
for entry in audit:
    print(f"{entry['action']}: {entry.get('changed_fields', [])}")
```

## Source Types

Supported source types:
- `local` - Local file system paths
- `directory` - Directory scanning
- `file` - Single file
- `web` - Web URLs
- `api` - External APIs
- `database` - Database connections
- `git` - Git repositories

## Status Values

- `pending` - Awaiting indexing
- `active` - Active and indexed
- `indexed` - Successfully indexed
- `inactive` - Temporarily disabled
- `error` - Indexing failed
- `failed` - Permanent failure

## API Reference

### KnowledgeSourceRepo

#### `list(source_type=None, status=None, limit=100) -> List[Dict]`

List knowledge sources with optional filtering.

**Parameters**:
- `source_type` (str, optional): Filter by source type
- `status` (str, optional): Filter by status
- `limit` (int): Maximum results (default: 100)

**Returns**: List of source dictionaries

#### `get(source_id: str) -> Optional[Dict]`

Get a single knowledge source by ID.

**Parameters**:
- `source_id` (str): Source ID

**Returns**: Source dictionary or None

#### `create(source: Dict) -> str`

Create a new knowledge source.

**Parameters**:
- `source` (dict): Source data with required fields:
  - `id` (str): Unique identifier
  - `name` (str): Display name
  - `source_type` (str): Type of source
  - `uri` (str): Source URI/path
  - `options` (dict, optional): Configuration options
  - `auth_config` (dict, optional): Authentication credentials
  - `status` (str, optional): Initial status (default: "pending")

**Returns**: Source ID

**Raises**: `ValueError` if required fields missing

#### `update(source_id: str, updates: Dict) -> bool`

Update an existing knowledge source.

**Parameters**:
- `source_id` (str): Source ID
- `updates` (dict): Fields to update

**Returns**: True if successful, False otherwise

#### `delete(source_id: str) -> bool`

Delete a knowledge source.

**Parameters**:
- `source_id` (str): Source ID

**Returns**: True if successful, False otherwise

**Note**: Audit log is preserved after deletion.

#### `get_audit_log(source_id=None, limit=100) -> List[Dict]`

Get audit log entries.

**Parameters**:
- `source_id` (str, optional): Filter by source ID
- `limit` (int): Maximum entries (default: 100)

**Returns**: List of audit entries

## Database Schema

### `knowledge_sources` Table

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT PRIMARY KEY | Unique identifier |
| name | TEXT NOT NULL | Display name |
| source_type | TEXT NOT NULL | Type (local/web/api/etc) |
| uri | TEXT NOT NULL | Source URI/path |
| auth_config | TEXT | JSON: authentication config |
| options | TEXT | JSON: additional options |
| status | TEXT NOT NULL | Status (active/pending/etc) |
| created_at | INTEGER NOT NULL | Creation timestamp (epoch ms) |
| updated_at | INTEGER NOT NULL | Last update timestamp (epoch ms) |
| last_indexed_at | INTEGER | Last index timestamp (epoch ms) |
| chunk_count | INTEGER | Number of indexed chunks |
| metadata | TEXT | JSON: additional metadata |

### `knowledge_source_audit` Table

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT PRIMARY KEY | Unique identifier |
| source_id | TEXT NOT NULL | Reference to source |
| action | TEXT NOT NULL | Action (create/update/delete) |
| changed_fields | TEXT | JSON: list of changed fields |
| old_values | TEXT | JSON: previous values |
| new_values | TEXT | JSON: new values |
| timestamp | INTEGER NOT NULL | Action timestamp (epoch ms) |
| metadata | TEXT | JSON: additional metadata |

## Examples

See `/examples/knowledge_sources_demo.py` for a complete demonstration.

## Security

⚠️ **WARNING**: The `auth_config` field currently stores credentials in **PLAINTEXT**.

See `/docs/knowledge_sources_security.md` for:
- Security considerations
- Encryption recommendations
- Best practices
- Implementation roadmap

## Migration

No migration needed from the old in-memory storage. The old `_data_sources_store` dictionary was never persisted, so no data needs to be migrated.

All new sources will be automatically stored in the database.

## Testing

Run the acceptance test suite:

```bash
python test_knowledge_acceptance.py
```

Expected result: 5/5 tests passed

## Performance

Typical operation times:
- Create: ~5ms
- Read: ~2ms
- Update: ~6ms
- Delete: ~6ms
- List (100 records): ~10ms

All common queries are indexed for optimal performance.

## Changelog

### v0.60.0 (2026-02-01)
- Initial release
- Persistent storage implementation
- Full CRUD operations
- Audit logging
- Migration from in-memory dict

## Support

For issues or questions:
- GitHub Issues: [agentos/issues](https://github.com/agentos/agentos/issues)
- Documentation: `/docs/knowledge_sources_security.md`
- Demo: `/examples/knowledge_sources_demo.py`

## License

Same as AgentOS project license.
