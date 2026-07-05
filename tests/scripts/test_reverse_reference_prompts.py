from __future__ import annotations

import json
from pathlib import Path

from scripts import reverse_reference_prompts


def _package(frame_path: str) -> dict:
    return {
        "version": "1.0",
        "source": {"input_type": "local_file", "input": "reference.mp4"},
        "editable_inputs": {"status": "needs_human_edit", "custom_assets": []},
        "scenes": [
            {
                "scene_id": "s1",
                "start": 0.0,
                "end": 8.0,
                "speech": "原文案。",
                "keyframes": [frame_path],
                "production_inputs": {
                    "status": "needs_human_edit",
                    "script_text": "原文案。",
                    "seedance_prompt": "旧提示词。",
                    "selected_assets": [],
                },
            }
        ],
        "approval": {"status": "pending_human_review", "required_before_production": True},
    }


def test_main_writes_reversed_prompt_package(monkeypatch, tmp_path, capsys):
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"fake jpg")
    package_path = tmp_path / "replication-package.json"
    package_path.write_text(json.dumps(_package(str(frame)), ensure_ascii=False), encoding="utf-8")

    class FakePromptReverse:
        def execute(self, inputs):
            from tools.base_tool import ToolResult

            package = json.loads(package_path.read_text(encoding="utf-8"))
            package["scenes"][0]["production_inputs"]["seedance_prompt"] = "豆包反推提示词。"
            out = tmp_path / "project" / "artifacts" / "reference-prompts" / "reference-prompts-reversed-package.json"
            out.parent.mkdir(parents=True)
            out.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")
            return ToolResult(success=True, data={"replication_package": package, "json_path": str(out)})

    monkeypatch.setattr(reverse_reference_prompts, "ReferencePromptReverse", FakePromptReverse)

    exit_code = reverse_reference_prompts.main(
        [
            str(package_path),
            "--project-dir",
            str(tmp_path / "project"),
            "--provider",
            "doubao",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert Path(payload["replication_package_path"]).is_file()
    assert payload["replication_package"]["scenes"][0]["production_inputs"]["seedance_prompt"] == "豆包反推提示词。"
