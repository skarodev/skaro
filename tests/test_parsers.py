"""Tests for LLM output parsers."""

from __future__ import annotations

import pytest

from skaro_core.phases.base import BasePhase, strip_outer_md_fence
from skaro_core.phases.plan import PlanPhase
from skaro_core.phases._clarify_parser import parse_raw_questions


# ═══════════════════════════════════════════════════
# _parse_file_blocks (BasePhase static method)
# ═══════════════════════════════════════════════════

class TestParseFileBlocks:

    def test_single_file(self):
        content = (
            "Here is the implementation:\n\n"
            "--- FILE: src/main.py ---\n"
            "def main():\n"
            "    print('hello')\n"
            "--- END FILE ---\n"
        )
        result = BasePhase._parse_file_blocks(content)
        assert "src/main.py" in result
        assert "def main():" in result["src/main.py"]

    def test_multiple_files(self):
        content = (
            "--- FILE: src/app.py ---\n"
            "from flask import Flask\n"
            "app = Flask(__name__)\n"
            "--- END FILE ---\n\n"
            "--- FILE: src/models.py ---\n"
            "class User:\n"
            "    pass\n"
            "--- END FILE ---\n"
        )
        result = BasePhase._parse_file_blocks(content)
        assert len(result) == 2
        assert "src/app.py" in result
        assert "src/models.py" in result

    def test_ignores_non_file_content(self):
        content = (
            "Here's an example:\n\n"
            "Some explanation text.\n\n"
            "--- FILE: src/real_file.py ---\n"
            "y = 99\n"
            "--- END FILE ---\n"
        )
        result = BasePhase._parse_file_blocks(content)
        assert len(result) == 1
        assert "src/real_file.py" in result

    def test_empty_content(self):
        assert BasePhase._parse_file_blocks("") == {}

    def test_no_file_blocks(self):
        content = "Just some text without any code blocks."
        assert BasePhase._parse_file_blocks(content) == {}

    def test_nested_path(self):
        content = (
            "--- FILE: src/api/routes/auth.py ---\n"
            "from fastapi import APIRouter\n"
            "--- END FILE ---\n"
        )
        result = BasePhase._parse_file_blocks(content)
        assert "src/api/routes/auth.py" in result

    def test_dotfile_recognized(self):
        content = (
            "--- FILE: .gitignore ---\n"
            "*.pyc\n"
            "__pycache__/\n"
            "--- END FILE ---\n"
        )
        result = BasePhase._parse_file_blocks(content)
        assert ".gitignore" in result

    def test_preserves_empty_lines(self):
        content = (
            "--- FILE: src/main.py ---\n"
            "line1\n"
            "\n"
            "line3\n"
            "--- END FILE ---\n"
        )
        result = BasePhase._parse_file_blocks(content)
        assert result["src/main.py"] == "line1\n\nline3"

    def test_backtick_fences_not_parsed_as_files(self):
        """Legacy backtick format should NOT be parsed."""
        content = (
            "```src/old.py\n"
            "print('old')\n"
            "```\n"
        )
        result = BasePhase._parse_file_blocks(content)
        assert result == {}


# ═══════════════════════════════════════════════════
# _strip_fences (PlanPhase static method)
# ═══════════════════════════════════════════════════

class TestStripFences:

    def test_strips_markdown_fence(self):
        text = "```markdown\n# Plan\n\n## Stage 1\nDo stuff\n```"
        result = PlanPhase._strip_fences(text)
        assert result.startswith("# Plan")
        assert "```" not in result

    def test_strips_md_fence(self):
        text = "```md\n# Plan\n```"
        result = PlanPhase._strip_fences(text)
        assert result == "# Plan"

    def test_strips_bare_fence(self):
        text = "```\n# Plan\n```"
        result = PlanPhase._strip_fences(text)
        assert result == "# Plan"

    def test_returns_unfenced_text_as_is(self):
        text = "# Plan\n\n## Stage 1\nDo stuff"
        assert PlanPhase._strip_fences(text) == text

    def test_handles_whitespace(self):
        text = "  ```markdown\n# Plan\n```  "
        result = PlanPhase._strip_fences(text)
        assert "```" not in result

    def test_empty_string(self):
        assert PlanPhase._strip_fences("") == ""


# ═══════════════════════════════════════════════════
# strip_outer_md_fence (shared utility)
# ═══════════════════════════════════════════════════

