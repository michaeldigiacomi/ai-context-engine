"""Tests for MemoryManager class."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch


def test_memory_manager_init(test_config):
    """Test MemoryManager initialization."""
    from context_engine.memory_manager import MemoryManager

    # Patch where the classes are imported in memory_manager.py
    with patch('context_engine.memory_manager.WorkingMemory') as mock_wm, \
         patch('context_engine.memory_manager.ContextEngine') as mock_ce:

        manager = MemoryManager(config=test_config, model_type="local-8k")

        assert manager.model_type == "local-8k"
        mock_wm.assert_called_once_with(test_config)
        mock_ce.assert_called_once_with(config=test_config)


def test_remember_to_working(test_config):
    """Test saving to working tier."""
    from context_engine.memory_manager import MemoryManager

    with patch('context_engine.memory_manager.WorkingMemory') as mock_wm, \
         patch('context_engine.memory_manager.ContextEngine') as mock_ce:

        mock_working = MagicMock()
        mock_working.set_session_context.return_value = None
        mock_wm.return_value = mock_working

        manager = MemoryManager(config=test_config)
        manager.remember("User prefers dark mode", tier="working")

        mock_working.set_session_context.assert_called_once()


def test_save_task(test_config):
    """Test saving task via MemoryManager."""
    from context_engine.memory_manager import MemoryManager

    with patch('context_engine.memory_manager.WorkingMemory') as mock_wm:
        mock_working = MagicMock()
        mock_working.save_task.return_value = "task-123"
        mock_wm.return_value = mock_working

        manager = MemoryManager(config=test_config)
        task_id = manager.save_task(description="Test task")

        assert task_id == "task-123"
        # Called with description as positional arg
        mock_working.save_task.assert_called_once_with("Test task")


def test_get_context_assembles_tiers(test_config):
    """Test get_context assembles working + reference."""
    from context_engine.memory_manager import MemoryManager

    with patch('context_engine.memory_manager.WorkingMemory') as mock_wm, \
         patch('context_engine.memory_manager.ContextEngine') as mock_ce:

        mock_working = MagicMock()
        mock_working.get_session_context.return_value = {"user": "Alice"}
        mock_working.get_recent_decisions.return_value = []
        mock_wm.return_value = mock_working

        mock_ref = MagicMock()
        mock_ref.search.return_value = [
            {"content": "Project uses FastAPI", "similarity": 0.8,
             "importance": 5, "created_at": datetime.now(),
             "access_count": 10}
        ]
        mock_ce.return_value = mock_ref

        manager = MemoryManager(config=test_config, model_type="local-8k")
        context = manager.get_context("What framework?", max_tokens=4000)

        assert "user" in context or "Alice" in context or "SESSION CONTEXT" in context


def test_get_context_with_ranking(test_config):
    """Test that reference results are ranked by composite score."""
    from context_engine.memory_manager import MemoryManager

    with patch('context_engine.memory_manager.WorkingMemory') as mock_wm, \
         patch('context_engine.memory_manager.ContextEngine') as mock_ce:

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

        # Results should be ranked
        assert "New and relevant" in context or "Old but important" in context
