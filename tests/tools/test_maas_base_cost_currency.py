"""MaasBaseTool.cost_currency contract.

Confirmed live: the job cost ledger (server/app/runner/tool_bridge.py)
treats every tool's ToolResult.cost_usd as an already-CNY amount unless the
tool declares otherwise via BaseTool.cost_currency. The MaaS gateway bills
internally in CNY (see maas_video.py's estimate_cost docstring) and is the
one deliberate exception — pin it here so a refactor can't silently drop it
and start treating real MaaS spend as 7.2x too large.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.maas_base import MaasBaseTool
from tools.video.maas_video import MaasVideo
from tools.audio.maas_tts import MaasTTS
from tools.graphics.maas_image import MaasImage


def test_maas_base_tool_declares_cny():
    assert MaasBaseTool.cost_currency == "CNY"


def test_every_maas_tool_inherits_cny():
    assert MaasVideo.cost_currency == "CNY"
    assert MaasTTS.cost_currency == "CNY"
    assert MaasImage.cost_currency == "CNY"
