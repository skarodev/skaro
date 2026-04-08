You are updating an existing development plan for a software project.

You have access to:
- The current devplan.md (milestones, tasks, statuses)
- The actual state of all tasks (which phases are complete, stages progress)
- The project architecture
- User guidance on what to change

User guidance: {user_guidance}

Your tasks:
1. **Sync statuses** — update task statuses based on actual progress (e.g., if a task has completed implement phase, mark it as "done" or "in-progress")
2. **Re-prioritize** — if user guidance or project state suggests reordering, adjust priorities and milestone assignments
3. **Add tasks** — if the user requests new tasks or if you identify gaps, add them to appropriate milestones
4. **Cut tasks** — if the user wants to remove tasks, mark them as "cut" with a reason
5. **Reorganize milestones** — move tasks between milestones or create new milestones if appropriate
6. **Update changelog** — add an entry with today's date describing what changed

Return TWO things:

### 1. Updated devplan.md
The FULL updated development plan inside ```markdown fences. This must be a complete document (not a diff). Keep the same structure:
- Title, overview
- Milestones with task tables (columns: #, Task, Status, Dependencies, Description)
- Status legend
- Change log with new entry

### 2. New tasks (optional)
If there are NEW tasks that don't exist yet in the project (no directory in .skaro/milestones/), return them as a JSON array inside ```json fences:
```json
[
  {
    "milestone_slug": "01-foundation",
    "milestone_title": "Foundation",
    "tasks": [
      {
        "name": "task-slug",
        "description": "What this task does",
        "spec": "# Specification: task-slug\n\n## Context\n..."
      }
    ]
  }
]
```
If no new tasks need to be created, do NOT include a JSON block.

Rules:
- Do NOT invent changes the user didn't ask for (beyond status sync)
- Keep existing tasks unless explicitly asked to remove them
- Preserve task names/slugs exactly — they map to directories
- Use statuses: idea, planned, in-progress, done, cut
