"""Task data model plus an original text (de)serializer.

A task is stored on a single line. The on-disk grammar tasky understands is::

    [x ] [(P) ] [completion-date ] [creation-date ] description

* ``x `` marks a completed task.
* ``(P)`` is a single upper-case priority letter A-Z.
* dates are ISO ``YYYY-MM-DD``. A completed task may carry two leading dates
  (completion then creation); a pending task carries at most one (creation).
* the description is free text that may embed ``+project`` tags,
  ``@context`` tags, and ``key:value`` metadata such as ``due:2026-09-25``.

The format is deliberately compatible in spirit with the widely used todo.txt
convention so files stay human-readable, but every line of parsing and
formatting logic here is original.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

__all__ = ["Task", "parse_date"]

# --- regular expressions used by the parser -------------------------------

_PRIORITY_RE = re.compile(r"^\(([A-Z])\)(?=\s|$)")
_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?=\s|$)")
_PROJECT_RE = re.compile(r"(?:^|\s)\+([^\s]+)")
_CONTEXT_RE = re.compile(r"(?:^|\s)@([^\s]+)")
# a key:value tag: key is word-ish, value is non-space and contains no ':'
_TAG_RE = re.compile(r"(?:^|\s)([A-Za-z0-9_]+):([^\s:]+)(?=\s|$)")


def parse_date(text: str) -> date:
    """Parse an ISO ``YYYY-MM-DD`` string into a :class:`datetime.date`.

    Raises :class:`ValueError` on anything else, including impossible dates
    such as ``2026-13-40``.
    """
    return datetime.strptime(text, "%Y-%m-%d").date()


def _try_date(text: str) -> Optional[date]:
    try:
        return parse_date(text)
    except ValueError:
        return None


@dataclass
class Task:
    """A single task.

    ``description`` is the canonical free text and keeps ``+project``,
    ``@context`` and ``key:value`` tags inline. The derived collections are
    exposed as read-only properties so the description always round-trips.
    """

    description: str = ""
    completed: bool = False
    priority: Optional[str] = None
    creation_date: Optional[date] = None
    completion_date: Optional[date] = None

    def __post_init__(self) -> None:
        self.description = (self.description or "").strip()
        if self.priority is not None:
            self.priority = self.priority.upper()
            if not re.fullmatch(r"[A-Z]", self.priority):
                raise ValueError(f"priority must be a single letter A-Z, got {self.priority!r}")

    # -- derived metadata ---------------------------------------------------

    @property
    def projects(self) -> list[str]:
        """Project tags (``+foo``) in order of first appearance, de-duplicated."""
        return _unique(_PROJECT_RE.findall(self.description))

    @property
    def contexts(self) -> list[str]:
        """Context tags (``@home``) in order of first appearance, de-duplicated."""
        return _unique(_CONTEXT_RE.findall(self.description))

    @property
    def tags(self) -> dict[str, str]:
        """``key:value`` metadata. Later duplicates win, matching left-to-right reads."""
        return {k: v for k, v in _TAG_RE.findall(self.description)}

    @property
    def due(self) -> Optional[date]:
        """The ``due:`` date if present and valid, else ``None``."""
        raw = self.tags.get("due")
        return _try_date(raw) if raw else None

    def is_overdue(self, today: Optional[date] = None) -> bool:
        today = today or date.today()
        due = self.due
        return due is not None and not self.completed and due < today

    def to_dict(self) -> dict:
        """A JSON-serializable view of the task.

        Dates are rendered as ISO ``YYYY-MM-DD`` strings (or ``None``), and the
        derived ``projects`` / ``contexts`` / ``tags`` / ``due`` fields are
        included so consumers don't have to re-parse the description. ``raw`` is
        the canonical stored line.
        """
        return {
            "description": self.description,
            "completed": self.completed,
            "priority": self.priority,
            "creation_date": self.creation_date.isoformat() if self.creation_date else None,
            "completion_date": self.completion_date.isoformat() if self.completion_date else None,
            "projects": self.projects,
            "contexts": self.contexts,
            "tags": self.tags,
            "due": self.due.isoformat() if self.due else None,
            "raw": self.format(),
        }

    # -- (de)serialization --------------------------------------------------

    @classmethod
    def parse(cls, line: str) -> "Task":
        """Build a :class:`Task` from a single stored line.

        Whitespace-only lines are not valid tasks; callers should filter them
        out before calling this.
        """
        s = line.strip()
        if not s:
            raise ValueError("cannot parse an empty task line")

        completed = False
        priority: Optional[str] = None
        completion_date: Optional[date] = None
        creation_date: Optional[date] = None

        # 1. completion marker: a leading lowercase 'x' as its own token.
        if s == "x" or s.startswith("x "):
            completed = True
            s = s[1:].lstrip()

        # 2. optional priority.
        m = _PRIORITY_RE.match(s)
        if m:
            priority = m.group(1)
            s = s[m.end():].lstrip()

        # 3. leading dates. A completed line may have two (completion, then
        #    creation); a pending line has at most one (creation).
        leading: list[date] = []
        max_dates = 2 if completed else 1
        while len(leading) < max_dates:
            dm = _DATE_RE.match(s)
            if not dm:
                break
            d = _try_date(dm.group(1))
            if d is None:
                break
            leading.append(d)
            s = s[dm.end():].lstrip()

        if completed:
            if len(leading) == 2:
                completion_date, creation_date = leading
            elif len(leading) == 1:
                completion_date = leading[0]
        else:
            if leading:
                creation_date = leading[0]

        return cls(
            description=s,
            completed=completed,
            priority=priority,
            creation_date=creation_date,
            completion_date=completion_date,
        )

    def format(self) -> str:
        """Serialize back to a single stored line."""
        parts: list[str] = []
        if self.completed:
            parts.append("x")
        if self.priority:
            parts.append(f"({self.priority})")
        if self.completed:
            if self.completion_date:
                parts.append(self.completion_date.isoformat())
                # only emit the creation date if we also have a completion date,
                # otherwise a lone date would be misread as the completion date.
                if self.creation_date:
                    parts.append(self.creation_date.isoformat())
        else:
            if self.creation_date:
                parts.append(self.creation_date.isoformat())
        if self.description:
            parts.append(self.description)
        return " ".join(parts)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.format()


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
