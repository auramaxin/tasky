import io
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

from tasky.cli import main
from tasky.core import TaskList
from tasky.model import Task


TODAY = date(2026, 10, 5)


def sample() -> TaskList:
    return TaskList([
        Task.parse("(A) Ship release +work @office due:2026-01-01"),  # pending, overdue
        Task.parse("x write tests +work"),                             # done
        Task.parse("buy groceries +home"),                             # pending
        Task.parse("read a book"),                                     # pending, no project
    ])


class ProjectReportTests(unittest.TestCase):
    def test_counts_per_project(self):
        rows = {r["project"]: r for r in sample().project_report(TODAY)}
        self.assertEqual(rows["work"]["total"], 2)
        self.assertEqual(rows["work"]["pending"], 1)
        self.assertEqual(rows["work"]["done"], 1)
        self.assertEqual(rows["work"]["overdue"], 1)
        self.assertEqual(rows["home"]["pending"], 1)

    def test_no_project_bucket(self):
        rows = sample().project_report(TODAY)
        names = [r["project"] for r in rows]
        self.assertIn("(no project)", names)
        # no-project bucket is always last
        self.assertEqual(names[-1], "(no project)")

    def test_multi_project_task_counted_in_each(self):
        tl = TaskList([Task.parse("cross-cutting +a +b")])
        rows = {r["project"]: r for r in tl.project_report(TODAY)}
        self.assertEqual(rows["a"]["total"], 1)
        self.assertEqual(rows["b"]["total"], 1)

    def test_empty_list(self):
        self.assertEqual(TaskList().project_report(TODAY), [])


class ReportCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = Path(self.tmp.name) / "tasks.txt"

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--no-color", "--file", str(self.file), *args])
        return code, out.getvalue()

    def test_report_output(self):
        self.run_cli("add", "Ship release", "+work", "-P", "A")
        self.run_cli("add", "Buy groceries", "+home")
        code, out = self.run_cli("report")
        self.assertEqual(code, 0)
        self.assertIn("project", out)
        self.assertIn("+work", out)
        self.assertIn("+home", out)

    def test_report_empty(self):
        code, out = self.run_cli("report")
        self.assertEqual(code, 0)
        self.assertIn("No tasks to report", out)


if __name__ == "__main__":
    unittest.main()
