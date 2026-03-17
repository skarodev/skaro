"""Analytics phase: pre-clarification analysis of task specification.

Runs before Clarify to provide:
- Complexity assessment
- Risk identification
- Dependency analysis
- Technology fit evaluation
- Estimated effort breakdown

Results are saved to analytics-report.md in the task directory.
"""

from __future__ import annotations

from typing import Any

from skaro_core.llm.base import LLMMessage
from skaro_core.phases.base import BasePhase, PhaseResult, strip_outer_md_fence

ANALYTICS_FILENAME = "analytics-report.md"


class AnalyticsPhase(BasePhase):
    phase_name = "analytics"

    async def run(self, task: str, **kwargs: Any) -> PhaseResult:
        """Run analytics on task specification."""
        spec = self.artifacts.find_and_read_task_file(task, "spec.md")
        if not spec:
            return PhaseResult(
                success=False,
                message=f"No spec.md found for task '{task}'",
            )

        # Gather context
        constitution = self.artifacts.read_constitution()
        architecture = self.artifacts.read_architecture()

        prompt_template = self._load_prompt_template("analytics")
        if not prompt_template:
            prompt_template = self._default_prompt()

        # Build context for LLM
        context_parts = [f"## Specification\n\n{spec}"]
        if constitution.strip():
            context_parts.append(f"## Constitution\n\n{constitution}")
        if architecture.strip():
            context_parts.append(f"## Architecture\n\n{architecture}")

        context = "\n\n---\n\n".join(context_parts)
        full_prompt = f"{prompt_template}\n\n---\n\n{context}"

        llm = self._get_llm(task)
        response = await llm.complete([
            LLMMessage(role="user", content=full_prompt),
        ])

        report = strip_outer_md_fence(response.text)

        # Save report
        task_dir = self.artifacts.find_task_dir(task)
        if task_dir:
            report_path = task_dir / ANALYTICS_FILENAME
            report_path.write_text(report, encoding="utf-8")

        # Extract risk level from report
        risk_level = self._extract_risk_level(report)

        return PhaseResult(
            success=True,
            message=f"Analytics complete — risk level: {risk_level}",
            artifacts_created=[ANALYTICS_FILENAME] if task_dir else [],
            data={"risk_level": risk_level, "report": report},
        )

    def _extract_risk_level(self, report: str) -> str:
        """Extract risk level from generated report."""
        report_lower = report.lower()
        if "critical" in report_lower or "🔴" in report:
            return "CRITICAL"
        elif "high" in report_lower or "🟠" in report:
            return "HIGH"
        elif "medium" in report_lower or "🟡" in report:
            return "MEDIUM"
        elif "low" in report_lower or "🟢" in report:
            return "LOW"
        return "UNKNOWN"

    def _default_prompt(self) -> str:
        return """Analyze this task specification and produce a structured analytics report.

Your report MUST include these sections:

## 1. Complexity Assessment
- Overall complexity: LOW / MEDIUM / HIGH / CRITICAL
- Key complexity drivers
- Estimated implementation stages count

## 2. Risk Analysis
List each risk with:
- Risk description
- Probability: LOW / MEDIUM / HIGH
- Impact: LOW / MEDIUM / HIGH / CRITICAL
- Mitigation strategy

## 3. Dependencies
- External services/APIs required
- Internal modules affected
- Third-party libraries needed

## 4. Technology Fit
Rate 1-5 how well the current stack fits this task.
Flag any mismatches or needed additions.

## 5. Effort Breakdown
Per-stage effort estimate:
- Research/Analysis: X hours
- Design: X hours
- Implementation: X hours
- Testing: X hours
- Total: X hours

## 6. Recommendations
- Suggested approach (top-down / bottom-up / iterative)
- Potential simplifications
- Things to clarify before starting

Return ONLY the markdown report. No preamble."""
