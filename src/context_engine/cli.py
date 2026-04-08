#!/usr/bin/env python3
"""
CLI for Context Engine.

Usage:
    ctx-engine save "Memory content" --category work
    ctx-engine search "What was I working on?"
    ctx-engine list --category work
    ctx-engine cleanup
"""

import argparse
import sys

from context_engine import ContextEngine


def show_agent_info(show_python=False):
    """Display information for AI agents about the context engine."""

    if show_python:
        python_example = '''
# QUICK START FOR AGENTS
# ======================

from context_engine import ContextEngine

# Initialize (auto-loads config from ~/.config/context_engine/config.json)
memory = ContextEngine()

# Save a memory
memory.save(
    content="User prefers Python",
    category="preference",
    importance=9.0
)

# Get relevant context for a query
context = memory.get_context(
    "What language should I use?",
    max_tokens=2000
)

# Save a conversation turn
memory.save_conversation(
    session_key="session-123",
    user_message="Hello",
    assistant_response="Hi there!"
)

# Search memories
results = memory.search("user preferences", limit=5)

# Cleanup
memory.close()
'''
        print(python_example)
        return

    info = '''
╔════════════════════════════════════════════════════════════════╗
║          PGVECTOR CONTEXT ENGINE - AGENT INFO                  ║
╚════════════════════════════════════════════════════════════════╝

WHAT IS THIS?
=============
A semantic memory system for AI agents. Store and retrieve relevant
context using vector embeddings (not just keyword search).

WHY USE IT?
===========
• Persistent memory across sessions
• Semantic search (find by meaning, not exact words)
• Automatic token budgeting for LLM context
• Namespace isolation for multi-agent setups
• TTL support for temporary memories

QUICK START
===========

1. Verify it's set up:
   ctx-engine list

2. Use in your agent code:

   from context_engine import ContextEngine
   memory = ContextEngine()

   # Save something
   memory.save("User likes Python", category="preference")

   # Retrieve relevant context
   context = memory.get_context("What language?", max_tokens=2000)

   # Use with your LLM
   response = call_llm(context + user_message)

COMMON COMMANDS
===============

ctx-engine save "Content" --category preference --importance 9
  → Save a memory with high importance

ctx-engine search "user preferences" --limit 5
  → Find relevant memories

ctx-engine get-context "current task" --max-tokens 3000
  → Get formatted context for LLM

ctx-engine list --category preference
  → List memories by category

AGENT BASE CLASS
================

For a complete agent framework:

from context_engine.agent import ContextAgent

class MyAgent(ContextAgent):
    def process(self, message):
        context = self.get_relevant_context(message)
        # Your LLM logic here
        return response

CONFIGURATION
=============

Config file: ~/.config/context_engine/config.json

Environment variables:
  CTX_DB_HOST      - PostgreSQL host
  CTX_DB_PORT      - PostgreSQL port
  CTX_DB_NAME      - Database name
  CTX_DB_USER      - Database user
  CTX_DB_PASS      - Database password
  CTX_NAMESPACE    - Agent namespace (isolation)
  CTX_OLLAMA_URL   - Ollama URL for embeddings

DOCUMENTATION
=============

• AGENT_SETUP.md      - Quick setup guide for agents
• AGENT_INTEGRATION.md - Detailed integration patterns
• README.md           - Full documentation

EXAMPLES
========

See examples/agent_example.py for a complete working agent.

MORE INFO
=========

Show Python code example:
  ctx-engine agent-info --python

Repository: https://github.com/michaeldigiacomi/ai-context-engine
'''
    print(info)


