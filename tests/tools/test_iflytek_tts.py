"""Unit tests for the iFlytek TTS provider (tools/audio/iflytek_tts.py).

The real API is never called -- requests.post/requests.get are patched. Covers
credential gating, the explicit-voice contract, the DTS signature (the part most
likely to be wrong, since iFlytek signs into query parameters rather than
headers), the create-request shape, base64 URL decoding, polling terminal
states, selector routing, cost, idempotency keys, and credential redaction.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

from tools.audio.iflytek_tts import IFlytekTTS
from tools.base_tool import ToolStatus
from tools.provider_pricing import PriceQuoteRequired


AUDIO_URL = "https://cdn.xfyun.cn/dts/task-1.mp3"


class _FakeResponse:
    def __init__(self, payload: dict | None = None, *, status_code: int = 200,
                 content: bytes = b"", text_body: str | None = None):
        self._payload = payload
        self.status_code = status_code
        self.content = content
        self._text_body = text_body

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _create_ok(task_id: str = "task-1") -> _FakeResponse:
    return _FakeResponse(
        {"header": {"code": 0, "message": "success", "sid": "sid-1", "task_id": task_id}}
    )


def _query(task_status: int, *, with_audio: bool = True, task_id: str = "task-1") -> _FakeResponse:
    payload: dict = {}
    if with_audio:
        payload = {
            "audio": {
                "encoding": "lame",
                "sample_rate": 24000,
                "audio": base64.b64encode(AUDIO_URL.encode()).decode(),
            }
        }
    return _FakeResponse(
        {
            "header": {"code": 0, "message": "success", "sid": "sid-1",
                       "task_id": task_id, "task_status": task_status},
            "payload": payload,
        }
    )


@pytest.fixture
def credentials(monkeypatch):
    monkeypatch.setenv("IFLYTEK_APP_ID", "appid123")
    monkeypatch.setenv("IFLYTEK_API_KEY", "key-abc")
    monkeypatch.setenv("IFLYTEK_API_SECRET", "secret-xyz")
    monkeypatch.delenv("IFLYTEK_TTS_VCN", raising=False)


@pytest.fixture
def no_credentials(monkeypatch):
    for name in ("IFLYTEK_APP_ID", "IFLYTEK_API_KEY", "IFLYTEK_API_SECRET", "IFLYTEK_TTS_VCN"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def no_sleep():
    """Polling is exercised for real; only the waiting is skipped."""
    with patch("time.sleep"):
        yield


def _run(inputs, tmp_path, *, query_responses=None, download=b"MP3BYTES"):
    """Execute the tool against a scripted create/query/download sequence."""
    query_responses = query_responses or [_query(5)]
    inputs = {"output_path": str(tmp_path / "narration.mp3"), **inputs}
    with patch("requests.post", side_effect=[_create_ok(), *query_responses]) as post, \
         patch("requests.get", return_value=_FakeResponse(content=download)) as get:
        result = IFlytekTTS().execute(inputs)
    return result, post, get


# ----------------------------------------------------------------------
# Credential gating
# ----------------------------------------------------------------------


class TestStatus:
    def test_unavailable_without_credentials(self, no_credentials):
        assert IFlytekTTS().get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_all_three(self, credentials):
        assert IFlytekTTS().get_status() == ToolStatus.AVAILABLE

    def test_unavailable_when_only_partially_configured(self, no_credentials, monkeypatch):
        monkeypatch.setenv("IFLYTEK_APP_ID", "appid123")
        monkeypatch.setenv("IFLYTEK_API_KEY", "key-abc")
        assert IFlytekTTS().get_status() == ToolStatus.UNAVAILABLE

    def test_execute_names_every_missing_variable(self, no_credentials, monkeypatch):
        monkeypatch.setenv("IFLYTEK_APP_ID", "appid123")
        result = IFlytekTTS().execute({"text": "hello", "voice_id": "x4_mingge"})
        assert result.success is False
        assert "IFLYTEK_API_KEY" in result.error
        assert "IFLYTEK_API_SECRET" in result.error
        assert "IFLYTEK_APP_ID" not in result.error.split(".")[0]


# ----------------------------------------------------------------------
# Explicit-voice contract
# ----------------------------------------------------------------------


class TestVoiceContract:
    def test_missing_voice_errors(self, credentials):
        result = IFlytekTTS().execute({"text": "hello"})
        assert result.success is False
        assert "IFLYTEK_TTS_VCN" in result.error

    def test_env_default_voice_is_used(self, credentials, monkeypatch, tmp_path):
        monkeypatch.setenv("IFLYTEK_TTS_VCN", "x4_qianxue")
        result, post, _ = _run({"text": "你好"}, tmp_path)
        assert result.success is True
        assert result.data["vcn"] == "x4_qianxue"
        _, kwargs = post.call_args_list[0]
        assert kwargs["json"]["parameter"]["dts"]["vcn"] == "x4_qianxue"

    def test_explicit_voice_beats_env_default(self, credentials, monkeypatch, tmp_path):
        monkeypatch.setenv("IFLYTEK_TTS_VCN", "x4_qianxue")
        result, _, _ = _run({"text": "你好", "voice_id": "x4_mingge"}, tmp_path)
        assert result.data["vcn"] == "x4_mingge"


# ----------------------------------------------------------------------
# Signature -- iFlytek signs into query parameters, not headers
# ----------------------------------------------------------------------


class TestSignature:
    def test_signed_url_carries_host_date_and_authorization(self, credentials, tmp_path):
        _, post, _ = _run({"text": "hi", "voice_id": "x4_mingge"}, tmp_path)
        url = post.call_args_list[0][0][0]
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert parsed.netloc == IFlytekTTS.HOST
        assert parsed.path == IFlytekTTS.CREATE_PATH
        assert params["host"] == [IFlytekTTS.HOST]
        assert set(params) == {"host", "date", "authorization"}

    def test_date_is_rfc1123_gmt(self, credentials, tmp_path):
        _, post, _ = _run({"text": "hi", "voice_id": "x4_mingge"}, tmp_path)
        date = parse_qs(urlparse(post.call_args_list[0][0][0]).query)["date"][0]
        # The DTS server rejects a non-GMT date outright.
        assert date.endswith("GMT")

    def test_signature_matches_hmac_sha256_of_the_request_line(self, credentials, tmp_path):
        _, post, _ = _run({"text": "hi", "voice_id": "x4_mingge"}, tmp_path)
        params = parse_qs(urlparse(post.call_args_list[0][0][0]).query)
        authorization = base64.b64decode(params["authorization"][0]).decode()

        assert 'api_key="key-abc"' in authorization
        assert 'algorithm="hmac-sha256"' in authorization
        assert 'headers="host date request-line"' in authorization

        signature = authorization.split('signature="')[1].rstrip('"')
        expected_origin = (
            f"host: {IFlytekTTS.HOST}\n"
            f"date: {params['date'][0]}\n"
            f"POST {IFlytekTTS.CREATE_PATH} HTTP/1.1"
        )
        expected = base64.b64encode(
            hmac.new(b"secret-xyz", expected_origin.encode(), hashlib.sha256).digest()
        ).decode()
        assert signature == expected

    def test_query_call_signs_the_query_path(self, credentials, tmp_path):
        _, post, _ = _run({"text": "hi", "voice_id": "x4_mingge"}, tmp_path)
        assert urlparse(post.call_args_list[1][0][0]).path == IFlytekTTS.QUERY_PATH

    def test_credentials_never_travel_in_the_body(self, credentials, tmp_path):
        _, post, _ = _run({"text": "hi", "voice_id": "x4_mingge"}, tmp_path)
        body = json.dumps(post.call_args_list[0][1]["json"])
        assert "secret-xyz" not in body
        assert "key-abc" not in body


# ----------------------------------------------------------------------
# Create-request shape
# ----------------------------------------------------------------------


class TestCreateBody:
    def test_text_is_base64_utf8(self, credentials, tmp_path):
        _, post, _ = _run({"text": "你好，世界", "voice_id": "x4_mingge"}, tmp_path)
        payload = post.call_args_list[0][1]["json"]["payload"]["text"]
        assert base64.b64decode(payload["text"]).decode("utf-8") == "你好，世界"
        assert payload["encoding"] == "utf8"
        assert payload["compress"] == "raw"

    def test_app_id_travels_in_the_header_block(self, credentials, tmp_path):
        _, post, _ = _run({"text": "hi", "voice_id": "x4_mingge"}, tmp_path)
        assert post.call_args_list[0][1]["json"]["header"]["app_id"] == "appid123"

    def test_prosody_and_audio_defaults(self, credentials, tmp_path):
        _, post, _ = _run({"text": "hi", "voice_id": "x4_mingge"}, tmp_path)
        dts = post.call_args_list[0][1]["json"]["parameter"]["dts"]
        assert (dts["speed"], dts["volume"], dts["pitch"]) == (50, 50, 50)
        assert dts["language"] == "zh"
        assert dts["audio"] == {"encoding": "lame", "sample_rate": 24000}

    def test_prosody_overrides_are_passed_through(self, credentials, tmp_path):
        _, post, _ = _run(
            {"text": "hi", "voice_id": "x4_mingge", "speed": 70, "volume": 30,
             "pitch": 40, "language": "en", "sample_rate": 16000},
            tmp_path,
        )
        dts = post.call_args_list[0][1]["json"]["parameter"]["dts"]
        assert (dts["speed"], dts["volume"], dts["pitch"]) == (70, 30, 40)
        assert dts["language"] == "en"
        assert dts["audio"]["sample_rate"] == 16000

    def test_read_punctuation_maps_to_ram(self, credentials, tmp_path):
        _, post, _ = _run({"text": "hi", "voice_id": "x4_mingge"}, tmp_path)
        assert post.call_args_list[0][1]["json"]["parameter"]["dts"]["ram"] == 0

        _, post, _ = _run(
            {"text": "hi", "voice_id": "x4_mingge", "read_punctuation": True}, tmp_path
        )
        assert post.call_args_list[0][1]["json"]["parameter"]["dts"]["ram"] == 1

    def test_query_body_carries_app_id_and_task_id(self, credentials, tmp_path):
        _, post, _ = _run({"text": "hi", "voice_id": "x4_mingge"}, tmp_path)
        assert post.call_args_list[1][1]["json"] == {
            "header": {"app_id": "appid123", "task_id": "task-1"}
        }


# ----------------------------------------------------------------------
# Happy path
# ----------------------------------------------------------------------


class TestGenerate:
    def test_writes_audio_and_metadata(self, credentials, tmp_path):
        out = tmp_path / "narration.mp3"
        result, _, get = _run({"text": "长文本旁白", "voice_id": "x4_mingge"}, tmp_path)

        assert result.success is True
        assert out.read_bytes() == b"MP3BYTES"
        assert result.data["provider"] == "iflytek"
        assert result.data["task_id"] == "task-1"
        assert result.model == "iflytek/dts"
        assert result.cost_usd is None
        assert result.data["cost_status"] == "unquoted"
        assert str(out) in result.artifacts

        metadata = json.loads((tmp_path / "narration.mp3.json").read_text(encoding="utf-8"))
        assert metadata["header"]["task_status"] == 5
        assert str(tmp_path / "narration.mp3.json") in result.artifacts

    def test_audio_url_is_base64_decoded_before_download(self, credentials, tmp_path):
        result, _, get = _run({"text": "hi", "voice_id": "x4_mingge"}, tmp_path)
        assert result.data["audio_url"] == AUDIO_URL
        assert get.call_args[0][0] == AUDIO_URL

    def test_metadata_path_override_is_honored(self, credentials, tmp_path):
        meta = tmp_path / "custom" / "dts.json"
        result, _, _ = _run(
            {"text": "hi", "voice_id": "x4_mingge", "metadata_path": str(meta)}, tmp_path
        )
        assert result.success is True
        assert meta.exists()
        assert result.data["metadata_path"] == str(meta)


# ----------------------------------------------------------------------
# Polling
# ----------------------------------------------------------------------


class TestPolling:
    def test_polls_until_the_task_completes(self, credentials, tmp_path):
        result, post, _ = _run(
            {"text": "hi", "voice_id": "x4_mingge"},
            tmp_path,
            query_responses=[_query(1, with_audio=False), _query(3, with_audio=False), _query(5)],
        )
        assert result.success is True
        assert post.call_count == 4  # 1 create + 3 query

    def test_dispatch_failure_is_terminal(self, credentials, tmp_path):
        result, post, _ = _run(
            {"text": "hi", "voice_id": "x4_mingge"},
            tmp_path,
            query_responses=[_query(2, with_audio=False)],
        )
        assert result.success is False
        assert "task_status=2" in result.error
        assert post.call_count == 2  # stops instead of polling to the timeout

    def test_audio_url_short_circuits_an_unenumerated_status(self, credentials, tmp_path):
        """A finished task must not be stranded by a status the docs omit."""
        result, _, _ = _run(
            {"text": "hi", "voice_id": "x4_mingge"}, tmp_path, query_responses=[_query(4)]
        )
        assert result.success is True

    def test_timeout_is_reported(self, credentials, tmp_path):
        # A fake clock that only advances when the tool sleeps, so the deadline
        # is reached deterministically instead of by wall time.
        class _Clock:
            def __init__(self):
                self.now = 0.0

            def time(self):
                return self.now

            def sleep(self, seconds):
                self.now += seconds

        with patch("requests.post", side_effect=[_create_ok(), *[_query(3, with_audio=False)] * 50]), \
             patch("tools.audio.iflytek_tts.time", _Clock()):
            result = IFlytekTTS().execute(
                {"text": "hi", "voice_id": "x4_mingge", "timeout_seconds": 30,
                 "output_path": str(tmp_path / "a.mp3")}
            )
        assert result.success is False
        assert "did not finish within 30 seconds" in result.error


# ----------------------------------------------------------------------
# Error mapping
# ----------------------------------------------------------------------


class TestErrors:
    def test_unauthorized_signature_gets_a_hint(self, credentials, tmp_path):
        with patch("requests.post", return_value=_FakeResponse(
            {"header": {"code": 11200, "message": "HMAC signature does not match"}},
            status_code=401,
        )):
            result = IFlytekTTS().execute({"text": "hi", "voice_id": "x4_mingge"})
        assert result.success is False
        assert "IFLYTEK_API_SECRET" in result.error

    def test_clock_skew_gets_a_hint(self, credentials):
        with patch("requests.post", return_value=_FakeResponse(
            {"header": {"code": 11201, "message": "clock offset"}}, status_code=403
        )):
            result = IFlytekTTS().execute({"text": "hi", "voice_id": "x4_mingge"})
        assert "clock skew" in result.error

    def test_bad_app_id_gets_a_hint(self, credentials):
        with patch("requests.post", return_value=_FakeResponse(
            {"header": {"code": 10313, "message": "appid cannot be empty"}}
        )):
            result = IFlytekTTS().execute({"text": "hi", "voice_id": "x4_mingge"})
        assert "IFLYTEK_APP_ID" in result.error

    def test_non_json_response_is_reported(self, credentials):
        with patch("requests.post", return_value=_FakeResponse(None, status_code=502)):
            result = IFlytekTTS().execute({"text": "hi", "voice_id": "x4_mingge"})
        assert "Non-JSON response" in result.error

    def test_missing_task_id_is_reported(self, credentials):
        with patch("requests.post", return_value=_FakeResponse({"header": {"code": 0}})):
            result = IFlytekTTS().execute({"text": "hi", "voice_id": "x4_mingge"})
        assert "did not return header.task_id" in result.error


# ----------------------------------------------------------------------
# Selector routing -- the shared tts_selector contract
# ----------------------------------------------------------------------


class TestSelectorRouting:
    def test_preferred_provider_reaches_iflytek(self, credentials, tmp_path):
        from tools.audio.tts_selector import TTSSelector

        out = tmp_path / "selector.mp3"
        with patch("requests.post", side_effect=[_create_ok(), _query(5)]), \
             patch("requests.get", return_value=_FakeResponse(content=b"SELECTED")):
            result = TTSSelector().execute(
                {
                    "text": "通过选择器路由",
                    "preferred_provider": "iflytek",
                    "voice_id": "x4_mingge",
                    "output_path": str(out),
                }
            )

        assert result.success is True
        assert result.data["selected_provider"] == "iflytek"
        assert result.data["selected_tool"] == "iflytek_tts"
        assert out.read_bytes() == b"SELECTED"


# ----------------------------------------------------------------------
# Cost and idempotency
# ----------------------------------------------------------------------


class TestCost:
    @pytest.mark.parametrize("text", ["", "a" * 1000])
    def test_account_quote_required(self, text):
        with pytest.raises(PriceQuoteRequired):
            IFlytekTTS().estimate_cost({"text": text})


class TestIdempotencyKey:
    @pytest.mark.parametrize(
        "field,value",
        [
            ("voice_id", "x4_qianxue"),
            ("language", "en"),
            ("format", "opus"),
            ("sample_rate", 16000),
            ("speed", 70),
            ("volume", 30),
            ("pitch", 40),
        ],
    )
    def test_output_affecting_controls_change_the_key(self, field, value):
        tool = IFlytekTTS()
        base = {"text": "hi", "voice_id": "x4_mingge"}
        assert tool.idempotency_key(base) != tool.idempotency_key({**base, field: value})

    def test_non_output_affecting_input_keeps_the_key(self):
        tool = IFlytekTTS()
        base = {"text": "hi", "voice_id": "x4_mingge"}
        assert tool.idempotency_key(base) == tool.idempotency_key(
            {**base, "output_path": "elsewhere.mp3", "poll_interval_seconds": 9}
        )


# ----------------------------------------------------------------------
# Registry metadata
# ----------------------------------------------------------------------


class TestRegistryMetadata:
    def test_declares_every_credential_as_an_env_dependency(self):
        assert set(IFlytekTTS.dependencies) == {
            "env:IFLYTEK_APP_ID",
            "env:IFLYTEK_API_KEY",
            "env:IFLYTEK_API_SECRET",
        }

    def test_declares_tts_capability_for_selector_discovery(self):
        assert IFlytekTTS.capability == "tts"
        assert IFlytekTTS.provider == "iflytek"

    def test_does_not_claim_word_timestamps(self):
        """DTS returns no word timings; claiming otherwise would misroute captions."""
        assert IFlytekTTS.supports["timestamps"] is False


# ----------------------------------------------------------------------
# Safety -- never leak credentials
# ----------------------------------------------------------------------


class TestCredentialRedaction:
    def test_error_does_not_leak_the_api_secret(self, credentials):
        def _boom(*args, **kwargs):
            raise RuntimeError("upstream rejected authorization for secret-xyz and key-abc")

        with patch("requests.post", side_effect=_boom):
            result = IFlytekTTS().execute({"text": "hi", "voice_id": "x4_mingge"})

        assert result.success is False
        assert "secret-xyz" not in result.error
        assert "key-abc" not in result.error
        assert "***" in result.error
