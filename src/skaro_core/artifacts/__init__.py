"""Artifact manager package.

Public API (backward-compatible):
    from skaro_core.artifacts import ArtifactManager, Phase, Status, TaskState, ProjectState
"""

from __future__ import annotations

from skaro_core.artifacts._architecture import ArchitectureMixin
from skaro_core.artifacts._base import _ArtifactManagerBase
from skaro_core.artifacts._constitution import ConstitutionMixin
from skaro_core.artifacts._devplan import DevplanMixin
from skaro_core.artifacts._features import FeaturesMixin
from skaro_core.artifacts._helpers import TEMPLATES_PKG_DIR, _find_templates_dir
from skaro_core.artifacts._milestones import MilestonesMixin
from skaro_core.artifacts._models import (
    PHASE_ORDER,
    Phase,
    ProjectState,
    Status,
    TaskState,
)
from skaro_core.artifacts._state import StateMixin
from skaro_core.artifacts._tasks import TasksMixin


class ArtifactManager(
    FeaturesMixin,
    TasksMixin,
    MilestonesMixin,
    DevplanMixin,
    ArchitectureMixin,
    ConstitutionMixin,
    StateMixin,
    _ArtifactManagerBase,
):
    """Manages all .skaro/ artifacts for a project.

    Composed from domain-specific mixins:
      _base          — init, templates, gitignore, content helpers
      _state         — state.yaml, hashes, approval flags
      _constitution  — constitution CRUD + validation
      _architecture  — architecture, review, ADRs
      _devplan       — dev plan CRUD
      _milestones    — milestone CRUD
      _tasks         — task CRUD, files, stages, slug resolvers, state
      _features      — feature CRUD, meta, plan, task/ADR linking
    """


__all__ = [
    "ArtifactManager",
    "Phase",
    "PHASE_ORDER",
    "ProjectState",
    "Status",
    "TaskState",
    "TEMPLATES_PKG_DIR",
    "_find_templates_dir",
]
