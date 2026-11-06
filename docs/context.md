# Context in the list, and what the app adds to Claude's settings

Each session shows how full its context window is: a small ring in its row and on its tab, green,
yellow from 60 %, red from 80 %, the figure in its tooltip. The ring is exact when Claude Code has
reported it and an estimate, drawn faint and labelled so, when it has not.

## Where the figure comes from

- **The app's statusline.** Claude Code runs a statusline command after each assistant message
  with the session's state as JSON. `agent_tablet/statusline.py` is that command: it prints the
  bar and leaves `$XDG_CACHE_HOME/agent-tablet/sessions/<session_id>.json` (the context reading:
  the keys are `context_fields.SESSION_FIELDS`, held to both sides by a test) and one line in
  `usage.jsonl` (cost, lines changed, the subscription's 5-hour and 7-day limits — what the
  transcript does not hold). It runs with any `python3`, outside the app, and never fails: a bad
  payload still prints a bar and exits 0.
- **How it reaches a session.** Every `claude` the app starts carries
  `--settings $XDG_CONFIG_HOME/agent-tablet/claude-settings.json`, which layers the statusline for
  that session only and writes nothing under `~/.claude` (`agent_tablet/claudesettings.py`; the
  flag is `Provider._session_flags`, Claude's only).
- **The estimate.** A session with no reading, or one older than its transcript's last assistant
  message, is estimated: that message's input + cache tokens over the last window size the
  statusline reported for the session, or 200k if it never did. The transcript does not say the
  window's size, so a 1M-token session estimated over 200k would read five times too full; the
  ring says "estimate".
- **The app side.** `agent_tablet/context.py` keeps one `ContextModel` per app: it watches the cache
  directory, reads off the main thread, one read in flight per session, and emits `"changed"`. The
  windows track the sessions of their project and pass each tab the fullest reading among its panes.

## The integrations menu

Preferences → Integrations lists what the app may add to `~/.claude/settings.json`, one switch per
piece, all off until the user turns them on. Today one piece: **the statusline in every Claude
session**, for the sessions started outside the app.

- Turning it on copies the file to `$XDG_STATE_HOME/agent-tablet/settings-backup/`, sets
  `statusLine` to the app's, and records what it wrote and the statusline it replaced
  (`$XDG_STATE_HOME/agent-tablet/integrations.json`).
- Turning it off puts the replaced statusline back, or removes the key — only if the file still
  holds what the app wrote; a file the user changed since is left alone and the switch says why.
- **The user's own statusline keeps showing.** Whether it was replaced by the global install or
  outranked by `--settings`, the app's script runs it with the same stdin and prints its output;
  the app only adds what it records on the side. The command to chain is computed by the app and
  left in `$XDG_CONFIG_HOME/agent-tablet/chained-statusline.json` for the script to read.

## Rejected, and why

- **Writing `statusLine` into `~/.claude/settings.json` by default**: the user decides each piece
  (`CLAUDE.md`); `--settings` covers every session the app starts without writing anything.
- **A Claude Code plugin**: plugins cannot set `statusLine`.
- **Hooks for the context or the cost**: no hook event carries either; the statusline does.
- **The estimate alone**: no window size in the transcript.
- **A number instead of a ring**: the human chose the ring, with the number in its tooltip.

## Not verified here

`make ui-check` shows the rings on the demo data and the Integrations page, but cannot click the
switch (Broadway draws the page too narrow, `docs/ui-verification.md`); installing and removing are
tested against a real settings file in `tests/test_integrations.py`. A real session's bar and its
ring matching it are checked by hand.
