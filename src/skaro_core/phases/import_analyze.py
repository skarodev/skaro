"""Import Analyze phase: analyze an existing repository and generate Skaro artifacts.

This phase is invoked during ``skaro init`` when the user chooses option B
(automatic analysis).  It:
  1. Scans the repository via RepoScanner.
  2. LLM Call 1: generates constitution.md from code.
  3. LLM Call 2: generates architecture.md (with constitution as context).
  4. LLM Call 3: generates completed-work.md (inventory of existing code).
  5. Creates a default "backlog" milestone so the user can start creating tasks immediately.
  6. Records import metadata in state.yaml.

The completed-work.md document ensures that subsequent phases (especially
DevPlan) are aware of what is already implemented and do not plan redundant
work.

Invariants are NOT generated during import. They are created when the user
runs Architecture Review (same as in the normal pipeline).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from skaro_core.phases.base import BasePhase, PhaseResult
from skaro_core.phases.repo_scan import RepoScanner

# Default milestone created after import so the user can work immediately.
_DEFAULT_MILESTONE = "backlog"
_DEFAULT_MILESTONE_TITLE = "Backlog"
_DEFAULT_MILESTONE_DESC = (
    "Default milestone created during project import. "
    "Add tasks here to start working on the project immediately."
)

# Per-call token limits — much lower than the old single-call flow
# because each call produces a single focused document.
_CONSTITUTION_TOKEN_LIMITS: dict[str, int] = {
    "anthropic": 16_384,
    "openai": 16_384,
    "groq": 8_192,
    "ollama": 16_384,
}

_ARCHITECTURE_TOKEN_LIMITS: dict[str, int] = {
    "anthropic": 32_768,
    "openai": 32_768,
    "groq": 16_384,
    "ollama": 32_768,
}

_COMPLETED_WORK_TOKEN_LIMITS: dict[str, int] = {
    "anthropic": 16_384,
    "openai": 16_384,
    "groq": 8_192,
    "ollama": 16_384,
}


class ImportAnalyzePhase(BasePhase):
    """Analyze an existing repository and generate Skaro project artifacts."""

    phase_name = "import_analyze"

    async def run(self, task: str | None = None, **kwargs: Any) -> PhaseResult:
        """Run the full import flow.

        Kwargs:
            project_name (str): Human-readable project name.
            source_commit (str): Git HEAD commit hash at import time (optional).
        """
        project_name: str = (
            kwargs.get("project_name")
            or self.config.project_name
            or self.artifacts.root.name
        )
        source_commit: str = kwargs.get("source_commit", "")

        # ── 1. Scan repository ───────────────────────────────────────────
        scanner = RepoScanner(
            self.artifacts.root,
            token_limit=self.config.import_config.token_limit,
            max_file_size=self.config.import_config.max_file_size,
        )
        scan = await asyncio.to_thread(scanner.scan)

        tree_text = scan.format_tree()
        files_text = scan.format_files()

        # ── 2. LLM Call 1: Constitution ──────────────────────────────────
        constitution = await self._generate_constitution(
            project_name, tree_text, files_text
        )
        if not constitution.strip():
            return PhaseResult(
                success=False,
                message="LLM returned empty constitution. Check your API key and model settings.",
            )

        # Write constitution immediately so it's saved even if call 2 fails
        am = self.artifacts
        am.constitution_path.parent.mkdir(parents=True, exist_ok=True)

        # Strip code fences if the LLM wrapped the constitution
        from skaro_core.phases._import_parser import _unwrap_fenced
        constitution = _unwrap_fenced(constitution)

        am.constitution_path.write_text(constitution, encoding="utf-8")
        created: list[str] = [str(am.constitution_path)]

        # ── 3. LLM Call 2: Architecture + Invariants ────────────────────
        # Pause to respect rate limits (input tokens per minute).
        # Call 1 consumed most of the budget; give the provider time to reset.
        await asyncio.sleep(5)

        architecture = await self._generate_architecture(
            project_name, tree_text, constitution
        )
        if not architecture.strip():
            return PhaseResult(
                success=False,
                message=(
                    "LLM returned empty architecture. "
                    "Constitution was generated successfully and saved."
                ),
                artifacts_created=created,
            )

        # Write architecture
        am.architecture_path.parent.mkdir(parents=True, exist_ok=True)
        am.architecture_path.write_text(architecture, encoding="utf-8")
        created.append(str(am.architecture_path))

        # ── 3.5. LLM Call 3: Completed Work ──────────────────────────────
        # Generates an inventory of what is already implemented so that
        # DevPlan and other phases do not plan redundant work.
        await asyncio.sleep(5)

        completed_work = await self._generate_completed_work(
            project_name, tree_text, files_text, constitution, architecture
        )

        if completed_work.strip():
            from skaro_core.phases._import_parser import _unwrap_fenced
            completed_work = _unwrap_fenced(completed_work)

            cw_path = am.skaro / "docs" / "completed-work.md"
            cw_path.parent.mkdir(parents=True, exist_ok=True)
            cw_path.write_text(completed_work, encoding="utf-8")
            created.append(str(cw_path))

        # ── 4. Create default milestone ──────────────────────────────────
        if not am.milestone_exists(_DEFAULT_MILESTONE):
            am.create_milestone(
                _DEFAULT_MILESTONE,
                title=_DEFAULT_MILESTONE_TITLE,
                description=_DEFAULT_MILESTONE_DESC,
            )
            created.append(f"milestones/{_DEFAULT_MILESTONE}/milestone.md")

        # ── 5. Record import state ───────────────────────────────────────
        am.mark_imported(mode="auto", source_commit=source_commit)

        return PhaseResult(
            success=True,
            message=(
                f"Import complete. Constitution, architecture, and completed work generated. "
                f"Default milestone '{_DEFAULT_MILESTONE}' created — "
                f"you can start adding tasks."
            ),
            artifacts_created=created,
            data={
                "analysis": {
                    "constitution": constitution,
                    "architecture": architecture,
                    "completed_work": completed_work if completed_work.strip() else "",
                },
                "scan": {
                    "files_included": len(scan.files),
                    "files_skipped": len(scan.skipped_paths),
                    "sampled": scan.sampled,
                    "estimated_tokens": scan.estimated_tokens,
                },
                "default_milestone": _DEFAULT_MILESTONE,
            },
        )

    # ── LLM call helpers ─────────────────────────────────────────────────

    async def _generate_constitution(
        self, project_name: str, tree: str, files: str
    ) -> str:
        """LLM Call 1: Generate constitution from repo contents."""
        prompt_template = self._load_prompt_template("repo-constitution")
        if not prompt_template:
            return ""

        prompt = (
            prompt_template
            .replace("{project_name}", project_name)
            .replace("{tree}", tree)
            .replace("{files}", files)
        )

        messages = self._build_messages_no_constitution(prompt)
        return await self._llm_collect_with_limit(
            messages, _CONSTITUTION_TOKEN_LIMITS
        )

    async def _generate_architecture(
        self,
        project_name: str,
        tree: str,
        constitution: str,
    ) -> str:
        """LLM Call 2: Generate architecture.

        Uses only tree + constitution (no source files) to stay within
        input token rate limits. Constitution already contains all the
        detail about stack, patterns, and standards extracted from code.
        """
        prompt_template = self._load_prompt_template("repo-architecture")
        if not prompt_template:
            return ""

        prompt = (
            prompt_template
            .replace("{project_name}", project_name)
            .replace("{tree}", tree)
            .replace("{constitution}", constitution)
        )

        messages = self._build_messages_no_constitution(prompt)
        response = await self._llm_collect_with_limit(
            messages, _ARCHITECTURE_TOKEN_LIMITS
        )

        # Strip code fences if the LLM wrapped the response
        from skaro_core.phases._import_parser import _unwrap_fenced
        return _unwrap_fenced(response.strip())

    async def _generate_completed_work(
        self,
        project_name: str,
        tree: str,
        files: str,
        constitution: str,
        architecture: str,
    ) -> str:
        """LLM Call 3: Generate completed-work.md — inventory of existing code.

        Uses constitution + architecture (already generated) plus tree and
        source files to produce a detailed list of what is already implemented.
        This document is consumed by DevPlan and other phases via the system
        message (see BasePhase._build_system_message).
        """
        prompt_template = self._load_prompt_template("repo-completed-work")
        if not prompt_template:
            return ""

        prompt = (
            prompt_template
            .replace("{project_name}", project_name)
            .replace("{tree}", tree)
            .replace("{files}", files)
            .replace("{constitution}", constitution)
            .replace("{architecture}", architecture)
        )

        messages = self._build_messages_no_constitution(prompt)
        return await self._llm_collect_with_limit(
            messages, _COMPLETED_WORK_TOKEN_LIMITS
        )

    # ── Private helpers ──────────────────────────────────────────────────

    def _build_messages_no_constitution(self, user_content: str) -> list:
        """Build messages with language instruction only — no constitution in system yet."""
        from skaro_core.llm.base import LLMMessage

        lang = self.config.lang
        lang_name = self._LANG_NAMES.get(lang, lang)
        system = (
            f"# LANGUAGE\n\n"
            f"IMPORTANT: You MUST respond entirely in {lang_name}. "
            f"All section content, descriptions, and comments must be in {lang_name}."
        )

        if lang != "en":
            user_content += f"\n\n---\nReminder: respond entirely in {lang_name}."

        return [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=user_content),
        ]

    async def _llm_collect_with_limit(
        self, messages: list, limits: dict[str, int],
        *, max_retries: int = 3,
    ) -> str:
        """Stream-collect LLM response with a per-call max_tokens limit.

        Retries with exponential backoff on rate-limit (retriable) errors.
        """
        original_max = self.llm.config.max_tokens
        provider = self.llm.config.provider.lower()
        self.llm.config.max_tokens = max(
            original_max,
            limits.get(provider, 16_384),
        )
        try:
            from skaro_core.llm.base import LLMError

            for attempt in range(max_retries + 1):
                try:
                    return await self._stream_collect(messages)
                except LLMError as exc:
                    if exc.retriable and attempt < max_retries:
                        wait = 30 * (2 ** attempt)  # 30s, 60s, 120s
                        if self.on_stream_chunk:
                            self.on_stream_chunk(
                                f"\n⏳ Rate limited. Retrying in {wait}s "
                                f"(attempt {attempt + 2}/{max_retries + 1})...\n"
                            )
                        await asyncio.sleep(wait)
                    else:
                        raise
            return ""  # unreachable, but satisfies type checker
        finally:
            self.llm.config.max_tokens = original_max
