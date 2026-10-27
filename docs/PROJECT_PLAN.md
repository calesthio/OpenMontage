# PROJECT_PLAN — YouTube канал "Образование и наука" (science-grounded speculation)

**Пилот:** «What Would Life Look Like on an Ocean Planet With No Land?», ~20–21 мин, 10 разделов, одна иллюстрация на предложение.
**Репозиторий:** OpenMontage (форк calesthio/OpenMontage), ветка `kilo/mega-100`, remote `origin = https://github.com/sora73636-stack/OpenMontage`.
**Лицензия репозитория:** GNU AGPL v3 (LICENSE, корень).
**Режим:** разработка пилота — установка разрешена, коммиты на `kilo/mega-100` через pre-push хук (блокировка файлов >90 МБ и секретов).

---

## 1. Карта архитектуры

### 1.1 Компоненты и где что запускается

| Уровень | Компонент | Путь | Где запускается | Статус | Назначение |
|---------|-----------|------|-----------------|--------|------------|
| Вход | Сценарий пилота | `docs/openmontage/pilot/script.md` | Codespace (чтение) | ГОТОВО | 214 предложений, 214 `PROMPT:`, 10 разделов, ~20:36 |
| Вход | Реестр утверждений | `docs/openmontage/evidence/S1_SPECULATIVE_CLAIM_LEDGER.md` | Codespace (чтение) | ГОТОВО | SE-01 … SE-13 |
| Вход | Стиль ниши | `docs/openmontage/niches/speculative_evolution/style.json`, `STYLE_BIBLE.md` | Codespace (чтение) | СЛОМАНО (устарел) | `field_guide_plate`, не `graphic-novel-ink` |
| Вход | Рецепт картинок | `docs/openmontage/image_gen/recipe_dreamshaper_xl_1_0.json` | Codespace (чтение) | ГОТОВО ( tekst) | 25 шагов, CFG 5.5, DEIS, fp16; ссылка на DreamShaper XL 1.0 не зарегистрирована в реестре моделей |
| Оркестрация | Episode runner | `scripts/run_episode.py` | Codespace | ЧАСТИЧНО | 13 стадий, state-файл, гейты; парсер сломан |
| Оркестрация | EDL builder | `scripts/build_episode_edl.py` | Codespace | КОД ЕСТЬ, не прогонялся | `edit_decisions.json` + `render_manifest` + права/кредиты |
| Оркестрация | Images driver | `scripts/run_episode_images.py` | Codespace | КОД ЕСТЬ, не прогонялся | Батчи, resume, retry, манифест |
| Оркестрация | Zero-cost gate | `lib/zero_cost_gate.py` | Codespace | ГОТОВО | Запрет необъявленных/неоплаченных маршрутов |
| Изображения | Image brief | `tools/illustration/image_brief.py` | Codespace | СЛОМАНО | Ожидает буллеты/таблицы, не `S001 [ID]` + `PROMPT:` |
| Изображения | Episode run | `tools/illustration/episode_run.py` | Codespace (планирование) / Kaggle T4 (генерация) | ГОТОВО по коду + ПРОВЕРЕНО запуском | Бюджет, батчи 40–100, resume по sha256, retry упавших |
| Изображения | Illustration QC | `tools/illustration/illustration_qc.py` | Codespace | КОД ЕСТЬ | Чёрные/NaN/блюр/текст/дубли/палитра |
| Изображения | Style kit | `tools/illustration/style_kit.py` | Codespace | КОД ЕСТЬ | Префикс/хвост/негатив стиля |
| Изображения | Pilot EDL | `tools/illustration/pilot_edl.py` | Codespace | СЛОМАНО | Ожидает другой формат сценария |
| Изображения | Kaggle bridge | `tools/kaggle_bridge/kaggle_bridge.py` | Codespace (CLI) / Kaggle T4 (ядро) | ГОТОВО + ПРОВЕРЕНО | submit/poll/fetch/output/logs; ядра `om-consistency-ab-test` (v12) и `pilot-frame-sdxl-baseline` выполнены на T4 |
| Изображения | Jobs | `tools/kaggle_bridge/jobs/` | Kaggle T4 | ГОТОВО | `consistency-ab-test/`, `pilot-frame-1b/`, `flux2-klein-test/` |
| Аудио | Kokoro TTS | `tools/audio/kokoro_tts.py` | Codespace (CPU) | ГОТОВО + ПРОВЕРЕНО | venv `/tmp/kilo/z1_venv`, `af_heart`, 24 кГц; синтезирован `narration.wav` §1 (83 с) |
| Аудио | Finish audio | `tools/audio/finish_audio.py` | Codespace (CPU) | КОД ЕСТЬ | −14 LUFS / −1.5 dBTP |
| Аудио | Narrate helper | `scripts/kokoro_torch_narrate.py` | Codespace (CPU) | КОД ЕСТЬ | Вызывается из `run_episode` |
| Субтитры | Forced alignment | `scripts/fw_subtitles.py` | Codespace | НЕ ПРОВЕРЕНО | SRT |
| Монтаж А | Video compose (ffmpeg) | `tools/video/video_compose.py` | Codespace | ffmpeg УСТАНОВЛЕН, не прогонялся на полном эпизоде | Используется `run_episode.cmd_render` |
| Монтаж Б | Remotion | `remotion-composer/` | Codespace (Node) | ГОТОВО + ПРОВЕРЕНО | `node_modules` установлен (201 пакетов); Remotion Free License подтверждена владельцем (соло-проект); составлен первый клип `out/pilot-scene-1.mp4`; в `run_episode` НЕ подключён |
| QA | QC checks | `tools/qa/qc.py` | Codespace | КОД ЕСТЬ, пороги конфликтуют | 16 проверок |
| QA | Thresholds | `config/qc_thresholds.json` | Codespace | КОНФЛИКТ | `ai_label_max_share: 0.15`, `graphics_per_90s_min: 1.0` — 100% AI видео не пройдёт |
| Гейты | Speculative gate, release gate, package draft | `run_episode` | Codespace | НЕ РЕАЛИЗОВАНО полностью | Гейты перед публикацией |

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
video_compose (ffmpeg) ──► final_<topic>_draft.mp4            Remotion ветка (отдельно):
                                                            │                                             кадр + аудио ──► out/pilot-scene-1.mp4
                                                            ▼
