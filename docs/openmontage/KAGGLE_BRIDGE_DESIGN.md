# Kaggle Bridge Design — OpenMontage Milestone K0

**Status:** design spec only. No application code, no pipeline changes, no process/lock changes.
**Auth status (step 3):** `KAGGLE_API_TOKEN` is **not set** in this environment → the read-only auth test (`kaggle kernels list --mine`) was **not run**, per step 3. The owner must create the Codespaces secret `KAGGLE_API_TOKEN` and restart the codespace before any live Kaggle call. **No token value was printed, logged, or committed.** Only presence (yes/no) and length are reported below.

---

## Step 0 — Preflight (observed)

- git status: clean; HEAD `7fd52a4` on `factory/business-documentary-pilot`.
- `df -h /workspaces`: 3.2 GB free (90% used).
- `KAGGLE_API_TOKEN`: **not set** (length n/a).

---

## Step 1 — Reachability (observed; 4 of 6 request cap used)

| Target | DNS | HTTPS (20 s timeout) | Classification |
|---|---|---|---|
| kaggle.com | resolves (35.244.233.98) | HTTP/2 404 on `/` (service up; root path has no handler) | reachable |
| api.kaggle.com | resolves (34.54.168.202) | HTTP/2 404 on `/` (service up; root path has no handler) | reachable |

Both endpoints are **reachable**. The 404 on `/` is expected (no root handler); it confirms the TLS endpoint is alive, not an error. No auth was used. 4 requests used; 2 remain unused.

---

## Step 2 — Official CLI install (observed)

- Package: `kaggle` (from Kaggle/kaggle-cli, PyPI), installed with `pip3 install --only-binary=:all: kaggle`.
- Version: `kaggle 2.2.4`.
- CLI path: `/home/codespace/.python/current/bin/kaggle`.
- Install size: `kaggle` package `1.3 MB` (plus small deps already present); `/workspaces` free space unchanged at ~3.2 GB (did not enlarge beyond a few MB).
- No third-party Kaggle MCP or wrappers installed.
- First-run notice (observed, no secret): CLI offers OAuth via `kaggle auth login` or API token via `KAGGLE_API_TOKEN` env var / `~/.kaggle/access_token`.

---

## Step 3 — Auth test (STOPPED per step 3)

