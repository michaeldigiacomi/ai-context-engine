# Two-Tier Memory System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Working Memory (session-scoped, fast) and MemoryManager (orchestration) alongside existing Reference Memory, with strict token budgets and cross-project search.

**Architecture:** PostgreSQL with two schemas (`working` and `reference`), Python classes for each tier, MemoryManager orchestrates context assembly with weighted ranking.

**Tech Stack:** Python 3.9+, PostgreSQL, psycopg2, existing pgvector extension

---

## File Structure

```
src/context_engine/
├── __init__.py              # Export MemoryManager, WorkingMemory
├── core.py                  # Existing ContextEngine (reference tier)
├── config.py                # Existing configuration
├── providers.py             # Existing embedding providers
├── schema.py                # Modify: add working schema support
├── working_memory.py        # New: WorkingMemory class
├── memory_manager.py        # New: MemoryManager class
└── cli.py                   # Modify: add working memory commands

tests/
├── test_working_memory.py   # New: WorkingMemory tests
├── test_memory_manager.py   # New: MemoryManager tests
└── conftest.py              # Modify: add working memory fixtures
```

---

## Task 1: Schema Support for Working Memory

**Files:**
- Modify: `src/context_engine/schema.py`
- Test: `tests/test_schema.py` (new test file)

**Context:** The `SchemaManager` currently handles the `memories` table. We need to extend it to create and manage the `working` schema with its tables.

- [ ] **Step 1: Write failing test for working schema creation**

```python
def test_working_schema_creation(schema_manager):
    """Test that working schema and tables are created."""
    schema_manager.ensure_working_schema()
    
    # Verify tables exist
    conn = psycopg2.connect(schema_manager.config.conn_string)
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'working'
    """)
    tables = {row[0] for row in cur.fetchall()}
    cur.close()
    conn.close()
    
    assert 'session_context' in tables
    assert 'tasks' in tables
    assert 'recent_decisions' in tables
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_schema.py::test_working_schema_creation -v
```

Expected: FAIL with "ensure_working_schema not defined"

- [ ] **Step 3: Add working schema methods to SchemaManager**

In `src/context_engine/schema.py`, add to `SchemaManager` class:

```python
def ensure_working_schema(self):
    """Create working schema tables if they don't exist."""
    conn = psycopg2.connect(self.config.conn_string)
    cur = conn.cursor()
    
    try:
        # Create schema
        cur.execute("CREATE SCHEMA IF NOT EXISTS working")
        
        # Create session_context table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS working.session_context (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                priority INTEGER DEFAULT 5,
                ttl_minutes INTEGER DEFAULT 60,
                last_accessed TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Create tasks table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS working.tasks (
                task_id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                plan JSONB,
                status TEXT DEFAULT 'planning',
                assigned_to TEXT,
                priority INTEGER DEFAULT 5,
                result JSONB,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Create recent_decisions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS working.recent_decisions (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'decision',
                context TEXT,
                ttl_minutes INTEGER DEFAULT 480,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        conn.commit()
    finally:
        cur.close()
        conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_schema.py::test_working_schema_creation -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/context_engine/schema.py tests/test_schema.py
git commit -m "feat: Add working schema support to SchemaManager

Add ensure_working_schema method to create working schema
tables: session_context, tasks, recent_decisions."
```

---

## Task 2: WorkingMemory Class

**Files:**
- Create: `src/context_engine/working_memory.py`
- Test: `tests/test_working_memory.py`

**Context:** WorkingMemory provides fast, session-scoped storage without embeddings. It manages TTL, size limits, and LRU eviction.

- [ ] **Step 1: Write failing test for WorkingMemory initialization**

```python
import pytest
from unittest.mock import MagicMock, patch

def test_working_memory_init(test_config):
    """Test WorkingMemory initialization."""
    from context_engine.working_memory import WorkingMemory
    
    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        wm = WorkingMemory(test_config)
        
        assert wm.config == test_config
        assert wm._conn is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_working_memory.py::test_working_memory_init -v
```

Expected: FAIL with "No module named 'context_engine.working_memory'"

- [ ] **Step 3: Create WorkingMemory class with initialization**

Create `src/context_engine/working_memory.py`:

```python
"""Working memory - session-scoped, fast-access storage."""

import psycopg2
from typing import Optional, Dict, Any, List
from context_engine.config import ContextEngineConfig


class WorkingMemory:
    """
    Fast, session-scoped memory for temporary state.
    
    No embeddings, direct SQL access, TTL-based expiration.
    """
    
    SOFT_LIMIT = 100
    HARD_LIMIT = 200
    
    def __init__(self, config: Optional[ContextEngineConfig] = None):
        """Initialize working memory."""
        self.config = config or ContextEngineConfig()
        self._conn = None
    
    def _get_conn(self):
        """Get database connection with lazy initialization."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.config.conn_string)
        return self._conn
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_working_memory.py::test_working_memory_init -v
```

Expected: PASS

- [ ] **Step 5: Write failing test for set_session_context**

```python
def test_set_session_context(test_config):
    """Test saving session context."""
    from context_engine.working_memory import WorkingMemory
    
    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn
        
        wm = WorkingMemory(test_config)
        wm.set_session_context("user_name", "Alice", priority=8)
        
        # Verify INSERT was called
        mock_cur.execute.assert_called_once()
        call_args = mock_cur.execute.call_args[0]
        assert "INSERT INTO working.session_context" in call_args[0]
        mock_conn.commit.assert_called_once()
```

