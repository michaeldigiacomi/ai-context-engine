"""Tests for schema management."""

import pytest
import psycopg2


@pytest.fixture
def schema_manager():
    """Create a schema manager for testing."""
    from context_engine.schema import SchemaManager
    from context_engine.config import ContextEngineConfig
    config = ContextEngineConfig()
    return SchemaManager(config)


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
