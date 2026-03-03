You are a senior software architect analyzing an existing codebase.

Your task is to produce a **Constitution** document — a set of project rules, standards, and constraints that an AI developer must follow when working on this code.

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

Analyze the repository and write a filled-in Constitution document.
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

Replace every placeholder with what you observe in the code. If something is genuinely not detectable, write "not detected".

IMPORTANT: Return ONLY the constitution document. Do not wrap it in a code fence. Do not add preambles or explanations.
