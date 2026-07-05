from pathlib import Path

from tools.analysis.reference_video_package import ReferenceVideoPackage


def test_reference_video_package_accepts_fixed_interval_scene_data(tmp_path):
    project_dir = tmp_path / "reference-smoke"
    keyframe = project_dir / "keyframes" / "scene-1.jpg"
    keyframe.parent.mkdir(parents=True)
    keyframe.write_bytes(b"fake-jpeg")

    result = ReferenceVideoPackage().execute(
        {
            "project_dir": str(project_dir),
            "reference_source": {
                "input_type": "local_file",
                "input": str(project_dir / "source.mp4"),
                "local_video_path": str(project_dir / "source.mp4"),
                "duration_seconds": 5.0,
                "width": 720,
                "height": 1280,
                "fps": 30,
                "ingest_method": "custom_asset_import",
            },
            "reference_analysis": {
                "method": "fixed_interval_fallback",
                "scenes": [
                    {
                        "scene_id": "s1",
                        "start": 0.0,
                        "end": 5.0,
                        "visual_summary": "单镜头竖屏口播",
                        "camera_motion": "固定机位",
                        "keyframes": [str(keyframe)],
                    }
                ],
            },
            "reference_transcript": {
                "status": "ok",
                "raw_text": "这是一个本地视频解析冒烟测试。",
                "segments": [
                    {
                        "start": 0.0,
                        "end": 5.0,
                        "text": "这是一个本地视频解析冒烟测试。",
                    }
                ],
            },
        }
    )

    assert result.success
    package = result.data["replication_package"]
    assert package["source"]["ingest_method"] == "custom_asset_import"
    assert package["scenes"][0]["pacing"] == "unknown"
    assert package["scenes"][0]["keyframes"] == [str(keyframe)]
    assert Path(result.data["markdown_path"]).is_file()
