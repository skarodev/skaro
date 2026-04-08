"""Autopilot — run all incomplete tasks end-to-end via SSE.

Flow per task:
  1. Clarify  — auto-answer via LLM
  2. Plan     — generate implementation plan
  3. Implement — stages 1..N with auto-apply (truncation-safe)
  4. Tests    — run & confirm only if passed

On any error the autopilot stops and reports the failure.
A stop signal (asyncio.Event) lets the user abort mid-flight,
including cancellation of in-progress LLM streams.
"""

from .router import router

__all__ = ["router"]
