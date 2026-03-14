You are a senior software architect analyzing an existing codebase.

Your task is to produce a **Completed Work** document — a detailed inventory of everything that is already implemented in this project. This document will be used by an AI development tool to avoid duplicating existing functionality when planning future work.

## Project

Name: {project_name}

## Project Constitution (generated from source code)

{constitution}

## Architecture (generated from source code)

{architecture}

## Repository Structure

```
{tree}
```

## Source Files

{files}

---

Analyze the repository and list everything that is already implemented. Be thorough and specific — name actual files, modules, classes, and functions.

Group by functional area or module. For each area, describe:
- What is implemented (features, APIs, logic)
- Key files and their roles
- Current state (complete, partial, stub)

Format as a Markdown document:

```
# Completed Work

## <Functional Area 1>
- **<Feature/Component>**: <what it does> (`path/to/file.py`, `path/to/other.py`)
  - Status: complete | partial | stub
  - Details: <specific classes, functions, endpoints implemented>

## <Functional Area 2>
...
```

Rules:
- Be EXHAUSTIVE — list every implemented feature, not just the major ones
- Reference ACTUAL file paths from the repository
- Distinguish between complete implementations and stubs/TODOs
- Note any TODO comments, FIXME markers, or incomplete implementations you find
- Do NOT suggest improvements or next steps — only document what EXISTS

IMPORTANT: Return ONLY the completed work document. Do not wrap it in a code fence. Do not add preambles or explanations.
