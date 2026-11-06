# 04 — Projects, the session list and tabs

> **Status: built 2026-11-06 (see the execution log); not closed until B0's interactive results and
> the human's check by hand.** Written the same day, after plan 01 B2. Every product decision is
> taken (`plans/00-STATUS.md` §1 1.13–1.19). B0 needs the human's go-ahead before it runs (it creates throwaway sessions in their `~/.claude`).
>
> **Comes from:** a design session with the human on 2026-11-05/06, with an interactive mock-up
> in view: <https://claude.ai/artifact/8jxpcxpcJRoirrMRd2cgdo> (private to the human). Where each
> thing sits in the UI was decided on that mock-up; the mock-up's own quirks are not the design.
>
> **Replaces:** plan 01 B3 ("Projects that remember their sessions"). B3's text is in git
> (`git log -p -- plans/01-agent-tablet-fork.md`).
>
> **Exit when executed:**
> - What the user sees — projects and the dropdown, adding sessions, groups, tabs of two, closing
>   a tab stops its session, quitting and reopening, several windows, favorites gone — →
>   `README.md`, including its "what changed from upstream" part.
> - Rules that constrain code not written yet → `CLAUDE.md`, "Product rules": a session belongs to
>   one project at most; a session runs if and only if it has a tab, and is in at most one tab
>   across every window; a project is open in at most one window; the app's own state is JSON in
>   its own config directory.
> - How projects, membership, the tab ↔ process lifecycle, the saved layout and the window registry
>   are built, and **"Rejected, and why"** below → `docs/projects.md`, with its row in `CLAUDE.md`'s
>   subsystem table.
> - "Out of scope" below → `docs/NOT_BUILT_YET.md`, each entry with its trigger.
> - What B0 finds about the CLI → `docs/projects.md` (it is why the code launches sessions as it
>   does).
> - The rest → `git log`.

## Goal

Today the app opens on every folder Claude has ever been used in. This plan makes it open on **a
project**: a name and the sessions the user put in it, from any folder, remembered across restarts.
The tabs on the right are the sessions the user is working with now: a session runs while it has a
tab, and closing the tab stops it, as it does today. Several windows can be open, one project in
each.

## What already exists (verified 2026-11-06)

Cited by symbol, not by line: the tree was being reformatted while this was written.

- **Sidebar:** `SessionSidebar` (`sidebar.py`) holds the header with the app menu, the `top` widget
  (`SpacesPanel` from `spaces.py`: sections `spaces` and `agents`, the open tabs grouped by folder),
  then the `history` section: search, an accordion by folder of every known session, a Favorites
  group, a selection mode with bulk actions, and a row menu (open, Ghostty, fork, chat, rename,
  favorite, details, replay, copy id, export, reveal, hide, trash, delete).
- **The list model:** `SessionStore` (`store.py`) scans off the main thread, watches the agents'
  folders, and keeps one `SessionItem` (`models.py`) per session, reused across refreshes so
  bindings survive. `_apply` orders favorites first, then groups by folder. `FAV_GROUP` is in
  `models.py`.
- **A "space" is a folder**: `_page_space[page] = (folder, agent)` in `window.py`; `TabStrip`
  (`spaces.py`) shows only the current space's tabs; `_space_last` remembers each space's last tab;
  next/previous tab and `_goto_tab` stay inside the space.
- **Favorites and hidden sessions** are in `state.json` (`AppState` in `state.py`). Settings
  `sidebar_show_spaces`, `sidebar_show_agents`, `sidebar_show_history`, `sidebar_collapsed` drive
  the sections; Preferences shows the three toggles (`prefs.py`).
- **Splits:** `PaneContainer` (`panes.py`) nests `Gtk.Paned` without limit. Its `primary` pane
  carries the session, the agent state and the tab's lifetime; the others are shells
  (`MainWindow._split`, keys in `_prefix_commands`).
- **Agent state is per page**, from the primary pane's `agent-state` signal (`_on_agent_state`,
  `_page_state`); the row's status comes from `SessionStore.set_status` via `_sync_status`.
- **Closing a tab stops its session:** `_on_close_page` starts `_graceful_close`, which types the
  provider's `graceful_exit()` (`/exit` for Claude; `None` for Cursor, which force-closes) and
  force-closes after 40 polls of 300 ms (`_poll_graceful`).
- **The agent runs inside the user's shell:** `TerminalTab._spawn` (`terminal.py`) spawns `$SHELL`
  and types `_initial_command` into it, so aliases and environment apply. When `claude` exits the
  shell stays, and so does the tab; the tab closes only when the shell exits (`_on_process_exited`).
- **A new session's id is guessed:** `_resolve_transcript` polls
  `ClaudeProvider.latest_transcript_for_cwd`, which returns **the newest transcript in that folder**.
  If another session of the same folder exists, it matches that one at once — the wrong session. It
  gives up after 120 polls of 1.5 s.
