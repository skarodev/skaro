Based on the project constitution and architecture, create a development plan.

Organize the work into MILESTONES — logical stages of the project. Each milestone groups related tasks that together achieve a coherent goal (e.g., "Foundation", "MVP", "Integrations").

Tasks within milestones can be anything: project setup, feature development, infrastructure, refactoring. A task is a unit of work, not necessarily a "feature".

For EACH milestone, provide:
1. **milestone_slug** — directory name with numeric prefix (e.g. `01-foundation`, `02-mvp`)
2. **milestone_title** — human-readable title
3. **description** — 1–2 sentences: what completing this milestone achieves
4. **tasks** — array of tasks within this milestone

For EACH task, provide:
1. **name** — directory slug (lowercase, hyphens only, e.g. `project-setup`, `user-auth`)
2. **description** — 1–2 sentences explaining what this task does and why
3. **priority** — implementation order within the milestone (1 = first)
4. **dependencies** — names of tasks this depends on (empty array if none)
5. **spec** — a FULL pre-filled specification in markdown

Each spec MUST follow this structure:
{spec_template}

Rules:
- If a "COMPLETED WORK" section, "Project File Tree", or "Project API Index" is provided in context, you MUST account for existing code — do NOT plan tasks that recreate already-implemented functionality
- First milestone should contain foundational work: project structure, configs, base models
- Subsequent milestones build on the foundation with functional tasks
- Order tasks so that dependencies come first
- Specs should be detailed enough for meaningful Clarify phase
- Include concrete functional requirements with IDs (FR-01, FR-02, ...)
- Include user scenarios with clear actor → action → outcome (where applicable)
- Include non-functional requirements where relevant
- List acceptance criteria as checkboxes
- Mark open questions that need clarification
- Do NOT over-engineer: keep tasks focused and scoped

Return ONLY a single JSON array wrapped in ```json fences. Each element is a milestone object:
```json
[
  {
    "milestone_slug": "01-foundation",
    "milestone_title": "Foundation",
    "description": "Project structure and core components",
    "tasks": [
      {
        "name": "project-setup",
        "description": "Create project structure, configs, entry points",
        "priority": 1,
        "dependencies": [],
        "spec": "# Specification: project-setup\n\n## Context\n..."
      }
    ]
  }
]
```
IMPORTANT: Return exactly ONE ```json ... ``` block containing ONE array. Do NOT split the response into multiple JSON blocks.
