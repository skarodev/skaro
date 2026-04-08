"""Mixin for running shell commands with timeout and output capture.

Used by TestsPhase (task-level verify commands) and ProjectReviewPhase
(global verify commands) to avoid duplicating execution logic.
"""

from __future__ import annotations

import asyncio
import os
import platform
from typing import Awaitable, Callable

# Max time for a single verify command (seconds).
COMMAND_TIMEOUT = 120

# Callback type for streaming command output.
_OutputCallback = Callable[[str], Awaitable[None]]

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

    When ``on_output_chunk`` is set to an async callable, command output
    is streamed line-by-line via that callback (used by the web layer to
    push real-time output over WebSocket).
    """

    # Optional streaming callback — set by the web endpoint before run().
    on_output_chunk: _OutputCallback | None = None

    async def _run_commands(self, commands: list[dict[str, str]]) -> list[dict]:
        """Run a list of verify commands and return results."""
        results: list[dict] = []
        for cmd_def in commands:
            if not cmd_def.get("command", "").strip():
                continue
            result = await self._execute_command(cmd_def["name"], cmd_def["command"])
            results.append(result)
        return results

    async def _emit(self, text: str) -> None:
        """Send a chunk of output to the streaming callback, if set."""
        cb = getattr(self, "on_output_chunk", None)
        if cb is not None:
            await cb(text)

    async def _execute_command(self, name: str, command: str) -> dict:
        """Execute a single shell command and capture output."""
        try:
            env = _build_env()

            # Wrap command via execution environment (docker, prefix, etc.)
            actual_command = command
            config = getattr(self, "config", None)
            if config and hasattr(config, "execution_env"):
                actual_command = config.execution_env.build_command_wrapper(command)

            # On Windows, execute through PowerShell instead of cmd.exe
            if platform.system() == "Windows":
                # Escape embedded double quotes for PowerShell -Command
                ps_cmd = actual_command.replace('"', '\\"')
                actual_command = (
                    'powershell -NoProfile -NonInteractive -Command '
                    f'"[Console]::OutputEncoding = [Text.Encoding]::UTF8; {ps_cmd}"'
                )

            proc = await asyncio.create_subprocess_shell(
                actual_command,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.artifacts.root),
                env=env,
            )

            cb = getattr(self, "on_output_chunk", None)
            if cb is not None:
                return await self._execute_streaming(proc, name, command)

            # ── Non-streaming (original) path ──
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
            await self._emit(f"  error: {exc}\n")
            return {
                "name": name,
                "command": command,
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(exc),
            }

    async def _execute_streaming(
        self,
        proc: asyncio.subprocess.Process,
        name: str,
        command: str,
    ) -> dict:
        """Read stdout/stderr line-by-line and stream via callback."""
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []

        async def _read_stream(
            stream: asyncio.StreamReader | None,
            parts: list[str],
        ) -> None:
            if stream is None:
                return
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = _decode_output(line)
                parts.append(text)
                await self._emit(text)

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    _read_stream(proc.stdout, stdout_parts),
                    _read_stream(proc.stderr, stderr_parts),
                ),
                timeout=COMMAND_TIMEOUT,
            )
            await proc.wait()
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            await self._emit(f"  ⚠ Command timed out after {COMMAND_TIMEOUT}s\n")
            return {
                "name": name,
                "command": command,
                "success": False,
                "exit_code": -1,
                "stdout": "".join(stdout_parts)[-5000:],
                "stderr": f"Command timed out after {COMMAND_TIMEOUT}s",
            }

        stdout_text = "".join(stdout_parts)[-5000:]
        stderr_text = "".join(stderr_parts)[-5000:]

        return {
            "name": name,
            "command": command,
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": stdout_text,
            "stderr": stderr_text,
        }
