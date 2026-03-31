---
name: jd-review
description: Daily review — triage email, catch up on OmniFocus, process JD inboxes. Guided walkthrough to get on top of everything.
user_invocable: true
---

# Daily Review

A guided walkthrough to get on top of email, tasks, and the filing system. Start with what's incoming, then catch up on what's overdue, then clean up.

## Tools Available

**Email:**
- `apple-mail unread` — unread messages
- `apple-mail recent` — recent messages (default 7 days)
- `apple-mail search --subject/--sender/--mailbox` — filtered search
- `apple-mail body <message-id>` — full message body
- `apple-mail flag <message-id>` — flag for follow-up
- `apple-mail archive <message-id>` — move to archive
- `apple-mail draft --to --subject --body` — create a draft reply
- `apple-mail mark-read <message-id>` — mark as read

**Tasks:**
- `omnifocus tasks` — list tasks (`--flagged`, `--project`, `--tag`)
- `omnifocus projects` — list all projects
- `omnifocus create-task --name --project --tag --note --flagged --due` — create a task
- `omnifocus complete <task-id>` — mark complete

**Filing system:**
- `jd omnifocus scan` — check OmniFocus/JD alignment
- `jd triage` — show JD inbox items needing attention
- `jd search` / `jd which` — find locations

All commands support `--json` for structured output. Always use `--json` and parse programmatically.

## Review Flow

### 1. Email Triage (what's incoming)

This is where new work arrives. Process it first.

```bash
apple-mail --json unread
```

Present unread messages grouped by mailbox. For each batch:
- **Actionable** — needs a reply, a task, or filing → create OmniFocus task or draft reply
- **FYI** — read and archive
- **Junk** — archive or ignore

Ask: "Here are your N unread messages. Which need action, which are just FYI?"

For actionable emails, offer to:
- Create an OmniFocus task (`omnifocus create-task`)
- Draft a reply (`apple-mail draft`)
- Flag for later (`apple-mail flag`)
- File into JD (`jd add`)

Archive processed emails with `apple-mail archive`.

### 2. Flagged & Overdue Tasks (what's screaming)

```bash
omnifocus --json tasks --flagged
omnifocus --json tasks
```

**Flagged tasks:** Present grouped by project. Ask which are done, stale, or need rescheduling.

**Overdue deferred tasks:** Filter for `defer_date` before today. Group by staleness:
- Weeks overdue → probably need attention
- Months overdue → likely stale, suggest completing or dropping

Present as a table. Ask: "Any of these done or no longer relevant?"

### 3. Project Health (what's drifting)

```bash
omnifocus --json projects
```

Look for:
- **Empty projects** — no remaining tasks. Complete or restock?
- **Stale projects** — all tasks have old defer dates
- **Too many tasks** — projects with 20+ items probably need pruning

Summary: "You have N projects. M look stale. K are empty."

### 4. JD Inbox & Triage (what's unfiled)

```bash
jd triage
```

Show JD inbox items that need filing. This catches documents, downloads, and captures that came in but never got sorted.

### 5. JD/OmniFocus Alignment

```bash
jd omnifocus scan
```

Check for mismatches between OmniFocus JD tags and the actual JD tree.

### 6. Quick Wins & Wrap-Up

Summarize what was done and suggest 3-5 concrete next actions:
- Tasks completed during review
- Emails archived
- New tasks created
- Items still needing attention

## Rules

- **Never complete, delete, or archive without asking.** Present findings, get approval, then act.
- **Batch operations.** Group items by type/project, don't ask one by one.
- **Be honest about the backlog.** If it's bad, say so without judgment.
- **Time-box each phase.** If there are 100+ unread emails, show the 20 most recent. If 200+ tasks, focus on flagged → overdue. Don't try to review everything.
- **Create tasks liberally.** When an email needs follow-up, always offer to create a task — that's the point of the system.
- **Use `--json` for all commands.** Parse structured data, don't scrape text.
- **Ask before moving on.** At the end of each phase, ask if the user wants to continue to the next phase or stop here.
