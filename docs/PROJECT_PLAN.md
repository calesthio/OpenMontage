# PROJECT_PLAN — YouTube канал "Образование и наука" (science-grounded speculation)

**Пилот:** «What Would Life Look Like on an Ocean Planet With No Land?», 20–21 мин, 10 разделов, одна иллюстрация на предложение.
**Репозиторий:** OpenMontage (форк calesthio/OpenMontage), ветка `kilo/mega-100`.
**Режим:** только чтение, аудит. Ничего не устанавливается, не коммитится, не запускается на GPU.
**Лицензия репозитория:** GNU AGPL v3 (LICENSE, корень).

---

## 1. Карта архитектуры

### 1.1 Компоненты и где что запускается

| Уровень | Компонент | Путь | Где запускается | Назначение |
|---------|-----------|------|-----------------|------------|
| Вход | Сценарий пилота | `docs/openmontage/pilot/script.md` | Codespace (чтение) | 214 предложений, 214 PROMPT, 10 разделов, 20:36 |
| Вход | Реестр утверждений | `docs/openmontage/evidence/S1_SPECULATIVE_CLAIM_LEDGER.md` | Codespace (чтение) | SE-01 … SE-13 |
| Вход | Стиль ниши | `docs/openmontage/niches/speculative_evolution/style.json`, `STYLE_BIBLE.md` | Codespace (чтение) | Префикс/хвост/негатив |
| Вход | Рецепт картинок | `docs/openmontage/image_gen/recipe_dreamshaper_xl_1_0.json` | Codespace (чтение) | DreamShaper XL 1.0, 25 шагов, CFG 5.5, fp16 |
| Оркестрация | Episode runner | `scripts/run_episode.py` | Codespace | 13 стадий, state-файл, гейты |
| Оркестрация | EDL builder | `scripts/build_episode_edl.py` | Codespace | edit_decisions.json + render_manifest + rights/credits |
| Оркестрация | Images driver | `scripts/run_episode_images.py` | Codespace | Батчи, resume, retry, манифест |
| Оркестрация | Zero-cost gate | `lib/zero_cost_gate.py` | Codespace | Запрет необъявленных/неоплаченных маршрутов |
| Изображения | Image brief | `tools/illustration/image_brief.py` | Codespace | Script -> brief (по битам) |
| Изображения | Episode run | `tools/illustration/episode_run.py` | Codespace (планирование) / Kaggle T4 (генерация) | Бюджет, батчи 40–100, resume, retry, манифест |
| Изображения | Illustration QC | `tools/illustration/illustration_qc.py` | Codespace | Чёрные/NaN/блюр/текст/дубли/палитра |
| Изображения | Style kit | `tools/illustration/style_kit.py` | Codespace | Префикс/хвост/негатив стиля |
| Изображения | Pilot EDL | `tools/illustration/pilot_edl.py` | Codespace | EDL из скрипта + манифеста картинок |
| Изображения | Kaggle bridge | `tools/kaggle_bridge/kaggle_bridge.py` | Codespace (CLI) / Kaggle T4 (ядро) | Submit / poll / fetch / verify / qc |
| Изображения | Jobs | `tools/kaggle_bridge/jobs/` (stick4-*) | Kaggle T4 | Зарегистрированные ядра |
| Аудио | Kokoro TTS | `tools/audio/kokoro_tts.py` | Codespace (CPU) | Kokoro-82M, af_heart, 24 кГц |
| Аудио | Finish audio | `tools/audio/finish_audio.py` | Codespace (CPU) | −14 LUFS / −1.5 dBTP |
| Аудио | Narrate helper | `scripts/kokoro_torch_narrate.py` | Codespace (CPU) | Вызывается из run_episode |
| Субтитры | Forced alignment | `scripts/fw_subtitles.py` | Codespace | SRT |
| Монтаж А | Video compose (ffmpeg) | `tools/video/video_compose.py` | Codespace | Используется run_episode.cmd_render |
| Монтаж Б | Remotion | `remotion-composer/` | Codespace (Node) | Используется отдельными скриптами, в run_episode НЕ подключён |
| QA | QC checks | `tools/qa/qc.py` | Codespace | 16 проверок |
| QA | Thresholds | `config/qc_thresholds.json` | Codespace | Пороги (initial guesses) |
| Гейты | Speculative gate, release gate, package draft | `run_episode` | Codespace | Гейты перед публикацией |

### 1.2 Поток данных (canonical path, `scripts/run_episode.py`)

```
script.md ──parse──► beats/sentences ──► image_brief.json ──► план батчей
                                                            │
                                                    Kaggle T4 (3 ядра) │
                                                            ▼
                                                    PNG + manifest.json (sha256, seeds, VRAM)
                                                            │
                                                    illustration_qc │
                                                            ▼
                                    illustration_manifest.json (label, rights_basis=ai_generated_illustration)
                                                            │
narration.wav (Kokoro) ──► narration_manifest.json          │
subtitles.srt                                             │
                                                            ▼
build_episode_edl.py ──► edit_decisions.json + render_manifest.json
                                                            │
                                                            ▼
video_compose (ffmpeg) ──► final_<topic>_draft.mp4
                                                            │
                                                            ▼
qc.py ──► qa_report.json ──► release_gate ──► package_draft (метаданные, БЕЗ публикации)
```

### 1.3 Расхождения «заявленное vs реализованное»

| Заявлено владельцем | Что в коде |
|---------------------|------------|
| DreamShaper XL 1.0 | `config/image_engine.json` → `model: "klein"` (FLUX.2-klein-4B); записи `dreamshaper-xl-1-0` в `models` нет |
| Bold ink стиль | `niches/speculative_evolution/style.json` → `field_guide_plate`, «flat vector» |
| Remotion монтаж | `run_episode.cmd_render` использует `video_compose.py` (ffmpeg); Remotion в `run_episode` не подключён |
| 214 иллюстраций | `episode_run.py` лимит 6–8 изображений/мин → 123–165, а не 214 |
| 100% AI-видео | `qc.py` по умолчанию `ai_label_max_share: 0.15` — 100% AI не проходит |

