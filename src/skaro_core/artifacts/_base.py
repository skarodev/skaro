"""Base ArtifactManager: init, templates, gitignore, content helpers."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from skaro_core.config import SKARO_DIR, find_project_root

from ._helpers import TEMPLATES_PKG_DIR


class _ArtifactManagerBase:
    """Core of ArtifactManager: initialization and shared helpers."""

    def __init__(self, project_root: Path | None = None):
        self.root = project_root or find_project_root() or Path.cwd()
        self.skaro = self.root / SKARO_DIR

    @property
    def is_initialized(self) -> bool:
        return self.skaro.is_dir()

    # ── Content helpers ─────────────────────────

    @staticmethod
    def _has_real_content(text: str, min_chars: int = 10) -> bool:
        """Check if markdown has real content beyond template placeholders."""
        stripped = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        stripped = re.sub(r"^#+\s.*$", "", stripped, flags=re.MULTILINE)
        stripped = re.sub(r"<[^>]+>", "", stripped)
        stripped = stripped.strip()
        return len(stripped) > min_chars

    def _is_template_content(
        self, content: str, template_name: str, task: str = ""
    ) -> bool:
        """Check if content is still the unmodified template."""
        template_path = self.skaro / "templates" / template_name
        if not template_path.exists():
            return False
        template = template_path.read_text(encoding="utf-8")
        if task:
            template = template.replace("<название задачи>", task)
            template = template.replace("<название фичи>", task)
        return content.strip() == template.strip()

    # ── Project initialization ──────────────────

    def init_project(self) -> Path:
        """Create .skaro/ structure with templates, constitution, and architecture."""
        dirs = [
            self.skaro / "architecture" / "diagrams",
            self.skaro / "milestones",
            self.skaro / "docs",
            self.skaro / "ops",
            self.skaro / "templates",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        self._install_templates()

        if not self.constitution_path.exists():
            self.create_constitution()
        if not self.architecture_path.exists():
            self.create_architecture()

        self._ensure_gitignore()
        self._ensure_skaroignore()

        return self.skaro

    # ── .gitignore ──────────────────────────────

    _GITIGNORE_MARKER = "# ── Skaro (auto-generated, do not remove this marker) ──"

    _GITIGNORE_SECTION = """\
# ── Skaro (auto-generated, do not remove this marker) ──
# This section is managed by `skaro init`. Do NOT delete it.
# You may add your own rules below the closing marker.
#
# Secrets — API keys, never commit!
.skaro/secrets.yaml

# Usage tracking — local stats, not project artifacts
.skaro/token_usage.yaml
.skaro/usage_log.jsonl
# ── /Skaro ─────────────────────────────────────────────
"""

    def _ensure_gitignore(self) -> None:
        gitignore = self.root / ".gitignore"

        existing = ""
        if gitignore.exists():
            existing = gitignore.read_text(encoding="utf-8")
            if self._GITIGNORE_MARKER in existing:
                return

        separator = "\n" if existing and not existing.endswith("\n") else ""
        prefix = "\n" if existing.strip() else ""

        with open(gitignore, "a", encoding="utf-8") as f:
            f.write(f"{separator}{prefix}{self._GITIGNORE_SECTION}")

    # ── .skaroignore ─────────────────────────────

    _SKAROIGNORE_HEADER = """\
# .skaroignore — files excluded from LLM analysis during `skaro init`
# Syntax is identical to .gitignore.
# Add paths that contain sensitive, private, or irrelevant content.
#
# ── Secrets & credentials ──────────────────────────────
.env
.env.*
!.env.example
*.pem
*.key
*.p12
*.pfx
secrets.*
credentials.*
*_secret*
*_credentials*
# ── Private data & dumps ───────────────────────────────
*.sql
*.dump
*.db
*.sqlite
*.sqlite3
data/
datasets/
fixtures/private/
# ── Generated & vendored ───────────────────────────────
vendor/
third_party/
generated/
auto_generated/
# ── Large assets ───────────────────────────────────────
assets/
media/
uploads/
storage/
"""

    def _ensure_skaroignore(self) -> None:
        """Create .skaroignore in the project root if it doesn't exist."""
        skaroignore = self.root / ".skaroignore"
        if not skaroignore.exists():
            skaroignore.write_text(self._SKAROIGNORE_HEADER, encoding="utf-8")

    # ── Templates ───────────────────────────────

    def _install_templates(self) -> None:
        """Copy bundled templates into .skaro/templates/."""
        templates_dest = self.skaro / "templates"
        templates_dest.mkdir(parents=True, exist_ok=True)
        if TEMPLATES_PKG_DIR is not None and TEMPLATES_PKG_DIR.is_dir():
            for tpl in TEMPLATES_PKG_DIR.glob("*.md"):
                dest = templates_dest / tpl.name
                if not dest.exists():
                    shutil.copy2(tpl, dest)

    # ── Ops paths ───────────────────────────────

    @property
    def devops_path(self) -> Path:
        return self.skaro / "ops" / "devops-notes.md"

    @property
    def security_path(self) -> Path:
        return self.skaro / "ops" / "security-review.md"

    @property
    def review_log_path(self) -> Path:
        return self.skaro / "docs" / "review-log.md"
