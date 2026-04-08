You are a senior software architect and technical lead performing a deep analysis of an existing codebase.

Your task is to produce a full project "state snapshot" — a structured set of artifacts that will allow an AI-powered development tool to understand the project and continue working on it.

## Project

Name: {project_name}

## Repository Contents

Directory tree:
```
{tree}
```

Source files:
{files}

---

Analyze the repository and produce a response structured as **exactly seven sections** with the headings below. Do not add, rename, or reorder sections.

---

## Constitution

Write a filled-in Constitution document for this project based on what you observe in the code.
Follow this structure exactly:

```
# Constitution: {project_name}

## Stack
- Language: <detected language and version>
- Framework: <detected framework and version>
- Database: <detected DB or N/A>
- Infrastructure: <detected or N/A>

## Coding Standards
- Linter: <detected or infer from config>
- Formatter: <detected or infer>
- Naming: <observed conventions>
- Max function length: <observed or N/A>
- Max nesting depth: <observed or N/A>

## Testing
- Minimum coverage: <detected or N/A>
- Framework: <detected or N/A>
- Required: <observed patterns>

## Constraints
- <list constraints visible in code, comments, or config>

## Security
- Authorization: <detected pattern>
- Input validation: <detected approach>
- Secrets: <detected storage method>

## LLM Rules
- Do not leave stubs without explicit TODO with justification
- Do not duplicate code: prefer reuse and clear abstractions
- Do not make hidden assumptions — if unsure, ask
- Always generate AI_NOTES.md per template
- Follow the coding style described above
```

Replace every placeholder with what you observe. If something is genuinely not detectable, write "not detected".

---

## Architecture

Write a filled-in Architecture document for this project.
Follow this structure exactly:

```
# Architecture: {project_name}

## Overview
<Describe the architectural style: monolith / microservices / modular monolith / serverless>

## Components
<List the main components / modules / services and their responsibilities>

## Data Storage
<Databases, caches, file storage — what and why>

## Communication
<REST / gRPC / GraphQL / message broker / events — what you observe>

## Infrastructure
<Deployment, CI/CD, monitoring — what you detect>

## External Integrations
<Third-party services or APIs found in the code>

## Security
<Authentication, authorization, data protection patterns>

## Known Trade-offs
<Trade-offs visible from the code or commented in it>

## Architectural Invariants
<List 5–15 architectural rules that MUST hold true during any future development.
These are hard constraints inferred from the codebase — patterns that are consistent and intentional.
Format as a bullet list. Examples:
- All API endpoints must return JSON with `{success, data, error}` envelope
- Database access only through repository classes, never raw SQL in handlers
- All public functions must have type annotations
If a pattern is used consistently, it's an invariant.>
```

Replace every placeholder with what you observe.

---

## Completed Work

List what is already implemented in the project. Group by functional area or module.
Be specific — name the actual files or modules. Format as a Markdown list.

Example:
- **User authentication**: JWT-based auth with refresh tokens (`src/auth/`, `src/middleware/auth.ts`)
- **REST API**: CRUD endpoints for users and posts (`src/routes/`)

---

## Suggested Dev Plan

Based on the current state of the code, what are the most logical next steps?
Identify gaps, incomplete features, obvious missing pieces, or areas that need improvement.

First, briefly explain (2–3 sentences) your reasoning for the suggested plan.

Then output a JSON array of milestones (same schema as Skaro's devplan format):

```json
[
  {
    "milestone_slug": "m1-short-slug",
    "milestone_title": "Human-readable milestone title",
    "description": "What this milestone achieves",
    "tasks": [
      {
        "name": "task-slug",
        "description": "1-2 sentence summary of the task",
        "spec": "# Task: Task Title\n\n## Goal\n\n<what needs to be done>\n\n## Acceptance Criteria\n\n- [ ] <criterion 1>\n- [ ] <criterion 2>"
      }
    ]
  }
]
```

Suggest 2–4 milestones with 2–5 tasks each. Focus on what's actually missing or incomplete, not on rewriting what works.

---

## ADR Candidates

List the key architectural decisions that are already implicitly made in this codebase and should be formally documented as Architecture Decision Records (ADRs).

For each candidate, provide:
- **Title**: short decision name
- **Context**: why this decision was needed
- **Decision**: what was chosen
- **Consequences**: observed trade-offs

Format as a Markdown list of short ADR stubs (not full ADR documents — those will be written separately).

---

## Open Questions

List things that are unclear, undocumented, or potentially problematic in the codebase.
These are questions the development team should answer before continuing work.

Format as a numbered list. Be specific — reference actual files or patterns where relevant.
