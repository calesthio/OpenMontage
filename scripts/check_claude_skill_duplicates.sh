#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
duplicate_found=0

for claude_skill in "$REPO_ROOT"/.claude/skills/*; do
    [[ -d "$claude_skill" && ! -L "$claude_skill" ]] || continue

    for agent_skill in "$REPO_ROOT"/.agents/skills/*; do
        [[ -d "$agent_skill" ]] || continue

        if diff -qr "$claude_skill" "$agent_skill" >/dev/null; then
            printf '%s duplicates %s; replace it with a symlink.\n' \
                "${claude_skill#"$REPO_ROOT"/}" \
                "${agent_skill#"$REPO_ROOT"/}" >&2
            duplicate_found=1
            break
        else
            diff_status=$?
            if [[ "$diff_status" -gt 1 ]]; then
                printf 'Could not compare %s with %s.\n' \
                    "${claude_skill#"$REPO_ROOT"/}" \
                    "${agent_skill#"$REPO_ROOT"/}" >&2
                exit "$diff_status"
            fi
        fi
    done
done

exit "$duplicate_found"
