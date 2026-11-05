# plans — the method

**What empties is the content, not the folder.** A delivered plan is deleted, because from then on
the code is a better description of itself; whatever must not be lost in that deletion is moved out
first, and **every plan declares where in its header** (`CLAUDE.md`, "Where each thing lives"). **A
plan whose header names a destination that does not exist yet is not deleted**: it stays alive
holding that part until the file that receives it exists.

Two kinds of file live here, and they are not confused:

| | What happens to them |
|---|---|
| `README.md`, `00-STATUS.md`, `ROLE-DESIGNER.md`, `ROLE-ORCHESTRATOR.md`, `ROLE-AUDITOR.md` | **Permanent.** They describe the method and the state, not a piece of work |
| Numbered plans (`NN-<topic>.md`) and audit reports (`AUDIT-<topic>.md`) | Deleted once delivered |

**The state is not here: it is `00-STATUS.md`** — what is decided, what is open, who owns each
topic, and which plan is in flight. This file is the *method*; that one is the *state*.

Four roles work on this folder, and **each is loaded with a skill** instead of being pasted by hand:
`/orchestrate` (what goes now, what runs in parallel, the execution session's prompt), `/design-plan`
(how a plan is written), `/execute-plan` (how a written plan is built) and `/audit-architecture`
(whether a subsystem can change without breaking). Three of those skills contain nothing but "read
`ROLE-*.md`", so the role cannot drift from what is versioned — a pasted copy goes stale silently the
next time something is reorganized. `/execute-plan` carries its procedure itself, because it is
identical for every plan and would otherwise be repeated in every one-shot prompt.

## Numbering

A plan's number is taken **by creating the empty file**, not by choosing it and writing later, and
`00-STATUS.md` is updated in the same act. If an orchestrator session is running, ask it for the
number. Two plans collide when the gap between choosing and creating is left unwatched.

## The shape of a plan

A **written** plan has execution blocks with checkboxes; a **stub** does not, and says so in its
header. That is the difference between something a session can execute and something that still
has to be designed.

**Header, always:** status and date · which design it comes from · **its exit when executed** (which
file each part moves to) · which plan it replaces or modifies, if any.

**Body, in this order:**

1. **Goal**, and **what already exists** in the tree that the design relies on — verified, not
   remembered. A plan that does not read the code proposes building things that are already there.
2. **The design**, with its rationale and **what was rejected and why**. That last part is what the
   code never documents and the first thing lost if it is not written. **Every product decision the
   code must hold names the test that asserts it**: the sentence goes in the test's comment, the
   promise goes in the assertion, with the concrete case (inputs and expected output), in a test an
   execution block writes **before** the code. Writing that test is what exposes two sections of
   the same plan contradicting each other — when the plan is executed, the contradiction is already
   built.
3. **Out of scope** and **Do not touch**, as two sections: the first bounds the plan, the second
   protects what already works while it is executed.
4. **Execution blocks**, each leaving the tree green and **ending in its verification** —
   `make ci` at least, plus the specific tests or the manual check that block declares. A block
   that cannot be verified is cut wrong.
5. **Execution log** at the end, written by the session that executes it: deviations from the plan
   and why, and what the plan did not anticipate.

## Rules for every role

- **Verify against the tree before asserting.** Not the old plan, not memory of the repo.
- **No abstraction without a consumer.** Deferring a piece, with its trigger written in
  `docs/NOT_BUILT_YET.md`, beats a plan that guesses.
- **Decisions belong to the human.** Ask with concrete options and **one recommendation**, showing
  the case that breaks (real volume, not three tidy examples); record the answer with its date in
  the file that owns it. **Do not re-litigate what is recorded** — and if something is reopened,
  say which part is and which part is not.
- **Discussing the design in the session is fine, but capture it in a file as you go.** If the
  context fills up, what is lost is the conversation, not the document.
- **Sessions do not commit** (`CLAUDE.md`, "Git and the shared tree").

## Rules that already cost something

- **Two plans run in parallel only if they share no file and no runtime resource** — not "if they
  don't depend on each other". The same `~/.config/agent-tablet/` state file, the installed launcher
  and icon, the statusline entry in `~/.claude/settings.json` are each a shared resource.
- **Two sections of one plan can ask for incompatible things, and the executor will do both.** The
  test named at design time is what exposes it; that is why the test is named when designing, not
  when executing.
- **"Same as X" is a citation, and it is verified before it is written.** If X is code, open it and
  name the line; if X is another plan, check that it was executed — an unexecuted plan is a shared
  intention, not a precedent, and the block that relied on it was mis-sized.
- **Everything to be built is in a BLOCK.** What appears only in a design section is not executed.
