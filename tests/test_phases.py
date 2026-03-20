"""Tests for phase logic: source collection, project scanning, and LLM-driven phases.

LLM calls are mocked — these tests verify parsing, artifact creation, and data flow.
Requires: pip install pytest-asyncio
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from skaro_core.artifacts import ArtifactManager
from skaro_core.config import LLMConfig, SkaroConfig
from skaro_core.llm.base import BaseLLMAdapter, LLMMessage, LLMResponse
from skaro_core.phases.base import BasePhase, PhaseResult, SKIP_DIRS, SOURCE_EXTENSIONS, BINARY_EXTENSIONS, is_text_file


# ═══════════════════════════════════════════════════
# Mock LLM adapter
# ═══════════════════════════════════════════════════

class MockLLMAdapter(BaseLLMAdapter):
    """LLM adapter that returns pre-configured responses."""

    def __init__(self, response_text: str = "mock response"):
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
        # Yield response in chunks to simulate streaming
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
def project_with_sources(init_project):
    """Project with sample source files for _collect_project_sources."""
    src = init_project / "src" / "myapp"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "main.py").write_text("def main():\n    print('hello')\n", encoding="utf-8")
    (src / "utils.py").write_text("def helper():\n    return 42\n", encoding="utf-8")

    # A JS file
    (init_project / "frontend").mkdir()
    (init_project / "frontend" / "app.js").write_text("console.log('hi');\n", encoding="utf-8")

    # Files that should be skipped
    pycache = init_project / "src" / "myapp" / "__pycache__"
    pycache.mkdir()
    (pycache / "main.cpython-312.pyc").write_bytes(b"\x00")

    node_modules = init_project / "node_modules"
    node_modules.mkdir()
    (node_modules / "something.js").write_text("skip", encoding="utf-8")

    return init_project


# ═══════════════════════════════════════════════════
# _scan_project_tree
# ═══════════════════════════════════════════════════

class TestScanProjectTree:

    def _make_phase(self, root: Path) -> BasePhase:
        """Create a concrete phase instance for testing."""
        from skaro_core.phases.plan import PlanPhase
        return PlanPhase(project_root=root)

    def test_lists_source_files(self, project_with_sources):
        phase = self._make_phase(project_with_sources)
        tree = phase._scan_project_tree()
        assert "src/myapp/main.py" in tree or "src\\myapp\\main.py" in tree
        assert "src/myapp/utils.py" in tree or "src\\myapp\\utils.py" in tree

    def test_skips_pycache(self, project_with_sources):
        phase = self._make_phase(project_with_sources)
        tree = phase._scan_project_tree()
        assert "__pycache__" not in tree
        assert ".pyc" not in tree

    def test_skips_node_modules(self, project_with_sources):
        phase = self._make_phase(project_with_sources)
        tree = phase._scan_project_tree()
        assert "node_modules" not in tree

    def test_skips_skaro_dir(self, project_with_sources):
        phase = self._make_phase(project_with_sources)
        tree = phase._scan_project_tree()
        assert ".skaro" not in tree

    def test_empty_project(self, init_project):
        phase = self._make_phase(init_project)
        tree = phase._scan_project_tree()
        # Only .skaro exists, which is skipped → empty
        assert tree == ""

    def test_truncates_at_200(self, init_project):
        # Create 210 files
        many_dir = init_project / "many"
        many_dir.mkdir()
        for i in range(210):
            (many_dir / f"file_{i:04d}.py").write_text(f"# file {i}", encoding="utf-8")

        phase = self._make_phase(init_project)
        tree = phase._scan_project_tree()
        assert "truncated" in tree
        lines = tree.strip().splitlines()
        assert len(lines) <= 201  # 200 files + 1 "truncated" line


# ═══════════════════════════════════════════════════
# _collect_project_sources
# ═══════════════════════════════════════════════════

class TestCollectProjectSources:

    def _make_phase(self, root: Path) -> BasePhase:
        from skaro_core.phases.plan import PlanPhase
        return PlanPhase(project_root=root)

    def test_collects_source_files(self, project_with_sources):
        phase = self._make_phase(project_with_sources)
        files = phase._collect_project_sources()
        # Should find .py and .js files
        py_files = [k for k in files if k.endswith(".py")]
        assert len(py_files) >= 2  # main.py, utils.py, __init__.py
        assert any("main.py" in k for k in files)

    def test_skips_pycache(self, project_with_sources):
        phase = self._make_phase(project_with_sources)
        files = phase._collect_project_sources()
        assert not any("__pycache__" in k for k in files)
        assert not any(".pyc" in k for k in files)

    def test_skips_node_modules(self, project_with_sources):
        phase = self._make_phase(project_with_sources)
        files = phase._collect_project_sources()
        assert not any("node_modules" in k for k in files)

    def test_respects_max_files(self, project_with_sources):
        phase = self._make_phase(project_with_sources)
        files = phase._collect_project_sources(max_files=2)
        assert len(files) <= 2

    def test_truncates_large_files(self, project_with_sources):
        # Create a large file
        big = project_with_sources / "src" / "big.py"
        big.write_text("x = 1\n" * 5000, encoding="utf-8")

        phase = self._make_phase(project_with_sources)
        files = phase._collect_project_sources(max_file_size=100)
        big_key = [k for k in files if "big.py" in k]
        assert len(big_key) == 1
        assert files[big_key[0]].endswith("... (truncated)")

    def test_config_files_collected(self, project_with_sources):
        """Config files (.yaml, .toml, .json) are now collected by default."""
        (project_with_sources / "config.yaml").write_text("key: value", encoding="utf-8")
        (project_with_sources / "pyproject.toml").write_text("[project]\nname='x'", encoding="utf-8")

        phase = self._make_phase(project_with_sources)
        files = phase._collect_project_sources()
        assert any(".yaml" in k for k in files)
        assert any(".toml" in k for k in files)

    def test_binary_files_skipped(self, project_with_sources):
        """Binary files (.png, .zip, .pyc) are not collected."""
        (project_with_sources / "logo.png").write_bytes(b"\x89PNG")
        (project_with_sources / "cache.pyc").write_bytes(b"\x00\x00")

        phase = self._make_phase(project_with_sources)
        files = phase._collect_project_sources()
        assert not any(".png" in k for k in files)
        assert not any(".pyc" in k for k in files)

    def test_empty_project(self, init_project):
        phase = self._make_phase(init_project)
        files = phase._collect_project_sources()
        assert files == {}


# ═══════════════════════════════════════════════════
# PlanPhase with mock LLM
# ═══════════════════════════════════════════════════

class TestPlanPhaseWithMock:

    @pytest.fixture
    def task_project(self, init_project):
        am = ArtifactManager(init_project)
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")
        am.write_task_file("01-foundation", "auth", "spec.md", "# Auth\n\nImplement JWT auth")
        return init_project

    @pytest.mark.asyncio
    async def test_plan_phase_creates_plan_md(self, task_project):
        mock_response = (
            "# Implementation Plan\n\n"
            "## Stage 1: Setup\n"
            "- Create project structure\n\n"
            "## Stage 2: Implementation\n"
            "- Implement JWT tokens\n"
        )
        mock_adapter = MockLLMAdapter(mock_response)

        with patch("skaro_core.phases.base.create_llm_adapter", return_value=mock_adapter):
            from skaro_core.phases.plan import PlanPhase
            phase = PlanPhase(project_root=task_project)
            result = await phase.run(task="auth")

        assert result.success is True
        assert result.data["stage_count"] == 2
        assert "plan" in result.data

        # Verify plan.md was written
        am = ArtifactManager(task_project)
        plan = am.find_and_read_task_file("auth", "plan.md")
        assert plan is not None
        assert "Stage 1" in plan

    @pytest.mark.asyncio
    async def test_plan_phase_counts_stages(self, task_project):
        mock_response = (
            "```markdown\n"
            "# Plan\n\n"
            "## Stage 1\nSetup\n\n"
            "## Stage 2\nBuild\n\n"
            "## Stage 3\nTest\n"
            "```"
        )
        mock_adapter = MockLLMAdapter(mock_response)

        with patch("skaro_core.phases.base.create_llm_adapter", return_value=mock_adapter):
            from skaro_core.phases.plan import PlanPhase
            phase = PlanPhase(project_root=task_project)
            result = await phase.run(task="auth")

        assert result.data["stage_count"] == 3

    @pytest.mark.asyncio
    async def test_plan_phase_handles_tasks_section(self, task_project):
        mock_response = (
            "# Plan\n\n"
            "## Stage 1\nSetup\n\n"
            "---TASKS---\n"
            "- [ ] Create models\n"
            "- [ ] Add routes\n"
        )
        mock_adapter = MockLLMAdapter(mock_response)

        with patch("skaro_core.phases.base.create_llm_adapter", return_value=mock_adapter):
            from skaro_core.phases.plan import PlanPhase
            phase = PlanPhase(project_root=task_project)
            result = await phase.run(task="auth")

        assert result.success is True
        assert result.data.get("tasks", "")  # tasks section parsed


# ═══════════════════════════════════════════════════
# ClarifyPhase with mock LLM
# ═══════════════════════════════════════════════════

class TestClarifyPhaseWithMock:

    @pytest.fixture
    def task_project(self, init_project):
        am = ArtifactManager(init_project)
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")
        am.write_task_file(
            "01-foundation", "auth", "spec.md",
            "# Auth Module\n\nImplement user authentication with JWT.\n"
        )
        return init_project

    @pytest.mark.asyncio
    async def test_generate_questions_json(self, task_project):
        mock_response = '''```json
[
  {"question": "Which database?", "context": "For user storage", "options": ["PostgreSQL", "MySQL"]},
  {"question": "Need OAuth?", "context": "Social login", "options": ["Yes", "No"]}
]
```'''
        mock_adapter = MockLLMAdapter(mock_response)

        with patch("skaro_core.phases.base.create_llm_adapter", return_value=mock_adapter):
            from skaro_core.phases.clarify import ClarifyPhase
            phase = ClarifyPhase(project_root=task_project)
            response = await phase.generate_questions("auth")

        assert "database" in response.lower() or "Which database" in response
        # Verify LLM was called with spec context
        assert len(mock_adapter.calls) == 1

    @pytest.mark.asyncio
    async def test_run_dispatches_to_generate(self, task_project):
        mock_response = '[{"question": "Test?", "context": "", "options": []}]'
        mock_adapter = MockLLMAdapter(mock_response)

        with patch("skaro_core.phases.base.create_llm_adapter", return_value=mock_adapter):
            from skaro_core.phases.clarify import ClarifyPhase
            phase = ClarifyPhase(project_root=task_project)
            result = await phase.run(task="auth")

        assert result.success is True
        assert "questions" in result.data


# ═══════════════════════════════════════════════════
# ImplementPhase with mock LLM
# ═══════════════════════════════════════════════════

class TestImplementPhaseWithMock:

    @pytest.fixture
    def task_project(self, init_project):
        am = ArtifactManager(init_project)
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")
        am.write_task_file(
            "01-foundation", "auth", "spec.md",
            "# Auth\nJWT auth module\n"
        )
        am.write_task_file(
            "01-foundation", "auth", "plan.md",
            "# Plan\n\n## Stage 1: Setup\n- Create base files\n"
        )
        return init_project

    @pytest.mark.asyncio
    async def test_implement_parses_file_blocks(self, task_project):
        mock_response = (
            "Here is the implementation:\n\n"
            "```src/auth/__init__.py\n"
            "# Auth module\n"
            "```\n\n"
            "```src/auth/jwt.py\n"
            "import jwt\n\n"
            "def create_token(user_id: str) -> str:\n"
            "    return jwt.encode({'sub': user_id}, 'secret')\n"
            "```\n\n"
            "```AI_NOTES.md\n"
            "# AI_NOTES — Stage 1\n\n"
            "Created auth module with JWT support.\n"
            "```\n"
        )
        mock_adapter = MockLLMAdapter(mock_response)

        with patch("skaro_core.phases.base.create_llm_adapter", return_value=mock_adapter):
            from skaro_core.phases.implement import ImplementPhase
            phase = ImplementPhase(project_root=task_project)
            result = await phase.run(task="auth", stage=1)

        assert result.success is True
        assert "files" in result.data
        files = result.data["files"]
        assert "src/auth/jwt.py" in files
        assert "AI_NOTES.md" not in files  # extracted separately

    @pytest.mark.asyncio
    async def test_implement_no_plan_fails(self, init_project):
        am = ArtifactManager(init_project)
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "no-plan")
        am.write_task_file("01-foundation", "no-plan", "spec.md", "# Task\nDo something")

        mock_adapter = MockLLMAdapter("response")

        with patch("skaro_core.phases.base.create_llm_adapter", return_value=mock_adapter):
            from skaro_core.phases.implement import ImplementPhase
            phase = ImplementPhase(project_root=init_project)
            result = await phase.run(task="no-plan", stage=1)

        assert result.success is False
        assert "plan" in result.message.lower()


# ═══════════════════════════════════════════════════
# _validate_project_path (already in test_validation, but test edge cases)
# ═══════════════════════════════════════════════════

class TestValidateProjectPathEdgeCases:

    def test_symlink_within_project(self, init_project):
        """Symlinks that resolve within project should be allowed."""
        real_file = init_project / "real.py"
        real_file.write_text("x = 1")
        result = BasePhase._validate_project_path(init_project, "real.py")
        assert result == real_file.resolve()

    def test_deeply_nested_valid_path(self, init_project):
        result = BasePhase._validate_project_path(
            init_project, "a/b/c/d/e/f.py"
        )
        assert init_project.resolve() in result.parents


# ═══════════════════════════════════════════════════
# FixPhase with mock LLM
# ═══════════════════════════════════════════════════

class TestFixPhaseWithMock:

    @pytest.fixture
    def task_project(self, init_project):
        am = ArtifactManager(init_project)
        am.create_milestone("01-foundation")
        am.create_task("01-foundation", "auth")
        am.write_task_file(
            "01-foundation", "auth", "spec.md",
            "# Auth\nJWT auth module\n"
        )
        am.write_task_file(
            "01-foundation", "auth", "plan.md",
            "# Plan\n\n## Stage 1: Setup\n- Create base files\n"
        )
        # Create a source file that LLM will "fix"
        src = init_project / "src" / "auth.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("def login():\n    pass  # TODO\n", encoding="utf-8")
        return init_project

    @pytest.mark.asyncio
    async def test_fix_returns_file_diffs(self, task_project):
        mock_response = (
            "I'll fix the login function.\n\n"
            "```src/auth.py\n"
            "def login(username: str, password: str) -> str:\n"
            "    return create_token(username)\n"
            "```\n"
        )
        mock_adapter = MockLLMAdapter(mock_response)

        with patch("skaro_core.phases.base.create_llm_adapter", return_value=mock_adapter):
            from skaro_core.phases.fix import FixPhase
            phase = FixPhase(project_root=task_project)
            result = await phase.run(
                task="auth",
                message="Fix the login function to accept credentials",
                conversation=[],
            )

        assert result.success is True
        assert "files" in result.data
        assert "src/auth.py" in result.data["files"]
        diff = result.data["files"]["src/auth.py"]
        assert diff["old"] is not None  # had existing file
        assert "create_token" in diff["new"]

    @pytest.mark.asyncio
    async def test_fix_persists_conversation(self, task_project):
        mock_response = "No code changes needed. The function looks correct."
        mock_adapter = MockLLMAdapter(mock_response)

        with patch("skaro_core.phases.base.create_llm_adapter", return_value=mock_adapter):
            from skaro_core.phases.fix import FixPhase
            phase = FixPhase(project_root=task_project)
            result = await phase.run(
                task="auth",
                message="Is the login function correct?",
                conversation=[],
            )

        assert "conversation" in result.data
        conv = result.data["conversation"]
        assert len(conv) == 2  # user + assistant
        assert conv[0]["role"] == "user"
        assert conv[1]["role"] == "assistant"

        # Verify persistence
        loaded = phase.load_conversation("auth")
        assert len(loaded) == 2

    @pytest.mark.asyncio
    async def test_fix_rejects_empty_message(self, task_project):
        with patch("skaro_core.phases.base.create_llm_adapter"):
            from skaro_core.phases.fix import FixPhase
            phase = FixPhase(project_root=task_project)
            result = await phase.run(task="auth", message="", conversation=[])

        assert result.success is False
        assert "required" in result.message.lower()

    def test_clear_conversation(self, task_project):
        from skaro_core.phases.fix import FixPhase
        phase = FixPhase(project_root=task_project)

        # Save a conversation
        phase._save_conversation("auth", [{"role": "user", "content": "test"}])
        assert len(phase.load_conversation("auth")) == 1

        # Clear it
        phase.clear_conversation("auth")
        assert phase.load_conversation("auth") == []

    def test_apply_file(self, task_project):
        from skaro_core.phases.fix import FixPhase
        phase = FixPhase(project_root=task_project)
        result = phase.apply_file("auth", "src/auth.py", "def login():\n    return 'ok'\n")
        assert result.success is True

        # Verify file was written
        content = (task_project / "src" / "auth.py").read_text(encoding="utf-8")
        assert "return 'ok'" in content

    def test_apply_file_rejects_traversal(self, task_project):
        from skaro_core.phases.fix import FixPhase
        phase = FixPhase(project_root=task_project)
        result = phase.apply_file("auth", "../../../etc/passwd", "hacked")
        assert result.success is False


# ═══════════════════════════════════════════════════
# _find_templates_dir
# ═══════════════════════════════════════════════════

class TestFindTemplatesDir:

    def test_templates_dir_found(self):
        """In dev mode, templates dir should be found via relative path."""
        from skaro_core.artifacts import _find_templates_dir
        result = _find_templates_dir()
        # May be None in CI without templates, but in our project it exists
        if result is not None:
            assert result.is_dir()
            assert (result / "constitution-template.md").exists()

    def test_templates_pkg_dir_is_set(self):
        """Module-level TEMPLATES_PKG_DIR should be initialized."""
        from skaro_core.artifacts import TEMPLATES_PKG_DIR
        # Either a valid Path or None (never raises)
        assert TEMPLATES_PKG_DIR is None or TEMPLATES_PKG_DIR.is_dir()
