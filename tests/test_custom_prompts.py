"""Tests for custom prompt loading (.skaro/prompts/ override)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from skaro_core.config import LLMConfig, SkaroConfig
from skaro_core.phases.base import BasePhase, PhaseResult


# ── Concrete subclass for testing ──────────────────────

class _StubPhase(BasePhase):
    """Minimal concrete phase for unit-testing base methods."""

    phase_name = "stub"

    async def run(self, task: str | None = None, **kwargs) -> PhaseResult:
        return PhaseResult(success=True, message="ok")


def _make_phase(project_root: Path) -> _StubPhase:
    cfg = SkaroConfig(
        llm=LLMConfig(provider="mock", model="m", api_key_env="X"),
    )
    return _StubPhase(project_root=project_root, config=cfg)


# ── Tests ──────────────────────────────────────────────

class TestLoadPromptTemplate:
    """Verify the .skaro/prompts/ → built-in fallback chain."""

    def test_builtin_prompt_loaded(self, tmp_path: Path):
        """Built-in prompts are returned when no override exists."""
        phase = _make_phase(tmp_path)
        # "clarify" is a known built-in prompt
        result = phase._load_prompt_template("clarify")
        assert result, "Expected built-in clarify.md to be loaded"

    def test_override_takes_precedence(self, tmp_path: Path):
        """A file in .skaro/prompts/ overrides the built-in."""
        override_dir = tmp_path / ".skaro" / "prompts"
        override_dir.mkdir(parents=True)
        (override_dir / "clarify.md").write_text(
            "CUSTOM CLARIFY PROMPT", encoding="utf-8",
        )

        phase = _make_phase(tmp_path)
        result = phase._load_prompt_template("clarify")
        assert result == "CUSTOM CLARIFY PROMPT"

    def test_fallback_when_override_missing(self, tmp_path: Path):
        """.skaro/prompts/ exists but doesn't contain the file → built-in used."""
        override_dir = tmp_path / ".skaro" / "prompts"
        override_dir.mkdir(parents=True)
        # No clarify.md in override dir

        phase = _make_phase(tmp_path)
        result = phase._load_prompt_template("clarify")
        # Should get the built-in content
        assert result, "Expected built-in clarify.md as fallback"
        assert "CUSTOM" not in result

    def test_nonexistent_prompt_returns_empty(self, tmp_path: Path):
        """Unknown prompt name → empty string (no crash)."""
        phase = _make_phase(tmp_path)
        result = phase._load_prompt_template("nonexistent-prompt-xyz")
        assert result == ""

    def test_no_project_root(self):
        """project_root=None → only built-in lookup, no crash."""
        cfg = SkaroConfig(
            llm=LLMConfig(provider="mock", model="m", api_key_env="X"),
        )
        phase = _StubPhase(project_root=None, config=cfg)
        result = phase._load_prompt_template("clarify")
        assert result, "Built-in should still load when project_root is None"
