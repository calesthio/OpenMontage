"""Contract test: the canonical event-type fixture matches the emit sites.

The backend emits ~21 distinct SSE event types; the frontend mirrors them in
two hand-maintained maps (EVENT_COLOR / EVENT_TYPE_LABELS in
web/components/job-status.tsx). That mirroring has drifted twice already
(commit 33a0273 fixed 7 unmapped types; "warning" went unmapped again after
that), so the contract is now test-enforced from both sides:

  * THIS test asserts schemas/events.json `event_types` equals the set of
    event-type literals actually found in the three emit-site source files.
  * web/__tests__/job-status.test.tsx asserts every fixture type is either
    mapped in EVENT_COLOR or deliberately allowlisted in `muted_ok`.

Extraction is a regex over the source text, which is acceptable here because
every emit site passes a literal dict with a literal "type" value. Known
limits of this approach (documented so nobody over-trusts it):

  * It only sees `"type": "<literal>"` inside the scanned files. An event
    type built dynamically (f-string, variable) would be missed — the one
    existing dynamic site, events.py's synthesized terminal event
    (`ev_type = "job_completed" if ... else "job_failed"`), gets its own
    dedicated pattern below.
  * It cannot tell dict literals passed to _emit/emit_event/push_event apart
    from other dicts syntactically; instead, non-event uses of the key
    "type" (OpenAI tool schemas' "type": "function" and JSON-schema
    "type": "object"/"string"/...) are excluded via NON_EVENT_TYPE_VALUES.
    A future EVENT named exactly like a JSON-schema type keyword would be
    wrongly excluded — don't name one that.
  * Set equality (not counts or line positions) keeps this robust to emit
    sites moving between helpers within the same files.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "schemas" / "events.json"

# The only three files that push SSE events (via stage_runner._emit,
# tool_bridge's emit_event callback, or job_store.push_event). events.py is
# included because it synthesizes terminal events on replay.
EMIT_SOURCE_FILES = [
    REPO_ROOT / "server" / "app" / "runner" / "stage_runner.py",
    REPO_ROOT / "server" / "app" / "runner" / "tool_bridge.py",
    REPO_ROOT / "server" / "app" / "routers" / "events.py",
]

# `"type": "<value>"` occurrences that are NOT SSE events: OpenAI tool-call /
# function-schema dicts ("function") and JSON-schema type keywords embedded
# in the tool definitions.
NON_EVENT_TYPE_VALUES = {
    "function",
    "object", "string", "number", "integer", "boolean", "array", "null",
}

# `"type": "stage_started"` — the literal dicts passed to the emit helpers.
_TYPE_LITERAL_RE = re.compile(r'"type"\s*:\s*"([a-z0-9_]+)"')

# events.py's synthesized replay terminal event:
#   ev_type = "job_completed" if job["status"] == "completed" else "job_failed"
# followed by `"type": ev_type` — the literals never appear next to "type",
# so the main pattern can't see them.
_EV_TYPE_ASSIGN_RE = re.compile(
    r'\bev_type\s*=\s*"([a-z0-9_]+)"\s+if\b[^\n]*\belse\s+"([a-z0-9_]+)"'
)


def _scan_emitted_types() -> set[str]:
    found: set[str] = set()
    for path in EMIT_SOURCE_FILES:
        source = path.read_text(encoding="utf-8")
        for value in _TYPE_LITERAL_RE.findall(source):
            if value not in NON_EVENT_TYPE_VALUES:
                found.add(value)
        for a, b in _EV_TYPE_ASSIGN_RE.findall(source):
            found.update((a, b))
    return found


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_fixture_matches_emit_sites():
    fixture = set(_load_fixture()["event_types"])
    emitted = _scan_emitted_types()

    missing_from_fixture = sorted(emitted - fixture)
    stale_in_fixture = sorted(fixture - emitted)

    assert not missing_from_fixture and not stale_in_fixture, (
        "schemas/events.json is out of sync with the backend emit sites.\n"
        f"  Emitted but NOT in the fixture: {missing_from_fixture}\n"
        f"  In the fixture but no longer emitted: {stale_in_fixture}\n"
        "If you added/removed an event type, update schemas/events.json "
        "AND the frontend maps (EVENT_COLOR / EVENT_TYPE_LABELS in "
        "web/components/job-status.tsx) — the web suite "
        "(web/__tests__/job-status.test.tsx) enforces the frontend half."
    )


def test_fixture_muted_ok_is_subset_of_event_types():
    # muted_ok is an allowlist over event_types — an entry outside the real
    # type set would be a typo silently weakening the frontend assertion.
    fixture = _load_fixture()
    unknown = sorted(set(fixture["muted_ok"]) - set(fixture["event_types"]))
    assert not unknown, (
        f"schemas/events.json muted_ok lists types not in event_types: {unknown}"
    )


def test_fixture_has_no_duplicates():
    fixture = _load_fixture()
    for key in ("event_types", "muted_ok"):
        values = fixture[key]
        assert len(values) == len(set(values)), (
            f"schemas/events.json {key} contains duplicates"
        )
