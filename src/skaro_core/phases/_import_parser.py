"""Parser for the LLM response produced by the repo-analyze prompt.

The legacy single-call flow expects seven top-level sections:

    ## Constitution
    ## Architecture
    ## Invariants
    ## Completed Work
    ## Suggested Dev Plan
    ## ADR Candidates
    ## Open Questions

Each section is extracted as raw Markdown text.
The ``Suggested Dev Plan`` section additionally embeds a JSON milestones
array (same schema as devplan) which is parsed separately.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from skaro_core.phases._devplan_parser import parse_milestones


_SECTION_NAMES = (
    "Constitution",
    "Architecture",
    "Invariants",
    "Completed Work",
    "Suggested Dev Plan",
    "ADR Candidates",
    "Open Questions",
)


@dataclass
class ImportAnalysisResult:
    """Parsed output of the repo-analyze LLM call."""

    constitution: str = ""
    architecture: str = ""
    invariants: str = ""
    completed_work: str = ""
    suggested_devplan_raw: str = ""
    adr_candidates: str = ""
    open_questions: str = ""
    milestones: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """True if the four primary artifacts were extracted."""
        return bool(
            self.constitution.strip()
            and self.architecture.strip()
        )


def parse_import_response(content: str) -> ImportAnalysisResult:
    """Extract all seven sections from the LLM repo-analyze response.

    Falls back gracefully: missing sections produce empty strings rather
    than raising errors, so partial responses are still usable.

    .. deprecated:: Use :func:`parse_architecture_response` for the new
       two-call import flow.
    """
    # Normalise line endings — LLM or OS may inject \r\n
    content = content.replace("\r\n", "\n")

    sections = _split_sections(content)

    result = ImportAnalysisResult(
        constitution=_unwrap_fenced(sections.get("Constitution", "").strip()),
        architecture=_unwrap_fenced(sections.get("Architecture", "").strip()),
        invariants=_unwrap_fenced(sections.get("Invariants", "").strip()),
        completed_work=_unwrap_fenced(sections.get("Completed Work", "").strip()),
        suggested_devplan_raw=sections.get("Suggested Dev Plan", "").strip(),
        adr_candidates=_unwrap_fenced(sections.get("ADR Candidates", "").strip()),
        open_questions=_unwrap_fenced(sections.get("Open Questions", "").strip()),
    )

    # Parse milestones from the Suggested Dev Plan section
    if result.suggested_devplan_raw:
        result.milestones = parse_milestones(result.suggested_devplan_raw)

    return result


def _unwrap_fenced(text: str) -> str:
    """Strip a surrounding fenced code block if the LLM wrapped the content.

    Handles both:
        ```markdown
        <content>
        ```
    and:
        ```
        <content>
        ```

    Also strips trailing horizontal rules (``---``) that the LLM places
    between sections, and normalises ``\\r\\n`` to ``\\n``.

    Preserves inner fenced blocks (e.g. code examples inside the document).
    """
    # Normalise line endings
    text = text.replace("\r\n", "\n")

    # Strip trailing horizontal rules (---, ***, ___) that sit after the fence
    text = re.sub(r"\n---\s*$", "", text.strip()).strip()

    # Match an outer fence at the very start and very end of the string
    match = re.match(
        r"^```[a-zA-Z]*\n([\s\S]*?)```\s*$",
        text,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    return text


def _split_sections(content: str) -> dict[str, str]:
    """Split Markdown content on ## headings that match known section names.

    Matching is case-insensitive and tolerant of extra whitespace.
    """
    known = {name.lower(): name for name in _SECTION_NAMES}

    # Build a regex that matches any known h2 heading
    pattern_parts = [re.escape(name) for name in _SECTION_NAMES]
    heading_re = re.compile(
        r"^##\s+(" + "|".join(pattern_parts) + r")\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    sections: dict[str, str] = {}
    matches = list(heading_re.finditer(content))

    for i, match in enumerate(matches):
        heading = known.get(match.group(1).strip().lower(), match.group(1).strip())
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sections[heading] = content[start:end]

    return sections
