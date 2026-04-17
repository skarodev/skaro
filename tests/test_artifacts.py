"""Tests for ArtifactManager."""

import tempfile
from pathlib import Path

import pytest

from skaro_core.artifacts import ArtifactManager, Phase, Status


@pytest.fixture
def project_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def am(project_dir):
    manager = ArtifactManager(project_dir)
    manager.init_project()
    return manager


class TestInit:
    def test_init_creates_skaro_dir(self, project_dir):
        am = ArtifactManager(project_dir)
        assert not am.is_initialized
        am.init_project()
        assert am.is_initialized

    def test_init_creates_subdirectories(self, am):
        skaro = am.skaro
        assert (skaro / "architecture").is_dir()
        assert (skaro / "milestones").is_dir()
        assert (skaro / "docs").is_dir()
        assert (skaro / "ops").is_dir()
        assert (skaro / "templates").is_dir()

    def test_init_copies_templates(self, am):
        templates = am.skaro / "templates"
        assert templates.is_dir()


class TestConstitution:
    def test_no_constitution_initially(self, am):
        assert not am.has_constitution

    def test_create_constitution(self, am):
        path = am.create_constitution()
        assert path.exists()

    def test_validate_empty_constitution(self, am):
        am.create_constitution()
        checks = am.validate_constitution()
        assert isinstance(checks, dict)
        assert "stack" in checks

    def test_validate_filled_constitution(self, am):
        am.constitution_path.write_text(
            "# Constitution\n\n"
            "## Stack\n- Language: Python 3.12\n\n"
            "## Coding Standards\n- Linter: ruff\n\n"
            "## Testing\n- Coverage: 80%\n\n"
            "## Constraints\n- Infra: Docker\n\n"
            "## Security\n- Authorization: JWT\n\n"
            "## LLM Rules\n- No stubs\n- AI_NOTES required\n",
            encoding="utf-8",
        )
        checks = am.validate_constitution()
        assert all(checks.values()), f"Failed checks: {checks}"


class TestMilestones:
    def test_no_milestones_initially(self, am):
        assert am.list_milestones() == []

    def test_create_milestone(self, am):
        mdir = am.create_milestone("01-foundation", title="Foundation")
        assert mdir.is_dir()
        assert (mdir / "milestone.md").exists()

    def test_list_milestones(self, am):
        am.create_milestone("01-foundation")
        am.create_milestone("02-mvp")
        assert am.list_milestones() == ["01-foundation", "02-mvp"]

    def test_milestone_exists(self, am):
        assert not am.milestone_exists("01-foundation")
        am.create_milestone("01-foundation")
        assert am.milestone_exists("01-foundation")

    def test_read_milestone_info(self, am):
        am.create_milestone("01-foundation", title="Foundation", description="Core setup")
        info = am.read_milestone_info("01-foundation")
        assert "Foundation" in info
        assert "Core setup" in info


class TestTasks:
    def test_no_tasks_initially(self, am):
        am.create_milestone("01-foundation")
        assert am.list_tasks("01-foundation") == []

    def test_create_task(self, am):
        am.create_milestone("01-foundation")
        tdir = am.create_task("01-foundation", "project-setup")
        assert tdir.is_dir()
        assert (tdir / "spec.md").exists()
        assert (tdir / "stages").is_dir()

    def test_list_tasks(self, am):
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "project-setup")
        am.create_task("01-foundation", "core-models")
        assert am.list_tasks("01-foundation") == ["core-models", "project-setup"]

    def test_list_all_tasks(self, am):
        am.create_milestone("01-foundation")
        am.create_milestone("02-mvp")
        am.create_task("01-foundation", "setup")
        am.create_task("02-mvp", "auth")
        all_tasks = am.list_all_tasks()
        assert ("01-foundation", "setup") in all_tasks
        assert ("02-mvp", "auth") in all_tasks

    def test_task_exists(self, am):
        am.create_milestone("01-foundation")
        assert not am.task_exists("01-foundation", "setup")
        am.create_task("01-foundation", "setup")
        assert am.task_exists("01-foundation", "setup")

    def test_read_write_task_file(self, am):
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")
        am.write_task_file("01-foundation", "auth", "clarifications.md", "# Clarify\n\nQ1: test")
        content = am.read_task_file("01-foundation", "auth", "clarifications.md")
        assert "Q1: test" in content


