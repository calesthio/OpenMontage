from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.base_tool import BaseTool, DependencyError, ToolResult


class DummyTool(BaseTool):
    def execute(self, inputs: dict) -> ToolResult:
        return ToolResult(success=True)


class BinaryDependencyTests(unittest.TestCase):
    def test_binary_dependency_prefix_is_checked_like_cmd(self) -> None:
        tool = DummyTool()
        tool.dependencies = ["binary:definitely-not-installed-openmontage-test"]
        tool.install_instructions = "install it"

        with patch("tools.base_tool.shutil.which", return_value=None):
            with self.assertRaises(DependencyError):
                tool.check_dependencies()

    def test_binary_dependency_prefix_accepts_available_command(self) -> None:
        tool = DummyTool()
        tool.dependencies = ["binary:ffmpeg"]
        tool.install_instructions = "install ffmpeg"

        with patch("tools.base_tool.shutil.which", return_value="/usr/bin/ffmpeg"):
            tool.check_dependencies()
    def test_run_command_error_preserves_called_process_error_type(self) -> None:
        tool = DummyTool()

        with self.assertRaises(subprocess.CalledProcessError) as ctx:
            tool.run_command([
                sys.executable,
                "-c",
                "import sys; print('specific stderr', file=sys.stderr); sys.exit(7)",
            ])

        self.assertEqual(ctx.exception.returncode, 7)
        self.assertIn("specific stderr", str(ctx.exception))


class EnvCommentHardeningTests(unittest.TestCase):
    """Verify that env var values starting with # are treated as unset (fixes #431)."""

    def setUp(self) -> None:
        self._saved = {
            k: os.environ.pop(k, None)
            for k in ("OPENMONTAGE_TEST_KEY", "OPENMONTAGE_TEST_KEY2")
        }

    def tearDown(self) -> None:
        for k, v in self._saved.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

    def test_env_var_with_comment_value_is_treated_as_unset(self) -> None:
        """An env var whose value starts with # should fail dependency check."""
        os.environ["OPENMONTAGE_TEST_KEY"] = "# some comment text"
        tool = DummyTool()
        tool.dependencies = ["env:OPENMONTAGE_TEST_KEY"]
        tool.install_instructions = "set OPENMONTAGE_TEST_KEY in .env"

        with self.assertRaises(DependencyError):
            tool.check_dependencies()

    def test_env_var_with_comment_and_leading_space_is_treated_as_unset(self) -> None:
        """An env var whose value is whitespace then # should fail dependency check."""
        os.environ["OPENMONTAGE_TEST_KEY"] = "   # some comment text"
        tool = DummyTool()
        tool.dependencies = ["env:OPENMONTAGE_TEST_KEY"]
        tool.install_instructions = "set OPENMONTAGE_TEST_KEY in .env"

        with self.assertRaises(DependencyError):
            tool.check_dependencies()

    def test_env_var_with_legitimate_value_is_not_rejected(self) -> None:
        """An env var with a real value (not starting with #) should pass."""
        os.environ["OPENMONTAGE_TEST_KEY"] = "sk-real-api-key-value"
        tool = DummyTool()
        tool.dependencies = ["env:OPENMONTAGE_TEST_KEY"]
        tool.install_instructions = "set OPENMONTAGE_TEST_KEY in .env"

        tool.check_dependencies()

    def test_env_var_with_empty_value_is_treated_as_unset(self) -> None:
        """An env var with empty value should fail dependency check."""
        os.environ["OPENMONTAGE_TEST_KEY"] = ""
        tool = DummyTool()
        tool.dependencies = ["env:OPENMONTAGE_TEST_KEY"]
        tool.install_instructions = "set OPENMONTAGE_TEST_KEY in .env"

        with self.assertRaises(DependencyError):
            tool.check_dependencies()


if __name__ == "__main__":
    unittest.main()
