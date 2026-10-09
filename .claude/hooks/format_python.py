"""PostToolUse hook: run black on any .py file that was just written or edited.

Uses the same interpreter that runs this script (the project venv), so black
must be installed there (it is listed in requirements.txt).
"""

import json
import subprocess
import sys


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    file_path = data.get("tool_input", {}).get("file_path", "") or ""
    if not file_path.endswith(".py"):
        return 0

    result = subprocess.run(
        [sys.executable, "-m", "black", "--quiet", file_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Non-blocking: surface the problem without stopping Claude.
        print(f"black failed on {file_path}: {result.stderr.strip()}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
