from pathlib import Path

from lib.envfile import parse_env_file


def test_parse_env_file_handles_comments_quotes_and_export(tmp_path: Path):
    p = tmp_path / ".env"
    p.write_text(
        "# comment\n"
        "\n"
        "export ELEVENLABS_API_KEY=\"sk_abc\"\n"
        "ELEVENLABS_VOICE_IDS='en:V1,fr:V2'\n"
        "NOT_A_PAIR\n"
        "ELEVENLABS_MODEL_ID=ELEVENLABS_MODEL_ID:-eleven_multilingual_v2\n"
    )
    out = parse_env_file(p)
    assert out == {
        "ELEVENLABS_API_KEY": "sk_abc",
        "ELEVENLABS_VOICE_IDS": "en:V1,fr:V2",
        "ELEVENLABS_MODEL_ID": "ELEVENLABS_MODEL_ID:-eleven_multilingual_v2",
    }


def test_parse_env_file_missing_returns_empty(tmp_path: Path):
    assert parse_env_file(tmp_path / "nope.env") == {}


def test_parse_env_file_strips_inline_comments_but_keeps_hashes_in_quotes(tmp_path: Path):
    p = tmp_path / ".env"
    p.write_text('A=en:V1,de:V2   # one entry per language\nB="x # not a comment"\nC=v#tight\n')
    assert parse_env_file(p) == {"A": "en:V1,de:V2", "B": "x # not a comment", "C": "v#tight"}
