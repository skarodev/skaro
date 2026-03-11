"""Architecture review and generation phase."""

from __future__ import annotations

import json
import re
from datetime import date as _date
from pathlib import Path
from typing import Any

from skaro_core.llm.base import LLMMessage
from skaro_core.phases.base import BasePhase, PhaseResult, _has_inner_close_ahead


# Marker that separates review from proposed architecture in LLM response.
_PROPOSED_HEADING_RE = re.compile(
    r"^##\s+Proposed\s+Architecture", re.IGNORECASE | re.MULTILINE
)


def _strip_file_block(text: str, filepath: str) -> str:
    """Remove a fenced file block (``\u0060\u0060\u0060<filepath>`` … ``\u0060\u0060\u0060``) from *text*.

    Correctly handles nested code fences inside the block.
    """
    lines = text.splitlines(True)  # keep line endings
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("```") and lines[i].strip()[3:].strip() == filepath:
            block_start = i
            i += 1
            inner_fence = False
            while i < len(lines):
                stripped = lines[i].strip()
                if inner_fence:
                    if stripped == "```":
                        inner_fence = False
                elif stripped.startswith("```") and len(stripped) > 3:
                    inner_fence = True
                elif stripped == "```":
                    # Check whether this is inner open or outer close
                    if _has_inner_close_ahead(
                        [l.rstrip("\n\r") for l in lines], i + 1
                    ):
                        inner_fence = True
                    else:
                        # Outer close found — remove lines[block_start..i] inclusive
                        return "".join(lines[:block_start] + lines[i + 1 :])
                i += 1
            # No closing fence found — remove from block_start to end
            return "".join(lines[:block_start])
        i += 1
    return text