---

## 2. Текущее состояние

### 2.1 Сводная таблица по стадиям

| # | Стадия | Статус | Доказательство (путь) |
|---|--------|--------|----------------------|
| 1 | Сценарий | ГОТОВО (как текст) | `docs/openmontage/pilot/script.md`: 214 предложений, 3 090 слов, 20:36 @150 wpm, 214 PROMPT, SE-01…SE-13 |
| 2 | Реестр утверждений | ГОТОВО | `docs/openmontage/evidence/S1_SPECULATIVE_CLAIM_LEDGER.md` |
| 3 | Парсер сценария | **СЛОМАНО** | `tools/illustration/image_brief.py:96`, `tools/illustration/pilot_edl.py:228,263`, `scripts/run_episode.py:407` — ждут буллеты/таблицы, не `S001 [ID]` + `PROMPT:` |
| 4 | Конфиг модели | **СЛОМАНО** | `config/image_engine.json` (model=klein, нет dreamshaper-xl-1-0 в `models`) |
| 5 | Стиль | **СЛОМАНО** (устарел) | `niches/speculative_evolution/style.json`, `STYLE_BIBLE.md` — `field_guide_plate`, не `graphic-novel-ink` |
| 6 | Рецепт картинок | ГОТОВО | `docs/openmontage/image_gen/recipe_dreamshaper_xl_1_0.json` (25 steps, CFG 5.5, DEIS, fp16) |
| 7 | Измерения модели | ГОТОВО | S12: 18/18 годных, 0 black/NaN, 25.5 s/img, 9 968 MB alloc / 12 828 MB reserved |
| 8 | Пакетная генерация | ГОТОВО по коду | `tools/illustration/episode_run.py`, `tools/illustration/kaggle_episode_bridge.py` |
| 9 | Kaggle-мост | ГОТОВО по коду, НЕ ПРОВЕРЕНО запуском | `tools/kaggle_bridge/kaggle_bridge.py` |
| 10 | Narration (Kokoro) | КОД ЕСТЬ, окружение отсутствует | `tools/audio/kokoro_tts.py`, `/tmp/kilo` пуст |
| 11 | Субтитры | НЕ ПРОВЕРЕНО | `scripts/fw_subtitles.py` |
| 12 | EDL | КОД ЕСТЬ, зависит от парсера | `scripts/build_episode_edl.py`, `tools/illustration/pilot_edl.py` |
| 13 | Рендер ffmpeg | НЕ ПРОВЕРЕНО (нет ffmpeg) | `tools/video/video_compose.py` |
| 14 | Рендер Remotion | НЕ ПРОВЕРЕНО (нет node_modules) | `remotion-composer/` |
| 15 | QA | КОД ЕСТЬ, пороги конфликтуют | `tools/qa/qc.py`, `config/qc_thresholds.json` |
| 16 | Права/лицензии | ЧАСТИЧНО | `docs/openmontage/image_gen/LICENSE_EVIDENCE.md`, `licenses/` |
| 17 | Музыка | ПОЛИТИКА: без музыки | `docs/openmontage/MUSIC_POLICY.md` |
| 18 | Публикация | НЕ РЕАЛИЗОВАНО | `docs/openmontage/youtube-publishing-analytics-STUB.md` |

### 2.2 Что работает (проверено чтением кода/измерениями)

- Сценарий: 10 разделов, 214 предложений, 214 уникальных `PROMPT:`, `[NARRATIVE]` в §5, §7, §8.
- Рецепт и измерения: `recipe_dreamshaper_xl_1_0.json` — DreamShaper XL 1.0, revision `41e6644…`, DEIS, 25 шагов, CFG 5.5, fp16. S12: 18/18 без чёрных/NaN; S15: 42/42, 0 NaN, 1344×768.
- Kaggle-мост: `kaggle_bridge.py` реализует submit/poll/fetch/verify, `_scrub_token` чистит токен.
- Пакетная логика: `episode_run.py` — батчи 40–100, resume по sha256, повтор только упавших, hard fail при недоборе.
- Права: `rights_basis=ai_generated_illustration`, метка «Speculative illustration» с первого кадра.
- Zero-cost gate: `lib/zero_cost_gate.py` блокирует необъявленные маршруты.

### 2.3 Что сломано (с точными местами)

**Б1. Парсер не понимает формат пилота.**
Все три парсера ждут `- предложение [id]` или markdown-таблицу, а не `S001 [ID]` + `PROMPT:`:
- `scripts/run_episode.py:407` `_parse_script_rows`
- `tools/illustration/pilot_edl.py:228` `sentence_rows`
- `tools/illustration/pilot_edl.py:263` `script_sections`
- `tools/illustration/image_brief.py:96` `parse_script`
Следствие: `rows=[]` → 0 предложений в манифесте, 0 битов в EDL, 0 промптов в brief. Требуется новый адаптер формата.

**Б2. Реестр моделей не знает DreamShaper XL 1.0.**
`config/image_engine.json`: `"model": "klein"`, `models` = klein, sdxl-lightning, dreamshaper-xl-lightning, sdxl, zimage. Записи `dreamshaper-xl-1-0` нет. `scripts/build_episode_edl.py:73` по умолчанию `--model klein`.

**Б3. Стиль противоречит S15.**
`style.json`: `field_guide_plate`, `flat-vector`, `locked_model=klein`. Требуется `graphic-novel-ink` (S15 winner).