- **The CLI has `--session-id <uuid>`** ("Use a specific session ID for the conversation") and
  `-n, --name` (checked in `claude --help`, Claude Code 2.1.319).
- **Discovery** skips only empty files (`ClaudeProvider.discover`): a transcript with no user
  message is still listed.
- **Several windows exist today:** `app.new-window` (`Ctrl+Shift+N`) in `app.py`; every
  `MainWindow` shares the app's one `AppState` and `SessionStore`, and has its own `Adw.TabView`.
- **Quitting** has no confirmation: no close-request handler in `window.py` or `app.py`.
- **Switchers:** `_quick_switch` lists every session in the store; `_goto_picker` lists the open
  tabs grouped by space. `QuickSwitcher` is in `switcher.py`.
- **Time** is read only through `agent_tablet/clock.py`; `tests/test_code_rules.py` enforces it.
- **The UI walk** is `tools/ui/check.py` (`STEPS`: title, history, search, preferences, about, no
  traceback), run by `make ui-check` (`docs/ui-verification.md`).
- **Upstream** (`r4nd3l/agent-session-manager`) is still at `07f72bd` (`git ls-remote`, 2026-11-06):
  its planned "Persistent spaces" has not started, so there is nothing to bring in.

## The design (decided 2026-11-06, `plans/00-STATUS.md` §1 1.13–1.18)

### Projects

- **A project is an id, a name, its sessions in order, and its groups.** No folders of its own.
- **A dropdown at the top of the sidebar** lists the projects, marks the current one, and creates a
  new one from a name. Names are unique, compared case-insensitively and trimmed.
- **The dropdown shows a count of *blocked* sessions in the other projects**, in every window.
- **A project called Default exists from the first start, empty.** It is an ordinary project.
- **A session belongs to one project at most.** Adding one that is in another project moves it
  ("Move here"), with its tab, even from another window.
- **Removing a session from a project never touches Claude's data.** If it is running, a
  confirmation says it will be stopped first.
- **Renaming and deleting a project** (§1 1.19): any project can
  be renamed; any can be deleted except the last one; deleting one with running sessions asks, then
  stops them; its sessions are only released, never touched.

### The session list (left)

- **Flat**, in the project's order, the user's groups first (in group order), then the sessions in
  no group under "No group" (the heading only when a group exists).
- **A row:** status dot, the session's name (plan 01 B2's order), the folder's **name** only
  (`guardian`), hidden when every member shares one folder. The context ring is plan 01 B4's and is
  not built here.
- **The row menu:** Open, Open beside the current tab (disabled when the tab is full or holds the
  session), Stop (only when running), Group ▸ (each group, No group, New group…), Remove from
  project. Rename, Details, Replay, Copy id, Export and Reveal keep their actions here too; Hide,
  Trash and Delete stay only in the "Add session" browser.
- **Groups** are the project's own, cross folders, and carry a color from a fixed palette of five,
  assigned in turn. An empty group disappears. They are not categories (plan 01 B5).
- **"Add session"** (a button under the list; the header's + opens it on "New"):
  - **Existing:** today's history browser (search, accordion by folder, hidden sessions, Hide,
    Trash, Delete, selection mode) inside a dialog. Each row gets "Add" (or "Move here" naming the
    other project, or "Added").
  - **New:** a **required** name, a folder (the folders of known sessions, or "Another folder…"
    with a folder chooser), and the provider. It runs the provider's new command with
    `--session-id <uuid chosen by the app>` and `-n <name>` in that folder.
- **A new session joins the project when Claude has created it**: when the store discovers its id
  with at least one user message. One closed before that leaves nothing in the project.
- **Favorites are removed**, and the `favorites` key leaves `state.json` on the next save.
- **Cursor sessions are members** under the same rules; Stop force-closes them.

### Tabs (right)

- **The tab strip shows the current project's tabs.** A tab shows its sessions' names (two joined
  by " │ "), the worst state of its panes (blocked > working > done > idle) and its group's color
  when every pane is in the same group. No folder.
- **A tab holds one or two panes**, side by side or stacked; a toggle swaps the orientation.
  "Open beside" puts a session in the second pane; `Ctrl+B v` / `Ctrl+B -` put a shell there. A
  third pane is refused with a toast.
- **A session is in at most one tab, across every window.** Opening one that has a tab selects it.
- **Double-click on a row** selects its tab, or opens one, resuming the session.
- **Chat and replay tabs** open in the current project, are not members, not saved, do not reopen.
- **Fork and "continue last session"** start a session that joins the current project under the
  new-session rule. A fork gets its id from `--session-id` too, if B0 shows the CLI allows it with
  `--fork-session`; otherwise the fork's id is read from the file the CLI creates.
- **Quick switcher** (`Ctrl+Shift+K`): the current project's sessions. **`Ctrl+B g`**: running
  sessions of every project, in every window; choosing one shows its project in its window.

