# Agent Integration Guide

Integrate pgvector-context-engine into your AI agents for persistent, semantic memory across sessions.

## Quick Start (5 minutes)

### 1. Install

```bash
pip install git+https://github.com/michaeldigiacomi/ai-context-engine.git
```

### 2. Configure

Create `~/.config/context_engine/config.json`:

```json
{
  "db_host": "your-postgres-host",
  "db_port": 5432,
  "db_name": "context_engine",
  "db_user": "your-user",
  "ollama_url": "http://localhost:11434",
  "embedding_model": "nomic-embed-text",
  "namespace": "my-agent"
}
```

Or use environment variables:

```bash
export CTX_DB_HOST=localhost
export CTX_DB_PORT=5432
export CTX_DB_NAME=context_engine
export CTX_DB_USER=myuser
export CTX_DB_PASS=mypassword
export CTX_NAMESPACE=my-agent
```

### 3. Use in Your Agent

```python
from context_engine import ContextEngine

class MyAgent:
    def __init__(self):
        # Initialize context engine
        self.memory = ContextEngine()
        
        # Load relevant context at startup
        self.context = self.memory.get_context(
            "Agent initialization",
            max_tokens=2000
        )
    
    def process_message(self, user_message):
        # Get relevant memories for this query
        relevant = self.memory.get_context(
            user_message,
            max_tokens=1500
        )
        
        # Combine with system context
        full_context = f"{self.context}\n\n{relevant}"
        
        # Your LLM call here
        response = self.call_llm(full_context, user_message)
        
        # Save this interaction
        self.memory.save_conversation(
            session_key=self.session_id,
            user_message=user_message,
            assistant_response=response
        )
        
        return response
    
    def remember(self, fact, category="general", importance=5.0):
        """Explicitly save a fact to memory."""
        self.memory.save(
            content=fact,
            category=category,
            importance=importance
        )
```

## API Reference

### Core Methods

| Method | Description |
|--------|-------------|
| `save(content, category, importance, ttl_days, tags)` | Save a memory, returns `doc_id` |
| `search(query, limit, min_similarity, category, fields)` | Semantic search |
| `search_one(query, category)` | Return single best match content |
| `get_context(query, max_tokens, max_memories, category)` | Get token-budgeted context |
| `list(limit, category)` | List memories |
| `delete(doc_id)` | Delete a memory |
| `cleanup_expired()` | Delete expired memories |
| `peek(doc_id)` | Show full content of a memory |
| `count(category)` | Count memories |
| `stats()` | Show memory statistics |
| `recall(query, limit, min_similarity, category)` | Quick recall with lean fields |

### Relationship Methods

| Method | Description |
|--------|-------------|
| `relate(source_doc_id, target_doc_id, rel_type)` | Create a typed relationship between two memories |
| `unrelate(source_doc_id, target_doc_id, rel_type=None)` | Remove relationship(s). If `rel_type` is None, removes all types |
| `relations(doc_id, direction="both", rel_type=None)` | Get relationships for a memory. Direction: `outgoing`, `incoming`, or `both` |

### VALID_REL_TYPES

The following relationship types are valid (defined as `ContextEngine.VALID_REL_TYPES`):

```python
VALID_REL_TYPES = {
    "related_to",    # General association
    "depends_on",    # Source requires target
    "supersedes",    # Source replaces target
    "about",         # Source is about target
    "blocks",        # Source blocks target
    "references",    # Source references target
    "contains",      # Source contains target
    "derived_from",  # Source derived from target
}
```

### Embedding Cache

By default, `ContextEngine` caches embedding results in an LRU cache (128 entries, thread-safe).
This avoids re-embedding identical content across save and search operations.

```python
ctx = ContextEngine(cache_embeddings=True)  # default

# Check cache performance
stats = ctx.embedding_cache_stats()
# {"hits": 42, "misses": 8, "size": 15, "hit_rate": 0.84}

# Clear if needed
ctx.clear_embedding_cache()

# Disable caching
ctx = ContextEngine(cache_embeddings=False)
```

### Compact Output Format

For AI agents consuming CLI output, set `CTX_OUTPUT=compact` for pipe-delimited output:

```bash
CTX_OUTPUT=compact ctx-engine search "k8s"
# doc_id|similarity|content

CTX_OUTPUT=compact ctx-engine list
# doc_id|category|importance|content

CTX_OUTPUT=compact ctx-engine agent-info
# version|namespace|commands|rel_types

CTX_OUTPUT=compact ctx-engine relate <src> <tgt> --rel-type depends_on
# relate|created|<source_doc_id>|<target_doc_id>|depends_on

CTX_OUTPUT=compact ctx-engine relations <doc_id>
# doc_id|rel_type|direction|content
```

JSON output is also available: `CTX_OUTPUT=json`

### Agent-Info Command

