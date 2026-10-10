"""Regression test for the approval_policy decision category.

skills/meta/checkpoint-protocol.md and AGENT_GUIDE.md require an explicit
full-run pre-authorization to be recorded as a decision_log entry with
`category: "approval_policy"`. The schema's category enum did not include it,
so following the documented protocol produced an invalid artifact and the
checkpoint writer rejected it.
"""

import sys
from pathlib import Path

import jsonschema
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.checkpoint import init_project, write_checkpoint  # noqa: E402
from schemas.artifacts import validate_artifact  # noqa: E402


def _decision_log(category: str) -> dict:
    return {
        "version": "1.0",
        "project_id": "approval-policy-test",
        "decisions": [
            {
                "decision_id": "d-001",
                "stage": "proposal",
                "category": category,
                "subject": "Full-run pre-authorization",
                "options_considered": [
                    {"option_id": "gate_each", "label": "Stop at every gate", "score": 0.3, "reason": "default protocol"},
                    {"option_id": "preauth", "label": "Run straight through", "score": 0.9, "reason": "user pre-authorized the full run"},
                ],
                "selected": "preauth",
                "reason": "User explicitly pre-authorized the full run in chat",
                "user_visible": True,
                "user_approved": True,
            }
        ],
    }


def test_approval_policy_category_is_schema_valid():
    validate_artifact("decision_log", _decision_log("approval_policy"))


def test_unknown_category_still_rejected():
    with pytest.raises(jsonschema.ValidationError):
        validate_artifact("decision_log", _decision_log("not_a_real_category"))


def test_checkpoint_accepts_approval_policy_decision_log(tmp_path):
    init_project("approval-policy-test", title="Approval policy", pipeline_type="framework-smoke", pipeline_dir=tmp_path)
    log = _decision_log("approval_policy")
    write_checkpoint(tmp_path, "approval-policy-test", "research", "in_progress", {"decision_log": log},
                     pipeline_type="framework-smoke")
    merged = (tmp_path / "approval-policy-test" / "decision_log.json")
    assert merged.exists()
    assert '"approval_policy"' in merged.read_text(encoding="utf-8")
