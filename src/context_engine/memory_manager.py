"""MemoryManager - orchestrates working and reference memory."""

from datetime import datetime, timedelta
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
        """Get ranked reference context."""
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
            days_old = (now - created).days if isinstance(created, datetime) else 0
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

    def save_task(self, description: str, **kwargs) -> str:
        """Save task to working memory."""
        return self.working.save_task(description, **kwargs)

    def get_ready_tasks(self) -> List[Dict[str, Any]]:
        """Get tasks ready for execution."""
        return self.working.get_tasks(status="ready")

    def update_task(self, task_id: str, **kwargs) -> bool:
        """Update task fields."""
        return self.working.update_task(task_id, **kwargs)

    def close(self):
        """Close all connections."""
        self.working.close()
        self.reference.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
