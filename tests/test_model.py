import unittest
from datetime import date

from tasky.model import Task, parse_date


class ParseTests(unittest.TestCase):
    def test_plain_task(self):
        t = Task.parse("Buy milk")
        self.assertFalse(t.completed)
        self.assertIsNone(t.priority)
        self.assertEqual(t.description, "Buy milk")

    def test_priority_and_creation_date(self):
        t = Task.parse("(A) 2026-09-20 Call the bank")
        self.assertEqual(t.priority, "A")
        self.assertEqual(t.creation_date, date(2026, 9, 20))
        self.assertEqual(t.description, "Call the bank")

    def test_completed_with_two_dates(self):
        t = Task.parse("x 2026-09-21 2026-09-20 Write report")
        self.assertTrue(t.completed)
        self.assertEqual(t.completion_date, date(2026, 9, 21))
        self.assertEqual(t.creation_date, date(2026, 9, 20))
        self.assertEqual(t.description, "Write report")

    def test_completed_with_priority_retained(self):
        t = Task.parse("x (B) 2026-09-21 Deploy")
        self.assertTrue(t.completed)
        self.assertEqual(t.priority, "B")
        self.assertEqual(t.completion_date, date(2026, 9, 21))
        self.assertIsNone(t.creation_date)

    def test_projects_contexts_tags(self):
        t = Task.parse("Ship v2 +release @work due:2026-10-01")
        self.assertEqual(t.projects, ["release"])
        self.assertEqual(t.contexts, ["work"])
        self.assertEqual(t.tags["due"], "2026-10-01")
        self.assertEqual(t.due, date(2026, 10, 1))

    def test_duplicate_projects_deduped_in_order(self):
        t = Task.parse("+a do +b then +a")
        self.assertEqual(t.projects, ["a", "b"])

    def test_bad_date_is_treated_as_text(self):
        t = Task.parse("2026-13-40 weird date")
        self.assertIsNone(t.creation_date)
        self.assertEqual(t.description, "2026-13-40 weird date")

    def test_empty_line_rejected(self):
        with self.assertRaises(ValueError):
            Task.parse("   ")


class FormatTests(unittest.TestCase):
    def test_roundtrip_pending(self):
        line = "(A) 2026-09-20 Call the bank +money @phone"
        self.assertEqual(Task.parse(line).format(), line)

    def test_roundtrip_completed(self):
        line = "x 2026-09-21 2026-09-20 Write report +docs"
        self.assertEqual(Task.parse(line).format(), line)

    def test_format_completed_without_creation_date(self):
        t = Task(description="thing", completed=True, completion_date=date(2026, 9, 21))
        self.assertEqual(t.format(), "x 2026-09-21 thing")

    def test_invalid_priority_rejected(self):
        with self.assertRaises(ValueError):
            Task(description="x", priority="AA")


class OverdueTests(unittest.TestCase):
    def test_overdue(self):
        t = Task.parse("pay rent due:2026-01-01")
        self.assertTrue(t.is_overdue(date(2026, 9, 21)))

    def test_completed_is_not_overdue(self):
        t = Task.parse("x pay rent due:2026-01-01")
        self.assertFalse(t.is_overdue(date(2026, 9, 21)))

    def test_parse_date_valid(self):
        self.assertEqual(parse_date("2026-02-28"), date(2026, 2, 28))


if __name__ == "__main__":
    unittest.main()
