from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from lib.config_model import BudgetMode
from tools.cost_tracker import BudgetExceededError, CostTracker


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

    def test_cap_mode_blocks_where_warn_only_flags(self) -> None:
        """The counterpart to the warn test above.

        Warn recording a flag and proceeding is what the default config did --
        it is the absence of enforcement, not enforcement. Cap must refuse.
        """
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = CostTracker(
                budget_total_usd=1.0,
                reserve_pct=0.0,
                single_action_approval_usd=None,
                require_approval_for_new_paid_tool=False,
                mode=BudgetMode.CAP,
                cost_log_path=Path(temp_dir) / "cost_log.json",
            )
            entry_id = tracker.estimate("paid_video", "generate", 2.0)

            with self.assertRaises(BudgetExceededError):
                tracker.reserve(entry_id)

            # Rejected reservations consume nothing.
            self.assertEqual(tracker.entries[0]["status"], "estimated")
            self.assertEqual(tracker.budget_reserved_usd, 0.0)

    def test_daily_bucket_resets_but_history_is_preserved(self) -> None:
        import tempfile
        from datetime import datetime, timezone
        from pathlib import Path

        moment = {"now": datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)}

        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = CostTracker(
                budget_total_usd=1.0,
                reserve_pct=0.0,
                single_action_approval_usd=None,
                require_approval_for_new_paid_tool=False,
                mode=BudgetMode.CAP,
                cost_log_path=Path(temp_dir) / "cost_log.json",
                clock=lambda: moment["now"],
            )
            eid = tracker.estimate("paid_video", "generate", 1.0)
            tracker.reserve(eid)
            tracker.reconcile(eid, 1.0, success=True)
            self.assertEqual(tracker.remaining_on("2026-07-16"), 0.0)

            moment["now"] = datetime(2026, 7, 17, 0, 1, tzinfo=timezone.utc)

            # New day: fresh budget, and yesterday's record still on the books.
            self.assertEqual(tracker.remaining_on("2026-07-17"), 1.0)
            self.assertEqual(tracker.spent_on("2026-07-16"), 1.0)
            tracker.reserve(tracker.estimate("paid_video", "generate", 1.0))
            self.assertEqual(tracker.entries[-1]["budget_date"], "2026-07-17")


if __name__ == "__main__":
    unittest.main()