### Stop, close, quit, reopen

- **A session runs if and only if it has a tab.** Closing the tab, closing its pane, the row's Stop
  and exiting inside the agent (`/exit`, Ctrl+D) all stop it, close its tab or pane, and leave its
  row *stopped*. Stopping is today's graceful `/exit`, then a force-close.
- **Exiting inside the agent closes the tab** because the command typed into the shell ends with
  `; exit` or `&& exit` (B0 decides which), so the shell ends with the agent. Aliases and
  environment keep applying, which `exec` would lose.
- **Closing a window with sessions running asks first**, naming them, then stops them. Closing the
  last window quits the app.
- **"Reopen tabs on start"**, in Preferences, **on by default**: the next start reopens each window
  with its project, and resumes the sessions that were in its tabs, with their splits and
  orientation. Off: one window, the last current project, no tabs. The projects' lists come back
  either way.

### Several windows

- **A project is open in at most one window.** Choosing it in another window's dropdown brings its
  window forward; the dropdown marks it "open in another window".
- **A window shows one project at a time** and keeps the tabs of every project it showed; a project
  is "in" a window while that window shows it or holds one of its tabs.
- **"New window"** opens a window on a project in no window; if every project is in one, on a new
  project the user names.
- **"Move here" across windows** moves the tab with `Adw.TabView.transfer_page`, without stopping
  the process.
- **Where a window opens on screen** is the system's choice: on Wayland the app cannot place it.

## Rejected, and why

| Alternative | Why not |
|---|---|
| A project is one or several folders (plan 01 B3) | A project mixes repos, and not every session of a folder belongs to it |
| A window per project, always (plan 01 B3) | The human works mostly in one window; a second window is for a second monitor, not the rule |
| A session in several projects | One process has one terminal: it cannot be a tab in two projects or two windows; the human would rather move it |
| The list flat when one folder, grouped by folder when mixed | Adding one session from another repo would reshape the whole list |
| Grouping by folder by default | The human groups by collaboration (a pair of sessions), which crosses folders |
| Closing a tab hides it and the session keeps running until stopped | A session working with no tab looks closed while it is not; one state (running = has a tab) is more intuitive and keeps today's behaviour |
| Keeping sessions alive after the app quits (tmux, dtach) | A second process supervisor to install and reason about; quitting stops them and reopening resumes them |
| Unlimited nested splits with sessions | Two panes are what the human uses; more is unreadable at a laptop's width |
| SQLite for projects | A few projects and hundreds of ids, one writer, read whole at start; JSON is readable and fixable by hand, as `state.json` is. SQLite is in the standard library if a later need (plan 01 B6) calls for queries |
| Guessing a new session's id from the newest transcript in its folder (today) | It matches another session of the same folder at once; the app picks the id with `--session-id` instead |
| `exec claude` to make the agent's exit close the tab | `exec` skips the user's aliases and shell functions, which typing into the shell exists to keep |
| The history browser as the main view | The project's list is the main view; every session Claude knows is one dialog away |

## Product decisions and the test that holds each

Every one is written **before** its code, in the block named. Names are the sentence they prove.

