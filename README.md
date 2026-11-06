# Agent Tablet

Native GTK4/libadwaita terminal workspace for AI coding agents. Run [Claude Code](https://claude.com/claude-code) and [Cursor](https://cursor.com) side by side in projects, tabs, and split panes; see at a glance which agent is working, blocked, or done; and resume any past session.

> **A modified version of [Agent Session Manager](https://github.com/r4nd3l/agent-session-manager)**
> by Máté Molnár, forked from v1.1.1 on 2026-11-05 and maintained on its own since. See
> [Changes from Agent Session Manager](#changes-from-agent-session-manager).

> **Unofficial community tool.** An independent community project, not affiliated with or endorsed by any agent vendor (including Anthropic) or by herdr.
> It never rewrites your agents' session data; the only changes it makes there are moving a transcript to the trash or deleting it, when you ask and confirm. All app state lives in its own config file.

![Agent Tablet](data/screenshot.png)

The workspace model and look are inspired by [herdr](https://herdr.dev), a terminal workspace manager for coding agents.

## Features

- **Projects**: a project is a name and the sessions you put in it, from any folder; the dropdown at the top of the sidebar switches, creates, renames and deletes them. **Default** exists from the first start. The sidebar lists the current project's sessions — your own **groups** first, each with a color, then the rest — with each session's folder name when the project mixes folders. A session belongs to one project; double-click it to open it in a tab. Projects are saved in `~/.config/agent-tablet/projects.json`.
- **Agents & states**: every running agent with a status dot — **working**, **blocked** (waiting on an approval or a question), **done** (finished while you weren't looking), or **idle** — rolled up to its tab. Detected from Claude Code's terminal title and screen and from Cursor's prompts (a simplified port of herdr's detection rules). Desktop notifications fire when an agent you aren't watching finishes or needs you.
- **Split panes**: shell panes next to the agent, split right or down, with focus moves, zoom, and close.
- **Context at a glance**: a small ring by each session and on each tab shows how full its context window is — green, yellow from 60 %, red from 80 % — with the exact figure on hover. Sessions started from the app report it through their status line; for the others it is estimated from the transcript and marked as such.
- **Integrations** (Preferences): what the app may add to Claude Code's own `~/.claude/settings.json` — today, its status line for sessions started outside the app — one switch per piece, all off by default, each removable, your own status line kept.
- **Usage** (main menu, or `agent-tablet usage`): how long Claude worked and how many tokens it used, per project, category and session, for today, 7 or 30 days — time started by you apart from other sessions and background tasks, time waiting on you apart, and a list-price cost estimate.
- **`Ctrl+B` prefix** with herdr's default keys for panes, tabs, the sidebar, and preferences; `Ctrl+B ?` lists them. **Go to agent** (`Ctrl+B g`) jumps to any running agent, filterable by state.
- **Add session**: every past session on disk (for Claude Code, under `~/.claude/projects/`), grouped by folder, with a **search box**, waiting / interrupted badges and live updates; **Add** puts one in the project, or moves it from another. **New** starts a named session in any folder, even one Claude was never used in. The quick switcher (`Ctrl+Shift+K`) searches the current project.
- **Names and emoji**: a session shows the name it has in Claude (`claude -n`, `/rename`); one Claude never named can be renamed in the app. Put one emoji on a tab (`Ctrl+.` or click the tab's emoji). What the app sets lives in `~/.config/agent-tablet/state.json`.
- **Terminals**: each tab is an embedded **VTE terminal** running your `$SHELL` with the agent's command, in the project folder. Closing a tab asks the agent to exit cleanly (Claude Code's `/exit`) first. In-terminal search (`Ctrl+Shift+G`); `Shift+Enter` inserts a newline in the agent's prompt.
- **Right-click a session in Add session** for the full action set: open, open in [Ghostty](https://ghostty.org), fork, continue in chat, rename, **details** (messages/models/tokens, a peek at recent messages, MCP servers and usage), replay, copy session ID, export as Markdown, reveal the transcript, hide, trash, or delete permanently. **Select mode** handles many sessions at once.
- **Look**: a terminal-workspace style in Catppuccin by default (matching herdr), with Tokyo Night, Gruvbox, Nord, Dracula, and more as variants coloring the whole window — or the **Classic (Adwaita)** style.
- **Also**: multiple windows, Claude Code and Cursor side by side, advanced new-session options (model, permission mode, extra directories, continue), an MCP servers browser, native streaming chat with permission cards, and session replay.

### Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+B`, then a key | Prefix commands (`v`/`-` split, `hjkl` move, `z` zoom, `x` close pane, `c` new agent, `n`/`p` tabs, `g` go to agent, `?` help…) |
| `Ctrl+Shift+T` | New session |
| `Ctrl+Shift+N` | New window |
| `Ctrl+Shift+W` | Close current tab |
| `Ctrl+Tab` / `Ctrl+PgDn` | Next tab in this project (with `Shift` / `PgUp`: previous) |
| `Ctrl+Shift+K` | Quick switcher (jump to any session) |
| `Ctrl+Shift+F` | Focus the history search |
| `Ctrl+.` | Pick an emoji for the current tab |
| `Ctrl+Shift+E` | Toggle 😊 on the current tab |
| `Ctrl+Shift+C` / `Ctrl+Shift+V` | Copy / paste in terminal |
| `Ctrl+Shift+G` | Find in terminal |
| `F9` | Toggle sidebar |
| `Ctrl+,` | Preferences |

## Requirements

Python ≥ 3.12, GTK 4, libadwaita ≥ 1.5, VTE (GTK 4 build), PyGObject — from your distro's packages:

```bash
# Ubuntu / Debian
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-vte-3.91

# Fedora
sudo dnf install python3-gobject gtk4 libadwaita vte291-gtk4

# Arch
sudo pacman -S python-gobject gtk4 libadwaita vte4
```

Plus a supported agent's CLI on your `PATH` — the [`claude` CLI](https://claude.com/claude-code) and/or [`cursor-agent`](https://cursor.com).

## Install

From source, until there is a first stable release:

```bash
git clone https://github.com/hernancontigiani/agent-tablet.git
cd agent-tablet
python3 -m agent_tablet      # run it from the checkout
./data/install.sh            # or install the launcher + icon ("Agent Tablet" in the app grid)
```

It installs next to Agent Session Manager without clashing: its own app id, launcher, icon and
config directory. On first start it imports the names you set in Agent Session
Manager; that app's files are left untouched.

Terminal shortcuts: `Ctrl+Shift+C` copy, `Ctrl+Shift+V` paste.

## Layout

```
agent_tablet/
├── app.py         # Adw.Application entry point + base CSS
├── window.py      # main window: projects, tabs, Ctrl+B prefix, actions
├── spaces.py      # the tab strip of the current project
├── panes.py       # split panes inside a tab
├── agentstate.py  # working / blocked / idle detection
├── sidebar.py     # the history, shown in the Add session dialog
├── projects.py    # projects, their sessions and groups, saved as JSON
├── layout.py      # which sessions are in which tab and window
├── projectbar.py  # the project dropdown
├── projectlist.py # the current project's sessions
├── addsession.py  # the Add session dialog
├── store.py       # session discovery off the main thread, file monitors
├── sessions.py    # transcript discovery + statistics
├── providers.py   # per-agent adapters (Claude Code, Cursor)
├── state.py       # persistent app state (names, emojis, hidden, settings)
├── themes.py      # color themes + the terminal-workspace stylesheet
├── prefs.py       # preferences dialog
└── terminal.py    # VTE terminal tab spawning the agent CLI
data/
├── io.github.hernancontigiani.AgentTablet.desktop   # launcher template
├── icons/io.github.hernancontigiani.AgentTablet.svg # app icon
└── install.sh                              # install launcher + icon for current user
scripts/
├── build_deb.sh                            # build the .deb package into dist/
└── make_demo_data.py                       # fake sessions for screenshots/demos
```

## Development

```bash
make venv    # uv venv with --system-site-packages (GTK comes from the system) + dev tools
make ci      # the gate: ruff + pytest
make run
```

## Changes from Agent Session Manager

- New identity — name, icon, app id, command and config directory — so both apps can be installed
  at once; the original's state is imported once.
- A session's name is the one it has in Claude; a name set in the app applies only to sessions
  Claude never named.
- No favorites; the ones saved by Agent Session Manager are dropped on the next save.
- Projects replace spaces: the sidebar shows the sessions you chose, from any folder, instead of
  every folder Claude was used in; the history moves to the "Add session" dialog.
- A context ring by each session and on each tab, from the app's own Claude status line (passed
  with `--settings`, so nothing is written to your Claude settings), and an Integrations page.
- A Usage report: execution time and tokens per project and session, from the transcripts.