`KAGGLE_API_TOKEN` is **not set**. Per the milestone rules, `kaggle kernels list --mine` was **not run**. Required next step (owner): create the Codespaces secret `KAGGLE_API_TOKEN` (value copied from https://www.kaggle.com/settings/api → "Generate New Token" under "API") and restart the codespace. Only after that can `kaggle kernels list --mine --page-size 5` be run read-only to confirm auth.

No token value was handled by this session.

---

## Step 4 — CLI help quotes (observed; read-only, no auth)

### `kaggle kernels` (top-level)

```
usage: kaggle kernels [-h]
                      {list,files,get,init,push,pull,output,status,logs,update,delete,topics} ...

commands:
  list                List available kernels. By default, shows 20 results sorted by hotness
  ...
  push (update)       Push new code to a kernel and run the kernel
  pull (get)          Pull down code from a kernel
  output              Get data output from the latest kernel run
  status              Display the status of the latest kernel run
  ...
```

### `kaggle kernels push --help`

```
usage: kaggle kernels push [-h] [-p FOLDER] [-t TIMEOUT] [--accelerator ACC]

options:
  -h, --help            show this help message and the exit
  -p, --path FOLDER     Folder for upload, containing data files and a special
                        kernel-metadata.json file. Defaults to current working directory
  -t, --timeout TIMEOUT Limit the run time of a kernel to the given number of seconds.
                        The global maximum time will not be exceeded.
  --accelerator ACC     Specify the type of accelerator to use for the kernel run
```

**Observed:** `push` supports `--accelerator ACC` and `-t/--timeout TIMEOUT`. It does **NOT** support `--no-run` — push always pushes code *and* runs the kernel. There is no "dry-run" push option. Also observed live: the kernel-metadata `title` must slugify to match the `id` suffix; otherwise push returns `409 Client Error: Conflict ... Your kernel title does not resolve to the specified id.` Set `title` to a value whose slug equals the kernel name (e.g. id `forts845/of-bridge-runner` with title `Of Bridge Runner`).

### `kaggle kernels status --help`

```
usage: kaggle kernels status [-h] [kernel]

kernel      Kernel URL suffix in format <owner>/<kernel-name>
            or <owner>/<kernel-name>/<version>
```

### `kaggle kernels output --help`

```
usage: kaggle kernels output [-h] [-p PATH] [-w] [-o] [-q]
                             [--file-pattern FILE_PATTERN]
                             [--page-size PAGE_SIZE] [--page-token PAGE_TOKEN]
                             [kernel]

-p, --path PATH      Folder where file(s) will be downloaded, defaults to CWD
-w, --wp             Download files to current working path
-o, --force          Skip check whether local version is up to date, force download
-q, --quiet          Suppress progress printing
--page-size PAGE_SIZE Number of items per page. Default 20, max 200
--page-token PAGE_TOKEN Page token for results paging.
```

### `kaggle kernels list --help`

```
usage: kaggle kernels list [-h] [-m] [--page-token PAGE_TOKEN]
                           [--page-size PAGE_SIZE] [-p PAGE] [-s SEARCH]
                           [-v | --format OUTPUT_FORMAT] [--parent PARENT]
                           [--competition COMPETITION] [--dataset DATASET]
                           [--user USER] [--language LANGUAGE]
                           [--kernel-type KERNEL_TYPE]
                           [--output-type OUTPUT_TYPE] [--sort-by SORT_BY]
-m, --mine            Display only my items
--page-size PAGE_SIZE Number of items per page. Default 20, max 200
--format OUTPUT_FORMAT csv, table, json
--language LANGUAGE   all, python, r, sqlite, julia (default all)
--kernel-type KERNEL_TYPE all, script, notebook (default all)
--sort-by SORT_BY     hotness, commentCount, dateCreated, dateRun, relevance, ...
```

**Status strings:** `status --help` does **not** enumerate the exact status strings. Observed live on `forts845/of-bridge-runner` (Milestone K1 step 4): `kernels status <slug>` returns a line of the form

    <owner>/<kernel-name> has status "KernelWorkerStatus.<STATUS>"

The only terminal status observed was `KernelWorkerStatus.COMPLETE` (the run completed during push, so it was COMPLETE at the first poll). Other statuses (e.g. `KernelWorkerStatus.RUNNING`, `KernelWorkerStatus.QUEUED`, `KernelWorkerStatus.ERROR`) are not yet observed — do not hard-code them; parse the `"KernelWorkerStatus.<STATUS>"` token generically and treat anything not explicitly `COMPLETE` as non-terminal unless it contains `error`/`fail`.

---

## Step 5 — Job protocol design

### 5.1 Job folder layout (per job)

Each Kaggle job is a folder pushed to the single private runner kernel:

```
jobs/<job_id>/
  job.json              # job descriptor (see schema below)
  kernel-metadata.json  # Kaggle kernel metadata for this push
  run.py                # runner entrypoint (reads job.json, renders, writes outputs)
```

`kernel-metadata.json` (Kaggle-required, per `https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels_metadata.md`):
- `id`: `<owner>/<runner-slug>` (the single private runner kernel)
- `title`: "OpenMontage runner"
- `code_file`: "run.py"
- `language`: "python"
- `kernel_type`: "script"
- `is_private`: true
- `enable_gpu`: true (per job if GPU required)
- `enable_internet`: false (see constraints)
- `dataset_sources`: []
- `competition_sources`: []

`job.json` schema:
```json
{
  "job_id": "string",
  "created_at": "ISO-8601 UTC",
  "voice": "kokoro",                 // TTS voice/engine selector
  "script": "string",                // narration text
  "audio": {                         // output contract
    "format": "wav",
    "sample_rate": 24000,
    "channels": 1,
    "manifest_required": true
  },
  "qc": {                            // QC gate config
    "tool": "tools/qa/qc.py",
    "thresholds": "config/qc_thresholds.json",
    "fail_closed": true
  },
  "resources": {                     // accelerator / session hints (UNVERIFIED)
    "accelerator": "gpu",            // or "cpu"; --accelerator value
    "timeout_seconds": 3600          // -t value (global max not exceeded)
  },
  "secrets": {                       // MUST be empty — nothing secret in kernel
    "note": "no secrets passed to kernel; Kaggle Secrets not settable via CLI"
  }
}
```

### 5.2 Output contract (per job)

The runner kernel writes, per job, exactly:

- `jobs/<job_id>/<job_id>.wav` — rendered narration audio (pcm_s16le, 24000 Hz mono, matching the pipeline convention from Milestone D2).
- `jobs/<job_id>/manifest.json`:
```json
{
  "job_id": "string",
  "sha256": "hex digest of the wav",
  "duration_seconds": "float",
  "sample_rate": 24000,
  "channels": 1,
  "library_versions": {
    "kokoro": "0.2.2",
    "torch": "2.14.1",
    "ffmpeg": "6.1.1"
  },
  "license_facts": {
    "kokoro_weights": "Apache-2.0",
    "kokoro_package": "Apache-2.0",
    "misaki_package": "Apache-2.0",
    "training_data_caveats": "CC BY items Koniwa/SIWIS; synthetic-data origin UNKNOWN"
  }
}
```

### 5.3 Bridge flow (orchestrator side)

1. **Serialize jobs** into `jobs/<job_id>/` folders locally.
2. **Push:** `kaggle kernels push -p jobs/<job_id> -t <timeout> --accelerator <acc>` to the single private runner kernel (`<owner>/<runner-slug>`, slug TBD).
3. **Poll with backoff + total timeout:** `kaggle kernels status <owner>/<runner-slug>` until status is terminal (`complete`/`error`/other live-observed string). Backoff between polls; hard wall-clock timeout equals `-t` plus a client-side total cap. On total-timeout -> fail-closed (see table).
4. **Output:** `kaggle kernels output <owner>/<runner-slug> -p <local_out> --file-pattern '<job_id>.*'` to fetch `job_id.wav` + `manifest.json`.
5. **Verify:** recompute sha256 of fetched wav; compare to `manifest.json` sha256; verify manifest fields (duration, sample_rate, channels, library_versions, license_facts). Hash mismatch -> fail-closed.
6. **QC:** run `tools/qa/qc.py` on the fetched wav; emit `qa_report.json` per QA_SPEC.md schema (job_id, check_id, status, evidence, measured_value, threshold, tool_version, timestamp).
7. **Result JSON:** write `<job_id>.result.json` summarizing push status, poll status, sha256 match, manifest validity, QC verdict.

### 5.4 Fail-closed table

| Failure | Detected how | Status | Action |
|---|---|---|---|
| auth failure | `kaggle` returns 401/403 or "Authentication required" | BLOCKED | owner must set `KAGGLE_API_TOKEN` secret; do not retry blindly |
| 409 / conflict | push rejected (kernel version conflict or duplicate) | BLOCKED | inspect `kernels status`/`output`; resolve slug/version before retry |
| queue / still running | `status` returns non-terminal (e.g. `queued`/`running` — UNVERIFIED strings) | REVIEW | continue polling with backoff; count toward total timeout |
| total timeout | client wall-clock cap exceeded before terminal status | BLOCKED | abort; do not treat partial output as success |
| error status | `status` returns terminal error (UNVERIFIED string) | FAILED | capture `kernels logs`/`output`; record evidence, do not proceed |
| empty output | `output` returns no files for the job | BLOCKED | treat as missing artifact; fail-closed |
| hash mismatch | recomputed sha256 != manifest.json sha256 | REJECT | do not run QC on mismatched artifact; fail-closed |
| manifest invalid | manifest.json missing/unenumerable/wrong fields | REJECT | fail-closed |
| QC failure | `tools/qa/qc.py` verdict != PASS | FAILED | emit qa_report.json; do not publish |

**Fail-closed rule:** any status not explicitly `PASS`/`complete` with verified sha256 and passing QC -> BLOCKED/FAILED/REJECT, never silently treated as success.

### 5.5 Constraints (mix of observed and UNVERIFIED)

- GPU quota: **30 h/week** (UNVERIFIED — K1 used CPU only).
- Session max: **12 h** per kernel run (UNVERIFIED; `-t` cannot exceed global max).
- Phone verification: may be required before GPU/internet (UNVERIFIED).
- Internet toggle: `enable_internet: false` **confirmed works** on a private CPU kernel (K1 step 4).
- Private kernel + serialized jobs: a single runner kernel processing jobs one at a time via `job.json` queue (UNVERIFIED that Kaggle permits this usage pattern; only one kernel was pushed in K1).
- Title/slug constraint: **confirmed** — push returns 409 if `title` does not slugify to the `id` suffix.

### 5.6 Secrets rule

- Nothing secret inside the kernel code or `job.json` (no API keys, tokens, credentials).
- Kaggle Secrets (kernel secrets) **cannot** be set via the CLI; if secrets are ever needed, they must be configured in the Kaggle UI by the owner — out of scope for K0/K1.
- The `KAGGLE_API_TOKEN` lives only in the Codespaces secret / orchestrator env, never in a pushed file.

### 5.7 Disk rule

After the bridge works end-to-end (K2), heavy packages (torch, kokoro, transformers) can be removed from the Codespace to free `/workspaces` disk (currently 3.2 GB free, 90% used). The bridge itself needs only `kaggle` CLI + `ffmpeg`/`ffprobe` + the QC tool.

---

## Step 6 — Proposed next milestones (no implementation now)

**K1 — Bridge code with tests (fake `kaggle` + live "hello" CPU job):**
- Implement `tools/qa/kaggle_bridge.py` (or similar) implementing §5.3 flow: serialize jobs, push, poll with backoff + total timeout, output, verify sha256/manifest, run `tools/qa/qc.py`, emit result JSON.
- Unit tests using a **fake `kaggle` executable on PATH** that simulates push/status/output behaviors (terminal statuses, error status, empty output, hash mismatch) — no network, no auth.
- One live "hello" CPU job (after `KAGGLE_API_TOKEN` is set): push a minimal kernel, poll, fetch output, verify.

**K2 — Kokoro job end-to-end:**
- A real job rendering narration via Kokoro-82M (installed in Milestone V) on the runner kernel, with `manifest.json` license facts, QC through `tools/qa/qc.py`, result JSON. Confirms GPU/accelerator path and 30 h/week quota behavior.

No implementation in K0; both are design proposals only.

---

## Step 6.5 — Live smoke job results (Milestone K1, observed)

**Kernel:** `forts845/of-bridge-runner` (private, CPU only, `enable_gpu=false`, `enable_internet=false`), created via `kaggle kernels push`.

**Push:** `kaggle kernels push -p jobs/hello-1 -t 3600 --accelerator cpu` → `Kernel version 1 successfully pushed.` Elapsed 2.4s. Requires `title` to slugify to the `id` suffix (else 409 Conflict).

**Status:** `kernels status forts845/of-bridge-runner` → `forts845/of-bridge-runner has status "KernelWorkerStatus.COMPLETE"`. COMPLETE at first poll after push (run completed during push). Single distinct status string observed.

**Output:** `kaggle kernels output forts845/of-bridge-runner -p <dest>` → `hello.txt` (6 bytes), `manifest.json` (186 bytes), `of-bridge-runner.log` (kernel log).

**Verify:** recomputed sha256 of `hello.txt` = `5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03` matches `manifest.json` sha256. Manifest fields: `job_id=hello-1`, `bytes=6`, `created_utc`, `python_version=3.13.15`.

**Verdict: PASS.**

Result JSON written to `/tmp/k1_result.json`.

---

## Step 7 — Observed vs assumed

**Observed:** kaggle.com/api.kaggle.com reachable (HTTP/2 404 on root = service up); kaggle CLI 2.2.4 installed (1.3 MB); `push` supports `--accelerator`/`-t` but not `--no-run`; `status` returns `<slug> has status "KernelWorkerStatus.<STATUS>"` (observed `KernelWorkerStatus.COMPLETE`); `output` downloads kernel output files; `list --mine` works with `KAGGLE_API_TOKEN` set; `--page-size` max 200; `/workspaces` 3.2 GB free. Live smoke job `forts845/of-bridge-runner` (CPU, no GPU/internet) pushed, ran COMPLETE, output fetched, sha256 verified → verdict PASS (result JSON at `/tmp/k1_result.json`). Title must slugify to the `id` suffix (else 409 Conflict). `enable_internet=false` confirmed works on a private CPU kernel.

**Assumed (not verified):** GPU 30 h/week; 12 h session max; phone verification; single-runner serialized-jobs pattern permitted by Kaggle (only one kernel pushed in K1). All other constraints still UNVERIFIED.

**Tests actually run:** 16 unit tests in `tests/tools/test_kaggle_bridge.py` (fake `kaggle`, no network) all pass; existing `tests/tools/test_qc_tool.py` (11) still pass. Live smoke job `forts845/of-bridge-runner` ran on real Kaggle (CPU).

**Budget / provider verification:** strict $0 held. pip install kaggle (PyPI, free). Kaggle API calls made via CLI with `KAGGLE_API_TOKEN` set (no token value logged/committed). No paid routes. No process/lock changes.

**Next smallest step:** proceed to K1/K2 per plan — K1 bridge code is complete; K2 = Kokoro job end-to-end.
