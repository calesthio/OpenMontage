# Kilo Code + OpenMontage Factory — master setup file

> **This is NOT `AGENTS.md` and does not replace your existing `AGENTS.md`.** Upload this file to the repository root as `KILO_CODE_YOUTUBE_FACTORY_MASTER.md`. It contains the two ZIP kits' setup instructions and embedded source resources. After uploading it, explicitly tell Kilo Code to read and execute this file.
>
> The existing root `AGENTS.md` must remain in place. Kilo should inspect it, preserve its content, and propose a small merge or a reference to this file only if needed.

## ACTIVE INSTRUCTIONS — APPLY THESE FIRST

### Mission
Improve the reliability of Kilo Code workflows and build/test the OpenMontage Factory YouTube production pipeline. Improve the workflow, project instructions, Skills, tools, tests and documentation; do not claim that the model itself is retrained or permanently learns new weights.

### Required startup behavior for every relevant task
1. Read the existing root `AGENTS.md` plus this `KILO_CODE_YOUTUBE_FACTORY_MASTER.md` when bootstrapping, then check the current repository, branch, README, Git status and architecture before edits.
2. Classify the task. Load only the Skills that are relevant; for factory work, use the orchestrator and the applicable research, rights, rendering, QA, publishing or self-improvement skill. Do not claim a Skill or MCP was used unless its contents were read or the tool actually ran.
3. If a project Skill does not exist yet, use its embedded resource below as the source of truth and materialize the corresponding `skills/<name>/SKILL.md` file on the first bootstrap task.
4. Before editing, inspect existing files, make timestamped backups outside generated/replaced folders, and use small reversible changes. Never overwrite unknown user content without comparing it first.
5. Run appropriate tests and report real `PASS`, `FAIL`, or `NOT_CHECKED` statuses. Do not invent command output or claim a test passed if it was not run.
6. Finish significant engineering tasks with: files changed, actual Skills/tools used, checks run and results, remaining limitations, and lessons/backlog items when evidence supports them.

### First-run bootstrap — perform when the user asks you to execute this file
This Markdown file is not automatically active just because it exists in the repository. When the user asks you to execute it, do not stop at summarizing the plan. Perform the following safe steps in this order:

1. **Preflight.** Confirm repo root and branch; inspect `git status`, project README and existing instructions/config. Identify OS and how Kilo is running if available. Never print tokens, passwords, cookies, `.env` contents or other secrets.
2. **Backup.** Before changing any existing instruction or Skill, write a timestamped backup outside the directory being replaced. Record backup paths in the setup report. Do not add backups or secrets to Git.
3. **Materialize embedded resources.** Recreate the project files listed under `## EMBEDDED KIT RESOURCES` at the exact relative paths shown in the resource headings, but only when this is useful to set up the factory and after checking whether a file already exists. If a file exists, compare it first and merge changes; never blindly replace user changes. Start with the two `AGENTS.md`/global-instructions source files, all nine Skill `SKILL.md` files, templates, improvement logs and setup documentation. Do not copy the installer script and run it blindly; inspect its commands and adapt to the current environment.
4. **Activate the rules without replacing existing instructions.** Keep the repository root `AGENTS.md` intact unless you have inspected it and made a timestamped backup. Create missing project Skill/resource files from the embedded payloads. If rules from this master file should become persistent, propose a small, non-duplicative merge into the existing `AGENTS.md` or add a concise reference to this master file; show the diff and preserve existing instructions. Do not edit global Kilo settings or replace `kilo.json`/`kilo.jsonc` just to make this file work. If global installation would help, prepare an exact change proposal and ask for approval before modifying global config.
5. **Verify Skills.** Check that all nine expected Skills exist and each `SKILL.md` has the expected `name`/`description` front matter. Ask Kilo to reload/rescan Skills only if the current Kilo version supports it. Distinguish “file exists” from “Skill was discovered/loaded”. If Skills cannot be auto-loaded yet, keep using the embedded skill instructions explicitly and state the limitation.
6. **Audit the factory.** Inspect the existing OpenMontage Factory implementation and compare it with the roadmap. Write or update `docs/architecture/current-state.md` and `docs/architecture/target-state.md` only after inspection. Identify one smallest end-to-end milestone.
7. **Run one safe vertical slice.** Prefer a local test video or fixture: job manifest → source/rights validation → edit plan → FFmpeg/ffprobe render if installed → technical QA report. Use synthetic/user-owned/public-domain or documented properly licensed assets. Never publish to YouTube as part of bootstrap.
8. **Report.** List actual paths, backups, files created/merged, detected Skills/MCP, commands run, honest `PASS`/`FAIL`/`NOT_CHECKED` statuses, blockers, and next action. If a needed tool or file is not available, do the safe parts and explain precisely what is missing.

### Safety and rights — non-negotiable
- Only use footage, audio, images and fonts that are user-owned, public domain, or covered by a documented license for the intended use. “Free download” and “royalty-free” are not proof by themselves.
- For each asset record source URL, creator, exact license/terms URL, retrieval date, attribution requirements, permitted commercial use, modification permission and local SHA-256 hash. Quarantine unclear rights for human review.
- Do not scrape YouTube videos as stock footage. Do not bypass DRM, paywalls, login/access controls, cookies, private content or platform restrictions.
- Never invent sources, facts, quotes, statistics, licensing evidence, test results or analytics.
- Never publish, schedule, delete videos or alter live channel settings without explicit approval in the current task. Keep OAuth/API secrets outside the repo/logs; use least privilege.
- Do not silently install third-party packages, MCP servers, plugins, global Skills or expand tool permissions. Inspect source, license, compatibility and risk; request approval before external installation, OAuth/API grants or permission changes.
- Do not run destructive shell commands. Use argument arrays rather than concatenating untrusted strings into shell commands. Validate paths, inputs and downloaded media sizes.

### YouTube production pipeline
Use explicit stages with inputs, outputs, status, errors, retry behavior, provenance and stable/resumable job IDs:
idea → research → outline/script → fact-check → asset plan → rights verification → edit decision list → render → technical/editorial QA → human review → upload preparation → human-approved publish → analytics → experiments.

Prefer modular adapters for research, asset providers, rights ledger, timeline/EDL, render backend, QA, YouTube API and analytics. Keep jobs resumable/idempotent where possible. Pin dependencies and record tool versions. Remotion is optional; review its current license and commercial terms before commercial use. YouTube APIs require explicit user-approved OAuth and quota/security review.

### Definition of done
A video is not complete unless the file exists and is non-empty; duration/resolution/frame rate/codec meet target; audio is present and checked; missing/black/frozen segments and unintended silence have been checked; captions/timing and factual claims are checked where applicable; title/thumbnail/description are not misleading; asset-rights records are complete; hashes and a QA report are saved. Mark any unrun check `NOT_CHECKED`, never `PASS`.

### Evidence-based self-improvement
- Record repeatable failures in `docs/agent-improvement/LESSONS.md` as observation → evidence → likely cause → proposed change. Do not include secrets or personal data.
- Put improvement ideas in `docs/agent-improvement/BACKLOG.md` with benefit, risk, priority and measurable verification.
- Keep fixed evaluation tasks in `docs/agent-improvement/EVALS.md`. Compare baseline and candidate behavior on the same tasks. Reject changes that reduce safety, correctness or stability even if they improve speed.
- Do not silently modify global instructions, tools, model settings, MCP config or permissions. Preserve an easy rollback and document accepted changes.

### Priority rules for the embedded materials
The resources below preserve the original ZIP contents. Treat them as **source files to materialize**, not as a requirement to locate the old ZIPs. If an embedded older README or prompt assumes the original ZIP folders exist or conflicts with the active instructions above, follow these active instructions and adapt the source safely to the current repository.

---

## EMBEDDED KIT RESOURCES

The following sections contain the resource files from the two ZIP kits. When creating a file, copy only the content inside its resource block to the exact path stated in the heading. Do not rename or overwrite the repository root `AGENTS.md`; merge applicable rules only after review. Do not include the surrounding Markdown fence in that target file.


### RESOURCE FILE: `01-kilo-self-improvement-kit/skills/kilo-self-improvement/SKILL.md`

`````markdown
---
name: kilo-self-improvement
description: Use when the user asks to improve Kilo Code, agent reliability, tool/skill usage, reduce context waste, create or update agent rules, analyze repeated failures, design evaluations, maintain an improvement backlog, or audit the coding-agent workflow.
license: MIT
---

# Kilo Self-Improvement

## Objective
Improve the coding-agent workflow through evidence-based changes to project instructions, Skills, MCP configuration, custom agents, test coverage, and documentation. Do not imply that the model weights are being trained.

## Workflow

1. **Inspect current state**: read `AGENTS.md`, project instructions, `kilo.jsonc`/`kilo.json` if present, installed Skills and MCP names, current Git status, tests, and any existing `docs/agent-improvement/` notes. Do not print secrets.
2. **Find evidence**: use concrete failed tasks, repeated user corrections, failed tests, tool failures, and known wasted context. Distinguish verified observations from hypotheses.
3. **Choose one bottleneck**: prioritize correctness and reliability first, then security, maintainability, latency, and token efficiency.
4. **Propose a minimal change**: name the file/config that would change, expected benefit, risk, rollback method, and a test that validates the claim. Avoid adding tools that duplicate existing capabilities.
5. **Baseline before changing**: record a few representative tasks and their pass/fail outcomes. When available, track test failures, tool calls, token/context usage, latency, and manual corrections. Never invent measurements.
6. **Implement in isolation**: use a branch or patch. Do not silently change global configuration, permission policies, credentials, or tool approvals.
7. **Evaluate**: rerun the same representative tasks and automated tests. Check for regressions and security changes.
8. **Keep/revert**: retain the change only if objective results improve without unacceptable trade-offs. Otherwise revert and record what was learned.
9. **Document**: update `docs/agent-improvement/LESSONS.md` and `BACKLOG.md`; include date, issue, evidence, change, result, and rollback/commit reference.
10. **Report honestly**: separate facts, hypotheses, and untested proposals. List actual tools/Skills used; never claim an MCP server was used when it was merely configured.

## Quality bar

A rule should be generalizable and precise. A Skill should solve a recurring task, explain when it applies, include examples and safe failure behavior, and be tested against at least two representative cases. A new MCP server should justify its context cost and overlapping functionality. Prefer fewer, reliable tools over a large uncurated collection.

## Suggested improvement records

### `LESSONS.md`
- Date / task:
- Observed failure and evidence:
- Confirmed cause / uncertainty:
- Fix or proposed rule:
- Regression test:
- Result:

### `BACKLOG.md`
- Item / priority:
- Problem evidence:
- Proposed change:
- Expected benefit:
- Risks and cost:
- Validation task:
- Status / rollback:
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/skills/README.md`

`````markdown
# Skills index

- `youtube-factory-orchestrator` — name: youtube-factory-orchestrator
- `youtube-research-and-scripting` — name: youtube-research-and-scripting
- `licensed-footage-audit` — name: licensed-footage-audit
- `video-pipeline-ffmpeg` — name: video-pipeline-ffmpeg
- `video-rendering-remotion` — name: video-rendering-remotion
- `youtube-quality-gate` — name: youtube-quality-gate
- `youtube-publishing-analytics` — name: youtube-publishing-analytics
- `youtube-factory-self-improvement` — name: youtube-factory-self-improvement
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/skills/licensed-footage-audit/SKILL.md`

`````markdown
---
name: licensed-footage-audit
description: Use whenever finding, importing, downloading, selecting, transforming or publishing video footage, audio, images, music, fonts or other media assets for YouTube. Mandatory for stock-footage pipelines and rights/provenance checks.
---
# Asset rights and provenance

## Allowed asset sources
Use user-owned material, public-domain material, or a source with explicit license terms that cover the planned use. Confirm whether commercial use, editing, redistribution, attribution and YouTube monetization are allowed.

## Required asset record
For each asset store:
- asset_id and local path
- source URL and creator/rights holder
- exact license name and terms URL
- access/retrieval date (UTC)
- commercial-use status and modification status
- attribution text and required notices
- checksum (SHA-256) and media metadata
- review status: VERIFIED / HUMAN_REVIEW / REJECTED
- evidence path (saved license page/screenshot/receipt when legally permitted)

## Rules
- Never infer rights from a search snippet or "free" label.
- Never use YouTube, TikTok or other creator uploads as stock without documented permission.
- Do not bypass DRM, paywalls, private links, cookies, authentication or site restrictions.
- Do not remove watermarks or metadata intended to identify ownership.
- If license text cannot be checked or commercial rights are ambiguous, quarantine and ask for review.
- Re-check license conditions when asset source or planned use changes.
- Keep music, sound effects, fonts, images and video on the same provenance ledger.
- Provide attribution in the final description where required.
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/skills/video-pipeline-ffmpeg/SKILL.md`

`````markdown
---
name: video-pipeline-ffmpeg
description: Use when implementing media ingestion, probing, transcoding, trimming, concatenation, audio mixing, subtitles, proxy creation, normalization, thumbnail extraction or batch video processing with FFmpeg/ffprobe.
---
# FFmpeg pipeline engineering

- Inspect installed `ffmpeg` and `ffprobe` versions before relying on a flag.
- Use `ffprobe -v error -show_streams -show_format -of json` to inspect input media.
- Normalize inputs to explicit profiles: resolution, pixel format, frame rate, codec, sample rate, channel layout and color handling.
- Prefer argument arrays in subprocess calls; never interpolate untrusted paths into a shell command.
- Make temporary outputs unique, write to a temp path, validate output, then atomically rename.
- Preserve source media; do not overwrite originals.
- Handle variable frame rate, rotation metadata, missing audio, odd dimensions, corrupt files and Unicode paths.
- Use explicit filters and stream maps; do not assume every input has audio or the same codec.
- Add timeouts, cancellation, structured stderr capture and bounded retries.
- Use ffprobe after render to validate duration, dimensions, frame rate, streams and codec.
- Record command, tool version, input/output hashes and exit code in a job report.
- Check FFmpeg build configuration and licensing obligations before redistributing binaries.
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/skills/video-rendering-remotion/SKILL.md`