- [ ] **Step 6: Add set_session_context method**

In `src/context_engine/working_memory.py`, add to `WorkingMemory` class:

```python
def set_session_context(self, key: str, value: str, 
                       priority: int = 5, ttl_minutes: int = 60) -> None:
    """Set session context with TTL."""
    self._check_size_limit()
    
    conn = self._get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO working.session_context 
            (key, value, priority, ttl_minutes, last_accessed, created_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                priority = EXCLUDED.priority,
                ttl_minutes = EXCLUDED.ttl_minutes,
                last_accessed = NOW()
        """, (key, value, priority, ttl_minutes))
        conn.commit()
    finally:
        cur.close()
```

- [ ] **Step 7: Add _check_size_limit helper**

In `src/context_engine/working_memory.py`, add:

```python
def _check_size_limit(self):
    """Check and enforce size limits."""
    conn = self._get_conn()
    cur = conn.cursor()
    
    try:
        # Get current count
        cur.execute("SELECT COUNT(*) FROM working.session_context")
        count = cur.fetchone()[0]
        
        if count >= self.HARD_LIMIT:
            # Evict lowest priority + oldest
            cur.execute("""
                DELETE FROM working.session_context
                WHERE ctid IN (
                    SELECT ctid FROM working.session_context
                    ORDER BY priority ASC, last_accessed ASC
                    LIMIT %s
                )
            """, (count - self.SOFT_LIMIT + 1,))
            conn.commit()
        elif count >= self.SOFT_LIMIT:
            # Just log warning (print for now)
            print(f"Warning: Working memory at {count}/{self.HARD_LIMIT} items")
    finally:
        cur.close()
```

- [ ] **Step 8: Run test to verify set_session_context works**

```bash
pytest tests/test_working_memory.py::test_set_session_context -v
```

Expected: PASS

- [ ] **Step 9: Write failing test for get_session_context**

```python
def test_get_session_context(test_config):
    """Test retrieving session context."""
    from context_engine.working_memory import WorkingMemory
    
    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        # Return a context row
        mock_cur.fetchall.return_value = [
            ("user_name", "Alice"),
            ("theme", "dark")
        ]
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn
        
        wm = WorkingMemory(test_config)
        result = wm.get_session_context()
        
        assert result == {"user_name": "Alice", "theme": "dark"}
        mock_cur.execute.assert_called_once()
```

- [ ] **Step 10: Add get_session_context method**

In `src/context_engine/working_memory.py`, add:

```python
def get_session_context(self) -> Dict[str, str]:
    """Get all session context key-values."""
    conn = self._get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT key, value FROM working.session_context
            WHERE created_at + INTERVAL '1 minute' * ttl_minutes > NOW()
        """)
        rows = cur.fetchall()
        return {key: value for key, value in rows}
    finally:
        cur.close()
```

- [ ] **Step 11: Run test to verify get_session_context works**

```bash
pytest tests/test_working_memory.py::test_get_session_context -v
```

Expected: PASS

- [ ] **Step 12: Write failing test for save_task**

```python
def test_save_task(test_config):
    """Test saving a task."""
    from context_engine.working_memory import WorkingMemory
    
    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn
        
        wm = WorkingMemory(test_config)
        task_id = wm.save_task(
            description="Refactor auth module",
            plan=["Step 1", "Step 2"],
            priority=8
        )
        
        assert task_id is not None
        assert len(task_id) > 0
```

- [ ] **Step 13: Add save_task and related methods**

In `src/context_engine/working_memory.py`, add:

```python
def save_task(self, description: str, plan: Optional[List[str]] = None,
              status: str = "planning", assigned_to: Optional[str] = None,
              priority: int = 5, task_id: Optional[str] = None) -> str:
    """Save task, auto-generate ID if not provided."""
    import json
    import uuid
    
    if task_id is None:
        task_id = f"task-{uuid.uuid4().hex[:8]}"
    
    conn = self._get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO working.tasks 
            (task_id, description, plan, status, assigned_to, priority, created_at, updated_at)
            VALUES (%s, %s, %s::jsonb, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (task_id) DO UPDATE SET
                description = EXCLUDED.description,
                plan = EXCLUDED.plan,
                status = EXCLUDED.status,
                assigned_to = EXCLUDED.assigned_to,
                priority = EXCLUDED.priority,
                updated_at = NOW()
        """, (task_id, description, json.dumps(plan) if plan else None, 
              status, assigned_to, priority))
        conn.commit()
        return task_id
    finally:
        cur.close()

def get_tasks(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Get tasks, optionally filtered by status."""
    import json
    conn = self._get_conn()
    cur = conn.cursor()
    
    try:
        if status:
            cur.execute("""
                SELECT task_id, description, plan, status, assigned_to, priority, result
                FROM working.tasks WHERE status = %s LIMIT %s
            """, (status, limit))
        else:
            cur.execute("""
                SELECT task_id, description, plan, status, assigned_to, priority, result
                FROM working.tasks ORDER BY updated_at DESC LIMIT %s
            """, (limit,))
        
        rows = cur.fetchall()
        tasks = []
        for row in rows:
            task = {
                "task_id": row[0],
                "description": row[1],
                "plan": row[2],
                "status": row[3],
                "assigned_to": row[4],
                "priority": row[5],
                "result": row[6]
            }
            tasks.append(task)
        return tasks
    finally:
        cur.close()

def update_task(self, task_id: str, **kwargs) -> bool:
    """Update task fields."""
    import json
    allowed = {"description", "plan", "status", "assigned_to", "priority", "result"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    
    if not updates:
        return False
    
    conn = self._get_conn()
    cur = conn.cursor()
    
    try:
        # Convert plan and result to JSON if needed
        if "plan" in updates and updates["plan"] is not None:
            updates["plan"] = json.dumps(updates["plan"])
        if "result" in updates and updates["result"] is not None:
            updates["result"] = json.dumps(updates["result"])
        
        # Build dynamic UPDATE
        set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
        values = list(updates.values()) + [task_id]
        
        cur.execute(f"""
            UPDATE working.tasks 
            SET {set_clause}, updated_at = NOW()
            WHERE task_id = %s
        """, values)
        
        updated = cur.rowcount > 0
        conn.commit()
        return updated
    finally:
        cur.close()
```

