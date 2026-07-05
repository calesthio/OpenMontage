from pathlib import Path

from schemas.artifacts import validate_artifact
from tools.assets.custom_asset_import import CustomAssetImport
from tools.base_tool import ToolStatus


def test_imports_user_assets_into_project_manifest(tmp_path):
    source_dir = tmp_path / "raw"
    source_dir.mkdir()
    source_video = source_dir / "clip.mp4"
    source_video.write_bytes(b"fake video")
    project_dir = tmp_path / "project"

    result = CustomAssetImport().execute(
        {
            "project_dir": str(project_dir),
            "assets": [
                {
                    "path": str(source_video),
                    "scene_id": "scene-1",
                    "id": "hero-clip",
                }
            ],
        }
    )

    assert result.success, result.error
    manifest = result.data["asset_manifest"]
    validate_artifact("asset_manifest", manifest)
    assert manifest["total_cost_usd"] == 0
    assert len(manifest["assets"]) == 1

    asset = manifest["assets"][0]
    assert asset["id"] == "hero-clip"
    assert asset["type"] == "video"
    assert asset["scene_id"] == "scene-1"
    assert asset["source_tool"] == "custom_asset_import"
    assert asset["provider"] == "user"
    assert asset["subtype"] == "user_provided"
    assert (project_dir / asset["path"]).read_bytes() == b"fake video"


def test_importer_is_available_without_external_dependencies():
    assert CustomAssetImport().get_status() == ToolStatus.AVAILABLE


def test_rejects_unknown_media_type(tmp_path):
    source = tmp_path / "notes.xyz"
    source.write_text("not media", encoding="utf-8")

    result = CustomAssetImport().execute(
        {
            "project_dir": str(tmp_path / "project"),
            "assets": [{"path": str(source), "scene_id": "scene-1"}],
        }
    )

    assert not result.success
    assert "Unsupported asset type" in result.error