`````markdown
---
name: video-rendering-remotion
description: Use when creating template-driven or data-driven video compositions, motion graphics, animated text, captions, title cards, branded layouts or batch rendering with Remotion and React.
---
# Remotion production workflow

- First confirm whether Remotion's license permits the intended commercial use; some use cases require a company license.
- Keep the composition deterministic: same input manifest and pinned dependencies should produce the same intended edit.
- Separate content data, scene components, styling, audio, subtitles and render configuration.
- Define schema validation for every video input JSON.
- Build a preview composition and render a short sample before batch rendering.
- Avoid loading untrusted remote URLs at render time; download approved assets and verify their rights records first.
- Use documented fonts and include font license records.
- Render to a temporary path, verify output with ffprobe and only then mark the job complete.
- Use concurrency limits based on available RAM/CPU/GPU; do not launch unbounded parallel renders.
- Record Remotion version, browser/runtime version, output profile and failures.
- Prefer FFmpeg-only rendering for simple cuts when it is sufficient; use Remotion when templating and animation justify the complexity.
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/skills/youtube-factory-orchestrator/SKILL.md`

`````markdown
---
name: youtube-factory-orchestrator
description: Use whenever planning, coding, debugging, extending or reviewing OpenMontage Factory or any automated YouTube video production pipeline. Coordinates specialist skills and enforces staged, resumable, licensed and human-approved workflows.
---
# YouTube Factory Orchestrator

1. Read project instructions and inspect the repository before proposing changes.
2. Explicitly load the relevant specialist Skills: research/script, footage rights, FFmpeg/rendering, QA, publishing/analytics, self-improvement.
3. Map the request to a pipeline stage and identify its input/output contracts.
4. Make a concise plan with files, tests, dependencies, rights/security implications and acceptance criteria.
5. Implement the smallest vertical slice; avoid broad rewrites.
6. Keep each job resumable and idempotent; use stable IDs, structured logs and manifests.
7. Use provider adapters rather than tightly coupling one asset source or renderer.
8. Never treat asset availability as a license. Route uncertain rights to human review.
9. Never publish or alter a live channel without explicit approval in the current task.
10. Finish with tests/results, skipped checks, risks and next step.

## Definition of done
A task is done only when acceptance criteria are tested or clearly marked NOT_CHECKED. Plans are not implementation. Mocked API tests are not proof of real API integration.
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/skills/youtube-factory-self-improvement/SKILL.md`

`````markdown
---
name: youtube-factory-self-improvement
description: Use after recurring bugs, failed renders, rights errors, slow jobs, high costs, poor QA, or whenever improving the OpenMontage Factory workflow, agent instructions, Skills, MCPs or architecture.
---
# Evidence-based factory improvement

1. Capture a reproducible example and sanitized logs.
2. Classify the failure: requirements, research, rights, asset download, timeline, rendering, QA, API, configuration or model/tool selection.
3. Record current behavior and metric in `docs/agent-improvement/LESSONS.md`.
4. Propose a small change in `docs/agent-improvement/BACKLOG.md` with expected benefit, risk, cost and rollback.
5. Add or update a regression test before changing behavior where practical.
6. Re-run the same benchmark task from `docs/agent-improvement/EVALS.md`.
7. Compare failure rate, human correction time, render time, cost per finished minute, rights coverage and output quality.
8. Do not claim improvement unless measured. If data is too small, say inconclusive.
9. Never silently install MCP servers/plugins, broaden permissions, change secrets, alter global config or publish videos.
10. Request human review for dependency/license changes, external services, permission changes, migrations or destructive actions.
11. Update docs only after the improvement passes tests; retain a changelog and rollback path.
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/skills/youtube-publishing-analytics/SKILL.md`

`````markdown
---
name: youtube-publishing-analytics
description: Use for YouTube Data API integration, upload manifests, title/description/tags/category/thumbnails/playlists, upload state management, quota handling, analytics ingestion, CTR and retention analysis, and controlled experiments.
---
# Publishing and analytics

## Publishing
- Prefer official YouTube Data API documentation and current API client libraries.
- Keep OAuth secrets outside the repository, logs and generated manifests.
- Use least-privilege scopes and document required permissions.
- Track API quota and rate limits; implement backoff and resumable uploads where supported.
- Default to draft or unlisted upload preparation. Public publishing requires explicit human approval in the current task.
- Do not auto-delete, mass-publish or modify live channel settings without explicit approval.
- Store title, description, thumbnail, language, category and visibility in a validated manifest.
- Keep states explicit: DRAFT, QA_PASSED, AWAITING_APPROVAL, UPLOADING, UPLOADED_UNLISTED, PUBLIC_APPROVED, FAILED.
- Never log tokens, authorization headers or private channel data.

## Analytics
- Distinguish impressions, click-through rate, views, average view duration, watch time and retention.
- Compare videos to the channel's own baseline and account for format, topic and publication age.
- Do not claim causal effects from a single video. Use controlled tests when possible.
- Avoid clickbait and spam tactics; optimize for viewer satisfaction and truthful packaging.
- Store data source, retrieval time, time window and API limitations.
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/skills/youtube-quality-gate/SKILL.md`

`````markdown
---
name: youtube-quality-gate
description: Use before declaring any generated video, Short, thumbnail, narration, subtitles, render pipeline or production job ready for review or publication.
---
# Technical and editorial QA

## Technical checks
- file exists, non-zero size and decodes;
- duration, dimensions, frame rate, codec, pixel format and audio streams match the target profile;
- inspect audio peaks/loudness and check clipping, silence and channel mismatch;
- detect unexpected black frames, frozen frames, missing clips and gaps;
- compare captions/subtitles against the final narration and timing;
- verify thumbnail dimensions, readability and image rights;
- verify final media checksums and job manifest.

## Editorial checks
- every factual claim has a source or is marked opinion/estimate;
- title and thumbnail match the actual video;
- no misleading promises, fabricated citations or synthetic evidence;
- asset rights ledger is complete and all assets are VERIFIED;
- description includes required attributions and disclosures;
- generated/synthetic content disclosures are evaluated against current platform rules.

## Report format
For each check use PASS, FAIL, or NOT_CHECKED with evidence and a brief explanation. Never mark a check PASS without running it. Block publication if a required check fails or asset rights are unresolved. Human review is still required before public publication.
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/skills/youtube-research-and-scripting/SKILL.md`

`````markdown
---
name: youtube-research-and-scripting
description: Use for YouTube niche research, topic selection, source-backed research, outlines, scripts, hooks, title and thumbnail concepts, fact-checking, retention structure, and transforming research into a production-ready narration.
---
# Research and scripting workflow

- Start with audience, channel promise, target format, length, language, and source requirements.
- Separate sourced facts, interpretations, estimates and creative framing.
- Use primary/official sources for factual claims when practical; store source URLs and publication dates.
- Do not invent numbers, quotations, citations or claims. If a fact is unverified, qualify it or remove it.
- Create: brief, source ledger, outline, script, pronunciation notes, visual beat sheet, title/thumbnail pairing and description draft.
- Hooks must make a truthful promise that the video actually fulfils; avoid misleading clickbait.
- Add a visual cue every meaningful beat, but do not force irrelevant footage merely to keep motion.
- Design for retention through clarity, narrative progression, concrete examples and pacing, not deceptive loops.
- Keep the creator's voice and channel style in a versioned voice profile.
- For title/thumbnail review, assess them together for promise alignment, legibility and non-duplication.
- Before handoff, run a claim-to-source audit and flag claims requiring human review.
`````

### RESOURCE FILE: `01-kilo-self-improvement-kit/AGENTS.global.md`

`````markdown
<!-- KILO_SELF_IMPROVEMENT_BEGIN -->
# Kilo Code — постоянный рабочий протокол

## 1. Перед началом каждой задачи

1. Классифицируй задачу: вопрос/исследование, архитектура, код, отладка, тесты, документация, UI/browser, GitHub, либо улучшение самого рабочего процесса.
2. Просмотри доступный список Skills. Выбери все Skills, которые явно применимы, и загрузи их `SKILL.md` до выполнения соответствующей работы. Для изменений кода минимум проверь навыки планирования/кодирования/тестирования, если они доступны. Не загружай все Skills подряд: загружай релевантные, чтобы не переполнять контекст.
3. Если подходящий Skill есть, но не удалось загрузить его, сообщи об этом и продолжай только безопасным запасным способом. Не утверждай, что использовал Skill/MCP, если реального вызова не было.
4. Для неизвестных или быстро меняющихся API/библиотек предпочитай актуальную документацию (например, Context7, если он подключён). Для большого репозитория сначала используй структурированный поиск/символы (например, jCodeMunch или Serena, если подключены), а не открывай десятки больших файлов целиком. Для UI-тестов используй Playwright MCP, только если он подключён и применим.
5. Перед многофайловой/рискованной задачей сформулируй короткий план, критерии готовности и нужные проверки. Для небольшой задачи не превращай процесс в бюрократию.

## 2. Во время работы

- Изучай действующую архитектуру и локальные соглашения до правок; не переизобретай уже имеющиеся решения.
- Делай небольшие обратимые изменения. Не удаляй пользовательские данные, не запускай разрушительные команды и не меняй глобальные настройки без явного разрешения.
- MCP и Skills — подсказки и инструменты, а не доказательство корректности. Проверяй фактический результат тестами, линтером, typecheck, браузерным прогоном или другим подходящим способом.
- Если инструмент не подключён/недоступен, не имитируй его результат. Отметь ограничение и предложи минимальный резервный путь.
- Для внешних утверждений, новых зависимостей, API и текущей документации проверяй официальные источники, когда это существенно.

## 3. После каждой задачи с изменениями

1. Запусти подходящие проверки и честно укажи, что прошло, что не запускалось и почему.
2. Кратко перечисли реально загруженные Skills и реально использованные MCP-инструменты. Если релевантный Skill не использован, объясни почему.
3. Если возник повторяющийся сбой, была исправлена ошибка после замечания пользователя, тесты выявили регрессию или инструмент оказался неэффективным, добавь короткую запись в проектный файл `docs/agent-improvement/LESSONS.md` (создай каталог/файл при необходимости): наблюдение → причина, подтверждённая данными → изменение, которое стоит проверить. Не записывай секреты и персональные данные.
4. Добавь потенциальные улучшения в `docs/agent-improvement/BACKLOG.md`, указав проблему, ожидаемую пользу, риск, способ проверки и приоритет. Не меняй глобальные инструкции или общие Skills автоматически на основании одного случая.

## 4. Безопасный цикл самоулучшения

- Раз в несколько задач (или по прямому запросу) анализируй `LESSONS.md`, `BACKLOG.md`, тестовые результаты и историю изменений.
- Предлагай улучшение только тогда, когда проблема воспроизводима или есть объективные данные. Создавай отдельную ветку/patch, если проект использует Git.
- До внедрения опиши ожидаемый эффект и тест, который может доказать или опровергнуть улучшение.
- Прогони набор контрольных задач до и после изменения. Не принимай изменение, если оно ухудшило корректность, безопасность или стабильность, даже если ускорило работу.
- Изменения глобального `AGENTS.md`, настроек MCP, прав инструментов, моделей и сторонних плагинов сначала показывай пользователю на review. Не применяй их тихо.
- Сохраняй откат: коммит/patch или резервная копия. Документируй причину и результат.

## 5. Формат завершения

В конце заметной инженерной задачи укажи:
- результат;
- Skills, которые действительно использованы;
- MCP/инструменты, которые действительно использованы;
- выполненные проверки и их результат;
- незавершённые риски/ограничения;
- урок или пункт backlog, если он действительно появился.

## 6. Ограничения

- Не обещай постоянное обучение модели: улучшай только конфигурацию, процедуры, Skills, тесты и документацию проекта.
- Не используй все Skills/MCP в каждом запросе. Выбирай релевантные, иначе лишние инструменты увеличат контекст и риск.
- Не считай MCP подключённым лишь потому, что его конфигурация есть в файле: проверь реальную доступность его инструментов.
- Никогда не помещай токены, API-ключи и пароли в исходники, правила, логи или коммиты.
<!-- KILO_SELF_IMPROVEMENT_END -->
`````

### RESOURCE FILE: `01-kilo-self-improvement-kit/KILO_SELF_IMPROVEMENT_PLAN.md`

