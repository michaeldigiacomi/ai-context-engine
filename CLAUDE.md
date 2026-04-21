# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PGVector Context Engine is a Python library providing semantic memory/storage using PostgreSQL + pgvector. It enables AI agents to store and retrieve context via vector embeddings with namespace isolation for multi-project use.

## Development Commands

### Installation
```bash
pip install -e .           # Basic install
pip install -e ".[dev]"    # With test dependencies
pip install -e ".[openai]" # With OpenAI embedding support
```

### Testing
```bash
python run_tests.py              # Run all tests
python run_tests.py --unit       # Unit tests only (no DB required)
python run_tests.py --integration  # Integration tests (requires PostgreSQL)
python run_tests.py --coverage   # With coverage report

# Or with pytest directly:
pytest tests/test_unit.py tests/test_cli.py -v
pytest tests/test_integration.py -v -m integration
```

### CLI Usage
```bash
ctx-engine init                    # Initialize database schema
ctx-engine save "content"          # Save a memory
ctx-engine search "query"          # Semantic search
ctx-engine search-one "query"     # Single best match
ctx-engine get-context "query"     # Get token-budgeted context
ctx-engine list                    # List memories
ctx-engine delete <doc_id>        # Delete a memory
ctx-engine cleanup                 # Delete expired memories
ctx-engine agent-info              # Show info for AI agents
ctx-engine stats                   # Memory statistics
ctx-engine peek <doc_id>          # Full content of a memory
ctx-engine count                   # Memory count
ctx-engine relate <src> <tgt> --rel-type depends_on  # Create relationship
ctx-engine unrelate <src> <tgt> --rel-type depends_on # Remove relationship
ctx-engine relations <doc_id>      # Show relationships
ctx-engine working set "key" "val" # Working memory set
ctx-engine working get             # Working memory get
```

## Architecture

### Core Components

```
src/context_engine/
├── __init__.py           # Public API exports
├── core.py               # ContextEngine - main class for memory operations
├── config.py             # ContextEngineConfig - env/file-based configuration
├── providers.py          # Embedding providers (Ollama, OpenAI)
├── schema.py             # SchemaManager - database schema/migrations
├── working_memory.py     # WorkingMemory - session-scoped short-term storage
├── memory_manager.py     # MemoryManager - two-tier memory coordinator
├── cli.py                # CLI tool entry point
└── agent.py              # ContextAgent - base class for AI agents
```

### Data Flow

```
Text Input → Embedding Cache (LRU 128) → Embedding (Ollama/OpenAI) → 768-dim vector → pgvector similarity search → Relationship graph → Token-budget filter → Formatted context
```

### Key Classes

**ContextEngine** (core.py)
- Main entry point for all memory operations
- Lazy database connection initialization
- Embedding cache (LRU 128 entries, thread-safe, on by default)
- Methods: `save()`, `get_context()`, `search()`, `search_one()`, `recall()`, `list()`, `delete()`, `save_conversation()`, `peek()`, `count()`, `stats()`
- Relationship methods: `relate()`, `unrelate()`, `relations()`
- Cache methods: `embedding_cache_stats()`, `clear_embedding_cache()`
- `VALID_REL_TYPES`: {"related_to", "depends_on", "supersedes", "about", "blocks", "references", "contains", "derived_from"}
- Uses `doc_id` (SHA256 hash) for idempotency

**ContextEngineConfig** (config.py)
- Dataclass with env var fallbacks (CTX_* prefix)
- Loads from `~/.config/context_engine/config.json`
- Properties: `conn_string` builds PostgreSQL connection URL

**ContextAgent** (agent.py)
- Abstract base class for AI agents
- Implements `process()` method
- Built-in methods: `remember()`, `recall()`, `remember_interaction()`, `get_relevant_context()`

### Configuration Hierarchy

1. Constructor arguments (highest priority)
2. Environment variables (CTX_DB_HOST, CTX_DB_USER, etc.)
3. Config file at `~/.config/context_engine/config.json`
4. Defaults (localhost:5432, namespace="default")

### Database Schema

