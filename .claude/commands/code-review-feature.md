---
description: Runs parallel security and quality code 
  review for a specific Spendly feature. Pass the spec 
  name as argument e.g. /code-review-feature 03-login-logout
allowed-tools: Bash(git diff:*), Bash(git status:*)
---

Run the full code review pipeline for the feature 
specified in $ARGUMENTS.

If no argument is provided, stop immediately and say:
"Please provide a spec name. Usage: /code-review-feature 
<spec-name> e.g. /code-review-feature 03-login-logout"

## Pre-flight Check

If `.claude/specs/$ARGUMENTS.md` does not exist, stop 
immediately and report it.

Before invoking any subagents, collect the changes 
(the same three sources the reviewers use):
- Run `git diff main...HEAD` for work already committed 
  on the feature branch
- Run `git diff HEAD` for uncommitted changes (staged 
  and unstaged)
- Run `git status --short` for new untracked files 
  (`??`), which `git diff` doesn't show
- Combine these into a single diff plus a list of new 
  files

If all three are empty, stop immediately and say:
"No changes detected. Implement the feature before 
running code review."

---

## Step 1: Parallel Review

Invoke both subagents simultaneously with the same 
context:

**spendly-security-reviewer** receives:
- The combined diff from the pre-flight check
- Spec file for context: `.claude/specs/$ARGUMENTS.md`
- Source files to reference: `app.py`, `database/` 
  directory, `templates/` directory (for XSS) and 
  `static/js/`
- Instruction: Review only the changed code for 
  security vulnerabilities. Do not comment on quality 
  or style.

**spendly-quality-reviewer** receives:
- The combined diff from the pre-flight check
- Spec file for context: `.claude/specs/$ARGUMENTS.md`
- Source files to reference: `app.py`, `database/` 
  directory, and `templates/` directory
- Instruction: Review only the changed code for quality, 
  Flask best practices, and maintainability. Do not 
  comment on security concerns.

Both subagents must run in parallel. Do not wait for 
one to finish before starting the other.

---

## Step 2: Unified Report

Once both subagents have completed, combine their 
findings into a single unified report. De-duplicate 
any overlapping findings — if both agents flagged the 
same line for different reasons, merge them into one 
finding with both perspectives noted.

Structure the combined report as:

```
## Code Review Report — $ARGUMENTS

### Security Findings
[spendly-security-reviewer output]

### Quality Findings
[spendly-quality-reviewer output]

### Combined Action Plan
Ordered checklist of everything worth fixing, using
the sections the reviewers already report:

1. Security "💡 Things to learn from" items
2. Quality "💡 Worth improving" items
3. Security "🌱 Nice to have" items
4. Quality "🌱 Polish ideas" items

("✅ Doing well" items are not action items — keep them
in the sections above.)

### Overall Verdict
One of:
- APPROVED — no 💡 items from either reviewer; ready
  to commit
- APPROVED WITH SUGGESTIONS — only 🌱 items; can
  commit, address suggestions in future steps
- CHANGES REQUESTED — at least one 💡 item; recommended
  to fix before committing, see action plan above
```

The verdict is a recommendation, not a gate — the 
reviewers are mentors, and the user decides what to 
fix and when.

---

## Step 3: Ask for Approval

After presenting the unified report, ask:

"Do you want me to implement the action plan now?"

Wait for explicit user confirmation before making 
any changes. Do not touch any files until the user 
approves.

---

## Rules
- Do NOT edit any files before user approval
- Do NOT start one reviewer before the other — 
  both must run in parallel
- Do NOT skip the pre-flight diff check
- Do NOT proceed if the spec file at 
  `.claude/specs/$ARGUMENTS.md` does not exist — 
  report it and stop
- If either subagent fails or returns no output, 
  report it and do not present a partial review 
  as complete