"""Core git operations for Skaro automation.

Pure subprocess-based helpers so ``skaro_core`` does not depend on
``gitpython``.  The web layer (``skaro_web.api.git``) continues to use
``gitpython`` for its richer diff/status API.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("skaro_core.git_ops")


# ═══════════════════════════════════════════════════
# Low-level helpers
# ═══════════════════════════════════════════════════

def _run(
    args: list[str],
    cwd: Path,
    *,
    check: bool = True,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the result."""
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
    )


def is_git_repo(root: Path) -> bool:
    """Return True if *root* is inside a git repository."""
    try:
        result = _run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=root,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def has_commits(root: Path) -> bool:
    """Return True if the repo has at least one commit."""
    try:
        result = _run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ═══════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════

def ensure_git_init(root: Path) -> bool:
    """Initialise a git repo and create the first commit.

    Skips gracefully if:
    - ``git`` is not installed.
    - ``.git`` already exists.

    Returns True if a new repo was created and the initial commit made.
    """
    if is_git_repo(root):
        logger.debug("Git repo already exists at %s", root)
        return False

    try:
        _run(["git", "init"], cwd=root)
        logger.info("Initialized git repository at %s", root)
    except FileNotFoundError:
        logger.warning("git is not installed — skipping auto-init")
        return False
    except subprocess.CalledProcessError as exc:
        logger.warning("git init failed: %s", exc.stderr.strip())
        return False

    # Stage .skaro/ directory and .skaroignore
    paths_to_stage = []
    skaro_dir = root / ".skaro"
    if skaro_dir.is_dir():
        paths_to_stage.append(".skaro/")
    skaroignore = root / ".skaroignore"
    if skaroignore.is_file():
        paths_to_stage.append(".skaroignore")
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        paths_to_stage.append(".gitignore")

    if not paths_to_stage:
        logger.debug("Nothing to stage for initial commit")
        return True

    try:
        _run(["git", "add", *paths_to_stage], cwd=root)
        _run(
            ["git", "commit", "-m", "chore: initialize skaro project"],
            cwd=root,
        )
        logger.info("Created initial commit with %s", paths_to_stage)
        return True
    except subprocess.CalledProcessError as exc:
        logger.warning("Initial commit failed: %s", exc.stderr.strip())
        return True  # Repo was still created


def commit_skaro_init(root: Path) -> bool:
    """Commit .skaro/ artifacts in an existing repo after ``skaro init``.

    Used when the repo already existed before ``skaro init`` ran.
    Returns True if a commit was made.
    """
    if not is_git_repo(root):
        return False

    paths_to_stage = []
    skaro_dir = root / ".skaro"
    if skaro_dir.is_dir():
        paths_to_stage.append(".skaro/")
    skaroignore = root / ".skaroignore"
    if skaroignore.is_file():
        paths_to_stage.append(".skaroignore")

    if not paths_to_stage:
        return False

    try:
        _run(["git", "add", *paths_to_stage], cwd=root)

        # Check if there's anything staged
        result = _run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=root,
            check=False,
        )
        if result.returncode == 0:
            logger.debug("Nothing new to commit after skaro init")
            return False

        _run(
            ["git", "commit", "-m", "chore: initialize skaro project"],
            cwd=root,
        )
        logger.info("Committed skaro init artifacts")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.warning("Failed to commit skaro init: %s", exc)
        return False


def auto_commit_task(
    root: Path,
    task_name: str,
    *,
    push: bool = False,
) -> bool:
    """Stage all changes and commit with a task-completion message.

    Called when a task reaches the "done" state (all 4 phases complete).
    Returns True if a commit was successfully made.
    """
    if not is_git_repo(root):
        return False

    try:
        # Stage all tracked changes + new files in .skaro/
        _run(["git", "add", "-A"], cwd=root)

        # Bail out if nothing to commit
        result = _run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=root,
            check=False,
        )
        if result.returncode == 0:
            logger.debug("Nothing to commit for task %s", task_name)
            return False

        message = f'chore(skaro): complete task "{task_name}"'
        _run(["git", "commit", "-m", message], cwd=root)
        logger.info("Auto-committed task completion: %s", task_name)

        if push:
            try:
                _run(["git", "push"], cwd=root, timeout=60)
                logger.info("Auto-pushed after task %s", task_name)
            except subprocess.CalledProcessError as exc:
                logger.warning("Auto-push failed: %s", exc.stderr.strip())

        return True

    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.warning("Auto-commit failed for task %s: %s", task_name, exc)
        return False