def main():
    parser = argparse.ArgumentParser(description="Context Engine CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # save command
    save_parser = subparsers.add_parser("save", help="Save a memory")
    save_parser.add_argument("content", help="Memory content")
    save_parser.add_argument("--category", default="general")
    save_parser.add_argument("--importance", type=float, default=1.0)
    save_parser.add_argument("--ttl", type=int, help="Days until expiration")
    save_parser.add_argument("--session", help="Session key")
    save_parser.add_argument("--tags", nargs="+", help="Tags")
    save_parser.add_argument("--source", help="Source identifier")
    save_parser.add_argument("--doc-id", help="Stable document ID")

    # search command
    search_parser = subparsers.add_parser("search", help="Search memories")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--min-similarity", type=float, default=0.5)
    search_parser.add_argument("--category", help="Filter by category")

    # get-context command
    ctx_parser = subparsers.add_parser("get-context", help="Get context for a query")
    ctx_parser.add_argument("query", help="Query or task description")
    ctx_parser.add_argument("--max-memories", type=int, default=10)
    ctx_parser.add_argument("--max-tokens", type=int, default=4000)
    ctx_parser.add_argument("--category", help="Filter by category")

    # list command
    list_parser = subparsers.add_parser("list", help="List memories")
    list_parser.add_argument("--category", help="Filter by category")
    list_parser.add_argument("--limit", type=int, default=50)

    # delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a memory")
    delete_parser.add_argument("doc_id", help="Document ID to delete")

    # cleanup command
    subparsers.add_parser("cleanup", help="Delete expired memories")

    # init command
    subparsers.add_parser("init", help="Initialize database schema")

    # agent-info command
    agent_info_parser = subparsers.add_parser("agent-info", help="Show information for AI agents")
    agent_info_parser.add_argument("--python", action="store_true", help="Show Python code example")

    # working command
    working_parser = subparsers.add_parser("working", help="Working memory commands")
    working_subparsers = working_parser.add_subparsers(dest="working_command")

    # working set
    set_parser = working_subparsers.add_parser("set", help="Set session context")
    set_parser.add_argument("key", help="Context key")
    set_parser.add_argument("value", help="Context value")
    set_parser.add_argument("--priority", type=int, default=5)
    set_parser.add_argument("--ttl", type=int, default=60, help="TTL in minutes")

    # working get
    get_parser = working_subparsers.add_parser("get", help="Get session context")

    # working tasks
    tasks_parser = working_subparsers.add_parser("tasks", help="List tasks")
    tasks_parser.add_argument("--status", help="Filter by status")

    # working add-task
    add_task_parser = working_subparsers.add_parser("add-task", help="Add a task")
    add_task_parser.add_argument("description", help="Task description")
    add_task_parser.add_argument("--priority", type=int, default=5)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Initialize engine
    try:
        ctx = ContextEngine()
    except Exception as e:
        print(f"Failed to initialize ContextEngine: {e}")
        sys.exit(1)

    try:
        if args.command == "save":
            doc_id = ctx.save(
                content=args.content,
                category=args.category,
                importance=args.importance,
                ttl_days=args.ttl,
                session_key=args.session,
                tags=args.tags,
                source=args.source,
                doc_id=args.doc_id,
            )
            print(f"Saved: {doc_id}")

        elif args.command == "search":
            results = ctx.search(
                query=args.query,
                limit=args.limit,
                min_similarity=args.min_similarity,
                category=args.category,
            )
            if not results:
                print("No results found.")
            else:
                for r in results:
                    print(f"[{r['similarity']:.2f}] [{r['category']}] {r['content'][:80]}...")

        elif args.command == "get-context":
            context = ctx.get_context(
                query=args.query,
                max_memories=args.max_memories,
                max_tokens=args.max_tokens,
                category=args.category,
            )
            print(context or "(no context found)")

        elif args.command == "list":
            memories = ctx.list(category=args.category, limit=args.limit)
            for m in memories:
                created = m.get("created_at", "unknown")
                print(f"[{created}] [{m['category']}] {m['content'][:60]}...")

        elif args.command == "delete":
            if ctx.delete(args.doc_id):
                print("Deleted.")
            else:
                print("Not found.")

        elif args.command == "cleanup":
            count = ctx.cleanup_expired()
            print(f"Deleted {count} expired memories.")

        elif args.command == "init":
            ctx._ensure_initialized()
            print("Database initialized.")

        elif args.command == "agent-info":
            show_agent_info(show_python=args.python)

        elif args.command == "working":
            from context_engine.memory_manager import MemoryManager
            manager = MemoryManager()

            if args.working_command == "set":
                manager.working.set_session_context(
                    args.key, args.value,
                    priority=args.priority, ttl_minutes=args.ttl
                )
                print(f"Set {args.key} = {args.value}")

            elif args.working_command == "get":
                ctx = manager.working.get_session_context()
                if ctx:
                    for k, v in ctx.items():
                        print(f"{k}: {v}")
                else:
                    print("No session context")

            elif args.working_command == "tasks":
                tasks = manager.working.get_tasks(status=args.status)
                for t in tasks:
                    print(f"[{t['status']}] {t['task_id']}: {t['description']}")

            elif args.working_command == "add-task":
                task_id = manager.working.save_task(
                    description=args.description,
                    priority=args.priority
                )
                print(f"Created task: {task_id}")

            manager.close()

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        ctx.close()


if __name__ == "__main__":
    main()
