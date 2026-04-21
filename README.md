# PGVector Context Engine

A reusable semantic memory/context engine using PostgreSQL + pgvector. Store and retrieve relevant context across projects using vector embeddings.

## Features

- **Semantic Search** - Query memories by meaning, not keywords
- **Project Isolation** - Namespace-based separation for multi-project use
- **Externalized Config** - All credentials via environment variables or config file
- **Pluggable Embeddings** - Ollama (default) or OpenAI
- **TTL & Importance** - Temporary memories and priority scoring
- **Category Organization** - Filter by source/category
- **Tags** - Array field for flexible labeling
- **Explicit Relationships** - Typed directed links between memories (8 relationship types)
- **Compact Agent Output** - Pipe-delimited, agent-friendly CLI format (`CTX_OUTPUT=compact`)
- **Embedding Cache** - LRU cache avoids re-embedding duplicate content (128-entry, thread-safe)
- **Working Memory** - Session-scoped, fast-access short-term storage (no embeddings)
- **Lean Python API** - Direct attribute access (`ctx.search`, `ctx.save`), lazy connection init
- **Agent Integration** - Built-in base class for AI agents plus `agent-info` subcommand

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Configure

**Option A: Interactive setup**
```bash
./samples/setup_context_engine.sh
```

**Option B: Environment variables**
```bash
export CTX_DB_HOST=localhost
export CTX_DB_PORT=5432
export CTX_DB_NAME=context_engine
export CTX_DB_USER=your_user
export CTX_DB_PASS=your_password
export CTX_NAMESPACE=my-project
export CTX_OLLAMA_URL=http://localhost:11434
```

**Option C: Config file** (`~/.config/context_engine/config.json`)
```json
{
  "db_host": "localhost",
  "db_port": 5432,
  "db_name": "context_engine",
  "db_user": "your_user",
  "ollama_url": "http://localhost:11434",
  "embedding_model": "nomic-embed-text",
  "namespace": "my-project"
}
```

### 3. Initialize Database

```bash
ctx-engine init
```

### 4. Use It

```bash
# Save memories
ctx-engine save "Deployed to k8s cluster" --category infrastructure --importance 8
ctx-engine save "User prefers terse responses" --category preference

# Search
ctx-engine search "What was I working on?"

# Get context for a task (token-budget aware)
ctx-engine get-context "Current session initialization" --max-tokens 3000

# List
ctx-engine list --category infrastructure

# Create relationships between memories
ctx-engine relate <source_doc_id> <target_doc_id> --rel-type depends_on
ctx-engine relate <doc_id_a> <doc_id_b> --rel-type references

# View relationships for a memory
ctx-engine relations <doc_id>

# Remove a relationship
ctx-engine unrelate <source_doc_id> <target_doc_id> --rel-type depends_on

# Compact output for AI agents (pipe-delimited)
CTX_OUTPUT=compact ctx-engine search "k8s deployment"

# Quick single-result search
ctx-engine search-one "deployment status"

# Working memory (session-scoped, no embeddings)
ctx-engine working set "current_task" "Refactor auth module"
ctx-engine working get
ctx-engine working tasks
ctx-engine working add-task "Fix login bug"
```

### Relationship Types

Valid relationship types (`VALID_REL_TYPES`):

| Type | Meaning |
|------|---------|
| `related_to` | General association |
| `depends_on` | Source requires target |
| `supersedes` | Source replaces target |
| `about` | Source is about target |
| `blocks` | Source blocks target |
| `references` | Source references target |
| `contains` | Source contains target |
| `derived_from` | Source derived from target |

## Python API

```python
from context_engine import ContextEngine

# Initialize (reads from env/config, lazy connection)
ctx = ContextEngine()

# Save a memory (returns doc_id)
doc_id = ctx.save(
    content="Deployed WebMonsters to k3s",
    category="infrastructure",
    importance=8.0,
    ttl_days=30
)

# Get relevant context
context = ctx.get_context(
    query="What was I working on?",
    max_memories=10,
    max_tokens=4000
)

# Search (lean API: ctx.search works directly)
results = ctx.search("k8s deployment", limit=5, min_similarity=0.6)
for r in results:
    print(f"[{r['similarity']:.2f}] {r['content']}")

# Quick single-result search
content = ctx.search_one("deployment status")

# Create explicit relationships
ctx.relate(source_doc_id, target_doc_id, rel_type="depends_on")
ctx.relate(source_doc_id, target_doc_id, rel_type="references")

# View relationships for a memory
rels = ctx.relations(doc_id, direction="both")
for r in rels:
    print(f"[{r['direction']}] {r['rel_type']}: {r['content']}")

# Remove a relationship
ctx.unrelate(source_doc_id, target_doc_id, rel_type="depends_on")
# Or remove all relationships between two memories
ctx.unrelate(source_doc_id, target_doc_id)

# Working memory (session-scoped, no embeddings)
from context_engine import WorkingMemory
wm = WorkingMemory()
wm.set_session_context("current_task", "Refactor auth")
task_id = wm.save_task(description="Fix login bug", status="ready")

# Embedding cache stats
stats = ctx.embedding_cache_stats()
print(f"Cache: {stats['hits']} hits, {stats['misses']} misses")

# Cleanup
ctx.cleanup_expired()
ctx.close()
```

## Agent Integration

For AI agents, use the built-in `ContextAgent` base class:

