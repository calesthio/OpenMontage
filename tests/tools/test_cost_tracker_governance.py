from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from lib.config_model import BudgetMode
from tools.cost_tracker import CostTracker


class CostTrackerGovernanceTests(unittest.TestCase):
    def test_warn_mode_marks_over_budget_reservation(self) -> None:
        with self.subTest("warning is recorded and persisted"):
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as temp_dir:
                log_path = Path(temp_dir) / "cost_log.json"
                tracker = CostTracker(
                    budget_total_usd=1.0,
                    reserve_pct=0.0,
                    single_action_approval_usd=99.0,
                    require_approval_for_new_paid_tool=False,
                    mode=BudgetMode.WARN,
                    cost_log_path=log_path,
                )
                entry_id = tracker.estimate("paid_video", "generate", 2.0)

                tracker.reserve(entry_id)

                entry = tracker.entries[0]
                self.assertEqual(entry["status"], "reserved")
                self.assertEqual(entry["reserved_usd"], 2.0)
                self.assertTrue(entry["budget_warning"])
                self.assertIn("exceeds usable budget", entry["budget_warning_message"])
                persisted = json.loads(log_path.read_text())
                self.assertTrue(persisted["entries"][0]["budget_warning"])

    def test_approved_tools_persist_across_tracker_restarts(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "cost_log.json"
            tracker = CostTracker(cost_log_path=log_path)
            tracker.approve_tool("paid_video")

            restarted = CostTracker(cost_log_path=log_path)

            entry_id = restarted.estimate("paid_video", "generate", 0.01)
            restarted.reserve(entry_id)
            self.assertEqual(restarted.entries[-1]["status"], "reserved")

    def test_completed_entry_cannot_be_refunded(self) -> None:
        tracker = CostTracker(
            mode=BudgetMode.OBSERVE,
            require_approval_for_new_paid_tool=False,
        )
        entry_id = tracker.estimate("paid_video", "generate", 1.0)
        tracker.reserve(entry_id)
        tracker.reconcile(entry_id, actual_usd=0.8)

        with self.assertRaisesRegex(ValueError, "Cannot refund.*completed"):
            tracker.refund(entry_id)

        self.assertEqual(tracker.budget_spent_usd, 0.8)
        self.assertEqual(tracker.entries[0]["status"], "completed")

    def test_entry_lifecycle_rejects_out_of_order_operations(self) -> None:
        tracker = CostTracker(
            mode=BudgetMode.OBSERVE,
            require_approval_for_new_paid_tool=False,
        )
        entry_id = tracker.estimate("paid_video", "generate", 1.0)

        with self.assertRaisesRegex(ValueError, "Cannot reconcile.*estimated"):
            tracker.reconcile(entry_id, actual_usd=0.8)

        tracker.reserve(entry_id)
        with self.assertRaisesRegex(ValueError, "Cannot reserve.*reserved"):
            tracker.reserve(entry_id)


if __name__ == "__main__":
    unittest.main()
