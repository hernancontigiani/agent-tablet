---
name: review-branch
description: Review a branch against its base for regressions and broken seams, and write the findings to a plain-text file the human can read and paste. Use when asked to review a branch or a set of commits, or to check whether a change broke anything. Not for writing code, and not for a style pass.
---

# Reviewing a branch

Read the change, verify it empirically, write one plain-text file, report its path. Nothing else
happens: this skill produces a file and a summary in chat.

## Never

Never commit, push, amend, stage, or modify the working tree. Never post anywhere — the author is
not contacted; the human decides what reaches them.

Never leave a worktree behind, and never run the suite in the human's own checkout — it may be on
another branch with work in progress.

## What counts as a finding

One test decides it: does this break something? A regression in behaviour that worked before, or a
seam that no longer holds against the code around it. That is the whole bar.

Naming, structure, style, a comment you would have written differently, a refactor you would prefer
— none of these go in. When torn between "this is wrong" and "I don't like this", it is the second
and it does not go in.

Two things that are not style and do earn a line:

- A rule `CLAUDE.md` states explicitly and the branch does not meet: a write under `~/.claude` the
  human did not decide, a second name kept for a session Claude already named, something encoded
  into a session name, a network connection, a user-visible string outside `_()`, blocking work on
  the GTK main loop, a path resolved at import in new code, `datetime.now()` inline in logic, a new
  PyPI dependency with no justification, a `CHANGELOG.md` entry written without approval.
- A new code path with no test where a silent failure would be indistinguishable from success.

If nothing survives the test, say so in one sentence. That is a useful result and the branch moves.

## Verify instead of asserting

Measure what a claim rests on rather than repeating it from the commit message or a plan. A premise
inherited without checking is how a review invents a blocker that does not exist.

Run `make ci` in a detached worktree under the session's scratchpad directory
(`git worktree add --detach <scratchpad>/review-<branch> <branch>`), and remove it when done
(`git worktree remove`). Report the counts. A red that the base also has is not this branch's;
check the base before attributing it.

State a negative only as wide as what was measured: "not in the callers I searched" is not "nothing
calls it".

When a code comment makes a factual claim the change depends on, check it against the code it
describes.

## Read the change for what a diff hides

Compare against the real merge base (`git merge-base`), not a moving branch name. If the base
advanced since the branch was cut, work out which side a difference came from before calling it a
finding.

List the files the branch touches that the base also moved. That intersection is where a rebase
merges cleanly and still means something different.

Follow a changed signature to every caller, including the ones outside the package the diff shows
(`ruff check` catches an undefined name; the behavioural ones need reading). A new setting, signal
or enum member is followed to every place that branches on it.

## The file

Write it to the session's scratchpad directory, never into the repository. Name it
`review-<branch>.txt`. Give the path as a `file://` link on its own line.

Plain text, not Markdown. No `#` headings, no bold, no italics, no backticks, no tables, no numbered
lists. Section titles are their own line in capitals. Flags, symbols and paths go as plain words.

Bullets start with `-` and are one sentence, two at most. One bullet is one finding.

Concise over complete. What the reader needs to decide, not a walkthrough of the diff. No anecdote,
no account of how the finding was reached, no praise.

## Sections, in this order

- `VERDICT` — one sentence: whether the branch introduces a regression, plus the `make ci` result
  and the commit reviewed.
- `BLOCKERS` — only what breaks. Each names where it is, what goes wrong, what sequence triggers it,
  and what would close it. Leave the section out when there are none.
- `ALSO IN THIS BRANCH` — the explicit `CLAUDE.md` rules the branch does not meet, and new paths with
  no test. Three bullets at most. Leave it out when there are none.
- `CHECKED AND CORRECT` — what was verified and holds, so the reader knows what not to re-check.
  Short: the seams that could plausibly have broken and did not.

Nothing else. No summary of the feature, no list of changed files, no severity labels, no next steps
for the author.
