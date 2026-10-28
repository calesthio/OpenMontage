"""Offline queue-to-file regressions for the effective fal image format."""

import base64
import io
import json
from pathlib import Path

from PIL import Image
import pytest

from tools.graphics.gemini_fal_image import GeminiFalImage
from tools.schema_media import local_image


@pytest.fixture
def queue(monkeypatch, tmp_path):
    import tools.fal_media as module

    monkeypatch.setenv("FAL_KEY", "offline-test-key")
    monkeypatch.chdir(tmp_path)
    calls = []
    selected_format = "png"

    def request(method, url, **kwargs):
        nonlocal selected_format
        calls.append((method, url, kwargs))
        if method == "POST":
            selected_format = kwargs["json"].get("output_format", "png")
            return {
                "request_id": "owned-job",
                "status_url": "https://queue.fal.run/status",
                "response_url": "https://queue.fal.run/result",
            }
        if url.endswith("status"):
            return {"status": "COMPLETED"}
        buffer = io.BytesIO()
        Image.new("RGB", (2, 2), color="red").save(buffer, format=selected_format)
        data = base64.b64encode(buffer.getvalue()).decode("ascii")
        return {"images": [{"url": f"data:image/{selected_format};base64,{data}"}]}

    monkeypatch.setattr(module, "request_json", request)
    return module, calls


@pytest.mark.parametrize("selected_format", ["jpeg", "webp"])
def test_checkpoint_only_resume_preserves_media_format(queue, tmp_path, monkeypatch, selected_format):
    module, calls = queue
    original_poll = module.poll
    monkeypatch.setattr(module, "poll", lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("pending")))
    checkpoint = tmp_path / "job.json"
    pending = GeminiFalImage().execute({"prompt": "A tree", "output_format": selected_format, "job_path": str(checkpoint)})
    assert not pending.success
    persisted = json.loads(checkpoint.read_text())
    assert persisted == pending.data["resume_job"]
    monkeypatch.setattr(module, "poll", original_poll)
    resumed = GeminiFalImage().execute({"resume_job": persisted})
    assert resumed.success, resumed.error
    output = Path(resumed.data["output"])
    with Image.open(output) as image:
        assert image.format.lower() == selected_format
    assert output.suffix == "." + selected_format
    assert local_image(output).startswith(f"data:image/{selected_format};base64,")
    assert sum(method == "POST" for method, _, _ in calls) == 1


def test_provider_parameters_control_default_filename(queue):
    _, calls = queue
    result = GeminiFalImage().execute({"prompt": "A tree", "provider_params": {"output_format": "jpeg"}})
    assert result.success, result.error
    assert calls[0][2]["json"]["output_format"] == "jpeg"
    assert result.data["output"].endswith(".jpeg")
    assert local_image(result.data["output"]).startswith("data:image/jpeg;base64,")


@pytest.mark.parametrize("filename", ["chosen-file.jpg", "intentional-name.png"])
def test_explicit_output_path_is_preserved(queue, tmp_path, filename):
    result = GeminiFalImage().execute({"prompt": "A tree", "output_format": "jpeg", "output_path": str(tmp_path / filename)})
    assert result.success, result.error
    assert result.data["output"] == str(tmp_path / filename)


def test_default_png_is_preserved(queue):
    result = GeminiFalImage().execute({"prompt": "A tree"})
    assert result.success, result.error
    assert result.data["output"] == "gemini_fal_image.png"
    assert local_image(result.data["output"]).startswith("data:image/png;base64,")


def test_legacy_resume_without_format_keeps_input_fallback(queue):
    result = GeminiFalImage().execute({"prompt": "A tree", "output_format": "jpeg"})
    assert result.success, result.error
    legacy_job = dict(result.data["resume_job"])
    legacy_job.pop("output_format", None)
    resumed = GeminiFalImage().execute({"resume_job": legacy_job, "output_format": "jpeg"})
    assert resumed.success, resumed.error
    assert resumed.data["output"].endswith(".jpeg")
