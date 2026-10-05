"""Command-line interface for tasky.

Run ``tasky --help`` or ``python -m tasky --help`` for usage.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Optional, Sequence

from . import __version__
from .core import Query, SORT_KEYS, TaskError, TaskList
from .model import Task, parse_date
from . import storage

# --- terminal colouring ----------------------------------------------------

_ANSI = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
}

_PRIORITY_COLOUR = {"A": "red", "B": "yellow", "C": "green"}


class Painter:
    """Wraps text in ANSI codes, or not, depending on ``enabled``."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def __call__(self, text: str, *styles: str) -> str:
        if not self.enabled or not styles:
            return text
        codes = "".join(_ANSI[s] for s in styles if s in _ANSI)
        return f"{codes}{text}{_ANSI['reset']}"


def _colour_enabled(no_color_flag: bool) -> bool:
    if no_color_flag or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


# --- rendering -------------------------------------------------------------

def _render_task(number: int, task: Task, width: int, paint: Painter, today: date) -> str:
    num = paint(f"{number:>{width}}", "dim")

    if task.completed:
        body = paint(task.format()[2:].strip() or task.description, "dim")
        return f"{num} {paint('x', 'dim')} {body}"

    pieces = []
    if task.priority:
        colour = _PRIORITY_COLOUR.get(task.priority, "magenta")
        pieces.append(paint(f"({task.priority})", colour, "bold"))
    pieces.append(_render_description(task, paint, today))
    return f"{num} " + " ".join(pieces)


def _render_description(task: Task, paint: Painter, today: date) -> str:
    """Colourise +projects, @contexts and an overdue due: tag inside the text."""
    words = task.description.split()
    out = []
    overdue = task.is_overdue(today)
    for word in words:
        if word.startswith("+") and len(word) > 1:
            out.append(paint(word, "cyan"))
        elif word.startswith("@") and len(word) > 1:
            out.append(paint(word, "blue"))
        elif word.startswith("due:"):
            out.append(paint(word, "red", "bold") if overdue else paint(word, "magenta"))
        else:
            out.append(word)
    return " ".join(out)


def _print_list(rows, paint: Painter, today: date, header: Optional[str] = None) -> None:
    if not rows:
        print("No matching tasks.")
        return
    width = max(len(str(nt.number)) for nt in rows)
    if header:
        print(paint(header, "bold"))
    for nt in rows:
        print(_render_task(nt.number, nt.task, width, paint, today))


# --- argument parsing ------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tasky",
        description="A small, human-readable command-line task manager.",
    )
    p.add_argument("--version", action="version", version=f"tasky {__version__}")
    p.add_argument("-f", "--file", help="path to the task file (default: $TASKY_FILE or ~/.tasky/tasks.txt)")
    p.add_argument("--no-color", action="store_true", help="disable coloured output")

    sub = p.add_subparsers(dest="command", metavar="<command>")

    # add
    sp = sub.add_parser("add", aliases=["a"], help="add a new task")
    sp.add_argument("text", nargs="+", help="task description (may include +project @context due:DATE)")
    sp.add_argument("-P", "--priority", help="priority letter A-Z")
    sp.add_argument("--project", action="append", default=[], help="add a +project (repeatable)")
    sp.add_argument("--context", action="append", default=[], help="add an @context (repeatable)")
    sp.add_argument("--due", help="due date YYYY-MM-DD")
    sp.add_argument("--no-date", action="store_true", help="do not record a creation date")
    sp.set_defaults(func=cmd_add)

    # list
    sp = sub.add_parser("list", aliases=["ls"], help="list tasks")
    _add_filter_args(sp)
    sp.add_argument("--sort", choices=SORT_KEYS, help="sort key")
    sp.add_argument("-r", "--reverse", action="store_true", help="reverse the order")
    sp.add_argument("--json", action="store_true", help="output matching tasks as JSON")
    sp.set_defaults(func=cmd_list)

    # done / undone
    sp = sub.add_parser("done", aliases=["do"], help="mark task(s) complete")
    sp.add_argument("numbers", nargs="+", type=int, help="task number(s)")
    sp.set_defaults(func=cmd_done)

    sp = sub.add_parser("undone", help="mark task(s) not complete")
    sp.add_argument("numbers", nargs="+", type=int, help="task number(s)")
    sp.set_defaults(func=cmd_undone)

    # priority
    sp = sub.add_parser("pri", help="set or clear a task's priority")
    sp.add_argument("number", type=int)
    sp.add_argument("priority", help="letter A-Z, or '-'/'none' to clear")
    sp.set_defaults(func=cmd_pri)

    # edit
    sp = sub.add_parser("edit", help="replace a task's description")
    sp.add_argument("number", type=int)
    sp.add_argument("text", nargs="+")
    sp.set_defaults(func=cmd_edit)

    # remove
    sp = sub.add_parser("rm", aliases=["remove"], help="delete task(s)")
    sp.add_argument("numbers", nargs="+", type=int)
    sp.set_defaults(func=cmd_rm)

    # search
    sp = sub.add_parser("search", help="full-text search across all tasks")
    sp.add_argument("text", nargs="+")
    sp.set_defaults(func=cmd_search)

    # projects / contexts
    sub.add_parser("projects", help="list all projects").set_defaults(func=cmd_projects)
    sub.add_parser("contexts", help="list all contexts").set_defaults(func=cmd_contexts)

    # stats
    sub.add_parser("stats", help="show a summary report").set_defaults(func=cmd_stats)

    # report
    sub.add_parser("report", help="per-project breakdown of task counts").set_defaults(func=cmd_report)

    # archive
    sub.add_parser("archive", help="move completed tasks to the done file").set_defaults(func=cmd_archive)

    # path
    sub.add_parser("path", help="print the active task file path").set_defaults(func=cmd_path)

    return p


