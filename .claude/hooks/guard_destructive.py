"""PreToolUse hook: block shell commands that would delete or overwrite protected files.

Reads the hook payload from stdin. Exits 2 (blocking) when a Bash/PowerShell
command both looks destructive and names a protected file; exits 0 otherwise.
This is a safety net against accidents, not a security boundary.
"""

import json
import re
import sys

PROTECTED = [
    r"expense_tracker\.db",
    r"(?<![\w.])\.env\b",
]

DESTRUCTIVE = [
    r"\brm\b",
    r"\brmdir\b",
    r"\bunlink\b",
    r"\btruncate\b",
    r"\bshred\b",
    r"\bmv\b",
    r"\bdel\b",
    r"\berase\b",
    r"\bmove\b",
    r"\bRemove-Item\b",
    r"\bri\b",
    r"\bMove-Item\b",
    r"\bClear-Content\b",
    r"\bSet-Content\b",
    r"\bOut-File\b",
    r"\bos\.(remove|unlink)\b",
    r"\bshutil\.(rmtree|move)\b",
    r"\.unlink\(",
    r"\bDROP\s+TABLE\b",
    r"\bDELETE\s+FROM\b",
    r"(?<![<>&\d])>(?!&)",  # shell redirect that overwrites a file
]


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    command = data.get("tool_input", {}).get("command", "") or ""

    hit_protected = [p for p in PROTECTED if re.search(p, command, re.IGNORECASE)]
    if not hit_protected:
        return 0
    if not any(re.search(d, command, re.IGNORECASE) for d in DESTRUCTIVE):
        return 0

    print(
        "BLOCKED by .claude/hooks/guard_destructive.py: this command looks like it "
        "would delete, move or overwrite a protected file (expense_tracker.db or "
        ".env). Ask the user to run it themselves if it is really intended.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
