"""Architecture fix phase: conversational dialog about architecture.

Provides LLM-based dialog for reviewing, discussing, and improving
system architecture with full project context.

Each fix request sends the full conversation history so LLM can iterate.
"""

from __future__ import annotations

import asyncio
from typing import Any

from skaro_core.phases._fix_base import ConversationalFixBase
from skaro_core.phases.base import PhaseResult

ARCH_FIX_LOG_FILENAME = "architecture-fix-log.md"


class ArchitectureFixPhase(ConversationalFixBase):
    phase_name = "architecture-fix"

    _FIX_ROLE = (
        "You are a senior software architect reviewing and improving system architecture.\n"
        "The user will ask questions about the architecture, request clarifications,\n"
        "or ask for improvements to specific aspects of the design.\n"
        "You must:\n"
        "1. Analyze the architecture and understand the design decisions\n"
        "2. Answer questions clearly and provide architectural guidance\n"
        "3. When code/design changes are needed, output changes as UNIFIED DIFF format:\n"
        "   ```diff\n"
        "   --- a/architecture.md\n"
        "   +++ b/architecture.md\n"
        "   @@ -line,count +line,count @@\n"
        "   -removed line\n"
        "   +added line\n"
        "    unchanged context line\n"
        "   ```\n"
        "4. Explain trade-offs, risks, and best practices\n"
        "5. IMPORTANT: Use standard unified diff format — NOT the full file.\n"
        "   The system will apply these changes automatically to the existing architecture.md"
    )

    async def run(self, **kwargs: Any) -> PhaseResult:
        """Process an architecture fix/discussion request.

        kwargs:
            message: str — user's question or request about architecture
            conversation: list[dict] — previous conversation turns
                [{"role": "user"|"assistant", "content": "..."}]
        """
        user_message: str = kwargs.get("message", "")
        conversation: list[dict] = kwargs.get("conversation", [])

        if not user_message.strip():
            return PhaseResult(success=False, message="Message is required.")

        # Build context: architecture + review
        extra_context: dict[str, str] = {}

        # Architecture document
        architecture = self.artifacts.read_architecture()
        if architecture.strip():
            extra_context["Current Architecture"] = architecture

        # Architecture review (if exists)
        review = self.artifacts.read_architecture_review()
        if review.strip():
            extra_context["Architecture Review"] = review

        # Project file tree
        tree = await self._scan_project_tree_async()
        if tree:
            extra_context["Project File Tree"] = tree

        # Cacheable context: architecture (prompt caching)
        cacheable_context: dict[str, str] = {}
        if architecture.strip():
            cacheable_context["Architecture"] = architecture

        response, proposed, file_diffs, updated_conv = await self._run_fix(
            user_message, conversation, extra_context,
            cacheable_context=cacheable_context,
        )

        # Persist
        self._write_fix_log_entry(
            self._arch_fix_log_path(),
            "# Architecture Fix Log",
            user_message,
            response,
            proposed,
        )
        self._save_conversation_to(self._arch_conv_path(), updated_conv)

        return PhaseResult(
            success=True,
            message=response,
            data={
                "files": file_diffs,
                "conversation": updated_conv,
            },
        )

    # ── Public API (called from web layer) ──

    def load_conversation(self) -> list[dict]:
        """Load persisted conversation from JSON file."""
        return self._load_conversation_from(self._arch_conv_path())

    def clear_conversation(self) -> None:
        """Clear persisted conversation."""
        self._clear_conversation_at(self._arch_conv_path())

    def apply_file(self, filepath: str, content: str) -> PhaseResult:
        """Apply a single proposed file change to disk."""
        result = self._apply_file_to_disk(filepath, content)
        if result.success:
            self._write_apply_log_entry(self._arch_fix_log_path(), filepath)
        return result

    # ── Path helpers ──

    def _arch_conv_path(self) -> Path:
        return self.artifacts.skaro / "architecture" / "fix-conversation.json"

    def _arch_fix_log_path(self) -> Path:
        return self.artifacts.skaro / "architecture" / ARCH_FIX_LOG_FILENAME
