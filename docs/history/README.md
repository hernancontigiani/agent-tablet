# history — the text that left the decision documents

**What stops being true goes here**: the previous version of a rule, when it changed, the closing
note of a delivered plan. The documents say how the system is today and why; this keeps how it got
there, for the day someone needs to understand an old decision. **Nothing loads it for anything
else**: no skill, role or `CLAUDE.md` sends a session to read it.

**Each decision document has its history at a mirrored path:**

| Document | Its history |
|---|---|
| `CLAUDE.md` | `docs/history/root/CLAUDE.md` |
| `docs/<file>` | `docs/history/<file>` |
| `plans/00-STATUS.md` | `docs/history/plans/00-STATUS.md` |

Numbered plans have no history: a plan's exit is its header, and git keeps the file. `README.md` has
none either: it is the user's guide, not a record of decisions.

**Inside, the order is the document's sections, not the dates.** Each source section has its
heading, with the same number and title as in the document, and under it the text that left,
**verbatim and in whole lines**, with one line above: `> Left §7 on YYYY-MM-DD.` If the same section
sheds text another day, it goes below with its own line. **The file only grows.**

**When a paragraph mixes the rule with the story**, the document keeps the rule rewritten and the
history receives the old lines whole.

**Section numbers in a document never change**: citations from elsewhere must keep resolving.

## The check

**`python3 docs/history/nothing_lost.py [<document>]`** (`make ci` runs it on every mirrored
document): every line that left a document since `HEAD` is in its history, and no history lost a
line. Blank lines, rules, table separators and code fences do not count. It compares against
`HEAD`, so **it is run on a document without someone else's uncommitted changes**
(`git diff --quiet HEAD -- <document>` before starting to cut); the human commits between batches.
