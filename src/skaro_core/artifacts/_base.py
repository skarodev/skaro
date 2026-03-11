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

    # ── .gitignore from constitution ─────────────

    _PROJECT_MARKER_START = "# ── Project rules (auto-generated from constitution) ──"
    _PROJECT_MARKER_END = "# ── /Project rules ──────────────────────────────────"

    # Technology keyword → gitignore patterns mapping.
    # Keys are lowercased substrings looked up in the constitution text.
    _GITIGNORE_RULES: dict[str, list[str]] = {
        # ── Languages ──
        "python": [
            "__pycache__/", "*.py[cod]", "*$py.class", "*.egg-info/", "*.egg",
            "dist/", "build/", ".venv/", "venv/", ".tox/", ".mypy_cache/",
            ".pytest_cache/", ".ruff_cache/", "htmlcov/", ".coverage",
            "*.pyo", "*.pyd",
        ],
        "typescript": [
            "node_modules/", "dist/", "build/", "*.tsbuildinfo", ".cache/",
        ],
        "javascript": [
            "node_modules/", "dist/", "build/", ".cache/",
        ],
        "dart": [
            ".dart_tool/", ".packages", "build/", ".pub-cache/",
            ".pub/", "pubspec.lock",
        ],
        "go": ["bin/", "*.exe", "*.out"],
        "rust": ["target/", "Cargo.lock"],
        "java": [
            "*.class", "*.jar", "*.war", "target/", ".gradle/",
            "build/", ".settings/", "*.iml",
        ],
        "kotlin": [
            "*.class", "*.jar", "build/", ".gradle/", "*.iml",
        ],
        "ruby": ["*.gem", ".bundle/", "vendor/bundle/", "Gemfile.lock"],
        # ── Frameworks ──
        "react": ["node_modules/", "build/", ".cache/"],
        "next.js": ["node_modules/", ".next/", "out/"],
        "nextjs": ["node_modules/", ".next/", "out/"],
        "nuxt": ["node_modules/", ".nuxt/", ".output/"],
        "vue": ["node_modules/", "dist/"],
        "angular": ["node_modules/", "dist/", ".angular/"],
        "svelte": ["node_modules/", ".svelte-kit/", "build/"],
        "sveltekit": ["node_modules/", ".svelte-kit/", "build/"],
        "fastapi": [
            "__pycache__/", "*.py[cod]", ".venv/", "venv/",
            ".mypy_cache/", ".pytest_cache/", ".ruff_cache/",
        ],
        "django": [
            "__pycache__/", "*.py[cod]", ".venv/", "venv/",
            "staticfiles/", "media/", "*.sqlite3", "db.sqlite3",
        ],
        "express": ["node_modules/", "dist/", "build/"],
        "nestjs": ["node_modules/", "dist/"],
        "flutter": [
            ".dart_tool/", ".packages", "build/",
            ".flutter-plugins", ".flutter-plugins-dependencies",
            "ios/Pods/", ".pub-cache/",
        ],
        "react native": [
            "node_modules/", "ios/Pods/", "android/.gradle/",
            "android/app/build/", ".expo/", ".buckconfig",
        ],
        "vite": ["node_modules/", "dist/"],
        # ── Infra / tools ──
        "docker": [".docker/"],
        "terraform": [".terraform/", "*.tfstate", "*.tfstate.backup"],
        # ── Databases ──
        "sqlite": ["*.sqlite3", "*.db"],
        "postgresql": [],
        "mongodb": [],
        "redis": ["dump.rdb"],
    }

    # Universal rules always included.
    _GITIGNORE_COMMON: list[str] = [
        "# OS",
        ".DS_Store",
        "Thumbs.db",
        "Desktop.ini",
        "",
        "# IDE",
        ".idea/",
        ".vscode/",
        "*.swp",
        "*.swo",
        "*~",
        "",
        "# Environment",
        ".env",
        ".env.*",
        "!.env.example",
        "",
        "# Logs",
        "*.log",
        "npm-debug.log*",
        "yarn-debug.log*",
        "yarn-error.log*",
    ]

    def generate_project_gitignore(self, constitution_content: str) -> None:
        """Parse constitution and generate/update .gitignore project section."""
        rules = self._detect_gitignore_rules(constitution_content)
        section_lines = [self._PROJECT_MARKER_START]
        section_lines.append(
            "# Auto-generated by Skaro from your constitution. "
            "Safe to edit below /Project rules marker."
        )
        section_lines.append("")

        # Common rules
        section_lines.extend(self._GITIGNORE_COMMON)
        section_lines.append("")

        # Stack-specific rules (deduplicated, preserving order)
        if rules:
            section_lines.append("# Stack-specific")
            seen: set[str] = set()
            for rule in rules:
                if rule not in seen:
                    seen.add(rule)
                    section_lines.append(rule)
            section_lines.append("")

        section_lines.append(self._PROJECT_MARKER_END)
        new_section = "\n".join(section_lines) + "\n"

        gitignore = self.root / ".gitignore"
        existing = ""
        if gitignore.exists():
            existing = gitignore.read_text(encoding="utf-8")

        # Replace existing project section or append
        if self._PROJECT_MARKER_START in existing:
            import re as _re
            pattern = (
                _re.escape(self._PROJECT_MARKER_START)
                + r".*?"
                + _re.escape(self._PROJECT_MARKER_END)
                + r"\n?"
            )
            updated = _re.sub(pattern, new_section, existing, flags=_re.DOTALL)
            gitignore.write_text(updated, encoding="utf-8")
        else:
            separator = "\n" if existing and not existing.endswith("\n") else ""
            prefix = "\n" if existing.strip() else ""
            with open(gitignore, "a", encoding="utf-8") as f:
                f.write(f"{separator}{prefix}{new_section}")

    def _detect_gitignore_rules(self, constitution_content: str) -> list[str]:
        """Detect technologies from constitution and return matching rules."""
        text = constitution_content.lower()
        collected: list[str] = []
        for keyword, rules in self._GITIGNORE_RULES.items():
            if keyword in text:
                collected.extend(rules)
        return collected

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
