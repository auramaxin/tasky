"""tasky - a small, human-readable command-line task manager.

tasky stores tasks as plain text lines that are easy to read, edit, and
version-control. It supports priorities, projects, contexts, due dates,
filtering, searching, sorting, reporting, and archiving.

This package is inspired in *scope* by todo.txt-cli and Taskwarrior, but the
implementation (parser, data model, query engine, and CLI) is written from
scratch.
"""

from .model import Task
from .core import TaskList

__all__ = ["Task", "TaskList", "__version__"]

__version__ = "0.1.0"