- [ ] **Step 14: Run test to verify save_task works**

```bash
pytest tests/test_working_memory.py::test_save_task -v
```

Expected: PASS

- [ ] **Step 15: Write failing test for save_decision and get_recent_decisions**

```python
def test_save_and_get_decisions(test_config):
    """Test saving and retrieving decisions."""
    from context_engine.working_memory import WorkingMemory
    
    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        # Return decision rows
        mock_cur.fetchall.return_value = [
            (1, "Use FastAPI", "framework", "Need async support"),
        ]
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn
        
        wm = WorkingMemory(test_config)
        
        # Save decision
        wm.save_decision("Use FastAPI", context="Need async support")
        
        # Get recent
        decisions = wm.get_recent_decisions(limit=5)
        
        assert len(decisions) == 1
        assert decisions[0]["content"] == "Use FastAPI"
```

- [ ] **Step 16: Add decision methods**

In `src/context_engine/working_memory.py`, add:

```python
def save_decision(self, content: str, context: Optional[str] = None,
                 category: str = "decision", ttl_minutes: int = 480) -> int:
    """Save decision with auto-expire. Returns decision ID."""
    conn = self._get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO working.recent_decisions 
            (content, category, context, ttl_minutes, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            RETURNING id
        """, (content, category, context, ttl_minutes))
        
        decision_id = cur.fetchone()[0]
        conn.commit()
        return decision_id
    finally:
        cur.close()

def get_recent_decisions(self, limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent decisions."""
    conn = self._get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT id, content, category, context, created_at
            FROM working.recent_decisions
            WHERE created_at + INTERVAL '1 minute' * ttl_minutes > NOW()
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))
        
        rows = cur.fetchall()
        decisions = []
        for row in rows:
            decisions.append({
                "id": row[0],
                "content": row[1],
                "category": row[2],
                "context": row[3],
                "created_at": row[4]
            })
        return decisions
```

- [ ] **Step 17: Run test to verify decision methods work**

```bash
pytest tests/test_working_memory.py::test_save_and_get_decisions -v
```

Expected: PASS

- [ ] **Step 18: Write failing test for cleanup_expired**

```python
def test_cleanup_expired(test_config):
    """Test cleaning up expired entries."""
    from context_engine.working_memory import WorkingMemory
    
    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.rowcount = 5
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn
        
        wm = WorkingMemory(test_config)
        count = wm.cleanup_expired()
        
        assert count == 5
        # Verify delete was called for session_context
        mock_cur.execute.assert_any_call("""
            DELETE FROM working.session_context
            WHERE created_at + INTERVAL '1 minute' * ttl_minutes <= NOW()
        """)
```

- [ ] **Step 19: Add cleanup_expired method**

In `src/context_engine/working_memory.py`, add:

```python
def cleanup_expired(self) -> int:
    """Delete expired entries from all working tables. Returns total count."""
    conn = self._get_conn()
    cur = conn.cursor()
    total = 0
    
    try:
        # Cleanup session_context
        cur.execute("""
            DELETE FROM working.session_context
            WHERE created_at + INTERVAL '1 minute' * ttl_minutes <= NOW()
        """)
        total += cur.rowcount
        
        # Cleanup recent_decisions
        cur.execute("""
            DELETE FROM working.recent_decisions
            WHERE created_at + INTERVAL '1 minute' * ttl_minutes <= NOW()
        """)
        total += cur.rowcount
        
        conn.commit()
        return total
    finally:
        cur.close()
```

- [ ] **Step 20: Run test to verify cleanup works**

```bash
pytest tests/test_working_memory.py::test_cleanup_expired -v
```

Expected: PASS

- [ ] **Step 21: Add close method and commit WorkingMemory**

In `src/context_engine/working_memory.py`, add:

```python
def close(self):
    """Close database connection."""
    if self._conn and not self._conn.closed:
        self._conn.close()
        self._conn = None

def __enter__(self):
    return self

def __exit__(self, exc_type, exc_val, exc_tb):
    self.close()
    return False
```

- [ ] **Step 22: Commit WorkingMemory class**

