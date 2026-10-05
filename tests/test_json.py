import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

from tasky.cli import main
from tasky.model import Task


class ToDictTests(unittest.TestCase):
    def test_to_dict_fields(self):
        t = Task.parse("(A) 2026-09-20 Ship +work @office due:2026-10-01")
        d = t.to_dict()
        self.assertEqual(d["description"], "Ship +work @office due:2026-10-01")
        self.assertFalse(d["completed"])
        self.assertEqual(d["priority"], "A")
        self.assertEqual(d["creation_date"], "2026-09-20")
        self.assertIsNone(d["completion_date"])
        self.assertEqual(d["projects"], ["work"])
        self.assertEqual(d["contexts"], ["office"])
        self.assertEqual(d["due"], "2026-10-01")
        self.assertEqual(d["tags"]["due"], "2026-10-01")
        self.assertEqual(d["raw"], t.format())

    def test_to_dict_is_json_serializable(self):
        t = Task.parse("x 2026-09-21 2026-09-20 done thing")
        # Should not raise.
        json.dumps(t.to_dict())


class JsonListCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = Path(self.tmp.name) / "tasks.txt"

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        out = io.StringIO()
        argv = ["--no-color", "--file", str(self.file), *args]
        with redirect_stdout(out):
            code = main(argv)
        return code, out.getvalue()

    def test_list_json_is_valid_and_structured(self):
        self.run_cli("add", "Buy milk", "+home", "@errands", "-P", "B")
        self.run_cli("add", "Write code", "+work")
        code, out = self.run_cli("list", "--json")
        self.assertEqual(code, 0)
        data = json.loads(out)  # must be valid JSON
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["number"], 1)
        self.assertEqual(data[0]["priority"], "B")
        self.assertIn("home", data[0]["projects"])
        self.assertEqual(data[1]["number"], 2)

    def test_json_respects_filters(self):
        self.run_cli("add", "Buy milk", "+home")
        self.run_cli("add", "Write code", "+work")
        _, out = self.run_cli("list", "--json", "--project", "work")
        data = json.loads(out)
        self.assertEqual(len(data), 1)
        self.assertIn("work", data[0]["projects"])

    def test_json_empty_is_valid_array(self):
        _, out = self.run_cli("list", "--json")
        self.assertEqual(json.loads(out), [])


if __name__ == "__main__":
    unittest.main()