def _add_filter_args(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("-p", "--project", help="only tasks in +PROJECT")
    sp.add_argument("-c", "--context", help="only tasks in @CONTEXT")
    sp.add_argument("-P", "--priority", help="only tasks with priority LETTER")
    sp.add_argument("-s", "--search", help="only tasks matching TEXT")
    sp.add_argument("-a", "--all", action="store_true", help="include completed tasks")
    sp.add_argument("--done", action="store_true", help="only completed tasks")
    sp.add_argument("--overdue", action="store_true", help="only overdue tasks")
    sp.add_argument("--due-before", help="only tasks due before YYYY-MM-DD")


# --- command context -------------------------------------------------------

class Context:
    def __init__(self, args: argparse.Namespace) -> None:
        self.path = Path(args.file).expanduser() if args.file else storage.default_path()
        self.paint = Painter(_colour_enabled(args.no_color))
        self.today = date.today()
        self.tasks: TaskList = storage.load(self.path)

    def save(self) -> None:
        storage.save(self.path, self.tasks)


def _query_from_args(args: argparse.Namespace) -> Query:
    status = "pending"
    if args.done:
        status = "done"
    elif args.all:
        status = "all"
    due_before = parse_date(args.due_before) if getattr(args, "due_before", None) else None
    return Query(
        project=args.project,
        context=args.context,
        priority=args.priority,
        status=status,
        text=args.search,
        due_before=due_before,
        overdue=args.overdue,
    )


# --- commands --------------------------------------------------------------

def cmd_add(ctx: Context, args: argparse.Namespace) -> int:
    description = " ".join(args.text).strip()
    for project in args.project:
        tag = "+" + project.lstrip("+")
        if tag not in description.split():
            description += f" {tag}"
    for context in args.context:
        tag = "@" + context.lstrip("@")
        if tag not in description.split():
            description += f" {tag}"
    if args.due:
        parse_date(args.due)  # validate; raises ValueError on bad input
        if "due:" not in description:
            description += f" due:{args.due}"

    task = Task(
        description=description.strip(),
        priority=args.priority,
        creation_date=None if args.no_date else ctx.today,
    )
    nt = ctx.tasks.add(task)
    ctx.save()
    print(f"Added #{nt.number}: {ctx.paint(task.format(), 'green')}")
    return 0


def cmd_list(ctx: Context, args: argparse.Namespace) -> int:
    rows = ctx.tasks.query(_query_from_args(args), sort=args.sort, reverse=args.reverse, today=ctx.today)
    if getattr(args, "json", False):
        payload = [{"number": nt.number, **nt.task.to_dict()} for nt in rows]
        print(json.dumps(payload, indent=2))
        return 0
    _print_list(rows, ctx.paint, ctx.today)
    if rows:
        print(ctx.paint(f"-- {len(rows)} task(s)", "dim"))
    return 0


def cmd_done(ctx: Context, args: argparse.Namespace) -> int:
    for number in args.numbers:
        task = ctx.tasks.complete(number, on=ctx.today)
        print(f"Completed #{number}: {task.description}")
    ctx.save()
    return 0


def cmd_undone(ctx: Context, args: argparse.Namespace) -> int:
    for number in args.numbers:
        task = ctx.tasks.uncomplete(number)
        print(f"Reopened #{number}: {task.description}")
    ctx.save()
    return 0


def cmd_pri(ctx: Context, args: argparse.Namespace) -> int:
    clear = args.priority.lower() in {"-", "none", ""}
    task = ctx.tasks.set_priority(args.number, None if clear else args.priority)
    if clear:
        print(f"Cleared priority on #{args.number}")
    else:
        print(f"Set #{args.number} to ({task.priority})")
    ctx.save()
    return 0


def cmd_edit(ctx: Context, args: argparse.Namespace) -> int:
    task = ctx.tasks.edit(args.number, " ".join(args.text))
    ctx.save()
    print(f"Edited #{args.number}: {task.format()}")
    return 0


def cmd_rm(ctx: Context, args: argparse.Namespace) -> int:
    # Remove high numbers first so earlier numbers stay valid mid-loop.
    for number in sorted(set(args.numbers), reverse=True):
        task = ctx.tasks.remove(number)
        print(f"Removed #{number}: {task.description}")
    ctx.save()
    return 0


def cmd_search(ctx: Context, args: argparse.Namespace) -> int:
    q = Query(status="all", text=" ".join(args.text))
    rows = ctx.tasks.query(q, today=ctx.today)
    _print_list(rows, ctx.paint, ctx.today)
    return 0


def cmd_projects(ctx: Context, args: argparse.Namespace) -> int:
    projects = ctx.tasks.projects()
    if not projects:
        print("No projects.")
    for name in projects:
        print(ctx.paint("+" + name, "cyan"))
    return 0


def cmd_contexts(ctx: Context, args: argparse.Namespace) -> int:
    contexts = ctx.tasks.contexts()
    if not contexts:
        print("No contexts.")
    for name in contexts:
        print(ctx.paint("@" + name, "blue"))
    return 0


def cmd_report(ctx: Context, args: argparse.Namespace) -> int:
    rows = ctx.tasks.project_report(ctx.today)
    if not rows:
        print("No tasks to report.")
        return 0
    paint = ctx.paint

    def display(name: str) -> str:
        return name if name == ctx.tasks.NO_PROJECT else "+" + name

    name_w = max(len("project"), max(len(display(r["project"])) for r in rows))
    header = f"{'project':<{name_w}}  {'pend':>4}  {'done':>4}  {'over':>4}  {'total':>5}"
    print(paint(header, "bold"))
    for r in rows:
        over = f"{r['overdue']:>4}"
        if r["overdue"]:
            over = paint(over, "red")
        print(
            f"{display(r['project']):<{name_w}}  "
            f"{r['pending']:>4}  {r['done']:>4}  {over}  {r['total']:>5}"
        )
    return 0


def cmd_stats(ctx: Context, args: argparse.Namespace) -> int:
    s = ctx.tasks.stats(ctx.today)
    paint = ctx.paint
    print(paint("tasky summary", "bold"))
    print(f"  total       {s['total']}")
    print(f"  pending     {s['pending']}")
    print(f"  done        {s['done']}")
    print(f"  overdue     {paint(str(s['overdue']), 'red') if s['overdue'] else '0'}")
    print(f"  projects    {s['projects']}")
    print(f"  contexts    {s['contexts']}")
    print(f"  completion  {s['completion_rate'] * 100:.0f}%")
    if s["by_priority"]:
        breakdown = ", ".join(f"({k}) {v}" for k, v in s["by_priority"].items())
        print(f"  priorities  {breakdown}")
    return 0


def cmd_archive(ctx: Context, args: argparse.Namespace) -> int:
    done = ctx.tasks.purge_completed()
    if not done:
        print("Nothing to archive.")
        return 0
    dest = storage.archive_path(ctx.path)
    storage.append_lines(dest, done)
    ctx.save()
    print(f"Archived {len(done)} task(s) to {dest}")
    return 0


def cmd_path(ctx: Context, args: argparse.Namespace) -> int:
    print(ctx.path)
    return 0


# --- entry point -----------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        parser.print_help()
        return 0

    try:
        ctx = Context(args)
        return args.func(ctx, args)
    except (TaskError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
