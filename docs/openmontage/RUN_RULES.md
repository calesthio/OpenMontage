# RUN RULES — OpenMontage factory lane (Kilo)

**Created:** 2026-10-22
**Source of truth:** `FACTORY_100_SPEC.md` (root, never edited) + this file.
**Applies to:** every Kilo session in the factory lane (`kilo/mega-100` and later working branches).
**Roles:** all work in a run is **inline, not independent** unless a separate read-only reviewer session is used.

These rules are operational. Where a rule conflicts with a task instruction, the task
instruction wins **only** if it does not break a hard rule (no paid routes, no secrets,
no media commits, fail-closed QC, no editing of protected files).

---

## 1. Scope — what Kilo may write

**Owned paths (Kilo may edit, commit and push):**

| Path | Note |
|---|---|
| `docs/` | includes `docs/openmontage/**` |
| `tools/` | **except** `tools/prompting/` |
| `scripts/` | **except** `scripts/score_rubric.py` |
| `tests/` | |
| `config/` | |
| `.kilo/` | project skills/agents only |

**Never edited by Kilo (any edit is a violation):**

- `FACTORY_100_SPEC.md` (root) — proposals go to `docs/openmontage/SPEC_CHANGE_REQUESTS.md`.
- `AGENTS.md` (root).
- `.env`, `.env.*` (including `.env.example`) — owner-owned.

**Not owned by Kilo (other lane; never committed from this repo):**

- `youtube-niche-finder/` (OpenCode research lane; reports are copied by the owner into
  `docs/openmontage/audit/demand/`).
- `tools/prompting/`, `scripts/score_rubric.py`, `niches/*/creatures/`, `evidence/spec_evo/`,
  `OPENCODE_REQUESTS.md` (OpenCode). Requests to change them go to
  `docs/openmontage/OPENCODE_REQUESTS.md`.

**Media and secrets are never committed.** Video, audio, images, model weights and large
binaries live in gitignored `projects/` or `/tmp`. No token, cookie, credential or `.env`
content is ever written to a file, a log, a commit message or chat output. `KAGGLE_API_TOKEN`
is reported as present/absent (name only), never its value.

## 2. Git rules

- Commit **own paths only**. Never `git add -A`, never `git add .`; stage explicit paths.
- Never commit media, secrets, caches or generated renders.
- Before committing: `git status`, `git diff`, `git log --oneline -10`.
- Sync with `git pull --rebase` (never merge commits from the remote).
- Push **non-force** to `origin`. `--force`/`--force-with-lease` is forbidden.
- Never commit to `main`. Work on a named working branch (`kilo/mega-100` currently).
- Stray untracked files that are not ours are **listed, never added**.

## 3. Test-first rule

- New behaviour or a bugfix is written as a failing test first (**red**: run it, record the
  command, the failure and the exit code), then the implementation, then the same command
  again (**green**).
- Record exact commands and exit codes in the run log and the final report.
- Never weaken or delete a test to make a suite pass; never silently skip a check.
- A test that cannot run is reported as `NOT_RUN`/`BLOCKED`, never as `PASS`.

## 4. Budget, network and routes

- Strict **$0**. Free/open tools only. No paid API, no paid footage, no paid fallback.
- An unnamed or unpriced route is **BLOCKED**, not free (`lib/zero_cost_gate.py`).
- Unknown price = forbidden until verified against an official source.
- Downloads use `curl -L`; downloads land only in gitignored `projects/` or `/tmp`, and are
  deleted when the milestone ends.

## 5. Quality gates (fail-closed)

- Every QC check reports one of `PASS | REVIEW | BLOCKED | FAILED | NOT_RUN`.
- **A check that cannot run is `BLOCKED`/`NOT_RUN`, never `PASS`.** The release verdict
  treats `NOT_RUN`/`BLOCKED` as not passed.
- QC thresholds come from `config/qc_thresholds.json`. **No silent threshold changes**:
  a threshold change requires an explicit owner decision and a documented reason.
- Rights are fail-closed: unknown rights basis = asset not usable; third-party credit,
  NC/ND licences and emblem-as-main-picture are `REJECT`.

## 6. Kaggle / remote job discipline

- **Never loop or sleep on Kaggle.** Submit once, record the job id and state, and make
  **at most one status call between phases**.
- No busy-wait, no `sleep` in a poll loop, no repeated status calls inside one phase.
- A failed attempt must change something concrete before the next attempt.

## 7. Persistence rule (per blocker)

- Up to **4 attempts** per blocker.
- Each attempt must **change something concrete** (different flag, different model, different
  parameter, different environment, different code path) — repeating the same failing call
  does not count as an attempt.
- **90 minute cap** per blocker (sum of the attempts). When the cap is reached the blocker is
  reported as `BLOCKED` with the evidence collected, and work continues on other items.
- Never escalate to a paid route to escape a blocker.

## 8. Owner-gated items

- An item that needs an owner decision (voice acceptance, blind image scoring, rights flags,
  emblem policy, disclosure wording, publishing) uses the **safest default**, is marked
  **`OWNER_GATED`**, and is **never waited on**. Work continues without it.

## 9. Disk discipline

- Keep **>= 800 MB free**.
- If free disk drops below 800 MB **after deleting the caches and renders this run created**,
  stop the run: write the state, report, and do not start new work.

## 10. Reporting

- **Never claim a command, test, commit, push, download, Kaggle run or subagent run that was
  not observed.** Unverified work is reported as `NOT_CHECKED`/`NOT_RUN`.
- Roles executed by a single agent are labelled **inline, not independent**.
- Image/audio quality is judged by the **owner**, not by agents.
- **Final report: max 12 lines**, in this order:
  `Status`, `Commit`, `Done`, `Failed/NOT_CHECKED`, `Owner decision`, `Next action`.

## 11. Non-goals

No automatic publishing, no YouTube OAuth, no comment posting, no voice cloning, no music
without stored licence evidence, no photoreal fake imagery, no AI upscaling of real footage,
no scraping of YouTube videos as stock footage.
