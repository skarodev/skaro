Create an implementation plan for this task.

CRITICAL CONTEXT — THE IMPLEMENTOR IS AN LLM:
Each stage of this plan will be implemented by a code-generating LLM in a single pass.
This means:
- An LLM can comfortably generate 500–1500 lines of coherent code in one pass.
- Quality degrades NOT from volume, but from mixing unrelated concerns in one stage.
- Each new stage costs significant overhead: the LLM must re-read the spec, plan, constitution, architecture, and all previous AI_NOTES. Fewer stages = less wasted context.
- DO NOT split work into tiny stages of 50–100 lines. This is counterproductive.

STAGE BOUNDARIES — group by logical cohesion, not by size:
- One stage = one logically complete unit (a module, a layer, a vertical slice, an API group).
- A stage MUST produce something testable or verifiable.
- Prefer fewer, larger stages over many small ones.
- Only split when there is a real dependency: stage B literally cannot start without stage A's output.
- Typical task should have 2–5 stages, not 8–15.

IMPORTANT — PROJECT STRUCTURE:
- If the project does not yet have a directory structure, Stage 1 MUST be "Project Structure Setup": creating directories, entry points, config files, and empty modules according to the Architecture document.
- All subsequent stages MUST reference files with FULL relative paths from the project root (e.g. `src/game/collision.py`, NOT `collision.py`).
- File paths in the plan MUST match the Architecture document.

Rules:
1. Break into stages following the cohesion principle above.
2. For each stage specify:
   - **Goal**: what this stage achieves
   - **Inputs**: what files/artifacts are needed
   - **Outputs**: what files will be created/modified (FULL paths!)
   - **DoD**: Definition of Done — concrete checklist
   - **Risks**: what could go wrong
3. Specify dependencies between stages explicitly.
4. Mark stages that can run in parallel.
5. Verify the plan does NOT violate architectural invariants.
6. Verify the plan complies with constitution.

Do NOT add stages not described in the specification. Do NOT over-engineer.
Do NOT create stages with fewer than 3 output files unless there is a strong reason.

VERIFY COMMANDS — MANDATORY:
At the END of plan.md (after all stages), add a `## Verify` section with shell commands
that will be run automatically after implementation to validate correctness.

CRITICAL: Commands MUST be compatible with the user's OS and shell specified in the
ENVIRONMENT section of the system prompt. Do NOT use Unix commands on Windows or vice versa.
For example, on Windows/PowerShell use `python -m pytest` instead of `pytest`,
use semicolons instead of `&&`, and avoid Unix-only tools like `grep`, `sed`, `awk`.

Choose commands specific to THIS task's files and modules. Format as YAML list:
```
## Verify
- name: Unit tests
  command: pytest tests/test_auth.py -v
- name: Type check
  command: mypy src/auth/
- name: Lint
  command: ruff check src/auth/
```
Good verify commands: run tests for specific files, type-check specific modules, lint, build.
Bad verify commands: generic "pytest" with no path, "npm test" when the task only touches one module.
If the task produces no testable output (e.g. documentation only), you may omit this section.

Output TWO documents separated by the marker `---TASKS---`:

**Document 1: plan.md** — stages with full details:
```
## Stage 1: Project Structure Setup
**Goal:** Create the project directory structure and base files according to architecture.
**Depends on:** none
**Inputs:** Architecture document, Constitution
**Outputs:** `src/`, `tests/`, config files, entry points
**DoD:**
- [ ] Directory structure matches architecture
- [ ] Entry points created
- [ ] Config files in place
**Risks:** None

## Stage 2: <title>
**Goal:** ...
**Depends on:** Stage 1
**Inputs:** ...
**Outputs:** `src/module/file.py`, `tests/test_file.py`
**DoD:**
- [ ] check 1
- [ ] check 2
**Risks:** ...
```

At the very end of plan.md, after the last stage:
```
## Verify
- name: Unit tests
  command: pytest tests/test_<module>.py -v
- name: Type check
  command: mypy src/<module>/
```

**Document 2: tasks.md** — flat task list with checkboxes:
```
# Tasks: <task name>

## Stage 1: Project Structure Setup
- [ ] Create directory structure → `src/`, `tests/`
- [ ] Create entry point → `src/main.py`

## Stage 2: <title>
- [ ] Task description → `src/module/file.py`
- [ ] Task description → `tests/test_file.py`
```
