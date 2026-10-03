---
description: Writes and runs tests for a specific Spendly feature. Pass the spec name as argument e.g. /test-feature 05-profile-backend
allowed-tools: Bash(venv/Scripts/python -m pytest:*)
---

Run the full testing pipeline for the feature specified 
in $ARGUMENTS.

If no argument is provided, stop immediately and say:
"Please provide a spec name. Usage: /test-feature 
<spec-name> e.g. /test-feature 05-profile-backend"

If `.claude/specs/$ARGUMENTS.md` does not exist, stop 
immediately and say:
"Spec file not found at .claude/specs/$ARGUMENTS.md. 
Please check the spec name and try again."

**Test file name**: drop the step number and use 
underscores — e.g. `05-profile-backend` → 
`tests/test_profile_backend.py`. Below, `<test-file>` 
means this path.

---

## Step 1: Write Tests

Invoke the **spendly-test-writer** subagent with the 
following context:

- Spec file to base tests on: 
  `.claude/specs/$ARGUMENTS.md`
- Test conventions to follow: `tests/conftest.py` and 
  existing `tests/test_*.py` files
- Output test file to create (or extend, if it exists):
  `<test-file>`
- Instruction: Write tests based on what the spec says 
  the feature SHOULD do. Do NOT derive test logic from 
  reading the implementation — only Grep `app.py` and 
  `database/` to confirm the route paths and helper 
  names the spec mentions exist. Cover happy paths, edge 
  cases, auth guards, validation errors, and DB side 
  effects. Do not run the tests.

Wait for spendly-test-writer to fully complete and 
confirm the test file has been written before 
proceeding to Step 2.

---

## Step 2: Run Tests

Once spendly-test-writer has finished, invoke the 
**spendly-test-runner** subagent with the following 
context:

- Test file to execute:
  `<test-file>`
- Spec file for context:
  `.claude/specs/$ARGUMENTS.md`
- Source files to analyze against when diagnosing 
  failures:
  - `app.py`
  - `database/` directory
- Run command:
  `venv/Scripts/python -m pytest <test-file> -v`
- Instruction: Run ONLY the specified test file. Do 
  NOT run the full test suite. Analyze any failures by 
  cross-referencing the test code, the spec, and the 
  source files. Classify each failure as a bug or a 
  missing feature. The tests come from the spec, so 
  never recommend weakening an assertion to make it 
  pass — if the spec itself looks wrong, say so.

---

## Handoff Rules

- Do NOT start Step 2 until Step 1 is fully complete
- Do NOT attempt to fix any code regardless of what 
  the test results show
- Do NOT run any tests beyond `<test-file>`
- If spendly-test-writer reports it could not write 
  the test file, stop and report the reason — do NOT 
  proceed to Step 2

---

## Final Output

After both subagents complete, produce a combined 
summary:

### Testing Pipeline Report — $ARGUMENTS

**Step 1 — Tests Written**
- List each test written with a one-line description 
  of which spec requirement it validates

**Step 2 — Test Results**
- Mirror the spendly-test-runner's structured report

**Verdict**
One of:
- ✅ Ready for code review — all tests pass
- ❌ Needs fixes — list the failing tests and their root causes