The `agent-info` subcommand provides a self-describing output for AI agents to discover available capabilities:

```bash
ctx-engine agent-info                # Human-readable text
ctx-engine agent-info --python       # Include Python code example
CTX_OUTPUT=compact ctx-engine agent-info  # Pipe-delimited
CTX_OUTPUT=json ctx-engine agent-info     # JSON format
```

## Integration Patterns

### Pattern 1: Simple Context Injection

```python
from context_engine import ContextEngine

class SimpleAgent:
    def __init__(self, agent_name="agent"):
        self.memory = ContextEngine()
        self.agent_name = agent_name
        
    def chat(self, message):
        # Get relevant context
        context = self.memory.get_context(
            message,
            max_tokens=3000
        )
        
        # Build prompt with context
        prompt = f"""Relevant context from previous interactions:
{context}

User: {message}
Assistant:"""
        
        # Get response from your LLM
        response = call_your_llm(prompt)
        
        # Save to memory
        self.memory.save_conversation(
            session_key=f"{self.agent_name}-session",
            user_message=message,
            assistant_response=response
        )
        
        return response
```

### Pattern 2: Persistent Agent with Categories

```python
from context_engine import ContextEngine

class PersistentAgent:
    """Agent with categorized memory for different types of information."""
    
    def __init__(self, agent_id="default"):
        self.memory = ContextEngine()
        self.agent_id = agent_id
        self.session_key = f"{agent_id}-{uuid.uuid4().hex[:8]}"
        
    def learn_user_preference(self, preference):
        """Save user preferences with high importance."""
        self.memory.save(
            content=preference,
            category="preference",
            importance=9.0  # User preferences are important
        )
    
    def learn_fact(self, fact):
        """Save general facts."""
        self.memory.save(
            content=fact,
            category="knowledge",
            importance=5.0
        )
    
    def get_context_for_task(self, task_description):
        """Get relevant context for a specific task."""
        # Get preferences (always include these)
        preferences = self.memory.get_context(
            "user preferences",
            category="preference",
            max_tokens=500
        )
        
        # Get relevant knowledge
        knowledge = self.memory.get_context(
            task_description,
            category="knowledge",
            max_tokens=2000
        )
        
        # Get recent conversation
        conversation = self.memory.get_context(
            task_description,
            category="conversation",
            max_tokens=1000
        )
        
        return f"""User Preferences:
{preferences}

Relevant Knowledge:
{knowledge}

Recent Conversation:
{conversation}"""
```

### Pattern 3: Multi-Agent Setup

```python
from context_engine import ContextEngine

class MultiAgentSystem:
    """Multiple agents sharing a database but isolated by namespace."""
    
    def __init__(self):
        self.agents = {}
    
    def create_agent(self, agent_name, role):
        """Create a new agent with isolated memory."""
        config = ContextEngineConfig(
            namespace=f"agent-{agent_name}",
            # ... other config
        )
        
        agent = ContextEngine(config=config)
        
        # Save agent's role
        agent.save(
            content=f"I am {agent_name}, my role is: {role}",
            category="system",
            importance=10.0
        )
        
        self.agents[agent_name] = agent
        return agent
    
    def get_agent(self, agent_name):
        return self.agents.get(agent_name)
```

### Pattern 4: Agent with Automatic Context Retrieval

```python
from context_engine import ContextEngine
import functools

class SmartAgent:
    """Agent that automatically injects relevant context."""
    
    def __init__(self):
        self.memory = ContextEngine()
        self._init_system_prompt()
    
    def _init_system_prompt(self):
        """Load persistent system context."""
        self.system_context = self.memory.get_context(
            "system instructions and preferences",
            max_tokens=2000
        )
    
    def with_context(self, category=None):
        """Decorator to automatically add context to methods."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Get query from first argument
                query = args[1] if len(args) > 1 else kwargs.get('message', '')
                
                # Retrieve relevant context
                context = self.memory.get_context(
                    query,
                    category=category,
                    max_tokens=2000
                )
                
                # Add context to kwargs
                kwargs['context'] = context
                
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    @with_context(category="knowledge")
    def answer_question(self, question, context=None):
        """Answer a question with relevant context."""
        prompt = f"""Context: {context}

Question: {question}
Answer:"""
        return call_llm(prompt)
```

### Pattern 5: Agent with Relationship Graph

