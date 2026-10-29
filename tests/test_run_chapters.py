#!/usr/bin/env python3
"""TDD tests for chapter mode (Milestone Z4).

Fake stages drive the orchestration — no media, network, or Kokoro required.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_episode  # noqa: E402

MAX_CHAPTER_DURATION = 360  # 6 min


def _chapter_script(tmp_path, sentences, chapter_idx):
    """Write a script md with the given sentences for a chapter."""
    lines = [
        "| Beat | Sentence | claim_ids | flags |",
        "|---|---|---|---|",
    ]
    for i, s in enumerate(sentences, 1):
        lines.append(f"| B1-{i} | {s} | CH-{chapter_idx}-{i} | |")
    path = tmp_path / f"chapter_{chapter_idx}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_split_script_into_chapters_respects_max_duration(tmp_path, monkeypatch):
    """Chapters are split so narration duration never exceeds max_chapter_duration_s."""
    # 20 sentences x 20 s = 400 s; max 60 s/chapter -> 7 chapters (3+3+3+3+3+3+2)
    script = _chapter_script(tmp_path, [f"sentence {i}." for i in range(1, 21)], 0)
    monkeypatch.setattr(run_episode, "_estimate_sentence_duration", lambda s: 20.0)

    chapters = run_episode.split_script_into_chapters(script, max_duration_s=60)
    assert len(chapters) == 7, chapters  # 20*20s = 400s, 60s/chapter -> 7 chapters
    for ch in chapters:
        assert ch["duration_s"] <= 60.0, ch


def test_split_script_into_chapters_single_chapter_when_short(tmp_path):
    """A short script (<= max duration) is a single chapter."""
    script = _chapter_script(tmp_path, ["short sentence one.", "short sentence two."], 0)
    chapters = run_episode.split_script_into_chapters(script, MAX_CHAPTER_DURATION)
    assert len(chapters) == 1
    assert chapters[0]["chapter_index"] == 0
    assert len(chapters[0]["sentences"]) == 2


def test_per_chapter_checkpoint_and_resume(tmp_path, monkeypatch):
    """Each chapter gets its own checkpoint; completed chapters are skipped on resume."""
    chapters = [
        {"chapter_index": 0, "sentences": ["s1.", "s2."], "duration_s": 30.0},
        {"chapter_index": 1, "sentences": ["s3.", "s4."], "duration_s": 30.0},
    ]
    monkeypatch.setattr(run_episode, "split_script_into_chapters", lambda *a, **k: chapters)

    chapter_runs = []
    def fake_run_pipeline(topic_id, state_path=None, state_root=None, stages=None, initial_state=None):
        chapter_runs.append(initial_state["chapter_index"])
        return {"verdict": "OK", "state": {"stages": {"render": {"status": "OK", "outputs": {"video": f"/tmp/chap{initial_state['chapter_index']}.mp4"}}}}}

    monkeypatch.setattr(run_episode, "run_pipeline", fake_run_pipeline)
    concat_calls = []
    monkeypatch.setattr(run_episode, "concatenate_chapters",
                        lambda vids, out, crossfade_duration_s=1.0: concat_calls.append((vids, out, crossfade_duration_s)) or {"status": "OK"})
    loudness_calls = []
    monkeypatch.setattr(run_episode, "final_loudness_pass",
                        lambda vid: loudness_calls.append(vid) or {"status": "OK", "outputs": {"video": str(vid) + "_loud.mp4"}})

    # First run: both chapters execute
    state_path = tmp_path / "chapter_state.json"
    res = run_episode.run_chapter_mode("artemis", script_path=None, chapters=chapters,
                                       state_path=state_path)
    assert res["verdict"] == "OK", res
    assert chapter_runs == [0, 1], chapter_runs
    assert concat_calls, "concatenate_chapters should be called"
    assert loudness_calls, "final_loudness_pass should be called"

    # Second run (resume): chapters skipped, nothing re-executed
    chapter_runs.clear()
    concat_calls.clear()
    loudness_calls.clear()
    res2 = run_episode.run_chapter_mode("artemis", script_path=None, chapters=chapters,
                                        state_path=state_path)
    assert res2["verdict"] == "OK", res2
    assert chapter_runs == [], chapter_runs  # skipped on resume
    assert not concat_calls, "concat should not re-run on full resume"
    assert not loudness_calls, "loudness should not re-run on full resume"


def test_chapter_failure_blocks_remaining_chapters(tmp_path, monkeypatch):
    """A failed chapter stops the chain; later chapters don't run."""
    chapters = [
        {"chapter_index": 0, "sentences": ["s1."], "duration_s": 30.0},
        {"chapter_index": 1, "sentences": ["s2."], "duration_s": 30.0},
        {"chapter_index": 2, "sentences": ["s3."], "duration_s": 30.0},
    ]
    monkeypatch.setattr(run_episode, "split_script_into_chapters", lambda *a, **k: chapters)

    chapter_runs = []
    def fake_run_pipeline(topic_id, state_path=None, state_root=None, stages=None, initial_state=None):
        ci = initial_state["chapter_index"]
        chapter_runs.append(ci)
        if ci == 1:
            return {"verdict": "BLOCKED", "stage": "edl", "state": {}}
        return {"verdict": "OK", "state": {"stages": {"render": {"status": "OK", "outputs": {"video": f"/tmp/chap{ci}.mp4"}}}}}

    monkeypatch.setattr(run_episode, "run_pipeline", fake_run_pipeline)
    concat_calls = []
    monkeypatch.setattr(run_episode, "concatenate_chapters",
                        lambda vids, out, crossfade_duration_s=1.0: concat_calls.append(1) or {"status": "OK"})

    state_path = tmp_path / "chapter_state.json"
    res = run_episode.run_chapter_mode("artemis", script_path=None, chapters=chapters,
                                       state_path=state_path)
    assert res["verdict"] == "BLOCKED", res
    assert res["chapter"] == 1, res
    assert chapter_runs == [0, 1], chapter_runs  # chapter 2 never ran
    assert not concat_calls, "concat should not run after a chapter failure"


def test_disk_budget_check_before_each_chapter(tmp_path, monkeypatch):
    """Disk budget checked before each chapter; below threshold blocks."""
    chapters = [
        {"chapter_index": 0, "sentences": ["s1."], "duration_s": 30.0},
        {"chapter_index": 1, "sentences": ["s2."], "duration_s": 30.0},
    ]
    monkeypatch.setattr(run_episode, "split_script_into_chapters", lambda *a, **k: chapters)

    run_episode.MIN_FREE_BYTES = 800 * 1024 * 1024
    monkeypatch.setattr(run_episode, "disk_free_bytes", lambda path: 100)

    chapter_runs = []
    def fake_run_pipeline(topic_id, state_path=None, state_root=None, stages=None, initial_state=None):
        chapter_runs.append(initial_state["chapter_index"])
        return {"verdict": "OK", "state": {}}

    monkeypatch.setattr(run_episode, "run_pipeline", fake_run_pipeline)

    state_path = tmp_path / "chapter_state.json"
    res = run_episode.run_chapter_mode("artemis", script_path=None, chapters=chapters,
                                       state_path=state_path)
    assert res["verdict"] == "BLOCKED", res
    assert res["stage"] == "disk", res
    assert chapter_runs == [], chapter_runs  # no chapter ran
