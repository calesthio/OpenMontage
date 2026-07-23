# Contributing to OpenMontage

Thank you for improving OpenMontage. We do not require a Contributor License Agreement (CLA), Developer Certificate of Origin sign-off, or any separate contribution contract.

By submitting a pull request, you confirm that you have the right to contribute its contents. Contributions must be compatible with the repository's [AGPLv3 license](LICENSE), and accepted contributions remain available under that license.

Please keep pull requests focused and include tests when behavior changes.

## Before you start

1. Check the issue tracker for existing discussion and related pull requests.
2. Keep changes focused on one logical concern.
3. Read the project context before changing pipeline, tool, or skill behavior:
   - `AGENT_GUIDE.md`
   - `PROJECT_CONTEXT.md`
4. Avoid committing generated outputs, local renders, API keys, `.env`, virtual environments, or build artifacts.

## Local setup

OpenMontage requires Python 3.10 or newer, FFmpeg, Node.js 18 or newer, and npm.

```bash
git clone https://github.com/calesthio/OpenMontage.git
cd OpenMontage
make setup
```

For development dependencies only, run:

```bash
make install-dev
```

## Development workflow

Create a branch from `main`:

```bash
git checkout main
git pull
git checkout -b fix/descriptive-name
```

Use the repository conventions for the area you are changing:

- Tools live under `tools/` and should inherit from `tools/base_tool.py`.
- Pipeline definitions live under `pipeline_defs/`.
- Stage instructions live under `skills/pipelines/`.
- Artifact and tool schemas live under `schemas/`.
- Tests live under `tests/` and should cover behavior that changed.

## Checks

Run the smallest relevant check first, then the broader checks before opening a pull request.

```bash
make lint
make test-contracts
make test
```

`make lint` runs the current smoke checks used by CI. `make test` runs the full pytest suite.

If your change only touches documentation, still run at least:

```bash
make lint
git diff --check
```

## Pull requests

Before opening a pull request:

1. Make sure the diff contains only intentional files.
2. Link the related issue, for example `Closes #135`.
3. List the exact commands you ran in the Testing section.
4. Update README or docs when behavior, setup, or usage changes.

A good pull request is small, reproducible, and easy to review.