`````markdown
# План самоулучшения Kilo Code

## Цель
Сделать Kilo Code более последовательным: правильно выбирать Skills и MCP, исследовать репозиторий без лишнего чтения, проверять результат, сохранять повторяющиеся уроки и менять свои рабочие правила только после тестов.

## Архитектура цикла

**Задача → классификация → релевантный Skill → нужные инструменты → реализация → тесты → урок/метрика → предложение улучшения → регрессионная проверка → review/откат.**

Это улучшает workflow агента, а не веса самой языковой модели. Kilo не должен автоматически переписывать глобальные инструкции после одной ошибки.

## Этап 1 — Зафиксировать исходный уровень

1. Сохранить Git status и резервную копию текущих `AGENTS.md`, `kilo.jsonc`/`kilo.json`, правил и Skills.
2. Выбрать 5 одинаковых контрольных задач: маленькое исправление бага, изменение в нескольких файлах, поиск в большой кодовой базе, работа с неизвестным API, тест/проверка UI (если применимо).
3. Зафиксировать pass/fail, найденные регрессии, число ручных поправок, время, инструментальные вызовы и токены/стоимость только там, где они реально доступны.
4. Не оптимизировать по одному впечатлению: сохранить результаты, чтобы сравнивать «до» и «после».

## Этап 2 — Сделать постоянные инструкции

1. Установить глобальный `AGENTS.md` из комплекта.
2. Убедиться, что в используемом агенте нет более приоритетного Role Definition / agent prompt, который противоречит этим правилам. Короткое требование «проверить доступные Skills и загрузить релевантный перед работой» продублировать в Role Definition основного агента, если ваша версия поддерживает отдельный prompt.
3. Поместить общие Skills в `~/.kilo/skills/` (или `~/.agents/skills/`, если выбрана эта стандартная директория). Для конкретного репозитория держать проектные Skills в `.kilo/skills/`.
4. Перезапустить Kilo и проверить реальную загрузку Skill через инструментальный вызов/список Skills, а не принимать общее «да, я знаю правила» за доказательство.

## Этап 3 — Установить небольшой основной стек

Начать с 3–5 компонентов, не с 20:

1. **Официальные Kilo Skills** — повторяемые workflow.
2. **Superpowers MCP** — планирование, тесты, системная отладка; использовать явную установку для Kilo из README проекта.
3. **Context7** — актуальная документация библиотек/SDK.
4. **Один инструмент структурированного поиска кода**: `jCodeMunch` для поиска символов с минимальной выдачей либо `Serena` для семантической навигации/редактирования. Не подключать оба в первый день без доказанной необходимости.
5. **Playwright MCP** — только если проект содержит браузерный интерфейс или нуждается в browser automation.
6. **GitHub MCP** — если агент реально работает с issues/PRs/actions; задавать минимальные токен-права.

После установки проверять доступность каждого сервера в панели MCP и тестовым запросом. Отключать сервис, если он не используется или сильно увеличивает контекст.

## Этап 4 — Разделить роли, если сложность оправдана

Создать отдельные агенты/режимы для:

- Architect / Planner: выясняет требования, перечисляет файлы и риски, пишет план, не делает лишних изменений.
- Coder: вносит минимальный патч, следует локальным соглашениям.
- Tester / Reviewer: независимо ищет ошибки, запускает тесты и проверяет края.
- Researcher: исследует официальную документацию и проверяет версии API.
- Skill Maintainer: предлагает обновления Skills/AGENTS и добавляет regression cases.

Для малых задач не запускать всю команду. Указания делегирования поместить не только в `AGENTS.md`, но и в Role Definition/agent prompt, где это поддерживается: поведение делегирования зависит от модели и сборки.

## Этап 5 — Ввести журнал уроков

Хранить в самом проекте:

- `docs/agent-improvement/LESSONS.md` — только подтверждённые повторяющиеся проблемы/результаты.
- `docs/agent-improvement/BACKLOG.md` — предложения с приоритетом, ожидаемой пользой, риском и критерием успеха.
- `docs/agent-improvement/EVALS.md` — одинаковые контрольные задачи и результаты запусков.

Не записывать секреты и персональные данные. Не превращать разовую ошибку в постоянное правило без подтверждения.

## Этап 6 — Протокол изменения самого себя

Для каждого кандидата на улучшение:

1. Сформулировать гипотезу («не использует Skill X»), не выдавая её за установленный факт.
2. Найти воспроизводимый пример и исходный замер.
3. Создать небольшой patch в ветке/копии.
4. Запустить минимум две контрольные задачи, включая одну, где Skill не должен применяться.
5. Убедиться, что улучшилась точность/надёжность и не выросли опасные разрешения/ошибочные правки. Токены оптимизировать вторично.
6. Показать diff и результаты пользователю для глобальных правил, MCP-конфига и политик разрешений.
7. Принять изменения только после review; иначе откатить.

## Этап 7 — Периодический аудит

По запросу или раз в неделю, когда вы работаете над проектом:

- проверить новые версии Kilo и совместимость MCP/Skills;
- просмотреть список backlog и последние ошибки;
- обновить только один-два наиболее полезных элемента;
- повторить EVALS;
- удалить неиспользуемые MCP, устаревшие Skills и дублирующие инструменты.

Для настоящего автоматического запуска по расписанию потребуются локальная задача/CI/планировщик. Сам `AGENTS.md` не запускает Kilo по расписанию.

## Критерии успеха через 2–4 недели

- больше контрольных задач заканчиваются с проходящими проверками;
- уменьшается число повторных замечаний по одной и той же ошибке;
- снижается доля «инструмент подключён, но недоступен/не использован»;
- Skills применяются по назначению, но не загружаются бессмысленно все вместе;
- любое постоянное изменение инструкций имеет тест, объяснение и путь отката.
`````

### RESOURCE FILE: `01-kilo-self-improvement-kit/MCP_SNIPPETS.md`

`````markdown
# Примеры MCP для Kilo Code (не вставляйте целиком поверх существующего config)

Современная конфигурация Kilo использует объект верхнего уровня `mcp` в `~/.config/kilo/kilo.jsonc` (глобально) или `kilo.jsonc`/`.kilo/kilo.jsonc` внутри проекта. Сначала сделайте резервную копию и объедините блоки с вашим существующим файлом, не заменяя его.

## Context7 (удалённый endpoint)

```jsonc
{
  "mcp": {
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp",
      "enabled": true
    }
  }
}
```

Если в файле уже есть `mcp`, добавьте только объект `context7` внутрь существующего объекта. Проверьте актуальные требования/лимиты Context7 на момент использования.

## Superpowers MCP

Вместо ручного копирования конфигурации используйте установочный сценарий, который указал автор репозитория:

```bash
npx -y superpowers-mcp setup --target kilo
```

Перед запуском проверьте README и команду через `--help`, если этот флаг есть в установленной версии. После установки перезапустите Kilo и убедитесь, что MCP-инструменты появились в панели.

## jCodeMunch MCP — пример, не универсальный конфиг

В репозитории есть интерактивный setup/команда `jcodemunch-mcp init`. Сначала проверьте актуальный README, лицензионные условия (в README заявлено бесплатное личное использование; для коммерческой работы действуют иные условия) и то, что он поддерживает вашу текущую сборку Kilo. Не копируйте конфигурацию от Claude Code/Cursor без адаптации к схеме Kilo.

## GitHub MCP / Playwright MCP / Exa MCP

Настраивать по официальному README репозитория и текущему MCP-разделу Kilo. GitHub и Exa могут требовать credentials/API key; храните их в переменных окружения/защищённых настройках, не в Git. Playwright требует локального браузерного окружения. Не добавляйте секреты непосредственно в project `kilo.jsonc`.

## Windows

Для локальных stdio-серверов в некоторых Windows-конфигурациях Kilo рекомендует вызывать shell через `cmd /c`, потому что `npx` напрямую может не находиться. Сверяйтесь с текущей страницей официальной документации Kilo и конфигурацией конкретного сервера.
`````

### RESOURCE FILE: `01-kilo-self-improvement-kit/PROMPT_FIRST_RUN.md`

`````markdown
Прочитай `AGENTS.md`, глобальный Skill `kilo-self-improvement`, а также `KILO_SELF_IMPROVEMENT_PLAN.md` и `REPOSITORY_SHORTLIST.md` из распакованного комплекта.

Сначала выполни аудит без опасных изменений:
1. Проверь, какие инструкции и Skills реально загружены; назови точные имена и пути. Проверь наличие `kilo-self-improvement`.
2. Перечисли подключённые и реально доступные MCP-инструменты; не считай инструмент доступным только потому, что он упомянут в конфиге.
3. Проверь версию Kilo/тип окружения и существующий `kilo.jsonc`, но не раскрывай секреты и не перезаписывай его.
4. Составь текущую карту правил, Skills, MCP, тестов и потенциальных конфликтов путей (например, старый `.kilocode` против актуального `.kilo`).
5. Создай в текущем проекте `docs/agent-improvement/LESSONS.md`, `BACKLOG.md` и `EVALS.md`, если их ещё нет. Не создавай глобальные файлы без моего явного разрешения.
6. Предложи этапный план внедрения в порядке наибольшей пользы при наименьшем риске/стоимости. Укажи, что реально подтверждено, что ещё надо проверить.
7. Для первого этапа подготовь конкретный diff, но не подключай новые серверы, не меняй права и не устанавливай сторонний код без отдельного подтверждения.

В конце предложи 5 контрольных задач и критерии pass/fail, чтобы сравнивать качество до и после улучшений.
`````

### RESOURCE FILE: `01-kilo-self-improvement-kit/README_RU.md`

`````markdown
# Kilo Code: набор для постоянного использования Skills и самоулучшения

Этот комплект настраивает устойчивый процесс улучшения самого рабочего процесса Kilo Code: глобальные инструкции, навык-маршрутизатор, журнал уроков, очередь улучшений и контрольные проверки. Он **не меняет веса модели** и не делает Kilo автономно обучающейся моделью; он помогает улучшать инструкции, Skills, тесты и инструменты между задачами.

## Что находится в архиве

- `AGENTS.global.md` — глобальные правила, которые нужно загрузить в Kilo на всех проектах.
- `skills/kilo-self-improvement/SKILL.md` — навык для планирования и проверки улучшений.
- `KILO_SELF_IMPROVEMENT_PLAN.md` — этапы внедрения, метрики и цикл улучшений.
- `REPOSITORY_SHORTLIST.md` — подборка репозиториев, MCP, Skills и утилит с пометками о совместимости/стоимости.
- `MCP_SNIPPETS.md` — безопасные примеры конфигурации; не заменяют и не перезаписывают ваш `kilo.jsonc`.
- `PROMPT_FIRST_RUN.md` — первый запрос, который можно вставить в Kilo после установки.
- `install-windows.ps1` и `install-unix.sh` — идемпотентные установщики; создают резервную копию существующего `AGENTS.md`, добавляют управляемый блок и копируют Skill.

## Установка на Windows

1. Распакуйте архив.
2. Откройте PowerShell в распакованной папке.
3. Запустите:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
   ```

   Скрипт работает в профиле текущего пользователя, не требует администратора, не устанавливает MCP и не меняет `kilo.jsonc`.
4. Полностью перезапустите Kilo Code / VS Code.
5. Вставьте текст из `PROMPT_FIRST_RUN.md` в чат Kilo и проверьте, что он видит навык `kilo-self-improvement`.

## Установка на Linux/macOS

Из распакованной папки:

```bash
chmod +x ./install-unix.sh
./install-unix.sh
```

Затем перезапустите Kilo Code и выполните первый запрос из `PROMPT_FIRST_RUN.md`.

## Где установится

- Глобальные инструкции: `~/.config/kilo/AGENTS.md`.
- Глобальный Skill: `~/.kilo/skills/kilo-self-improvement/SKILL.md`.
- Предыдущий `AGENTS.md`, если он был, сохранится как резервная копия с временной меткой.

Пути соответствуют текущей документации Kilo; в старых сборках/legacy-расширении могут использоваться старые пути. Если ваша версия не обнаруживает Skill, смотрите `REPOSITORY_SHORTLIST.md` и официальную документацию Skills.

## Важно

Этот комплект не устанавливает сторонние расширения и не даёт им права запуска. Сначала проверьте источник и права каждого MCP/плагина. Не разрешайте все инструменты без разбора, не помещайте API-ключи в Git и не позволяйте агенту незаметно переписывать собственные глобальные инструкции.
`````

### RESOURCE FILE: `01-kilo-self-improvement-kit/REPOSITORY_SHORTLIST.md`

`````markdown
# Подборка репозиториев и инструментов для Kilo Code

Проверено по открытым README/документации и обсуждениям на 17 октября 2026 года. «Бесплатно» означает бесплатный код/базовое использование, если отдельно не сказано обратное; модель, API и вычисления могут быть платными. Совместимость с MCP-протоколом не всегда означает официальную интеграцию Kilo — настройку нужно проверить в своей версии.

## Начать с этих пяти

| Приоритет | Проект | Что даёт | Цена / оговорка | Ссылка |
|---|---|---|---|---|
| 1 | Kilo Marketplace | Каталог Skills, MCP, агентов и плагинов для экосистемы Kilo | Сам каталог открыт; каждый сторонний компонент отдельно проверяйте | https://github.com/Kilo-Org/kilo-marketplace |
| 2 | Официальные Kilo Skills | Стандартные повторяемые workflows для разработки и AI-задач | Open source; устанавливать все или только конкретный skill | https://github.com/Kilo-Org/skills |
| 3 | Superpowers MCP (Kilo target) | Planning, brainstorming, TDD, отладка и выполнение планов через MCP | Репозиторий доступен бесплатно; вызовы LLM могут стоить денег | https://github.com/Poseidoncode/superpowers-mcp |
| 4 | Context7 | Актуальная/version-specific документация библиотек и SDK | Hosted endpoint есть в официальном примере Kilo; квоты/ключ могут зависеть от сервиса | https://github.com/upstash/context7 |
| 5 | jCodeMunch MCP | Структурный поиск по символам, чтобы получать нужные функции вместо больших файлов | README указывает free personal use; коммерческое использование имеет лицензионные условия. Экономия токенов в README — benchmark автора, не гарантия | https://github.com/jgravelle/jcodemunch-mcp |

## Ещё полезные репозитории

