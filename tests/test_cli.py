import io
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from tasky import storage
from tasky.cli import main


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = Path(self.tmp.name) / "tasks.txt"

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        """Run the CLI against the temp file; return (exit_code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        argv = ["--no-color", "--file", str(self.file), *args]
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def lines(self):
        return storage.load(self.file)


class AddAndListTests(CliTestCase):
    def test_add_creates_file_and_task(self):
        code, out, _ = self.run_cli("add", "Buy", "milk", "--project", "home", "-P", "A")
        self.assertEqual(code, 0)
        self.assertIn("Added #1", out)
        tasks = list(self.lines())
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].priority, "A")
        self.assertIn("home", tasks[0].projects)

    def test_add_with_due_validates(self):
        code, _, err = self.run_cli("add", "pay", "rent", "--due", "not-a-date")
        self.assertEqual(code, 1)
        self.assertIn("error", err)

    def test_list_default_hides_completed(self):
        self.run_cli("add", "task one")
        self.run_cli("add", "task two")
        self.run_cli("done", "1")
        code, out, _ = self.run_cli("list")
        self.assertEqual(code, 0)
        self.assertNotIn("task one", out)
        self.assertIn("task two", out)

    def test_list_all_shows_completed(self):
        self.run_cli("add", "task one")
        self.run_cli("done", "1")
        _, out, _ = self.run_cli("list", "--all")
        self.assertIn("task one", out)


class LifecycleTests(CliTestCase):
    def test_done_undone_roundtrip(self):
        self.run_cli("add", "something")
        self.run_cli("done", "1")
        self.assertTrue(list(self.lines())[0].completed)
        self.run_cli("undone", "1")
        self.assertFalse(list(self.lines())[0].completed)

    def test_priority_set_and_clear(self):
        self.run_cli("add", "thing")
        self.run_cli("pri", "1", "b")
        self.assertEqual(list(self.lines())[0].priority, "B")
        self.run_cli("pri", "1", "-")
        self.assertIsNone(list(self.lines())[0].priority)

    def test_edit(self):
        self.run_cli("add", "old text")
        self.run_cli("edit", "1", "new", "text", "+proj")
        self.assertEqual(list(self.lines())[0].description, "new text +proj")

    def test_remove_multiple_keeps_numbering(self):
        for i in range(1, 4):
            self.run_cli("add", f"task {i}")
        self.run_cli("rm", "1", "3")
        remaining = [t.description for t in self.lines()]
        self.assertEqual(remaining, ["task 2"])

    def test_out_of_range_number_errors(self):
        code, _, err = self.run_cli("done", "5")
        self.assertEqual(code, 1)
        self.assertIn("no task numbered 5", err)


class QueryReportTests(CliTestCase):
    def setUp(self):
        super().setUp()
        self.run_cli("add", "Ship release", "+work", "@office", "-P", "A", "--due", "2026-01-01")
        self.run_cli("add", "Buy groceries", "+home", "@errands")
        self.run_cli("add", "Write tests", "+work")

    def test_search(self):
        _, out, _ = self.run_cli("search", "groceries")
        self.assertIn("Buy groceries", out)
        self.assertNotIn("Ship release", out)

    def test_filter_by_project(self):
        _, out, _ = self.run_cli("list", "--project", "work")
        self.assertIn("Ship release", out)
        self.assertIn("Write tests", out)
        self.assertNotIn("Buy groceries", out)

    def test_overdue_filter(self):
        _, out, _ = self.run_cli("list", "--overdue")
        self.assertIn("Ship release", out)
        self.assertNotIn("Write tests", out)

    def test_projects_and_contexts_listing(self):
        _, out, _ = self.run_cli("projects")
        self.assertIn("+home", out)
        self.assertIn("+work", out)
        _, out, _ = self.run_cli("contexts")
        self.assertIn("@office", out)

    def test_stats(self):
        _, out, _ = self.run_cli("stats")
        self.assertIn("total", out)
        self.assertIn("pending", out)
        self.assertIn("overdue", out)

    def test_archive_moves_completed(self):
        self.run_cli("done", "2")
        code, out, _ = self.run_cli("archive")
        self.assertEqual(code, 0)
        self.assertIn("Archived 1", out)
        # completed task gone from the active file...
        self.assertTrue(all(not t.completed for t in self.lines()))
        # ...and present in the done file.
        done_file = storage.archive_path(self.file)
        self.assertTrue(done_file.exists())
        archived = storage.load(done_file)
        self.assertEqual(len(archived), 1)


class MiscTests(CliTestCase):
    def test_no_command_prints_help(self):
        code, out, _ = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("usage", out.lower())

    def test_path_command(self):
        _, out, _ = self.run_cli("path")
        self.assertIn("tasks.txt", out)


if __name__ == "__main__":
    unittest.main()
