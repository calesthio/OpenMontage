"""Paid submissions must survive polling/download failures without resubmission."""
import json
from unittest.mock import patch

import pytest
from tools.audio.iflytek_tts import IFlytekTTS
from tools.provider_pricing import PriceQuoteRequired
from tools.base_tool import ResumeSupport
from tests.tools.test_iflytek_tts import _create_ok, _query, _FakeResponse


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    for key in ('APP_ID', 'API_KEY', 'API_SECRET'):
        monkeypatch.setenv('IFLYTEK_' + key, 'test-' + key)
    monkeypatch.delenv('IFLYTEK_TTS_VCN', raising=False)


def test_quote_required_instead_of_invented_charge():
    with pytest.raises(PriceQuoteRequired):
        IFlytekTTS().estimate_cost({'text': 'hello'})
    assert IFlytekTTS().dry_run({'text': 'hello'})['estimated_cost_usd'] is None


@pytest.mark.parametrize('failure', ['poll', 'download'])
def test_accepted_task_survives_failure_and_resume(tmp_path, failure):
    tool = IFlytekTTS()
    inputs = {'text': 'hello', 'voice_id': 'voice', 'output_path': str(tmp_path / 'a.mp3')}
    poll = [TimeoutError('poll timeout'), _query(5).json()] if failure == 'poll' else [_query(5).json()] * 2
    download = [_FakeResponse(content=b'audio')] if failure == 'poll' else [OSError('interrupted download'), _FakeResponse(content=b'audio')]
    with patch('requests.post', return_value=_create_ok()) as post, patch.object(tool, '_poll_query', side_effect=poll), patch('requests.get', side_effect=download):
        first = tool.execute(inputs)
        assert not first.success
        assert first.data['task_id'] == 'task-1'
        saved = json.loads((tmp_path / 'a.mp3.json.task.json').read_text())
        assert saved == first.data['resume_inputs']
        assert first.cost_usd is None
        assert not (tmp_path / 'a.mp3').exists()
        # A new instance/process can recover using just the saved checkpoint.
        second = tool.execute(saved)
        assert second.success, second.error
        assert second.cost_usd is None
        assert second.data['cost_status'] == 'unquoted'
        assert post.call_count == 1
        assert (tmp_path / 'a.mp3').read_bytes() == b'audio'


def test_resume_only_queries_without_text_or_voice(tmp_path):
    with patch('requests.post', return_value=_query(5)) as post, patch('requests.get', return_value=_FakeResponse(content=b'audio')), patch('time.sleep'):
        result = IFlytekTTS().execute({'task_id': 'task-1', 'output_path': str(tmp_path / 'a.mp3')})
    assert result.success, result.error
    assert post.call_count == 1
    assert '/dts_query?' in post.call_args.args[0]


def test_checkpoint_write_failure_still_returns_task_id(tmp_path):
    with patch('requests.post', return_value=_create_ok()) as post, patch.object(IFlytekTTS, '_atomic_write', side_effect=OSError('disk full')):
        result = IFlytekTTS().execute({'text': 'hello', 'voice_id': 'voice', 'output_path': str(tmp_path / 'a.mp3')})
    assert not result.success
    assert result.data['resume_inputs']['task_id'] == 'task-1'
    assert post.call_count == 1


def test_submission_retry_disabled():
    assert IFlytekTTS.retry_policy.max_retries == 0
    assert not IFlytekTTS.retry_policy.retryable_errors
    assert IFlytekTTS.resume_support == ResumeSupport.FROM_CHECKPOINT


def test_signed_url_is_redacted_on_submission_failure(tmp_path):
    tool = IFlytekTTS()
    url = tool._signed_url(tool.CREATE_PATH, api_key='test-API_KEY', api_secret='test-API_SECRET')
    with patch('requests.post', side_effect=TimeoutError(url)) as post:
        result = tool.execute({'text': 'hello', 'voice_id': 'voice', 'output_path': str(tmp_path / 'a.mp3')})
    assert not result.success
    assert 'authorization=' not in result.error
    assert post.call_count == 1