**Б4. Бюджет изображений несовместим с 214 картинками.**
`tools/illustration/episode_run.py:38-40`: 6–8 img/min → 123–165 для 20.6 мин. 214 картинок = 10.4 img/min → `BudgetError` (строка 200).

**Б5. QA-пороги гарантированно валят пилот.**
- `tools/qa/qc.py:401` и `:1135`: `ai_label_max_share` = 0.15 → 100% AI видео → FAIL.
- `scripts/run_episode.py:876`: `cmd_qc` не передаёт `ai_label_max_share`.
- `config/qc_thresholds.json`: `graphics_per_90s_min: 1.0` → 0.73 на 1 236 с → FAIL.

**Б6. `import soundfile` ломает `registry.discover()`.**
`tools/audio/kokoro_tts.py:23` — верхнеуровневый импорт. Без `soundfile` падает весь реестр инструментов.

**Б7. Окружение не готово.**
| Компонент | Факт |
|-----------|------|
| ffmpeg, ffprobe | отсутствуют |
| kaggle CLI | отсутствует |
| pytest | отсутствует |
| soundfile, kokoro | отсутствуют |
| remotion-composer/node_modules | отсутствует |
| /tmp/kilo (venv) | пуст |
| Python | 3.14.2 (рецепт: 3.13.15) |
| torch локально | 2.14.1+cpu (рецепт: 2.11.0+cu128) |
| diffusers / transformers | 0.37.0 / 4.57.6 — совпадают |
| Node / npm | 24.21.0 / 11.19.0 — есть |
| Диск | 32 ГБ всего, 15 ГБ свободно |
| KAGGLE_API_TOKEN | приStringствет (имя только) |

**Б8. Нет пайплайна под научную спекуляцию.**
В `pipeline_defs/` нет `science-explainer` или `speculative-science`. Ближайший — `animated-explainer.yaml`.

**Б9. Remotion не подключён к эпизодному раннеру.**
`run_episode.cmd_render` → `video_compose.py` (ffmpeg). Remotion только отдельными скриптами.

**Б10. Нет `projects/` и F2-рендера с реальными кадрами.**
Единственный видеоартефакт — `docs/openmontage/smoke/p0_smoke.mp4` (espeak-ng, не Kokoro). Полного прогона не было.

---

## 3. Цель и критерии готовности пилота

**Цель:** YouTube-канал в нише Education & Science, позиционирование "science-grounded speculation". Пилот: 20–21 мин, 10 разделов, DreamShaper XL 1.0 (bold ink), Kokoro af_heart, Remotion/ffmpeg монтаж, тяжёлая генерация на Kaggle T4. Только FOSS и коммерчески разрешённые лицензии.

Пилот считается готовым, когда **все** пункты D1–D15 выполнены и подтверждены артефактом. Любой невыполненный пункт = NOT_READY, отсутствие проверки = NOT_CHECKED (не PASS).

| ID | Критерий | Порог | Подтверждение |
|----|----------|-------|---------------|
| D1 | Видеофайл | 1920×1080, H.264 + AAC, 24/30 fps, 1 236 ± 6 с | `ffprobe` + `qa_report.json` |
| D2 | Полный декод | 0 ошибок декодирования | `full_decode` |
| D3 | Narration | 214/214, 24 кГц, −14 ± 2 LUFS, TP ≤ −1.5 dBTP, silence ≤ 10% | `ebur128`, `silencedetect`, `narration_manifest.json` |
| D4 | Субтитры | 214 реплик, дрейф ≤ 0.5 с, 0 расхождений | `subtitle_sync` |
| D5 | Картинки | 214/214 файлов, sha256 совпадает, 0 black/NaN, ≥ 190 (≥89%) проходят QC | `illustration_manifest.json` + `illustration_qc` |
| D6 | Стиль | 100% промптов с префиксом/хвостом/негативом; 0 кадров с текстом; дрейф палитры ≤ 70 | `text_detect`, `palette_drift` |
| D7 | Монтаж | 214 склеек + ≥ 14 графических событий; нет still-only > 15 с; ≥ 3 типа движения | `motion_variety`, `edit_decisions.json` |
| D8 | Плотность графики | ≥ 1.0 события / 90 с (≥ 14 на 1 236 с) | `graphics_per_90s_min` |
| D9 | Права | 214/214 rights records (модель + revision + лицензия + sha256); `credits.txt` полон | `rights_basis`, `credits_complete` |
| D10 | Claim'ы | 100% claim_id в леджере; `[NARRATIVE]` не claim | `claim_ids`, `claim_ids_resolve` |
| D11 | Метка AI | метка на каждом AI-кадре + в описании; решение по `ai_label_max_share` | `speculative_label`, `ai_illustration_label` |
| D12 | QA-вердикт | `verdict: PASS`, ни одной NOT_RUN/BLOCKED | `qa_report.json` |
| D13 | Zero-cost | гейт PASS, 0 платных маршрутов | `zero_cost_gate` |
| D14 | Воспроизводимость | 10 случайных картинок, тот же seed → тот же sha256 | повторный мини-прогон |
| D15 | Пакет | title/description/tags/thumbnail готовы, статус `draft`, публикации нет | `package_draft` |

---

## 4. Риски и пробелы

### 4.1 Лицензии (главный риск)

