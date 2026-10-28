"""Contract tests for Pixabay music candidate search and selected download."""

from __future__ import annotations

from tools.audio.pixabay_music import PixabayMusic


def _tracks():
    return [
        {
            "title": "Quiet Product Reveal",
            "artist": "Artist One",
            "audio_url": "https://cdn.pixabay.com/audio/one.mp3",
            "duration": 34,
            "pixabay_id": 1,
        },
        {
            "title": "Soft Luxury Motion",
            "artist": "Artist Two",
            "audio_url": "https://cdn.pixabay.com/audio/two.mp3",
            "duration": 45,
            "pixabay_id": 2,
        },
        {
            "title": "Elegant Brand Bed",
            "artist": "Artist Three",
            "audio_url": "https://cdn.pixabay.com/audio/three.mp3",
            "duration": 52,
            "pixabay_id": 3,
        },
        {
            "title": "Fourth Result",
            "artist": "Artist Four",
            "audio_url": "https://cdn.pixabay.com/audio/four.mp3",
            "duration": 60,
            "pixabay_id": 4,
        },
    ]


def test_search_returns_three_ordered_candidates_without_writing(monkeypatch, tmp_path):
    tool = PixabayMusic()
    monkeypatch.setattr(tool, "_search", lambda inputs: _tracks())
    output = tmp_path / "must-not-exist.mp3"

    result = tool.execute(
        {
            "query": "elegant product commercial",
            "operation": "search",
            "max_results": 3,
            "output_path": str(output),
        }
    )

    assert result.success is True
    assert result.artifacts == []
    assert not output.exists()
    assert [candidate["index"] for candidate in result.data["candidates"]] == [1, 2, 3]
    assert [candidate["title"] for candidate in result.data["candidates"]] == [
        "Quiet Product Reveal",
        "Soft Luxury Motion",
        "Elegant Brand Bed",
    ]
    assert all(
        candidate["license"] == "Pixabay Content License"
        for candidate in result.data["candidates"]
    )
    assert all(
        candidate["duration_seconds"] > 0
        for candidate in result.data["candidates"]
    )
    assert all(
        candidate["download_url"].startswith("https://cdn.pixabay.com/")
        for candidate in result.data["candidates"]
    )


def test_download_writes_exactly_the_selected_candidate(monkeypatch, tmp_path):
    tool = PixabayMusic()
    output = tmp_path / "selected.mp3"

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"selected-audio-bytes"

    monkeypatch.setattr(
        "tools.audio.pixabay_music.urllib.request.urlopen",
        lambda *args, **kwargs: Response(),
    )

    result = tool.execute(
        {
            "query": "elegant product commercial",
            "operation": "download",
            "download_url": "https://cdn.pixabay.com/audio/two.mp3",
            "candidate_index": 2,
            "title": "Soft Luxury Motion",
            "artist": "Artist Two",
            "output_path": str(output),
        }
    )

    assert result.success is True
    assert output.read_bytes() == b"selected-audio-bytes"
    assert result.data["track_title"] == "Soft Luxury Motion"
    assert result.data["selected_index"] == 2
    assert result.artifacts == [str(output)]


def test_non_pixabay_download_url_is_rejected_before_network(monkeypatch, tmp_path):
    tool = PixabayMusic()

    def fail_network(*args, **kwargs):
        raise AssertionError("non-Pixabay URL must not call network")

    monkeypatch.setattr(
        "tools.audio.pixabay_music.urllib.request.urlopen",
        fail_network,
    )
    result = tool.execute(
        {
            "query": "elegant product commercial",
            "operation": "download",
            "download_url": "https://example.com/evil.mp3",
            "title": "Unsafe",
            "output_path": str(tmp_path / "unsafe.mp3"),
        }
    )

    assert result.success is False
    assert "Pixabay" in result.error
    assert not (tmp_path / "unsafe.mp3").exists()


def test_legacy_search_and_download_uses_first_result(monkeypatch, tmp_path):
    tool = PixabayMusic()
    captured = {}
    output = tmp_path / "legacy.mp3"
    monkeypatch.setattr(tool, "_search", lambda inputs: _tracks())

    def fake_download(track, inputs):
        captured["track"] = track
        output.write_bytes(b"legacy")
        return output

    monkeypatch.setattr(tool, "_download", fake_download)
    result = tool.execute(
        {
            "query": "elegant product commercial",
            "output_path": str(output),
        }
    )

    assert result.success is True
    assert captured["track"]["title"] == "Quiet Product Reveal"
    assert result.data["output"] == str(output)


def test_download_cache_key_depends_on_selected_url():
    tool = PixabayMusic()
    common = {
        "query": "elegant product commercial",
        "operation": "download",
        "output_path": "/tmp/selected.mp3",
    }

    first = tool.cache_key(
        {**common, "download_url": "https://cdn.pixabay.com/audio/one.mp3"}
    )
    second = tool.cache_key(
        {**common, "download_url": "https://cdn.pixabay.com/audio/two.mp3"}
    )

    assert first != second
