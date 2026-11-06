"""Projects: a name and the sessions the user put in them, from any folder.

Saved as JSON in the app's own config directory. A session belongs to one project at most, so
membership has one owner to ask. Nothing here reads or writes an agent's files.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .i18n import _
from .sessions import Session

log = logging.getLogger(__name__)

VERSION = 1
FILE_NAME = "projects.json"
DEFAULT_NAME = "Default"
GROUP_COLORS = ("#5ec4b6", "#c17be0", "#e0b45b", "#7fb2ff", "#e57c9a")


class ProjectError(ValueError):
    """A refused change; its message is a sentence for the user."""


@dataclass
class Group:
    name: str
    color: str
    members: list[str] = field(default_factory=list)


@dataclass
class Project:
    id: str
    name: str
    members: list[str] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)  # keys a later version wrote, kept as they came


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _key(name: str) -> str:
    return name.strip().casefold()


class _Invalid(ValueError):
    pass


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise _Invalid
    return list(value)


def _project_from(data: Any, owned: set[str]) -> Project:
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("id"), str)
        or not isinstance(data.get("name"), str)
    ):
        raise _Invalid
    members = [sid for sid in _strings(data.get("members", [])) if sid not in owned]
    owned.update(members)
    groups = []
    for raw in data.get("groups") or []:
        if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
            raise _Invalid
        in_group = [sid for sid in _strings(raw.get("members", [])) if sid in members]
        if in_group:
            groups.append(Group(raw["name"], str(raw.get("color") or GROUP_COLORS[0]), in_group))
    extra = {k: v for k, v in data.items() if k not in ("id", "name", "members", "groups")}
    return Project(data["id"], data["name"], members, groups, extra)


class Projects:
    def __init__(self, projects: list[Project], current: str) -> None:
        self.projects = projects
        self.current = current
        self.windows: list[Any] = []  # the saved window layouts, read and written by layout.py
        self.extra: dict[str, Any] = {}
        self.broken: Path | None = None  # where an unreadable file was moved on load

    # -- persistence -----------------------------------------------------------------------

    @classmethod
    def fresh(cls) -> Projects:
        default = Project(_new_id(), DEFAULT_NAME)
        return cls([default], default.id)

    @classmethod
    def load(cls, path: Path) -> Projects:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return cls.fresh()
        try:
            return cls.from_dict(json.loads(text))
        except (json.JSONDecodeError, _Invalid):
            broken = path.with_name(FILE_NAME + ".broken")
            path.replace(broken)
            log.warning("unreadable projects file moved aside", extra={"path": str(broken)})
            projects = cls.fresh()
            projects.broken = broken
            return projects

    @classmethod
    def from_dict(cls, data: Any) -> Projects:
        if (
            not isinstance(data, dict)
            or data.get("version") != VERSION
            or not isinstance(data.get("projects"), list)
        ):
            raise _Invalid
        owned: set[str] = set()
        projects = [_project_from(raw, owned) for raw in data["projects"]]
        if not projects:
            raise _Invalid
        ids = [p.id for p in projects]
        current = data.get("current")
        loaded = cls(projects, current if current in ids else ids[0])
        windows = data.get("windows", [])
        loaded.windows = windows if isinstance(windows, list) else []
        loaded.extra = {
            k: v for k, v in data.items() if k not in ("version", "current", "projects", "windows")
        }
        return loaded

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.extra,
            "version": VERSION,
            "current": self.current,
            "projects": [
                {
                    **p.extra,
                    "id": p.id,
                    "name": p.name,
                    "members": list(p.members),
                    "groups": [
                        {"name": g.name, "color": g.color, "members": list(g.members)} for g in p.groups
                    ],
                }
                for p in self.projects
            ],
            "windows": self.windows,
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(FILE_NAME + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            tmp.replace(path)
        except OSError:
            tmp.unlink(missing_ok=True)
            raise

    # -- lookups -------------------------------------------------------------------------

    def get(self, project_id: str) -> Project:
        for project in self.projects:
            if project.id == project_id:
                return project
        raise KeyError(project_id)

    def owner(self, session_id: str) -> Project | None:
        return next((p for p in self.projects if session_id in p.members), None)

    def rows(self, project_id: str) -> list[tuple[Group | None, list[str]]]:
        """The list's sections: each group with its sessions, then the sessions in no group."""
        project = self.get(project_id)
        grouped = {sid for g in project.groups for sid in g.members}
        rows: list[tuple[Group | None, list[str]]] = [(g, list(g.members)) for g in project.groups]
        loose = [sid for sid in project.members if sid not in grouped]
        if loose:
            rows.append((None, loose))
        return rows

    # -- projects ------------------------------------------------------------------------

    def _check_name(self, name: str, keep: Project | None = None) -> str:
        name = name.strip()
        if not name:
            raise ProjectError(_("A project needs a name."))
        if any(_key(p.name) == _key(name) for p in self.projects if p is not keep):
            raise ProjectError(_("There is already a project with that name."))
        return name

    def create(self, name: str) -> Project:
        project = Project(_new_id(), self._check_name(name))
        self.projects.append(project)
        return project

    def rename(self, project_id: str, name: str) -> None:
        project = self.get(project_id)
        project.name = self._check_name(name, keep=project)

    def delete(self, project_id: str) -> list[str]:
        """Remove a project; returns the sessions it released."""
        if len(self.projects) == 1:
            raise ProjectError(_("The last project cannot be deleted."))
        project = self.get(project_id)
        self.projects.remove(project)
        if self.current == project_id:
            self.current = self.projects[0].id
        return list(project.members)

    # -- membership ----------------------------------------------------------------------

    def add(self, project_id: str, session_id: str) -> Project | None:
        """Put a session in a project; returns the project it was taken from, if another."""
        target = self.get(project_id)
        previous = self.owner(session_id)
        if previous is target:
            return None
        if previous is not None:
            self.remove(previous.id, session_id)
        target.members.append(session_id)
        return previous

    def remove(self, project_id: str, session_id: str) -> None:
        project = self.get(project_id)
        if session_id in project.members:
            project.members.remove(session_id)
        self._ungroup(project, session_id)

    # -- groups --------------------------------------------------------------------------

    def _ungroup(self, project: Project, session_id: str) -> None:
        for group in project.groups:
            if session_id in group.members:
                group.members.remove(session_id)
        project.groups = [g for g in project.groups if g.members]

    def new_group(self, project_id: str, name: str, session_id: str) -> Group:
        project = self.get(project_id)
        name = name.strip()
        if not name:
            raise ProjectError(_("A group needs a name."))
        if any(_key(g.name) == _key(name) for g in project.groups):
            raise ProjectError(_("There is already a group with that name."))
        self._ungroup(project, session_id)
        group = Group(name, GROUP_COLORS[len(project.groups) % len(GROUP_COLORS)], [session_id])
        project.groups.append(group)
        return group

    def set_group(self, project_id: str, session_id: str, group_name: str | None) -> None:
        project = self.get(project_id)
        target = next((g for g in project.groups if g.name == group_name), None) if group_name else None
        self._ungroup(project, session_id)
        if target is not None and target in project.groups:
            target.members.append(session_id)
        elif target is not None:  # it held only this session and was dropped: bring it back
            target.members = [session_id]
            project.groups.append(target)


def folder_labels(cwds: dict[str, str | None]) -> dict[str, str]:
    """Each session's folder by its name, or nothing when every session shares one folder."""
    folders = {cwd for cwd in cwds.values() if cwd}
    if len(folders) <= 1:
        return dict.fromkeys(cwds, "")
    return {sid: (Path(cwd).name or cwd) if cwd else "" for sid, cwd in cwds.items()}


def blocked_elsewhere(projects: Projects, current_id: str, states: dict[str, str]) -> int:
    return sum(
        1
        for p in projects.projects
        if p.id != current_id
        for sid in p.members
        if states.get(sid) == "blocked"
    )


def joins_project(session: Session) -> bool:
    """A new session joins its project once Claude has a message the user typed in it: one closed
    before that is not kept. The preview is the first such message."""
    return bool(session.preview)


def validate_new_session(name: str, folder: str) -> str | None:
    if not name.strip():
        return _("Give the session a name: sessions find each other by it.")
    if not folder or not Path(folder).is_dir():
        return _("That folder does not exist.")
    return None