class TestTaskLookup:
    """Test resolve_task and find_* methods that search by slug."""

    def test_resolve_task(self, am):
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")
        ms, task = am.resolve_task("auth")
        assert ms == "01-foundation"
        assert task == "auth"

    def test_resolve_task_not_found(self, am):
        with pytest.raises(FileNotFoundError):
            am.resolve_task("nonexistent")

    def test_resolve_task_safe(self, am):
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")
        assert am.resolve_task_safe("auth") == ("01-foundation", "auth")
        assert am.resolve_task_safe("nonexistent") is None

    def test_find_task_exists(self, am):
        am.create_milestone("01-foundation")
        assert not am.find_task_exists("auth")
        am.create_task("01-foundation", "auth")
        assert am.find_task_exists("auth")

    def test_find_and_read_write_task_file(self, am):
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")
        am.find_and_write_task_file("auth", "notes.md", "hello")
        content = am.find_and_read_task_file("auth", "notes.md")
        assert content == "hello"

    def test_find_task_state(self, am):
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")
        state = am.find_task_state("auth")
        assert state.name == "auth"
        assert state.milestone == "01-foundation"

    def test_resolve_task_by_ref_with_duplicate_slugs(self, am):
        am.create_milestone("01-foundation")
        am.create_milestone("02-mvp")
        am.create_task("01-foundation", "auth")
        am.create_task("02-mvp", "auth")

        assert am.resolve_task("01-foundation::auth") == ("01-foundation", "auth")
        assert am.resolve_task("02-mvp::auth") == ("02-mvp", "auth")

    def test_task_state_exposes_unique_ref(self, am):
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")

        state = am.get_task_state("01-foundation", "auth")

        assert state.ref == "01-foundation::auth"


class TestStages:
    def test_no_completed_stages_initially(self, am):
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")
        assert am.get_completed_stages("01-foundation", "auth") == []

    def test_create_stage_notes(self, am):
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")
        path = am.create_stage_notes("01-foundation", "auth", 1, "# AI_NOTES\n\nTest")
        assert path.exists()
        assert am.get_completed_stages("01-foundation", "auth") == [1]

    def test_multiple_stages(self, am):
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")
        am.create_stage_notes("01-foundation", "auth", 1, "Stage 1")
        am.create_stage_notes("01-foundation", "auth", 2, "Stage 2")
        assert am.get_completed_stages("01-foundation", "auth") == [1, 2]

    def test_find_completed_stages(self, am):
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")
        am.create_stage_notes("01-foundation", "auth", 1, "Stage 1")
        assert am.find_completed_stages("auth") == [1]


class TestTaskState:
    def test_initial_state(self, am):
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")
        state = am.get_task_state("01-foundation", "auth")
        assert state.name == "auth"
        assert state.milestone == "01-foundation"
        assert state.current_stage == 0
        assert state.phases[Phase.CLARIFY] == Status.NOT_STARTED

    def test_state_with_clarify_done(self, am):
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")
        am.write_task_file("01-foundation", "auth", "clarifications.md", "done")
        state = am.get_task_state("01-foundation", "auth")
        assert state.phases[Phase.CLARIFY] == Status.COMPLETE

    def test_state_with_plan(self, am):
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")
        am.write_task_file("01-foundation", "auth", "plan.md", "## Stage 1\n## Stage 2")
        state = am.get_task_state("01-foundation", "auth")
        assert state.phases[Phase.PLAN] == Status.COMPLETE
        assert state.total_stages == 2


class TestProjectState:
    def test_project_state(self, am):
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")
        am.create_task("01-foundation", "payments")
        state = am.get_project_state()
        assert state.root == am.root
        assert len(state.tasks) == 2
        # Backward compat alias (deprecated, still works)
        assert len(state.features) == 2

    def test_ensure_task_creates_milestone_and_task(self, am):
        """ensure_task auto-creates milestone if needed."""
        am.ensure_task("setup", milestone="01-foundation")
        assert am.milestone_exists("01-foundation")
        assert am.task_exists("01-foundation", "setup")


class TestADR:
    def test_create_adr(self, am):
        path = am.create_adr(1, "Use PostgreSQL")
        assert path.exists()
        assert "ADR-001" in path.read_text(encoding="utf-8")

    def test_list_adrs(self, am):
        am.create_adr(1, "Use PostgreSQL")
        am.create_adr(2, "Event Sourcing")
        adrs = am.list_adrs()
        assert len(adrs) == 2


class TestGitignore:

    def test_init_creates_gitignore(self, project_dir):
        """init_project creates .gitignore with Skaro section."""
        am = ArtifactManager(project_dir)
        am.init_project()

        gitignore = project_dir / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text(encoding="utf-8")
        assert "secrets.yaml" in content
        assert "token_usage.yaml" in content
        assert "usage_log.jsonl" in content
        assert "Do NOT delete" in content

    def test_init_appends_to_existing_gitignore(self, project_dir):
        """Skaro section is appended without touching existing content."""
        gitignore = project_dir / ".gitignore"
        gitignore.write_text("node_modules/\n*.pyc\n", encoding="utf-8")

        am = ArtifactManager(project_dir)
        am.init_project()

        content = gitignore.read_text(encoding="utf-8")
        assert content.startswith("node_modules/")
        assert "secrets.yaml" in content

    def test_init_idempotent_gitignore(self, project_dir):
        """Running init twice does not duplicate the Skaro section."""
        am = ArtifactManager(project_dir)
        am.init_project()
        am.init_project()

        content = (project_dir / ".gitignore").read_text(encoding="utf-8")
        assert content.count("secrets.yaml") == 1