qc.py ──► qa_report.json ──► release_gate ──► package_draft (метаданные, БЕЗ публикации)
```

### 1.3 Расхождения «заявленное vs реализованное»

| Заявлено владельцем | Что в коде / что реально |
|---------------------|--------------------------|
| DreamShaper XL 1.0 как база | `config/image_engine.json` → `model: "klein"`; записи `dreamshaper-xl-1-0` в `models` нет. Реальная рабочая база — **SDXL Base 1.0** (45/45 картинок, 5.2 ГБ пик VRAM на T4). DreamShaper не используется (лицензия не зафиксирована в `LICENSE_EVIDENCE.md`). |
| Bold ink стиль | `style.json` → `field_guide_plate`, «flat vector»; требуется `graphic-novel-ink`. |
| Remotion монтаж | `run_episode.cmd_render` использует `video_compose.py` (ffmpeg). Remotion подключён отдельно: собран первый клип `pilot-scene-1.mp4`, в эпизодный раннер не встроен. |
| 214 иллюстраций | Сгенерировано 1 кадр пилота (S001, §1). Остальные 213 не сгенерированы. |
| 100% AI-видео | `qc.py` по умолчанию `ai_label_max_share: 0.15` — 100% AI не проходит; требуется override-файл с подписью владельца. |

---

## 2. Текущее состояние по стадиям

| # | Стадия | Статус | Доказательство (путь) |
|---|--------|--------|----------------------|
| 1 | Сценарий | ГОТОВО (как текст) | `docs/openmontage/pilot/script.md`: 214 предложений, 3 090 слов, ~20:36 @150 wpm, 214 `PROMPT:`, SE-01…SE-13 |
| 2 | Реестр утверждений | ГОТОВО | `docs/openmontage/evidence/S1_SPECULATIVE_CLAIM_LEDGER.md` |
| 3 | Парсер сценария | **СЛОМАНО** (блокирующая) | `tools/illustration/image_brief.py:96`, `tools/illustration/pilot_edl.py:228,263`, `scripts/run_episode.py:407` — ждут буллеты/таблицы, не `S001 [ID]` + `PROMPT:` |
| 4 | Конфиг модели | **СЛОМАНО** (требует переключения на SDXL Base 1.0) | `config/image_engine.json` (model=klein, dreamshaper-xl-1-0 не зарегистрирован) |
| 5 | Стиль | **СЛОМАНО** (устарел) | `style.json`, `STYLE_BIBLE.md` — `field_guide_plate`, не `graphic-novel-ink` |
| 6 | Рецепт картинок | ГОТОВО | `docs/openmontage/image_gen/recipe_dreamshaper_xl_1_0.json` |
| 7 | Измерения модели | ГОТОВО | SDXL Base 1.0 baseline: 45/45 годных, 0 black/NaN, пик VRAM 5 196 MB на 768×768 (4 независимых прогона на Kaggle T4) |
| 8 | Пакетная генерация | ГОТОВО по коду + ПРОВЕРЕНО запуском | `tools/illustration/episode_run.py`, `tools/illustration/kaggle_episode_bridge.py`; Kaggle ядра запускались и завершались |
| 9 | Kaggle-мост | ГОТОВО + ПРОВЕРЕНО | `tools/kaggle_bridge/kaggle_bridge.py`; push/status/fetch/output/logs работают; аккаунт forts845 (FORTS_FACTORY) авторизован, 15 ядер видны |
| 10 | Narration (Kokoro) | ГОТОВО + ПРОВЕРЕНО | `/tmp/kilo/z1_venv` (kokoro==0.2.2, KPipeline импортируется), `af_heart`; §1 синтезирован: `narration.wav`, 83.03 с, 24 кГц |
| 11 | Субтитры | НЕ ПРОВЕРЕНО | `scripts/fw_subtitles.py` |
| 12 | EDL | КОД ЕСТЬ, зависит от парсера | `scripts/build_episode_edl.py`, `tools/illustration/pilot_edl.py` |
| 13 | Рендер ffmpeg | ffmpeg УСТАНОВЛЕН (6.1.1-3ubuntu5, `--enable-gpl`), не прогонялся на полном эпизоде | `tools/video/video_compose.py` |
| 14 | Рендер Remotion | ГОТОВО + ПРОВЕРЕНО (proof-of-concept) | `remotion-composer/out/pilot-scene-1.mp4`: h264 1920×1080 + aac, 83 с, 6.4 МБ, ffprobe-валиден |
| 15 | QA | КОД ЕСТЬ, пороги конфликтуют | `tools/qa/qc.py`, `config/qc_thresholds.json` |
| 16 | Права/лицензии | ЧАСТИЧНО | `docs/openmontage/image_gen/LICENSE_EVIDENCE.md` актуализировано (SDXL Base 1.0 + SDXL-Lightning commercial-OK OpenRAIL++; FLUX.2-klein-4B apache-2.0 commercial-OK; FLUX 3 Image Klein flux-kommunity-license только для Qualifying Users) |
| 17 | Музыка | ПОЛИТИКА: без музыки | `docs/openmontage/MUSIC_POLICY.md` |
| 18 | Публикация | НЕ РЕАЛИЗОВАНО | `docs/openmontage/youtube-publishing-analytics-STUB.md` |

### 2.1 Что работает (подтверждено запуском/измерением)

- Сценарий: 10 разделов, 214 предложений, 214 уникальных `PROMPT:`, `[NARRATIVE]` в §5, §7, §8.
- SDXL Base 1.0 baseline стабилен: 45/45 картинок, пик VRAM 5 196 МБ на 768×768, 4 независимых прогона на Kaggle T4 без OOM.
- Kaggle-мост: `kaggle_bridge.py` реализует submit/poll/fetch/output/logs, `_scrub_token` чистит токен. Ядра `om-consistency-ab-test` v12 и `pilot-frame-sdxl-baseline` выполнены на T4.
- Пакетная логика: `episode_run.py` — батчи 40–100, resume по sha256, повтор только упавших, hard fail при недоборе.
- Права: `rights_basis=ai_generated_illustration`, метка «Speculative illustration» с первого кадра.
- Zero-cost gate: `lib/zero_cost_gate.py` блокирует необъявленные маршруты.
- Окружение закрыто: pytest 9.1.1 (2578 тестов собраны), kaggle CLI 2.2.5 авторизован, ffmpeg 6.1.1 с `--enable-gpl`, node_modules (201 пакета), Kokoro venv с `af_heart` работает, Remotion Free License подтверждена.
- Infrastructure (Фаза B): 6 субагентов (`.kilo/agents/`), `niche-researcher` перенесён из `.opencode`, pre-push хук, `.kilo/kilo.jsonc`, `.devcontainer/devcontainer.json`.

### 2.2 Что сломано (с точными местами)

**Б1. Парсер не понимает формат пилота.** Все три парсера ждут `- предложение [id]` или markdown-таблицу, а не `S001 [ID]` + `PROMPT:`:
- `scripts/run_episode.py:407` `_parse_script_rows`
- `tools/illustration/pilot_edl.py:228` `sentence_rows`
- `tools/illustration/pilot_edl.py:263` `script_sections`
- `tools/illustration/image_brief.py:96` `parse_script`
Следствие: `rows=[]` → 0 предложений в манифесте, 0 битов в EDL, 0 промптов в brief. Требуется новый адаптер формата.

**Б2. Реестр моделей не знает DreamShaper XL 1.0.** `config/image_engine.json`: `"model": "klein"`, `models` = klein, sdxl-lightning, dreamshaper-xl-lightning, sdxl, zimage. Записи `dreamshaper-xl-1-0` нет. `scripts/build_episode_edl.py:73` по умолчанию `--model klein`.

**Б3. Стиль противоречит S15.** `style.json`: `field_guide_plate`, `flat-vector`, `locked_model=klein`. Требуется `graphic-novel-ink` (S15 winner).

**Б4. Бюджет изображений несовместим с 214 картинками.** `tools/illustration/episode_run.py:38-40`: 6–8 img/min → 123–165 для 20.6 мин. 214 картинок = 10.4 img/min → `BudgetError` (строка 200).

**Б5. QA-пороги гарантированно валят пилот.**
- `tools/qa/qc.py:401` и `:1135`: `ai_label_max_share` = 0.15 → 100% AI видео → FAIL.
- `scripts/run_episode.py:876`: `cmd_qc` не передаёт `ai_label_max_share`.
- `config/qc_thresholds.json`: `graphics_per_90s_min: 1.0` → 0.73 на 1 236 с → FAIL.

**Б6. `import soundfile` ломает `registry.discover()`.** `tools/audio/kokoro_tts.py:23` — верхнеуровневый импорт.

**Б7. Нет `projects/` и F2-рендера с реальными кадрами.** Единственный видеоартефакт — `docs/openmontage/smoke/p0_smoke.mp4` (espeak-ng) и proof-of-concept `remotion-composer/out/pilot-scene-1.mp4`. Полного прогона эпизода не было.

**Б8. Нет пайплайна под научную спекуляцию.** В `pipeline_defs/` нет `science-explainer` или `speculative-science`.

**Б9. Remotion не подключён к эпизодному раннеру.** `run_episode.cmd_render` → `video_compose.py` (ffmpeg). Remotion только отдельными скриптами.

**Б10. Python 3.14.2 vs рецепт 3.13.15.** Локальные бинарные колёса (torch, kokoro) могут отсутствовать; Kokoro venv развёрнут отдельно в `/tmp/kilo/z1_venv`.

---

## 3. Цель и критерии готовности пилота

**Цель:** YouTube-канал в нише Education & Science, позиционирование "science-grounded speculation". Пилот: 20–21 мин, 10 разделов, стиль bold ink illustration (graphic-novel-ink), Kokoro af_heart, монтаж Remotion/ffmpeg, генерация на Kaggle T4. Только FOSS и коммерчески разрешённые лицензии.

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
| L1 | Remotion | кастомная лицензия, не FOSS (бесплатно для физлиц, ≤3 сотрудников, некоммерческих); Free License подтверждена владельцем для соло-проекта | противоречие «только FOSS» | Решение владельца O1; альтернатива — ffmpeg или HyperFrames (Apache-2.0) |
| L2 | DreamShaper XL 1.0 | OpenRAIL++ (не OSI FOSS, коммерческое использование разрешено с ограничениями) | ограничения использования + передача downstream | Решение владельца O2; текст лицензии в репозитории; не используется как база пилота |
| L3 | Kokoro-82M | веса Apache-2.0; CC BY в обучающих данных (Koniwa tnc, SIWIS); синтетика UNKNOWN | атрибуция, неопределённость синтетики | Решение владельца O3; блок атрибуции |
| L4 | SDXL-продукты | OpenRAIL++ | то же, что L2 | SDXL Base 1.0 commercial-OK (зафиксировано в LICENSE_EVIDENCE.md) |
| L5 | FLUX.2-klein-4B | apache-2.0, коммерческое использование разрешено; diffusers 0.37.0 уже содержит Flux2KleinPipeline | базовая модель пилота; SDXL Base 1.0 = резерв | требует enable_model_cpu_offload() на T4 (14.56 ГБ VRAM) |
| L6 | FLUX 3 Image Klein | flux-kommunity-license v1.0: коммерция только для Qualifying Users (< US$5M валовая выручаемая выручка с аффилиатами) | класс лицензии, не открытый исходный код | решение владельца перед включением; исключён навсегда для T4 (25 ГБ VRAM минимум) |
| L7 | Шрифты | `@remotion/google-fonts` тянет сетевые шрифты | офлайн-рендер + лицензия | OFL-шрифт локально (Inter / JetBrains Mono, OFL-1.1) |
| L8 | Музыка | политика: без музыки | «royalty-free» ≠ разрешение | без музыки на пилоте |
| L9 | FFmpeg | LGPL-2.1+ / GPL-2.0+ (в зависимости от сборки), `--enable-gpl` подтвержден | несовместимость с FOSS маловероятна | зафиксировать `ffmpeg -version` |

### 4.2 VRAM и железо (Kaggle T4, ~14.56 ГБ доступных)

| ID | Риск | Данные | Митигация |
|----|------|--------|-----------|
| V1 | Голова под адаптеры отсутствует | DreamShaper: 9 968 MB alloc / 12 828 MB reserved | не ставить IP-Adapter/InstantID на пилоте; консистентность — seed+промпт |
| V2 | VAE-decode OOM | IP-Adapter Plus пик ~13.9 ГБ → OOM | не ставить адаптер на пилоте |
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
| K3 | Токен в артефактах ядра | `kaggle_bridge._scrub_token` чистит |
| K4 | OAuth YouTube | не настроен, не нужен на пилоте |

### 4.5 Версии и зависимости (закреплены, не менять без решения владельца)

| Пакет | Закреплённая версия | Локально | Статус |
|-------|---------------------|----------|--------|
| diffusers | 0.37.0 | 0.37.0 | ок |
| transformers | 4.57.6 | 4.57.6 | ок |
| huggingface_hub | 0.36.2 | не проверено | — |
| torch | 2.11.0+cu128 | 2.14.1+cpu | расхождение (GPU только на Kaggle) |
| Python | 3.13.15 | 3.14.2 | расхождение |
| Node / npm | — | 24.21.0 / 11.19.0 | ок |

### 4.6 Процессные риски

| ID | Риск |
|----|------|
| P1 | PR #837 (809 файлов, +139k) не отревьюен, не смержен |
| P2 | Заголовок в файле не совпадает с темой владельца |
| P3 | `projects/` отсутствует — нет канонического корня проекта |
| P4 | QC-обход порогов «на словах» → фиктивный PASS |
| P5 | Нет F2-рендера с реальными кадрами — все тайминги расчётные (proof-of-concept §1 есть) |

---

## 5. Итоги тестирования консистентности персонажа (Kaggle T4)

Ядро `forts845/om-consistency-ab-test`, протокол `test_protocol.json`. База — **SDXL Base 1.0** (DreamShaper XL не зафиксирован в `LICENSE_EVIDENCE.md` → не используется как база). Запрещено: IP-Adapter FaceID, PhotoMaker V2, PuLID (InsightFace), Character LoRA. Ручное построение `ip_adapter_image_embeds` запрещено.

### 5.1 Пять ранних запусков (v1–v5, diffusers 0.37.0)

| Запуск | diffusers | Формат `ip_adapter_image_embeds` | Тест A (baseline) | Тест B (Plus Face) | Тест C (Plus full-body) | Тест D (комбо) |
|--------|-----------|----------------------------------|-------------------|--------------------|-------------------------|----------------|
| #1 | 0.40.0 | 3D (с `.unsqueeze(1)`) | 45/45, 5196 MB | 0/45, ошибка интеграции | 0/45, ошибка интеграции | — |
| #2 | 0.37.0 | 3D (с `.unsqueeze(1)`) | 45/45, 5196 MB | 0/45, "unpack (expected 2, got 1)" | 0/45, та же ошибка | 0/45, та же ошибка, пик 9946 MB |
| #3 | 0.37.0 | 2D (без `.unsqueeze(1)`) | 45/45, 5196 MB | 0/45, "has to be 3D or 4D tensors but is 2D" | та же ошибка | та же ошибка |
| #4 | 0.37.0 | 3D + кортежи (key,value) | 45/45, 5196 MB | 0/45, "'tuple' object has no attribute 'ndim'" | та же ошибка | та же ошибка |
| #5 | 0.37.0 | 3D + [neg,pos] конкатенация | 45/45, 5196 MB | 0/45, "Tensors must have same number of dimensions: got 2 and 3" | та же ошибка | OOM, пик 14160 MB |

**Вывод:** Pinning diffusers на 0.37.0 НЕ исправил IP-Adapter. Внутренний код diffusers 0.37.0 при обработке `ip_adapter_image_embeds` с CFG несовместим с форматами эмбеддингов. Тест A (базовый SDXL без IP-Adapter): 45/45 картинок, пик VRAM 5 196 МБ — стабильно во всех запусках.

### 5.2 Запуск v6 — официальный IP-Adapter API (quick-режим, 1 seed × 1 сценарий, 2026-10-27)

Ядро `forts845/om-consistency-ab-test` версия 12. Окружение: torch 2.11.0+cu128, diffusers 0.37.0, Tesla T4, 14.56 ГБ VRAM. Код: `pipe.load_ip_adapter("h94/IP-Adapter", subfolder="sdxl_models", weight_name="ip-adapter-plus-face_sdxl_vit-h.safetensors")`, `pipe.set_ip_adapter_scale(0.6)`, `ip_adapter_image=PIL.Image`.

| Тест | Конфигурация | Картин | Пик VRAM | Ошибка рендера | Вердикт |
|------|-------------|--------|----------|----------------|---------|
| A — baseline | SDXL Base 1.0, 768×768, fp16, vae_slicing+tiling+model_cpu_offload, без адаптера | 1/1 | 5 196 МБ | — | **Пройден** |
| B — Plus Face (офиц. API) | A + `ip-adapter-plus-face_sdxl_vit-h`, scale 0.6 | 0/1 | 5 839 МБ | `mat1 and mat2 shapes cannot be multiplied (514x1664 and 1280x1280)` | Не пригоден |
| C — Plus full-body (офиц. API) | A + `ip-adapter-plus_sdxl_vit-h`, scale 0.6 | 0/1 | 5 839 МБ | та же ошибка (1664 vs 1280) | Не пригоден |
| D — комбо Plus + Plus Face | B + C | 0/1 | 11 664,7 МБ | та же ошибка | Не пригоден |

Причина: `h94/IP-Adapter` sdxl_models кодирует изображение через `image_encoder` (ViT-H, `last_hidden_state` 1664 dim), а веса `ip-adapter-plus-face_sdxl_vit-h` ждут на вход проекции 1280-dim `image_embeds`. Официальный `ip_adapter_image` кормит проекцию `last_hidden_state` → несовпадение размерностей. Полная матрица 5 seed × 9 сценариев не имеет смысла — ни один адаптерный тест не выдаёт годного кадра.

**Детальный отчёт:** `tools/kaggle_bridge/jobs/consistency-ab-test/results_v6/consistency-ab-test/results.json`.

### 5.3 FLUX.2 Klein 4B разведка

- Статус: ПРОВЕРЕНО — diffusers 0.37.0 уже содержит `Flux2KleinPipeline` (апгрейд не нужен).
- Исправление прошлой ошибки: ошибка `expected feature_extractor, image_encoder, text_encoder_2, tokenizer_2` вызвана использованием класса `FluxPipeline` (FLUX.1), а не `Flux2KleinPipeline`. Вывод «Klein несовместим с 0.37.0» неверен.
- Официальные настройки FLUX.2 Klein: 4 шага, `guidance_scale=1.0` (CFG выключен), 1280×720 (кратны 16), до 4 референсов, нарративный промптинг с явным описанием техники (только позитивно, негативные промпты не работают).

### 5.4 FLUX 3 Image Klein

Исключён навсегда: минимальный официальный VRAM 25 ГБ (NVFP4), T4 имеет 14.56 ГБ.

---

## 6. Финальный метод консистентности персонажа

**Метод для пилота (фиксировано, не пересматривать в рамках текущего плана): нативный multi-reference Klein 4B (до 4 референсных изображений), IP-Adapter не нужен, SDXL Base 1.0 = резерв.** Фиксированное описание персонажа/субъекта в каждом промпте. Пилот можно собрать и так.

Адаптерный метод консистентности **ещё не выбран** (не пригоден с текущим стеком: diffusers 0.37.0, T4 14.56 ГБ, h94/IP-Adapter не совместим по размерностям эмбеддингов 1664 vs 1280). Откладывается на отдельный timebox после пилота.

**Два кандидата на адаптерный метод (post-pilot timebox):**

1. **X — IP-Adapter Plus Face с исправлением размерности эмбеддингов.** Требует либо изменения внутреннего кода diffusers 0.37.0, либо ручной сборки `ip_adapter_image_embeds` (запрещено ограничениями текущего плана), либо апгрейда diffusers (заблокировано dependency-guard без решения владельца).
2. **Y — альтернативная модель адаптера/подход** (например, другой IP-Adapter вес с совместимой размерностью проекции или Character LoRA — при условии одобрения владельцем, см. перечень «не рассматриваются»).

Контроль консистентности на пилоте — визуальный, владельцем, по сохранённым кадрам Теста A.

---

## 7. Первый собранный кадр сцены пилота (реальный результат, 2026-10-27)

Собран первый клип пилота — раздел §1 «Hook and the question» («What Would Life Look Like on an Ocean Planet With No Land?»), от текста до готового кадра с озвучкой.

| Поле | Значение |
|------|----------|
| Сцена | §1 «Hook and the question», 14 предложений (S001–S014) |
| Кадр | 1 кадр, beat S001, baseline SDXL Base 1.0 (fallback-метод консистентности), 768×768, фиксированный детальный промпт + стиль graphic-novel-ink как текст |
| Генерация кадра | Kaggle T4, ядро `forts845/pilot-frame-sdxl-baseline`, peak VRAM 5 196 MB, 22 с |
| Озвучка | Kokoro-82M, голос `af_heart`, venv `/tmp/kilo/z1_venv`, 83.03 с, 24 кГц |
| Сборка | Remotion composition `PilotScene1` (`remotion-composer/src/PilotScene.tsx`), кадр full-bleed + аудио, `remotion-composer/out/pilot-scene-1.mp4` |
| Результат | h264 1920×1080 + aac, 83 с, 6.4 MB, валиден (ffprobe: видео h264 1920×1080, аудио aac) |

**Путь первого кадра:** `tools/kaggle_bridge/jobs/pilot-frame-1b/output/pilot-frame-1/frame_001.png` → `remotion-composer/public/pilot/frame.png`  
**Путь озвучки:** `/tmp/kilo/pilot_scene1/narration.wav` → `remotion-composer/public/pilot/narration.wav`  
**Готовый клип:** `remotion-composer/out/pilot-scene-1.mp4` (не коммитится в git — артефакт сборки)

**Осталось до полного пилота:** 9 разделов (§2–§10, 200 оставшихся предложений из 214). Каждый раздел нужен свой набор кадров + озвучка, затем склейка, субтитры, переходы, графика, QA.

---

## 7.5 Все 10 разделов пилота — сгенерировано (реальный результат, 2026-10-27)

Сгенерировано по одному кадру на каждый из 10 разделов сценария пилота методом консистентности из `docs/openmontage/image_gen/EPISODE_IMAGE_PIPELINE.md` §10 (baseline SDXL Base 1.0 + фиксированный text-prompt, без IP-Adapter).

| Раздел | Файл | Заголовок | Статус | Время (с) | Пик VRAM (MB) |
|--------|------|-----------|--------|-----------|---------------|
| §1 | `tools/kaggle_bridge/jobs/pilot-render/images/section_01.png` | Hook and the question | OK | 19.700 | 5196 |
| §2 | `tools/kaggle_bridge/jobs/pilot-render/images/section_02.png` | The world: an ocean with no shores | OK | 18.188 | 5196 |
| §3 | `tools/kaggle_bridge/jobs/pilot-render/images/section_03.png` | Energy: no sunlight, two answers | OK | 17.169 | 5196 |
| §4 | `tools/kaggle_bridge/jobs/pilot-render/images/section_04.png` | Life near the ice: mats and filter-feeders | OK | 17.695 | 5196 |
| §5 | `tools/kaggle_bridge/jobs/pilot-render/images/section_05.png` | Predators, and the logic of an arms race | OK | 18.347 | 5196 |
| §6 | `tools/kaggle_bridge/jobs/pilot-render/images/section_06.png` | The deep, the vents, and the animals that stay | OK | 19.198 | 5196 |
| §7 | `tools/kaggle_bridge/jobs/pilot-render/images/section_07.png` | Chance and law: would this world repeat? | OK | 19.509 | 5196 |
| §8 | `tools/kaggle_bridge/jobs/pilot-render/images/section_08.png` | What blocks technology without land or fire | OK | 18.750 | 5196 |
| §9 | `tools/kaggle_bridge/jobs/pilot-render/images/section_09.png` | What is science, and what is a guess | OK | 18.608 | 5196 |
| §10 | `tools/kaggle_bridge/jobs/pilot-render/images/section_10.png` | Closing and a question for you | OK | 18.787 | 5196 |

**Ядро:** `forts845/om-pilot-render` (v2), Kaggle T4, diffusers 0.37.0  
**Модель:** `stabilityai/stable-diffusion-xl-base-1.0` (SDXL Base 1.0)  
**Параметры:** 768×768, 25 steps, CFG 7.5, seed 42, fp16  
**Стиль:** bold graphic-novel ink, night ink/deep sea teal/pale bone/coral accent, fixed prefix + tail per script.md recipe  
**Итого:** 10/10 OK, 0 failed, ~4.5 мин GPU времени  
**Отчёт:** `tools/kaggle_bridge/jobs/pilot-render/RESULTS.md`

**Важное замечание:** базовая модель пилота — FLUX.2-klein-4B (black-forest-labs/FLUX.2-klein-4B, Apache-2.0), diffusers 0.37.0 уже содержит Flux2KleinPipeline. SDXL Base 1.0 = резерв.

**Известные риски консистентности:**
- Кросс-секционная визуальная консистентность (дизайн созданий: гразер 6 конечностей,дрифтер-лента, норатор-сегмент; палитра) не проверялась программно — требуется визуальная проверка владельцем.
- Один кадр на раздел (10 всего) — при негодности кадра требуется перегенерация с новым сидом.
- В сценарии пилота нет человеческого персонажа — консистентность поддерживается через фиксированный стильプレфикс/хвост и описания созданий, а не через описание человека.

---

## 7.6 Озвучка всех 10 разделов — Kokoro TTS (af_heart) (2026-10-27)

Сгенерировано аудио для каждого из 10 разделов через Kokoro 0.2.2, голос `af_heart`, 24 кГц.

| Раздел | Файл | Заголовок | Слова | Длительность (с) | Ожидается (с) | Разница (с) | Статус |
|--------|------|-----------|-------|-----------------|---------------|-------------|--------|
| §1 | `audio/section_01.wav` | Hook and the question | 229 | 83.0 | 91 | −8.0 | OK |
| §2 | `audio/section_02.wav` | The world: an ocean with no shores | 384 | 129.4 | 153 | −23.6 | OK |
| §3 | `audio/section_03.wav` | Energy: no sunlight, two answers | 377 | 148.6 | 150 | −1.4 | OK |
| §4 | `audio/section_04.wav` | Life near the ice: mats and filter-feeders | 381 | 135.5 | 155 | −19.5 | OK |
| §5 | `audio/section_05.wav` | Predators, and the logic of an arms race | 383 | 132.9 | 149 | −16.1 | OK |
| §6 | `audio/section_06.wav` | The deep, the vents, and the animals that stay | 390 | 137.8 | 152 | −14.2 | OK |
| §7 | `audio/section_07.wav` | Chance and law: would this world repeat? | 302 | 99.9 | 118 | −18.1 | OK |
| §8 | `audio/section_08.wav` | What blocks technology without land or fire | 332 | 101.4 | 120 | −18.6 | OK |
| §9 | `audio/section_09.wav` | What is science, and what is a guess | 268 | 83.6 | 87 | −3.4 | OK |
| §10 | `audio/section_10.wav` | Closing and a question for you | 208 | 47.8 | 57 | −9.2 | OK |

**Всего:** 1099.9с (18:20) фактически vs 1232с (20:32) ожидается (−132.1с, −10.7%)

**Ядро:** `/tmp/kilo/z1_venv` (Python 3.14.2, kokoro==0.2.2), голос `af_heart`  
**Генерация:** секции 3–10 построчно в отдельных процессах (избежать накопления памяти)  
**Отчёт:** `tools/kaggle_bridge/jobs/pilot-render/audio/RESULTS.md`

**Примечание:** все секции короче ожидаемого времени из `script.md` (150 wpm человеческий темп). Kokoro читает быстрее без естественных пауз между предложениями — паузы добавляются в пост-продакшене.

---

## 7.7 Черновой рендер пилота через Remotion (2026-10-27)

Собрана композиция `PilotDraft` (`remotion-composer/src/PilotDraft.tsx`), зарегистрированная в `remotion-composer/src/Root.tsx`:
- 10 секций, по одному сгенерированному изображению на раздел, full-bleed
- Каждая секция синхронизирована со своим аудио-файлом (Kokoro af_heart)
- Без переходов/эффектов — черновик для проверки владельцем
- TypeScript компилируется без ошибок

**Пути:**
- Композиция: `remotion-composer/src/PilotDraft.tsx`
- Регистрация: `remotion-composer/src/Root.tsx` (Composition id `PilotDraft`)
- Изображения: `remotion-composer/public/pilot/section_*.png` (скопированы из `tools/kaggle_bridge/jobs/pilot-render/images/`)
- Аудио: `remotion-composer/public/pilot/section_*.wav` (скопированы из `tools/kaggle_bridge/jobs/pilot-render/audio/`)
- Выход: `remotion-composer/out/pilot-draft.mp4` (рендер не завершён в этой сессии — Remotion рендерит ~33 000 кадров через Chrome headless, оценка ~2.5 часа)

**Статус рендера:** запущен и остановлен на ~920/32 994 кадра (~3%). Нужно дореNDERить отдельно.

---

## 7.8 Что ещё нужно для финальной версии пилота

| Пункт | Статус | Комментарий |
|-------|--------|-------------|
| Переходы между секциями | НЕ СДЕЛАНО | Черновик без переходов |
| Субтитры (SRT) | НЕ СДЕЛАНО | `scripts/fw_subtitles.py` не проверялся |
| Музыкальная подложка | ОТКРЫТЫЙ ПУНКТ | Согласно HANDOFF-документу, музыкальная подложка ещё не выбрана. Требуется решение владельца. |
| Полный рендер 20:30 | НЕ СДЕЛАНО | Черновик ~18:20, нужен финальный монтаж |
| QA и гейт выпуска | НЕ СДЕЛАНО | `tools/qa/qc.py`, пороги требуют override-файла |

---

## 8. Фазовый план — только оставшиеся шаги до готового пилота

Уже сделано (не повторять как TODO): окружение закрыто (pytest, kaggle CLI, ffmpeg, Kokoro venv, node_modules, Remotion Free License), закреплены версии diffusers/transformers/huggingface_hub, проведён полный цикл тестирования консистентности (v1–v6), выбран fallback-метод консистентности, собран первый кадр пилота §1.

Размеры: **S** ≤ 0.5 дня, **M** 0.5–1.5 дня, **L** > 1.5 дня (включая ожидание GPU).

### Фаза 1 — Адаптер формата пилота (M) — **блокирующая**

Новый модуль `tools/illustration/pilot_script.py`: парсит `S<NNN> [ID]` + `PROMPT:`; отдаёт `{sections, sentences, prompts, claim_ids}`; валидирует нумерацию, уникальность промптов, резолв claim_id в леджере.

| Файлы | `tools/illustration/pilot_script.py` (новый), `tests/illustration/test_pilot_script.py` (новый), подключение: `scripts/run_episode.py:407`, `tools/illustration/pilot_edl.py:228,263`, `tools/illustration/image_brief.py:96` |
|-------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Приёмка | 214 предложений, 10 разделов, 214 промптов, 0 неизвестных claim_id; старый формат (буллеты/таблицы) не сломан — тест на регрессию |
| Риск | средний: три парсера, легко получить расхождение; тест обязателен |

### Фаза 2 — Сведение конфигов и стиля на FLUX.2-klein-4B (S) — **блокирующая**

Добавить в `config/image_engine.json` запись `flux2-klein-4b` (4 шага, guidance_scale=1.0, fp16/bf16 с фолбэком, model_cpu_offload, 1280×720, Apache-2.0); переключить `model` на `flux2-klein-4b`; привести `style.json` и `STYLE_BIBLE.md` к графическому инк-иллюстрационному стилю (VISUAL_STYLE_GUIDE.md); SDXL Base 1.0 оставить как резерв; `build_episode_edl.py --model` по умолчанию = `flux2-klein-4b`.

| Файлы | `config/image_engine.json`, `docs/openmontage/pilot/VISUAL_STYLE_GUIDE.md`, `docs/openmontage/pilot/HOST_CHARACTER.md`, `docs/openmontage/niches/speculative_evolution/style.json`, `.../STYLE_BIBLE.md`, `scripts/build_episode_edl.py:73`, `docs/openmontage/image_gen/EPISODE_IMAGE_PIPELINE.md` |
|-------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Приёмка | один источник истины: рецепт = конфиг = стиль = сценарий; Klein 4B — базовая модель пилота, SDXL Base 1.0 — резерв |
| Риск | средний: правки в нескольких файлах, нужен дифф-ревью |

### Фаза 3 — Производство 214 изображений (L)

Job-файл на базе проверенного baseline с `model_config` из рецепта; 3 батча 72/71/71; seed-лог на каждую картинку; `DONE.json` в `finally`; fetch + verify sha256; `illustration_qc`; ретраи только упавших (≤ 2 на картинку).

| Файлы | `tools/kaggle_bridge/jobs/pilot-sd-xl-1-0-{1,2,3}/`, `scripts/run_episode_images.py`, состояние в `projects/<pilot>/` |
|-------|-------------------------------------------------------------------------------------------------|
| Приёмка | 214/214 verified; 0 black/NaN; ≥ 190 (≥89%) проходят QC с первой попытки; суммарно ≤ 110 мин GPU; манифест содержит model/revision/seed/sha256 |
| Риск | высокий: OOM, чёрные кадры, квоты, обрыв ядра |

### Фаза 4 — Narration и субтитры (M) — параллельна фазе 3

214 предложений через `kokoro_tts` (`af_heart`, CPU); `finish_audio` до −14 LUFS; forced alignment → SRT.

| Файлы | `scripts/run_episode.py:311` (`cmd_narration`), `tools/audio/kokoro_tts.py`, `scripts/kokoro_torch_narrate.py`, `scripts/fw_subtitles.py` |
|-------|-------------------------------------------------------------------------------------------------------------------------------|
| Приёмка | WAV 24 кГц; −14 ± 2 LUFS; TP ≤ −1.5 dBTP; 214 реплик; дрейф ≤ 0.5 с; 20 контрольных терминов проверено вручную |
| Риск | средний: Python 3.14 + бинарные колёса; `af_heart` может спотыкаться на латинице/числах |

### Фаза 5 — EDL и монтаж (L)

`build_episode_edl.py` на реальном манифесте; 10 карточек разделов + ≥ 4 доп. графических события (для D8); чередование движений; per-cut rationale + claim_id; затем рендер ffmpeg или Remotion (по решению O1/O10).

| Файлы | `scripts/build_episode_edl.py`, `tools/illustration/pilot_edl.py`, `tools/video/video_compose.py`, `remotion-composer/` |
|-------|---------------------------------------------------------------------------------------------------|
| Приёмка | D1, D7, D8; каждое решение о склейке имеет rationale; ни одного still-only > 15 с |
| Риск | средний: длительность 20:36 в ±6 с |

### Фаза 6 — QA и пакет (M)

Прогон 16 проверок; **файл-обход** порогов (`config/qc_pilot_override.json`) с подписью владельца: `ai_label_max_share: 1.0`, `graphics_per_90s_min: 0.73` — только если O5 выбран вариант «обход»; собрать `credits.txt`, `rights_records.json`, метаданные.

| Файлы | `tools/qa/qc.py`, `config/qc_thresholds.json` / новый override, `scripts/run_episode.py:870` |
|-------|-----------------------------------------------------------------------------------|
| Приёмка | D9–D13, D15; `qa_report.json` без `NOT_RUN`/`BLOCKED` |
| Риск | высокий: любой NOT_RUN = BLOCKED, а не PASS |

### Фаза 7 — Опционально: консистентность персонажа (M, timebox 1 ядро, после пилота)

Одно ядро-эксперимент: 9 референсов, замер VRAM; сравнить кандидатов X и Y только на 3 сценах.

| Приёмка | go/no-go с измеренным пиком VRAM; при OOM — ветка закрывается навсегда |
|---------|------------------------------------------------------------------------|
| Риск | высокий; IP-Adapter Plus давал 13.9/14.56 ГБ (OOM risk) |

---

## 9. Параллельность и правила конфликтов

### 9.1 Жёсткая последовательность

```
Фаза 1 → Фаза 2 → Фаза 3 ─┐
                         ├→ Фаза 5 → Фаза 6 → пакет
