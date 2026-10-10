import os
import subprocess
from typing import Dict, Optional


class LocalGitError(Exception):
    pass


def run_git_command(args: list[str], cwd: Optional[str] = None) -> str:
    """Executes a git command and returns stdout."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except FileNotFoundError:
        raise LocalGitError("Git is not installed or not in PATH.")
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() or e.stdout.strip()
        raise LocalGitError(f"Git command failed: {error_msg}")


def get_diff_from_file(file_path: str) -> str:
    """Reads git diff text from an external file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Diff file '{file_path}' does not exist.")
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def get_local_git_context(cwd: Optional[str] = None) -> Dict[str, str]:
    """Retrieves local repository branch name and recent commit info for context."""
    context = {}
    try:
        branch = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd).strip()
        context["current_branch"] = branch
    except Exception:
        context["current_branch"] = "unknown"

    try:
        recent_commit = run_git_command(["log", "-1", "--pretty=format:%h - %s (%an)"], cwd=cwd).strip()
        context["latest_commit"] = recent_commit
    except Exception:
        context["latest_commit"] = "none"

    return context


def get_local_diff(base_branch: Optional[str] = None, staged_only: bool = False, cwd: Optional[str] = None) -> str:
    """
    Retrieves the git diff for local changes:
    - If base_branch is specified: git diff base_branch...HEAD
    - If staged_only: git diff --cached
    - Otherwise: git diff HEAD (or working tree against latest commit)
    """
    if base_branch:
        return run_git_command(["diff", f"{base_branch}...HEAD"], cwd=cwd)
    elif staged_only:
        return run_git_command(["diff", "--cached"], cwd=cwd)
    else:
        # First check diff against HEAD, if no commit yet check unstaged
        try:
            diff = run_git_command(["diff", "HEAD"], cwd=cwd)
            if not diff.strip():
                # Maybe untracked or only unstaged
                diff = run_git_command(["diff"], cwd=cwd)
            return diff
        except LocalGitError:
            return run_git_command(["diff"], cwd=cwd)