| Decision | Test (file) | Case |
|---|---|---|
| Default exists from the first start, empty | `test_a_missing_projects_file_starts_with_an_empty_default` (`test_projects.py`) | no file → one project "Default", no members, and it is current |
| A session belongs to one project at most | `test_adding_a_session_from_another_project_moves_it` | `s1` in A, add to B → A has no `s1`, B ends with `s1`; the call returns A |
| Names are unique | `test_a_project_name_is_unique_ignoring_case_and_spaces` | "Core" exists → " core " is refused; "Core 2" is accepted |
| Any project but the last can be deleted, and deleting releases its sessions | `test_the_last_project_cannot_be_deleted_and_deleting_releases_its_sessions` (`test_projects.py`) | one project → refused; A with `s1`, B → delete A → `owner(s1)` is `None`, B intact |
| An empty group disappears | `test_a_group_disappears_when_its_last_session_leaves` | group of `s1`, `s1` removed or regrouped → no group |
| Removing never touches Claude's files | `test_removing_a_session_leaves_its_transcript_byte_for_byte` | real transcript in `projects_dir`, bytes before == after |
| Projects are JSON, written by rename | `test_saving_writes_the_whole_file_through_a_temporary` | save → `projects.json` parses, no `.tmp` left; a failing write leaves the old file intact (`monkeypatch` `Path.replace` to raise) |
| An unreadable file is kept, not overwritten | `test_an_unreadable_projects_file_is_kept_aside_and_default_starts` | file `{` → renamed to `projects.json.broken`, Default current, the broken file's bytes intact |
| Unknown keys survive a save | `test_unknown_keys_in_a_project_survive_a_round_trip` | a project with `"folders": [...]` → still there after load/save (topic 2.9 must not be ruled out) |
| The folder shows as its name, hidden when shared | `test_the_folder_label_is_the_name_and_hidden_when_shared` | `/a/guardian` + `/b/fabric` → `guardian`, `fabric`; two in `/a/guardian` → no label |
| The blocked count is of other projects | `test_the_blocked_count_counts_only_other_projects` | A: 1 blocked, B: 2 blocked, current A → 2 |
| A tab holds two panes at most | `test_a_tab_layout_refuses_a_third_pane` (`test_layout.py`) | add a third → refused, layout unchanged |
| A session is in one tab at most | `test_a_session_already_in_a_tab_is_not_placed_in_another` | `s1` in tab 1, open `s1` → tab 1 selected, no new tab |
| Reopen follows the setting | `test_reopening_restores_tabs_only_when_the_setting_is_on` | saved two windows → on: both with their tabs; off: one window, last current project, no tabs |
| A reopened tab whose session left the project is dropped | `test_a_saved_tab_of_a_session_no_longer_a_member_is_dropped` | saved tab `s1`, `s1` removed → not restored |
| A project is in at most one window | `test_a_project_is_open_in_at_most_one_window` (`test_layout.py`) | A in window 1, window 2 asks for A → told window 1 |
| A new window takes a free project | `test_a_new_window_takes_a_project_in_no_window` | A, B; A in window 1 → B; both taken → none (the UI asks for a name) |
| Favorites leave `state.json` | `test_favorites_leave_state_json_on_the_next_save` (`test_state.py`) | state with `"favorites": [...]` → saved file has no `favorites` key |
| A new session carries its id and name | `test_a_new_session_command_carries_its_id_and_name` (`test_providers.py`) | id `u`, name `lm plan` → `claude --session-id u -n 'lm plan'`, quoted |
| The agent's exit ends the shell | `test_the_typed_command_ends_the_shell_with_the_agent` (`test_providers.py`) | the command typed into the shell ends with B0's separator and `exit` |
| A session joins only once it has a user message | `test_a_session_joins_its_project_only_after_a_user_message` (`test_projects.py`) | transcript with only a `custom-title` line → no; with a user line → yes |
| A new session's name is required | `test_a_new_session_needs_a_name_and_a_folder` (`test_projects.py`) | `""`, `"  "` → refused with our sentence; a folder that does not exist → refused |

## Out of scope

- Sessions that survive quitting the app.
- Dragging a session onto a tab's edge to split it, and reordering rows or tabs by dragging.
- More than two panes in a tab.
- Grouping or ordering tabs by group beyond the group's color.
- Choosing which monitor a window opens on.
- The context ring (plan 01 B4), categories (B5), cost (B6).
- Tabs that are not agents (a file to read or edit) and project folders to scope them
  (`plans/00-STATUS.md` §2, 2.9). The schema keeps unknown keys so they are not ruled out.

## Do not touch