```python
from context_engine import ContextEngine

class GraphAgent:
    """Agent that uses explicit relationships between memories."""
    
    def __init__(self):
        self.memory = ContextEngine()
    
    def save_with_dependency(self, content, depends_on_content, **kwargs):
        """Save a memory and link it to a dependency."""
        doc_id = self.memory.save(content=content, **kwargs)
        dep_results = self.memory.search(depends_on_content, limit=1)
        if dep_results:
            dep_id = dep_results[0]['doc_id']
            self.memory.relate(doc_id, dep_id, rel_type="depends_on")
        return doc_id
    
    def get_related_context(self, query, max_tokens=3000):
        """Get context plus related memories via relationships."""
        results = self.memory.search(query, limit=5)
        context_parts = []
        
        for r in results:
            context_parts.append(r['content'])
            # Get relationships for each result
            rels = self.memory.relations(r['doc_id'], direction="outgoing")
            for rel in rels:
                context_parts.append(
                    f"  [{rel['rel_type']}] {rel['content']}"
                )
        
        return "\n".join(context_parts)
    
    def link_as_reference(self, source_id, target_id):
        """Mark source as referencing target."""
        return self.memory.relate(source_id, target_id, rel_type="references")
    
    def mark_superseded(self, old_id, new_id):
        """Mark new memory as superseding the old one."""
        return self.memory.relate(new_id, old_id, rel_type="supersedes")
```

### Pattern 6: Agent with Working Memory

```python
from context_engine import ContextEngine, WorkingMemory

class AgentWithWorkingMemory:
    """Agent using both working memory (fast, session-scoped) and reference memory."""
    
    def __init__(self):
        self.memory = ContextEngine()
        self.working = WorkingMemory()
    
    def start_task(self, task_description):
        """Start a new task with working memory tracking."""
        task_id = self.working.save_task(
            description=task_description,
            status="in_progress"
        )
        self.working.set_session_context("current_task", task_id)
        return task_id
    
    def decide(self, decision_text, context=None):
        """Record a decision in working memory."""
        return self.working.save_decision(
            content=decision_text,
            context=context
        )
    
    def finish_task(self, task_id, result):
        """Complete a task and optionally persist key facts."""
        self.working.update_task(task_id, status="completed", result=result)
        # Persist important facts to long-term memory
        self.memory.save(content=result, category="task_result")
```

## Framework-Specific Integrations

### LangChain Integration

```python
from langchain.agents import AgentExecutor
from context_engine import ContextEngine

class ContextEngineTool:
    """LangChain tool for context engine."""
    
    def __init__(self):
        self.memory = ContextEngine()
    
    def search_memory(self, query: str) -> str:
        """Search agent's memory for relevant information."""
        results = self.memory.search(query, limit=5)
        return "\n".join([r['content'] for r in results])
    
    def save_memory(self, content: str, category: str = "general") -> str:
        """Save information to agent's memory."""
        doc_id = self.memory.save(content=content, category=category)
        return f"Saved to memory: {doc_id}"
    
    def relate_memories(self, source_id: str, target_id: str, rel_type: str = "related_to") -> str:
        """Create a relationship between two memories."""
        self.memory.relate(source_id, target_id, rel_type=rel_type)
        return f"Created {rel_type} relationship: {source_id} -> {target_id}"
    
    def get_relations(self, doc_id: str) -> str:
        """Get relationships for a memory."""
        rels = self.memory.relations(doc_id)
        lines = [f"{r['direction']} {r['rel_type']}: {r['content']}" for r in rels]
        return "\n".join(lines) if lines else "No relationships found"
```

### CrewAI Integration

```python
from crewai import Agent
from context_engine import ContextEngine

class MemoryEnabledAgent(Agent):
    """CrewAI agent with pgvector memory."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.memory = ContextEngine()
        
        # Load context into agent's memory
        context = self.memory.get_context(
            self.role,
            max_tokens=2000
        )
        if context:
            self.memory_context = context
```

## Best Practices

### 1. Token Budget Management

Always respect the token budget to avoid overloading your LLM:

```python
# Good: Token-aware context retrieval
context = memory.get_context(
    query,
    max_tokens=3000,  # Leave room for system prompt + user message
    max_memories=10
)
```

### 2. Categorize Memories

Use categories to organize different types of information:

```python
memory.save(content="User likes Python", category="preference")
memory.save(content="API key: xyz", category="credential", ttl_days=1)
memory.save(content="Project uses FastAPI", category="project")
```

### 3. Importance Scoring

Set importance based on relevance:

```python
# Critical information
memory.save(content="User is allergic to peanuts", importance=10.0)

# General information
memory.save(content="User prefers dark mode", importance=5.0)

# Low priority
memory.save(content="User mentioned it's sunny today", importance=1.0)
```

### 4. Session Management

Track conversation sessions:

```python
import uuid

session_key = f"session-{uuid.uuid4().hex}"

# Save conversation turns
memory.save_conversation(
    session_key=session_key,
    user_message=msg,
    assistant_response=resp
)

# Retrieve full conversation later
conversation = memory.get_session(session_key)
```

### 5. Cleanup

Always close connections:

```python
class MyAgent:
    def __init__(self):
        self.memory = ContextEngine()
    
    def cleanup(self):
        self.memory.close()

# Or use context manager
with ContextEngine() as memory:
    agent = MyAgent(memory)
    # ... use agent
```

