# REPO_AUDIT_V8 — Инвентаризация репозитория OpenMontage (V8)

Дата: 2026-11-07
Статус: Этап 1 — инвентаризация (только просмотр, ничего не удалено)
Диск: 96% использования (~1.3 GB свободно) — критично

## Методология

Каждый путь верхнего уровня и крупный файл проверен на:
1. **Реальные импорты/ссылки** в `lib/`, `scripts/`, `tools/`, `qc/` (grep по имени пути/модуля)
2. **Принадлежность к Stickman-эре** (до пивота на гибридный реалистичный стиль)
3. **Время создания/изменения** (git log или дата на диске)
4. **Размер** (du -sh)

## Сводка по категориям

| Категория | Количество путей | Общий размер |
|-----------|-----------------|--------------|
| ACTIVE | ~20 | ~150 MB (без docs/openmontage, assets/, projects/) |
| STICKMAN_ERA_UNUSED | 13 | ~4.3 MB |
| UNKNOWN_ORIGIN | 18 | ~30 MB |
| TEST_ARTIFACT | 4 | ~2 MB |

---

## Детальная таблица

### lib/ — ACTIVE

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| lib/ | 1.8 MB | ACTIVE | Ядро библиотеки: checkpoint, state_store, render_integration, audio_mixer, audio_mixing, scene_router, motion_director, tts_engine, color_match, claim_ledger, human_review, music_dramaturgy, storyboard, audio_master, flow_job_manager, pipeline_loader, config_model, batch_scheduler | Оставить |

### scripts/ — ACTIVE

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| scripts/ | 1.1 MB | ACTIVE | Конвейер V8: run_factory.py, run_episode.py, run_episode_images.py, assemble_pilot_final*, build_shot_list, build_contact_sheets_klein, package_youtube, new_episode_scaffold, backlot_*, s1-s15 bake-off скрипты | Оставить |

### tools/ — ACTIVE

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| tools/ | 120 MB | ACTIVE | kaggle_bridge (генерация изображений на Kaggle T4), video (video_compose, remotion_caption_burn), audio, illustration, prompting, graphics, motion, analysis, capture, subtitle, publishers, enhancement | Оставить |

### qc/ — ACTIVE

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| qc/ | - | ACTIVE | Контроль качества (qc.py, thresholds) | Оставить |

### remotion-composer/ — ACTIVE

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| remotion-composer/ | 636 KB | ACTIVE | Текущий рендер-движок (Remotion v26, @remotion/cli ^4.0.484). Ссылки: scripts/run_factory.py, scripts/assemble_pilot_final*, scripts/atelier_snapshots.py, scripts/package_youtube.py, tools/video/video_compose.py, tools/video/remotion_caption_burn.py, lib/render_engine.py | Оставить |

### pipeline_defs/ — ACTIVE

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| pipeline_defs/ | 144 KB | ACTIVE | YAML манифесты конвейера: factory.yaml, cinematic.yaml, documentary-montage.yaml, hybrid.yaml и др. Ссылки: lib/pipeline_loader.py, scripts/run_factory.py | Оставить |

### schemas/ — ACTIVE

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| schemas/ | 276 KB | ACTIVE | JSON-схемы: pipelines, checkpoints, artifacts (publish_package, render_report, scene_plan, fact_check_report и др.). Ссылки: lib/playbook_generator.py, tools/analysis/video_analyzer.py | Оставить |

### styles/ — ACTIVE

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| styles/ | 56 KB | ACTIVE | Плейбуки стилей для иллюстраций. Ссылки: lib/checkpoint.py, lib/playbook_generator.py, lib/config_model.py, tools/video/video_compose.py, tools/illustration/style_kit.py, tools/kaggle_bridge/s15_style_lock_run.py | Оставить |

### config/ — ACTIVE

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| config/ | 36 KB | ACTIVE | qc_thresholds.json, image_engine.json, voice.json, mcp-allowlist-*.env. Ссылки: scripts/run_episode.py, scripts/f2_qc.py, scripts/creature_sheet.py, scripts/s10_push_style_test.py, scripts/s10_build_testset.py, scripts/image_engine.py, scripts/run_illustrations.py, scripts/f2_tts_edl.py | Оставить |