class TestStripOuterMdFence:
    """Tests for the fixed outer-fence stripping logic."""

    def test_no_wrapper_with_inner_bare_blocks_preserved(self):
        """Inner bare ``` code blocks must NOT be treated as outer wrapper."""
        text = (
            "# Plan\n\n"
            "## Stage 1\n\n"
            "Example:\n\n"
            "```\nhello world\n```\n\n"
            "## Stage 2\nMore text"
        )
        assert strip_outer_md_fence(text) == text

    def test_no_wrapper_multiple_bare_blocks_preserved(self):
        text = (
            "# Plan\n\n"
            "```\ncode block 1\n```\n\n"
            "Some text\n\n"
            "```\ncode block 2\n```"
        )
        assert strip_outer_md_fence(text) == text

    def test_wrapped_md_preserves_inner_labeled_blocks(self):
        text = (
            "```markdown\n"
            "# Plan\n\n"
            "```python\ndef hello():\n    pass\n```\n\n"
            "More text\n"
            "```"
        )
        result = strip_outer_md_fence(text)
        assert "# Plan" in result
        assert "```python" in result
        assert "def hello():" in result

    def test_wrapped_md_preserves_inner_bare_blocks(self):
        text = (
            "```markdown\n"
            "# Plan\n\n"
            "```\nsome code\n```\n\n"
            "More text\n"
            "```"
        )
        result = strip_outer_md_fence(text)
        assert "# Plan" in result
        assert "some code" in result
        assert result.count("```") == 2  # only inner pair

    def test_text_after_closing_fence_prevents_stripping(self):
        """If there's non-blank text after the last ```, it's not a wrapper."""
        text = "```markdown\n# Plan\n```\n\nAdditional notes here"
        assert strip_outer_md_fence(text) == text

    def test_strips_bare_wrapper(self):
        text = "```\n# Content\n```"
        assert strip_outer_md_fence(text) == "# Content"

    def test_strips_md_wrapper(self):
        text = "```md\n# Content\n```"
        assert strip_outer_md_fence(text) == "# Content"

    def test_strips_markdown_wrapper(self):
        text = "```markdown\n# Content\n```"
        assert strip_outer_md_fence(text) == "# Content"

    def test_no_false_positive_on_language_fence(self):
        """```python at start should not be treated as outer MD wrapper."""
        text = "```python\nprint('hi')\n```"
        assert strip_outer_md_fence(text) == text


# ═══════════════════════════════════════════════════
# parse_raw_questions (_clarify_parser)
# ═══════════════════════════════════════════════════

class TestClarifyParser:

    def test_json_format(self):
        text = '''```json
[
  {
    "question": "What database will you use?",
    "context": "Needed for persistence layer",
    "options": ["PostgreSQL", "MySQL", "SQLite"]
  },
  {
    "question": "Do you need auth?",
    "context": "",
    "options": ["Yes", "No"]
  }
]
```'''
        result = parse_raw_questions(text)
        assert len(result) == 2
        assert result[0]["question"] == "What database will you use?"
        assert result[0]["options"] == ["PostgreSQL", "MySQL", "SQLite"]
        assert result[1]["question"] == "Do you need auth?"

    def test_json_without_fences(self):
        text = '[{"question": "How many users?", "context": "", "options": []}]'
        result = parse_raw_questions(text)
        assert len(result) == 1
        assert result[0]["question"] == "How many users?"

    def test_json_with_preamble(self):
        text = (
            "Here are my clarifying questions:\n\n"
            '[{"question": "Framework preference?", "context": "web", "options": ["FastAPI", "Django"]}]'
        )
        result = parse_raw_questions(text)
        assert len(result) == 1

    def test_legacy_numbered_format(self):
        text = (
            "Question 1: What database do you prefer?\n"
            "PostgreSQL or MySQL?\n\n"
            "Question 2: Do you need real-time features?\n"
            "WebSocket vs SSE\n"
        )
        result = parse_raw_questions(text)
        assert len(result) == 2
        assert "database" in result[0]["question"]

    def test_legacy_q_format(self):
        text = (
            "Q1. What is the target audience?\n"
            "Consumer or enterprise?\n\n"
            "Q2. What is the budget?\n"
        )
        result = parse_raw_questions(text)
        assert len(result) == 2

    def test_legacy_numbered_plain(self):
        text = (
            "1. What language should the API use?\n"
            "2. Should we support pagination?\n"
        )
        result = parse_raw_questions(text)
        assert len(result) == 2

    def test_empty_input(self):
        assert parse_raw_questions("") == []

    def test_no_questions_found(self):
        text = "This is just some random text without any questions."
        result = parse_raw_questions(text)
        assert result == []

    def test_json_skips_items_without_question_key(self):
        text = '[{"question": "Valid?"}, {"not_a_question": "Skip me"}]'
        result = parse_raw_questions(text)
        assert len(result) == 1

    def test_json_invalid_fallback_to_legacy(self):
        text = (
            "{invalid json[\n\n"
            "Question 1: Fallback question?\n"
        )
        result = parse_raw_questions(text)
        assert len(result) == 1
        assert "Fallback" in result[0]["question"]
