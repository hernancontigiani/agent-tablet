---
name: execute-plan
description: Execute a written plan from plans/ in agent-tablet block by block — read what is mandatory, build one block at a time with its verification, report without stopping, and close with the execution log and the declared exit. Use when the human asks to execute, implement or build a plan that is already written.
---

You execute **one** plan from `plans/`: the one the human names. **You do not redesign it** — it is
decided, and your job is to build it. If the human did not say which, ask before reading anything
else. If it is a stub (no execution blocks), say so and stop: it needs `/design-plan` first.

## Before touching a line

1. **`CLAUDE.md`** — the product rules, the Python conventions, the git rules (**sessions do not
   commit**) and the language (everything in English).
2. **`plans/README.md`** — the method, and above all the shape of a plan.
3. **The whole plan, not only its blocks.** The design sections carry the rationale and **what was
   rejected and why**; without it you will "improve" something that was decided on purpose. **"Out
   of scope" and "Do not touch" are two different sections.**
4. **Whatever the plan's header tells you to read.**
5. **Your launch prompt, if there is one** (`prompts/PROMPT-*.md`), in full.

Then confirm with **one screen**: what you understood, the order of the blocks, and **what you
found in the code that contradicts the plan**. Only then start.

## How you work

- **One block at a time, in order.** Each block leaves the tree green.
- **Each block ends in its verification** — the one the block declares, plus `make ci`. A block
  without its verification run is not finished. **A block that changes the UI also runs
  `make ui-check` and looks at its screenshots** (`docs/ui-verification.md`): a green walk proves
  the screens open, not that they look right.
- **A new test is seen red before it is trusted.** Inject the defect from a temporary test or an env
  var, or invert the assertion — never by editing code another session may be reading — watch it
  fail, then put it back.
- **When a block passes, start the next one in the same turn.** The end-of-block report is a
  paragraph, **not the end of a turn**: handing control back between blocks makes the human say "go
  on" five times. Go until the plan is done.
- **There are only three reasons to really stop**: a shared resource another session holds (the
  installed launcher, the statusline entry in `~/.claude/settings.json` — `plans/ROLE-ORCHESTRATOR.md`), a **decision that
  belongs to the human** that the plan did not take, or a **problem that blocks you**. Not the
  commit, not "the block came out nice", not asking permission to continue.
- **Each block report lists the paths that block touched.** It is all the human needs to commit
  later without reading the whole tree, and with several sessions on one tree it is what says which
  change is yours.
- **Verify against the code before asserting.** If the code contradicts the plan, **say so** instead
  of choosing silently. **What a subagent returns is a report, not a fact**: check it before passing
  it on.
- **If a decision the plan did not take shows up on the way**, do not take it for convenience: ask
  with concrete options and one recommendation.
- **A file you create as NEW that `git status` shows as modified is not new**: you are overwriting
  someone else's. Look at the status before taking the obvious name.
- **A red in a package you did not touch, on a shared tree, is almost never yours.** Run the suite
  again and check whose package it is; if it still looks real, tell the orchestrator instead of
  fixing it.
- **A long plan does not fit in one context**: before a compaction, load `/compact-safe` and write
  the handoff.

## How you close

- **A sweep that needs a hand-maintained LIST to be correct is badly formulated.** Rephrase it so it
  holds by itself — "no module outside `state` writes under the config dir" instead of "these twelve
  call sites were reviewed".
- **Search for STRUCTURE, not for the string.** A `grep` measures what is easy to grab instead of
  what matters, and a green sweep over the wrong question closes the suspicion for everybody.
- **Once per plan, ask out loud: does what this plan measures or verifies reach the person?** No
  suite answers it, and it finds what the tests cannot: a correct, tested piece **nobody calls**, a
  number computed and never shown where the user looks.
- **The documentation goes in the same pass, not after.** A text your block makes false is fixed
  **in that block**, not in a documentation block at the end: until then the tree contradicts
  itself, and another session works in that window.
- **The execution log at the end of the plan is part of the work**: deviations from the plan and
  why, and what you found that the plan did not anticipate.
- **The plan is deleted on delivery**, after each part has moved to the destination **the plan's own
  header declares**. The plan's row leaves `plans/00-STATUS.md` §3 and its closing note goes to
  `docs/history/plans/00-STATUS.md`; what it left open enters §2 in one line.
- **A rule your exit replaces leaves verbatim for its history** (`docs/history/README.md`) in the
  same change; `make ci` fails while a removed line has not reached it.
- **If a declared destination does not exist yet, the plan is not deleted.** It stays alive holding
  that part; say so in its header with the reason, so it does not read as forgotten.
- **Mind the log: it dies with the file that holds it.** If the plan is deleted in the same tree
  state the log was written in, the log is in no commit. Tell the human the log must be committed
  before the deletion, or move it where it belongs.
- **Fix dangling references** to the deleted file in the same pass — its name as well as its path.
- **Only then delete your own `prompts/PROMPT-*.md`.** Not earlier: `prompts/` is gitignored, so it is
  the only copy, and while you work it is the record of what you were asked.
- **Do not propose a `CHANGELOG.md` entry before the first tagged release** (`CLAUDE.md`).
