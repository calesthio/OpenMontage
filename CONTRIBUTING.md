# Contributing to OpenMontage

Thank you for your interest in contributing to OpenMontage! This project is designed to be open, community-driven, and easy for contributors to get started with.

## Getting started

1. Fork the repository.
2. Clone your fork:

```bash
git clone https://github.com/<your-username>/OpenMontage.git
cd OpenMontage
```

3. Install dependencies:

```bash
make setup
```

If you do not have `make`, run:

```bash
python -m pip install -r requirements.txt
cd remotion-composer && npm install && cd ..
python -m pip install piper-tts
cp .env.example .env
```

4. Add any optional API keys you want to use to `.env`. Do not commit `.env` or any private secrets.

## Running checks

Run the standard lint and test suite before submitting changes:

```bash
make lint
make test
make test-contracts
```

If you make Python changes, `make lint` now runs `ruff`, `black --check`, and `mypy` across `lib/`, `tools/`, and `tests/`.

## Making changes

- Create a descriptive branch name: `git checkout -b fix/<short-description>` or `feature/<short-description>`.
- Keep changes focused and split large work into smaller PRs when possible.
- Update documentation when behavior changes.
- If your change affects providers, pipeline behavior, render workflows, or output paths, include an explanation of the expected runtime behavior.

## Submitting a pull request

1. Push your branch to your fork.
2. Open a pull request against `calesthio/OpenMontage` `main`.
3. In the PR description, include:
   - what problem the change fixes or what feature it adds
   - how to reproduce or validate the change
   - any relevant notes about provider configuration, required env vars, or runtime behavior

## Code review and CI

This repository uses GitHub Actions to run CI on pushes and pull requests to `main`.
The workflow installs dev dependencies and runs `make lint`, `make test`, and `make test-contracts`.

Please make sure your branch is up to date with `main` before requesting review.

## Need help?

- If you're unsure how to contribute, open a GitHub Discussion or issue first.
- For questions about architecture, provider behavior, or pipeline design, see `AGENT_GUIDE.md`, `PROJECT_CONTEXT.md`, and `docs/ARCHITECTURE.md`.
- If you want to help review provider or rendering PRs, see `docs/REVIEWER_GUIDE.md`.

## Notes

- Do not commit `.env` or other private keys.
- Use `git rebase main` or `git merge main` to keep your branch in sync before final review.
- Keep commit history clean and meaningful.