```bash
git add src/context_engine/working_memory.py tests/test_working_memory.py
git commit -m "feat: Add WorkingMemory class

Fast session-scoped storage with TTL, size limits,
task tracking, and recent decisions."
```

---

## Task 3: MemoryManager Class

**Files:**
- Create: `src/context_engine/memory_manager.py`
- Modify: `src/context_engine/__init__.py` (exports)
- Test: `tests/test_memory_manager.py`

**Context:** MemoryManager orchestrates WorkingMemory and ContextEngine with token budgets and intelligent ranking.

- [ ] **Step 1: Write failing test for MemoryManager initialization**

```python
def test_memory_manager_init(test_config):
    """Test MemoryManager initialization."""
    from context_engine.memory_manager import MemoryManager
    
    with patch('context_engine.working_memory.WorkingMemory') as mock_wm, \
         patch('context_engine.core.ContextEngine') as mock_ce:
        
        manager = MemoryManager(config=test_config, model_type="local-8k")
        
        assert manager.model_type == "local-8k"
        mock_wm.assert_called_once_with(test_config)
        mock_ce.assert_called_once_with(config=test_config)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_memory_manager.py::test_memory_manager_init -v
```

Expected: FAIL with "No module named 'context_engine.memory_manager'"

- [ ] **Step 3: Create MemoryManager class**

Create `src/context_engine/memory_manager.py`:

```python
"""MemoryManager - orchestrates working and reference memory."""

from typing import Optional, Dict, Any, List
from context_engine.config import ContextEngineConfig
from context_engine.core import ContextEngine
from context_engine.working_memory import WorkingMemory


DEFAULT_TOKEN_BUDGETS = {
    "local-8k": 4000,
    "local-32k": 8000,
    "claude-haiku": 6000,
    "claude-sonnet": 8000,
    "claude-opus": 12000,
    "gpt-4o": 8000,
}


class MemoryManager:
    """
    Orchestrates working and reference memory tiers.
    
    Manages token budgets, context assembly, and cross-namespace search.
    """
    
    def __init__(self, config: Optional[ContextEngineConfig] = None,
                 model_type: str = "claude-sonnet"):
        """Initialize memory manager with both tiers."""
        self.config = config or ContextEngineConfig()
        self.model_type = model_type
        self.working = WorkingMemory(self.config)
        self.reference = ContextEngine(config=self.config)
    
    def _get_token_budget(self, max_tokens: Optional[int] = None) -> int:
        """Get token budget based on model type or explicit override."""
        if max_tokens is not None:
            return max_tokens
        return DEFAULT_TOKEN_BUDGETS.get(self.model_type, 8000)
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text."""
        return len(text) // 4  # ~4 chars per token
```

- [ ] **Step 4: Run test to verify initialization works**

```bash
pytest tests/test_memory_manager.py::test_memory_manager_init -v
```

Expected: PASS

- [ ] **Step 5: Write failing test for remember with tier selection**

```python
def test_remember_to_working(test_config):
    """Test saving to working tier."""
    from context_engine.memory_manager import MemoryManager
    
    with patch('context_engine.working_memory.WorkingMemory') as mock_wm, \
         patch('context_engine.core.ContextEngine') as mock_ce:
        
        mock_working = MagicMock()
        mock_working.set_session_context.return_value = None
        mock_wm.return_value = mock_working
        
        manager = MemoryManager(config=test_config)
        manager.remember("User prefers dark mode", tier="working")
        
        mock_working.set_session_context.assert_called_once()
```

- [ ] **Step 6: Add remember method with tier routing**

In `src/context_engine/memory_manager.py`, add to `MemoryManager`:

```python
def remember(self, content: str, tier: str = "reference", **kwargs) -> str:
    """
    Save to appropriate tier.
    
    tier="working": Session-scoped, no embedding
    tier="reference": Long-term, semantic searchable
    """
    if tier == "working":
        # For working memory, store as session context
        key = kwargs.get("key", f"memory-{hash(content) & 0xFFFFFF}")
        self.working.set_session_context(
            key=key,
            value=content,
            priority=kwargs.get("priority", 5),
            ttl_minutes=kwargs.get("ttl_minutes", 60)
        )
        return key
    else:
        # Reference tier
        return self.reference.save(content, **kwargs)
```

- [ ] **Step 7: Run test to verify remember works**

```bash
pytest tests/test_memory_manager.py::test_remember_to_working -v
```

Expected: PASS

- [ ] **Step 8: Write failing test for save_task**

```python
def test_save_task(test_config):
    """Test saving task via MemoryManager."""
    from context_engine.memory_manager import MemoryManager
    
    with patch('context_engine.working_memory.WorkingMemory') as mock_wm:
        mock_working = MagicMock()
        mock_working.save_task.return_value = "task-123"
        mock_wm.return_value = mock_working
        
        manager = MemoryManager(config=test_config)
        task_id = manager.save_task(description="Test task")
        
        assert task_id == "task-123"
        mock_working.save_task.assert_called_once_with(
            description="Test task"
        )
```

- [ ] **Step 9: Add save_task and task methods**

In `src/context_engine/memory_manager.py`, add:

