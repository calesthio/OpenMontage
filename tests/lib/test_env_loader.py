"""There is one `.env` reader: `lib.env_loader`.

`tools/base_tool.py`, `ToolRegistry` and `lib/env_loader.py` each parsed `.env`
on their own, with three slightly different ideas of what a line means. The two
tool-side copies now delegate, and the built-in fallback parser (used only when
python-dotenv cannot read the file) agrees with it on the cases that matter.
"""

import inspect

import pytest

from lib import env_loader
from lib.env_loader import _parse_env_text, load_env, read_env_file
from tools import base_tool
from tools.tool_registry import ToolRegistry

SAMPLE = """
# a comment
PLAIN=value
export EXPORTED=yes
QUOTED="has # hash and spaces "
SINGLE='single quoted'
INLINE=keep   # trailing note
EMPTY_WITH_NOTE=   # only a note
EMPTY=
not a pair
"""

EXPECTED = {
    "PLAIN": "value",
    "EXPORTED": "yes",
    "QUOTED": "has # hash and spaces ",
    "SINGLE": "single quoted",
    "INLINE": "keep",
    "EMPTY_WITH_NOTE": "",
    "EMPTY": "",
}


def test_builtin_parser_reads_the_cases_that_matter():
    assert _parse_env_text(SAMPLE) == EXPECTED


def test_file_reader_agrees_with_the_builtin_parser(tmp_path):
    path = tmp_path / ".env"
    path.write_text(SAMPLE, encoding="utf-8")
    assert read_env_file(path) == EXPECTED
    assert read_env_file(tmp_path / "missing.env") == {}


def test_reader_falls_back_when_python_dotenv_cannot_be_used(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text(SAMPLE, encoding="utf-8")
    import dotenv

    def unusable(*args, **kwargs):
        raise RuntimeError("dotenv unavailable")

    monkeypatch.setattr(dotenv, "dotenv_values", unusable)
    assert read_env_file(path) == EXPECTED


def test_load_env_fills_unset_and_blank_but_keeps_real_values(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("A_UNSET=from_file\nA_BLANK=from_file\nA_SET=from_file\n")
    monkeypatch.delenv("A_UNSET", raising=False)
    monkeypatch.setenv("A_BLANK", "   ")
    monkeypatch.setenv("A_SET", "from_process")
    load_env(tmp_path)
    import os

    assert os.environ["A_UNSET"] == "from_file"
    assert os.environ["A_BLANK"] == "from_file"
    assert os.environ["A_SET"] == "from_process"
    for key in ("A_UNSET", "A_BLANK"):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize("delegate", [base_tool._load_dotenv, ToolRegistry._load_dotenv])
def test_tool_side_loaders_delegate_instead_of_parsing(delegate, monkeypatch):
    source = inspect.getsource(delegate)
    assert "load_env" in source
    assert "partition" not in source and "open(" not in source   # no private parser left

    calls = []
    monkeypatch.setattr(env_loader, "load_env", lambda root=None: calls.append(root))
    delegate()
    assert len(calls) == 1 and (calls[0] / "tools").is_dir()
