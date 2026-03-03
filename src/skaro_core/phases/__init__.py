"""Skaro Phases — all development phases."""

from skaro_core.phases.architecture import ArchitecturePhase
from skaro_core.phases.base import (
    BasePhase,
    PhaseResult,
    SKIP_DIRS,
    SOURCE_EXTENSIONS,
)
from skaro_core.phases.clarify import ClarifyPhase
from skaro_core.phases.devplan import DevPlanPhase
from skaro_core.phases.implement import ImplementPhase
from skaro_core.phases.import_analyze import ImportAnalyzePhase
from skaro_core.phases.plan import PlanPhase
from skaro_core.phases.tests import TestsPhase

__all__ = [
    "BasePhase",
    "PhaseResult",
    "SKIP_DIRS",
    "SOURCE_EXTENSIONS",
    "ArchitecturePhase",
    "ClarifyPhase",
    "DevPlanPhase",
    "ImportAnalyzePhase",
    "PlanPhase",
    "ImplementPhase",
    "TestsPhase",
    "get_phase",
]


def get_phase(name: str, **kwargs) -> BasePhase:
    """Get a phase instance by name."""
    phases = {
        "architecture": ArchitecturePhase,
        "clarify": ClarifyPhase,
        "devplan": DevPlanPhase,
        "import_analyze": ImportAnalyzePhase,
        "plan": PlanPhase,
        "implement": ImplementPhase,
        "tests": TestsPhase,
    }
    cls = phases.get(name)
    if cls is None:
        raise ValueError(f"Unknown phase: {name}. Available: {list(phases.keys())}")
    return cls(**kwargs)