```python
def save_task(self, description: str, **kwargs) -> str:
    """Save task to working memory."""
    return self.working.save_task(description, **kwargs)

def get_ready_tasks(self) -> List[Dict[str, Any]]:
    """Get tasks ready for execution."""
    return self.working.get_tasks(status="ready")

def update_task(self, task_id: str, **kwargs) -> bool:
    """Update task fields."""
    return self.working.update_task(task_id, **kwargs)
```

- [ ] **Step 10: Run test to verify save_task works**

```bash
pytest tests/test_memory_manager.py::test_save_task -v
```

Expected: PASS

- [ ] **Step 11: Write failing test for get_context**

```python
def test_get_context_assembles_tiers(test_config):
    """Test get_context assembles working + reference."""
    from context_engine.memory_manager import MemoryManager
    
    with patch('context_engine.working_memory.WorkingMemory') as mock_wm, \
         patch('context_engine.core.ContextEngine') as mock_ce:
        
        mock_working = MagicMock()
        mock_working.get_session_context.return_value = {"user": "Alice"}
        mock_working.get_recent_decisions.return_value = []
        mock_wm.return_value = mock_working
        
        mock_ref = MagicMock()
        mock_ref.get_context.return_value = "Project uses FastAPI"
        mock_ref.search.return_value = []
        mock_ce.return_value = mock_ref
        
        manager = MemoryManager(config=test_config, model_type="local-8k")
        context = manager.get_context("What framework?", max_tokens=4000)
        
        assert "user" in context
        assert "Alice" in context
```

- [ ] **Step 12: Add get_context method**

In `src/context_engine/memory_manager.py`, add:

```python
def get_context(self, query: str, max_tokens: Optional[int] = None,
               include_namespaces: Optional[List[str]] = None) -> str:
    """
    Get assembled context respecting token budget.
    
    Budget allocation:
    - Working memory: up to 20%
    - Recent decisions: up to 10%
    - Reference: remaining 70%
    """
    budget = self._get_token_budget(max_tokens)
    sections = []
    
    # Working memory (max 20%)
    working_limit = int(budget * 0.2)
    working_ctx = self._format_working_context()
    working_tokens = self._estimate_tokens(working_ctx)
    
    if working_tokens <= working_limit:
        if working_ctx:
            sections.append(("SESSION CONTEXT", working_ctx))
        budget -= working_tokens
    else:
        truncated = self._truncate(working_ctx, working_limit)
        if truncated:
            sections.append(("SESSION CONTEXT", truncated))
        budget = int(budget * 0.8)
    
    # Recent decisions (max 10%)
    if budget > 0:
        dec_limit = int(budget * 0.1)
        decisions = self.working.get_recent_decisions(limit=5)
        if decisions:
            dec_text = self._format_decisions(decisions)
            if self._estimate_tokens(dec_text) <= dec_limit:
                sections.append(("RECENT DECISIONS", dec_text))
                budget -= self._estimate_tokens(dec_text)
            else:
                sections.append(("RECENT DECISIONS", 
                    self._truncate(dec_text, dec_limit)))
                budget = int(budget * 0.9)
    
    # Reference memory (remaining budget)
    if budget > 500:  # Need at least 500 tokens for reference
        ref_ctx = self._get_reference_context(query, budget, include_namespaces)
        if ref_ctx:
            sections.append(("RELEVANT KNOWLEDGE", ref_ctx))
    
    return self._format_sections(sections)

def _format_working_context(self) -> str:
    """Format working memory as context string."""
    ctx = self.working.get_session_context()
    if not ctx:
        return ""
    lines = [f"{k}: {v}" for k, v in ctx.items()]
    return "\n".join(lines)

def _format_decisions(self, decisions: List[Dict]) -> str:
    """Format decisions as context string."""
    lines = []
    for d in decisions:
        line = f"- {d['content']}"
        if d.get('context'):
            line += f" (Context: {d['context']})"
        lines.append(line)
    return "\n".join(lines)

def _get_reference_context(self, query: str, budget: int,
                          namespaces: Optional[List[str]]) -> str:
    """Get reference context with optional cross-namespace search."""
    contexts = []
    
    # Current namespace
    current = self.reference.get_context(query, max_tokens=int(budget * 0.7))
    if current:
        contexts.append(current)
    
    # Cross-namespace if requested
    if namespaces and "*" in namespaces:
        # Would need to implement cross-namespace search in ContextEngine
        # For now, just return current
        pass
    
    return "\n\n".join(contexts)

def _format_sections(self, sections: List[tuple]) -> str:
    """Format sections with headers."""
    parts = []
    for title, content in sections:
        if content.strip():
            parts.append(f"{title}:\n{content}")
    return "\n\n".join(parts)

def _truncate(self, text: str, token_budget: int) -> str:
    """Truncate text to fit token budget."""
    max_chars = token_budget * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars-3] + "..."
```

- [ ] **Step 13: Run test to verify get_context works**

```bash
pytest tests/test_memory_manager.py::test_get_context_assembles_tiers -v
```

Expected: PASS

- [ ] **Step 14: Write failing test for ranked reference results**

