"""The in-memory task list and query engine.

Tasks are addressed by a 1-based number that mirrors their position in the
file, which keeps the CLI ergonomic (``tasky done 3``). Filtering preserves
these numbers so a filtered view can still be acted on by number.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Iterable, Optional

from .model import Task

__all__ = ["TaskList", "NumberedTask", "Query", "TaskError"]


class TaskError(Exception):
    """Raised for user-facing errors such as an out-of-range task number."""


@dataclass(frozen=True)
class NumberedTask:
    """A task paired with its stable 1-based number."""

    number: int
    task: Task


# Sort keys usable from the CLI. Each maps to a function producing a
# comparable value; ``None``-ish values are pushed to the end for date keys.
def _due_key(t: Task):
    d = t.due
    return (d is None, d or date.max)


def _priority_key(t: Task):
    # No priority sorts after 'Z'.
    return t.priority or "["


_SORT_KEYS: dict[str, Callable[[Task], object]] = {
    "priority": _priority_key,
    "due": _due_key,
    "created": lambda t: (t.creation_date is None, t.creation_date or date.max),
    "text": lambda t: t.description.lower(),
    "project": lambda t: (t.projects[0].lower() if t.projects else "~"),
}

SORT_KEYS = tuple(_SORT_KEYS)


@dataclass
class Query:
    """A declarative filter over a task list.

    All supplied criteria must match (logical AND). ``project`` / ``context``
    matching is case-insensitive. ``text`` is a case-insensitive substring
    search over the full task line.
    """

    project: Optional[str] = None
    context: Optional[str] = None
    priority: Optional[str] = None
    status: str = "pending"  # "pending" | "done" | "all"
    text: Optional[str] = None
    due_before: Optional[date] = None
    overdue: bool = False

    def matches(self, task: Task, today: Optional[date] = None) -> bool:
        today = today or date.today()

        if self.status == "pending" and task.completed:
            return False
        if self.status == "done" and not task.completed:
            return False

        if self.project is not None:
            if self.project.lstrip("+").lower() not in {p.lower() for p in task.projects}:
                return False
        if self.context is not None:
            if self.context.lstrip("@").lower() not in {c.lower() for c in task.contexts}:
                return False
        if self.priority is not None:
            if (task.priority or "").upper() != self.priority.upper():
                return False
        if self.text is not None:
            if self.text.lower() not in task.format().lower():
                return False
        if self.overdue and not task.is_overdue(today):
            return False
        if self.due_before is not None:
            due = task.due
            if due is None or due >= self.due_before:
                return False
        return True


class TaskList:
    """An ordered collection of tasks with CRUD and query operations."""

    def __init__(self, tasks: Optional[Iterable[Task]] = None) -> None:
        self._tasks: list[Task] = list(tasks or [])

    # -- container basics ---------------------------------------------------

    def __len__(self) -> int:
        return len(self._tasks)

    def __iter__(self):
        return iter(self._tasks)

    def numbered(self) -> list[NumberedTask]:
        return [NumberedTask(i + 1, t) for i, t in enumerate(self._tasks)]

    def get(self, number: int) -> Task:
        self._check(number)
        return self._tasks[number - 1]

    def _check(self, number: int) -> None:
        if not isinstance(number, int) or number < 1 or number > len(self._tasks):
            raise TaskError(f"no task numbered {number} (have 1..{len(self._tasks)})")

    # -- create / update / delete ------------------------------------------

    def add(self, task: Task) -> NumberedTask:
        self._tasks.append(task)
        return NumberedTask(len(self._tasks), task)

    def complete(self, number: int, on: Optional[date] = None) -> Task:
        task = self.get(number)
        if not task.completed:
            task.completed = True
            task.completion_date = on or date.today()
        return task

    def uncomplete(self, number: int) -> Task:
        task = self.get(number)
        task.completed = False
        task.completion_date = None
        return task

    def set_priority(self, number: int, priority: Optional[str]) -> Task:
        task = self.get(number)
        if priority is None:
            task.priority = None
        else:
            priority = priority.upper()
            if len(priority) != 1 or not priority.isalpha():
                raise TaskError("priority must be a single letter A-Z")
            task.priority = priority
        return task

    def edit(self, number: int, description: str) -> Task:
        task = self.get(number)
        task.description = description.strip()
        return task

    def remove(self, number: int) -> Task:
        self._check(number)
        return self._tasks.pop(number - 1)

    def purge_completed(self) -> list[Task]:
        """Remove and return all completed tasks."""
        done = [t for t in self._tasks if t.completed]
        self._tasks = [t for t in self._tasks if not t.completed]
        return done

    # -- query --------------------------------------------------------------

    def query(
        self,
        q: Optional[Query] = None,
        sort: Optional[str] = None,
        reverse: bool = False,
        today: Optional[date] = None,
    ) -> list[NumberedTask]:
        q = q or Query()
        result = [nt for nt in self.numbered() if q.matches(nt.task, today)]
        if sort:
            if sort not in _SORT_KEYS:
                raise TaskError(f"unknown sort key {sort!r}; choose from {', '.join(SORT_KEYS)}")
            key = _SORT_KEYS[sort]
            result.sort(key=lambda nt: key(nt.task), reverse=reverse)
        elif reverse:
            result.reverse()
        return result

    def projects(self) -> list[str]:
        return _sorted_unique(p for t in self._tasks for p in t.projects)

    def contexts(self) -> list[str]:
        return _sorted_unique(c for t in self._tasks for c in t.contexts)

    # -- reporting ----------------------------------------------------------

    def stats(self, today: Optional[date] = None) -> dict:
        today = today or date.today()
        pending = [t for t in self._tasks if not t.completed]
        done = [t for t in self._tasks if t.completed]
        overdue = [t for t in pending if t.is_overdue(today)]
        by_priority: dict[str, int] = {}
        for t in pending:
            if t.priority:
                by_priority[t.priority] = by_priority.get(t.priority, 0) + 1
        total = len(self._tasks)
        return {
            "total": total,
            "pending": len(pending),
            "done": len(done),
            "overdue": len(overdue),
            "projects": len(self.projects()),
            "contexts": len(self.contexts()),
            "by_priority": dict(sorted(by_priority.items())),
            "completion_rate": (len(done) / total) if total else 0.0,
        }


def _sorted_unique(items: Iterable[str]) -> list[str]:
    return sorted(set(items), key=str.lower)
