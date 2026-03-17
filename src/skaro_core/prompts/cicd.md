Generate a complete CI/CD pipeline configuration based on the project details.

Requirements:
1. **Lint stage** — run the project's linter (from constitution)
2. **Test stage** — run all tests with coverage
3. **Build stage** — build artifacts if applicable
4. **Deploy stage** — placeholder with clear TODO comments

Rules:
- Use the detected CI platform syntax
- Include caching for dependencies
- Set appropriate triggers (push to main, PRs)
- Include environment variables as placeholders
- Add matrix builds if multiple versions detected
- Include security scanning if constitution mentions it

Return ONLY the pipeline YAML configuration.
Add comments explaining each section.
If multiple workflow files are needed, prefix each with:
# filename.yml