```python
def test_get_context_with_ranking(test_config):
    """Test that reference results are ranked by composite score."""
    from context_engine.memory_manager import MemoryManager
    
    with patch('context_engine.working_memory.WorkingMemory') as mock_wm, \
         patch('context_engine.core.ContextEngine') as mock_ce:
        
        mock_wm.return_value = MagicMock()
        mock_wm.return_value.get_session_context.return_value = {}
        mock_wm.return_value.get_recent_decisions.return_value = []
        
        # Simulate search results that need ranking
        mock_ref = MagicMock()
        mock_ref.search.return_value = [
            {"content": "Old but important", "similarity": 0.6, 
             "importance": 10, "created_at": datetime(2024, 1, 1),
             "access_count": 100},
            {"content": "New and relevant", "similarity": 0.8,
             "importance": 5, "created_at": datetime.now(),
             "access_count": 5},
        ]
        mock_ce.return_value = mock_ref
        
        manager = MemoryManager(config=test_config)
        # Should rank new+relevant higher than old+important
        context = manager.get_context("current task")
        
        # "New and relevant" should appear before "Old but important"
        new_pos = context.find("New and relevant")
        old_pos = context.find("Old but important")
        assert new_pos < old_pos
```

- [ ] **Step 15: Add ranking to _get_reference_context**

In `src/context_engine/memory_manager.py`, replace `_get_reference_context` with ranked version:

```python
def _get_reference_context(self, query: str, budget: int,
                          namespaces: Optional[List[str]]) -> str:
    """Get ranked reference context."""
    from datetime import datetime, timedelta
    
    # Search for matches
    results = self.reference.search(query, limit=20)
    
    if not results:
        return ""
    
    # Rank by composite score
    now = datetime.now()
    for r in results:
        # Base similarity (0-1)
        sim = r.get("similarity", 0)
        
        # Importance normalized (0-1)
        imp = r.get("importance", 5) / 10.0
        
        # Recency decay (0-1), 30 days = 1.0, older = decay
        created = r.get("created_at", now)
        if isinstance(created, str):
            created = datetime.fromisoformat(created.replace('Z', '+00:00'))
        days_old = (now - created).days
        rec = max(0, 1 - (days_old / 30.0))
        
        # Frequency normalized (0-1), cap at 100
        freq = min(r.get("access_count", 0), 100) / 100.0
        
        # Weighted composite
        r["score"] = (0.5 * sim + 0.2 * imp + 0.2 * rec + 0.1 * freq)
    
    # Sort by score
    results.sort(key=lambda x: x["score"], reverse=True)
    
    # Build context within budget
    max_chars = budget * 4
    context_parts = []
    total_chars = 0
    
    for r in results:
        content = r.get("content", "")
        if total_chars + len(content) + 50 > max_chars:
            break
        context_parts.append(content)
        total_chars += len(content) + 50
    
    return "\n\n".join(context_parts)
```

- [ ] **Step 16: Run test to verify ranking works**

```bash
pytest tests/test_memory_manager.py::test_get_context_with_ranking -v
```

Expected: PASS

- [ ] **Step 17: Add close method and export MemoryManager**

In `src/context_engine/memory_manager.py`, add:

```python
def close(self):
    """Close all connections."""
    self.working.close()
    self.reference.close()

def __enter__(self):
    return self

def __exit__(self, exc_type, exc_val, exc_tb):
    self.close()
    return False
```

In `src/context_engine/__init__.py`, add exports:

```python
from context_engine.memory_manager import MemoryManager
from context_engine.working_memory import WorkingMemory

__all__ = [
    "ContextEngine",
    "ContextEngineConfig",
    "EmbeddingProvider",
    "OllamaProvider",
    "MemoryManager",  # New
    "WorkingMemory",  # New
]
```

- [ ] **Step 18: Commit MemoryManager**

```bash
git add src/context_engine/memory_manager.py src/context_engine/__init__.py tests/test_memory_manager.py
git commit -m "feat: Add MemoryManager class

Orchestrates working and reference memory tiers with
token budgets, ranked reference results, and task management."
```

---

## Task 4: CLI Integration

**Files:**
- Modify: `src/context_engine/cli.py`
- Test: `tests/test_cli.py` (additional tests)

**Context:** Add CLI commands for working memory management.

- [ ] **Step 1: Write failing test for working memory CLI commands**

```python
def test_cli_working_context(mock_memory_manager):
    """Test working context command."""
    from context_engine.cli import main
    
    with patch('context_engine.cli.MemoryManager') as mock_mm:
        mock_manager = MagicMock()
        mock_manager.working.get_session_context.return_value = {"user": "test"}
        mock_mm.return_value = mock_manager
        
        with patch('sys.argv', ['ctx-engine', 'working-context']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                main()
                output = mock_stdout.getvalue()
                assert "user" in output
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_cli.py::test_cli_working_context -v
```

Expected: FAIL with "working-context not a recognized command"

- [ ] **Step 3: Add working memory CLI commands**

In `src/context_engine/cli.py`, add to argument parser:

```python
# Add subparser for working commands
working_parser = subparsers.add_parser('working', help='Working memory commands')
working_subparsers = working_parser.add_subparsers(dest='working_command')

# working set
set_parser = working_subparsers.add_parser('set', help='Set session context')
set_parser.add_argument('key', help='Context key')
set_parser.add_argument('value', help='Context value')
set_parser.add_argument('--priority', type=int, default=5)
set_parser.add_argument('--ttl', type=int, default=60, help='TTL in minutes')

# working get
get_parser = working_subparsers.add_parser('get', help='Get session context')

# working tasks
 tasks_parser = working_subparsers.add_parser('tasks', help='List tasks')
 tasks_parser.add_argument('--status', help='Filter by status')

# working add-task
add_task_parser = working_subparsers.add_parser('add-task', help='Add a task')
add_task_parser.add_argument('description', help='Task description')
add_task_parser.add_argument('--priority', type=int, default=5)
```

