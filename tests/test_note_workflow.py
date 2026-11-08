import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from note_workflow import Project, ROOT


class WorkflowLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Project(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def register(self):
        return self.project.register("test-article", "テスト素材（実在の記事ではない）",
                                     "https://note.com/test/n/test", "2024-01-31", "free")

    def test_ninety_day_deadline_final_record_and_history(self):
        row = self.register()
        self.assertEqual(row["monitor_until"], "2024-04-30")
        self.assertEqual(self.project.due(date(2024, 2, 6)), [])
        self.assertEqual(self.project.due(date(2024, 2, 7))[0]["action"], "observation_due")
        first = self.project.observe("test-article", "test fixture", "manual",
                                     likes=0, notes="テスト", observed_at="2024-02-07T10:00:00+09:00")
        record = json.loads(first.read_text(encoding="utf-8"))
        self.assertEqual(record["likes"], 0)
        self.assertIsNone(record["purchases"])
        self.assertFalse(record["is_final"])
        self.project.set_status("test-article", "paused", "テスト中の一時停止")
        self.assertEqual(self.project.due(date(2024, 3, 1)), [])
        self.assertEqual(self.project.due(date(2024, 4, 30))[0]["action"], "final_observation_required")
        self.assertEqual(self.project.read()[0]["monitoring_status"], "paused")
        final = self.project.observe("test-article", "test fixture", "manual",
                                     notes="表示を取得できなかったため数値は未取得。テスト。",
                                     observed_at="2024-04-30T10:00:00+09:00", final=True)
        self.assertTrue(json.loads(final.read_text(encoding="utf-8"))["is_final"])
        self.assertTrue(first.exists())
        self.assertEqual(self.project.read()[0]["monitoring_status"], "completed")
        self.assertEqual(self.project.due(date(2024, 5, 1)), [])
        self.assertGreaterEqual(len(list((self.project.root / ".history").glob("*/published_articles.csv"))), 2)

    def test_invalid_actions_leave_ledger_unchanged(self):
        self.register()
        original = self.project.ledger.read_bytes()
        with self.assertRaises(ValueError):
            self.register()
        with self.assertRaises(ValueError):
            self.project.observe("test-article", "test", "manual", likes=-1)
        with self.assertRaises(ValueError):
            self.project.observe("test-article", "test", "manual", likes=1,
                                 observed_at="2024-02-07T10:00:00+09:00", final=True)
        with self.assertRaises(ValueError):
            self.project.checkpoint(self.project.root.parent / "outside.md")
        self.assertEqual(self.project.ledger.read_bytes(), original)

    def test_new_themes_keep_all_previous_work(self):
        import shutil
        shutil.copytree(ROOT / "templates", self.project.root / "templates")
        first = self.project.new_theme("same-slug", "最初の素材")
        second = self.project.new_theme("same-slug", "別の素材")
        self.assertNotEqual(first, second)
        self.assertIn("最初の素材", (first / "brief.md").read_text(encoding="utf-8"))
        self.assertIn("別の素材", (second / "brief.md").read_text(encoding="utf-8"))
        self.assertEqual(len(list(first.glob("*.md"))), 9)


if __name__ == "__main__":
    unittest.main()
