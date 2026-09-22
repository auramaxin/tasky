import unittest
from datetime import date

from tasky.core import Query, TaskError, TaskList
from tasky.model import Task


def sample() -> TaskList:
    return TaskList([
        Task.parse("(A) 2026-09-20 Ship release +work @office due:2026-09-19"),
        Task.parse("(C) buy groceries +home @errands due:2030-01-01"),
        Task.parse("x 2026-09-18 old thing +work"),
        Task.parse("write tests +work @office"),
    ])


TODAY = date(2026, 9, 21)


class CrudTests(unittest.TestCase):
    def test_add_and_numbering(self):
        tl = TaskList()
        nt = tl.add(Task(description="first"))
        self.assertEqual(nt.number, 1)
        self.assertEqual(len(tl), 1)

    def test_complete_and_uncomplete(self):
        tl = sample()
        tl.complete(4, on=TODAY)
        self.assertTrue(tl.get(4).completed)
        self.assertEqual(tl.get(4).completion_date, TODAY)
        tl.uncomplete(4)
        self.assertFalse(tl.get(4).completed)
        self.assertIsNone(tl.get(4).completion_date)

    def test_set_and_clear_priority(self):
        tl = sample()
        tl.set_priority(4, "b")
        self.assertEqual(tl.get(4).priority, "B")
        tl.set_priority(4, None)
        self.assertIsNone(tl.get(4).priority)

    def test_bad_priority(self):
        tl = sample()
        with self.assertRaises(TaskError):
            tl.set_priority(4, "AB")

    def test_edit(self):
        tl = sample()
        tl.edit(2, "buy less +home")
        self.assertEqual(tl.get(2).description, "buy less +home")

    def test_remove_out_of_range(self):
        tl = sample()
        with self.assertRaises(TaskError):
            tl.remove(99)

    def test_purge_completed(self):
        tl = sample()
        removed = tl.purge_completed()
        self.assertEqual(len(removed), 1)
        self.assertEqual(len(tl), 3)


class QueryTests(unittest.TestCase):
    def test_default_pending_only(self):
        rows = sample().query(today=TODAY)
        self.assertEqual([nt.number for nt in rows], [1, 2, 4])

    def test_filter_by_project(self):
        rows = sample().query(Query(project="work"), today=TODAY)
        self.assertEqual([nt.number for nt in rows], [1, 4])

    def test_filter_by_context_and_priority(self):
        rows = sample().query(Query(context="office"), today=TODAY)
        self.assertEqual([nt.number for nt in rows], [1, 4])
        rows = sample().query(Query(priority="A"), today=TODAY)
        self.assertEqual([nt.number for nt in rows], [1])

    def test_status_all_and_done(self):
        self.assertEqual(len(sample().query(Query(status="all"), today=TODAY)), 4)
        self.assertEqual(len(sample().query(Query(status="done"), today=TODAY)), 1)

    def test_overdue(self):
        rows = sample().query(Query(overdue=True), today=TODAY)
        self.assertEqual([nt.number for nt in rows], [1])

    def test_text_search_is_case_insensitive(self):
        rows = sample().query(Query(status="all", text="GROCERIES"), today=TODAY)
        self.assertEqual([nt.number for nt in rows], [2])

    def test_due_before(self):
        rows = sample().query(Query(due_before=date(2026, 9, 20)), today=TODAY)
        self.assertEqual([nt.number for nt in rows], [1])

    def test_sort_by_priority(self):
        rows = sample().query(Query(status="all"), sort="priority", today=TODAY)
        # A, C, then the two without a priority.
        self.assertEqual([nt.task.priority for nt in rows][:2], ["A", "C"])

    def test_sort_by_due(self):
        rows = sample().query(Query(status="all"), sort="due", today=TODAY)
        self.assertEqual(rows[0].task.due, date(2026, 9, 19))

    def test_unknown_sort_key(self):
        with self.assertRaises(TaskError):
            sample().query(sort="nope")


class ReportTests(unittest.TestCase):
    def test_projects_and_contexts(self):
        self.assertEqual(sample().projects(), ["home", "work"])
        self.assertEqual(sample().contexts(), ["errands", "office"])

    def test_stats(self):
        s = sample().stats(TODAY)
        self.assertEqual(s["total"], 4)
        self.assertEqual(s["pending"], 3)
        self.assertEqual(s["done"], 1)
        self.assertEqual(s["overdue"], 1)
        self.assertEqual(s["by_priority"], {"A": 1, "C": 1})
        self.assertAlmostEqual(s["completion_rate"], 0.25)


if __name__ == "__main__":
    unittest.main()
