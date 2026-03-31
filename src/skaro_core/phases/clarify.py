"""Clarify phase: interactive specification refinement with LLM.

Questions and answers are persisted to clarifications.md.
Format:
    ## Question 1
    <question text>

    *Context:* <why it matters>

    **Options:**
    - A) option text
    - B) option text

    **Answer:**
    <selected option letter, number, or custom text>

The file is never deleted — it serves as permanent record of Q&A.
UI checks whether answers are filled to determine state.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, AsyncIterator

from skaro_core.llm.base import LLMMessage
from skaro_core.phases.base import BasePhase, PhaseResult, strip_outer_md_fence

CLARIFY_FILENAME = "clarifications.md"

OPTION_LETTERS = "ABCDEFGHIJ"


class ClarifyPhase(BasePhase):
    phase_name = "clarify"

    async def generate_questions(self, task: str) -> str:
        """Ask LLM to generate clarification questions for a task spec."""
        spec = self.artifacts.find_and_read_task_file(task, "spec.md")
        if not spec:
            raise ValueError(f"No spec.md found for task '{task}'")

        prompt_template = self._load_prompt_template("clarify")
        prompt = prompt_template or (
            "Perform structured clarification of this specification.\n"
            "Return a JSON array of questions with options.\n"
            "Each item: {question, context, options: [...]}\n"
            "3-7 questions max."
        )

        extra_context: dict[str, str] = {"Specification": spec}
        cacheable_context: dict[str, str] = {}

        # Architecture — so LLM knows project structure decisions
        architecture = self.artifacts.read_architecture()
        if architecture.strip():
            cacheable_context["Architecture"] = architecture

        # AST index — so LLM sees what code already exists
        from skaro_core.context import SmartContextBuilder

        builder = SmartContextBuilder(
            self.artifacts.root,
            always_include=self.config.context_always_include,
        )
        smart = await asyncio.to_thread(
            builder.build,
            stage_section=spec,
            max_full_files=0,  # Clarify only needs signatures, not full code
        )
        if smart.signatures:
            cacheable_context["Project API Index (existing code)"] = smart.signatures

        # Project file tree — so LLM sees what files exist
        project_tree = await self._scan_project_tree_async()
        if project_tree:
            extra_context["Current project file tree"] = project_tree

        # Add existing clarifications if any
        existing = self.artifacts.find_and_read_task_file(task, CLARIFY_FILENAME)
        if existing:
            extra_context["Previous clarifications"] = existing

        messages = self._build_messages(prompt, extra_context, cacheable_context=cacheable_context)
        response_content = await self._stream_collect(messages, task=task or "")
        return response_content

    async def process_answers(
        self, task: str, questions_raw: str, answers: dict[int, str]
    ) -> PhaseResult:
        """Process user answers: update clarifications.md with full Q&A, then update spec."""
        spec = self.artifacts.find_and_read_task_file(task, "spec.md")

        # Load current clarifications.md to get question texts
        current = self.artifacts.find_and_read_task_file(task, CLARIFY_FILENAME)
        if current:
            parsed = parse_clarifications(current)
            # Merge: UI answers take priority, fall back to file answers
            for q in parsed:
                num = q["num"]
                if num not in answers or not answers[num].strip():
                    if q["answer"].strip():
                        answers[num] = q["answer"]
        else:
            parsed = []

        # Build full Q&A document (questions + options + answers together)
        lines = [f"# Clarifications: {task}", ""]
        for q in parsed:
            num = q["num"]
            lines.append(f"## Question {num}")
            lines.append(q["question"])
            lines.append("")
            if q.get("context"):
                lines.append(f"*Context:* {q['context']}")
                lines.append("")
            if q.get("options"):
                lines.append("**Options:**")
                for j, opt in enumerate(q["options"]):
                    letter = OPTION_LETTERS[j] if j < len(OPTION_LETTERS) else str(j + 1)
                    lines.append(f"- {letter}) {opt}")
                lines.append("")
            lines.append("**Answer:**")
            answer = answers.get(num, q["answer"]).strip()
            # Resolve option letter to full text for LLM
            resolved = _resolve_answer(answer, q.get("options", []))
            lines.append(resolved)
            lines.append("")

        qa_content = "\n".join(lines)

        # Build Q&A summary for LLM prompt (with resolved answers)
        qa_for_llm = []
        for q in parsed:
            num = q["num"]
            ans = answers.get(num, "").strip()
            if ans:
                resolved = _resolve_answer(ans, q.get("options", []))
                qa_for_llm.append(f"Q{num}: {q['question']}\nA{num}: {resolved}")
        qa_prompt = "\n\n".join(qa_for_llm)

        # Ask LLM to update spec based on clarifications
        prompt = (
            "Based on these clarification Q&As, update the specification.\n\n"
            "Rules:\n"
            "- Incorporate all answers into the spec\n"
            "- Remove or resolve items from 'Open questions'\n"
            "- Add acceptance criteria where missing\n"
            "- Do NOT remove existing content, only add/clarify\n"
            "- Return the FULL updated spec.md\n\n"
            f"Q&A:\n{qa_prompt}"
        )

        messages = self._build_messages(prompt, {"Current spec.md": spec})
        response_content = await self._stream_collect(messages, task=task or "")

        # Save clarifications (with questions AND answers)
        clarify_path = self.artifacts.find_and_write_task_file(
            task, CLARIFY_FILENAME, qa_content
        )

        # Save updated spec — strip outer markdown fence if LLM wrapped the response
        updated_spec = strip_outer_md_fence(response_content)

        spec_path = self.artifacts.find_and_write_task_file(task, "spec.md", updated_spec)

        return PhaseResult(
            success=True,
            message="Clarifications saved, spec updated.",
            artifacts_updated=[str(clarify_path), str(spec_path)],
        )

    async def run(self, task: str | None = None, **kwargs: Any) -> PhaseResult:
        """Generate questions and save to clarifications.md with empty answers."""
        if not task:
            return PhaseResult(success=False, message="Task name is required.")

        questions_raw = await self.generate_questions(task)

        # Persist to clarifications.md
        content = format_clarifications(task, questions_raw)
        self.artifacts.find_and_write_task_file(task, CLARIFY_FILENAME, content)

        return PhaseResult(
            success=True,
            message=questions_raw,
            artifacts_created=[CLARIFY_FILENAME],
            data={"questions": questions_raw, "phase": "clarify"},
        )

    def save_draft(self, task: str, questions: list[dict]) -> PhaseResult:
        """Save partial answers back to clarifications.md."""
        lines = [f"# Clarifications: {task}", ""]
        for q in questions:
            num = q.get("num", 0)
            text = q.get("question", "")
            context = q.get("context", "")
            options = q.get("options", [])
            answer = q.get("answer", "")
            lines.append(f"## Question {num}")
            lines.append(text)
            lines.append("")
            if context:
                lines.append(f"*Context:* {context}")
                lines.append("")
            if options:
                lines.append("**Options:**")
                for j, opt in enumerate(options):
                    letter = OPTION_LETTERS[j] if j < len(OPTION_LETTERS) else str(j + 1)
                    lines.append(f"- {letter}) {opt}")
                lines.append("")
            lines.append("**Answer:**")
            lines.append(answer)
            lines.append("")

        content = "\n".join(lines)
        self.artifacts.find_and_write_task_file(task, CLARIFY_FILENAME, content)
        return PhaseResult(success=True, message="Draft saved.")

    async def stream_run(
        self, task: str | None = None, **kwargs: Any
    ) -> AsyncIterator[str]:
        """Stream clarification questions."""
        if not task:
            yield "Error: task name is required."
            return

        spec = self.artifacts.find_and_read_task_file(task, "spec.md")
        if not spec:
            yield f"Error: no spec.md found for task '{task}'"
            return

        prompt_template = self._load_prompt_template("clarify")
        prompt = prompt_template or (
            "Perform structured clarification of this specification. "
            "Return JSON array of questions with options."
        )

        extra_context: dict[str, str] = {"Specification": spec}
        cacheable_context: dict[str, str] = {}

        architecture = self.artifacts.read_architecture()
        if architecture.strip():
            cacheable_context["Architecture"] = architecture

        from skaro_core.context import SmartContextBuilder

        builder = SmartContextBuilder(
            self.artifacts.root,
            always_include=self.config.context_always_include,
        )
        smart = await asyncio.to_thread(
            builder.build,
            stage_section=spec,
            max_full_files=0,
        )
        if smart.signatures:
            cacheable_context["Project API Index (existing code)"] = smart.signatures

        project_tree = await self._scan_project_tree_async()
        if project_tree:
            extra_context["Current project file tree"] = project_tree

        messages = self._build_messages(prompt, extra_context, cacheable_context=cacheable_context)
        async for chunk in self.llm.stream(messages):
            yield chunk


# ── File format helpers ─────────────────────────────

def _resolve_answer(answer: str, options: list[str]) -> str:
    """If answer is an option letter/number, resolve to full option text."""
    if not answer or not options:
        return answer
    a = answer.strip().upper().rstrip(")")
    # Try letter: A, B, C...
    if len(a) == 1 and a in OPTION_LETTERS:
        idx = OPTION_LETTERS.index(a)
        if idx < len(options):
            return options[idx]
    # Try number: 1, 2, 3...
    try:
        idx = int(a) - 1
        if 0 <= idx < len(options):
            return options[idx]
    except ValueError:
        pass
    return answer


def format_clarifications(task: str, llm_questions: str) -> str:
    """Convert raw LLM questions into structured clarifications.md with empty answers."""
    from skaro_core.phases._clarify_parser import parse_raw_questions

    parsed = parse_raw_questions(llm_questions)

    lines = [f"# Clarifications: {task}", ""]
    for i, q in enumerate(parsed, 1):
        question = q.get("question", q) if isinstance(q, dict) else str(q)
        context = q.get("context", "") if isinstance(q, dict) else ""
        options = q.get("options", []) if isinstance(q, dict) else []

        lines.append(f"## Question {i}")
        lines.append(question.strip())
        lines.append("")
        if context:
            lines.append(f"*Context:* {context}")
            lines.append("")
        if options:
            lines.append("**Options:**")
            for j, opt in enumerate(options):
                letter = OPTION_LETTERS[j] if j < len(OPTION_LETTERS) else str(j + 1)
                lines.append(f"- {letter}) {opt}")
            lines.append("")
        lines.append("**Answer:**")
        lines.append("")
        lines.append("")

    # If parsing yielded nothing, dump raw text as single question
    if not parsed:
        lines.append("## Question 1")
        lines.append(llm_questions.strip())
        lines.append("")
        lines.append("**Answer:**")
        lines.append("")

    return "\n".join(lines)


def parse_clarifications(content: str) -> list[dict]:
    """Parse clarifications.md into list of {num, question, context, options, answer}.

    Format:
        ## Question N
        <question text>

        *Context:* <optional>

        **Options:**
        - A) option text
        - B) option text

        **Answer:**
        <answer text or empty>
    """
    blocks: list[dict] = []
    parts = re.split(r"^## Question\s+(\d+)\s*$", content, flags=re.MULTILINE)
    # parts = [header, "1", block1, "2", block2, ...]
    i = 1
    while i < len(parts) - 1:
        num = int(parts[i])
        block = parts[i + 1]

        # Extract answer
        answer_split = re.split(
            r"^\*\*Answer:\*\*\s*$", block, maxsplit=1, flags=re.MULTILINE
        )
        before_answer = answer_split[0]
        answer_text = answer_split[1].strip() if len(answer_split) > 1 else ""

        # Extract context
        context = ""
        ctx_match = re.search(r"^\*Context:\*\s*(.+)$", before_answer, re.MULTILINE)
        if ctx_match:
            context = ctx_match.group(1).strip()

        # Extract options
        options: list[str] = []
        opts_match = re.split(r"^\*\*Options:\*\*\s*$", before_answer, maxsplit=1, flags=re.MULTILINE)
        if len(opts_match) > 1:
            opt_block = opts_match[1]
            for m in re.finditer(r"^- [A-Z]\)\s*(.+)$", opt_block, re.MULTILINE):
                options.append(m.group(1).strip())

        # Question text = everything before context/options markers
        question_text = before_answer
        # Remove context line
        question_text = re.sub(r"^\*Context:\*\s*.+$", "", question_text, flags=re.MULTILINE)
        # Remove options block
        question_text = re.sub(r"^\*\*Options:\*\*[\s\S]*$", "", question_text, flags=re.MULTILINE)
        question_text = question_text.strip()

        blocks.append({
            "num": num,
            "question": question_text,
            "context": context,
            "options": options,
            "answer": answer_text,
        })
        i += 2

    return blocks
