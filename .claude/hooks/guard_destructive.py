"""PreToolUse hook: stop Claude from deleting or overwriting protected files.

Reads the hook payload from stdin and exits 2 (blocking) when:
  - a Bash/PowerShell command looks destructive and names a protected file,
    either directly or through a glob that could expand to one (e.g. *.db);
  - a Write/Edit/MultiEdit/NotebookEdit targets a protected file, including
    the hook configuration itself, so the guard cannot be switched off.
Exits 0 otherwise. Any crash exits non-zero, and settings.json turns that into
exit 2, so the guard fails closed.

This matches command text, so it is a safety net against accidents, not a
security boundary.
"""

import fnmatch
import json
import os
import re
import shlex
import sys

PROTECTED_NAMES = ["expense_tracker.db", ".env"]

# Paths relative to the project root that Write/Edit may not touch.
PROTECTED_PATHS = [
    "expense_tracker.db",
    ".env",
    ".claude/settings.json",
    ".claude/settings.local.json",
]
PROTECTED_DIRS = [".claude/hooks/"]

PROTECTED_IN_COMMAND = [
    r"expense_tracker\.db",
    r"(?<![\w.])\.env\b",
    r"\.claude[/\\]+settings(\.local)?\.json",
    r"\.claude[/\\]+hooks\b",
]

DESTRUCTIVE = [
    r"\brm\b",
    r"\brmdir\b",
    r"\bunlink\b",
    r"\btruncate\b",
    r"\bshred\b",
    r"\bmv\b",
    r"\bcp\b",
    r"\bsed\s+-i",
    r"\bdel\b",
    r"\berase\b",
    r"\bmove\b",
    r"\bcopy\b",
    r"\bRemove-Item\b",
    r"\bri\b",
    r"\bMove-Item\b",
    r"\bCopy-Item\b",
    r"\bClear-Content\b",
    r"\bSet-Content\b",
    r"\bAdd-Content\b",
    r"\bOut-File\b",
    r"\bos\.(remove|unlink)\b",
    r"\bshutil\.(rmtree|move)\b",
    r"\.unlink\(",
    r"\bDROP\s+TABLE\b",
    r"\bDELETE\s+FROM\b",
    r"(?<![<>&\d])>(?!&)",  # shell redirect that overwrites a file
]

GLOB_CHARS = set("*?[")

BLOCK_MESSAGE = (
    "BLOCKED by .claude/hooks/guard_destructive.py: {reason}. "
    "Do not look for a workaround; ask the user to do this themselves if it "
    "is really intended."
)


def block(reason):
    print(BLOCK_MESSAGE.format(reason=reason), file=sys.stderr)
    return 2


def glob_hits_protected(command):
    """True if any glob token in the command could expand to a protected file."""
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        tokens = command.split()
    for token in tokens:
        if not GLOB_CHARS & set(token):
            continue
        pattern = re.split(r"[/\\]", token)[-1] or "*"
        for name in PROTECTED_NAMES:
            if fnmatch.fnmatch(name, pattern):
                return True
    return False


def check_command(command):
    if not any(re.search(d, command, re.IGNORECASE) for d in DESTRUCTIVE):
        return 0
    if any(re.search(p, command, re.IGNORECASE) for p in PROTECTED_IN_COMMAND):
        return block("this command would delete, move or overwrite a protected file")
    if glob_hits_protected(command):
        return block(
            "this command uses a wildcard that could match a protected file "
            "(expense_tracker.db or .env)"
        )
    return 0


def to_relative(file_path, project_dir):
    full = os.path.normcase(os.path.abspath(file_path))
    root = os.path.normcase(os.path.abspath(project_dir))
    try:
        rel = os.path.relpath(full, root)
    except ValueError:  # different drive on Windows
        return None
    return rel.replace("\\", "/")


def check_file_edit(file_path, project_dir):
    if not file_path:
        return 0
    if os.path.basename(file_path).lower() in PROTECTED_NAMES:
        return block(f"{file_path} is a protected file")
    rel = to_relative(file_path, project_dir)
    if rel is None:
        return 0
    if rel in PROTECTED_PATHS or any(rel.startswith(d) for d in PROTECTED_DIRS):
        return block(f"{rel} is protected hook configuration")
    return 0


def main():
    data = json.load(sys.stdin)
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {}) or {}
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or "."

    if tool_name in ("Bash", "PowerShell"):
        return check_command(tool_input.get("command", "") or "")
    if tool_name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        return check_file_edit(path, project_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
