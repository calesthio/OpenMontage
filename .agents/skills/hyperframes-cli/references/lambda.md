# lambda — Cloud Rendering on AWS Lambda

Deploy HyperFrames distributed rendering to AWS Lambda and drive renders from your laptop or CI. Wraps `@hyperframes/aws-lambda` SDK plus AWS SAM. End-to-end is three commands:

```bash
npx hyperframes lambda deploy
npx hyperframes lambda render ./my-project --width 1920 --height 1080 --wait
npx hyperframes lambda destroy
```

## When to Use Lambda vs Local Render

- **Local `render`** — dev-loop iteration, single host, anything under a few minutes at 1080p.
- **`lambda render`** — long videos, 4K, large parallel batches, or anything where local Chrome would time out / exhaust RAM. Pay-per-invocation, no idle cost.

For one-off short renders Lambda is not worth the deploy overhead.

## Prerequisites

- AWS credentials configured (env vars, `~/.aws/credentials`, SSO, or IMDS).
- AWS SAM CLI on `PATH`.
- `bun` on `PATH` (builds the Lambda handler ZIP).

## Subcommands

### deploy

```bash
npx hyperframes lambda deploy \
  --stack-name=hyperframes-prod \
  --region=us-east-1 \
  --concurrency=8 \
  --memory=10240
```

Builds `packages/aws-lambda/dist/handler.zip` and SAM-deploys the stack (Lambda + Step Functions + S3 + IAM). Idempotent — re-running on the same `--stack-name` is a no-op when nothing changed. Writes `<cwd>/.hyperframes/lambda-stack-<name>.json` so later subcommands don't need to call `describe-stacks`.

| Flag            | Default                         | Description                   |
| --------------- | ------------------------------- | ----------------------------- |
| `--stack-name`  | `hyperframes-default`           | CloudFormation stack name     |
| `--region`      | `AWS_REGION` env or `us-east-1` | AWS region                    |
| `--profile`     | `AWS_PROFILE` env               | Named AWS credentials profile |
| `--concurrency` | `8`                             | Lambda reserved concurrency   |
| `--memory`      | `10240`                         | Lambda memory in MB           |
| `--skip-build`  | off                             | Reuse existing `handler.zip`  |

### sites create

```bash
npx hyperframes lambda sites create ./my-project
# → siteId: abc1234deadbeef0  (stable across re-runs of the same tree)

npx hyperframes lambda render ./my-project --site-id=abc1234deadbeef0 ...
```

Tars + uploads `<projectDir>` to S3 with a content-addressed key. Returns a stable `siteId` you can reuse — re-renders of the same tree skip the upload.

### render

```bash
npx hyperframes lambda render ./my-project \
  --width 1920 --height 1080 --fps 30 --format mp4 \
  --chunk-size 240 --max-parallel-chunks 16 \
  --wait
```

Starts a Step Functions execution. Returns immediately with a `renderId` unless `--wait` is set, in which case the CLI blocks until completion and streams per-chunk progress lines. Add `--json` for machine-parseable output.