class ArchitecturePhase(BasePhase):
    phase_name = "architecture"

    # ── Chat-based architecture generation ─────────────

    async def chat(
        self,
        message: str,
        conversation: list[dict[str, str]],
    ) -> PhaseResult:
        """Conversational architecture generation.

        The LLM acts as an architect: asks clarifying questions or generates
        the full architecture document when it has enough context.

        When the LLM generates architecture, it wraps it in a
        ``\u0060\u0060\u0060architecture.md`` code fence which is extracted
        as a proposed file.
        """
        prompt_template = self._load_prompt_template("architecture-chat")
        system = self._build_system_message()
        if prompt_template:
            system += "\n\n---\n\n" + prompt_template

        messages: list[LLMMessage] = [LLMMessage(role="system", content=system)]

        # Replay conversation history
        for turn in conversation:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content.strip():
                messages.append(LLMMessage(role=role, content=content))

        # Current user message (+ language reminder)
        final_message = message
        if self.config.lang != "en":
            final_message += f"\n\n---\nReminder: {self._lang_instruction()}"
        messages.append(LLMMessage(role="user", content=final_message))

        response_content = await self._stream_collect(messages, min_tokens=16384)

        # Check if LLM produced an architecture document
        proposed_files = self._parse_file_blocks(response_content)
        arch_content = proposed_files.get("architecture.md", "")

        file_diffs: dict[str, dict] = {}
        if arch_content:
            file_diffs["architecture.md"] = {
                "old": "",
                "new": arch_content,
                "is_new": True,
            }

        # Strip the code fence from the visible message
        display_message = response_content
        if arch_content:
            display_message = _strip_file_block(
                display_message, "architecture.md"
            ).strip()

        updated_conversation = list(conversation) + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": response_content},
        ]

        # Persist conversation
        self._save_chat_conversation(updated_conversation)

        return PhaseResult(
            success=True,
            message=display_message,
            data={
                "files": file_diffs,
                "conversation": updated_conversation,
                "has_architecture": bool(arch_content),
            },
        )

    def load_chat_conversation(self) -> list[dict]:
        """Load persisted architecture chat conversation."""
        path = self._chat_conv_path()
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def clear_chat_conversation(self) -> None:
        """Clear persisted architecture chat conversation."""
        path = self._chat_conv_path()
        if path.exists():
            path.unlink()

    def _save_chat_conversation(self, conversation: list[dict]) -> None:
        path = self._chat_conv_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(conversation, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _chat_conv_path(self) -> Path:
        return self.artifacts.skaro / "architecture" / "chat-conversation.json"

    # ── Review (existing) ──────────────────────────────

    async def run(self, feature: str | None = None, **kwargs: Any) -> PhaseResult:
        architecture_draft = kwargs.get("architecture_draft", "")
        domain_description = kwargs.get("domain_description", "")

        if not architecture_draft:
            return PhaseResult(
                success=False,
                message="Architecture draft is required. Pass it as architecture_draft.",
            )

        prompt_template = self._load_prompt_template("architecture")
        if prompt_template:
            prompt = prompt_template.replace(
                "{domain_description}", domain_description or "(not provided)"
            ).replace(
                "{architecture_draft}", architecture_draft
            )
        else:
            prompt = (
                f"Review this architecture as a senior architect.\n\n"
                f"Domain: {domain_description}\n\n"
                f"Architecture draft:\n{architecture_draft}\n\n"
                f"Provide your response in two sections:\n"
                f"## Review\n<risks, recommendations>\n\n"
                f"## Proposed Architecture\n<full improved architecture document>"
            )

        messages = self._build_messages(prompt)
        response_content = await self._stream_collect(messages)

        review_text, proposed_text = self._split_response(response_content)

        # Persist the review result so it survives page reloads.
        self.artifacts.write_architecture_review(review_text)

        return PhaseResult(
            success=True,
            message=review_text,
            data={
                "proposed_architecture": proposed_text,
            },
        )

    async def apply_review(self, architecture: str, review: str) -> str:
        """Apply review recommendations: LLM rewrites architecture.

        Returns the proposed architecture text.
        """
        prompt_template = self._load_prompt_template("architecture-apply")
        if prompt_template:
            prompt = prompt_template
        else:
            prompt = (
                "Apply review recommendations to this architecture.\n\n"
                "## Current Architecture\n{architecture}\n\n"
                "## Review\n{review}\n\n"
                "Return the complete improved architecture document."
            )

        prompt = prompt.replace("{architecture}", architecture).replace("{review}", review)
        messages = self._build_messages(prompt)
        response = await self._stream_collect(messages)
        return response.strip()

    async def generate_adrs(
        self,
        architecture: str,
        review: str = "",
        adr_template: str = "",
    ) -> list[dict[str, str]]:
        """Generate ADR proposals from architecture using LLM.

        Returns a list of ``{"title": ..., "content": ...}`` dicts.
        Raises ValueError if LLM response cannot be parsed as JSON.
        """
        prompt_template = self._load_prompt_template("adr-generate")
        if prompt_template:
            prompt = prompt_template
        else:
            prompt = (
                "Generate ADRs for this architecture. Return JSON array with "
                "number, title, content fields.\n\nArchitecture:\n{architecture}"
            )

        today = _date.today().isoformat()
        review_section = f"Architecture review feedback:\n{review}" if review.strip() else ""
        prompt = (
            prompt
            .replace("{architecture}", architecture)
            .replace("{review_section}", review_section)
            .replace("{adr_template}", adr_template)
            .replace("{today}", today)
        )

        messages = self._build_messages(prompt)
        response = await self._stream_collect(messages)

        json_match = re.search(r"```json\s*\n([\s\S]*?)\n\s*```", response)
        if not json_match:
            raise ValueError(f"LLM did not return valid JSON.\n{response}")

        return json.loads(json_match.group(1))

    @staticmethod
    def _split_response(content: str) -> tuple[str, str]:
        """Split LLM response into (review, proposed_architecture).

        Looks for '## Proposed Architecture' heading.  Everything before it
        is the review; everything after (including the heading) is the
        proposed architecture body (heading stripped).
        """
        match = _PROPOSED_HEADING_RE.search(content)
        if not match:
            # LLM didn't follow format — treat entire response as review.
            return content.strip(), ""

        review = content[: match.start()].strip()
        # Strip the heading itself from the proposed section.
        proposed_raw = content[match.end() :].strip()
        return review, proposed_raw