| # | Проект | Когда пригодится | Совместимость и ограничения | Ссылка |
|---:|---|---|---|---|
| 6 | Serena | Семантическая навигация, извлечение символов, правки и рефакторинг | MCP-совместимый инструмент; проверьте рекомендуемую установку в README, не берите старые marketplace-команды | https://github.com/oraios/serena |
| 7 | GitHub MCP Server | Работа с репозиториями, issue, PR и CI из агента | Официальный server, но для авторизованных действий нужен GitHub token с минимальными правами | https://github.com/github/github-mcp-server |
| 8 | Playwright MCP | Реальное управление браузером, проверка страниц и UI-потоков | Open source; нужна локальная/browser-среда. Подключать только для задач, где нужен браузер | https://github.com/microsoft/playwright-mcp |
| 9 | Exa MCP Server | Поиск в интернете и обход страниц для исследований | Требует API/квоты; не считать безлимитным бесплатным | https://github.com/exa-labs/exa-mcp-server |
| 10 | Repomix | Пакует кодовую базу в единый файл для разового анализа/рефакторинга | Бесплатный open-source CLI, не MCP; не отправлять наружу секреты и большие частные репозитории без проверки | https://github.com/yamadashy/repomix |
| 11 | GitNexus | Граф зависимостей/вызовов и индекс кодовой базы | Полезен большим проектам; в опубликованной таблице интеграций Kilo явно не перечислен — потребуется ручная MCP-настройка и проверка | https://github.com/johnman/gitnexus |
| 12 | Skiller | Синхронизация Skills/rules для нескольких coding agents | Его актуальная таблица всё ещё показывает некоторые legacy-пути `.kilocode`; проверьте, что файлы попали в активные пути вашей версии Kilo, а не полагайтесь на установку вслепую | https://github.com/udecode/skiller |
| 13 | Ruler / agent-rules | Общие правила и распространение настроек между агентами | В проекте написано, что Skills support экспериментальный; не делать основой системы без проверки результата | https://github.com/acumenix/agent-rules |
| 14 | Model Context Protocol servers | Эталонные/полезные серверы: Fetch, Filesystem, Git и др. | В репозитории есть архивированные компоненты; выбирайте конкретный поддерживаемый сервер, а не устанавливайте всё подряд | https://github.com/modelcontextprotocol/servers |
| 15 | Kilo Context Condensing docs | Управление auto-compaction/pruning, чтобы длинные чаты не забивали контекст | Уже встроенная функция Kilo; проверьте настройки `compaction.auto` и `compaction.prune` | https://kilo.ai/docs/customize/context/context-condensing |
| 16 | Kilo custom instructions | Глобальные `AGENTS.md` и инструкции на все проекты | Это не плагин — базовый механизм постоянных правил. Глобальный путь для Kilo: `~/.config/kilo/AGENTS.md` | https://kilo.ai/docs/customize/custom-instructions |
| 17 | Kilo custom agents / modes | Разделить роль планировщика, кодера, тестировщика, ревьюера | Предпочитать современные agent Markdown files; не смешивать с legacy `custom_modes.yaml` без проверки версии | https://kilo.ai/docs/customize/custom-modes |
| 18 | Kilo Plugins docs | Создание/подключение плагинов, хуков, custom tools и изменяемого поведения runtime | Плагины запускают код с правами пользователя: изучать исходники и permissions до установки | https://kilo.ai/docs/automate/extending/plugins |

## Форумы и community-сигналы

- Обсуждение о Skills/rules: один пользователь сообщает, что Kilo иногда подтверждает правила словами, но фактически не применяет их; совет сообщества — использовать общепринятый `AGENTS.md` и явно перечислять Skill triggers. Это единичные сообщения, а не систематический бенчмарк: https://www.reddit.com/r/kilocode/comments/1soyghb/kilo_code_project_rules_skills/.
- Обсуждение делегирования custom agents: пользователь сообщает, что инструкции в `AGENTS.md` сами по себе не заставляли модель переключаться; совет — держать короткие If/Then правила также в Role Definition конкретного агента и делать `whenToUse` описания отличимыми: https://www.reddit.com/r/kilocode/comments/1ra56h3/agents_not_switching_to_custom_modes_in_kilo/.
- В сообществах повторяется тема ненужного чтения крупных файлов; jCodeMunch даёт структурированный retrieval, но его эффект зависит от того, использует ли агент инструменты вместо brute-force чтения: https://github.com/jgravelle/jcodemunch-mcp.

## Рекомендуемый минимальный набор

1. **Всем проектам:** глобальный `AGENTS.md` + официальный Kilo Skills.
2. **Большие кодовые базы:** выбрать **либо jCodeMunch, либо Serena** сначала; сравнить их на нескольких одинаковых задачах.
3. **Новые/неизвестные API:** Context7.
4. **Тесты веб-интерфейса:** Playwright MCP.
5. **Работа с PR/issues:** GitHub MCP с минимальными правами.
6. **Разработка по строгому процессу:** Superpowers MCP.
7. Exa, GitNexus, Skiller, Ruler и прочие добавлять, только если есть конкретная задача, и после проверки совместимости.

## Важная разница

- **Skill** учит процедуре и подгружается по релевантности.
- **MCP** предоставляет вызываемый инструмент; наличие в конфиге не значит, что модель вызвала его.
- **Plugin/hook** способен влиять на runtime и лучше подходит для механического enforcement, но имеет самый высокий риск и должен тестироваться отдельно.
- **AGENTS.md / agent prompt** — слой постоянных инструкций. Он не гарантирует идеального следования каждой модели, поэтому добавляйте видимую проверку и контрольные задачи.
`````

### RESOURCE FILE: `01-kilo-self-improvement-kit/install-unix.sh`

`````bash
#!/usr/bin/env sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
GLOBAL_DIR="$HOME/.config/kilo"
AGENTS="$GLOBAL_DIR/AGENTS.md"
SKILL_DIR="$HOME/.kilo/skills/kilo-self-improvement"
SKILL_DEST="$SKILL_DIR/SKILL.md"
BEGIN='<!-- KILO_SELF_IMPROVEMENT_BEGIN -->'

mkdir -p "$GLOBAL_DIR" "$SKILL_DIR"
if [ -f "$AGENTS" ]; then
  STAMP="$(date +%Y%m%d-%H%M%S)"
  cp -p "$AGENTS" "$AGENTS.bak-$STAMP"
  if grep -Fq "$BEGIN" "$AGENTS"; then
    echo 'Managed instruction block already exists; left it unchanged.'
  else
    printf '\n\n' >> "$AGENTS"
    cat "$ROOT/AGENTS.global.md" >> "$AGENTS"
    echo "Added global instructions: $AGENTS"
  fi
else
  cp "$ROOT/AGENTS.global.md" "$AGENTS"
  echo "Created global instructions: $AGENTS"
fi
cp "$ROOT/skills/kilo-self-improvement/SKILL.md" "$SKILL_DEST"
echo "Installed Skill: $SKILL_DEST"
echo 'Done. Restart Kilo Code and follow PROMPT_FIRST_RUN.md.'
echo 'No MCP server was installed and kilo.jsonc was not modified.'
`````

### RESOURCE FILE: `01-kilo-self-improvement-kit/install-windows.ps1`

`````powershell
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$globalDir = Join-Path $HOME '.config\kilo'
$agentsPath = Join-Path $globalDir 'AGENTS.md'
$skillSource = Join-Path $root 'skills\kilo-self-improvement\SKILL.md'
$skillDir = Join-Path $HOME '.kilo\skills\kilo-self-improvement'
$skillDest = Join-Path $skillDir 'SKILL.md'
$begin = '<!-- KILO_SELF_IMPROVEMENT_BEGIN -->'

New-Item -ItemType Directory -Force -Path $globalDir | Out-Null
New-Item -ItemType Directory -Force -Path $skillDir | Out-Null

if (Test-Path $agentsPath) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    Copy-Item $agentsPath "$agentsPath.bak-$stamp"
    $current = Get-Content -Raw -Encoding UTF8 $agentsPath
} else {
    $current = ''
}

$block = Get-Content -Raw -Encoding UTF8 (Join-Path $root 'AGENTS.global.md')
if (-not $current.Contains($begin)) {
    if ($current.Trim().Length -gt 0) {
        $current = $current.TrimEnd() + "`r`n`r`n" + $block
    } else {
        $current = $block
    }
    Set-Content -Encoding UTF8 -Path $agentsPath -Value $current
    Write-Host "Added global instructions: $agentsPath"
} else {
    Write-Host 'Managed instruction block already exists; left it unchanged.'
}

Copy-Item -Force $skillSource $skillDest
Write-Host "Installed Skill: $skillDest"
Write-Host 'Done. Restart Kilo Code / VS Code, then use PROMPT_FIRST_RUN.md.'
Write-Host 'No MCP server was installed and kilo.jsonc was not modified.'
`````

### RESOURCE FILE: `01-kilo-self-improvement-kit/templates/BACKLOG.md`

`````markdown
# Agent Improvement Backlog

## Item template
- Item / priority:
- Problem evidence:
- Proposed change:
- Expected benefit:
- Risks and cost:
- Validation task:
- Status / rollback:
`````

### RESOURCE FILE: `01-kilo-self-improvement-kit/templates/EVALS.md`

`````markdown
# Kilo Code evaluation set

Repeat the same tasks before and after any meaningful agent-rule/Skill/MCP change. Record only observed facts.

| ID | Task | Pass criteria | Baseline | New result | Regression? | Notes |
|---|---|---|---|---|---|---|
| E1 | Fix a small reproducible bug | Test added or existing test proves fix; no unrelated edits | | | | |
| E2 | Multi-file feature | Plan followed, tests pass, public behavior documented | | | | |
| E3 | Find behavior in large codebase | Relevant symbols/files found without broad unnecessary file dumps | | | | |
| E4 | Use an unfamiliar library API | API checked against current official docs; no invented method | | | | |
| E5 | Verify UI/browser workflow (if applicable) | Actual browser/test evidence; result reproducible | | | | |
`````

### RESOURCE FILE: `01-kilo-self-improvement-kit/templates/LESSONS.md`

`````markdown
# Lessons

Record only useful, evidence-backed lessons. Do not include secrets or personal data.

## Entry template
- Date / task:
- Observed failure and evidence:
- Confirmed cause / uncertainty:
- Fix or proposed rule:
- Regression test:
- Result:
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/AGENTS.md`

`````markdown
# OpenMontage Factory — instructions for Kilo Code

## Mission
Help build a reliable, maintainable and low-cost YouTube video production pipeline. Prioritize reproducible outputs, licensed assets, quality gates and human approval over speed or volume.

## Required startup routine
At the beginning of every task:
1. Inspect the project README, current task, git status and relevant architecture docs.
2. List available Skills and load the most relevant ones explicitly. For video factory work, check `youtube-factory-orchestrator`; also use the relevant specialist Skill(s).
3. State briefly which Skills/tools you will use and why. Do not claim a Skill was used unless its contents were actually read or its slash command/tool was invoked.
4. Inspect existing code before changing it. Prefer a small, testable change over broad rewrites.
5. If an external API, library, license or platform policy may have changed, consult official docs or repository source rather than guessing.

## Factory pipeline
Treat production as explicit stages:
idea -> research -> outline/script -> fact-check -> asset plan -> asset/license verification -> edit decision list -> render -> technical QA -> human review -> upload preparation -> human-approved publish -> analytics -> experiment.

Each stage should have inputs, outputs, status, errors, retry policy and provenance. Keep stages idempotent where possible. Use stable job IDs and write intermediate manifests so interrupted jobs can resume.

## Rights and provenance — hard requirement
- Use only footage/audio/images/fonts that are user-owned, public domain, or covered by a documented license allowing the intended use.
- Do not treat "free download", "royalty-free", or a search result as proof of permission.
- For every asset record source URL, creator, exact license/terms URL, retrieval date, attribution text, intended commercial use status, modification status, and a local file hash.
- If license terms are unclear, quarantine the asset and ask for human review.
- Do not scrape or download YouTube videos as stock footage. Do not bypass DRM, paywalls, access controls, cookies, private content, or platform restrictions.
- Never invent citations, quotes, statistics, license claims, footage provenance, or performance data.

## YouTube publishing safety
- Build draft metadata and upload manifests first.
- Never publish, schedule, delete, or change a live video/channel setting without explicit human approval in the current task.
- Keep OAuth credentials outside the repo and logs. Use least-privilege scopes.
- Respect YouTube API quota, spam/deceptive practices rules, copyright policy and monetization/reused-content policies. Do not promise monetization eligibility.
- Make publication state observable: draft / approved / uploaded-unlisted / public / failed.

## Engineering standards
- Prefer modular adapters: research, asset providers, rights ledger, timeline/EDL, render backend, QA, YouTube API, analytics.
- Do not hardcode provider-specific logic across the pipeline.
- Add tests for parsing, path safety, retries, metadata, license records and failure handling.
- Validate external input; protect against path traversal, shell injection, oversized downloads and malformed media.
- Use subprocess argument arrays, not shell-concatenated untrusted strings.
- Store secrets in environment variables or a secret manager. Never commit `.env`; provide `.env.example` without secrets.
- Use pinned versions/lockfiles for reproducible builds. Record tool versions in each job report.
- Avoid adding dependencies unless they solve a concrete problem and have acceptable licenses.

## Quality gate before calling a video complete
Check:
- file exists and is non-empty;
- duration, resolution, frame rate and codec match the target profile;
- audio stream exists, loudness/clipping are within configured limits;
- no missing media, black gaps, frozen frames or unintended silence;
- subtitles/captions match the final narration and timing;
- claims and factual details are sourced;
- thumbnail/title/description are consistent and not misleading;
- asset-rights manifest is complete;
- render report and hashes are saved.
If a check cannot be performed, mark it NOT_CHECKED, never PASS.

## Self-improvement
- Record repeatable failures in `docs/agent-improvement/LESSONS.md`.
- Propose changes in `docs/agent-improvement/BACKLOG.md`; do not silently change global config or install new MCP/plugins.
- Evaluate proposed changes on the same benchmark tasks in `docs/agent-improvement/EVALS.md`.
- Require a human review for new permissions, external services, uploads, publishing, licensing exceptions, dependency changes or destructive migrations.
- Measure quality, failure rate, human correction time, cost per finished minute, render time and rights coverage. Optimize only when measurements improve.

## Completion response
Report: files changed, commands run, tests and results, skipped checks, rights/security risks, and the next smallest useful step. Distinguish implemented code from plans and unverified assumptions.
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/IMPLEMENTATION_ROADMAP.md`

`````markdown
# Roadmap: OpenMontage Factory

## Phase 0 — Audit, no destructive changes
- Read the current repository and identify implemented vs planned features.
- Map current pipeline, runtime, storage, queue, UI, tests and deployment.
- Create `docs/architecture/current-state.md` and `docs/architecture/target-state.md`.
- Run existing tests and record baseline; do not replace the stack before understanding it.

## Phase 1 — One reliable video end-to-end
- Define a typed job manifest and stable job ID.
- Accept a script and human-approved local/licensed assets.
- Store source/license metadata and SHA-256 checksums in an asset ledger.
- Build a simple EDL/timeline with clips, narration, music, subtitles and transitions.
- Render with FFmpeg for straightforward edits; add Remotion only where templates/animation require it.
- Generate a machine-readable QA report and a human-review preview.
- Deliver one finished local MP4; no auto-publishing.

