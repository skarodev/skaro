You MUST implement ONLY Stage {stage} of the plan. Nothing else.

Here is the section of the plan you must implement:

{stage_section}

RULES:
1. Implement EXACTLY what Stage {stage} describes. Do NOT implement other stages.
2. Every file MUST use FULL relative paths from project root (e.g. `src/game/collision.ts`, NOT `collision.ts`).
3. Match the project structure from Architecture. If "Current project files" are provided, follow the same structure.
4. NEVER place source files in the project root — only config files like `package.json`, `tsconfig.json`, `vite.config.ts` go in root.
5. Output ONLY files you create or modify in this stage.
6. Do NOT duplicate code that already exists — import from existing modules.
7. Do NOT leave stubs, placeholders, or TODOs.
8. If unsure about a decision, list alternatives in AI_NOTES — do NOT make hidden assumptions.
9. Follow coding standards from constitution.
10. Check compliance with architectural invariants.

OUTPUT FORMAT — each file wrapped in file markers with the FULL path:

--- FILE: src/game/module.ts ---
// file content here
--- END FILE ---

--- FILE: tests/module.test.ts ---
// test content here
--- END FILE ---

LAST file must be AI_NOTES:

--- FILE: AI_NOTES.md ---
# AI_NOTES — Stage {stage}: <title from plan>

## What was done
- <list of changes>

## Why this approach
- <rationale>

## Files created / modified
| File | Action | Description |
|---|---|---|
| `src/game/module.ts` | created | what and why |

## Risks and limitations
- <known issues>

## Invariant compliance
- [ ] <invariant> — respected / violated (explain)

## How to verify
1. <command or manual check>
--- END FILE ---
