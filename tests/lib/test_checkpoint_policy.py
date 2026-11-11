"""`checkpoint.policy` in config.yaml must do something.

The value was parsed (`lib/config_model.py`) and read by nothing, as was the
manifest's `default_checkpoint_policy`; `write_checkpoint` stamped "guided" on
every checkpoint whatever either said. Now the strictest of the caller's
argument, config.yaml and the manifest applies, and `manual_all` gates every
stage.
"""

import json

import pytest

from lib import checkpoint
from lib.checkpoint import (
    CheckpointValidationError,
    init_project,
    resolve_checkpoint_policy,
    write_checkpoint,
)
from tests.contracts.test_phase0_contracts import sample_artifact

# cinematic: research (not gated) > proposal* > script* ...


@pytest.fixture
def config_policy(tmp_path, monkeypatch):
    """Point the checkpoint module at a temp config.yaml with a chosen policy."""

    def set_policy(policy):
        path = tmp_path / "config.yaml"
        path.write_text(f"checkpoint:\n  policy: {policy}\n", encoding="utf-8")
        monkeypatch.setattr(checkpoint, "_CONFIG_PATH", path)
        checkpoint._config_policy_cached.cache_clear()
        return path

    yield set_policy
    checkpoint._config_policy_cached.cache_clear()


def test_default_is_guided():
    assert resolve_checkpoint_policy("cinematic") == "guided"
    assert resolve_checkpoint_policy(None) == "guided"


def test_the_strictest_source_wins(config_policy):
    config_policy("manual_all")
    assert resolve_checkpoint_policy("cinematic") == "manual_all"
    # A caller cannot relax what the user configured.
    assert resolve_checkpoint_policy("cinematic", "guided") == "manual_all"
    assert resolve_checkpoint_policy("cinematic", "auto_noncreative") == "manual_all"

    config_policy("guided")
    assert resolve_checkpoint_policy("cinematic", "manual_all") == "manual_all"
    # auto_noncreative cannot loosen the manifest's "guided".
    assert resolve_checkpoint_policy("cinematic", "auto_noncreative") == "guided"


def test_manual_all_gates_a_stage_the_manifest_leaves_open(tmp_path, config_policy):
    config_policy("manual_all")
    init_project("film", title="Film", pipeline_type="cinematic", pipeline_dir=tmp_path)
    brief = sample_artifact("research_brief")

    with pytest.raises(CheckpointValidationError, match="manual_all") as exc:
        write_checkpoint(tmp_path, "film", "research", "completed", {"research_brief": brief})
    assert "GATE VIOLATION" in str(exc.value)

    write_checkpoint(tmp_path, "film", "research", "awaiting_human", {"research_brief": brief})
    path = write_checkpoint(tmp_path, "film", "research", "completed",
                            {"research_brief": brief}, human_approved=True)
    saved = json.loads(path.read_text())
    assert saved["checkpoint_policy"] == "manual_all"
    assert saved["human_approval_required"] is True


def test_guided_leaves_an_ungated_stage_alone(tmp_path, config_policy):
    config_policy("guided")
    init_project("film", title="Film", pipeline_type="cinematic", pipeline_dir=tmp_path)
    path = write_checkpoint(tmp_path, "film", "research", "completed",
                            {"research_brief": sample_artifact("research_brief")})
    saved = json.loads(path.read_text())
    assert saved["checkpoint_policy"] == "guided"
    assert saved["human_approval_required"] is False


def test_a_config_change_is_picked_up_without_restarting(tmp_path, config_policy):
    path = config_policy("guided")
    assert resolve_checkpoint_policy("cinematic") == "guided"
    import os

    path.write_text("checkpoint:\n  policy: manual_all\n", encoding="utf-8")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000))
    assert resolve_checkpoint_policy("cinematic") == "manual_all"


def test_unreadable_config_falls_back_to_the_manifest(tmp_path, config_policy, caplog):
    path = config_policy("guided")
    path.write_text("checkpoint:\n  policy: not-a-policy\n", encoding="utf-8")
    checkpoint._config_policy_cached.cache_clear()
    assert resolve_checkpoint_policy("cinematic") == "guided"
    assert "checkpoint.policy" in caplog.text


def test_shipped_config_has_no_dead_keys():
    """config.yaml only carries settings something reads."""
    import yaml

    raw = yaml.safe_load((checkpoint._CONFIG_PATH).read_text(encoding="utf-8"))
    assert "paths" not in raw, "paths.* pointed at directories nothing uses (real root: projects/)"
    assert set(raw["checkpoint"]) == {"policy"}
