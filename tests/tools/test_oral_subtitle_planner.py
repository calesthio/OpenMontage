from __future__ import annotations

from tools.subtitle.oral_subtitle_planner import OralSubtitlePlanner


SCRIPT = (
    "在这些案子上面，我积累了充足的实战经验。"
    "如果你身边刚好缺一位靠谱的律师朋友，今天刷到这条视频，"
    "不妨给徐律师点个赞、留个关注。"
    "徐律师就是你的私人法律顾问。"
    "往后再遇上工程扯皮、刑事案件相关麻烦，"
    "我会尽全力帮你维护你的合法权益。"
)


def test_plans_oral_chinese_subtitles_as_short_readable_cues():
    result = OralSubtitlePlanner().execute(
        {
            "text": SCRIPT,
            "start": 0,
            "end": 15,
            "max_chars_per_line": 12,
            "max_lines_per_cue": 2,
            "min_duration": 0.8,
            "max_duration": 2.2,
        }
    )

    assert result.success
    assert result.data["provider"] == "openmontage"
    assert result.data["requires_api_call"] is False
    assert result.data["cue_count"] >= 10

    cues = result.data["cues"]
    assert cues[0]["start"] == 0
    assert cues[-1]["end"] == 15
    assert all(0.75 <= cue["end"] - cue["start"] <= 2.25 for cue in cues)

    display_lines = [
        line
        for cue in cues
        for line in cue["text"].splitlines()
        if line.strip()
    ]
    assert all(len(cue["text"].splitlines()) <= 2 for cue in cues)
    assert all(len(line) <= 12 for line in display_lines)
    assert not any("\n法\n" in cue["text"] for cue in cues)
    assert not any("法\n律" in cue["text"] for cue in cues)
    assert not any("合\n法权益" in cue["text"] for cue in cues)
    assert any(cue["text"] == "私人法律顾问。" for cue in cues)


def test_rejects_empty_subtitle_text():
    result = OralSubtitlePlanner().execute({"text": "   ", "start": 0, "end": 3})

    assert not result.success
    assert "text is required" in result.error
