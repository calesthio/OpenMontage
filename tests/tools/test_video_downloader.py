import sys
from types import SimpleNamespace

from tools.analysis.video_downloader import VideoDownloader


def test_cookies_file_reaches_every_yt_dlp_invocation(monkeypatch, tmp_path) -> None:
    options = []

    class FakeYoutubeDL:
        def __init__(self, opts):
            options.append(opts)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def extract_info(self, url, *, download):
            return {}

        def download(self, urls):
            return None

    monkeypatch.setitem(
        sys.modules,
        "yt_dlp",
        SimpleNamespace(YoutubeDL=FakeYoutubeDL),
    )
    tool = VideoDownloader()
    cookies_file = str(tmp_path / "cookies.txt")

    tool._extract_metadata("https://example.com/video", cookies_file)
    tool._download_video("https://example.com/video", tmp_path, "720p", cookies_file)
    tool._download_audio("https://example.com/video", tmp_path, cookies_file)
    tool._download_subtitles("https://example.com/video", tmp_path, cookies_file)

    assert [opts["cookiefile"] for opts in options] == [cookies_file] * 4


def test_cookies_file_changes_idempotency_key() -> None:
    tool = VideoDownloader()
    inputs = {
        "url": "https://example.com/video",
        "format": "video",
        "max_resolution": "720p",
    }
    inputs_with_cookies = {**inputs, "cookies_file": "/cookies.txt"}

    assert tool.idempotency_key(inputs) != tool.idempotency_key(inputs_with_cookies)
    assert tool.idempotency_key(inputs) == tool.idempotency_key(dict(inputs))
    assert tool.idempotency_key(inputs_with_cookies) == tool.idempotency_key(
        dict(inputs_with_cookies)
    )
