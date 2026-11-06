# Автономное производство видео 20–25 мин — архитектура OpenMontage + gflow-cli

Концепция: **одно предложение сценария = одно уникальное ИИ-изображение**. Каждое предложение получает уникальный ID, текст озвучки, отдельный визуальный промпт, отдельное изображение, ссылку на аудиофрагмент, точное время начала/окончания и путь к файлу изображения.

Целевой ролик: 20–25 минут, английская аудитория, ~160–250 предложений, столько же уникальных изображений, формат 16:9, озвучка синхронизирована с изображениями, плавные движения камеры, музыка, финальный MP4.

## 1. Правило «одно предложение — одно изображение»

```
S001 — "The ocean covers most of our planet."  →  Изображение S001 (16:9)
S002 — "But its deepest regions remain mysterious."  →  Изображение S002 (16:9)
S003 — "Sunlight cannot reach these depths."  →  Изображение S003 (16:9)
```

Каждое изображение:
- уникально (нет повторов, нет дублей),
- соответствует именно этому предложению и общему контексту истории,
- генерируется отдельным вызовом `gflow image t2i` (или `gflow run` батчем).

## 2. Производственный конвейер (stage-by-stage)

```
idea → research → script → scene_plan → assets(gflow) → audio(TTS) → sync → edit → compose → QA → render MP4 → publish
```

Все этапы декларируются в `pipeline_defs/*.yaml`. Инструменты Discover через `tools/tool_registry.py`. Каждый этап пишет канонический артефакт в `projects/<project-id>/artifacts/` и чекпоинт в `projects/<project-id>/checkpoint_<этап>.json`.

## 3. Взаимодействие модулей OpenMontage с gflow-cli

| Модуль OpenMontage | Назначение | Связь с gflow-cli |
|---|---|---|
| `lib/script_analyzer.py` | Делит сценарий на смысловые блоки, выявляет научные утверждения, визуальные моменты, повторения | Генерирует список предложений с ID и текстом → источник промптов для gflow |
| `lib/sentence_segmenter.py` | Разбивает сценарий на предложения с уникальными ID `S001`…`S250+`, сохраняет текст, порядок, контекст абзаца | Источник ID и текста для промптов, аудио и изображений |
| `lib/scene_planner.py` | Maps блоки → сцены (размер кадра, движение, объектив, свет, композиция, переходы) | Формирует параметры `--aspect`, `--model`, motion-промпт для gflow image/video |
| `lib/visual_director.py` | Требует разнообразия ракурсов, места под подписи, композицию | Контролирует, что промпты не повторяют стиль/ракурс предыдущих сцен |
| `lib/character_consistency_manager.py` | Анатомия персонажа, референсы, проверка консистентности между сценами | Создаёт CHARACTER через `gflow character create`, передаёт `--reference-entity` в `gflow image t2i` / `gflow video t2v` |
| `lib/prompt_engineer.py` | Собирает пакеты основного/негативного промпта с визуальным фундаментом | Готовит текст промпта для каждой сцены, передаёт в `gflow image t2i` |
| **`lib/gflow_wrapper.py`** | **Безопасный subprocess-драйвер gflow-cli 0.92.0 (без shell=True)** | **Вызывает `gflow image t2i`/`gflow run --config`; парсит media_id/output_path/размеры; обрабатывает коды выхода 0/2/11/33; enforces zero-cost gate** |
| **`lib/gflow_provider.py`** | **Адаптер между движком изображений и gflow-cli** | **Планирует джобы на READY_FOR_APPROVAL; выполняет только после одобрения владельца** |
| **`lib/image_generation_engine.py`** | **Оркестратор: sentence → prompt → job → image → QC → asset** | **Ведёт полный конвейер генерации изображений: промпты, регистрация ассетов, планирование джобов, QC, обнаружение дубликатов** |
| `lib/quality_control.py` | 9 критериев QC на сцену (соответствие сценарию, научная точность, референс персонажа, дубли, анатомия, противоречия, 다양ность, нет текста, техническая пригодность) | Проверяет выход `gflow image t2i` перед принятием изображения |
| `lib/image_uniqueness.py` | Обнаружение ближайших дубликатов через aHash (расстояние Хэмма) | Помечает Near-duplicate изображения для переката |
| `lib/asset_registry.py` | Реестр активов: manifest.json, prompts.json, generation_jobs.json, assets/, qc_reports/, generation_logs/ | Один ассет на sentence_id; контроль целостности, уникальности ID, отсутствующих изображений |
| `lib/batch_scheduler.py` | Пакетный планировщик в рамках лимита gflow (макс 4 промпта/вызов, лимит параллелизма 1) | Разбивает 250 предложений на пакеты; отслеживает прогресс; поддерживает возобновление |
| `lib/recovery_manager.py` | Чекпоинт восстановления после перезапуска Codespace | `recovery_checkpoint.json`; пропускает завершённые; повторяет только неудачные |
| `lib/flow_integration.py` | Создаёт Flow-джобы, валидирует → READY_FOR_APPROVAL, без авто-отправки | Оборачивает вызовы `gflow image`/`gflow video`, останавливается перед кредитной операцией |
| `lib/flow_job_manager.py` | Жизненный цикл джобов: DRAFT → VALIDATED → READY_FOR_APPROVAL → APPROVED → SUBMITTED → COMPLETED/FAILED. Автоматизм стоп на READY_FOR_APPROVAL | Сохраняет job_id, status, content hash (SHA-256), предотвращает дубликаты |
| `lib/production_manifest.py` | Версионированный манифест (schema + SHA-256), блоки сцены/аудио/таймлайн | Записывает путь к каждому изображению, его SHA-256, длительность, позицию на таймлайне |
| `lib/audio_sync.py` | Связка сцены с фрагментом озвучки, обнаружение too_long/too_short, ручная коррекция | Связывает изображение S00N с аудиофрагментом S00N и временными метками |
| `lib/image_asset_pipeline.py` | Безопасный приём ассета, валидация, детекция дублей/повреждений, превью | Проверяет, что файл изображения от gflow существует, не пуст, корректен |
| `lib/motion_engine.py` | Спецификации движения: pan/zoom/parallax/static/chapter-card с разнообразием | Определяет параметры движения для Remotion/FFmpeg на этапе compose |
| `lib/render_integration.py` | 8-punkt проверка готовности, генерация edit-решений, тестовый рендер | Финальная сборка MP4 из изображений + аудио |