**memories table** (migrations/001_initial.sql):
- `doc_id` - SHA256 hash of content (unique constraint)
- `embedding` - pgvector vector(768)
- `namespace` - Project isolation key
- `category`, `importance`, `ttl_days`, `session_key` - Organization/weighting
- `tags` - Array field for flexible labeling
- `metadata` - JSONB for extensible key-value data
- Access tracking: `access_count`, `last_accessed`

**relationships table** (migrations):
- `source_id` - FK to memories (source of relationship)
- `target_id` - FK to memories (target of relationship)
- `rel_type` - Relationship type (must be in VALID_REL_TYPES)
- `created_at` - Timestamp
- Unique constraint: (source_id, target_id, rel_type)

**working schema** (session-scoped tables):
- `working.session_context` - Key-value session state with TTL
- `working.tasks` - Task tracking with status/plans
- `working.recent_decisions` - Auto-expiring decisions

### Testing Strategy

- **Unit tests** (test_unit.py): Mock database and embedding provider, test business logic
- **CLI tests** (test_cli.py): Mock stdout/stderr, test argument parsing
- **Integration tests** (test_integration.py): Require PostgreSQL with pgvector extension
- Fixtures in conftest.py: `mock_embedding`, `test_config`, `postgres_available`, `ollama_available`

## Important Patterns

### Idempotent Saves
Saves use `ON CONFLICT (doc_id) DO UPDATE` where `doc_id` is derived from content hash. Saving identical content updates the existing record.

### Lazy Initialization
Database connection and schema initialization are deferred until first operation. Use `auto_init=False` to disable automatic schema creation.

### Namespace Isolation
Memories are scoped to namespaces (default: "default"). Different namespaces cannot see each other's data. Use this for multi-project or multi-agent isolation.

### Token Budget Context
`get_context()` respects `max_tokens` by approximating 4 chars/token and truncating results while prioritizing by similarity score (>0.5 threshold).

### Context Manager Support
Both `ContextEngine` and `ContextAgent` support `with` statements for automatic cleanup.

### Embedding Cache
`ContextEngine` caches embeddings in a thread-safe LRU (128 entries). On by default (`cache_embeddings=True`). Access stats via `embedding_cache_stats()`, clear via `clear_embedding_cache()`. Disable with `ContextEngine(cache_embeddings=False)`.

### Explicit Relationships
Use `relate(source_doc_id, target_doc_id, rel_type)` to create typed directed edges between memories. `rel_type` must be one of `VALID_REL_TYPES`. Relationships are stored in a `relationships` table with a unique constraint on (source_id, target_id, rel_type). Use `relations(doc_id, direction)` to query - direction can be `outgoing`, `incoming`, or `both`.

```python
# Create relationship
ctx.relate(doc_a, doc_b, rel_type="depends_on")

# Query relationships
rels = ctx.relations(doc_a, direction="outgoing", rel_type="depends_on")

# Remove relationship
ctx.unrelate(doc_a, doc_b, rel_type="depends_on")
ctx.unrelate(doc_a, doc_b)  # Remove all types between A and B
```

### Compact Output Format
Set `CTX_OUTPUT=compact` for pipe-delimited output optimized for AI agent consumption. Also supports `CTX_OUTPUT=json`. The `agent-info` subcommand provides self-describing capability discovery.

### Working Memory
`WorkingMemory` provides fast, session-scoped storage without embeddings. Tables: `session_context` (key-value with TTL), `tasks` (task tracking), `recent_decisions` (auto-expiring decisions). Available as `WorkingMemory()` class or via `ctx-engine working` CLI commands.

## Common Tasks

### Run a single test
```bash
pytest tests/test_unit.py::test_save_basic -v
```

### Test with real database
Set environment variables:
```bash
export CTX_DB_HOST=localhost
export CTX_DB_USER=your_user
export CTX_DB_PASS=your_password
pytest tests/test_integration.py -v
```

### Check database connection
```python
from context_engine.schema import SchemaManager
from context_engine.config import ContextEngineConfig

config = ContextEngineConfig()
schema = SchemaManager(config)
success, error = schema.verify_connection()
```
