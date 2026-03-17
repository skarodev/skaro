"""CI/CD phase: generate deployment pipelines after tests pass.

Runs after Tests to generate:
- GitHub Actions workflows
- GitLab CI pipelines
- Docker configuration
- Environment setup scripts

Results are saved to .github/workflows/ or .gitlab-ci.yml.
"""

from __future__ import annotations

from typing import Any

from skaro_core.llm.base import LLMMessage
from skaro_core.phases.base import BasePhase, PhaseResult, strip_outer_md_fence


class CICDPhase(BasePhase):
    phase_name = "cicd"

    async def run(self, task: str, **kwargs: Any) -> PhaseResult:
        """Generate CI/CD configuration based on project constitution and tests."""
        constitution = self.artifacts.read_constitution()
        architecture = self.artifacts.read_architecture()

        # Check for existing test configuration
        test_results = self._find_test_config()

        # Detect CI platform preference
        ci_platform = self._detect_ci_platform()

        prompt_template = self._load_prompt_template("cicd")
        if not prompt_template:
            prompt_template = self._default_prompt()

        # Gather project source summary
        source_summary = self._summarize_source()

        context_parts = []
        if constitution.strip():
            context_parts.append(f"## Constitution\n\n{constitution}")
        if architecture.strip():
            context_parts.append(f"## Architecture\n\n{architecture}")
        context_parts.append(f"## CI Platform Detected: {ci_platform}")
        context_parts.append(f"## Test Configuration\n\n{test_results}")
        context_parts.append(f"## Source Summary\n\n{source_summary}")

        context = "\n\n---\n\n".join(context_parts)
        full_prompt = f"{prompt_template}\n\n---\n\n{context}"

        llm = self._get_llm(task)
        response = await llm.complete([
            LLMMessage(role="user", content=full_prompt),
        ])

        pipeline_config = strip_outer_md_fence(response.text)

        # Save pipeline files
        artifacts_created = self._save_pipeline_files(pipeline_config, ci_platform)

        return PhaseResult(
            success=True,
            message=f"CI/CD pipeline generated for {ci_platform}",
            artifacts_created=artifacts_created,
            data={"platform": ci_platform, "config": pipeline_config},
        )

    def _detect_ci_platform(self) -> str:
        """Detect which CI platform to target."""
        project = self.project_root
        if project:
            if (project / ".github").exists():
                return "github-actions"
            if (project / ".gitlab-ci.yml").exists():
                return "gitlab-ci"
            if (project / "bitbucket-pipelines.yml").exists():
                return "bitbucket-pipelines"
        return "github-actions"  # default

    def _find_test_config(self) -> str:
        """Find test configuration in project."""
        project = self.project_root
        if not project:
            return "No test configuration found"

        configs = []
        for name in ["pytest.ini", "pyproject.toml", "setup.cfg", "jest.config.js",
                      "vitest.config.ts", "go.mod", "Cargo.toml", "pom.xml"]:
            path = project / name
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8")[:500]
                    configs.append(f"### {name}\n```\n{content}\n```")
                except OSError:
                    pass

        return "\n\n".join(configs) if configs else "No test configuration found"

    def _summarize_source(self) -> str:
        """Create a brief summary of project source structure."""
        project = self.project_root
        if not project:
            return "No project root"

        from skaro_core.phases.base import SKIP_DIRS, SOURCE_EXTENSIONS

        file_counts: dict[str, int] = {}
        for path in project.rglob("*"):
            if path.is_file():
                # Skip ignored dirs
                if any(skip in path.parts for skip in SKIP_DIRS):
                    continue
                ext = path.suffix
                if ext in SOURCE_EXTENSIONS:
                    file_counts[ext] = file_counts.get(ext, 0) + 1

        if not file_counts:
            return "No source files found"

        lines = [f"{ext}: {count} files" for ext, count in sorted(file_counts.items())]
        total = sum(file_counts.values())
        return f"Total: {total} source files\n" + "\n".join(lines)

    def _save_pipeline_files(self, config: str, platform: str) -> list[str]:
        """Save generated pipeline files to project."""
        project = self.project_root
        if not project:
            return []

        created = []

        if platform == "github-actions":
            workflows_dir = project / ".github" / "workflows"
            workflows_dir.mkdir(parents=True, exist_ok=True)

            # Try to extract individual workflow files from config
            workflows = self._split_workflows(config)
            for filename, content in workflows.items():
                path = workflows_dir / filename
                path.write_text(content, encoding="utf-8")
                created.append(f".github/workflows/{filename}")

        elif platform == "gitlab-ci":
            path = project / ".gitlab-ci.yml"
            path.write_text(config, encoding="utf-8")
            created.append(".gitlab-ci.yml")

        if not created:
            # Fallback: save raw config
            path = project / ".skaro" / "cicd-output.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(config, encoding="utf-8")
            created.append(".skaro/cicd-output.md")

        return created

    def _split_workflows(self, config: str) -> dict[str, str]:
        """Split LLM output into separate workflow files."""
        workflows = {}
        current_name = "ci.yml"
        current_lines: list[str] = []

        for line in config.splitlines():
            # Detect workflow file markers
            if line.startswith("# ") and (line.endswith(".yml") or line.endswith(".yaml")):
                if current_lines:
                    workflows[current_name] = "\n".join(current_lines)
                current_name = line[2:].strip()
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            workflows[current_name] = "\n".join(current_lines)

        return workflows

    def _default_prompt(self) -> str:
        return """Generate a complete CI/CD pipeline configuration based on the project details.

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
# filename.yml"""
