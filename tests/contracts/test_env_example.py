from pathlib import Path

from dotenv import dotenv_values


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_env_example_does_not_turn_comments_into_credentials() -> None:
    """A fresh copy of .env.example must leave every documented key unset."""

    values = dotenv_values(REPO_ROOT / ".env.example")
    false_credentials = {
        key: value
        for key, value in values.items()
        if isinstance(value, str) and value.lstrip().startswith("#")
    }

    assert false_credentials == {}