### assets/music/ — ACTIVE

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| assets/music/ | 47 MB | ACTIVE | Лицензированная музыка (Public Domain / CC0). Ссылки: lib/checkpoint.py (стр. 228), lib/budget_guard.py (стр. 90), scripts/run_factory.py (стр. 908), scripts/scaffold_atelier_project.py (стр. 53) | Оставить |

### assets/ (другие файлы) — UNKNOWN_ORIGIN

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| assets/signal-from-tomorrow-demo.mp4 | 20 MB | UNKNOWN_ORIGIN | Нет ссылок в lib/scripts/tools. Дата на диске: 31 окт 2026 (до сессии V8). Не в git. Происхождение неизвестно | Нужно решение владельца |
| assets/showcase.jpg | 272 KB | UNKNOWN_ORIGIN | Нет ссылок в lib/scripts/tools | Нужно решение владельца |
| assets/social_preview.png | 176 KB | UNKNOWN_ORIGIN | Нет ссылок в lib/scripts/tools | Нужно решение владельца |
| assets/logo.png | 128 KB | UNKNOWN_ORIGIN | Нет ссылок в lib/scripts/tools | Нужно решение владельца |

### projects/ — ACTIVE

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| projects/pilot/ | 24 MB | ACTIVE | Пилотный эпизод first_video (уже очищен: оставлен только final.mp4, прошедший QC). Ссылки: scripts/package_youtube.py, scripts/run_factory.py | Оставить |

### docs/openmontage/ — ACTIVE

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| docs/openmontage/ | 12 MB | ACTIVE | Источник истины V8: скрипты, claim ledgers, стиль ниши, рецепт изображений, evidence ledger, FACTORY_GAP_AUDIT, FACTORY_ARCHITECTURE и др. slice/ уже заархивирован и удалён | Оставить |

### docs/images/ — UNKNOWN_ORIGIN

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| docs/images/ | 2.7 MB | UNKNOWN_ORIGIN | Нет ссылок в *.py файлах. Содержит только подпапку backlot/. Git log: один коммит (811480d, backlot README/screenshot) | Нужно решение владельца |

### docs/ (корневые файлы) — ACTIVE / UNKNOWN_ORIGIN

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| docs/FACTORY_TECHNICAL_AUDIT.md | 24 KB | ACTIVE | Технический аудит фабрики | Оставить |
| docs/FACTORY_IMPLEMENTATION_ROADMAP.md | 24 KB | ACTIVE | Дорожная карта внедрения | Оставить |
| docs/OPENMONTAGE_FACTORY_MASTER_PLAN_RU (1).md | 52 KB | ACTIVE | Мастер-план фабрики | Оставить |
| docs/OPENMONTAGE_WORK_LOG.md | 88 KB | ACTIVE | Журнал работ | Оставить |
| docs/PROJECT_PLAN.md | 68 KB | ACTIVE | План проекта | Оставить |
| docs/PROVIDERS.md | 68 KB | ACTIVE | Провайдеры | Оставить |
| docs/agent-improvement/ | 76 KB | ACTIVE | BACKLOG, CHANGELOG, EVALS, LESSONS, PROPOSALS_FOR_OWNER.md | Оставить |
| docs/audit/ | 44 KB | ACTIVE | Аудит | Оставить |
| Остальные *.md в docs/ | ~150 KB | UNKNOWN_ORIGIN | Различные отчеты (GFLOW_CLI, comfyui-adapter-plan, PILOT_OWNER_REVIEW, etc.) — не проверены на ссылки | Нужно решение владельца |

