"""Update checker for Skaro.

Checks PyPI for the latest version, detects installation method,
and provides appropriate upgrade instructions.

Cache is stored in ``~/.skaro/update-check.json`` with a configurable TTL
so that network calls don't slow down every CLI invocation.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

PYPI_URL = "https://pypi.org/pypi/skaro/json"
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours
DOCS_UPDATE_URL = "https://docs.skaro.dev/cli/update"

InstallMethod = Literal["venv", "pipx", "unknown"]


@dataclass
class UpdateCheckResult:
    """Result of an update check."""

    current_version: str
    latest_version: str | None = None
    has_update: bool = False
    install_method: InstallMethod = "unknown"
    update_instruction: str = ""
    docs_url: str = DOCS_UPDATE_URL
    error: str | None = None
    checked_at: float = field(default_factory=time.time)


# ── Version helpers ────────────────────────────


def get_current_version() -> str:
    """Return the currently installed package version (single source of truth)."""
    try:
        from importlib.metadata import version

        return version("skaro")
    except Exception:
        return "0.0.0"


# ── Install method detection ───────────────────


def _skaro_home() -> Path:
    """Return the Skaro home directory (``~/.skaro`` by default)."""
    return Path(os.environ.get("SKARO_HOME", Path.home() / ".skaro"))


def detect_install_method() -> InstallMethod:
    """Detect how Skaro was installed.

    Returns:
        ``"venv"``  — installed in ``~/.skaro/venv`` via ``install.ps1`` / ``install.sh``
        ``"pipx"``  — installed via ``pipx install skaro``
        ``"unknown"``— could not determine; fall back to generic instructions
    """
    exe = Path(sys.executable).resolve()

    # Check if running inside ~/.skaro/venv
    venv_dir = _skaro_home() / "venv"
    try:
        if venv_dir.exists() and exe.is_relative_to(venv_dir.resolve()):
            return "venv"
    except (ValueError, OSError):
        pass

    # Check for pipx: the executable typically lives in ~/.local/pipx/venvs/skaro/
    # or on Windows: %USERPROFILE%\.local\pipx\venvs\skaro\
    exe_str = str(exe).lower()
    if "pipx" in exe_str:
        return "pipx"

    return "unknown"


def get_update_instruction(method: InstallMethod) -> str:
    """Return the shell command to update Skaro for the given install method."""
    if method == "venv":
        venv_pip = _skaro_home() / "venv"
        if sys.platform == "win32":
            pip_path = venv_pip / "Scripts" / "pip.exe"
        else:
            pip_path = venv_pip / "bin" / "pip"
        return f'"{pip_path}" install --upgrade skaro'

    if method == "pipx":
        return "pipx upgrade skaro"

    # Fallback: show both common options
    return f"See {DOCS_UPDATE_URL}"


# ── PyPI check ─────────────────────────────────


def _fetch_latest_version() -> str | None:
    """Fetch the latest version string from PyPI. Returns None on failure."""
    try:
        import httpx

        resp = httpx.get(PYPI_URL, timeout=5, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        return data["info"]["version"]
    except Exception as exc:
        logger.debug("Failed to fetch latest version from PyPI: %s", exc)
        return None


def _is_newer(latest: str, current: str) -> bool:
    """Compare two PEP 440 version strings. Returns True if *latest* > *current*."""
    try:
        from packaging.version import Version

        return Version(latest) > Version(current)
    except Exception:
        pass

    # Fallback: simple tuple comparison for X.Y.Z versions
    try:
        def _parts(v: str) -> tuple[int, ...]:
            return tuple(int(x) for x in v.strip().split("."))

        return _parts(latest) > _parts(current)
    except (ValueError, TypeError):
        return False


# ── Cache ──────────────────────────────────────


def _cache_path() -> Path:
    return _skaro_home() / "update-check.json"


def _read_cache() -> UpdateCheckResult | None:
    """Read cached check result if it exists and hasn't expired."""
    path = _cache_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        checked_at = data.get("checked_at", 0)
        if time.time() - checked_at > CACHE_TTL_SECONDS:
            return None
        return UpdateCheckResult(**{
            k: v for k, v in data.items() if k in UpdateCheckResult.__dataclass_fields__
        })
    except Exception:
        return None


def _write_cache(result: UpdateCheckResult) -> None:
    """Persist the check result to disk."""
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(result)), encoding="utf-8")
    except Exception as exc:
        logger.debug("Failed to write update cache: %s", exc)


# ── Public API ─────────────────────────────────


def check_for_update(*, force: bool = False) -> UpdateCheckResult:
    """Check whether a newer version of Skaro is available on PyPI.

    Uses a local cache (TTL 24 h) to avoid hitting the network on every call.
    Pass ``force=True`` to bypass the cache.

    Returns an :class:`UpdateCheckResult` with all relevant info.
    """
    if not force:
        cached = _read_cache()
        if cached is not None:
            return cached

    current = get_current_version()
    method = detect_install_method()
    instruction = get_update_instruction(method)

    result = UpdateCheckResult(
        current_version=current,
        install_method=method,
        update_instruction=instruction,
    )

    latest = _fetch_latest_version()
    if latest is None:
        result.error = "Could not reach PyPI"
    else:
        result.latest_version = latest
        result.has_update = _is_newer(latest, current)

    _write_cache(result)
    return result