## 4. Поэтапный план автономного производства

### Этап A — Сценарий (без gflow)
1. Получить текст сценария на английском (~20–25 мин, 160–250 предложений).
2. `script_analyzer` разбивает на предложения с уникальными ID `S001`…`S250`.
3. Для каждого предложения: текст озвучки, оценка длительности (слова / 150 wpm).

### Этап B — Планирование сцен (без gflow)
1. `scene_planner` определяет для каждого предложения: framing, camera, lighting, mood, aspect=16:9.
2. `visual_director` проверяет разнообразие ракурсов (не более 2 одинаковых подряд).
3. `character_consistency_manager` создаёт/подтверждает персонажа (мастер-референс) через `gflow character create --project <ID> --name ... --face-prompt ... --body-prompt ...`.

### Этап C — Генерация изображений (gflow-cli) — РЕАЛИЗОВАН (P2)

Для каждого предложения `S00N` конвейер реализован в `lib/image_generation_engine.py`:

1. `sentence_segmenter` выдаёт `S00N` с текстом, оценкой длительности, порядком.
2. `prompt_engineer` собирает визуальный промпт (содержание предложения + стиль + камера + свет).
3. `gflow_provider.plan_image()` создаёт Flow-джоб на `READY_FOR_APPROVAL` — автосистема стоп; владелец одобряет вручную.
4. `asset_registry.register_asset()` связывает `sentence_id` → `asset_id` → `prompt_id` → `job_id` (один ассет на предложение).
5. После одобрения: `gflow image t2i "<промпт>" --aspect 16:9 --model nano2 -n 1 --out ...` (через `gflow_wrapper`, subprocess без shell=True).
6. `image_asset_pipeline` валидирует файл (существует, не пуст, корректное изображение, SHA-256).
7. `quality_control` проверяет 9 критериев; `image_uniqueness` проверяет aHash Near-dup.
8. Результат записывается в `production_manifest` и `asset_registry` (manifest.json, prompts.json, generation_jobs.json, qc_reports/).

