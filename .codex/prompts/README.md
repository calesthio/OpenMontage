# Codex custom prompts

Codex only scans **`~/.codex/prompts/`** (user home) for custom prompts — it does **not** read project-level `.codex/prompts/`. These files are versioned here as the source of truth; to use them in Codex, copy or symlink them into your home dir:

```bash
mkdir -p ~/.codex/prompts
cp .codex/prompts/ink-art.md .codex/prompts/animated-drawing.md ~/.codex/prompts/
# or symlink so repo edits propagate:
# ln -s "$PWD/.codex/prompts/ink-art.md" ~/.codex/prompts/ink-art.md
```

Then restart Codex; `/ink-art` and `/animated-drawing` appear in the `/` menu. (OpenAI is deprecating custom prompts in favor of Codex "skills" — migrate when that stabilizes.)
