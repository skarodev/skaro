"""Tests for ArchitecturePhase and DevPlanPhase with mock LLM.

LLM calls are mocked — tests verify data flow, artifact creation, and precondition checks.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import AsyncIterator
from unittest.mock import patch

import pytest

from skaro_core.artifacts import ArtifactManager
from skaro_core.config import LLMConfig
from skaro_core.llm.base import BaseLLMAdapter, LLMMessage, LLMResponse


# ═══════════════════════════════════════════════════
# Mock
# ═══════════════════════════════════════════════════


class MockLLMAdapter(BaseLLMAdapter):
    def __init__(self, response_text: str = "mock"):
        config = LLMConfig(provider="mock", model="mock-1", api_key_env="MOCK_KEY")
        super().__init__(config)
        self.response_text = response_text
        self.calls: list[list[LLMMessage]] = []

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        self.calls.append(messages)
        return LLMResponse(
            content=self.response_text,
            model="mock-1",
            usage={"input_tokens": 100, "output_tokens": 50},
        )

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        self.calls.append(messages)
        words = self.response_text.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
        self.last_usage = {"input_tokens": 100, "output_tokens": 50}


# ═══════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════


@pytest.fixture
def project_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def init_project(project_dir):
    am = ArtifactManager(project_dir)
    am.init_project()
    return project_dir


@pytest.fixture
def project_with_arch(init_project):
    """Project with filled constitution + architecture (reviewed)."""
    am = ArtifactManager(init_project)
    am.write_constitution(
        "# Constitution\n\n"
        "## Stack\nPython 3.12, FastAPI, PostgreSQL, Redis\n\n"
        "## Coding Standards\nlinter: ruff, formatter: black\n\n"
        "## Testing\ncoverage 80%, pytest, pytest-asyncio\n\n"
        "## Constraints\ninfra: Docker, Kubernetes\n\n"
        "## Security\nauthorization: JWT, bcrypt for passwords\n\n"
        "## LLM Rules\nai_notes in every stage, no hallucinated imports\n"
    )
    am.write_architecture(
        "# Architecture\n\n"
        "## Overview\nMonolithic FastAPI application with layered architecture.\n\n"
        "## Components\n"
        "- API layer: FastAPI routers with Pydantic validation\n"
        "- Service layer: business logic, no framework dependencies\n"
        "- Data layer: SQLAlchemy models, Alembic migrations\n"
        "- Infrastructure: Docker, CI/CD with GitHub Actions\n"
    )
    am.mark_architecture_reviewed()
    return init_project


# ═══════════════════════════════════════════════════
# ArchitecturePhase
# ═══════════════════════════════════════════════════


class TestArchitecturePhase:

    @pytest.mark.asyncio
    async def test_review_splits_response(self, init_project):
        mock_response = (
            "## Review\n"
            "The architecture is solid but missing error handling.\n\n"
            "## Proposed Architecture\n"
            "# Architecture\n\n"
            "## Overview\nMonolithic app with error boundaries\n"
        )
        mock_adapter = MockLLMAdapter(mock_response)

        with patch("skaro_core.phases.base.create_llm_adapter", return_value=mock_adapter):
            from skaro_core.phases.architecture import ArchitecturePhase
            phase = ArchitecturePhase(project_root=init_project)
            result = await phase.run(
                architecture_draft="# Arch\nMonolithic app",
                domain_description="Task management",
            )

        assert result.success is True
        assert "error handling" in result.message
        assert "error boundaries" in result.data["proposed_architecture"]

    @pytest.mark.asyncio
    async def test_review_persists(self, init_project):
        mock_adapter = MockLLMAdapter("## Review\nLooks good\n\n## Proposed Architecture\nNo changes")

        with patch("skaro_core.phases.base.create_llm_adapter", return_value=mock_adapter):
            from skaro_core.phases.architecture import ArchitecturePhase
            phase = ArchitecturePhase(project_root=init_project)
            await phase.run(architecture_draft="# Arch\nDraft")

        am = ArtifactManager(init_project)
        review = am.read_architecture_review()
        assert "Looks good" in review

    @pytest.mark.asyncio
    async def test_requires_draft(self, init_project):
        with patch("skaro_core.phases.base.create_llm_adapter"):
            from skaro_core.phases.architecture import ArchitecturePhase
            phase = ArchitecturePhase(project_root=init_project)
            result = await phase.run(architecture_draft="")

        assert result.success is False
        assert "required" in result.message.lower()

    @pytest.mark.asyncio
    async def test_no_proposed_section(self, init_project):
        """LLM didn't follow format — entire response is review."""
        mock_adapter = MockLLMAdapter("This architecture needs a complete rewrite.")

        with patch("skaro_core.phases.base.create_llm_adapter", return_value=mock_adapter):
            from skaro_core.phases.architecture import ArchitecturePhase
            phase = ArchitecturePhase(project_root=init_project)
            result = await phase.run(architecture_draft="# Arch\nBad draft")

        assert result.success is True
        assert "complete rewrite" in result.message
        assert result.data["proposed_architecture"] == ""

    def test_split_response_static(self):
        from skaro_core.phases.architecture import ArchitecturePhase

        review, proposed = ArchitecturePhase._split_response(
            "Review text\n\n## Proposed Architecture\nNew arch"
        )
        assert review == "Review text"
        assert proposed == "New arch"

    def test_split_response_no_proposed(self):
        from skaro_core.phases.architecture import ArchitecturePhase

        review, proposed = ArchitecturePhase._split_response("Just review, no sections")
        assert review == "Just review, no sections"
        assert proposed == ""