## Phase 2 — Resumable production pipeline
- Model each stage with status, input/output, retries, timeout, error classification and provenance.
- Make stages idempotent and resumable after crash.
- Keep artifacts in per-job directories; prevent path traversal and unsafe filenames.
- Add structured logs, queue limits, cancellation and disk-space checks.
- Write integration tests for failed downloads, corrupt media, missing audio and interrupted renders.

## Phase 3 — Research and creative workflow
- Add source-backed research and a claim-to-source ledger.
- Generate outline, script, visual beat sheet, title/thumbnail pair and narration.
- Separate facts from creative framing; human review for sensitive or uncertain claims.
- Add versioned channel voice profile and format presets (long-form / Shorts).

## Phase 4 — Asset-provider adapters
- Integrate one approved provider at a time through a provider interface.
- Require license metadata and usage terms before asset can be accepted.
- Support local asset library as a first-class provider.
- Add cache, attribution and license-change review; quarantine unverified assets.
- Never scrape YouTube as a stock library or bypass access controls.

## Phase 5 — Quality gates
- Validate media technical specs using ffprobe.
- Detect black frames, frozen frames, audio clipping/silence and subtitle drift where tools permit.
- Run factual claim audit, title/thumbnail alignment and rights completeness checks.
- Mark checks PASS/FAIL/NOT_CHECKED with evidence.
- Block publishing if required checks fail.

## Phase 6 — YouTube integration
- Use the official YouTube Data API or an audited MCP adapter.
- Keep OAuth credentials out of source and logs; least privilege.
- Add quota accounting, resumable upload, retries and explicit publication states.
- Default to draft/unlisted. Public publishing and scheduling require explicit approval.
- Test with a private/unlisted test channel before production.

## Phase 7 — Analytics and feedback loop
- Import permitted analytics exports/API metrics with timestamp and measurement window.
- Track CTR, retention, average view duration, production time, failure rate, rights coverage and cost per finished minute.
- Compare similar videos against channel baselines; do not infer causation from a single upload.
- Add controlled experiments and record outcomes.

## Phase 8 — Self-improvement and hardening
- Keep LESSONS.md, BACKLOG.md, EVALS.md and CHANGELOG.
- Require regression tests for repeated failures.
- Test candidate changes on fixed benchmark tasks before adoption.
- Require review for dependency, license, permissions, secret, publishing and migration changes.
- Add CI, linting, type checking, dependency scanning and backup/restore tests.

## Acceptance criteria for the first milestone
- A test job produces a valid local MP4 from a manifest and approved assets.
- Each asset has a complete rights record or is rejected.
- A failed render can be retried without corrupting prior outputs.
- QA produces PASS/FAIL/NOT_CHECKED evidence.
- No upload/publication happens automatically.
- Unit and integration tests cover the critical path.
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/MCP_AND_TOOLS.md`

`````markdown
# Recommended stack for OpenMontage Factory (Kilo Code)

Start with the local core, then add only what a measured bottleneck requires.

## Core local tools
- **FFmpeg + ffprobe** — ingest, transcode, render simple edits, probe outputs. Repository: https://github.com/FFmpeg/FFmpeg
- **Remotion** — template-driven React compositions, motion graphics and batch rendering. https://github.com/remotion-dev/remotion
  - License warning: Remotion has special commercial licensing terms for some use cases. Check before commercial deployment.
- **Python or Node.js** — orchestration, manifests, queues, retries, tests. Pin dependencies and lockfiles.
- **SQLite** initially for job state and asset ledger; migrate only if measured concurrency needs it.
- **Git + automated tests** — reproducibility and rollback.

## Skills
- Official Kilo skills: https://github.com/Kilo-Org/skills
- YouTube agent skills (MIT): https://github.com/Jakeschincariol/youtube-agent-skill
  - Created for Claude Code; adapt/copy selected `SKILL.md` files into Kilo's `.kilo/skills/` or `~/.kilo/skills/`, check their scripts and dependencies. Do not assume the Claude plugin wrapper works in Kilo. This project includes channel strategy, scripting, packaging, retention, edit decisions and Shorts workflows.
- Remotion skills: https://github.com/remotion-dev/skills
  - Use for Remotion-specific coding, rendering and composition guidance.
- Superpowers MCP: https://github.com/Poseidoncode/superpowers-mcp
  - Optional workflow aid for planning/TDD/debugging; verify current compatibility and inspect setup before running.

## MCP / APIs
- **Context7**: https://github.com/upstash/context7 — current library documentation; optional remote service and possible limits.
- **GitHub MCP**: https://github.com/github/github-mcp-server — repository/issue/PR workflows; token permissions should be minimal.
- **YouTube MCP**: https://github.com/vapvarun/youtube-mcp — self-hostable YouTube Data API integration with OAuth. Verify current project license, API scope, quotas and security before use.
- Alternative YouTube upload MCP: https://github.com/adamanz/youtube-mcp-server — review maintenance and dependencies before selecting.
- **Playwright MCP**: https://github.com/microsoft/playwright-mcp — browser-based UI tests, only if the factory has a web dashboard.
- **Serena**: https://github.com/oraios/serena — semantic code navigation; optional if large codebase exploration is a bottleneck.
- **n8n**: https://github.com/n8n-io/n8n — optional workflow orchestration, but its fair-code license is not equivalent to a permissive OSI open-source license. Check commercial terms before embedding/reselling.

## Asset sources
Do not install an asset downloader before defining allowed sources and the rights ledger. Prefer official APIs from licensed providers or a human-approved local asset library. For each provider, store the exact license terms and a record of retrieval.
Do not use yt-dlp to scrape YouTube videos for stock footage. `yt-dlp` is a useful downloader for content you are authorized to download, but a tool's existence is not permission to reuse someone else's work.

## Suggested initial MCP set
1. Context7, if network access is acceptable.
2. GitHub MCP, only if you want Kilo to manage issues/PRs with approved access.
3. YouTube MCP only after a local prototype is tested; start with read-only or draft/unlisted workflows and keep public publishing approval manual.

Do not connect all MCPs at once. More tools can increase prompt clutter, latency, attack surface and troubleshooting complexity. Record why each tool is needed and measure whether it helps.
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/PROMPT_FIRST_RUN.md`

`````markdown
# Prompt to paste into Kilo Code

You are the implementation engineer for OpenMontage Factory, an automated YouTube video production system.

Before coding:
1. Read `AGENTS.md`, the repository README, architecture, tests, and current git status.
2. Explicitly inspect and load relevant Skills, especially `youtube-factory-orchestrator`, `licensed-footage-audit`, `video-pipeline-ffmpeg`, `youtube-quality-gate`, and any skill matching the actual task. State which ones you really loaded.
3. Audit the current repository. Do not assume planned features exist. Separate implemented, partially implemented, missing and broken functionality.
4. Read `IMPLEMENTATION_ROADMAP.md`, `MCP_AND_TOOLS.md` and `REPOSITORY_SHORTLIST.md`.
5. Research current official documentation and inspect source/README/license of any external repository before recommending integration.

Then produce:
- current architecture and data flow;
- prioritized backlog with impact, effort, dependencies and risk;
- a first small vertical slice with acceptance tests;
- exact files to change and a rollback plan;
- free/local-first options first, with any paid API or license costs called out.

Hard constraints:
- Never use unlicensed footage/audio/images/fonts; implement an asset rights ledger before automated asset selection.
- Do not scrape YouTube videos as stock footage or bypass DRM, access controls or site restrictions.
- Never expose secrets or commit OAuth tokens.
- Never publish, schedule, delete, or modify a live YouTube channel without explicit approval.
- Do not install plugins/MCP or alter global configuration without asking first.
- Do not claim a feature or test works until verified.

Start with an audit and the smallest valuable change. Do not rewrite the whole project. After each stage, run relevant tests, show actual results, update docs and identify remaining gaps.
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/README_RU.md`

`````markdown
# Kilo Code — YouTube Factory Kit

Комплект инструкций и Skills, чтобы Kilo Code помогал проектировать и развивать автоматизированную фабрику YouTube-видео (OpenMontage Factory): от исследования темы и сценария до поиска лицензированных материалов, монтажа, QA и подготовки публикации.

## Что внутри
- `AGENTS.md` — правила проекта и постоянный рабочий процесс.
- `skills/` — 8 специализированных Agent Skills:
  1. `youtube-factory-orchestrator`
  2. `youtube-research-and-scripting`
  3. `licensed-footage-audit`
  4. `video-pipeline-ffmpeg`
  5. `video-rendering-remotion`
  6. `youtube-quality-gate`
  7. `youtube-publishing-analytics`
  8. `youtube-factory-self-improvement`
- `MCP_AND_TOOLS.md` — рекомендованные MCP/CLI, назначение и ограничения.
- `REPOSITORY_SHORTLIST.md` — исследованные GitHub-репозитории.
- `IMPLEMENTATION_ROADMAP.md` — поэтапный план создания фабрики.
- `PROMPT_FIRST_RUN.md` — первый запрос для Kilo.
- `templates/` — шаблоны реестра материалов, видео-манифеста и QA-отчёта.
- `install-windows.ps1` и `install-unix.sh` — копируют Skills в пользовательскую папку Kilo; не устанавливают MCP, не меняют настройки API и не публикуют видео.

## Установка

### Windows PowerShell
Распакуй архив, открой PowerShell в этой папке и запусти:
```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install-windows.ps1
```

### Linux/macOS
```bash
chmod +x ./install-unix.sh
./install-unix.sh
```

Установщики делают резервные копии совпадающих Skills и не перезаписывают глобальный `AGENTS.md` без согласия. Они добавляют отдельный файл `YOUTUBE_FACTORY_RULES.md`; перенеси его содержимое в глобальный `AGENTS.md`, если хочешь глобальные правила, или оставь `AGENTS.md` в корне проекта фабрики для проектных правил.

После установки перезапусти Kilo Code или выполни `/reload`, если команда поддерживается твоей версией. Проверь, что Skills отображаются. Kilo обнаруживает Skills по метаданным и сам выбирает их для задачи; это не абсолютная гарантия. Поэтому в `AGENTS.md` есть явное правило: на старте каждой задачи проверить список Skills и назвать применимые.

## Важные ограничения
- Ничего не скачивает автоматически из интернета и не запускает установку сторонних MCP.
- Никакой публикации на YouTube без явного подтверждения человека.
- Использовать только собственные, public-domain или лицензированные ассеты с подтверждёнными условиями. Сохранять URL, лицензию, автора, дату получения и доказательство лицензии.
- Не обходить DRM, paywall, приватные ссылки, авторизацию или технические ограничения платформ.
- Учитывать лицензии FFmpeg, Remotion и каждого конкретного инструмента. Remotion имеет отдельные коммерческие условия в некоторых случаях.
- Не хранить API keys/OAuth tokens в Git, логах, манифестах или отчётах.
- Не обещать просмотры, вирусность или доход.

## Рекомендуемая стратегия
Сначала создать вертикальный срез: один короткий тестовый ролик с ручным подтверждением ассетов и экспорта. Только после воспроизводимого QA подключать очередь, аналитику и загрузку через YouTube Data API.
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/REPOSITORY_SHORTLIST.md`

`````markdown
# GitHub shortlist for building the YouTube Factory

Checked as a shortlist for architecture and integration planning on 2026-10-17. Repository status, API behavior, dependencies and licenses can change; verify before adopting.

| Project | Role | Recommendation / caveat |
|---|---|---|
| https://github.com/Jakeschincariol/youtube-agent-skill | 11 YouTube channel Skills: scripts, title/thumbnail packaging, retention, EDL, Shorts | MIT. Written for Claude Code; adapt Skill files, audit scripts and dependencies before Kilo use. |
| https://github.com/Jakeschincariol/chatgpt-youtube-agent-skill | Compatible-style YouTube workflow Skills | Compare with above; avoid duplicate skills with overlapping names. |
| https://github.com/remotion-dev/skills | Remotion agent skills | Use when implementing Remotion compositions and rendering. |
| https://github.com/remotion-dev/remotion | Programmatic video creation and batch rendering with React | Check Remotion commercial license terms. |
| https://github.com/FFmpeg/FFmpeg | Video/audio processing primitives | Check the exact build's LGPL/GPL configuration and redistribution obligations. |
| https://github.com/vapvarun/youtube-mcp | Self-hosted YouTube Data API MCP: upload/metadata/thumbnails/playlists | Requires Google OAuth setup; review license, scopes, API quota and security. |
| https://github.com/adamanz/youtube-mcp-server | YouTube upload MCP | Alternative; compare maintenance, API behavior, security and license before choosing. |
| https://github.com/github/github-mcp-server | GitHub issues, PRs and repository integration | Optional; use least-privilege token. |
| https://github.com/upstash/context7 | Current documentation lookup MCP | Optional external service; check limits and data handling. |
| https://github.com/microsoft/playwright-mcp | Browser automation | Useful for testing a factory dashboard, not required for a CLI-only factory. |
| https://github.com/oraios/serena | Semantic code navigation and editing | Optional; add if repository size makes code exploration costly. |
| https://github.com/Poseidoncode/superpowers-mcp | Planning, TDD and debugging workflow tools | Optional; verify Kilo setup instructions and inspect code before execution. |
| https://github.com/n8n-io/n8n | Workflow orchestration and integrations | Optional; fair-code license, check commercial terms. |
| https://github.com/yt-dlp/yt-dlp | Downloader for authorized media | Do not use to harvest third-party YouTube footage; download only content you have permission to obtain. |
| https://github.com/yt-dlp/FFmpeg-Builds | FFmpeg builds used by yt-dlp | Review build configuration and license obligations. |
| https://github.com/modelcontextprotocol/servers | Reference MCP server implementations | Some components may be archived; choose maintained projects individually. |
| https://github.com/udecode/skiller | Skill synchronization across agents | Optional; verify current Kilo paths and avoid overwriting project Skills. |
| https://github.com/Kilo-Org/kilo-marketplace | Kilo-compatible Skills, MCPs, agents and plugins catalog | Best first stop for Kilo-specific integration. |

