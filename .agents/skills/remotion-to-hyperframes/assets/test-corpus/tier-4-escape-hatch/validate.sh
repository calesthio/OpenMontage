#!/usr/bin/env bash
# validate.sh — assert lint_source.py output matches expected.json for every T4 case.
#
# T4 has no renders to diff. The skill is graded on whether it correctly
# refuses to translate each case (or drops only the lambda config in case 5,
# or warns appropriately in cases 6 and 7).
#
# Usage:
#   ./validate.sh
# Exit 0 on pass.

set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$(cd "$THIS_DIR/../../../scripts" && pwd)"
EXPECTED="$THIS_DIR/expected.json"

if [[ ! -f "$SCRIPTS_DIR/lint_source.py" ]]; then
  echo "error: lint_source.py not found at $SCRIPTS_DIR/lint_source.py" >&2
  exit 2
fi
if [[ ! -f "$EXPECTED" ]]; then
  echo "error: expected.json not found at $EXPECTED" >&2
  exit 2
fi

# Drive lint_file() in-process so the per-case overhead is one Python startup,
# not N (8 cases × ~80 ms forking python3 was the dominant cost).
SCRIPTS_DIR="$SCRIPTS_DIR" \
THIS_DIR="$THIS_DIR" \
EXPECTED="$EXPECTED" \
python3 <<'PY'
import json
import os
import sys
from collections import Counter
from pathlib import Path

scripts_dir = Path(os.environ["SCRIPTS_DIR"])
this_dir = Path(os.environ["THIS_DIR"])
expected_path = Path(os.environ["EXPECTED"])
cases_dir = this_dir / "cases"

sys.path.insert(0, str(scripts_dir))
from lint_source import BLOCKER, WARNING, lint_file  # noqa: E402

expected = json.loads(expected_path.read_text())

fails: list[str] = []
passes: list[str] = []

for case in expected["cases"]:
    file_name = case["file"]
    fixture = cases_dir / file_name
    if not fixture.exists():
        fails.append(f"{file_name}: fixture missing at {fixture}")
        continue

    findings = lint_file(fixture)
    rule_counts: Counter[str] = Counter()
    severity_by_rule: dict[str, str] = {}
    for f in findings:
        rule_counts[f.rule] += 1
        severity_by_rule[f.rule] = f.severity

    case_failed = False

    def assert_rule(expected_entry, expected_severity_floor, kind):
        global case_failed
        rule = expected_entry["rule"]
        min_count = expected_entry["min_count"]
        actual = rule_counts[rule]
        actual_severity = severity_by_rule.get(rule)
        if actual < min_count:
            fails.append(f"{file_name}: expected >={min_count} {kind} findings of rule {rule}, got {actual}")
            case_failed = True
        elif actual_severity not in expected_severity_floor:
            fails.append(
                f"{file_name}: rule {rule} found but severity={actual_severity!r} (expected {kind})"
            )
            case_failed = True

    for entry in case["expected"]["blockers"]:
        assert_rule(entry, {BLOCKER}, "blocker")
    for entry in case["expected"]["warnings"]:
        assert_rule(entry, {WARNING, BLOCKER}, "warning")

    # Implied lint exit code: 1 when blockers are expected, 0 otherwise.
    has_blockers = any(f.severity == BLOCKER for f in findings)
    expected_has_blockers = bool(case["expected"]["blockers"])
    if has_blockers != expected_has_blockers:
        fails.append(
            f"{file_name}: implied lint exit {1 if has_blockers else 0}, "
            f"expected {1 if expected_has_blockers else 0} (blockers expected: {expected_has_blockers})"
        )
        case_failed = True

    if not case_failed:
        passes.append(file_name)

print(f"Passed: {len(passes)}")
for name in passes:
    print(f"  ✓ {name}")
if fails:
    print(f"Failed: {len(fails)}")
    for msg in fails:
        print(f"  ✗ {msg}")
    sys.exit(1)
sys.exit(0)
PY