| ID | Объект | Факт | Риск | Что делать |
|----|--------|------|------|------------|
| L1 | Remotion | кастомная лицензия, не FOSS (бесплатно для физлиц, ≤3 сотрудников, некоммерческих) | противоречие «только FOSS» | Решение владельца O1; альтернатива — ffmpeg или HyperFrames (Apache-2.0) |
| L2 | DreamShaper XL 1.0 | OpenRAIL++ (не OSI FOSS, коммерческое использование разрешено с ограничениями) | ограничения использования + передача downstream | Решение владельца O2; текст лицензии в репозитории |
| L3 | Kokoro-82M | веса Apache-2.0; CC BY в обучающих данных (Koniwa tnc, SIWIS); синтетика UNKNOWN | атрибуция, неопределённость синтетики | Решение владельца O3; блок атрибуции |
| L4 | SDXL-продукты | OpenRAIL++ | то же, что L2 | не использовать в пилоте |
| L5 | FLUX.2-klein | Apache-2.0, стиль не тот | — | вывести из пилотного пути |
| L6 | Шрифты | `@remotion/google-fonts` тянет сетевые шрифты | офлайн-рендер + лицензия | OFL-шрифт локально (Inter / JetBrains Mono, OFL-1.1) |
| L7 | Музыка | политика: без музыки | «royalty-free» ≠ разрешение | без музыки на пилоте |
| L8 | FFmpeg | LGPL vs GPL в зависимости от сборки | несовместимость с FOSS маловероятна | зафиксировать `ffmpeg -version` |

### 4.2 VRAM и железо (Kaggle T4, ~14.56 ГБ доступных)

| ID | Риск | Данные | Митигация |
|----|------|--------|-----------|
| V1 | Голова под адаптеры отсутствует | DreamShaper: 9 968 MB alloc / 12 828 MB reserved | не ставить IP-Adapter/InstantID; консистентность — seed+промпт |
| V2 | VAE-decode OOM | IP-Adapter Plus: пик 13.9 ГБ → 0/3 | `vae_fallback` только при black/NaN; без tiling |
| V3 | Batch > 100 не поддержан | `episode_run.py:52` | 3 батча по 72/71/71 |
| V4 | Лимит ядра 90 мин | `MAX_WALL_SECONDS = 5400` | 3 отдельных ядра, resume по манифесту |

### 4.3 Диск и окружение

| ID | Риск | Данные |
|----|------|--------|
| S1 | Мало места | 15 ГБ свободно; рендер + node_modules + 214 PNG |
| S2 | Локальный torch не тот | 2.14.1+cpu vs 2.11.0+cu128 → локально невоспроизводимо |
| S3 | Python 3.14.2 vs 3.13.15 | бинарные колёса (torch, kokoro) могут отсутствовать |
| S4 | `soundfile` ломает `registry.discover()` | `tools/audio/kokoro_tts.py:23` |

### 4.4 Секреты

| ID | Риск | Статус |
|----|------|--------|
| K1 | `KAGGLE_API_TOKEN` в окружении | присутствует, значение не читалось |
| K2 | `.env` в git | `.gitignore` исключает — ок |
| K3 | Токен в артефактах ядра | `kaggle_bridge._scrub_token` чистит; требует проверки |
| K4 | OAuth YouTube | не настроен, не нужен на пилоте |

### 4.5 Версии и зависимости

| Пакет | Рецепт (GPU) | Локально | Совместимость |
|-------|-------------|----------|---------------|
| diffusers | 0.37.0 | 0.37.0 | ок |
| transformers | 4.57.6 | 4.57.6 | ок |
| huggingface_hub | 0.36.2 | не проверено | — |
| torch | 2.11.0+cu128 | 2.14.1+cpu | **расхождение** |
| Python | 3.13.15 | 3.14.2 | **расхождение** |
| Node | — | 24.21.0 | ок |

### 4.6 Процессные риски

| ID | Риск |
|----|------|
| P1 | PR #837 (809 файлов, +139k) не отревьюен, не смержен |
| P2 | Заголовок в файле не совпадает с темой владельца |
| P3 | `projects/` отсутствует — нет канонического корня проекта |
| P4 | QC-обход порогов «на словах» → фиктивный PASS |
| P5 | Нет F2-рендера с реальными кадрами — все тайминги расчётные |

### 4.7 Результаты A/B-теста консистентности персонажа (Kaggle T4)

Прогон `tools/kaggle_bridge/jobs/consistency-ab-test/` (ядро `forts845/om-consistency-ab-test`, версия 6, 2026-10-26), протокол `test_protocol.json`. База — **SDXL Base 1.0** (DreamShaper XL не зафиксирован в `docs/openmontage/image_gen/LICENSE_EVIDENCE.md` → не используется как база, см. Шаг 0 протокола). Запрещено: IP-Adapter FaceID, PhotoMaker V2, PuLID (InsightFace), Character LoRA.

| Тест | Конфигурация | OOM | Картин | Пик VRAM | Вердикт |
|------|-------------|-----|--------|----------|---------|
| A — baseline | SDXL Base 1.0, 768×768, fp16, vae_slicing+tiling+model_cpu_offload, без адаптера | Нет | 45/45 | 5 196 МБ | **Пройден (контрольная точка)** |
| B — Plus Face | A + `ip-adapter-plus-face_sdxl_vit-h` (scale 0.7) | Нет | 0/45 | 5 106 МБ | Не пригоден (ошибка интеграции `image_embeds` с diffusers 0.40) |
| C — Plus full-body | A + `ip-adapter-plus_sdxl_vit-h` (scale 0.7) | Нет | 0/45 | 5 106 МБ | Не пригоден (та же ошибка интеграции) |
| D — комбинация | A + Plus (0.7) + Plus Face (0.25) | Нет | 0/45 | 9 945,9 МБ | Не пригоден (пик близко к лимиту T4 14,56 ГБ) |

Тесты Б/В не упали с OOM (пик снизился с утренних 13,9 ГБ до 5 106 МБ благодаря оптимизациям памяти), но не выпустили ни одной картинки из-за несовместимости `h94/IP-Adapter` с `diffusers 0.40` (ошибки размерности/типа/ранга `image_embeds`). Тест Г не имеет смысла пока Б/В не отработают.

