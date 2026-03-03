"""State mixin: state.yaml persistence, content hashes, approval flags."""

from __future__ import annotations

import hashlib
from typing import Any

import yaml


class StateMixin:
    """Manages .skaro/state.yaml — tracks validation/review/confirmation flags."""

    @property
    def state_path(self):
        return self.skaro / "state.yaml"

    def _load_state(self) -> dict[str, Any]:
        if self.state_path.exists():
            with open(self.state_path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def _save_state(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            yaml.dump(state, f, default_flow_style=False, allow_unicode=True)

    # ── Constitution hash ───────────────────────

    def _constitution_hash(self) -> str:
        if self.constitution_path.exists():
            return hashlib.sha256(self.constitution_path.read_bytes()).hexdigest()
        return ""

    @property
    def is_constitution_validated(self) -> bool:
        state = self._load_state()
        if not state.get("constitution_validated"):
            return False
        return state.get("constitution_hash", "") == self._constitution_hash()

    def mark_constitution_validated(self) -> None:
        state = self._load_state()
        state["constitution_validated"] = True
        state["constitution_hash"] = self._constitution_hash()
        self._save_state(state)

    # ── Architecture hash ───────────────────────

    def _architecture_hash(self) -> str:
        if self.architecture_path.exists():
            return hashlib.sha256(self.architecture_path.read_bytes()).hexdigest()
        return ""

    @property
    def is_architecture_reviewed(self) -> bool:
        state = self._load_state()
        if not state.get("architecture_reviewed"):
            return False
        return state.get("architecture_hash", "") == self._architecture_hash()

    def mark_architecture_reviewed(self) -> None:
        state = self._load_state()
        state["architecture_reviewed"] = True
        state["architecture_hash"] = self._architecture_hash()
        self._save_state(state)

    # ── Dev Plan hash ───────────────────────────

    def _devplan_hash(self) -> str:
        if self.devplan_path.exists():
            return hashlib.sha256(self.devplan_path.read_bytes()).hexdigest()
        return ""

    @property
    def is_devplan_confirmed(self) -> bool:
        state = self._load_state()
        if not state.get("devplan_confirmed"):
            return False
        return state.get("devplan_hash", "") == self._devplan_hash()

    def mark_devplan_confirmed(self) -> None:
        state = self._load_state()
        state["devplan_confirmed"] = True
        state["devplan_hash"] = self._devplan_hash()
        self._save_state(state)

    # ── Import state ────────────────────────────

    @property
    def import_mode(self) -> str | None:
        """Return 'auto', 'manual', or None if not an imported project."""
        return self._load_state().get("import_mode")

    @property
    def import_source_commit(self) -> str:
        return self._load_state().get("import_source_commit", "")

    def mark_imported(self, *, mode: str, source_commit: str = "") -> None:
        """Record that the project was initialized via import (auto or manual)."""
        from datetime import datetime, timezone

        state = self._load_state()
        state["import_mode"] = mode
        state["import_timestamp"] = datetime.now(timezone.utc).isoformat()
        state["import_source_commit"] = source_commit
        # Reset approval flags so user is prompted to review generated artifacts
        state["constitution_validated"] = False
        state["architecture_reviewed"] = False
        state["devplan_confirmed"] = False
        self._save_state(state)

    def clear_import_flags(self) -> None:
        """Remove import metadata (e.g. on re-initialization)."""
        state = self._load_state()
        for key in ("import_mode", "import_timestamp", "import_source_commit"):
            state.pop(key, None)
        self._save_state(state)