# ═══════════════════════════════════════════════════
# DevPlanPhase
# ═══════════════════════════════════════════════════


class TestDevPlanPhase:

    @pytest.mark.asyncio
    async def test_run_creates_devplan(self, project_with_arch):
        mock_response = '''```json
[
  {
    "milestone_slug": "01-foundation",
    "milestone_title": "Foundation",
    "description": "Base setup",
    "tasks": [
      {"name": "project-setup", "description": "Init", "priority": 1, "spec": "# Setup"}
    ]
  }
]
```'''
        mock_adapter = MockLLMAdapter(mock_response)

        with patch("skaro_core.phases.base.create_llm_adapter", return_value=mock_adapter):
            from skaro_core.phases.devplan import DevPlanPhase
            phase = DevPlanPhase(project_root=project_with_arch)
            result = await phase.run()

        assert result.success is True
        assert "milestones" in result.data
        assert len(result.data["milestones"]) == 1

        am = ArtifactManager(project_with_arch)
        assert am.has_devplan
        devplan = am.read_devplan()
        assert "Foundation" in devplan

    @pytest.mark.asyncio
    async def test_run_requires_constitution(self, init_project):
        am = ArtifactManager(init_project)
        # Clear template constitution so precondition fires
        am.write_constitution("")

        with patch("skaro_core.phases.base.create_llm_adapter"):
            from skaro_core.phases.devplan import DevPlanPhase
            phase = DevPlanPhase(project_root=init_project)
            result = await phase.run()

        assert result.success is False
        assert "constitution" in result.message.lower()

    @pytest.mark.asyncio
    async def test_run_requires_architecture_review(self, init_project):
        am = ArtifactManager(init_project)
        am.write_constitution("# Constitution\n\n" + "x" * 200)
        am.write_architecture("# Architecture\n\n" + "x" * 200)
        # NOT reviewed

        with patch("skaro_core.phases.base.create_llm_adapter"):
            from skaro_core.phases.devplan import DevPlanPhase
            phase = DevPlanPhase(project_root=init_project)
            result = await phase.run()

        assert result.success is False
        assert "approved" in result.message.lower() or "review" in result.message.lower()

    @pytest.mark.asyncio
    async def test_confirm_plan_creates_directories(self, project_with_arch):
        from skaro_core.phases.devplan import DevPlanPhase
        phase = DevPlanPhase(project_root=project_with_arch)

        # Write a devplan first
        am = ArtifactManager(project_with_arch)
        am.write_devplan("# Dev Plan\n## Change Log\n")

        milestones = [
            {
                "milestone_slug": "01-core",
                "milestone_title": "Core",
                "description": "Core features",
                "tasks": [
                    {"name": "auth", "spec": "# Auth\nJWT auth"},
                    {"name": "database", "spec": "# DB\nPostgreSQL setup"},
                ],
            }
        ]
        result = await phase.confirm_plan(milestones)

        assert result.success is True
        assert len(result.data["tasks_created"]) == 2
        assert am.task_exists("01-core", "auth")
        assert am.task_exists("01-core", "database")

        spec = am.read_task_file("01-core", "auth", "spec.md")
        assert "JWT auth" in spec

        # Verify task order is preserved (not alphabetical)
        order = am.get_task_order("01-core")
        assert order == ["auth", "database"], f"Expected LLM order, got {order}"
        assert am.list_tasks("01-core") == ["auth", "database"]

    @pytest.mark.asyncio
    async def test_confirm_plan_updates_changelog(self, project_with_arch):
        from skaro_core.phases.devplan import DevPlanPhase
        phase = DevPlanPhase(project_root=project_with_arch)

        am = ArtifactManager(project_with_arch)
        am.write_devplan("# Dev Plan\n\n## Change Log\n")

        milestones = [
            {
                "milestone_slug": "01-x",
                "milestone_title": "X",
                "tasks": [{"name": "task-a", "spec": ""}],
            }
        ]
        await phase.confirm_plan(milestones)

        devplan = am.read_devplan()
        assert "Confirmed 1 tasks" in devplan

    @pytest.mark.asyncio
    async def test_update_requires_existing_devplan(self, project_with_arch):
        with patch("skaro_core.phases.base.create_llm_adapter"):
            from skaro_core.phases.devplan import DevPlanPhase
            phase = DevPlanPhase(project_root=project_with_arch)
            result = await phase.update(user_guidance="Add logging")

        assert result.success is False
        assert "no devplan" in result.message.lower()

    @pytest.mark.asyncio
    async def test_confirm_update_creates_new_tasks(self, project_with_arch):
        from skaro_core.phases.devplan import DevPlanPhase
        phase = DevPlanPhase(project_root=project_with_arch)

        am = ArtifactManager(project_with_arch)
        am.write_devplan("# Dev Plan\n## Existing")

        result = await phase.confirm_update(
            updated_devplan="# Dev Plan\n## Updated",
            new_milestones=[
                {
                    "milestone_slug": "02-new",
                    "milestone_title": "New",
                    "tasks": [{"name": "logs", "spec": "# Logging"}],
                }
            ],
        )

        assert result.success is True
        assert am.task_exists("02-new", "logs")
        devplan = am.read_devplan()
        assert "Updated" in devplan
