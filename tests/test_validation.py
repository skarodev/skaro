"""Tests for path traversal protection and Pydantic schema validation."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from skaro_core.phases.base import BasePhase
from skaro_web.api.schemas import (
    AdrStatusBody,
    ArchAcceptBody,
    ConfigUpdateBody,
    FileApplyBody,
    FixBody,
    TaskCreateBody,
)


# ═══════════════════════════════════════════════════
# _validate_project_path
# ═══════════════════════════════════════════════════

class TestValidateProjectPath:

    def test_valid_relative_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = BasePhase._validate_project_path(root, "src/main.py")
            assert result == (root / "src" / "main.py").resolve()

    def test_valid_nested_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = BasePhase._validate_project_path(root, "src/api/routes/auth.py")
            assert root.resolve() in result.parents or result.parent == root.resolve()

    def test_rejects_dot_dot_traversal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with pytest.raises(ValueError, match="traversal"):
                BasePhase._validate_project_path(root, "../../../etc/passwd")

    def test_rejects_dot_dot_in_middle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with pytest.raises(ValueError, match="traversal"):
                BasePhase._validate_project_path(root, "src/../../etc/passwd")

    def test_rejects_absolute_path_outside(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with pytest.raises(ValueError, match="traversal"):
                BasePhase._validate_project_path(root, "/etc/passwd")

    def test_allows_dotfiles(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = BasePhase._validate_project_path(root, ".gitignore")
            assert result.name == ".gitignore"

    def test_allows_hidden_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = BasePhase._validate_project_path(root, ".github/workflows/ci.yml")
            assert ".github" in str(result)


# ═══════════════════════════════════════════════════
# Pydantic schemas
# ═══════════════════════════════════════════════════

class TestFileApplyBody:

    def test_valid_filepath(self):
        body = FileApplyBody(filepath="src/main.py", content="hello")
        assert body.filepath == "src/main.py"

    def test_rejects_empty_filepath(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FileApplyBody(filepath="", content="hello")

    def test_rejects_dot_dot(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="must not contain"):
            FileApplyBody(filepath="../etc/passwd", content="hack")

    def test_rejects_absolute_path(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="must be relative"):
            FileApplyBody(filepath="/etc/passwd", content="hack")

    def test_allows_dotfile(self):
        body = FileApplyBody(filepath=".env", content="SECRET=x")
        assert body.filepath == ".env"


class TestAdrStatusBody:

    def test_valid_statuses(self):
        for status in ("proposed", "accepted", "deprecated", "superseded"):
            body = AdrStatusBody(status=status)
            assert body.status == status

    def test_rejects_invalid_status(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="Invalid ADR status"):
            AdrStatusBody(status="invalid")


class TestArchAcceptBody:

    def test_rejects_empty_architecture(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ArchAcceptBody(proposed_architecture="")


class TestTaskCreateBody:

    def test_rejects_empty_name(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            TaskCreateBody(name="")

    def test_valid_task(self):
        body = TaskCreateBody(name="auth-setup", milestone="01-foundation")
        assert body.name == "auth-setup"


class TestFixBody:

    def test_rejects_empty_message(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FixBody(message="")

    def test_valid_fix(self):
        body = FixBody(message="Fix the login bug", conversation=[])
        assert body.message == "Fix the login bug"


class TestConfigUpdateBody:

    def test_defaults(self):
        body = ConfigUpdateBody()
        assert body.llm.provider == "anthropic"
        assert body.lang == "en"

    def test_to_dict(self):
        body = ConfigUpdateBody(lang="ru")
        d = body.to_dict()
        assert d["lang"] == "ru"
        assert "llm" in d
        assert "ui" in d

    def test_rejects_invalid_port(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ConfigUpdateBody(ui={"port": 0})

    def test_rejects_invalid_temperature(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ConfigUpdateBody(llm={"temperature": 5.0})