```python
from context_engine.agent import ContextAgent

class MyAgent(ContextAgent):
    def process(self, message):
        # Context automatically retrieved
        context = self.get_relevant_context(message)
        
        # Your LLM call here
        response = call_your_llm(context, message)
        
        # Auto-saved to memory
        self.remember_interaction(message, response)
        return response

# Run immediately (zero config if context engine is set up)
agent = MyAgent("MyBot")
agent.run()
```

See [AGENT_SETUP.md](AGENT_SETUP.md) for quick agent setup (when context engine is already configured).
See [AGENT_INTEGRATION.md](AGENT_INTEGRATION.md) for detailed integration patterns.

## CLI Command Reference

| Command | Description |
|---------|-------------|
| `save` | Save a memory |
| `search` | Semantic search for memories |
| `search-one` | Return single best match content |
| `get-context` | Get token-budgeted context |
| `list` | List memories |
| `delete` | Delete a memory |
| `cleanup` | Delete expired memories |
| `init` | Initialize database schema |
| `agent-info` | Show info for AI agents (compact/json/text) |
| `stats` | Show memory statistics |
| `peek` | Show full content of a memory |
| `count` | Print memory count |
| `relate` | Create a relationship between two memories |
| `unrelate` | Remove a relationship between memories |
| `relations` | Show relationships for a memory |
| `working` | Working memory commands (set/get/tasks/add-task) |

Set `CTX_OUTPUT=compact` for pipe-delimited output suitable for AI agents.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CTX_DB_HOST` | `localhost` | PostgreSQL host |
| `CTX_DB_PORT` | `5432` | PostgreSQL port |
| `CTX_DB_NAME` | `context_engine` | Database name |
| `CTX_DB_USER` | (none) | Database user |
| `CTX_DB_PASS` | (none) | Database password |
| `CTX_DB_SSLMODE` | `disable` | SSL mode |
| `CTX_OLLAMA_URL` | `http://localhost:11434` | Ollama URL |
| `CTX_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `CTX_NAMESPACE` | `default` | Project namespace |

## Namespace Isolation

Namespaces keep memories separate per project:

```bash
# Project A
CTX_NAMESPACE=project-a ctx-engine save "Working on auth"

# Project B
CTX_NAMESPACE=project-b ctx-engine save "Refactoring API"

# Search only returns memories from current namespace
CTX_NAMESPACE=project-a ctx-engine search "auth"  # Returns project-a memory
CTX_NAMESPACE=project-b ctx-engine search "auth"  # Returns project-b memory
```

## Database Setup

### PostgreSQL + pgvector

```bash
# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib
sudo apt install postgresql-14-pgvector

# Enable extension (as superuser)
psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Create Database

```sql
CREATE DATABASE context_engine;
CREATE USER ctx_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE context_engine TO ctx_user;
\c context_engine
-- Run migrations/001_initial.sql
```

## Architecture

```
Query Text
    ↓
[Embedding Cache] → check LRU cache (128 entries, thread-safe)
    ↓ (cache miss)
[Embedding] → 768-dim vector (Ollama: nomic-embed-text / OpenAI)
    ↓
[pgvector Search] → Top-K similar memories (by namespace)
    ↓
[Relationship Graph] → Explicit typed edges (relationships table)
    ↓
[Token Budget Filter] → Context within limit
    ↓
LLM Context
```

### Compact Output Format

For AI agent consumption, set `CTX_OUTPUT=compact` for pipe-delimited output:

```bash
CTX_OUTPUT=compact ctx-engine search "k8s"
# Output: doc_id|similarity|content
# abc123|0.89|Deployed to k8s cluster

CTX_OUTPUT=compact ctx-engine list
# Output: doc_id|category|importance|content

CTX_OUTPUT=compact ctx-engine agent-info
# Output: version|namespace|commands|rel_types
```

Embedding cache stats and agent-info are also available programmatically:

```python
# Cache stats
stats = ctx.embedding_cache_stats()
# {"hits": 42, "misses": 8, "size": 15, "hit_rate": 0.84}

# Clear cache
ctx.clear_embedding_cache()
```

## File Structure

```
src/context_engine/
├── __init__.py           # Public API exports
├── config.py             # Configuration (env + config file)
├── providers.py          # Embedding providers (Ollama, OpenAI)
├── schema.py             # Database schema management
├── core.py               # Main ContextEngine class
├── working_memory.py     # WorkingMemory - session-scoped short-term storage
├── memory_manager.py     # MemoryManager - two-tier memory coordinator
├── cli.py                # CLI tool
└── agent.py              # ContextAgent - base class for AI agents
```

## Examples

See `examples/claude_integration.py` for Claude Code integration patterns:

- Per-project context initialization
- Saving architectural decisions
- User preference memory
- Session-based conversation storage

## Two-Tier Memory System

For agents that need both fast session state and semantic long-term memory:

```python
from context_engine import MemoryManager

# Initialize for your model type
manager = MemoryManager(model_type="local-8k")

# Working memory - fast, session-scoped
manager.working.set_session_context("user_name", "Alice")
task_id = manager.working.save_task(
    description="Refactor auth module",
    status="ready"
)

# Reference memory - semantic, long-term
manager.reference.save(
    content="User prefers Python",
    category="preference"
)

# Get assembled context with token budgeting
context = manager.get_context(
    "What should I refactor?",
    max_tokens=4000
)

# Working + reference combined with intelligent ranking
```

See [docs/two-tier-memory.md](docs/two-tier-memory.md) for detailed documentation.