Фаза 4 ─────────────────┘ (параллельна фазе 3)
```

Обоснование: без парсера нельзя применить конфиг к 214 промптам; генерация не в той модели тратит квоту GPU; EDL требует длительности озвучки и реальные файлы картинок; QA проверяет готовый MP4.

### 9.2 Параллельно

| Задача A | Задача B | Почему безопасно |
|----------|----------|------------------|
| Фаза 3 (GPU) | Фаза 4 (CPU, Kokoro) | независимые ресурсы и файлы |
| Фаза 3 | Пакет атрибуции/лицензий (L1–L3) | только текст |
| Фаза 4 | Черновик title/description/thumbnail | опирается на замороженный сценарий |
| Фаза 5 | Спайк Remotion/ffmpeg в отдельном worktree | не пересекаются по файлам |

### 9.3 Правила конфликтов

1. Один файл — один писатель. `config/image_engine.json` правит только оркестратор (фаза 2).
2. `qa_report.json` пишет только `qa-reviewer`.
3. EDL/`edit_decisions.json` — только `editor`.
4. `evidence-checker` и `footage-scout` почти не задействованы: внешних ассетов нет, все картинки — AI.
5. Любая параллельная ветка работает в отдельном worktree; мерж — после приёмки.

---

## 10. Решения, которые должен принять владелец

| ID | Вопрос | Варианты | Влияние | Рекомендация |
|----|--------|----------|---------|--------------|
| O1 | Remotion не FOSS. Принимаем для пилота? | (а) принять (Free License, физлицо/≤3 сотрудника); (б) заменить на ffmpeg; (в) заменить на HyperFrames (Apache-2.0) | Фаза 5, юридическая чистота | (а) — уже подтверждено для соло-проекта, использовано для proof-of-concept клипа |
| O2 | DreamShaper XL 1.0 — OpenRAIL++, не OSI. База пилота — SDXL Base 1.0 (commercial-OK). Принимаем? | (а) SDXL Base 1.0 + OpenRAIL++; (б) DreamShaper XL 1.0 + текст лицензии | Лицензионный режим пилота | (а) — SDXL Base 1.0 уже протестирован, 5 196 МБ пик на T4 |
| O3 | Kokoro: CC BY в данных + неизвестная синтетика | (а) подписать + атрибуция; (б) сменить голос | Описание видео, юридический риск | (а) + блок атрибуции |
| O4 | 214 картинок vs бюджет 6–8 img/min | (а) поднять до 10.4; (б) сократить до 165; (в) оставить 214 + расширить лимит | Объём GPU, ритм монтажа | (а) — «одна на предложение» |
| O5 | QA: 100% AI + плотность графики | (а) override-файл `ai_label_max_share=1.0` + 4 события; (б) override и по плотности | Честность гейта | (а): метку оставить, плотность событиями |
| O6 | Заголовок | (а) «What Would Life Look Like on an Ocean Planet With No Land?»; (б) текущий в файле | Метаданные, thumbnail, сценарий | (а) как тема канала, (б) как подзаголовок |
| O7 | Музыка | (а) без музыки; (б) лицензированный трек | Тон, права | (а) на пилоте |
| O8 | Консистентность персонажа | (а) только seed+промпт (принято для пилота); (б) timebox на 1 ядро после пилота | Качество, риск OOM | (а) сейчас, (б) после пилота |
| O9 | Голос | `af_heart` единственный | Единообразие | подтвердить `af_heart` |
| O10 | Канонический рендер | (а) ffmpeg `video_compose` (подключён); (б) Remotion (proof-of-concept есть) | Сроки, лицензия | (а) для пилота, (б) второй путь |
| O11 | Квоты Kaggle | 3 ядра / ~96 мин GPU в неделю | Сроки | подтвердить доступ и окно |
| O12 | Раскрытие AI | (а) метка на каждом кадре + в описании; (б) только в описании | Политика YouTube, доверие | (а) |

---

## 11. Инфраструктура (Фаза B, внедрена и протестирована)

**Дата внедрения:** 2026-10-26

### 11.1 Субагенты (`.kilo/agents/`, mode: subagent)

| Агент | Файл | Mode | Статус |
|-------|------|------|--------|
| license-checker | `.kilo/agents/license-checker.md` | subagent | Создан, YAML frontmatter валиден |
| kaggle-test-runner | `.kilo/agents/kaggle-test-runner.md` | subagent | Создан, YAML frontmatter валиден |
| dependency-guard | `.kilo/agents/dependency-guard.md` | subagent | Создан, YAML frontmatter валиден |
| git-hygiene | `.kilo/agents/git-hygiene.md` | subagent | Создан, YAML frontmatter валиден |
| plan-keeper | `.kilo/agents/plan-keeper.md` | subagent | Создан, YAML frontmatter валиден |
| code-reviewer | `.kilo/agents/code-reviewer.md` | subagent | Создан, YAML frontmatter валиден |
| niche-researcher | `.kilo/agents/niche-researcher.md` | subagent | Скопирован из `.opencode/agent/` |

### 11.2 Инфраструктурные защиты

| Компонент | Файл | Статус | Тест |
|-----------|------|--------|------|
| Pre-push хук | `.kilo/hooks/pre-push.sh` + `.git/hooks/pre-push` (symlink) | Создан, исполняем | Блокирует файл >90 МБ (exit code 1) |
| Права агентов | `.kilo/kilo.jsonc` | Создан | Config validation OK |
| Devcontainer | `.devcontainer/devcontainer.json` | Создан | python:3.12 + Node.js LTS, postCreateCommand настраивает хук, venv, pip, npm. Требует пересборки codespace для применения. |

### 11.3 Результаты тестов агентов

| Агент | Тест | Результат |
|-------|------|-----------|
| license-checker | Кейс Cheyenne (style1/manifest.json) | Файл валиден, правила требуют точного имени проекта |
| kaggle-test-runner | Синтаксис YAML frontmatter | ✅ Валидно |
| dependency-guard | Конфликт diffusers==0.40.0 vs 0.37.0 | ✅ Конфликт обнаружен, будет заблокирован |
| git-hygiene | 95 МБ файл через pre-push хук | ✅ Заблокирован (exit code 1) |
| code-reviewer | Синтаксис YAML frontmatter | ✅ Валидно |
| plan-keeper | Синтаксис YAML frontmatter | ✅ Валидно |

---

## 12. Что проверить первым делом в следующей сессии

1. Окружение закрыто (все 6 пунктов §11.3 и §2.1 подтверждены запуском).
2. Консистентность: fallback-метод зафиксирован (§6); адаптер X/Y не выбран, timebox после пилота.
3. Первая реальная scena собрана (§7) — `remotion-composer/out/pilot-scene-1.mp4`.
4. Следующий реальный шаг: **Фаза 1** — адаптер формата пилота (`tools/illustration/pilot_script.py`), без него нельзя перейти к генерации 214 изображений.
5. После fáзы 1: Фаза 2 (конфиги на SDXL Base 1.0 + стиль graphic-novel-ink), затем Фаза 3 (генерация 214 изображений на Kaggle T4) параллельно Фазе 4 (озвучка 214 предложений Kokoro af_heart).
6. Осталось не автоматизировано: парсер формата пилота (Б1), субтитры/forced alignment, переходы между сценами и EDL, полный рендер эпизода (20–21 мин).

---

**Файл:** `docs/PROJECT_PLAN.md`
