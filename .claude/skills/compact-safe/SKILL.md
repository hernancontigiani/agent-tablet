---
name: compact-safe
description: Cross a context compaction without losing the thread — write a handoff to yourself before the context is compressed, and consume and delete it on return. Use when the human says they are about to compact, when the context passes ~88%, and right after a compaction to consume the handoff.
---

A compaction keeps **what was said** and loses **what you were about to do**. The automatic summary
is good at rebuilding the story and bad at state: what you promised another session, the exact
number you measured, what you already ruled out. This skill is the handoff from you to yourself, in
two moments.

## Moment 1 — Write, before the compaction

One file, `HANDOFF.md`, **in your scratchpad directory** — the one the environment names every turn.
**There, not in the repository**: the tree is shared and the human commits by hand, so a file of
yours at the root is someone else's noise; and the scratchpad path **arrives through the
environment, not the conversation**, which is exactly what the compaction compresses.

At the very top, one line each: **the date and time**, and **which plan or task you are on**.
Without them, a file that survives an abrupt end is indistinguishable from a live one.

Then **only** this — the question deciding each line is *"will the summary rebuild this, or lose
it?"*:

- **What you owe another session and what you expect from it.** Who you promised what, which shared
  resource you hold, which question you sent that is unanswered. **The summary flattens this
  first**, and it is the only thing that, lost, blocks someone else.
- **What was verified, with the command that verified it, apart from what was assumed.** Write
  *"verified with `X`: N"* or *"assumed, not verified"*, never the bare claim.
- **Exact numbers and identifiers.** `ok  ./internal/cli 1.012s`, a commit hash, the full name of
  the test that stayed red. A summary rounds them or drops them.
- **What you already ruled out, with the why in half a line.** The most expensive thing to lose:
  without it the returning session retries what already failed, and thinks it was its own idea.
- **The next step, in the imperative and with the file.** Not *"continue block 4"* but *"edit
  `internal/x/y.go`, function `z`, so that …"*.
- **What NOT to touch** in this task, if instinct would.

**What does not go in**: anything the tree, `git log`, `plans/00-STATUS.md` or `CLAUDE.md` answer.
**If the file is longer than a screen, half of it is surplus.**

Last thing before the human compacts: **name the file's path in your visible message.** The
summary carries the last thing said, so that line is what tells the later you the handoff exists.

## Moment 2 — Consume and delete it, on return

1. Read it whole **before** any other tool. If unsure whether there is one, `ls` the scratchpad.
2. **Re-verify in the tree what the file claims about state** before relying on it — you were away,
   other sessions were not.
3. Take the next step.
4. **Delete it.** An old handoff is worse than none: it reads with the same confidence as a fresh
   one and describes a tree that no longer exists. Delete it as soon as it is consumed.

**If the date is not today, it is not a handoff: it is debris from a session that died.** Name it
and ask before acting on it.

## What this file is NOT

**It is a handoff from you to you, within one session.** A session relaunched from scratch has
another scratchpad and will never find it — which is fine. **What must outlive the session does not
go here**: it goes to the plan's execution log, to the right `docs/` file, or to a message to the
orchestrator.
