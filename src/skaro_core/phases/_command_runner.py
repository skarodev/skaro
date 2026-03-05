"""Mixin for running shell commands with timeout and output capture.

Used by TestsPhase (task-level verify commands) and ProjectReviewPhase
(global verify commands) to avoid duplicating execution logic.
"""

from __future__ import annotations

import asyncio

# Max time for a single verify command (seconds).
COMMAND_TIMEOUT = 120


class CommandRunnerMixin:
    """Run shell commands inside the project directory.

    Requires ``self.artifacts.root`` (provided by :class:`BasePhase`).
    """

    async def _run_commands(self, commands: list[dict[str, str]]) -> list[dict]:
        """Run a list of verify commands and return results."""
        results: list[dict] = []
        for cmd_def in commands:
            if not cmd_def.get("command", "").strip():
                continue
            result = await self._execute_command(cmd_def["name"], cmd_def["command"])
            results.append(result)
        return results

    async def _execute_command(self, name: str, command: str) -> dict:
        """Execute a single shell command and capture output."""
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.artifacts.root),
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=COMMAND_TIMEOUT
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return {
                    "name": name,
                    "command": command,
                    "success": False,
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Command timed out after {COMMAND_TIMEOUT}s",
                }

            stdout_text = stdout.decode("utf-8", errors="replace")[-5000:]
            stderr_text = stderr.decode("utf-8", errors="replace")[-5000:]

            return {
                "name": name,
                "command": command,
                "success": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": stdout_text,
                "stderr": stderr_text,
            }
        except Exception as exc:
            return {
                "name": name,
                "command": command,
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(exc),
            }