Ограничение: `gflow image t2i` генерирует максимум 4 изображения за вызов, батч `gflow run` — до 50 промптов. Для 250 изображений нужно ~5–50 батчей в зависимости от конфига, последовательно, с `--resume` для восстановления. Все вызовы проходят через `zero_cost_gate` — неизвестная стоимость блокирует вызов.

Примерная структура проекта после P2:
```
projects/<id>/
├── manifest.json          # все ассеты + статус
├── prompts.json           # sentence_id → source prompt + prompt_id
├── generation_jobs.json   # job_id → запись джоба
├── assets/
│   └── S001.png ... S250.png   # по одному на предложение
├── qc_reports/            # S001.json ... S250.json
└── generation_logs/
```

### Этап D — Озвучка (без gflow)
1. TTS через Kokoro (venv `/tmp/kilo/z1_venv`, голос `af_heart`) — отдельный аудиофрагмент на каждое предложение.
2. Или ElevenLabs/Azure TTS (если настроены).
3. `audio_sync` связывает каждый аудиофрагмент с предложением S00N, фиксирует start/end время.

### Этап E — Синхронизация и монтаж (OpenMontage)
1. Каждое изображение S00N показывается в течение длительности аудио S00N.
2. `motion_engine` добавляет плавные pan/zoom/parallax на статичные изображения.
3. `render_integration` собирает таймлайн, генерирует edit-решения, проверяет готовность (8 пунктов).
4. Сборка через выбранный runtime (Remotion / HyperFrames / FFmpeg).

### Этап F — Финал (без gflow)
1. Музыкальный фон (из `music_library/` или API-генерация).
2. Субтитры (SRT, 2–5 с на фразу, ≤42 знака/строка).
3. Финальный рендер MP4 16:9.
4. QA: длительность 20–25 мин, синхронизация, качество, отсутствие чёрных кадров.

## 5. Точные команды gflow-cli для автономного производства

### Создание проекта Flow
```bash
gflow project create --project-name "Ocean Planet Documentary"
# или использовать существующий ID из `gflow project list`
```

### Создание персонажа (мастер-референс)
```bash
GFLOW_CLI_HEADLESS=true gflow character create --project <PROJECT_ID> --name "Host" \
  --face-prompt "bioluminescent deep-sea alien face, lantern-shaped glowing head" \
  --body-prompt "six long graceful tendrils, two pairs of small fins, deep navy and teal" \
  --model nano2 --json
```

### Генерация одного изображения (16:9)
```bash
GFLOW_CLI_HEADLESS=true gflow image t2i "<промпт предложения S00N>" \
  --aspect 16:9 --model nano2 -n 1 \
  --reference-entity <CHARACTER_ID> \
  --out projects/<id>/assets/images/
```

### Пакетная генерация (до 50 промптов)
```bash
# batch.json — см. схему в GFLOW_CLI_COMPLETE_GUIDE.md §8
GFLOW_CLI_HEADLESS=true gflow run --config batch.json \
  --output-dir projects/<id>/assets/images/ \
  --profile flow_remote --project <PROJECT_ID> --continue-on-error --resume
```

### Проверка результата
```bash
gflow data list                          # каталог сгенерированного
gflow data media <MEDIA_ID>              # метаданные файла
```

### Видео из изображения (если нужна анимация кадра)
```bash
GFLOW_CLI_HEADLESS=true gflow video i2v ./assets/images/S00N.png \
  "camera slowly pushes in" --aspect 16:9 --duration 8 --out-dir ./assets/video/
```

### Цепочка клипов
```bash
GFLOW_CLI_HEADLESS=true gflow video chain links.json --model veo-lite --aspect 16:9 --resume-from <CHAIN_ID>
```

## 6. Ограничения gflow-cli (установленная версия 0.92.0)