**Итог:** единственная рабочая конфигурация без OOM — Тест A. Рекомендация для пилота: использовать Тест A как базу, консистентность персонажа — фиксированный seed + единый промпт (O8 вариант «а»); IP-Adapter-консистентность — отдельный timebox после пилота. Детальный отчёт: `tools/kaggle_bridge/jobs/consistency-ab-test/RESULTS.md`.

---

## 5. План по фазам

Размеры: **S** ≤ 0.5 дня, **M** 0.5–1.5 дня, **L** > 1.5 дня (включая ожидание GPU).

### Фаза 0 — Фиксация базовой линии (S)

| Поле | Значение |
|------|----------|
| Задачи | Зафиксировать версии и хеши: сценарий, рецепт, S15-манифест, `qc_thresholds.json`, `image_engine.json`; записать матрицу окружения |
| Файлы | Новый `docs/openmontage/pilot/BASELINE.md` |
| Приёмка | все пины и sha256 записаны; матрица «локально / Kaggle» заполнена; 0 изменений в коде |
| Субагент | `evidence-checker` (сверка фактов), проверка — `qa-reviewer` |
| Риск | нет |

### Фаза 1 — Адаптер формата пилота (M) — **блокирующая**

| Поле | Значение |
|------|----------|
| Задачи | Новый модуль `tools/illustration/pilot_script.py`: парсит `S<NNN> [ID]` + `PROMPT:`; отдаёт `{sections, sentences, prompts, claim_ids}`; валидирует нумерацию, уникальность промптов, резолв claim_id в леджере |
| Файлы | `tools/illustration/pilot_script.py` (новый), `tests/illustration/test_pilot_script.py` (новый), подключение: `scripts/run_episode.py:407`, `tools/illustration/pilot_edl.py:228,263`, `tools/illustration/image_brief.py:96` |
| Приёмка | 214 предложений, 10 разделов, 214 промптов, 0 неизвестных claim_id; старый формат (буллеты/таблицы) не сломан — тест на регрессию |
| Субагент | оркестратор (нет субагента с правом писать `tools/**`); приёмка — `qa-reviewer` |
| Риск | средний: три парсера, легко получить расхождение; тест обязателен |

### Фаза 2 — Сведение конфигов и стиля (S) — **блокирующая**

| Поле | Значение |
|------|----------|
| Задачи | Добавить в `config/image_engine.json` запись `dreamshaper-xl-1-0` (revision, DEIS, 25/5.5, fp16, VAE stock, лицензия, измерения S12/S15); переключить `model`; привести `style.json` и `STYLE_BIBLE.md` к `graphic-novel-ink`; убрать `klein` из пилотного пути; `build_episode_edl.py --model` по умолчанию = `dreamshaper-xl-1-0` |
| Файлы | `config/image_engine.json`, `docs/openmontage/niches/speculative_evolution/style.json`, `.../STYLE_BIBLE.md`, `scripts/build_episode_edl.py:73`, `docs/openmontage/image_gen/EPISODE_IMAGE_PIPELINE.md`, `IMAGE_MODULE_SPEC.md` |
| Приёмка | один источник истины: рецепт = конфиг = стиль = сценарий; `python scripts/image_engine.py status` показывает `dreamshaper-xl-1-0`; grep по `klein` в пилотном пути пуст |
| Субагент | оркестратор; независимая сверка — `qa-reviewer` |
| Риск | средний: правки в 6 файлах, нужен дифф-ревью |

### Фаза 3 — Производство 214 изображений (L)

| Поле | Значение |
|------|----------|
| Задачи | job-файл на базе `s15_style_lock_run.py` с `model_config` из рецепта; 3 батча 72/71/71; seed-лог на каждую картинку; `DONE.json` в `finally`; fetch + verify sha256; `illustration_qc`; ретраи только упавших (≤ 2 на картинку) |
| Файлы | `tools/kaggle_bridge/jobs/pilot-ds-xl-1-0-{1,2,3}/`, `scripts/run_episode_images.py`, состояние в `projects/<pilot>/` |
| Приёмка | 214/214 verified; 0 black/NaN; ≥ 190 (≥89%) проходят QC с первой попытки; суммарно ≤ 110 мин GPU; манифест содержит model/revision/seed/sha256 |
| Субагент | оркестратор (запуск), `qa-reviewer` (сверка манифеста и QC), `footage-scout` — не нужен (нет внешних ассетов) |
| Риск | высокий: OOM, чёрные кадры, квоты, обрыв ядра |

### Фаза 4 — Narration и субтитры (M) — параллельна фазе 3

| Поле | Значение |
|------|----------|
| Задачи | Поднять venv `/tmp/kilo/z1_venv` по `docs/openmontage/z1_voice_venv.requirements.txt`; 214 предложений через `kokoro_tts` (`af_heart`, CPU); `finish_audio` до −14 LUFS; forced alignment → SRT |
| Файлы | `scripts/run_episode.py:311` (`cmd_narration`), `tools/audio/kokoro_tts.py`, `scripts/kokoro_torch_narrate.py`, `scripts/fw_subtitles.py` |
| Приёмка | WAV 24 кГц; −14 ± 2 LUFS; TP ≤ −1.5 dBTP; 214 реплик; дрейф ≤ 0.5 с; 20 контрольных терминов проверено вручную |
| Субагент | оркестратор; замеры — `qa-reviewer` |
| Риск | средний: Python 3.14 + бинарные колёса; `af_heart` может спотыкаться на латинице/числах |

### Фаза 5 — EDL и монтаж (L)

| Поле | Значение |
|------|----------|
| Задачи | `build_episode_edl.py` на реальном манифесте; 10 карточек разделов + ≥ 4 доп. графических события (для D8); чередование движений; per-cut rationale + claim_id; затем рендер |
| Файлы | `scripts/build_episode_edl.py`, `tools/illustration/pilot_edl.py`, `tools/video/video_compose.py` |
| Приёмка | D1, D7, D8; каждое решение о склейке имеет rationale; ни одного still-only > 15 с |
| Субагент | `editor` (пишет только `projects/**/edit/**` и EDL) |
| Риск | средний: длительность 20:36 в ±6 с |

