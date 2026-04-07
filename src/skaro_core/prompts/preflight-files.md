You are analyzing which source files from the project repository are needed to work on this task.

You have access to:
1. An AST index showing all classes, functions, and type signatures in the codebase
2. A project file tree showing all files
3. The task context (specification, plan, error messages, etc.)

Your job: determine which source files the developer (or you) would need to READ IN FULL to properly work on this task — to understand existing implementations, dependencies, data models, APIs, configs, etc.

Rules:
- Select files that are DIRECTLY relevant: files that will be modified, files they import from, config files they depend on
- Do NOT select test files unless the task is specifically about fixing tests
- Do NOT select files that are only tangentially related
- Prefer fewer, more relevant files over many loosely related ones
- Maximum 20 files
- Use exact paths from the file tree

Return ONLY a JSON array of file paths — no preamble, no markdown fences, no explanation.

Example:
["src/auth/middleware.py", "src/models/user.py", "src/config.py"]

CRITICAL: Return raw JSON array only. No ```json fences. No text before or after.
