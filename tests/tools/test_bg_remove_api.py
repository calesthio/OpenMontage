import sys
from unittest.mock import MagicMock

from PIL import Image


def test_bg_remove_selects_model_through_rembg_session(monkeypatch, tmp_path) -> None:
    fake_rembg = MagicMock()
    fake_rembg.new_session.return_value = "selected-session"
    fake_rembg.remove.side_effect = lambda image, **kwargs: image.convert("RGBA")
    monkeypatch.setitem(sys.modules, "rembg", fake_rembg)

    input_path = tmp_path / "input.png"
    Image.new("RGB", (8, 8), (10, 20, 30)).save(input_path)

    from tools.enhancement.bg_remove import BgRemove

    result = BgRemove().execute({
        "input_path": str(input_path),
        "output_path": str(tmp_path / "output.png"),
        "model": "isnet-general-use",
    })

    assert result.success, result.error
    fake_rembg.new_session.assert_called_once_with("isnet-general-use")
    kwargs = fake_rembg.remove.call_args.kwargs
    assert kwargs["session"] == "selected-session"
    assert "model_name" not in kwargs
