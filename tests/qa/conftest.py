"""tests/qa holds standalone QA scripts plus one pytest module.

test_04..test_08 run their whole workload at import time and report by
printing (see QA_PLAN.md). Collected by pytest, every run of the main suite
executed them during collection (about 17 s) and their failures could never
fail a test. Run them with `python tests/qa/<script>.py`; they exit 1 on a
failed step.
"""

collect_ignore = [
    "test_04_audio_mix.py",
    "test_05_video_compose.py",
    "test_06_video_stitch.py",
    "test_07_playbook_intelligence.py",
    "test_08_end_to_end.py",
]
