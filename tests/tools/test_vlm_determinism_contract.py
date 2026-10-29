"""Metadata contract test: determinism claims must match seed support.

The registry and planning layer read a tool's `determinism` attribute to
decide whether it can be re-run reproducibly. This test locks the contract:

  - A tool declaring Determinism.SEEDED MUST accept a `seed` input and
    propagate it to the underlying inference (or the claim is a lie).
  - VLM-based tools are stochastic by nature (nonzero-temperature Ollama
    inference, no seed plumbing) and MUST declare STOCHASTIC.

If this test fails, the tool metadata drifted from its runtime behaviour —
fix the declaration, not the test.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.base_tool import Determinism  # noqa: E402
from tools.video.vlm_clip_rating import VlmClipRating  # noqa: E402
from tools.video.vlm_comparative_rank import VlmComparativeRank  # noqa: E402
from tools.video.vlm_zoom_rating import VlmZoomRating  # noqa: E402

# The VLM rating tools use Ollama with a nonzero temperature and do not
# expose or forward a seed. They are honest stochastic tools.
VLM_TOOLS = [VlmClipRating, VlmZoomRating, VlmComparativeRank]


class TestDeterminismMetadataContract(unittest.TestCase):
    def test_vlm_tools_are_stochastic(self):
        """VLM rating tools must NOT claim SEEDED without seed plumbing."""
        for tool_cls in VLM_TOOLS:
            tool = tool_cls()
            self.assertEqual(
                tool.determinism,
                Determinism.STOCHASTIC,
                f"{tool_cls.__name__} claims {tool.determinism.value} but "
                f"does not accept/propagate a seed — it must be STOCHASTIC.",
            )

    def test_seeded_tools_expose_seed_parameter(self):
        """Any tool claiming SEEDED must accept a `seed` input."""
        import importlib
        import pkgutil
        import tools.video as video_pkg

        for mod in pkgutil.iter_modules(video_pkg.__path__):
            if not mod.name.startswith("vlm_"):
                continue
            module = importlib.import_module(f"tools.video.{mod.name}")
            for attr in dir(module):
                cls = getattr(module, attr)
                if not isinstance(cls, type) or not hasattr(cls, "determinism"):
                    continue
                # instantiate only BaseTool subclasses
                try:
                    tool = cls()
                except Exception:
                    continue
                if not hasattr(tool, "input_schema"):
                    continue
                if tool.determinism == Determinism.SEEDED:
                    props = tool.input_schema.get("properties", {})
                    self.assertIn(
                        "seed",
                        props,
                        f"{cls.__name__} claims SEEDED but has no `seed` "
                        f"parameter — either add seed plumbing or mark "
                        f"STOCHASTIC.",
                    )


if __name__ == "__main__":
    unittest.main()