### backlot/ — ACTIVE

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| backlot/ | 176 KB | ACTIVE | Python-пакет (backlot/__init__.py, server.py, state.py, ui/). Используется в tests/backlot/*.py. Git history: активен (commits 9482edd, af87fc1, f633b5f, 4f9c612, 9f77aa2) | Оставить |

### .backlot/ — ACTIVE (runtime)

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| .backlot/ | - | ACTIVE | Runtime-директория для скриншотов backlot (screenshot-stage/). Ссылки: scripts/backlot_visual_eval.py, scripts/backlot_simulate_run.py, scripts/backlot_watch_captures.py, scripts/backlot_screenshot_stage.py | Оставить |

### flow_audit/, flow_queue/, flow_results/ — ACTIVE

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| flow_audit/ | 560 KB | ACTIVE | Ссылки: lib/flow_job_manager.py (стр. 116-120) | Оставить |
| flow_queue/ | 4 KB | ACTIVE | Ссылки: lib/flow_job_manager.py (стр. 116) | Оставить |
| flow_results/ | 4 KB | ACTIVE | Ссылки: lib/flow_job_manager.py (стр. 117) | Оставить |

### gflow-runtime/ — UNKNOWN_ORIGIN

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| gflow-runtime/ | 4 KB | UNKNOWN_ORIGIN | Пустая директория. Нет ссылок в lib/scripts/tools. Не в git history | Нужно решение владельца |

### jobs/ — UNKNOWN_ORIGIN

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| jobs/ | 28 KB | UNKNOWN_ORIGIN | Содержит demo_jobs.json. Нет ссылок в lib/scripts/tools. Git: "p6 tests and demo_jobs stub" | Нужно решение владельца |

### manifests/ — UNKNOWN_ORIGIN

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| manifests/ | 12 KB | UNKNOWN_ORIGIN | Содержит future_topics_footage_survey.json. Нет ссылок в lib/scripts/tools. Git: "p4 footage source survey for 4 future topics" | Нужно решение владельца |

### templates/ — UNKNOWN_ORIGIN

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| templates/ | 16 KB | UNKNOWN_ORIGIN | Содержит qa-report.json, video-job-manifest.json, asset-rights-ledger.csv. Нет ссылок на локальные файлы в коде (только внешний URL в comfyui_video.py). Git: "chore: save remaining skills, backlog, architecture docs, templates" | Нужно решение владельца |

### ink-theater/ — UNKNOWN_ORIGIN

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| ink-theater/ | 2.2 MB | UNKNOWN_ORIGIN | Нет ссылок в lib/scripts/tools. Дата на диске: не проверена | Нужно решение владельца |

### style1/ — UNKNOWN_ORIGIN

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| style1/ | 4.4 MB | UNKNOWN_ORIGIN | Нет ссылок в lib/scripts/tools. Git history: активен (b9d850a, 2db3625, 2f16b07, 9482edd — playbook_loader, anime-ghibli) | Нужно решение владельца |

### .agents/skills/hyperframes-media/ — STICKMAN_ERA_UNUSED

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| .agents/skills/hyperframes-media/ | 1.5 MB | STICKMAN_ERA_UNUSED | SFX-библиотека эпохи character-animation. Нет ссылок в lib/scripts/tools. Не используется в audio_mixer.py или audio_mixing.py (они принимают sfx_paths как параметр, а не жесткий путь к библиотеке) | Архивировать + удалить |

### Stickman-эра (корень репозитория) — STICKMAN_ERA_UNUSED

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| stick2_idtest/ | 16 KB | STICKMAN_ERA_UNUSED | Нет ссылок в lib/scripts/tools/qc. Только в лог-файлах корня. Git: 1da666a (pinned deps) | Архивировать + удалить |
| stick3_ipadapter/ | 1.4 MB | STICKMAN_ERA_UNUSED | Нет ссылок в lib/scripts/tools/qc. Git: 1da666a | Архивировать + удалить |
| stick4_1prompt1story_stick4-1prompt1story-1/ | 12 KB | STICKMAN_ERA_UNUSED | Нет ссылок в lib/scripts/tools/qc. Git: 1da666a | Архивировать + удалить |
| stick4_1prompt1story_stick4-1prompt1story-2/ | 1.5 MB | STICKMAN_ERA_UNUSED | Нет ссылок в lib/scripts/tools/qc. Git: 1da666a | Архивировать + удалить |
| stick4_ipadapter_fixed_stick4-ipadapter-fixed-1/ | 12 KB | STICKMAN_ERA_UNUSED | Нет ссылок в lib/scripts/tools/qc. Git: 1da666a | Архивировать + удалить |
| stick4_ipadapter_fixed_stick4-ipadapter-fixed-2/ | 32 KB | STICKMAN_ERA_UNUSED | Нет ссылок в lib/scripts/tools/qc. Git: 1da666a | Архивировать + удалить |
| stick4_ipadapter_plus/ | 1008 KB | STICKMAN_ERA_UNUSED | Нет ссылок в lib/scripts/tools/qc. Git: 1da666a | Архивировать + удалить |
| stick4-1prompt1story.log | 16 KB | STICKMAN_ERA_UNUSED | Лог-файл stickman-эры. Нет ссылок в коде | Архивировать + удалить |
| stick4-ipadapter-fixed.log | 32 KB | STICKMAN_ERA_UNUSED | Лог-файл stickman-эры. Нет ссылок в коде | Архивировать + удалить |
| openmontage-stick2-id-test.log | 2 KB | STICKMAN_ERA_UNUSED | Лог-файл stickman-эры | Архивировать + удалить |
| openmontage-stick2-id-test-v2.log | 6 KB | STICKMAN_ERA_UNUSED | Лог-файл stickman-эры | Архивировать + удалить |
| openmontage-stick2-id-test-v3.log | 7 KB | STICKMAN_ERA_UNUSED | Лог-файл stickman-эры | Архивировать + удалить |
| openmontage-stick3-ipadapter-v3.log | 25 KB | STICKMAN_ERA_UNUSED | Лог-файл stickman-эры | Архивировать + удалить |
| openmontage-style1-cheyenne-flux.log | 14 KB | STICKMAN_ERA_UNUSED | Лог-файл stickman-эры | Архивировать + удалить |
| openmontage-style1-cheyenne-flux-v2.log | 14 KB | STICKMAN_ERA_UNUSED | Лог-файл stickman-эры | Архивировать + удалить |

**Итого STICKMAN_ERA_UNUSED: ~4.3 MB**

### Root JSON файлы — UNKNOWN_ORIGIN

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| apollo_11.json | 153 KB | UNKNOWN_ORIGIN | Нет ссылок в lib/scripts/tools | Нужно решение владельца |
| artemis_sls.json | 296 KB | UNKNOWN_ORIGIN | Нет ссылок в lib/scripts/tools | Нужно решение владельца |
| cassini_saturn.json | 30 KB | UNKNOWN_ORIGIN | Нет ссылок в lib/scripts/tools | Нужно решение владельца |
| dart_asteroid.json | 66 KB | UNKNOWN_ORIGIN | Нет ссылок в lib/scripts/tools | Нужно решение владельца |
| hubble_space_telescope.json | 228 KB | UNKNOWN_ORIGIN | Нет ссылок в lib/scripts/tools | Нужно решение владельца |
| james_webb_space_telescope.json | 245 KB | UNKNOWN_ORIGIN | Нет ссылок в lib/scripts/tools | Нужно решение владельца |
| osiris_rex.json | 214 KB | UNKNOWN_ORIGIN | Нет ссылок в lib/scripts/tools | Нужно решение владельца |
| parker_solar_probe.json | 70 KB | UNKNOWN_ORIGIN | Нет ссылок в lib/scripts/tools | Нужно решение владельца |
| voyager.json | 87 KB | UNKNOWN_ORIGIN | Нет ссылок в lib/scripts/tools | Нужно решение владельца |

**Итого корневые JSON: ~1.4 MB**

### Root утилиты — UNKNOWN_ORIGIN / TEST_ARTIFACT

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| render_demo.py | 4.6 KB | UNKNOWN_ORIGIN | Только self-reference (def render_demo вызывает самого себя). Нет импортов из других скриптов | Нужно решение владельца |
| render-demo.sh | 242 B | UNKNOWN_ORIGIN | Нет ссылок в коде | Нужно решение владельца |
| Makefile | 7.4 KB | UNKNOWN_ORIGIN | Нет ссылок в *.py файлах. Возможно используется через `make` напрямую | Нужно решение владельца |
| setup.py | 463 B | ACTIVE | Стандартный Python packaging файл | Оставить |
| config.yaml | 896 B | UNKNOWN_ORIGIN | Нет ссылок в *.py файлах (lib/config_model.py загружает config.yaml, но это другой файл в корне) | Нужно решение владельца |

### DONE.json / status.txt — ACTIVE (runtime)

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| DONE.json | 215 B | ACTIVE | Ссылки: scripts/s15_collect.py, scripts/f2_collect.py, scripts/s14_assemble.py, scripts/s12_collect.py | Оставить |
| status.txt | 49 B | ACTIVE | Ссылки: scripts/s15_collect.py, scripts/s7_fetch.py, scripts/s14_assemble.py, scripts/s12_collect.py | Оставить |

### Hidden директории — инфраструктура среды

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| .claude/ | 3.9 MB | UNKNOWN_ORIGIN | Локальные настройки Claude Code. Не часть V8 кода | Нужно решение владельца |
| .mypy_cache/ | 3.0 MB | TEST_ARTIFACT | Кэш mypy. Уже в .gitignore | Удалить (кэш) |
| .kilo/ | 440 KB | UNKNOWN_ORIGIN | Конфиг Kilo. Не часть V8 кода | Нужно решение владельца |
| .codex/ | 24 KB | UNKNOWN_ORIGIN | Конфиг Codex | Нужно решение владельца |
| .cursor/ | 28 KB | UNKNOWN_ORIGIN | Конфиг Cursor | Нужно решение владельца |
| .opencode/ | 24 KB | UNKNOWN_ORIGIN | Конфиг Opencode | Нужно решение владельца |
| .devcontainer/ | 8 KB | ACTIVE | Dev container конфиг | Оставить |
| .github/ | 72 KB | ACTIVE | GitHub Actions, шаблоны PR | Оставить |

### TEST_ARTIFACT (kaggle_bridge jobs)

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| tools/kaggle_bridge/jobs/consistency-ab-test/ | - | TEST_ARTIFACT | Результаты теста консистентности (A/B тест). См. RESULTS.md — требуется просмотр владельцем | Архивировать + удалить |
| tools/kaggle_bridge/jobs/character-benchmark/ | - | TEST_ARTIFACT | Benchmarkキャラクター. См. report.md | Архивировать + удалить |
| tools/kaggle_bridge/jobs/flux2-klein-test/ | - | TEST_ARTIFACT | Тест Flux2 Klein. См. test_protocol.json | Архивировать + удалить |
| tools/kaggle_bridge/jobs/k3-v3-host-variations/ | - | TEST_ARTIFACT | Вариации хостов K3. См. run.py | Архивировать + удалить |

### Stickman-эра в tools/kaggle_bridge/ — требует решения владельца

| Путь | Размер | Статус | Обоснование | Рекомендация |
|------|--------|--------|-------------|--------------|
| tools/kaggle_bridge/jobs/stick4-ipadapter-fixed-2/ | 1016 KB | UNKNOWN_ORIGIN | Ссылки: tools/kaggle_bridge/stick4_ipadapter_fixed.py (который не вызван основными скриптами конвейера) | Нужно решение владельца |
| tools/kaggle_bridge/jobs/stick4-1prompt1story-2/ | 1012 KB | UNKNOWN_ORIGIN | Ссылки: tools/kaggle_bridge/stick4_1prompt1story.py (который не вызван основными скриптами конвейера) | Нужно решение владельца |

### Ветка archive/stickman-concept-v4

Существует ветка `archive/stickman-concept-v4` (локально и на origin). При пивоте на гибридный реалистичный стиль stickman-концепция была заархивирована туда. Корневые stickman-папки можно удалить из рабочей ветки со ссылкой на эту архивную ветку.

---

## Итог Этапа 1

**Можно безопасно архивировать и удалить (STICKMAN_ERA_UNUSED, ~4.3 MB):**
- 15 путей в корне репозитория (stick2_idtest/, stick3_ipadapter/, stick4_* папки, *.log файлы)

**Требует решения владельца (UNKNOWN_ORIGIN, ~30 MB):**
- ink-theater/, style1/, gflow-runtime/, jobs/, manifests/, templates/
- assets/signal-from-tomorrow-demo.mp4, assets/showcase.jpg, assets/social_preview.png, assets/logo.png
- Корневые JSON файлы (apollo_11.json и др., ~1.4 MB)
- docs/images/, render_demo.py, render-demo.sh, Makefile, config.yaml
- .claude/, .kilo/, .codex/, .cursor/, .opencode/
- tools/kaggle_bridge/jobs/stick4-ipadapter-fixed-2/, tools/kaggle_bridge/jobs/stick4-1prompt1story-2/

**TEST_ARTIFACT (~2 MB):**
- tools/kaggle_bridge/jobs/consistency-ab-test/, character-benchmark/, flux2-klein-test/, k3-v3-host-variations/

---

## Следующие шаги (Этап 2)

После утверждения этого аудита:
1. Архивировать STICKMAN_ERA_UNUSED в один tar.gz, выгрузить, удалить из рабочего дерева
2. Архивировать TEST_ARTIFACT в один tar.gz, выгрузить, удалить из рабочего дерева
3. UNKNOWN_ORIGIN не трогать — ждать решения владельца
4. ACTIVE не трогать
