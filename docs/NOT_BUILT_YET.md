# Deliberately not built yet

Each entry is a decision to defer, not an oversight, listed with the **trigger** that should reopen
it. A piece with no consumer is deferred here instead of being designed blind.

What a plan will build in its turn does not belong here: the roadmap is `plans/00-STATUS.md`. This
file is for what was considered and consciously left out.

An entry is:

```
### <What is not built>

Why it is deferred, and what would go wrong if it were built now.

**Trigger:** the concrete situation that reopens it, and the first question to answer then.
```

### A packaged release (`.deb`, PyPI)

Installation is from source (`data/install.sh`) until there is a first stable version: a package is
a promise of upgrades, and every rename in plan 01 would break it. `debian/` and
`scripts/build_deb.sh` are kept and rebranded so they are ready; the original's AUR, PPA and PyPI
publishing were removed.

**Trigger:** the human calls a version stable. First question: which Ubuntu releases the `.deb`
targets, given the Python 3.12 floor.

### A documentation site

The original's VitePress site was removed with the fork; `README.md` is the user guide.

**Trigger:** the README stops fitting on a few screens, or someone outside the human uses the app.

### Sessions that survive quitting the app

Quitting stops every agent; the next start resumes the ones that were in tabs. Keeping them alive
would need a process supervisor (tmux, dtach) to install and reason about.

**Trigger:** the human loses work to a quit, or wants an agent to keep working with the app closed.
First question: does resuming lose anything the agent had not written to its transcript?

### Dragging sessions and tabs

"Open beside" from a row's menu puts a session in a tab's second pane; rows and tabs are not
reordered by dragging.

**Trigger:** the human misses dragging a row onto a tab, or reordering rows. First question: is the
order of a project's sessions worth saving, or is the group enough?

### More than two panes in a tab

Two panes are what the human uses; more is unreadable at a laptop's width.

**Trigger:** a workflow that needs three agents in view at once. First question: a third pane, or a
second window on another monitor?

### Choosing which monitor a window opens on

On Wayland the app cannot place its windows; reopened windows land where the system puts them.

**Trigger:** the human rearranges windows by hand after every start. First question: does the
compositor offer a portal for it by then?


### Claude Code hooks

The statusline gives the context, the cost and the limits; the transcripts give tokens and time.
No hook event carries any of them, so the app installs none. The integrations menu is where a hook
would go, consented to and removable like the statusline.

**Trigger:** a feature needs an event the statusline and the transcript cannot give (for example,
knowing the instant a permission prompt appears). First question: can it ride `--settings` for the
sessions the app starts, before asking for a global install?
