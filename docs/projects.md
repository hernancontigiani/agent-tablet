# Projects, tabs and windows

How the app decides which sessions it shows, which run, and where. The code is the source of truth
for the shapes; this file holds the reasons, what the CLI does that the code relies on, and what was
rejected.

## The model

- **A project is a name and the sessions the user put in it**, from any folder, with the user's
  groups (`projects.py`). It has no folders of its own. A project called Default exists from the
  first start, empty.
- **A session belongs to one project at most.** Adding one that another project holds moves it,
  with its tab. One process has one terminal: a session in two projects would need two tabs.
- **A session runs if and only if it has a tab.** Closing the tab or its pane, Stop, and the agent's
  own exit (`/exit`, Ctrl+D) all stop it; its row stays, *stopped*. A session working with no tab
  would look closed while it is not.
- **A project is in at most one window**: the window that shows it, or holds one of its tabs. So a
  session is never open twice (`layout.py`).
- Projects, groups and the windows' tabs are saved in `~/.config/agent-tablet/projects.json`,
  written whole through a temporary file. An unreadable file is moved aside to
  `projects.json.broken` and a fresh Default starts; unknown keys are written back as they came.

## Starting and stopping a session

- **The app picks a new session's id** and starts it with `--session-id <uuid> -n <name>`; a fork
  gets its own with `--resume <id> --fork-session --session-id <uuid>`. Guessing it from the newest
  transcript in the folder, as the app did before, took another session of the same folder.
- **A new session joins its project once Claude has a message the user typed in it**: one closed
  before that leaves nothing in the project. The window waits for that file while the tab lives.
- **The command typed into the tab's shell ends with `&& exit`**, so the tab goes with the agent and
  a failing start leaves its message in the shell. It is typed into the user's shell, not run with
  `exec`, to keep their aliases and functions.
- Quitting asks when agents run, stops them, and keeps the layout; with "Reopen tabs on start"
  (on by default) the next start reopens each window with its project and resumes its tabs.

## What the CLI does (Claude Code 2.1.319, checked 2026-11-06)

- `--session-id <uuid> -n <name>`: the transcript is `<uuid>.jsonl`; its first lines carry the name
  (`custom-title`, `agent-name`) before the first `user` line.
- `--fork-session --session-id <uuid>` together are accepted; the fork's transcript takes that id.
- `--continue` keeps the id of the session it continues; it creates no file.
- A failing start (an invalid `--session-id`) exits with status 1.

## Rejected, and why

| Alternative | Why not |
|---|---|
| A project is one or several folders | A project mixes repos, and not every session of a folder belongs to it |
| A window per project, always | The human works mostly in one window; a second one is for a second monitor |
| A session in several projects | One process has one terminal: it cannot be a tab in two projects or two windows |
| The list flat for one folder, grouped by folder when mixed | Adding one session from another repo would reshape the whole list |
| Grouping by folder by default | The human groups by collaboration (a pair of sessions), which crosses folders |
| Closing a tab hides it and the session keeps running | A session working with no tab looks closed while it is not |
| Keeping sessions alive after the app quits (tmux, dtach) | A second process supervisor to install and reason about; quitting stops them and reopening resumes them |
| Unlimited nested splits with sessions | Two panes are what the human uses; more is unreadable at a laptop's width |
| SQLite for projects | A few projects and hundreds of ids, one writer, read whole at start; JSON is readable and fixable by hand |
| Guessing a new session's id from the newest transcript in its folder | It matches another session of the same folder at once |
| `exec claude` to close the tab with the agent | `exec` skips the user's aliases and shell functions |
| The history browser as the main view | The project's list is the main view; every session Claude knows is one dialog away |
| Favorites | A project is the user's chosen list; a second one is redundant |
