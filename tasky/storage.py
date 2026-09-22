"""Loading and saving task files.

The store is a UTF-8 text file with one task per line. Blank lines and lines
beginning with ``#`` are treated as comments and preserved on save so a
hand-edited file keeps its structure.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .core import TaskList
from .model import Task

__all__ = ["default_path", "archive_path", "load", "save", "append_lines"]

ENV_VAR = "TASKY_FILE"


def default_path() -> Path:
    """Resolve the active task file.

    Order of precedence: ``$TASKY_FILE`` -> ``$HOME/.tasky/tasks.txt``.
    """
    env = os.environ.get(ENV_VAR)
    if env:
        return Path(env).expanduser()
    return Path.home() / ".tasky" / "tasks.txt"


def archive_path(path: Path) -> Path:
    """The companion ``done`` file that sits next to ``path``."""
    return path.with_name("done" + path.suffix if path.suffix else path.name + ".done")


def load(path: Path) -> TaskList:
    """Read a :class:`~tasky.core.TaskList` from ``path``.

    A missing file yields an empty list rather than an error, so the first
    ``add`` on a fresh machine just works.
    """
    tasks: list[Task] = []
    if not path.exists():
        return TaskList()
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            tasks.append(Task.parse(stripped))
    return TaskList(tasks)


def save(path: Path, tasks: TaskList) -> None:
    """Write ``tasks`` to ``path`` atomically (write-temp-then-replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for task in tasks:
            fh.write(task.format() + "\n")
    os.replace(tmp, path)


def append_lines(path: Path, tasks: list[Task]) -> None:
    """Append serialized ``tasks`` to ``path``, creating it if needed."""
    if not tasks:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        for task in tasks:
            fh.write(task.format() + "\n")