### Фаза 6 — QA и пакет (M)

| Поле | Значение |
|------|----------|
| Задачи | Прогон 16 проверок; **файл-обход** порогов (`config/qc_pilot_override.json`) с подписью владельца: `ai_label_max_share: 1.0`, `graphics_per_90s_min: 0.73` — только если O5 выбран вариант «обход»; собрать `credits.txt`, `rights_records.json`, метаданные |
| Файлы | `tools/qa/qc.py`, `config/qc_thresholds.json` / новый override, `scripts/run_episode.py:870` |
| Приёмка | D9–D13, D15; `qa_report.json` без `NOT_RUN`/`BLOCKED` |
| Субагент | `qa-reviewer` (единственный, кто пишет `qa_report.json`) |
| Риск | высокий: любой NOT_RUN = BLOCKED, а не PASS |

### Фаза 7 — Опционально: консистентность персонажа (M, timebox 1 ядро)

| Поле | Значение |
|------|----------|
| Задачи | Одно ядро-эксперимент: 9 референсов, замер VRAM; сравнить 3 подхода только на 3 сценах |
| Приёмка | go/no-go с измеренным пиком VRAM; при OOM — ветка закрывается навсегда |
| Субагент | оркестратор + `qa-reviewer` |
| Риск | высокий; IP-Adapter Plus давал 13.9/14.56 ГБ (OOM) |

---

## 6. Параллельно vs строго последовательно

### 6.1 Жёсткая последовательность

```
Фаза 0 → Фаза 1 → Фаза 2 → Фаза 3 ─┐
                                   ├→ Фаза 5 → Фаза 6 → пакет
                        Фаза 4 ────┘
```

Обоснование:
- **1 → 2**: без парсера нельзя проверить применение конфига к 214 промптам.
- **2 → 3**: генерация с `klein` даст 214 картинок не в той модели/стиле — деньги/время впустую.
- **3 и 4 → 5**: EDL требует и длительности озвучки, и реальные файлы картинок.
- **5 → 6**: QA проверяет готовый MP4; раньше запускать нечего.
- **6 → пакет**: метаданные должны ссылаться на проверенный рендер.

### 6.2 Параллельно

| Задача A | Задача B | Почему безопасно |
|----------|----------|------------------|
| Фаза 3 (GPU) | Фаза 4 (CPU, Kokoro) | независимые ресурсы и файлы |
| Фаза 3 | Пакет атрибуции/лицензий (L1–L3) | только текст, не влияет на рендер |
| Фаза 4 | Черновик title/description/thumbnail | опирается на замороженный сценарий |
| Фаза 5 (ffmpeg) | Спайк Remotion в отдельном worktree | не пересекаются по файлам |
| Фаза 6 | Расширение QA (override-файл) | разные файлы; вердикт — только после рендера |

### 6.3 Правила конфликтов

1. Один файл — один писатель. `config/image_engine.json` правит только оркестратор (фаза 2).
2. `qa_report.json` пишет только `qa-reviewer`.
3. EDL/`edit_decisions.json` — только `editor`.
4. `evidence-checker` и `footage-scout` почти не задействованы: внешних ассетов нет, все картинки — AI.
5. Любая параллельная ветка работает в отдельном worktree; мерж — после приёмки.

---

## 7. Решения, которые должен принять владелец

(ни одно не принято — не принимаю их за владельца)

| ID | Вопрос | Варианты | Влияние | Рекомендация |
|----|--------|----------|---------|--------------|
| O1 | Remotion не FOSS. Принимаем? | (а) принять (физлицо/≤3 сотрудников); (б) заменить на ffmpeg; (в) заменить на HyperFrames (Apache-2.0) | Фаза 5, юридическая чистота | (а), если применимо; иначе (б) |
| O2 | DreamShaper XL 1.0 — OpenRAIL++, не OSI | (а) принять как «commercially permitted, not FOSS»; (б) искать OSI-модель | Лицензионный режим пилота | (а) + текст лицензии в репозитории |
| O3 | Kokoro: CC BY в данных + неизвестная синтетика | (а) подписать + атрибуция; (б) сменить голос | Описание видео, юридический риск | (а) + блок атрибуции |
| O4 | 214 картинок vs бюджет 6–8 img/min | (а) поднять до 10.4; (б) сократить до 165; (в) оставить 214 + расширить лимит | Объём GPU, ритм монтажа | (а) — «одна на предложение» |
| O5 | QA: 100% AI + плотность графики | (а) override-файл `ai_label_max_share=1.0` + 4 события; (б) override и по плотности | Честность гейта | (а): метку оставить, плотность событиями |
| O6 | Заголовок | (а) «What Would Life Look Like on an Ocean Planet With No Land?»; (б) текущий в файле | Метаданные, thumbnail, сценарий | (а) как тема канала, (б) как подзаголовок |
| O7 | Музыка | (а) без музыки; (б) лицензированный трек | Тон, права | (а) на пилоте |
| O8 | Консистентность персонажа | (а) только seed+промпт; (б) timebox на 1 ядро | Качество, риск OOM | (а) сейчас, (б) после пилота |
| O9 | Голос | `af_heart` единственный | Единообразие | подтвердить `af_heart` |
| O10 | Канонический рендер | (а) ffmpeg `video_compose` (подключён); (б) Remotion | Сроки, лицензия | (а) для пилота, (б) второй путь после O1 |
| O11 | Квоты Kaggle | 3 ядра / ~96 мин GPU в неделю | Сроки | подтвердить доступ и окно |
| O12 | Раскрытие AI | (а) метка на каждом кадре + в описании; (б) только в описании | Политика YouTube, доверие | (а) |

