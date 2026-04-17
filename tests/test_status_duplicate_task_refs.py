"""Regression tests for duplicate task slugs across milestones in status payload."""

from pathlib import Path

from skaro_core.artifacts import ArtifactManager
from skaro_web.api.status import _build_status


def test_build_status_includes_unique_task_refs_for_duplicate_slugs(tmp_path: Path):
    am = ArtifactManager(tmp_path)
    am.init_project()
    am.create_milestone("01-foundation")
    am.create_milestone("02-mvp")
    am.create_task("01-foundation", "auth")
    am.create_task("02-mvp", "auth")

    status = _build_status(am, tmp_path)

    refs = [task["ref"] for task in status["tasks"]]
    names = [task["name"] for task in status["tasks"]]

    assert names == ["auth", "auth"]
    assert refs == ["01-foundation::auth", "02-mvp::auth"]
    assert len(set(refs)) == 2
