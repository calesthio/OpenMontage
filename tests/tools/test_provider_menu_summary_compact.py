"""``provider_menu_summary(compact=True)`` is the form printed at preflight.

The per-tool ``setup_offers`` list made the mandatory preflight dump ~40 KB on
a machine with few keys configured, and the agent then regrouped it by env var
by hand. The compact form does that grouping in the registry.
"""

from __future__ import annotations

import json

from tools.tool_registry import _group_setup_offers, registry


def offer(tool, capability, env_vars=None, hint="Set the key.", **extra):
    entry = {"tool": tool, "capability": capability, "install_instructions": hint}
    if env_vars:
        entry["env_vars"] = env_vars
    entry.update(extra)
    return entry


def test_tools_sharing_a_credential_collapse_into_one_group():
    groups, others = _group_setup_offers([
        offer("flux_fal", "image_generation", ["FAL_KEY"], hint="Set FAL_KEY."),
        offer("kling_fal", "video_generation", ["FAL_KEY"]),
        offer("wan_fal", "video_generation", ["FAL_KEY"]),
        offer("heygen_video", "avatar", ["HEYGEN_API_KEY"]),
    ])

    assert others == []
    assert groups[0] == {
        "env_vars": ["FAL_KEY"],
        "unlocks": 3,
        "capabilities": {"image_generation": 1, "video_generation": 2},
        "tools": ["flux_fal", "kling_fal", "wan_fal"],
        "install_instructions": "Set FAL_KEY.",
    }
    # Ordered by impact: the credential that unlocks the most comes first.
    assert [g["env_vars"] for g in groups] == [["FAL_KEY"], ["HEYGEN_API_KEY"]]


def test_non_env_fixes_keep_a_short_hint():
    groups, others = _group_setup_offers([
        offer(
            "comfyui_video", "video_generation", hint="x" * 900,
            kind="local_server", fix_complexity="5-minute install",
            server_url="http://127.0.0.1:8188", workflows=["a", "b"],
        ),
    ])

    assert groups == []
    assert others == [{
        "capability": "video_generation",
        "tool": "comfyui_video",
        "install_instructions": "x" * 157 + "...",
        "kind": "local_server",
        "fix_complexity": "5-minute install",
    }]


def test_compact_summary_names_every_offered_tool_exactly_once():
    registry.ensure_discovered()
    full = registry.provider_menu_summary()
    compact = registry.provider_menu_summary(compact=True)

    assert "setup_offers" not in compact
    assert {k: compact[k] for k in ("composition_runtimes", "capabilities", "runtime_warnings")} == {
        k: full[k] for k in ("composition_runtimes", "capabilities", "runtime_warnings")
    }
    offered = sorted(o["tool"] for o in full["setup_offers"])
    grouped = sorted(
        [tool for group in compact["setup_groups"] for tool in group["tools"]]
        + [other["tool"] for other in compact["other_setup"]]
    )
    assert grouped == offered
    assert sum(g["unlocks"] for g in compact["setup_groups"]) + len(
        compact["other_setup"]
    ) == len(full["setup_offers"])


def test_compact_summary_is_never_larger_than_the_full_one():
    registry.ensure_discovered()

    assert len(json.dumps(registry.provider_menu_summary(compact=True))) <= len(
        json.dumps(registry.provider_menu_summary())
    )