- How transcripts are read (`sessions.py`, the providers' `discover`): this plan changes what the
  app shows, not what it reads.
- Moving a transcript to the trash and deleting it, with their confirmations.
- The `Ctrl+B` prefix and its keys, apart from refusing a third pane.
- The chat and replay tabs' own code (`chatsession*.py`, `replay*.py`).
- `classic` and `tui` styles: both get the new widgets; neither is removed.

## Execution blocks

Each block leaves `make ci` green. A block that changes the UI also runs `make ui-check`, **looks at
its screenshots**, and adds the steps named to `tools/ui/check.py`. The demo data the walk uses is
`scripts/make_demo_data.py`; B3 adds projects to it.

### B0 — What the CLI does (no code in `agent_tablet/`)

Needs the human's go-ahead in that session: it starts real `claude` sessions, which write
transcripts under their `~/.claude/projects/`. Run in a new empty folder under the scratchpad; at
the end, list the transcripts it created and ask the human before trashing them.

- [ ] `claude --session-id <uuid4> -n b0-probe` in that folder, then `/exit` before typing anything:
  does `~/.claude/projects/<folder>/<uuid>.jsonl` exist, and what does it hold?
- [ ] The same, send one message, `/exit`: the file has that id and a user line.
- [ ] `--resume <that id> --fork-session --session-id <uuid2>`: does the fork take `uuid2`? If the
  CLI refuses the pair, note the error.
- [ ] `--continue` in that folder: does it keep the session's id?
- [ ] The exit status of `claude` after `/exit`, after Ctrl+D twice, after Ctrl+C twice, and after
  a crash (`claude --session-id not-a-uuid`): `echo $?` in the shell each time.
- [ ] The same exit status for `cursor-agent`, if installed; if not, write that it was not checked.

**Decides:** `&& exit` if every clean way out returns 0 and a failure does not (a failing start then
leaves its message in a shell); `; exit` otherwise. Whether a fork takes `--session-id`. Whether a
session closed before its first message leaves a file (it does not change the rule: membership
waits for a user line).

**Verification:** the findings, with the commands and outputs, in the execution log; the human
confirms the transcripts to trash.

### B1 — Projects and layout as data (no GTK)

New `agent_tablet/projects.py`, pure Python, no `gi` import (assert it in `test_code_rules.py` with
the existing AST walk):

- `Group(name, color, members: list[str])`, `Project(id, name, members: list[str], groups:
  list[Group], extra: dict)`. `extra` holds unknown keys, written back as they came.
- `Projects` with `load(path)` and `save(path)`, the path passed in (resolved by the caller from
  `$XDG_CONFIG_HOME` when called, never at import). Missing file → Default. Unreadable or invalid →
  rename to `projects.json.broken` (replacing an older `.broken`), log it with the path in `extra`,
  start with Default, and report it so the window can show our own toast.
- Operations, each returning what the UI needs to say: `create(name)`, `rename(id, name)`,
  `delete(id)` (refused for the last project), `add(project_id, session_id)` →
  previous owner or `None`, `remove(project_id, session_id)`, `owner(session_id)`,
  `set_group(project_id, session_id, group_name | None)`, `new_group(project_id, name,
  session_id)`, `folder_labels(sessions)`, `blocked_elsewhere(current_id, states)`.
- `validate_new_session(name, folder) -> str | None`: our own sentence through `_()`, or `None`.
- `joins_project(lines) -> bool`: a user entry exists. It reads the transcript **incrementally**
  through the store's existing scan, not a new full read; the function only judges entries.
- File shape (`version: 1`):
  `{"version": 1, "current": "<id>", "projects": [{"id", "name", "members", "groups": [{"name",
  "color", "members"}]}], "windows": [...]}` — `windows` is B6's.

New `agent_tablet/layout.py`, pure Python: `TabLayout(panes: list[str], orientation)` with at
most two panes, `WindowLayout(project_ids, current, tabs: dict[project_id, list[TabLayout]])`,
`Layouts` that enforces "one session in one tab" and "one project in one window" across windows,
`new_window_project(...)`, and `restore(saved, members, reopen_tabs)`.

**Verification:** the tests of the table marked `test_projects.py` and `test_layout.py`, written
first and seen red (an inverted assertion, then restored); `make ci`.

### B2 — Favorites out; the store serves projects

- `state.py`: `favorites`, `is_favorite`, `toggle_favorite` go; `save` no longer writes the key.
  `store.py`: favorites grouping and `toggle_favorite` / `set_favorites` go; `_apply` groups by
  folder only. `models.py`: `FAV_GROUP` and the `favorite` property go. `sidebar.py`: the star,
  the "Add to / Remove from favorites" item and the two bulk buttons go. Their strings leave `po/`.
- `SessionStore` gains a second `Gio.ListStore` per window for the current project's rows, built
  from the **same** `SessionItem`s (bindings keep working), refreshed on `refreshed` and on project
  changes, in project order. Members the store does not know (a transcript trashed outside the app)
  are kept in `projects.json` and not shown.
- `AppState` owns the `Projects` instance and its path; one `save` call writes both files.

**Verification:** `test_favorites_leave_state_json_on_the_next_save`; existing tests that use
favorites are updated, not deleted, when they test something else; `make ci`; `make ui-check` —
the history step still passes, no star in the screenshot.

### B3 — Starting and stopping a session

- `Provider.new_command(options, session_id, name)`: Claude adds `--session-id` and `-n`
  (`shlex.quote`); Cursor ignores both if its CLI has no such flags (B0).
- The command typed into the shell ends with B0's separator and `exit`, for every agent command
  (new, resume, fork, continue). A shell pane gets nothing typed, as today.
- `TerminalTab` for a new session knows its id from the start; `_resolve_transcript` waits for
  **that** path (`<projects_dir>/<encoded cwd>/<id>.jsonl`) with no attempt limit while the pane is
  alive, and stops when the pane is gone. `latest_transcript_for_cwd` stays only for "continue last
  session", where "the newest" is what the user asked for.
- Membership of new, fork and continue sessions: the window keeps `pending: dict[session_id,
  project_id]`; on the store's `refreshed`, an id that `joins_project` accepts is added to its
  project, and the row appears.
- `_on_process_exited` already closes the tab; after it, the row shows *stopped* through
  `_sync_status`. Closing a pane holding a session stops that session the same way the tab does
  (`_graceful_close` per pane, not per page).
- Agent state per pane: `_page_state` becomes per session; the page's state is the worst of its
  panes; notifications name the pane's session.
- `scripts/make_demo_data.py` writes a `projects.json` with two projects (one single-folder, one
  mixed, one group) for the walk.

**Verification:** the B3 tests in the table; `make ci`. By hand (the human, their machine): a new
session in a folder that already has one joins as itself; `/exit` and Ctrl+D close the tab and the
row says *stopped*; a session closed before its first message does not appear.

### B4 — The sidebar: dropdown, project list, "Add session"

- New `agent_tablet/projectbar.py`: the dropdown (`Gtk.MenuButton` with a popover: projects, the
  current marked, blocked counts, "open in another window", a "New project" entry; rename and
  delete per project). New `agent_tablet/projectlist.py`: the rows and group
  headings of the design, bound to the project model of B2, the row menu, and "Add session" under
  the list.
- `AddSessionDialog` (`Adw.Dialog`): "Existing" hosts `SessionSidebar` as it is minus favorites,
  with an `add` mode where a row's button adds or moves; "New" has the name, folder and provider
  fields and runs `validate_new_session`.
- `SpacesPanel` and its `spaces` / `agents` sections go, with `sidebar_show_*` and
  `sidebar_collapsed` for them and their Preferences toggles; `TabStrip` stays in `spaces.py`.
- The header's + opens the dialog on "New"; its menu items (advanced, continue, chat) stay.
- `_quick_switch` lists the current project's members.
- New walk steps: `step_project_list` (the demo's mixed project: group heading, folder names),
  `step_project_dropdown` (opens it, the other project with its blocked count),
  `step_add_session` (the dialog, both pages). They replace `step_history` and `step_search`,
  whose checks move inside `step_add_session`. Menus are opened before any typing (Broadway's
  trap, `docs/ui-verification.md`).

**Verification:** `make ci`; `make ui-check` and its screenshots: the list with its group, folder
names in the mixed project and none in the single-folder one, the dropdown, the dialog. Compared by
eye with the mock-up's layout.

### B5 — Tabs: the project's strip, two panes, open beside

- `_page_space[page]` holds the project id instead of the folder; `TabStrip`, `_space_last`,
  next/previous and `_goto_tab` therefore work per project unchanged. The tab title joins the panes'
  names; the strip shows the rolled-up state and the group color.
- `PaneContainer` refuses a third pane; "Open beside" builds a `TerminalTab` for the session and
  splits the current tab with it. A toggle in the tab menu swaps orientation.
- `_pages` maps every session to its page, both panes included; "open" of a session with a page
  selects it, in another window too (B6 adds the window).
- Switching project in the dropdown changes the strip and the list, stops nothing.
- `_goto_picker` lists every running session of every project in this window (B6 extends it to all
  windows).
- Walk step `step_two_panes`: open a demo session, open another beside it, screenshot.

**Verification:** `test_layout.py`'s tab tests; `make ci`; `make ui-check` with the two-pane
screenshot. By hand: two sessions in a tab, close one pane → that session *stopped*, the other
keeps working; the tab's color is the group's.

### B6 — Quitting, reopening, several windows

- A close-request handler on `MainWindow`: if any pane runs an agent, a dialog names them; on
  confirm, every pane is stopped (`_graceful_close`), then the window closes. The last window
  closing quits.
- Every change to tabs (open, close, split, orientation, project switch) writes `windows` in
  `projects.json` through `Layouts`, debounced like the sidebar width.
- `app.py` keeps the `Layouts` registry for all windows. On start: `restore(...)` with the new
  setting `reopen_tabs` (default `True`, in `DEFAULT_SETTINGS` and a Preferences switch).
- The dropdown in one window marks projects in another and brings that window forward.
  "New window" uses `new_window_project`, or asks for a new project's name.
- "Move here" across windows: `transfer_page` to this window's `TabView`, then the project move.
- `_goto_picker` spans every window.

**Verification:** the B6 tests in the table; `make ci`; `make ui-check` (one window; the walk does
not quit the app). By hand, on the human's machine with two monitors: two windows with two
projects; choose the first project in the second window → the first window comes forward; quit
with sessions running → the dialog names them; reopen → both windows, their tabs and splits, each
session answering what it was doing. With "Reopen tabs on start" off: one window, no tabs.

### B7 — Exit

- `README.md`: the user's view of projects, tabs, stop, quit and reopen, windows, favorites gone,
  in its "what changed from upstream" part.
- `CLAUDE.md`, "Product rules": the four rules of the header. The subsystem table gets
  `docs/projects.md` ("Changing projects, tabs, windows, or how a session is started or stopped").
- `docs/projects.md`: the model, membership, the lifecycle, the layout file and the registry, what
  B0 found about the CLI, and "Rejected, and why".
- `docs/NOT_BUILT_YET.md`: each "Out of scope" line with its trigger.
- `plans/00-STATUS.md`: the plan's row leaves §3, its closing note goes to
  `docs/history/plans/00-STATUS.md`; this file is deleted.

**Verification:** `make ci` (`nothing_lost.py` included); `README.md` read against the running app.

## Execution log

**Before B0 (2026-11-06):** plan 01 B2 was executed first in the same session, at the human's
choice, so the list shows Claude's names from this plan's first screenshot.

**B0 (2026-11-06), partial.** Run with `claude -p` (print mode skips the folder-trust prompt) in a
scratchpad folder, Claude Code 2.1.319:
- `--session-id <uuid> -n b0-probe`: the transcript is `<that uuid>.jsonl`; its first lines are
  `custom-title` and `agent-name` with the name, before the first `user` line.
- `--resume <id> --fork-session --session-id <uuid2>`: the fork's transcript is `<uuid2>.jsonl`. The
  CLI accepts the pair, so a fork gets its id from the app.
- `--continue`: no new transcript; the newest session of the folder grows. It keeps its id.
- A failing start (`--session-id not-a-uuid`) exits with 1, interactive or not.
- `cursor-agent` is not installed on this machine: its exit status was not checked.
- Not answered yet: the exit status after `/exit`, Ctrl+D and Ctrl+C, and whether a session left
  before any message writes a file. Driving the TUI from a pty failed at the folder-trust prompt
  (Esc is read as "cancel", and the choice did not register), so the human runs a short script in
  their own terminal.

**B1 (2026-11-06).** `agent_tablet/projects.py` and `agent_tablet/layout.py`, no GTK (asserted by
`test_projects_and_layout_stay_free_of_gtk` in `tests/test_code_rules.py`). Deviations:
- `blocked_elsewhere` takes the `Projects` it counts in, not only the current id.
- `Layouts` also has `release` (a deleted project leaves every window), `close_tab` and
  `move_session` ("Move here" carries the tab), which B4–B6 call.
- An unreadable file includes one with no project or a newer `version`; a session listed in two
  projects by hand stays in the first.
- One known folder plus sessions with no folder counts as "shared", so no label shows.
- Two tests were written against the design wrongly and corrected, not the code: the folder case
  above, and a project shown and left without tabs is free for another window (1.18).
- Each key test seen red against a defect injected from a throwaway test file.

**B2 (2026-11-06).** Favorites removed from `state.py`, `models.py`, `store.py`, `sidebar.py` (star,
menu item, bulk buttons), `window.py` (the action) and `prefs.py`; `state.json` loses the key on the
next save (`test_favorites_leave_state_json_on_the_next_save`, seen red). The demo data, the walk's
`history` step, `README.md`, the metainfo and `CLAUDE.md`'s introduction follow (its old line is in
`docs/history/root/CLAUDE.md`). Deviations:
- The per-window list model of the current project and `AppState` owning `Projects` move to B3/B4,
  where their first consumer is built: no model without its caller.
- `po/` still holds the favorites' msgids: this machine has neither `xgettext` nor `msgfmt`, so the
  catalogues are not regenerated; stale msgids are unused, not wrong.

**B3 (2026-11-06), built except one line.** Providers build `--session-id`/`-n` and the fork's
`--session-id` (`_identity_flags`; Cursor's base returns none); `transcript_path` knows a
session's file from its folder and id. `TerminalTab` takes `new_id`/`name`, its resolver waits for
that exact file while the pane lives, and exposes `transcript_id`. The window keeps `_joining`
entries (new, fork and continue tabs) and adds a session to its project on the store's refresh once
`joins_project` accepts it, also after its tab closed. `AppState` owns `projects` and
`save_projects()`, next to `state.json`. Deviations:
- `joins_project` judges the `Session` (its preview is the first typed message), not raw entries:
  discovery already reads the first lines, so nothing is read twice.
- Per-pane agent state and stopping a pane's session move to B5, where a tab first holds two
  sessions; the demo `projects.json` moved to B4, where the walk first uses it.
- **Pending:** the separator before `exit` in the typed command (`&& exit` or `; exit`) waits for
  B0's interactive results.

**B4 (2026-11-06).** `projectbar.py` (the dropdown: switch, create, rename, delete, blocked
counts), `projectlist.py` (rows with state dot, Claude's name, folder name; group headings; the
row menu), `addsession.py` (the history browser with Add / Added / "Move from …", and the New page
with a required name). `SpacesPanel`, `SectionHeader`, the section settings and their Preferences
toggles are gone; `TabStrip` stays in `spaces.py`. Deviations:
- **The space→project switch of B5 was done here**: with the spaces panel gone, the strip had to
  show the project's tabs or other folders' tabs would have been unreachable. `_page_space` holds
  the project id; a selection that lands on another project's tab returns to this one's.
- Opening a session makes it a member: of this project if it has none, or its own project is shown
  first. "Advanced" and the header's provider items go through the dialog, so every new session
  has a name.
- A hidden session keeps its item in the store, so hiding one in the history does not take it out
  of its project's list.
- The demo has three projects (Default empty, "Client work" mixing two folders with a group,
  "Dotfiles" in one folder). Walk steps: `project-list`, `project-dropdown` (after a restart, since
  Broadway's popovers stop after a dialog), `add-session`. Clicks inside the Add session dialog do
  not reach it under Broadway after the earlier steps, so its Add / Move / New are left to the
  human's check; the step asserts the dialog, both pages and the history.
- The blocked count in the dropdown is not in the walk: the demo runs no agent.


**B5 (2026-11-06).** `PaneContainer` holds two panes at most (`split` returns `False` when full),
lets the primary pane close (the other becomes primary) and swaps orientation (tab menu "Swap the
split's orientation"). The window keeps the agent state per pane (`_pane_state`), rolls it up per
tab, and finds a pane's page from the widget (`_page_of`), so a pane can move between tabs.
"Open beside the current tab" (row menu) builds the session's terminal in the second pane, or moves
it there without stopping when it was alone in its own tab. Closing a pane, the row's Stop, and the
agent's own exit stop that pane's session only; closing the tab exits every agent in it. A tab of
two sessions is titled "A │ B"; its strip button carries the group color when both are in one
group. The typed command ends with `&& exit` (`typed_command`), **provisionally** until B0's
interactive results: a failing start then leaves its message in the shell. Deviations:
- The row's "⋯" builds its menu on each click and drops it on close, as the history's row menu
  does: one popover per row made the walk's tool unable to tell which one was open.
- The walk's isolated environment puts a stand-in `claude` first in `PATH`
  (`tools/ui/session.py`, `FAKE_AGENT`): it waits for `/exit`, so opening a tab logs in nowhere.
  Taking the agents' CLIs out of `PATH` instead was tried and dropped: the app then sees no
  provider and lists no session.
- Under Broadway, once a terminal is up, popovers and then clicks stop reaching the app; the walk's
  `open-tab` step runs last, after a restart, and "Open beside", a pane closing and the tab's two
  names are left to the human's check.

**B6 (2026-11-06).** Each window keeps its own project (`MainWindow(project_id=…)`) and can say
what would reopen (`snapshot()`); the application builds a `Layouts` from them when it needs one
(`App.layouts`, `window_holding`, `held_elsewhere`, `all_states`), so nothing keeps a second copy
of which tab is where. Every change to tabs saves `windows` in `projects.json`, debounced; a window
closing on its own leaves the saved layout, and the last one keeps it whole before its tabs stop.
Closing a window with agents running names them and stops them ("Stop and close"). On start,
`restore(...)` with the new `reopen_tabs` setting (on by default; Preferences, "Start") opens each
window on its project and resumes its tabs, their second panes and their orientation, once the
store's first scan is in. "New window" takes a project in no window, or asks for a new project's
name. Choosing a project another window holds brings that window forward; the dropdown marks it
and counts blocked sessions across windows. "Move here" moves a lone tab across windows with
`transfer_page`; a tab shared with another session is not moved. `Ctrl+B g` lists every window's
tabs. Deviations:
- The window reaches the application through a small `Protocol` (`_Host`), so a bare window
  without the application still works (the tests' and the walk's).
- The walk checks that a tab opens and that its layout is written (read from the session's
  `projects.json` by hand once: `[{'current': 'demo-1', 'tabs': {'demo-1': [{'panes': [...],
  'orientation': 'horizontal'}]}}]`); reopening on start needs a third restart, which the tool
  cannot do, so it is the human's check. The two new Broadway traps are in `docs/ui-verification.md`.

**B7 (2026-11-06), partial.** `README.md` was kept current block by block. `CLAUDE.md` has the two
rules of the header (sessions, tabs, projects and windows in one rule; JSON state) and the
`docs/projects.md` row; `docs/projects.md` and four `docs/NOT_BUILT_YET.md` entries are written.
`docs/projects.md` states `&& exit` as built; if B0's interactive results contradict it, the
separator, its test and that paragraph change together. **Not done:** deleting this plan and
closing its row, which wait for B0's results and the human's check.

**For the human, by hand** (their machine, their data; Broadway cannot reach these):
1. Add session → Existing: "Add" puts a session in the project; one of another project shows
   "Move from …" and moves, with its tab if open. New: a name and a folder (also "Another folder…")
   start a session that joins the list after its first message; one closed before that does not.
2. A row's ⋯: Stop closes its tab and leaves it *stopped*; "Open beside" puts it in the current
   tab's second pane (moving it from its own tab if open); closing one pane stops only that one;
   "Swap the split's orientation" from the tab's menu; groups: new, move, "No group".
3. `/exit` and Ctrl+D inside Claude close the tab and leave the row *stopped*.
4. The dropdown: create, rename, delete (the last one refuses); a blocked session in another
   project shows its count.
5. Quit with sessions running: the dialog names them; reopen: the tabs, their splits and their
   windows come back, each session answering what it was doing. With "Reopen tabs on start" off:
   one window, no tabs.
6. Two windows (Ctrl+Shift+N) with two projects: choosing the first window's project in the second
   brings the first forward; "Move from …" across windows moves the tab.

