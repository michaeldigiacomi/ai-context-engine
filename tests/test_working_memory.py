"""Tests for WorkingMemory class."""

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


def test_set_session_context(test_config):
    """Test saving session context."""
    from context_engine.working_memory import WorkingMemory

    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        # First call is for count, return 0
        mock_cur.fetchone.return_value = [0]
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn

        wm = WorkingMemory(test_config)
        wm.set_session_context("user_name", "Alice", priority=8)

        # Verify INSERT was called
        calls = mock_cur.execute.call_args_list
        assert any("INSERT INTO working.session_context" in str(c) for c in calls)
        mock_conn.commit.assert_called()


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
        assert task_id.startswith("task-")


def test_save_and_get_decisions(test_config):
    """Test saving and retrieving decisions."""
    from context_engine.working_memory import WorkingMemory

    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        # Return decision rows
        mock_cur.fetchall.return_value = [
            (1, "Use FastAPI", "framework", "Need async support", None),
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


def test_cleanup_expired(test_config):
    """Test cleaning up expired entries."""
    from context_engine.working_memory import WorkingMemory

    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.rowcount = 5  # Each table returns 5
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn

        wm = WorkingMemory(test_config)
        count = wm.cleanup_expired()

        # 5 from session_context + 5 from recent_decisions = 10
        assert count == 10