---

## 8. Кандидатные скиллы/плагины/MCP (только список, ничего не устанавливать)

| Кандидат | URL | Лицензия (проверена по LICENSE) | Что даёт | Вердикт |
|----------|-----|---------------------------------|----------|---------|
| Remotion | https://github.com/remotion-dev/remotion | кастомная Remotion License (LICENSE в репо), не FOSS | Motion-графика, уже в репо | Использовать только после O1 |
| HyperFrames | https://www.npmjs.com/package/hyperframes | Apache-2.0 (LICENSE в npm-пакете) | HTML→MP4, замена Remotion при лицензионном блоке | Кандидат-страховка |
| OpenTimelineIO | https://github.com/AcademySoftwareFoundation/OpenTimelineIO | Apache-2.0 (LICENSE) | Обмен EDL/OTIO с `editor` | Кандидат, не обязателен |
| auto-editor | https://github.com/WyattBlue/auto-editor | Unlicense (LICENSE) | Авто-трим тишины, анализ темпа | Не нужен: озвучка синтезируется точно |
| stable-ts | https://github.com/jianfch/stable-ts | MIT (LICENSE) | Запасной путь субтитров, если forced alignment упадёт | Кандидат |
| WhisperX | https://github.com/m-bain/whisperX | BSD-2-Clause (LICENSE) | Word-level timestamps | Кандидат, тяжелее stable-ts |
| faster-whisper | https://github.com/SYSTRAN/faster-whisper | MIT (LICENSE) | Локальная проверка субтитров | Кандидат для QA |
| Silero VAD | https://github.com/snakers4/silero-vad | MIT (LICENSE) | Детект пауз для `silencedetect`-альтернативы | Кандидат |
| Kokoro-82M | https://huggingface.co/hexgrad/Kokoro-82M | Apache-2.0 (LICENSE на HF) + оговорки по данным | Уже выбран | Принят с оговоркой O3 |
| Inter / JetBrains Mono | https://github.com/rsms/inter, https://github.com/JetBrains/JetBrainsMono | OFL-1.1 (LICENSE) | Локальные шрифты вместо `@remotion/google-fonts` | Кандидат: убрать сетевую зависимость |
| FFmpeg | https://ffmpeg.org/legal.html | LGPL-2.1+ / GPL-2.0+ (в зависимости от сборки) | Рендер | Проверить `ffmpeg -version` на `--enable-gpl` |

**Не рассматриваются:** insightface, ArcFace, antelopev2, buffalo_l, InstantID, IP-Adapter-FaceID, PuLID, ConsiStory, StoryDiffusion, Z-Image-Turbo, FLUX (non-commercial) — исключены владельцем (PROJECT_PLAN §2.5, B5).

---

## 10. Статус внедрения Фазы B (субагенты и инфраструктура)

**Дата внедрения:** 2026-10-26
**Статус:** Внедрено и протестировано

### 10.1 Созданные субагенты (.kilo/agents/)

| Агент | Файл | Mode | Статус |
|-------|------|------|--------|
| license-checker | `.kilo/agents/license-checker.md` | subagent | Создан, YAML frontmatter валиден |
| kaggle-test-runner | `.kilo/agents/kaggle-test-runner.md` | subagent | Создан, YAML frontmatter валиден |
| dependency-guard | `.kilo/agents/dependency-guard.md` | subagent | Создан, YAML frontmatter валиден |
| git-hygiene | `.kilo/agents/git-hygiene.md` | subagent | Создан, YAML frontmatter валиден |
| plan-keeper | `.kilo/agents/plan-keeper.md` | subagent | Создан, YAML frontmatter валиден |
| code-reviewer | `.kilo/agents/code-reviewer.md` | subagent | Создан, YAML frontmatter валиден |
| niche-researcher | `.kilo/agents/niche-researcher.md` | subagent | Скопирован из `.opencode/agent/` (оригинал нетронут) |

### 10.2 Инфраструктурные защиты

| Компонент | Файл | Статус | Тест |
|-----------|------|--------|------|
| Pre-push хук | `.kilo/hooks/pre-push.sh` + `.git/hooks/pre-push` (symlink) | Создан, исполняем | ✅ Блокирует файл >90 МБ (exit code 1) |
| Права агентов | `.kilo/kilo.jsonc` | Создан | Config validation OK |

### 10.3 Результаты тестов (раздел B5 из AGENT_BUILD_PROPOSAL.md)

| Агент | Тест | Результат |
|-------|------|-----------|
| license-checker | Проверка на кейсе Cheyenne (style1/manifest.json) | Файл валиден, правила требуют точного имени проекта |
| kaggle-test-runner | Проверка синтаксиса YAML frontmatter | ✅ Валидно |
| dependency-guard | Проверка конфликта diffusers==0.40.0 vs закреплённое 0.37.0 | ✅ Конфликт обнаружен, будет заблокирован |
| git-hygiene | Тест 95 МБ файла через pre-push хук | ✅ Заблокирован (exit code 1), файл удалён после теста |
| code-reviewer | Проверка синтаксиса YAML frontmatter | ✅ Валидно |
| plan-keeper | Проверка синтаксиса YAML frontmatter | ✅ Валидно |

### 10.4 Статус пунктов из раздела 9 (проверка окружения)