| Функция | Статус | Примечание |
|---|---|---|
| t2i (текст → изображение) | ✅ Доступно | 1–4 изображения, макс 2000 символов промпта |
| i2i (изображение → изображение) | ✅ Доступно | Требует `--ref`, ref_cap по модели |
| batch (до 5 промптов) | ✅ Доступно | `gflow image batch` |
| JSON-пакет (до 50 промптов) | ✅ Доступно | `gflow run --config` |
| upload изображения | ✅ Доступно | `gflow image upload` |
| upscale изображения | ✅ Доступно | 2k/4k, бесплатно |
| t2v (текст → видео) | ✅ Доступно | 1–4 клипа, duration 4/6/8/10 |
| i2v (кадр → видео) | ✅ Доступно | initial-frame/end-frame |
| r2v (референсы → видео) | ✅ Доступно | omni-flash=7 ref, lite/fast/lite-lp=3, quality=0 |
| chain (цепочка клипов) | ✅ Доступно | Только Veo 3.1 модели, не omni-flash |
| extend (продолжение +8с) | ✅ Доступно | До 30 сегментов, требует подтверждения |
| upscale видео | ✅ Доступно | 1080p/720p/270p GIF, платная операция |
| Персонажи (CHARACTER) | ✅ Доступно | create/list/show/rm/voices |
| movie.toml (многосценарийный фильм) | ✅ Доступно | `gflow movie run` |
| Генерация более 4 изображений за вызов | ❌ Недоступно | Лимит count=4; для сотен — батчи `gflow run` |
| Генерация видео 20+ мин напрямую | ❌ Недоступно | gflow генерирует клипы 4–10 сек; длинное видео собирается OpenMontage из изображений |
| Авто-оплата/трата кредитов | ⛔ Заблокировано | `--no-spend`, READ_ONLY_MODE, MCP Security Proxy, останов на READY_FOR_APPROVAL |

## 7. Обработка ошибок и восстановление

- **Сбой отдельного изображения:** `--continue-on-error` в `gflow run`; повторная генерация с другим промптом через `prompt_engineer`.
- **Прерванный батч:** `--resume` пропускает уже сохранённые строки.
- **Прерванная цепочка видео:** `gflow video chain --resume-from <CHAIN_ID>`.
- **Прерванный extend:** `gflow video extend --resume-from <SCENE_ID>`.
- **Повторное выполнение:** `gflow data errors` показывает историю неудач; `gflow data sync` восстанавливает каталог.
- **Дубликаты:** `flow_job_manager` предотвращает по job_id + content hash (SHA-256).
- **Проверка успеха:** файл существует, не пуст, корректное изображение/видео (ffprobe для видео, PIL для изображения), `gflow data media <id>` подтверждает запись в каталоге.

## 8. Сохранение и проверка результатов

Все артефакты под `projects/<project-id>/`:
```
projects/<project-id>/
├── artifacts/         # JSON артефакты этапов (brief, script, scene_plan, asset_manifest, edit_decisions, render_report)
├── assets/
│   ├── images/        # Изображения от gflow (PNG/JPG, 16:9)
│   ├── video/         # Клипы от gflow (MP4)
│   ├── audio/         # Озвучка (MP3/WAV)
│   └── music/         # Фоновая музыка
├── checkpoints/       # Чекпоинты этапов
├── renders/
│   └── final.mp4      # Финальное видео
└── project.json       # Маркер проекта
```

Проверка каждого изображения:
1. Файл существует и не пуст (>0 байт).
2. PIL открывает как изображение, разрешение 1376×768 (16:9) или иное целевое.
3. `gflow data media <MEDIA_ID>` подтверждает запись в локальном каталоге.
4. `quality_control` проходит 9 критериев.
5. SHA-256 записан в `production_manifest`.

## 9. Отказ от ответственности

Не тратьте кредиты без явного одобрения. Автоматизированная система останавливается на `READY_FOR_APPROVAL`; переход к `SUBMITTED` требует ручного одобрения человека. MCP Security Proxy и `GFLOW_MCP_NO_SPEND=1` блокируют кредитные инструменты на границе.
