"""Architecture mixin: architecture, review, ADRs."""

from __future__ import annotations

import re
import shutil
from pathlib import Path


class ArchitectureMixin:
    """Manages .skaro/architecture/ — architecture doc, review, ADRs."""

    @property
    def architecture_path(self) -> Path:
        return self.skaro / "architecture" / "architecture.md"

    @property
    def has_architecture(self) -> bool:
        if not self.architecture_path.exists():
            return False
        content = self.architecture_path.read_text(encoding="utf-8")
        if self._is_template_content(content, "architecture-template.md"):
            return False
        return bool(content.strip())

    def create_architecture(self) -> Path:
        self.architecture_path.parent.mkdir(parents=True, exist_ok=True)
        template = self.skaro / "templates" / "architecture-template.md"
        if template.exists():
            shutil.copy2(template, self.architecture_path)
        else:
            self.architecture_path.write_text(
                "# Architecture\n\n<!-- Describe your architecture here -->\n",
                encoding="utf-8",
            )
        return self.architecture_path

    def read_architecture(self) -> str:
        if self.architecture_path.exists():
            return self.architecture_path.read_text(encoding="utf-8")
        return ""

    def write_architecture(self, content: str) -> Path:
        self.architecture_path.parent.mkdir(parents=True, exist_ok=True)
        self.architecture_path.write_text(content, encoding="utf-8")
        return self.architecture_path

    # ── Review ──────────────────────────────────

    @property
    def architecture_review_path(self) -> Path:
        return self.skaro / "architecture" / "last-review.md"

    def write_architecture_review(self, content: str) -> Path:
        self.architecture_review_path.parent.mkdir(parents=True, exist_ok=True)
        self.architecture_review_path.write_text(content, encoding="utf-8")
        return self.architecture_review_path

    def read_architecture_review(self) -> str:
        if self.architecture_review_path.exists():
            return self.architecture_review_path.read_text(encoding="utf-8")
        return ""

    # ── Invariants (embedded in architecture) ───

    _INVARIANTS_HEADING_RE = re.compile(
        r"^##\s+Architectural\s+Invariants\s*$", re.IGNORECASE | re.MULTILINE,
    )

    @property
    def _legacy_invariants_path(self) -> Path:
        return self.skaro / "architecture" / "invariants.md"

    def migrate_invariants(self) -> bool:
        """One-time migration: merge legacy ``invariants.md`` into architecture.

        Returns ``True`` if migration was performed.
        """
        legacy = self._legacy_invariants_path
        if not legacy.exists():
            return False

        inv_content = legacy.read_text(encoding="utf-8").strip()
        if not inv_content:
            legacy.unlink(missing_ok=True)
            return False

        arch = self.read_architecture()
        if self._INVARIANTS_HEADING_RE.search(arch):
            # Architecture already has the section — just remove legacy file
            legacy.unlink(missing_ok=True)
            return True

        # Append invariants section to architecture
        section = f"\n\n## Architectural Invariants\n\n{inv_content}\n"
        self.write_architecture(arch.rstrip() + section)
        legacy.unlink(missing_ok=True)
        return True

    # ── ADRs ────────────────────────────────────

    def create_adr(self, number: int, title: str) -> Path:
        slug = title.lower().replace(" ", "-").replace("/", "-")[:50]
        filename = f"adr-{number:03d}-{slug}.md"
        path = self.skaro / "architecture" / filename
        template = self.skaro / "templates" / "adr-template.md"
        if template.exists():
            content = template.read_text(encoding="utf-8")
            content = content.replace("<NNN>", f"{number:03d}").replace(
                "<название решения>", title
            )
            path.write_text(content, encoding="utf-8")
        else:
            path.write_text(f"# ADR-{number:03d}: {title}\n", encoding="utf-8")
        return path

    def list_adrs(self) -> list[Path]:
        arch_dir = self.skaro / "architecture"
        if arch_dir.is_dir():
            return sorted(arch_dir.glob("adr-*.md"))
        return []

    @staticmethod
    def parse_adr_metadata(content: str, filename: str = "") -> dict[str, str]:
        meta: dict[str, str] = {"status": "proposed", "date": "", "title": ""}
        m = re.search(r"^#\s+ADR-\d+:\s*(.+)", content, re.MULTILINE)
        if m:
            meta["title"] = m.group(1).strip()
        m = re.search(r"\*\*Status:\*\*\s*(\S+)", content)
        if m:
            meta["status"] = m.group(1).strip().lower()
        m = re.search(r"\*\*Date:\*\*\s*(\S+)", content)
        if m:
            meta["date"] = m.group(1).strip()
        if filename:
            m = re.match(r"adr-(\d+)", filename)
            if m:
                meta["number"] = int(m.group(1))
        return meta

    def read_adr_index(self) -> str:
        entries: list[str] = []
        for adr_path in self.list_adrs():
            content = adr_path.read_text(encoding="utf-8")
            meta = self.parse_adr_metadata(content, adr_path.name)
            if meta["status"] != "accepted":
                continue
            title = meta.get("title", adr_path.stem)
            number = meta.get("number", 0)
            m = re.search(
                r"## Decision\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL
            )
            decision = m.group(1).strip() if m else ""
            if len(decision) > 150:
                decision = decision[:147] + "..."
            entry = f"- **ADR-{number:03d}: {title}**"
            if decision:
                entry += f" — {decision}"
            entries.append(entry)
        if not entries:
            return ""
        return "# ARCHITECTURE DECISIONS (ADR)\n\n" + "\n".join(entries)

    def update_adr_status(self, number: int, new_status: str) -> Path | None:
        valid = {"proposed", "accepted", "deprecated", "superseded"}
        if new_status not in valid:
            raise ValueError(
                f"Invalid ADR status: {new_status}. Must be one of {valid}"
            )
        for adr_path in self.list_adrs():
            m = re.match(r"adr-(\d+)", adr_path.name)
            if m and int(m.group(1)) == number:
                content = adr_path.read_text(encoding="utf-8")
                updated = re.sub(
                    r"(\*\*Status:\*\*)\s*\S+",
                    rf"\1 {new_status}",
                    content,
                    count=1,
                )
                adr_path.write_text(updated, encoding="utf-8")
                return adr_path
        return None

    def write_adr_content(self, number: int, content: str) -> Path | None:
        """Overwrite the full content of an ADR by its number."""
        for adr_path in self.list_adrs():
            m = re.match(r"adr-(\d+)", adr_path.name)
            if m and int(m.group(1)) == number:
                adr_path.write_text(content, encoding="utf-8")
                return adr_path
        return None
