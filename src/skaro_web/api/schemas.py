"""Pydantic schemas for Skaro Web API request/response validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


# ═══════════════════════════════════════════════════
# Shared / reusable
# ═══════════════════════════════════════════════════

class ContentBody(BaseModel):
    """Generic body with a single 'content' field (constitution, architecture, devplan, ADR)."""
    content: str


class FileApplyBody(BaseModel):
    """Apply a generated file to disk."""
    filepath: str = Field(..., min_length=1)
    content: str

    @field_validator("filepath")
    @classmethod
    def forbid_path_traversal(cls, v: str) -> str:
        normalized = v.replace("\\", "/")
        if ".." in normalized.split("/"):
            raise ValueError("Path must not contain '..' components.")
        if normalized.startswith("/"):
            raise ValueError("Path must be relative, not absolute.")
        return v


# ═══════════════════════════════════════════════════
# Architecture
# ═══════════════════════════════════════════════════

class ArchReviewBody(BaseModel):
    architecture_draft: str = ""
    domain_description: str = ""


class ArchAcceptBody(BaseModel):
    proposed_architecture: str = Field(..., min_length=1)


class AdrCreateBody(BaseModel):
    title: str = Field(default="Untitled", min_length=1)


class AdrStatusBody(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid = {"proposed", "accepted", "deprecated", "superseded"}
        if v not in valid:
            raise ValueError(f"Invalid ADR status: {v}. Must be one of {valid}")
        return v


# ═══════════════════════════════════════════════════
# Development Plan
# ═══════════════════════════════════════════════════

class DevPlanTask(BaseModel):
    name: str = ""
    description: str = ""
    priority: int = 99
    dependencies: list[str] = Field(default_factory=list)
    spec: str = ""


class DevPlanMilestone(BaseModel):
    milestone_slug: str = ""
    milestone_title: str = ""
    description: str = ""
    tasks: list[DevPlanTask] = Field(default_factory=list)


class DevPlanConfirmBody(BaseModel):
    milestones: list[DevPlanMilestone] = Field(..., min_length=1)


class DevPlanUpdateBody(BaseModel):
    guidance: str = ""


class DevPlanConfirmUpdateBody(BaseModel):
    updated_devplan: str = Field(..., min_length=1)
    new_milestones: list[DevPlanMilestone] = Field(default_factory=list)


# ═══════════════════════════════════════════════════
# Tasks
# ═══════════════════════════════════════════════════

class TaskCreateBody(BaseModel):
    name: str = Field(..., min_length=1)
    milestone: str = ""


class ClarifyAnswerBody(BaseModel):
    questions: str = ""
    answers: dict[str, str] = Field(default_factory=dict)

    def parsed_answers(self) -> dict[int, str]:
        """Convert string keys to int keys for phase compatibility."""
        return {int(k): v for k, v in self.answers.items()}


class ClarifyQuestion(BaseModel):
    num: int = 0
    question: str = ""
    context: str = ""
    options: list[str] = Field(default_factory=list)
    answer: str = ""


class ClarifyDraftBody(BaseModel):
    questions: list[ClarifyQuestion] = Field(default_factory=list)

    def to_dicts(self) -> list[dict[str, Any]]:
        """Convert to plain dicts for phase compatibility."""
        return [q.model_dump() for q in self.questions]


class ImplementBody(BaseModel):
    stage: int | None = None
    source_files: dict[str, str] = Field(default_factory=dict)


class FixBody(BaseModel):
    message: str = Field(..., min_length=1)
    conversation: list[dict[str, str]] = Field(default_factory=list)


# ═══════════════════════════════════════════════════
# Verify commands (Tests phase)
# ═══════════════════════════════════════════════════

class VerifyCommandItem(BaseModel):
    """A single verify command for a task."""
    name: str = ""
    command: str = ""


class VerifyCommandsBody(BaseModel):
    """Payload for saving task-level verify commands."""
    commands: list[VerifyCommandItem] = Field(default_factory=list)


# ═══════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════

class LLMConfigBody(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    api_key: str = ""
    base_url: str | None = None
    max_tokens: int = Field(default=16384, ge=1, le=200000)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)


class RoleConfigBody(BaseModel):
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None


class UIConfigBody(BaseModel):
    auto_open_browser: bool = True


class ConfigUpdateBody(BaseModel):
    llm: LLMConfigBody = Field(default_factory=LLMConfigBody)
    ui: UIConfigBody = Field(default_factory=UIConfigBody)
    lang: str = "en"
    theme: str = "dark"
    project_name: str = ""
    project_description: str = ""
    roles: dict[str, RoleConfigBody | None] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to plain dict for SkaroConfig.from_dict() compatibility."""
        d = self.model_dump()
        # Flatten roles: None stays None, RoleConfigBody → dict
        roles_raw = {}
        for rname, rc in d.get("roles", {}).items():
            roles_raw[rname] = rc
        d["roles"] = roles_raw
        return d