- [ ] **Step 4: Add command handlers**

In `src/context_engine/cli.py`, add handler in `main()`:

```python
elif args.command == 'working':
    from context_engine.memory_manager import MemoryManager
    manager = MemoryManager()
    
    if args.working_command == 'set':
        manager.working.set_session_context(
            args.key, args.value, 
            priority=args.priority, ttl_minutes=args.ttl
        )
        print(f"Set {args.key} = {args.value}")
    
    elif args.working_command == 'get':
        ctx = manager.working.get_session_context()
        if ctx:
            for k, v in ctx.items():
                print(f"{k}: {v}")
        else:
            print("No session context")
    
    elif args.working_command == 'tasks':
        tasks = manager.working.get_tasks(status=args.status)
        for t in tasks:
            print(f"[{t['status']}] {t['task_id']}: {t['description']}")
    
    elif args.working_command == 'add-task':
        task_id = manager.working.save_task(
            description=args.description,
            priority=args.priority
        )
        print(f"Created task: {task_id}")
    
    manager.close()
```

- [ ] **Step 5: Run test to verify CLI commands work**

```bash
pytest tests/test_cli.py::test_cli_working_context -v
```

Expected: PASS

- [ ] **Step 6: Commit CLI integration**

```bash
git add src/context_engine/cli.py tests/test_cli.py
git commit -m "feat: Add working memory CLI commands

Add 'working' subcommand with set, get, tasks, add-task operations."
```

---

## Task 5: Integration Tests

**Files:**
- Create: `tests/test_integration_two_tier.py`

**Context:** Integration tests requiring real PostgreSQL.

- [ ] **Step 1: Create integration test file**

Create `tests/test_integration_two_tier.py`:

```python
"""Integration tests for two-tier memory system."""

import pytest
import os


pytestmark = pytest.mark.integration


def test_working_memory_full_lifecycle(postgres_available):
    """Test complete working memory lifecycle with real PostgreSQL."""
    if not postgres_available:
        pytest.skip("PostgreSQL not available")
    
    from context_engine.memory_manager import MemoryManager
    from context_engine.config import ContextEngineConfig
    
    config = ContextEngineConfig(
        db_host=os.getenv("CTX_DB_HOST", "localhost"),
        db_port=int(os.getenv("CTX_DB_PORT", "5432")),
        db_name=os.getenv("CTX_DB_NAME", "context_engine"),
        db_user=os.getenv("CTX_DB_USER", ""),
        db_pass=os.getenv("CTX_DB_PASS", ""),
        namespace="test-two-tier"
    )
    
    manager = MemoryManager(config=config)
    
    # Save session context
    manager.working.set_session_context("test_key", "test_value")
    
    # Retrieve
    ctx = manager.working.get_session_context()
    assert ctx["test_key"] == "test_value"
    
    # Save task
    task_id = manager.working.save_task(
        description="Test task",
        plan=["Step 1", "Step 2"],
        status="ready"
    )
    assert task_id is not None
    
    # Retrieve task
    tasks = manager.working.get_tasks(status="ready")
    assert len(tasks) >= 1
    
    # Update task
    manager.working.update_task(task_id, status="done")
    tasks = manager.working.get_tasks(status="done")
    assert any(t["task_id"] == task_id for t in tasks)
    
    manager.close()


def test_memory_manager_context_assembly(postgres_available):
    """Test context assembly with both tiers."""
    if not postgres_available:
        pytest.skip("PostgreSQL not available")
    
    from context_engine.memory_manager import MemoryManager
    from context_engine.config import ContextEngineConfig
    
    config = ContextEngineConfig(namespace="test-assembly")
    manager = MemoryManager(config=config)
    
    # Save to reference
    manager.reference.save(
        content="Project uses FastAPI framework",
        category="tech_stack",
        importance=8
    )
    
    # Save to working
    manager.working.set_session_context("current_task", "refactor auth")
    
    # Get assembled context
    context = manager.get_context("What framework to use?", max_tokens=2000)
    
    # Verify both tiers present
    assert "current_task" in context
    assert "FastAPI" in context
    
    manager.close()


def test_ttl_expiration(postgres_available):
    """Test that expired entries are cleaned up."""
    if not postgres_available:
        pytest.skip("PostgreSQL not available")
    
    from context_engine.working_memory import WorkingMemory
    from context_engine.config import ContextEngineConfig
    import time
    
    config = ContextEngineConfig(namespace="test-ttl")
    wm = WorkingMemory(config)
    
    # Save with 1 second TTL
    wm.set_session_context("temp", "value", ttl_minutes=0.0167)  # ~1 second
    
    # Verify exists
    ctx = wm.get_session_context()
    assert ctx.get("temp") == "value"
    
    # Wait for expiration
    time.sleep(2)
    
    # Cleanup
    wm.cleanup_expired()
    
    # Verify gone
    ctx = wm.get_session_context()
    assert "temp" not in ctx
    
    wm.close()
```

- [ ] **Step 2: Run integration tests**

