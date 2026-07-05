import os

from tools.env_loader import load_dotenv_files


def test_loads_env_local_when_env_is_absent(monkeypatch, tmp_path):
    monkeypatch.delenv("RUNNINGHUB_API_KEY", raising=False)
    (tmp_path / ".env.local").write_text(
        "RUNNINGHUB_API_KEY=local-test-key\n",
        encoding="utf-8",
    )

    load_dotenv_files(tmp_path)

    assert "RUNNINGHUB_API_KEY" in os.environ
    assert os.environ["RUNNINGHUB_API_KEY"] == "local-test-key"


def test_env_local_overrides_env_file_but_not_process_env(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNNINGHUB_API_KEY", "process-key")
    (tmp_path / ".env").write_text("RUNNINGHUB_API_KEY=env-key\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text(
        "RUNNINGHUB_API_KEY=local-key\n",
        encoding="utf-8",
    )

    load_dotenv_files(tmp_path)

    assert os.environ["RUNNINGHUB_API_KEY"] == "process-key"


def test_env_local_overrides_env_when_process_env_is_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("RUNNINGHUB_API_KEY", raising=False)
    (tmp_path / ".env").write_text("RUNNINGHUB_API_KEY=env-key\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text(
        "RUNNINGHUB_API_KEY=local-key\n",
        encoding="utf-8",
    )

    load_dotenv_files(tmp_path)

    assert os.environ["RUNNINGHUB_API_KEY"] == "local-key"