## Environment Setup

### Docker Compose Setup

```yaml
version: '3.8'

services:
  postgres:
    image: ankane/pgvector:latest
    environment:
      POSTGRES_USER: agent
      POSTGRES_PASSWORD: agentpass
      POSTGRES_DB: context_engine
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama:/root/.ollama
    ports:
      - "11434:11434"

  agent:
    build: .
    environment:
      CTX_DB_HOST: postgres
      CTX_DB_PORT: 5432
      CTX_DB_NAME: context_engine
      CTX_DB_USER: agent
      CTX_DB_PASS: agentpass
      CTX_OLLAMA_URL: http://ollama:11434
      CTX_NAMESPACE: my-agent
    depends_on:
      - postgres
      - ollama

volumes:
  pgdata:
  ollama:
```

## CLI Command Reference

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `save` | Save a memory | `--category`, `--importance`, `--ttl-days`, `--tags` |
| `search` | Semantic search | `--limit`, `--min-similarity`, `--category` |
| `search-one` | Single best match | `--category` |
| `get-context` | Token-budgeted context | `--max-tokens`, `--max-memories` |
| `list` | List memories | `--limit`, `--category` |
| `delete` | Delete a memory | `doc_id` positional |
| `cleanup` | Delete expired memories | — |
| `init` | Initialize database schema | — |
| `agent-info` | Info for AI agents | `--python`, `--verbose` |
| `stats` | Memory statistics | — |
| `peek` | Full content of a memory | `doc_id` positional |
| `count` | Memory count | `--category` |
| `relate` | Create relationship | `--rel-type` (required) |
| `unrelate` | Remove relationship | `--rel-type` (optional, removes all if omitted) |
| `relations` | Show relationships | `--direction`, `--rel-type` |
| `working set` | Set session context | `key`, `value` positional |
| `working get` | Get session context | — |
| `working tasks` | List tasks | — |
| `working add-task` | Add a task | `--status`, `--assigned-to` |

Set `CTX_OUTPUT=compact` for pipe-delimited output. Set `CTX_OUTPUT=json` for JSON.

## Troubleshooting

### Connection Issues

```python
from context_engine.schema import SchemaManager
from context_engine.config import ContextEngineConfig

config = ContextEngineConfig()
schema = SchemaManager(config)

# Verify connection
success, error = schema.verify_connection()
if not success:
    print(f"Database error: {error}")
```

### Embedding Not Working

```python
from context_engine.providers import OllamaProvider

provider = OllamaProvider()
try:
    embedding = provider.embed("test")
    print(f"Embedding dimension: {len(embedding)}")
except Exception as e:
    print(f"Ollama error: {e}")
```

## Example: Complete Agent

See `examples/agent_example.py` for a complete working example.

```python
# examples/agent_example.py
from context_engine import ContextEngine
import uuid

class ContextAwareAgent:
    """Complete example of an agent with semantic memory."""
    
    def __init__(self, name="Agent"):
        self.name = name
        self.session_id = str(uuid.uuid4())[:8]
        self.memory = ContextEngine()
        
        # Load any existing preferences
        self._load_preferences()
    
    def _load_preferences(self):
        """Load user preferences at startup."""
        prefs = self.memory.get_context(
            "user preferences",
            category="preference",
            max_tokens=500
        )
        if prefs:
            print(f"Loaded preferences: {prefs}")
    
    def chat(self, message):
        """Process a message with context."""
        # Get relevant context
        context = self.memory.get_context(
            message,
            max_tokens=2000
        )
        
        # Build prompt
        prompt = self._build_prompt(context, message)
        
        # Simulate LLM response
        response = self._generate_response(prompt)
        
        # Save interaction
        self.memory.save_conversation(
            session_key=self.session_id,
            user_message=message,
            assistant_response=response
        )
        
        return response
    
    def _build_prompt(self, context, message):
        parts = []
        if context:
            parts.append(f"Relevant context:\n{context}")
        parts.append(f"User: {message}")
        parts.append("Assistant:")
        return "\n\n".join(parts)
    
    def _generate_response(self, prompt):
        # Your LLM integration here
        return f"[Response based on context]"
    
    def remember(self, fact, importance=5.0):
        """Explicitly remember a fact."""
        self.memory.save(
            content=fact,
            importance=importance
        )
        return "Remembered!"
    
    def cleanup(self):
        """Clean up resources."""
        self.memory.close()

# Usage
if __name__ == "__main__":
    agent = ContextAwareAgent("MyBot")
    
    # Learn something
    agent.remember("User likes Python", importance=8.0)
    
    # Chat
    response = agent.chat("What programming language should I use?")
    print(response)
    
    # Cleanup
    agent.cleanup()
```
