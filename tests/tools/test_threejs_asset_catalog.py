import json
import zipfile
from pathlib import Path

from tools.graphics.threejs_asset_catalog import CATALOGS, ThreeJSAssetCatalog


def test_catalog_list_is_rights_explicit():
    result = ThreeJSAssetCatalog().execute({"operation": "list"})
    assert result.success
    assert result.data["catalogs"]
    assert all(item["license"] == "CC0-1.0" for item in result.data["catalogs"].values())


def test_catalog_install_inventories_gltf(tmp_path, monkeypatch):
    source_zip = tmp_path / "fixture.zip"
    with zipfile.ZipFile(source_zip, "w") as package:
        package.writestr("Models/GLTF format/Tree.gltf", json.dumps({"asset": {"version": "2.0"}}))
        package.writestr("Models/GLTF format/Tree.bin", b"mesh")
        package.writestr("Textures/tree.png", b"texture")

    fixture_id = "fixture-catalog"
    monkeypatch.setitem(CATALOGS, fixture_id, {
        "title": "Fixture",
        "source_url": "https://example.test/source",
        "download_url": "https://example.test/catalog.zip",
        "license": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "tags": ["fixture"],
    })

    def fake_download(_url: str, destination: Path) -> None:
        destination.write_bytes(source_zip.read_bytes())

    monkeypatch.setattr("tools.graphics.threejs_asset_catalog._download", fake_download)
    output = tmp_path / "installed"
    result = ThreeJSAssetCatalog().execute({
        "operation": "install",
        "catalog_id": fixture_id,
        "output_path": str(output),
    })
    assert result.success, result.error
    assert result.data["model_count"] == 1
    assert result.data["texture_count"] == 1
    assert (output / "catalog-manifest.json").exists()
