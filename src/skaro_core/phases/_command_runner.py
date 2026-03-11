"""Mixin for running shell commands with timeout and output capture.

Used by TestsPhase (task-level verify commands) and ProjectReviewPhase
(global verify commands) to avoid duplicating execution logic.
"""

from __future__ import annotations

import asyncio
import os
import platform

# Max time for a single verify command (seconds).
COMMAND_TIMEOUT = 120

# Windows Cyrillic fallback codepages (console OEM → ANSI).
_WIN_FALLBACK_ENCODINGS = ("cp866", "cp1251")


def _decode_output(data: bytes) -> str:
    """Decode subprocess output, handling Windows Cyrillic codepages.

    Strategy: try UTF-8 strictly first, then fall back to common
    Windows codepages (cp866 for console, cp1251 for ANSI) before
    resorting to ``errors='replace'``.
    """
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    if platform.system() == "Windows":
        for enc in _WIN_FALLBACK_ENCODINGS:
            try:
                return data.decode(enc)
            except (UnicodeDecodeError, LookupError):
                pass
    return data.decode("utf-8", errors="replace")


def _build_env() -> dict[str, str]:
    """Build subprocess environment with UTF-8 forced on Windows."""
    env = os.environ.copy()
    if platform.system() == "Windows":
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        # Many CLI tools respect these variables and switch to UTF-8
        env["PYTHONLEGACYWINDOWSSTDIO"] = "0"
    return env


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
            env = _build_env()

            # On Windows, force console to UTF-8 via chcp 65001
            actual_command = command
            if platform.system() == "Windows":
                actual_command = f"chcp 65001 >nul 2>&1 && {command}"

            proc = await asyncio.create_subprocess_shell(
                actual_command,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.artifacts.root),
                env=env,
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

            stdout_text = _decode_output(stdout)[-5000:]
            stderr_text = _decode_output(stderr)[-5000:]

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
