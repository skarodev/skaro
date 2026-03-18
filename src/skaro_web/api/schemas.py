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


class ConstitutionSaveBody(BaseModel):
    """Body for saving constitution, with optional preset linkage."""
    content: str
    preset_id: str | None = None


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


class ArchChatBody(BaseModel):
    """Payload for architecture generation chat."""
    message: str = Field(..., min_length=1)
    conversation: list[dict[str, str]] = Field(default_factory=list)


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


class TaskReorderBody(BaseModel):
    """Reorder tasks within a milestone."""
    milestone: str = Field(..., min_length=1)
    tasks: list[str] = Field(..., min_length=1)


class TaskFileSaveBody(BaseModel):
    """Save a task file (spec.md, plan.md, etc.)."""
    filename: str = Field(..., min_length=1)
    content: str

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        allowed = {"spec.md", "clarifications.md", "plan.md", "tasks.md"}
        if v not in allowed:
            raise ValueError(f"Cannot edit '{v}'. Allowed: {', '.join(sorted(allowed))}")
        return v


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
    scope_paths: list[str] = Field(default_factory=list)


class FixFromIssuesBody(BaseModel):
    """Start a Fix session from selected test issues."""
    issue_ids: list[str] = Field(default_factory=list)
    conversation: list[dict[str, str]] = Field(default_factory=list)
    scope_paths: list[str] = Field(default_factory=list)


class ProjectFixBody(BaseModel):
    """Payload for project-level fix chat."""
    message: str = Field(..., min_length=1)
    conversation: list[dict[str, str]] = Field(default_factory=list)
    scope_tasks: list[str] = Field(default_factory=list)
    scope_paths: list[str] = Field(default_factory=list)


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
    max_tokens: int = Field(default=16384, ge=1, le=2097152)
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


class ExecutionEnvBody(BaseModel):
    """Execution environment settings for verify commands."""
    mode: str = "host"
    docker_service: str = ""
    docker_compose_file: str = ""
    workdir: str = ""
    command_prefix: str = ""
    shell: str = ""


class ConfigUpdateBody(BaseModel):
    llm: LLMConfigBody = Field(default_factory=LLMConfigBody)
    ui: UIConfigBody = Field(default_factory=UIConfigBody)
    lang: str = "en"
    theme: str = "dark"
    project_name: str = ""
    project_description: str = ""
    roles: dict[str, RoleConfigBody | None] = Field(default_factory=dict)
    execution_env: ExecutionEnvBody = Field(default_factory=ExecutionEnvBody)

    def to_dict(self) -> dict[str, Any]:
        """Convert to plain dict for SkaroConfig.from_dict() compatibility."""
        d = self.model_dump()
        # Flatten roles: None stays None, RoleConfigBody → dict
        roles_raw = {}
        for rname, rc in d.get("roles", {}).items():
            roles_raw[rname] = rc
        d["roles"] = roles_raw
        return d


# ═══════════════════════════════════════════════════
# Git
# ═══════════════════════════════════════════════════

class GitStageBody(BaseModel):
    """Stage or unstage a list of file paths."""
    files: list[str] = Field(..., min_length=1)


class GitCommitBody(BaseModel):
    """Commit staged changes."""
    message: str = Field(..., min_length=1)
    push: bool = False


class GitCheckoutBody(BaseModel):
    """Switch or create a branch."""
    branch: str = Field(..., min_length=1)
    create: bool = False


# ═══════════════════════════════════════════════════
# Features
# ═══════════════════════════════════════════════════

class FeatureChatBody(BaseModel):
    """Payload for feature planning chat."""
    message: str = Field(..., min_length=1)
    conversation: list[dict[str, str]] = Field(default_factory=list)
    scope_paths: list[str] = Field(default_factory=list)


class FeatureUpdateBody(BaseModel):
    """Partial update for feature meta."""
    title: str | None = None
    description: str | None = None
    status: str | None = None


class FeatureProposalTask(BaseModel):
    """A task within a feature proposal."""
    name: str = ""
    milestone: str = ""
    description: str = ""
    spec: str = ""


class FeatureProposalAdr(BaseModel):
    """Optional ADR within a feature proposal."""
    title: str = ""
    content: str = ""


class FeatureConfirmBody(BaseModel):
    """Confirm a feature proposal — creates tasks, ADR, plan."""
    title: str = Field(..., min_length=1)
    description: str = ""
    plan: str = ""
    tasks: list[FeatureProposalTask] = Field(default_factory=list)
    adr: FeatureProposalAdr | None = None
