You are creating a development plan for an EXISTING project that has been imported into Skaro.

CRITICAL: This project already has working code. Your plan must NOT recreate what already exists.

## What is already built

The "COMPLETED WORK" section in the system context describes everything that is already implemented.
The "Project File Tree" and "Project API Index" sections below show the current codebase structure and API surface.

Your job is to plan ONLY:
1. **Missing features** — functionality described in the constitution/architecture but not yet implemented
2. **Incomplete implementations** — stubs, TODOs, partial features that need finishing
3. **Improvements** — refactoring, performance, security hardening, test coverage gaps
4. **New capabilities** — logical next steps that build on the existing foundation

DO NOT plan:
- Project setup, directory structure creation, or boilerplate — these already exist
- Re-implementation of existing features — reference them as dependencies instead
- Foundation/infrastructure work that is already in place

Organize the work into MILESTONES — logical stages of development. Each milestone groups related tasks that together achieve a coherent goal.

For EACH milestone, provide:
1. **milestone_slug** — directory name with numeric prefix (e.g. `01-improvements`, `02-new-features`)
2. **milestone_title** — human-readable title
3. **description** — 1–2 sentences: what completing this milestone achieves
4. **tasks** — array of tasks within this milestone

For EACH task, provide:
1. **name** — directory slug (lowercase, hyphens only, e.g. `add-caching`, `fix-auth-flow`)
2. **description** — 1–2 sentences explaining what this task does and why
3. **priority** — implementation order within the milestone (1 = first)
4. **dependencies** — names of tasks this depends on (empty array if none)
5. **spec** — a FULL pre-filled specification in markdown

Each spec MUST follow this structure:
{spec_template}

In each spec's Context section, explicitly reference the existing code that this task builds upon or modifies. Use actual file paths.

Rules:
- Reference existing modules by their actual paths when describing dependencies
- Specs should mention which existing files will be MODIFIED vs which are NEW
- Include concrete functional requirements with IDs (FR-01, FR-02, ...)
- Include acceptance criteria as checkboxes
- Mark open questions that need clarification
- Do NOT over-engineer: keep tasks focused and scoped
- First milestone should address the most impactful improvements or missing pieces

Return ONLY a single JSON array wrapped in ```json fences. Each element is a milestone object:
```json
[
  {
    "milestone_slug": "01-improvements",
    "milestone_title": "Code Quality & Gaps",
    "description": "Address missing tests, TODOs, and incomplete features",
    "tasks": [
      {
        "name": "add-missing-tests",
        "description": "Add unit tests for modules X and Y that currently lack coverage",
        "priority": 1,
        "dependencies": [],
        "spec": "# Specification: add-missing-tests\n\n## Context\nModules `src/x.py` and `src/y.py` exist but have no corresponding tests...\n..."
      }
    ]
  }
]
```
IMPORTANT: Return exactly ONE ```json ... ``` block containing ONE array. Do NOT split the response into multiple JSON blocks.