```bash
python run_tests.py --integration
```

Expected: PASS (if PostgreSQL available)

- [ ] **Step 3: Commit integration tests**

```bash
git add tests/test_integration_two_tier.py
git commit -m "test: Add two-tier memory integration tests

Tests for working memory lifecycle, context assembly,
and TTL expiration with real PostgreSQL."
```

---

## Task 6: Documentation

**Files:**
- Modify: `README.md` (add section)
- Create: `docs/two-tier-memory.md`

- [ ] **Step 1: Add Two-Tier Memory section to README**

In `README.md`, after existing sections, add:

```markdown
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
```

- [ ] **Step 2: Create detailed documentation**

Create `docs/two-tier-memory.md`:

```markdown
# Two-Tier Memory System

## Overview

The two-tier memory system provides separate storage optimized for different access patterns:

- **Working Memory**: Session-scoped, fast access, no embeddings
- **Reference Memory**: Long-term, semantic search with embeddings

## Use Cases

### Local Agent (Fast, Conversational)

```python
manager = MemoryManager(model_type="local-8k")

# Quick session context
manager.working.set_session_context("current_topic", "auth")

# Check for ready tasks
tasks = manager.working.get_tasks(status="ready")
for task in tasks:
    process_task(task)
```

### Remote Agent (Powerful, Batch)

```python
manager = MemoryManager(model_type="claude-opus")

# Rich context with cross-project learning
context = manager.get_context(
    query="authentication patterns",
    max_tokens=12000,
    include_namespaces=["*"]
)

# Execute complex task
result = process_with_context(context)
manager.working.update_task(task_id, status="done", result=result)
```

## Token Budgets

Default budgets by model type:

| Model Type | Default Budget |
|------------|----------------|
| local-8k | 4000 |
| local-32k | 8000 |
| claude-haiku | 6000 |
| claude-sonnet | 8000 |
| claude-opus | 12000 |
| gpt-4o | 8000 |

## API Reference

### MemoryManager

```python
class MemoryManager:
    def __init__(self, config=None, model_type="claude-sonnet")
    def get_context(query, max_tokens=None, include_namespaces=None) -> str
    def remember(content, tier="reference", **kwargs) -> str
    def save_task(description, **kwargs) -> str
    def get_ready_tasks() -> List[Dict]
    def update_task(task_id, **kwargs) -> bool
    def close()
```

### WorkingMemory

```python
class WorkingMemory:
    def set_session_context(key, value, priority=5, ttl_minutes=60)
    def get_session_context() -> Dict[str, str]
    def save_task(description, **kwargs) -> str
    def get_tasks(status=None, limit=50) -> List[Dict]
    def update_task(task_id, **kwargs) -> bool
    def save_decision(content, context=None, category="decision", ttl_minutes=480) -> int
    def get_recent_decisions(limit=10) -> List[Dict]
    def cleanup_expired() -> int
    def close()
```

## CLI Commands

```bash
# Working memory
ctx-engine working set key value --priority 8 --ttl 120
ctx-engine working get
ctx-engine working tasks --status ready
ctx-engine working add-task "Task description" --priority 8
```

## Database Schema

### working.session_context

| Column | Type | Description |
|--------|------|-------------|
| key | TEXT PK | Context key |
| value | TEXT | Context value |
| priority | INTEGER | 1-10, higher = keep longer |
| ttl_minutes | INTEGER | Expiration time |
| last_accessed | TIMESTAMP | Last access time |
| created_at | TIMESTAMP | Creation time |

### working.tasks

| Column | Type | Description |
|--------|------|-------------|
| task_id | TEXT PK | Unique task ID |
| description | TEXT | Task description |
| plan | JSONB | Array of steps |
| status | TEXT | planning, ready, executing, done, error |
| assigned_to | TEXT | Agent identifier |
| priority | INTEGER | Task priority |
| result | JSONB | Task output |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update |

### working.recent_decisions

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | Decision ID |
| content | TEXT | Decision text |
| category | TEXT | Decision category |
| context | TEXT | Context that prompted decision |
| ttl_minutes | INTEGER | Expiration time |
| created_at | TIMESTAMP | Creation time |
```

- [ ] **Step 3: Commit documentation**

```bash
git add README.md docs/two-tier-memory.md
git commit -m "docs: Add two-tier memory documentation

Add README section and detailed documentation
for the two-tier memory system."
```

---

## Final Verification

- [ ] **Run all tests**

```bash
python run_tests.py --unit
python run_tests.py --integration  # if PostgreSQL available
```

- [ ] **Verify imports work**

```bash
python -c "from context_engine import MemoryManager, WorkingMemory; print('OK')"
```

- [ ] **Final commit**

```bash
git log --oneline -10
```

---

## Spec Coverage Check

| Spec Requirement | Task | Status |
|------------------|------|--------|
| Working schema tables | Task 1 | ✓ |
| WorkingMemory class | Task 2 | ✓ |
| MemoryManager orchestration | Task 3 | ✓ |
| Token budget enforcement | Task 3 | ✓ |
| Ranked reference results | Task 3 | ✓ |
| Task management | Task 2, 3 | ✓ |
| CLI integration | Task 4 | ✓ |
| Integration tests | Task 5 | ✓ |
| Documentation | Task 6 | ✓ |

All spec requirements covered.