## How to decide
Score each candidate on: verified compatibility, active maintenance, license fit, secrets/permissions, installation complexity, token/latency impact, testability and actual improvement on benchmark tasks. Do not equate GitHub stars with security or quality.
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/YOUTUBE_FACTORY_RULES.md`

`````markdown
# Global rules for YouTube Factory tasks

For every task related to OpenMontage Factory or automated YouTube production:
- Explicitly inspect and use the relevant available Skills; do not rely on vague memory.
- Prefer official documentation and current repository source for tool/API behavior.
- Protect rights: no asset enters a final timeline without a traceable license/provenance record.
- Keep human approval before any public upload, scheduling, deletion or channel mutation.
- Build modular, testable stages and preserve job manifests for resumability.
- Run tests and a technical media QA gate; mark unperformed checks NOT_CHECKED.
- Record repeated failures and propose evidence-based improvements; never silently modify global config, install plugins, expose secrets or publish.
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/docs/agent-improvement/BACKLOG.md`

`````markdown
# Improvement backlog

| ID | Problem | Evidence | Proposed change | Impact | Effort | Risk | Status |
|---|---|---|---|---|---|---|---|
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/docs/agent-improvement/CHANGELOG.md`

`````markdown
# Improvement changelog

Record accepted changes, benchmark evidence, reviewer and rollback method.
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/docs/agent-improvement/EVALS.md`

`````markdown
# Evaluation set

Keep stable benchmark tasks and expected outcomes. Run the same tasks before/after agent, Skill, MCP or pipeline changes. Record model/tool versions, pass rate, cost, runtime and human corrections.
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/docs/agent-improvement/LESSONS.md`

`````markdown
# Lessons learned

Add only reproducible, evidence-backed lessons. Include date, symptom, root cause, fix, test and confidence.
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/install-unix.sh`

`````bash
#!/usr/bin/env bash
set -euo pipefail
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skills"
DEST="$HOME/.kilo/skills"
mkdir -p "$DEST"
stamp="$(date +%Y%m%d-%H%M%S)"

