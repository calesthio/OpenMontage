from __future__ import annotations

import zipfile

import pytest

from tools.graphics.skp_to_glb import ConversionError, _extract_skp_from_zip


def test_extracts_only_skp_from_archive_with_sketchup_backup(tmp_path):
    archive_path = tmp_path / "model.zip"
    output_path = tmp_path / "safe" / "input.skp"
    output_path.parent.mkdir()

    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("warehouse.skb", b"backup")
        archive.writestr("warehouse.skp", b"model")

    assert _extract_skp_from_zip(archive_path, output_path) == output_path
    assert output_path.read_bytes() == b"model"


def test_extracts_archive_member_to_fixed_destination_without_path_traversal(tmp_path):
    archive_path = tmp_path / "model.zip"
    output_path = tmp_path / "safe" / "input.skp"
    output_path.parent.mkdir()

    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../outside.skp", b"model")

    _extract_skp_from_zip(archive_path, output_path)

    assert output_path.read_bytes() == b"model"
    assert not (tmp_path / "outside.skp").exists()


@pytest.mark.parametrize(
    ("members", "message"),
    [
        ([], "found 0"),
        ([("one.skp", b"1"), ("two.skp", b"2")], "found 2"),
    ],
)
def test_rejects_archives_without_exactly_one_skp(tmp_path, members, message):
    archive_path = tmp_path / "model.zip"
    output_path = tmp_path / "input.skp"

    with zipfile.ZipFile(archive_path, "w") as archive:
        for name, content in members:
            archive.writestr(name, content)

    with pytest.raises(ConversionError, match=message):
        _extract_skp_from_zip(archive_path, output_path)