| # | Пункт | Статус | Детали |
|---|-------|--------|--------|
| 1 | `pytest` в окружении | ✅ Установлен | pytest 9.1.1, 2578 тестов собраны, 5 ошибок сбора (ожидаемо без тестовых данных/ffmpeg ранее) |
| 2 | `kaggle` CLI и доступ к аккаунту | ✅ Работает | kaggle CLI 2.2.5 установлен, авторизация подтверждена (kaggle kernels list --mine вернул 15 ядер без ошибки 401/403) |
| 3 | `ffmpeg`/`ffprobe` | ✅ Установлен | ffmpeg 6.1.1-3ubuntu5, `--enable-gpl` подтвержден |
| 4 | `node_modules` + решение O1 | ✅ Решено | node_modules установлен (201 пакетов), Remotion Free License подтверждена владельцем (соло-проект, 1 человек, подпадает под Free License: individual, ≤3 сотрудников). Company License не требуется. |
| 5 | `/tmp/kilo/z1_venv` | ✅ Решено | venv создан на Python 3.12.3, kokoro==0.2.2 + misaki==0.7.4 установлены, импорт kokoro.KPipeline подтвержден |
| 6 | `.devcontainer/devcontainer.json` | ✅ Создан | Базовый образ python:3.12, Node.js LTS, postCreateCommand настраивает pre-push хук, z1_venv, pip install, npm install. Ожидает пересборки codespace для применения. |

**Примечание:** Файл `.devcontainer/devcontainer.json` создан и закоммичен. Для применения в текущем codespace необходимо пересобрать контейнер (Command Palette → "Rebuild Container"). В новых codespace применится автоматически.

### 10.5 Исправление несовпадения версий diffusers (Kaggle-ядро vs requirements-pinned.txt) — РЕАЛЬНЫЕ РЕЗУЛЬТАТЫ

**Причина провала тестов Б/В/Г:** несоответствие версий diffusers БЫЛО частью проблемы, но после pinning на 0.37.0 тесты Б/В/Г всё ещё не проходят — есть более глубокая несовместимость IP-Adapter с diffusers 0.37.0.

**Кодирование ядра consistency-ab-test (4 запуска на Kaggle T4):**

| Запуск | diffusers | ip_adapter_image_embeds формат | Тест A | Тест B (face) | Тест C (fullbody) | Тест D (комбо) |
|--------|-----------|-------------------------------|--------|---------------|-------------------|----------------|
| #1 | 0.40.0 (предустановлено) | 3D (с .unsqueeze(1)) | 45/45, 5196 MB | 0/45, ошибка интеграции | 0/45, ошибка интеграции | — |
| #2 | 0.37.0 (закреплено) | 3D (с .unsqueeze(1)) | 45/45, 5196 MB | 0/45, "not enough values to unpack (expected 2, got 1)" | 0/45, та же ошибка | 0/45, та же ошибка, пик 9946 MB |
| #3 | 0.37.0 (закреплено) | 2D (без .unsqueeze(1)) | 45/45, 5196 MB | 0/45, "ip_adapter_image_embeds has to be a list of 3D or 4D tensors but is 2D" | та же ошибка | та же ошибка |
| #4 | 0.37.0 (закреплено) | 3D + кортежи (key,value) | 45/45, 5196 MB | 0/45, "'tuple' object has no attribute 'ndim'" | та же ошибка | та же ошибка |

**Вывод:** Version pinning на diffusers 0.37.0 НЕ исправил IP-Adapter. Проблема глубже — внутренний код diffusers 0.37.0 при обработке `ip_adapter_image_embeds` пытается одновременно получить `.ndim` у тензора и распаковать его как `(key, value)`, что несовместимо с одним тензором. IP-Adapter Plus с h94/IP-Adapter не работает с diffusers 0.37.0 в текущей кодовой базе run.py.

**Тест A (базовый SDXL без IP-Adapter):** 45/45 картинок, пик VRAM 5196 МБ — работает стабильно во всех запусках.

**FLUX.2 Klein 4B разведка (ядро flux2-klein-test):**
- Статус: ФАИЛ при загрузке модели
- Ошибка: `Pipeline FluxPipeline expected ['feature_extractor', 'image_encoder', 'scheduler', 'text_encoder', 'text_encoder_2', 'tokenizer', 'tokenizer_2', 'transformer', 'vae'], but only {'vae', 'text_encoder', 'transformer', 'scheduler', 'tokenizer'} were passed.`
- Вывод: diffusers 0.37.0 не поддерживает `black-forest-labs/FLUX.2-klein-4B` — отсутствуют компоненты `feature_extractor`, `image_encoder`, `text_encoder_2`, `tokenizer_2`. FLUX.2 Klein не может быть использован с diffusers 0.37.0.

**Файлы результатов:**
- `tools/kaggle_bridge/jobs/consistency-ab-test/results_v*/consistency-ab-test/results.json` — результаты всех 4 запусков
- `tools/kaggle_bridge/jobs/flux2-klein-test/results/flux2-klein-test/results.json` — результат FLUX.2 Klein теста

---

## 9. Что проверить первым делом в следующей сессии

Все 6 пунктов проверки окружения закрыты:
1. `pytest` — ✅ установлен (9.1.1), 2578 тестов собраны
2. `kaggle` CLI — ✅ авторизован (15 ядер получены без ошибки)
3. `ffmpeg`/`ffprobe` — ✅ установлен (6.1.1-3ubuntu5, `--enable-gpl`)
4. `node_modules` + Remotion Free License — ✅ установлена, владелец подтвердил Free License (соло-проект)
5. `/tmp/kilo/z1_venv` — ✅ Python 3.12.3, kokoro==0.2.2, импорт OK
6. `.devcontainer/devcontainer.json` — ✅ создан, требует пересборки codespace для применения

**Новые блокирующие задачи:**
- IP-Adapter Plus с h94/IP-Adapter не работает с diffusers 0.37.0 — 4 запуска на Kaggle T4, все тесты Б/В/Д дают 0/45 картинок. Требуется альтернативный подход к консистентности персонажа (например, только seed+промпт, или другая модель адаптера).
- FLUX.2 Klein 4B не загружается на diffusers 0.37.0 (отсутствуют компоненты модели).

---

**Файл:** `docs/PROJECT_PLAN.md`
