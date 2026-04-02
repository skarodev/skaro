"""Git backup utilities for Skaro artifacts.

Automatically creates git commits before LLM modifies .skaro files.
"""

import subprocess
from pathlib import Path
from datetime import datetime


def create_backup_commit(project_root: Path) -> bool:
    """Create a git commit with all .skaro changes before LLM modification.
    
    Args:
        project_root: Path to the project root (where .git and .skaro are)
        
    Returns:
        True if commit was created, False if no changes or error
    """
    skaro_dir = project_root / '.skaro'
    git_dir = project_root / '.git'
    
    # Check if both directories exist
    if not skaro_dir.exists() or not git_dir.exists():
        return False
    
    try:
        # Stage all .skaro files
        subprocess.run(
            ["git", "add", "-A", ".skaro/"],
            cwd=project_root,
            capture_output=True,
            timeout=5,
            check=False,
        )
        
        # Check if there are changes to commit
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=project_root,
            capture_output=True,
            timeout=5,
        )
        
        if result.returncode != 0:
            # There are changes - commit them
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            subprocess.run(
                ["git", "commit", "-m", f"🤖 Skaro auto-backup before LLM change ({timestamp})"],
                cwd=project_root,
                capture_output=True,
                timeout=5,
                check=False,
            )
            return True
        
        return False  # No changes to commit
        
    except Exception as e:
        # Silently ignore git errors - don't block the workflow
        print(f"[WARN] Could not create backup commit: {e}")
        return False