| Flag                    | Description                                                                                                                                                                                                                                                                                                                                                   |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--width` / `--height`  | Output dimensions in pixels                                                                                                                                                                                                                                                                                                                                   |
| `--output-resolution`   | Supersampling preset (engages Chrome `deviceScaleFactor`) — `landscape` / `landscape-4k` / `portrait` / `portrait-4k` / `square` / `square-4k`, plus aliases (`1080p`, `4k`, `uhd`, `hd`, `1080p-portrait`, `4k-portrait`, `1080p-square`, `4k-square`). Use this to render an authored-at-1080p composition at 4K without re-laying-out — see footgun below. |
| `--fps`                 | `24` / `30` / `60`                                                                                                                                                                                                                                                                                                                                            |
| `--format`              | `mp4` / `mov` / `png-sequence` (default `mp4`)                                                                                                                                                                                                                                                                                                                |
| `--codec`               | `h264` / `h265` (mp4 only)                                                                                                                                                                                                                                                                                                                                    |
| `--quality`             | `draft` / `standard` / `high`                                                                                                                                                                                                                                                                                                                                 |
| `--chunk-size`          | Frames per chunk (default `240`)                                                                                                                                                                                                                                                                                                                              |
| `--max-parallel-chunks` | Max concurrent chunks (default `16`)                                                                                                                                                                                                                                                                                                                          |
| `--site-id`             | Reuse an existing site (skip upload)                                                                                                                                                                                                                                                                                                                          |
| `--wait`                | Block until completion, stream progress                                                                                                                                                                                                                                                                                                                       |
| `--json`                | Machine-parseable progress snapshot                                                                                                                                                                                                                                                                                                                           |

**`--width` / `--height` footgun.** Setting `--width 3840 --height 2160` against a composition whose `data-width="1920"` silently produces 1080p — the runtime lays out the page at the composition's authored dimensions and the CLI flags are ignored for layout. To actually output at 4K, use `--output-resolution 4k` (supersamples via `deviceScaleFactor`). The CLI now prints a warning when CLI dimensions disagree with the composition's `data-width` / `data-height` and `--output-resolution` is not set; the warning is suppressed when `--json` is on or `index.html` isn't on disk (`--site-id` flows).

### progress

```bash
npx hyperframes lambda progress hf-render-abcd1234
npx hyperframes lambda progress arn:aws:states:us-east-1:...:execution:...
```

Prints one snapshot — overall percent, frames rendered, Lambda invocations, accrued cost, and any errors. Accepts a bare `renderId` (resolved against the stack's state-machine ARN) or a full SFN execution ARN.

### destroy

```bash
npx hyperframes lambda destroy
```

Calls `sam delete --no-prompts` and drops the local state file. **The render S3 bucket is configured `Retain`** so it survives stack destruction — empty + delete it via the AWS console / CLI if you want the storage back.

### Non-retryable errors

A subset of failures the Step Functions state machine short-circuits instead of running through its 4× 15-min retry budget. `progress` surfaces these immediately with the error class name; do not re-issue `lambda render` blindly when you see one.

- **`ChromeBinaryUnavailableError`** — `@sparticuz/chromium` returned an empty/missing executable path. A prior chunk hit `Sandbox.Timedout` mid-extraction and the warm instance is wedged until the execution environment recycles. Remedy: bump a Lambda env var (forces a new exec env) or `lambda deploy` again. Not a transient render failure; retries will burn budget on the same wedged instance.
- **`FFMPEG_VERSION_MISMATCH`** / **`PLAN_HASH_MISMATCH`** — planner / executor version drift. Re-deploy.

### policies

Print or validate the minimum IAM permissions the CLI needs.

```bash
npx hyperframes lambda policies user                                  # inline policy for an IAM user
npx hyperframes lambda policies role --principal=cloudformation       # { TrustRelationship, InlinePolicy }
npx hyperframes lambda policies validate ./infra/iam/hf-deploy.json   # CI gate
```

`validate` reads a JSON policy doc and checks the union of its `Effect: Allow` actions (expanding `s3:*` / `s3:Get*` / `*` wildcards) against the CLI's required action set. Missing actions print to stderr; the command exits non-zero. Wire it into CI to catch policy drift before the next deploy fails.

The default action set is deliberately broad (`Resource: "*"`) because CloudFormation creates new ARNs on every adopter's first deploy. Tighten `Resource` after that first run if security posture requires it.

## State Files

`hyperframes lambda` stores per-stack metadata under `<cwd>/.hyperframes/lambda-stack-<name>.json` (bucket name, state-machine ARN, region). Not secret, but AWS-account-identifying. Commit it to a repo or `.gitignore` it per your workflow.

## Cost and Cleanup

- `lambda destroy` removes the SAM stack but **leaves the S3 bucket** (`Retain`). Delete it manually if you want the storage back.
- Lambda billing is per-invocation + duration. `progress` reports the accrued cost.
- `--concurrency` caps parallel Lambda invocations — keep it aligned with your account quota.
- `--chunk-size` and `--max-parallel-chunks` trade off per-chunk overhead against parallelism; larger chunks reduce coordinator overhead, smaller chunks parallelize more aggressively.
