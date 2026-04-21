# Agent Setup (Context Engine Already Configured)

If the context engine is already set up (PostgreSQL + pgvector running, database created), agents can start using it immediately with zero additional configuration.

## For Agent Developers

### Option 1: Zero-Config (Reads from existing config)

```python
from context_engine import ContextEngine

# Automatically loads config from ~/.config/context_engine/config.json
# or from environment variables
memory = ContextEngine()

# Start using immediately
memory.save("User prefers dark mode", category="preference")
context = memory.get_context("What are user preferences?")
```

### Option 2: Explicit Namespace (Recommended for multi-agent)

```python
from context_engine import ContextEngine
from context_engine.config import ContextEngineConfig

# Use existing DB config but isolate this agent's memories
config = ContextEngineConfig(namespace="customer-support-bot")
memory = ContextEngine(config=config)
```

### Option 3: Full Agent Class

```python
from context_engine.agent import ContextAgent

class MyAgent(ContextAgent):
    def __init__(self):
        # Just pass namespace - DB config loads automatically
        super().__init__(name="SupportBot", namespace="support-team")
    
    def process(self, message):
        # Context automatically retrieved
        context = self.get_relevant_context(message)
        
        # Your LLM call here
        response = call_llm(context, message)
        
        # Auto-saved to memory
        self.remember_interaction(message, response)
        return response

# Run immediately
agent = MyAgent()
agent.run()
```

## What the Agent Gets For Free

When context engine is pre-configured, agents automatically get:

1. **Database Connection** - No setup needed
2. **Embeddings** - Via configured Ollama/OpenAI
3. **Embedding Cache** - LRU cache avoids re-embedding duplicate content (128 entries, thread-safe)
4. **Namespace Isolation** - Each agent can have its own memory space
5. **Session Tracking** - Conversations automatically tracked
6. **TTL Support** - Temporary memories auto-expire
7. **Relationships** - Typed directed links between memories (8 types)
8. **Working Memory** - Fast session-scoped storage without embeddings
9. **Compact Output** - Pipe-delimited CLI output for AI agents (`CTX_OUTPUT=compact`)
10. **Agent Info** - Self-describing output for agent discovery (`ctx-engine agent-info`)

## Configuration Precedence

The agent checks for config in this order:

1. **Explicit config passed** to constructor
2. **Environment variables** (CTX_DB_HOST, etc.)
3. **Config file** at `~/.config/context_engine/config.json`
4. **Defaults** (localhost:5432)

## Quick Test

Verify the agent can connect:

```python
from context_engine import ContextEngine

memory = ContextEngine()

# Test save/retrieve
doc_id = memory.save("Test connection", category="test")
results = memory.search("test connection")

print(f"✓ Connected! Found {len(results)} results")

# Test relationships
doc_b = memory.save("Related test", category="test")
memory.relate(doc_id, doc_b, rel_type="related_to")
rels = memory.relations(doc_id)
print(f"✓ Relationships work! Found {len(rels)} relations")

memory.close()
```

## CLI Commands

When the context engine is configured, agents can use any of these CLI commands:

```bash
# Core operations
ctx-engine save "content" --category cat --importance 8
ctx-engine search "query" --limit 5
ctx-engine search-one "query"              # Single best match
ctx-engine get-context "query" --max-tokens 3000
ctx-engine list --category preference
ctx-engine delete <doc_id>
ctx-engine cleanup
ctx-engine init

# Agent-optimized commands
ctx-engine agent-info                      # Discover capabilities
ctx-engine stats                           # Memory statistics
ctx-engine peek <doc_id>                   # Full content of a memory
ctx-engine count                           # Memory count

# Relationships
ctx-engine relate <source> <target> --rel-type depends_on
ctx-engine relations <doc_id>               # Show relationships
ctx-engine unrelate <source> <target> --rel-type depends_on

# Working memory (session-scoped)
ctx-engine working set "key" "value"
ctx-engine working get
ctx-engine working tasks
ctx-engine working add-task "description" --status ready

# Compact output for AI consumption
CTX_OUTPUT=compact ctx-engine search "query"
CTX_OUTPUT=compact ctx-engine agent-info
CTX_OUTPUT=json ctx-engine stats
```

### VALID_REL_TYPES

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

## Common Patterns

### Multi-Agent Shared Database

```python
# Agent A - Customer Support
support_agent = ContextEngine(
    config=ContextEngineConfig(namespace="support")
)

# Agent B - Code Review  
code_agent = ContextEngine(
    config=ContextEngineConfig(namespace="code-review")
)

# Both use same DB, but memories are isolated
```

### Session-Based Agents

