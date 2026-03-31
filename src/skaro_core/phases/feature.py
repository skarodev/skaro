"""Feature phase: conversational feature planning and decomposition.

Provides LLM with full project context and lets the user describe a new feature.
The LLM iterates via clarifying questions, then generates a structured JSON
proposal that the frontend renders as a reviewable card.  On user confirmation
the proposal is materialized into tasks, ADR, and plan.md.
"""

from __future__ import annotations

import asyncio
from typing import Any

from skaro_core.phases._fix_base import ConversationalFixBase
from skaro_core.phases.base import PhaseResult


class FeaturePhase(ConversationalFixBase):
    phase_name = "feature"

    _FIX_ROLE = (
        "You are a senior architect and tech lead helping plan a NEW FEATURE "
        "for an existing project.\n"
        "The user will describe a feature they want to add.\n"
        "Your job is to understand, ask clarifying questions, then generate "
        "a structured proposal."
    )

    async def run(self, task: str | None = None, **kwargs: Any) -> PhaseResult:
        """Process a message in the feature planning conversation.

        kwargs:
            feature_slug: str — feature slug (for conversation path)
            message: str — user message
            conversation: list[dict] — previous turns
        """
        feature_slug: str = kwargs.get("feature_slug", "")
        user_message: str = kwargs.get("message", "")
        conversation: list[dict] = kwargs.get("conversation", [])
        scope_paths: list[str] = kwargs.get("scope_paths", [])

        if not user_message.strip():
            return PhaseResult(success=False, message="Message is required.")
        if not feature_slug:
            return PhaseResult(success=False, message="Feature slug is required.")

        # ── Build context ─────────────────────────────────
        cacheable_context: dict[str, str] = {}
        extra_context: dict[str, str] = {}

        architecture = self.artifacts.read_architecture()
        if architecture.strip():
            cacheable_context["Architecture"] = architecture
        invariants = self.artifacts.read_invariants()
        if invariants.strip():
            cacheable_context["Architectural Invariants"] = invariants

        adr_index = self.artifacts.read_adr_index()
        if adr_index:
            cacheable_context["Existing ADRs (accepted)"] = adr_index

        devplan = self.artifacts.read_devplan()
        if devplan.strip():
            extra_context["Current Development Plan"] = devplan

        tasks_state = self._gather_tasks_state()
        if tasks_state:
            extra_context["Current Tasks State"] = tasks_state

        tree = await self._scan_project_tree_async()
        if tree:
            extra_context["Project File Tree"] = tree

        from skaro_core.context import SmartContextBuilder

        builder = SmartContextBuilder(
            self.artifacts.root,
            always_include=self.config.context_always_include,
        )
        smart = await asyncio.to_thread(
            builder.build,
            stage_section=user_message,
            max_full_files=0,
        )
        if smart.signatures:
            cacheable_context["Project API Index"] = smart.signatures

        # Scope files: user-selected files (full code)
        if scope_paths:
            scope_code = await asyncio.to_thread(self._read_scope_files, scope_paths)
            if scope_code:
                extra_context["Selected source files (full code)"] = scope_code

        # ── Build messages ────────────────────────────────
        from skaro_core.llm.base import LLMMessage

        prompt_template = self._load_prompt_template("feature-analyze") or ""

        system = self._build_system_message()
        system += (
            "\n\n# YOUR ROLE\n"
            f"{self._FIX_ROLE}\n\n"
            f"{prompt_template}\n"
        )

        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=system, cache=True)
        ]

        if cacheable_context:
            ctx_parts = [
                f"## {label}\n\n{content}"
                for label, content in cacheable_context.items()
                if content.strip()
            ]
            if ctx_parts:
                messages.append(LLMMessage(
                    role="user", content="\n\n---\n\n".join(ctx_parts), cache=True,
                ))
                messages.append(LLMMessage(
                    role="assistant",
                    content="I've reviewed the project architecture, ADRs, and codebase. Ready to help plan a new feature.",
                ))

        if extra_context:
            ctx_parts = [
                f"## {label}\n\n{content}"
                for label, content in extra_context.items()
                if content.strip()
            ]
            if ctx_parts:
                messages.append(LLMMessage(
                    role="user", content="\n\n---\n\n".join(ctx_parts),
                ))
                messages.append(LLMMessage(
                    role="assistant",
                    content="I've reviewed the current devplan and task states. Ready to discuss the new feature.",
                ))

        for turn in conversation:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content.strip():
                messages.append(LLMMessage(role=role, content=content))

        final_message = user_message
        if self.config.lang != "en":
            final_message += f"\n\n---\nReminder: {self._lang_instruction()}"
        messages.append(LLMMessage(role="user", content=final_message))

        # ── LLM call ──────────────────────────────────────
        response_content = await self._stream_collect(messages, min_tokens=16384)

        updated_conversation = list(conversation) + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": response_content},
        ]

        # Persist
        conv_path = self.artifacts.feature_conversation_path(feature_slug)
        self._save_conversation_to(conv_path, updated_conversation)

        self._write_fix_log_entry(
            self.artifacts.feature_log_path(feature_slug),
            f"# Feature Log: {feature_slug}",
            user_message,
            response_content,
            {},
        )

        return PhaseResult(
            success=True,
            message=response_content,
            data={"conversation": updated_conversation},
        )

    # ── Conversation persistence ──────────────────────

    def load_conversation(self, feature_slug: str) -> list[dict]:
        return self._load_conversation_from(
            self.artifacts.feature_conversation_path(feature_slug)
        )

    def clear_conversation(self, feature_slug: str) -> None:
        self._clear_conversation_at(
            self.artifacts.feature_conversation_path(feature_slug)
        )

    # ── Confirm proposal (materialize) ────────────────

    def confirm_proposal(
        self,
        feature_slug: str,
        *,
        title: str,
        description: str,
        plan: str,
        tasks: list[dict[str, Any]],
        adr: dict[str, Any] | None = None,
    ) -> PhaseResult:
        """Materialize a confirmed feature proposal.

        Creates plan.md, tasks on disk, ADR if provided.
        Transitions feature from draft → planned.
        """
        am = self.artifacts

        # Update meta
        am.update_feature_meta(
            feature_slug,
            title=title,
            description=description,
            status="planned",
        )

        # Write plan
        if plan.strip():
            am.write_feature_plan(feature_slug, plan)

        # Create tasks
        from skaro_core.phases._devplan_parser import make_slug

        created_tasks: list[str] = []
        for task_data in tasks:
            name = task_data.get("name", "").strip()
            spec = task_data.get("spec", "").strip()
            milestone = task_data.get("milestone", "").strip()
            if not name or not milestone:
                continue

            slug = make_slug(name)

            if not am.milestone_exists(milestone):
                am.create_milestone(milestone)

            if not am.task_exists(milestone, slug):
                am.create_task(milestone, slug)
            if spec:
                am.write_task_file(milestone, slug, "spec.md", spec)

            am.link_task_to_feature(feature_slug, slug)
            created_tasks.append(f"{milestone}/{slug}")

            # Update task order
            existing_order = am.get_task_order(milestone)
            if slug not in existing_order:
                existing_order.append(slug)
                am.save_task_order(milestone, existing_order)

        # Create ADR if provided
        adr_number = None
        if adr and adr.get("title"):
            existing_adrs = am.list_adrs()
            adr_number = len(existing_adrs) + 1
            adr_path = am.create_adr(adr_number, adr["title"])
            if adr.get("content"):
                adr_path.write_text(adr["content"], encoding="utf-8")
            am.link_adr_to_feature(feature_slug, adr_number)

        return PhaseResult(
            success=True,
            message=f"Feature '{title}' created with {len(created_tasks)} tasks.",
            data={
                "tasks_created": created_tasks,
                "adr_number": adr_number,
            },
        )

    # ── Context helpers ───────────────────────────────

    def _gather_tasks_state(self) -> str:
        lines: list[str] = []
        for ms in self.artifacts.list_milestones():
            lines.append(f"### Milestone: {ms}")
            for task in self.artifacts.list_tasks(ms):
                state = self.artifacts.get_task_state(ms, task)
                phase = state.current_phase.value
                progress = state.progress_percent
                lines.append(f"  - {task}: phase={phase}, progress={progress}%")
        return "\n".join(lines) if lines else ""