for skill_dir in "$SOURCE"/*; do
  [ -d "$skill_dir" ] || continue
  name="$(basename "$skill_dir")"
  target="$DEST/$name"
  if [ -e "$target" ]; then
    cp -R "$target" "$target.backup-$stamp"
    rm -rf "$target"
    echo "Backed up existing skill: $target.backup-$stamp"
  fi
  cp -R "$skill_dir" "$target"
  echo "Installed skill: $name"
done

cp "$(dirname "$SOURCE")/YOUTUBE_FACTORY_RULES.md" "$HOME/.kilo/YOUTUBE_FACTORY_RULES.md"
echo
echo "Skills installed to: $DEST"
echo "Rules copied to: $HOME/.kilo/YOUTUBE_FACTORY_RULES.md"
echo "Review and merge rules into your global AGENTS.md if desired."
echo "Restart Kilo Code or use /reload, then verify skill discovery."
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/install-windows.ps1`

`````powershell
$ErrorActionPreference = "Stop"
$source = Join-Path $PSScriptRoot "skills"
$dest = Join-Path $HOME ".kilo\skills"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

Get-ChildItem -Directory $source | ForEach-Object {
    $target = Join-Path $dest $_.Name
    if (Test-Path $target) {
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        Copy-Item -Recurse $target "$target.backup-$stamp"
        Write-Host "Backed up existing skill: $target"
        Remove-Item -Recurse -Force $target
    }
    Copy-Item -Recurse $_.FullName $target
    Write-Host "Installed skill: $($_.Name)"
}

$rules = Join-Path $PSScriptRoot "YOUTUBE_FACTORY_RULES.md"
$rulesTarget = Join-Path $HOME ".kilo\YOUTUBE_FACTORY_RULES.md"
Copy-Item $rules $rulesTarget -Force
Write-Host ""
Write-Host "Skills installed to $dest"
Write-Host "Rules copied to $rulesTarget"
Write-Host "Review the rules and merge into your global AGENTS.md if desired."
Write-Host "Restart Kilo Code or use /reload, then verify skill discovery."
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/templates/asset-rights-ledger.csv`

`````csv
asset_id,local_path,sha256,source_url,creator,license_name,license_url,retrieved_at_utc,commercial_use,modification_allowed,attribution_text,evidence_path,status,review_notes
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/templates/qa-report.json`

`````json
{
  "job_id": "example-001",
  "overall_status": "NOT_CHECKED",
  "checks": [
    {
      "name": "output_exists",
      "status": "NOT_CHECKED",
      "evidence": ""
    },
    {
      "name": "ffprobe_streams",
      "status": "NOT_CHECKED",
      "evidence": ""
    },
    {
      "name": "audio_quality",
      "status": "NOT_CHECKED",
      "evidence": ""
    },
    {
      "name": "black_frames_and_gaps",
      "status": "NOT_CHECKED",
      "evidence": ""
    },
    {
      "name": "captions_sync",
      "status": "NOT_CHECKED",
      "evidence": ""
    },
    {
      "name": "factual_claims_sources",
      "status": "NOT_CHECKED",
      "evidence": ""
    },
    {
      "name": "asset_rights_complete",
      "status": "NOT_CHECKED",
      "evidence": ""
    },
    {
      "name": "human_approval",
      "status": "NOT_CHECKED",
      "evidence": ""
    }
  ]
}
`````

### RESOURCE FILE: `02-youtube-factory-kilo-kit/templates/video-job-manifest.json`

`````json
{
  "schema_version": "1.0",
  "job_id": "example-001",
  "channel_id": "local-placeholder",
  "format": "long-form",
  "language": "en",
  "target": {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "container": "mp4"
  },
  "script_path": "script/script.md",
  "assets_manifest": "assets/asset-rights-ledger.csv",
  "timeline_path": "timeline/edl.json",
  "render": {
    "backend": "ffmpeg",
    "preset": "review",
    "output_path": "output/review.mp4"
  },
  "qa": {
    "status": "NOT_CHECKED",
    "report_path": "reports/qa.json"
  },
  "publishing": {
    "status": "DRAFT",
    "requires_human_approval": true
  },
  "provenance": {
    "tool_versions": {},
    "created_at_utc": null
  }
}
`````

### RESOURCE FILE: `INSTALL_CHECKLIST_RU.md`

`````markdown
# Контрольный список после настройки Kilo Code

## Установка

- [ ] Я открыл в Kilo Code именно проект OpenMontage Factory.
- [ ] Оба комплекта были доступны агенту; установлены те файлы, которые реально присутствовали.
- [ ] Созданы резервные копии прежних инструкций и одноимённых Skills.
- [ ] Активный глобальный `AGENTS.md` содержит блок самоулучшения без дубликатов.
- [ ] YouTube-правила реально подключены к глобальному или проектному активному `AGENTS.md`.
- [ ] `kilo-self-improvement` обнаруживается.
- [ ] Все восемь YouTube Skills обнаруживаются и лежат в поддерживаемом каталоге.
- [ ] Kilo перезапущен или Skills перечитаны через поддерживаемый `/reload`.
- [ ] Существующий `kilo.json`/`kilo.jsonc` не был заменён шаблоном.
- [ ] MCP не объявлены «установленными», если не проверен фактический вызов.

## Поведение

- [ ] На обычной задаче Kilo использует общие инструкции и не загружает все YouTube Skills без причины.
- [ ] На задаче YouTube он выбирает `youtube-factory-orchestrator` и соответствующие specialist Skills.
- [ ] В отчёте перечисляются только фактически прочитанные Skills и действительно использованные инструменты.
- [ ] Тесты не объявляются пройденными без реального запуска.
- [ ] Ассеты без понятной лицензии блокируются/помещаются в карантин.
- [ ] Публичная публикация, расписание и изменения канала требуют явного подтверждения.
- [ ] Секреты не выводятся в терминал, отчёты или Git.
- [ ] Повторяющиеся ошибки попадают в `LESSONS.md`; предложения — в `BACKLOG.md`; сравнительные тесты — в `EVALS.md`.

## Критерий завершения

Считать установку завершённой только после фактической проверки инструкций, каждого Skill, тестового маршрутизирования Skills и существующих тестов проекта. Всё, что реально не выполнялось, отмечать `NOT_CHECKED`, а не `PASS`.
`````

### RESOURCE FILE: `MASTER_PLAN_RU.md`

`````markdown
# Мастер-план: объединение двух комплектов Kilo Code и OpenMontage Factory

## Конечная цель

Настроить Kilo Code так, чтобы он последовательно работал по двум уровням:

1. **Общие инженерные навыки Kilo Code:** разбирать задачу, находить применимые Skills, проверять доступность MCP, изучать проект, делать небольшие изменения, выполнять тесты, фиксировать повторяющиеся ошибки и предлагать улучшения, проверяемые контрольными задачами.
2. **Специализация YouTube Factory:** проводить исследование, готовить сценарии и план визуальных сцен, проверять лицензии материалов, формировать монтажный план, рендерить видео, делать QA, готовить метаданные и аналитику с ручным контролем публикации.

Это улучшает рабочий процесс, инструкции, Skills и тесты, а не обучает модель на новых весах. «Всегда использовать» означает: на каждой задаче проверять релевантность навыков и явно загружать подходящие. Это не означает загружать восемь YouTube Skills к любому вопросу или утверждать, что невызванный Skill был использован.

---

## Архитектура после установки

### Слой A — глобальные правила Kilo Code

Основной файл: `~/.config/kilo/AGENTS.md` (в Windows обычно `%USERPROFILE%\.config\kilo\AGENTS.md`).

Он содержит общий протокол:
- классифицировать задачу;
- проверять и читать описания релевантных Skills;
- выбирать нужные MCP только по фактической доступности и пользе;
- сначала изучать существующий код и состояние Git;
- проверять результат тестами;
- записывать воспроизводимые уроки и идеи улучшений;
- не менять глобальные правила, секреты, разрешения и публикацию без отдельного обзора.

### Слой B — глобальные Skills

Каталог: `~/.kilo/skills/`.

Первый комплект добавляет `kilo-self-improvement`. Второй добавляет восемь тематических Skills:

1. `youtube-factory-orchestrator` — выбор этапов и координация конвейера.
2. `youtube-research-and-scripting` — исследование, источники, сценарии.
3. `licensed-footage-audit` — проверка прав, лицензий и происхождения файлов.
4. `video-pipeline-ffmpeg` — автоматизация монтажа и проверка медиа через FFmpeg/ffprobe.
5. `video-rendering-remotion` — шаблонный рендер и motion-графика, если они нужны.
6. `youtube-quality-gate` — техническая и содержательная проверка результата.
7. `youtube-publishing-analytics` — подготовка загрузки и разбор метрик при наличии доступа.
8. `youtube-factory-self-improvement` — измеряемые улучшения производственного конвейера.

### Слой C — активные YouTube-правила

Файл второго архива `YOUTUBE_FACTORY_RULES.md` — отдельный файл, и копирование в `~/.kilo/YOUTUBE_FACTORY_RULES.md` само по себе не гарантирует, что он будет подгружаться автоматически.

Нужно безопасно добавить содержимое в конец активного глобального `AGENTS.md` под отдельными маркерами, например:

`<!-- OPENMONTAGE_FACTORY_RULES_BEGIN -->`

`<!-- OPENMONTAGE_FACTORY_RULES_END -->`

Перед редактированием: сделать копию с временной меткой, сохранить всё существующее содержимое и не создавать второй конфликтующий блок при повторном запуске. Альтернатива — хранить правила в `AGENTS.md` корня самого проекта OpenMontage Factory; это обычно чище, если инструкции нужны только этому проекту.

### Слой D — файлы проекта фабрики

В корне репозитория OpenMontage Factory должны находиться проектные инструкции `AGENTS.md` и необходимые документы/тесты. В проекте поддерживаются:

- `docs/architecture/current-state.md` — что действительно реализовано сейчас;
- `docs/architecture/target-state.md` — целевая схема;
- `docs/agent-improvement/LESSONS.md` — подтверждённые повторяющиеся уроки;
- `docs/agent-improvement/BACKLOG.md` — идеи улучшений с риском и критерием успеха;
- `docs/agent-improvement/EVALS.md` — одинаковые контрольные задания;
- `docs/agent-improvement/CHANGELOG.md` — принятые изменения правил/workflow;
- `templates/asset-rights-ledger.csv` — реестр прав на материалы;
- `templates/video-job-manifest.json` — параметры и состояние задания;
- `templates/qa-report.json` — результат QA.

Если этих файлов нет, Kilo должен создать минимальные версии, не подменяя ими существующие документы без сравнения и резервного копирования.

---

## Порядок внедрения

## Этап 0. Подготовить окружение и сохранить исходное состояние

1. Открыть в Kilo Code именно репозиторий OpenMontage Factory.
2. Убедиться, что оба каталога комплектов доступны в текущей рабочей области.
3. Записать `git status`, текущую ветку и хеш последнего коммита, если используется Git.
4. Проверить версию Kilo Code, ОС, активную оболочку и способ запуска (VS Code extension или CLI).
5. Найти все существующие `AGENTS.md`, `kilo.jsonc`, `kilo.json`, Skills и MCP-конфигурации. Не выводить секреты в отчёт.
6. Сохранить резервные копии файлов инструкций, соответствующих Skills и конфигурации до их изменения.
7. Не считать конфигурацию MCP доказательством, что сервер доступен: проверить реальные инструменты после перезапуска.

**Готово, когда:** имеется карта текущей конфигурации и план отката, а пользовательские настройки и незакоммиченные файлы не потеряны.

## Этап 1. Поставить слой самоулучшения

1. Проверить содержимое `01-kilo-self-improvement-kit/`.
2. Установить `kilo-self-improvement/SKILL.md` в `~/.kilo/skills/kilo-self-improvement/SKILL.md`, предварительно сохранив старую версию, если она существует.
3. Добавить блок `AGENTS.global.md` в активный глобальный `AGENTS.md`. Сохранить существующий текст и избежать дублирования при повторных установках.
4. Создать/сверить проектные файлы `LESSONS.md`, `BACKLOG.md`, `EVALS.md`; если они существуют, объединять аккуратно, не перезаписывать пользовательские записи.
5. Проверить, что Kilo видит Skill по правильному пути и что `SKILL.md` находится непосредственно в каталоге Skill.

**Готово, когда:** глобальные правила реально загружены, Skill обнаруживается, а резервные копии доступны.

## Этап 2. Поставить YouTube Skills и правила фабрики

1. Проверить метаданные `name` и `description` у всех восьми Skills.
2. Установить их в `~/.kilo/skills/` либо в `.kilo/skills/` проекта. Выбрать один вариант, не плодить копии без причины.
3. Перед заменой одноимённых Skill сохранить резервную копию и сравнить содержимое.
4. Включить `YOUTUBE_FACTORY_RULES.md` в глобальные инструкции под отдельными маркерами или подключить его через официально поддерживаемую настройку инструкций. Для правил, которые нужны только фабрике, предпочесть проектный `AGENTS.md`.
5. Проверить, что общие правила самоулучшения и YouTube-правила не противоречат друг другу. При конфликте: безопасность, права, секреты и ручное подтверждение публикации имеют приоритет.
6. Перезапустить Kilo или выполнить `/reload`, если команда поддерживается этой версией.

**Готово, когда:** Kilo фактически обнаруживает все предназначенные Skills; YouTube-правила поступают из активного источника инструкций, а не только лежат отдельным файлом.

## Этап 3. Оценить MCP и внешние инструменты

Не подключать все MCP «на всякий случай». Сначала проверить текущую документацию, состояние репозитория, лицензию, поддерживаемую конфигурацию Kilo, команды, окружение, доступы и стоимость.

Рекомендованное решение по одному компоненту за раз:

- **Context7:** потенциально полезен для актуальной документации библиотек; проверить требования текущей версии и сетевую политику.
- **GitHub MCP:** подключать, только если Kilo должен работать с Issues/PR/репозиторием через API; использовать минимальные полномочия токена.
- **Superpowers MCP:** необязательный помощник по workflow; проверить README, команду установки и совместимость перед запуском.
- **Serena или jCodeMunch:** выбрать не более одного на старте, если навигация по большому коду действительно является узким местом.
- **Playwright MCP:** только если у фабрики есть веб-интерфейс или нужны browser-тесты.
- **YouTube MCP:** отложить до успешного локального рендера; требует отдельной проверки OAuth, разрешений, квот и безопасности.
- **n8n:** не считать автоматически бесплатным permissive open source; проверить условия лицензии и коммерческого использования до включения.

На каждый MCP: назначение → подтверждённая совместимость → права → секреты/сеть/стоимость → конфиг diff → фактический тест вызова. Не записывать токены в репозиторий, логи или отчёты. Не заменять весь `kilo.jsonc` новым примером: объединять только необходимые ключи и сохранять резервную копию.

**Готово, когда:** подключены только оправданные инструменты, реальные вызовы проверены, остальные оставлены в backlog с причиной.

## Этап 4. Сделать аудит OpenMontage Factory

До серьёзного кодирования Kilo должен определить:

- какие части конвейера уже реализованы, частично реализованы, отсутствуют или сломаны;
- каковы архитектура, используемые языки, зависимости, точка входа, тесты и способы запуска;
- где хранятся файлы заданий, ассеты, результаты рендера и логи;
- что работает, что является планом, а что ещё не проверено;
- какие изменения нужны для минимального end-to-end прототипа.

Создать `docs/architecture/current-state.md` и `target-state.md`, а также baseline из существующих тестов. Не переписывать проект, пока карта не готова.

## Этап 5. Собрать вертикальный срез: один ролик от входа до MP4

Минимальная цепочка:

`идея → исследование → сценарий → план визуала → одобренные ассеты → реестр прав → монтажный план/EDL → рендер → QA-отчёт → просмотр человеком`.

Первый прототип должен работать на локальных или вручную одобренных файлах. Использовать FFmpeg/ffprobe для обычного монтажа; добавлять Remotion, только если нужны React-шаблоны или сложная анимация и лицензия подходит проекту. На первом этапе не нужна автоматическая публикация.

Минимальные приёмочные критерии:

- видео MP4 существует, не пустое и соответствует заданному профилю;
- длительность, разрешение, частота кадров и кодеки проверены;
- аудио проверено на наличие, клиппинг и нежелательную тишину в пределах возможностей доступных инструментов;
- нет пропавших ассетов и неожиданных чёрных вставок в пределах выполненных проверок;
- права и происхождение каждого ассета записаны; неизвестные материалы отклонены или помещены в карантин;
- фактические утверждения в сценарии имеют источники;
- QA отмечает `PASS`, `FAIL` либо `NOT_CHECKED` и указывает доказательства;
- публикация не запускается автоматически.

## Этап 6. Сделать конвейер возобновляемым и тестируемым

После успешного вертикального среза добавить устойчивые ID заданий, промежуточные манифесты, статусы стадий, тайм-ауты, ограниченные повторные попытки, классификацию ошибок, лимиты очереди, контроль диска и продолжение после сбоя. Каждый этап должен быть по возможности идемпотентным.

Тестировать повреждённые файлы, отсутствующее аудио, недостающие лицензии, прерванный рендер, неверные пути, повторные попытки и небезопасные имена файлов. Не склеивать недоверенные строки в shell-команды.

## Этап 7. Публикация и аналитика — только после QA

Сначала готовить метаданные и черновой манифест. API загрузки — отдельный модуль с минимальными OAuth scope, защитой секретов, учётом квот, retry и явными состояниями: `draft`, `approved`, `uploaded-unlisted`, `public`, `failed`.

Никакой публичной публикации, планирования, удаления видео или изменения настроек канала без явного подтверждения пользователя в текущей задаче. После разрешённой публикации аналитика должна хранить окно измерения и дату сбора; не делать причинные выводы по одному видео.

## Этап 8. Включить измеряемое самоулучшение

По повторяющимся сбоям обновлять `LESSONS.md`, предложения помещать в `BACKLOG.md`, а контрольные задания хранить в `EVALS.md`. Для каждого изменения:

1. зафиксировать наблюдение и подтверждённую причину;
2. определить baseline и проверяемую гипотезу;
3. сделать небольшой diff/ветку;
4. прогнать одинаковые задачи до и после;
5. убедиться, что не ухудшились корректность, права, безопасность и стабильность;
6. показать изменения глобальных правил, MCP или разрешений на review;
7. документировать принятие либо откат.

Не изменять глобальные инструкции автоматически после одной ошибки. «Самоулучшение» не запускается само по расписанию: для расписания требуется отдельный локальный планировщик/CI, который должен быть согласован и протестирован.

---

## Контрольные задачи до и после улучшений

1. **Маленький баг:** найти причину, внести маленький diff, запустить подходящий тест. PASS только если тест действительно был выполнен и прошёл.
2. **Большой проект:** найти нужный символ/поток данных с минимальным чтением; указать реальные инструменты и файлы, а не выдумывать.
3. **Неизвестный API:** посмотреть актуальную официальную документацию/подключённый Context7, указать версию и источник; не придумывать параметры.
4. **YouTube-сценарий:** подготовить сценарий и таблицу «утверждение → источник → подтверждение»; отделить проверенные факты от неизвестного.
5. **Ассет с неясной лицензией:** система должна отказать в его финальном использовании, пометить `QUARANTINE` и объяснить, каких доказательств не хватает.
6. **Технический QA:** для тестового MP4 приложить фактические результаты `ffprobe`/проверок, отметить непройденное как `NOT_CHECKED`.
7. **Повторяющаяся ошибка:** оформить урок и regression test, предложить маленькое изменение и сравнить до/после.
8. **Безопасность публикации:** подготовить черновик загрузки, но не публиковать и не менять канал без текущего явного одобрения человека.

Записывать PASS/FAIL, фактические результаты, ограничения, ручные исправления и время/стоимость только если они действительно доступны. Не сравнивать модели по выдуманным метрикам.

---

## Когда мастер-внедрение считается законченным

- глобальный `AGENTS.md` сохранён, объединён и действительно активен;
- Skill самоулучшения и восемь YouTube Skills обнаружены Kilo по фактическим путям;
- релевантные Skills называются в начале задач, но нерелевантные не загружаются;
- настроенные MCP проверены реальными вызовами; непроверенные обозначены;
- `LESSONS.md`, `BACKLOG.md`, `EVALS.md` и `CHANGELOG.md` ведутся в проекте;
- карта текущего состояния фабрики отделяет код от планов;
- есть один воспроизводимый локальный MP4 с реестром прав и QA-отчётом;
- секреты не попали в файлы/логи/Git;
- публичная публикация остаётся под ручным подтверждением;
- по всем глобальным изменениям существует резервная копия и план отката.

## Источники по расположению настроек

- [Kilo Code: Custom Instructions](https://kilo.ai/docs/customize/custom-instructions)
- [Kilo Code: Skills](https://kilo.ai/docs/customize/skills)
- [Kilo Code: Using MCP](https://kilo.ai/docs/automate/mcp/using-in-kilo-code)
`````

### RESOURCE FILE: `MASTER_PROMPT_KILO_CODE_RU.md`

`````markdown
# Главный промпт для Kilo Code: установить два набора, объединить инструкции и запустить OpenMontage Factory

Ты — ведущий инженер по инструментам и реализации OpenMontage Factory. Твоя задача — аккуратно установить и объединить два предоставленных набора:

1. `01-kilo-self-improvement-kit` — общие Skills и постоянный цикл улучшения качества Kilo Code.
2. `02-youtube-factory-kilo-kit` — восемь Skills и правила для YouTube-конвейера.

Моя цель: сделать использование релевантных Skills, проверок и правил постоянной частью каждого подходящего рабочего процесса. Не ограничивайся фразой «установлено»: докажи фактические пути, доступность и поведение контрольными проверками.

## Правила выполнения

- Действуй поэтапно и автономно в рамках безопасных файловых изменений, которые описаны ниже. Не проси подтверждения на каждый безопасный шаг.
- Сначала проверь состояние и создай резервные копии; затем изменяй файлы. Не перезаписывай неизвестное содержимое без сравнения.
- Не переписывай весь проект и не удаляй пользовательские данные.
- Не раскрывай секреты и не включай API-ключи, OAuth tokens, пароли или cookies в отчёты, команды, Git или файлы инструкций.
- Не утверждай, что команда, Skill, MCP, тест или функция сработали, пока не проверил фактический результат.
- Не считай MCP доступным только потому, что он указан в конфигурации. Проверь реальную доступность инструмента.
- Не устанавливай все найденные плагины/MCP автоматически. Исследуй официальный источник, назначение, совместимость, лицензию и права. Перед добавлением удалённого сервиса, установкой стороннего исполняемого пакета, OAuth/API-доступом, новыми разрешениями или изменением разрешений инструментов остановись на кратком review и запроси отдельное разрешение. Не обходи системные диалоги разрешений.
- Не изменяй live YouTube-канал. Никогда не публикуй, не планируй, не удаляй ролики и не меняй настройки канала без отдельного явного разрешения пользователя в текущей задаче.
- Не называй модель обучающейся или самообучающейся: здесь улучшаются инструкции, Skills, инструменты, тесты и документация.

## Шаг 1. Найди наборы и проверь среду

1. Найди папки `01-kilo-self-improvement-kit` и `02-youtube-factory-kilo-kit` в рабочей области. Если есть несколько копий, сравни содержимое и выбери ту, где присутствуют README, установочные сценарии и Skills. Не используй предположительные пути, если их нельзя подтвердить.
2. Убедись, что открыт именно репозиторий OpenMontage Factory. Если его нет, не создавай большой проект по догадке: подготовь аудит наборов и сообщи, что до реализации конвейера нужен путь к репозиторию.
3. Определи ОС, версию Kilo, способ запуска (VS Code extension/CLI), активную оболочку и поддерживаемые пути инструкций/Skills по текущей официальной документации.
4. Проверь `git status`, ветку и последний коммит, если это Git-репозиторий.
5. Найди глобальный `AGENTS.md`, существующие `AGENTS.md` в проекте, глобальные и проектные `kilo.json`/`kilo.jsonc`, существующие Skills, MCP и файлы правил. Секреты не показывай: достаточно сообщить, что секретные поля присутствуют, и их расположение.
6. Составь короткий preflight-отчёт: что найдено, что будет изменено, какие резервные копии сделаны, что не удалось проверить.

Если один из комплектов недоступен, не имитируй установку. Выполни доступную безопасную часть и укажи точный недостающий путь.

## Шаг 2. Сделай резервные копии

Перед редактированием глобальных инструкций, Skills или конфигураций:

- создай резервную копию с датой/временем для каждого изменяемого существующего файла;
- для каталога Skill создай копию всего каталога;
- сохраняй копии вне пути, который установщик удаляет/заменяет;
- запиши список backup-путей в локальный отчёт установки;
- не добавляй резервные копии, конфиги с секретами или `.env` в Git.

Существующий `kilo.json`/`kilo.jsonc` не заменяй. В этом этапе его можно только прочитать без показа секретов.

## Шаг 3. Установи слой постоянного самоулучшения

Используй `01-kilo-self-improvement-kit/README_RU.md`, `AGENTS.global.md`, `KILO_SELF_IMPROVEMENT_PLAN.md`, `skills/kilo-self-improvement/SKILL.md` и установочный сценарий как источники.

1. Установи Skill `kilo-self-improvement` в подтверждённый глобальный каталог Skills Kilo. На обычной установке это `~/.kilo/skills/kilo-self-improvement/SKILL.md`, но сначала проверь путь для текущей версии.
2. Установи общий протокол из `AGENTS.global.md` в действующий глобальный `AGENTS.md`. Объедини аккуратно, не затирай пользовательские правила. Если в файле уже присутствует маркер `KILO_SELF_IMPROVEMENT_BEGIN`, обновляй управляемый блок только после сравнения и с сохранением пользовательских соседних разделов; не добавляй повторный блок.
3. Если используешь предоставленный установочный сценарий, сначала изучи его текст, проверь целевые пути, создай backup и запускай только подходящий сценарий для текущей ОС. Не запускай оба варианта.
4. Убедись, что `SKILL.md` находится непосредственно в каталоге `kilo-self-improvement` и содержит корректные поля `name` и `description` в frontmatter.

## Шаг 4. Установи YouTube Skills

Используй `02-youtube-factory-kilo-kit/README_RU.md`, `skills/README.md`, `YOUTUBE_FACTORY_RULES.md` и содержимое всех Skills.

1. Установи восемь Skills в проверенный глобальный `~/.kilo/skills/` (либо, если текущая версия или устройство не поддерживает ожидаемый путь, выбери актуальный официальный путь и объясни почему):
   - `youtube-factory-orchestrator`
   - `youtube-research-and-scripting`
   - `licensed-footage-audit`
   - `video-pipeline-ffmpeg`
   - `video-rendering-remotion`
   - `youtube-quality-gate`
   - `youtube-publishing-analytics`
   - `youtube-factory-self-improvement`
2. До замены одноимённого Skills сравни версии и создай резервную копию. Не удаляй другие Skills.
3. Проверь каждый `SKILL.md`: имя, описание, расположение и читаемость. Не заявляй о загрузке, пока Kilo не обнаруживает его.

## Шаг 5. Подключи YouTube-правила так, чтобы они реально действовали

Важно: копия `YOUTUBE_FACTORY_RULES.md` в `~/.kilo/YOUTUBE_FACTORY_RULES.md` не обязательно загружается как инструкция автоматически.

Сделай один из двух подтверждённых вариантов:

**Предпочтительно для отдельного проекта:** безопасно объединить содержимое `02-youtube-factory-kilo-kit/AGENTS.md` с существующим `AGENTS.md` в корне OpenMontage Factory. Если `AGENTS.md` уже есть, сохрани его структуру и собственные правила, добавь только отсутствующие нужные правила и не дублируй одинаковые разделы.

**Для всех проектов:** если пользователь действительно хочет глобальные YouTube-правила, добавь содержимое `YOUTUBE_FACTORY_RULES.md` в активный глобальный `AGENTS.md` под отдельными уникальными маркерами `OPENMONTAGE_FACTORY_RULES_BEGIN` и `OPENMONTAGE_FACTORY_RULES_END`. Не добавляй его только как отдельный неактивный файл. Сохрани backup.

В обоих вариантах обеспечь согласованность: общие правила Kilo действуют для всех задач; YouTube-специализация применяется только к OpenMontage Factory и релевантным YouTube-задачам. Не загружай восемь YouTube Skills на нерелевантные задачи.

## Шаг 6. Подготовь журнал самоулучшения и карту проекта

В корне проекта сохрани существующие записи или создай при отсутствии:

- `docs/agent-improvement/LESSONS.md`
- `docs/agent-improvement/BACKLOG.md`
- `docs/agent-improvement/EVALS.md`
- `docs/agent-improvement/CHANGELOG.md`

В `docs/architecture/` создай `current-state.md` и `target-state.md`, если их ещё нет. Сначала исследуй код, зависимости, тесты, точку входа, структуру хранения и рендер. Раздели всё на `implemented`, `partial`, `missing`, `broken`, `not verified`. Не выдавай roadmap за существующую реализацию. Если репозиторий пуст или недоступен — не выдумывай архитектуру, создай только честный отчёт о блокере.

## Шаг 7. MCP и инструменты: аудит, а не слепая установка

Сначала проинвентаризируй реальные доступные MCP и инструменты. Затем подготовь приоритетный список с назначением, официальным источником, совместимостью, ценой/лимитами, требованиями к секретам, разрешениями, статусом и способом теста.

Оцени по мере необходимости:
- Context7 — актуальная документация библиотек;
- GitHub MCP — только если нужны GitHub Issues/PR/API, с минимальными scope;
- Superpowers MCP — после проверки официального README и команды настройки для Kilo;
- один инструмент навигации по большому коду (Serena или jCodeMunch), только если есть узкое место;
- Playwright MCP — только при наличии веб-интерфейса/браузерных тестов;
- YouTube MCP — отложить до рабочего локального MVP; перед запуском проверить официальный код, лицензию, OAuth, права API и квоты.

Можешь безопасно подготовить предложения и diff конфигурации. Не изменяй `kilo.json`/`kilo.jsonc`, права, токены и сторонние серверы без отдельного review/разрешения. Не устанавливай инструменты только ради количества. Для инструментов, уже подключённых, проверь реальный тестовый вызов и измерь полезность.

Локальный производственный стек оцени отдельно: FFmpeg и ffprobe, Python или Node.js, Git, тесты; Remotion добавляй только при конкретной необходимости и после проверки лицензии коммерческого использования. Не обещай, что все составляющие бесплатны.

## Шаг 8. Обязательно активируй и проверь правила

1. Укажи точный путь каждого активного файла инструкций.
2. Перезапусти Kilo Code либо выполни `/reload`, если он поддерживается.
3. Проверь список обнаруженных Skills или открой меню Skills. Проверь все девять Skills (самоулучшение плюс восемь YouTube); если какой-либо не найден, диагностируй имя, frontmatter и путь.
4. Для задачи о YouTube явно выбери оркестратор и релевантные specialist Skills. Перед работой прочитай их `SKILL.md` или вызови Skill-команду, если интерфейс поддерживает это. В начале каждой подходящей задачи перечисляй фактически выбранные/прочитанные Skills, но не утверждай, что использовал невызванный Skill.
5. В тестовой обычной задаче не загружай YouTube Skills, если они нерелевантны; это проверяет корректное маршрутизирование, а не загрузку всего подряд.
6. Проверяй инструкции с учётом иерархии Kilo: agent prompt и конфигурация могут иметь более высокий приоритет, чем `AGENTS.md`. Если найден конфликт, покажи его и предложи минимальное исправление. Не делай необнаруженных предположений о приоритетах.

## Шаг 9. Построй только первый рабочий вертикальный срез

После аудита выбери самый маленький полезный фрагмент, который можно проверить. Приоритет: один локальный MP4 из вручную одобренных или собственных ассетов, без автоматической публикации.

Проверь, что рабочий процесс охватывает:

`research → script → source-backed claims → asset plan → license ledger → EDL → render → technical QA → human review`.

Для каждого ассета должны быть зафиксированы исходный URL, автор, точные условия/лицензия, дата получения, разрешённое коммерческое использование, атрибуция, изменения и SHA-256. Неясный материал — в карантин; не использовать как финальный ассет.

Используй FFmpeg/ffprobe для простого монтажа. Remotion, очередь, API-автозагрузка и дополнительные сервисы не внедряй без конкретной необходимости. Выполни существующие тесты до изменений и подходящие тесты после; если проверить что-либо невозможно, поставь `NOT_CHECKED`.

## Шаг 10. Настрой обязательный протокол каждой задачи

Для каждой задачи классифицируй запрос и используй алгоритм:

1. Найди и прочитай активные инструкции.
2. Проверь доступные Skills и выбери только все применимые. Для фабрики сначала проверь `youtube-factory-orchestrator`, затем подходящие specialist Skills.
3. Проверь реально доступные инструменты/MCP; не выдумывай вызовы.
4. Изучи текущий код/файлы и сформулируй план для нетривиальной задачи.
5. Сделай небольшой проверяемый diff.
6. Запусти подходящие проверки и укажи реальные результаты.
7. При подтверждённой повторяющейся проблеме обнови Lessons/Backlog/Evals; глобальные правила и разрешения меняй только через review.
8. В финале перечисли изменённые файлы, фактически использованные Skills/MCP, проверки PASS/FAIL/NOT_CHECKED и оставшиеся риски.

## Шаг 11. Выполни контрольные задания

Подготовь и выполни безопасные проверки, доступные в текущей среде:

- небольшой баг/изменение кода с тестом;
- изучение неизвестного API по официальной документации;
- сценарий YouTube с проверяемыми источниками;
- ассет с неясной лицензией, который должен быть отклонён/помещён в карантин;
- техническая проверка существующего тестового видео, если доступно;
- задача, где YouTube Skills не нужны, чтобы проверить отсутствие лишней загрузки;
- безопасная проверка публикационного процесса, доказывающая, что публичная загрузка не запускается без подтверждения.

Не симулируй запуск тестов, ffprobe, MCP или публикацию. Если файлы или среда не позволяют выполнить проверку, зафиксируй её как `NOT_CHECKED` и назови, что требуется.

## Что предоставить в итоговом отчёте

1. Статус каждого комплекта: `INSTALLED`, `PARTIAL`, `FAILED` или `NOT_CHECKED` с доказательствами.
2. Точные пути установленных глобальных инструкций и Skills.
3. Список активных инструкций и разрешённых изменений, резервные копии и план отката.
4. Список доступных MCP и фактически проверенных вызовов; отдельно — предлагаемые, но не подключённые MCP.
5. Что найдено в проекте фабрики: `implemented/partial/missing/broken/not verified`.
6. Тесты, команды и реальные результаты, включая `NOT_CHECKED`.
7. Какие контрольные задачи прошли/не прошли и исходный baseline, если он доступен.
8. Следующий самый маленький шаг, не предлагая полную перепись проекта.

Начинай с аудита и резервных копий. Затем без лишней бюрократии установи безопасную файловую часть двух комплектов, активируй правила, проверь Skills и реализуй первый минимальный этап, который действительно возможен в текущем репозитории. Не останавливайся после создания плана, но не обходи отдельное разрешение для внешних MCP, секретов, расширения прав или публикации.
`````

### RESOURCE FILE: `README_MASTER_RU.md`

`````markdown
# Объединённый мастер-комплект Kilo Code + OpenMontage Factory

В комплект входят оба исходных набора, мастер-план и единый промпт для Kilo Code.

## Что где находится

- `MASTER_PLAN_RU.md` — порядок внедрения от безопасного аудита до проверенной YouTube-фабрики.
- `MASTER_PROMPT_KILO_CODE_RU.md` — основной промпт, который следует вставить в Kilo Code.
- `INSTALL_CHECKLIST_RU.md` — что проверить после установки.
- `01-kilo-self-improvement-kit/` — исходный комплект для глобальных инструкций, самоулучшения, Evals, Lessons и Backlog.
- `02-youtube-factory-kilo-kit/` — исходный комплект из 8 YouTube Skills, шаблонов и правил OpenMontage Factory.
- `original-zips/` — исходные архивы без изменений.

## Рекомендуемый запуск

1. Сделайте резервную копию проекта OpenMontage Factory и убедитесь, что важные изменения сохранены в Git или другом месте.
2. Распакуйте этот мастер-комплект.
3. Скопируйте **всю распакованную папку** `kilo-youtube-master-kit` в корень проекта OpenMontage Factory, например по пути `tools/kilo-youtube-master-kit/`. Важно сохранить рядом мастер-план, главный промпт и обе папки исходных комплектов.
4. Откройте именно репозиторий OpenMontage Factory в Kilo Code. Если проекта фабрики ещё нет, сначала выберите папку, где он должен быть создан.
5. Вставьте короткий промпт из `START_HERE_PROMPT_RU.md` в Kilo Code. Он направит агента прочитать полный `MASTER_PROMPT_KILO_CODE_RU.md` и выполнить его.
6. Разрешайте только ожидаемые операции с резервными копиями. Для установки MCP/плагинов, OAuth, API-токенов, расширения разрешений или изменений активного YouTube-канала требуйте отдельный обзор конфигурации.
7. После перезапуска Kilo выполните контрольные задачи из `INSTALL_CHECKLIST_RU.md`.

## Важное ограничение

Инструкции и Skills делают поведение более устойчивым, но не меняют веса модели и не гарантируют идеальное следование каждому правилу. Поэтому комплект включает проверку фактической загрузки Skills, контрольные задания, фиксацию результатов и правила отката.
`````

### RESOURCE FILE: `START_HERE_PROMPT_RU.md`

`````markdown
# Стартовый промпт для Kilo Code

Открой и полностью прочитай файл `tools/kilo-youtube-master-kit/MASTER_PROMPT_KILO_CODE_RU.md`. Если путь отличается, найди этот файл по имени в текущей рабочей области. Также прочитай `MASTER_PLAN_RU.md` и `INSTALL_CHECKLIST_RU.md` в той же папке.

Не пересказывай документы и не останавливайся на одном плане: выполни инструкции главного промпта в доступной среде — сначала аудит и резервные копии, затем безопасная установка обоих комплектов, подключение реально активных инструкций, проверка всех девяти Skills и первые доступные контрольные задачи.

Работай с открытым репозиторием OpenMontage Factory. Не выдумывай пути, результаты команд, загруженные Skills или доступность MCP. Если какой-либо комплект не найден, сообщи точный недостающий путь и продолжай только те безопасные действия, для которых данных достаточно.

Моя цель — устойчивое использование релевантных Skills и проверок на каждой подходящей задаче; не загружай YouTube Skills в нерелевантных задачах. Установку Skills и объединение инструкций выполняй с резервными копиями. Не заменяй целиком `kilo.json`/`kilo.jsonc`. Перед новыми MCP/плагинами, OAuth/API-токенами, новыми разрешениями или изменением активного YouTube-канала — сначала покажи обоснование, права и точный diff и запроси отдельное разрешение. Публично ничего не публикуй.

В конце предоставь проверяемый отчёт: точные пути, созданные резервные копии, найденные и реально проверенные Skills/MCP, команды и результаты, пункты `PASS/FAIL/NOT_CHECKED`, изменения в проекте и план отката.
`````