```python
import uuid

class SessionAgent:
    def __init__(self, session_id=None):
        self.memory = ContextEngine()
        self.session_id = session_id or str(uuid.uuid4())[:8]
    
    def chat(self, user_msg):
        # Load session context
        history = self.memory.get_session(self.session_id)
        
        # Get relevant context from all sessions
        relevant = self.memory.get_context(user_msg)
        
        # Process and save
        response = self.process(user_msg, history, relevant)
        self.memory.save_conversation(
            session_key=self.session_id,
            user_message=user_msg,
            assistant_response=response
        )
        return response
```

### Agent with Relationships

```python
from context_engine import ContextEngine

class RelatingAgent:
    def __init__(self):
        self.memory = ContextEngine()
    
    def track_dependency(self, feature, blocker):
        """Save both and link with depends_on."""
        feat_id = self.memory.save(content=feature, category="feature")
        block_id = self.memory.save(content=blocker, category="blocker")
        self.memory.relate(feat_id, block_id, rel_type="depends_on")
    
    def find_blockers(self, feature_doc_id):
        """Find what a feature depends on."""
        return self.memory.relations(
            feature_doc_id, direction="outgoing", rel_type="depends_on"
        )
    
    def supersede(self, old_doc_id, new_doc_id):
        """Mark new memory as replacing old one."""
        self.memory.relate(new_doc_id, old_doc_id, rel_type="supersedes")
```

### Agent with Working Memory

```python
from context_engine import ContextEngine, WorkingMemory

class TaskAgent:
    """Agent that tracks current tasks in working memory."""
    
    def __init__(self):
        self.memory = ContextEngine()       # Long-term semantic memory
        self.working = WorkingMemory()      # Short-term session memory
    
    def start_session(self):
        """Initialize working memory for a session."""
        self.working.set_session_context("agent_status", "active")
        self.working.set_session_context("step", "0")
    
    def work_on_task(self, description):
        """Create and track a task."""
        task_id = self.working.save_task(
            description=description, status="in_progress"
        )
        # Also persist to long-term memory
        self.memory.save(content=description, category="task")
        return task_id
    
    def complete_task(self, task_id, result):
        """Finish a task."""
        self.working.update_task(
            task_id, status="completed", result=result
        )
    
    def get_session_state(self):
        """Get all current working context."""
        return self.working.get_session_context()
```

## Environment Variables

If the context engine was set up with a script, these might already be set:

```bash
# Check what's configured
env | grep CTX_

# Typical setup from setup_context_engine.sh
CTX_DB_HOST=localhost
CTX_DB_PORT=5432
CTX_DB_NAME=context_engine
CTX_DB_USER=youruser
CTX_OLLAMA_URL=http://localhost:11434
CTX_NAMESPACE=default
```

## Migration from Markdown/Memory Files

If your agent currently uses markdown files or in-memory storage:

### Before (Markdown)
```python
# Load from file
with open("agent_memory.md") as f:
    context = f.read()

# Save to file  
with open("agent_memory.md", "a") as f:
    f.write(f"\nUser: {msg}\nAgent: {response}")
```

### After (Context Engine)
```python
from context_engine import ContextEngine

memory = ContextEngine()

# Semantic retrieval (not just text search)
context = memory.get_context(user_query, max_tokens=2000)

# Auto-embedded and searchable
memory.save_conversation(
    session_key="session-123",
    user_message=msg,
    assistant_response=response
)
```

## Troubleshooting

### "Database connection failed"

Check if context engine is accessible:

```python
from context_engine.schema import SchemaManager
from context_engine.config import ContextEngineConfig

config = ContextEngineConfig()
schema = SchemaManager(config)

success, error = schema.verify_connection()
if not success:
    print(f"Connection failed: {error}")
    print(f"Tried to connect to: {config.conn_string}")
```

### "No results found"

The database might be empty or using different namespace:

```python
# Check what's in the database
all_memories = memory.list(limit=100)
print(f"Found {len(all_memories)} memories")
print(f"Current namespace: {memory.namespace}")

# Check by category
for mem in all_memories:
    print(f"  [{mem['category']}] {mem['content'][:50]}...")
```

### "Embedding failed"

Check Ollama connection:

```python
import requests

ollama_url = "http://localhost:11434"  # From config
try:
    response = requests.get(f"{ollama_url}/api/tags", timeout=5)
    if response.status_code == 200:
        print("✓ Ollama is running")
    else:
        print(f"✗ Ollama returned {response.status_code}")
except Exception as e:
    print(f"✗ Cannot reach Ollama: {e}")
```

## Summary

For agents, using an existing context engine is **zero-setup**:

1. Import `ContextEngine` or `ContextAgent`
2. Call `ContextEngine()` - config loads automatically
3. Start saving/retrieving memories
4. Use `relate()/unrelate()/relations()` for explicit relationships
5. Use `WorkingMemory` for session-scoped short-term storage
6. Set `CTX_OUTPUT=compact` for agent-friendly CLI output
7. Run `ctx-engine agent-info` to discover available capabilities

The context engine handles all the complexity (embeddings, database, caching, etc.). Agents just use the simple API.
