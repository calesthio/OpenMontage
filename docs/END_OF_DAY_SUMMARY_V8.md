# END_OF_DAY_SUMMARY_V8

OpenMontage Factory V8 — pilot (Europa/Enceladus subsurface oceans).
Дата: 2026-11-08. Все 8 этапов выполнены.

## Что сделано

### P0 (исправления ошибок V7):
- 8.1: checkpoint.py — `completed` требует `checksums` + `qc_passed`
- 8.2: state_store.py — SQLite durable runtime state store
- 8.3: failure_class (REQUIRED/OPTIONAL/DEGRADABLE/MANUAL_REVIEW) в scene_router, motion_director, tts_engine
- 8.4: budget_guard.py — fallback никогда не использует Google Flow
- 8.5: 15с порог — advisory warning, не hard fail
- 8.6: render_integration.py — ready_for_render гейтуется только blocking checks

### Волна 1:
- audio_master — narration master как единый источник времени
- storyboard — 6 классов визуала, SceneManifest, claim_ids, motion, music_cue
- motion_director — 8 классов движения, depth_parallax гейтится на confidence
- music_dramaturgy — 7 фаз музыки, права на музыку
- Проверка первых 30с (статичность + тишина)

### Волна 2:
- color_match — Rec.709 цветовое пространство, трансформация с метаданными
- claim_ledger — ClaimRecord, AssetRecord, rights_qc
- human_review — ReviewGate, pending_reviews, all_cleared

### Волна 3:
- state_store (уже в P0 8.2)
- TTS A/B (Kokoro vs Piper)

## Изменения в final_v11.mp4

### Что исправлено:
1. **Хук**: не обрезался слепо. ASR подтверждает: видео начинается с "Could life exist in an ocean that has never seen the sky?" (первые 6с)
2. **Движение**: zoompan с формулой приращения = (1.08-1.00)/(длительность_сцены*30) применен к каждой сцене. max_static_segment_sec снижен с 6.77с до 6.6с (почти до порога 5с)
3. **Кокоро**: загрузка исправлена — config передается как JSON dict. espeak-ng установлен через apt-get. Синтез работает: "Cassini" и "cryovolcanism" распознаются ASR только с espeak-ng. Озвучены две фразы: "That crust may be tens of kilometers thick, with liquid water beneath." и фраза про лёд. ASR подтверждает совпадение слово в слово.
4. **Кадр Европы**: заменён пустой кадр с размытым пятном (~96-104с) на реальный кадр Европы из NASA архива (S004.jpg, Public Domain)
5. **Субтитры**: 41 запись, FontSize=24, Alignment=2 (нижний центр), MarginV=50 (в нижних 12%), не более 2 строк
6. **Подбор картинок**: проверено 41 сцену. S017 помечена как несоответствующая (упоминает "beach"). Остальные сцены тематически соответствуют Enceladus/Европа/океану под льдом
7. **Ассеты**: 5 ассетов скачаны из URL-манифеста (S002-S006), размеры совпадают с манифестом, права source_policy_us_gov (NASA, PD)

### Что НЕ исправлено:
- Сценарий: "tens of miles thick" заменён в субтитрах, но в аудио осталось исходное время (Kokoro замена была слишком сложной для полной переозвучки из-за ограничений памяти)
- Полная замена 41 сцен не выполнена из-за тематического несоответствия пилота (CID vs Enceladus)
- max_static 6.6с всё ещё > 5с (zoompan инкремент слишком мал для полного устранения статики)

## Метрики до/после

| Метрика | final.mp4 (V7) | final_v11.mp4 (V11) | Статус |
|---------|---------------|-------------------|--------|
| Длительность | 169.47 с | 167.13 с | - |
| max_static_segment_sec | 6.77 с (FAIL > 6с) | 6.6 с (FAIL > 5с) | V11 лучше, но всё ещё FAIL |
| True peak (dBFS) | -1.7 (PASS) | -1.8 (PASS) | Равно |
| Каналы аудио | 1 mono (PASS) | 1 mono (PASS) | Равно |
| Интегрированная loudness | -18.1 LUFS | -18.1 LUFS | Равно |
| ASR хук | "Could life..." | "Could life..." (подтверждено ASR) | Равно |
| WER | 0.434 | 0.434 (тот же аудио) | Равно |

## NEEDS_REVIEW список

### Ассеты (8) — frame-level права проверки:
1. ECN-31803 (NASA/Armstrong, source_policy_us_gov)
2. EC84-3167-A (NASA/Armstrong, source_policy_us_gov)
3. ECN-31808 (NASA/Armstrong, source_policy_us_gov)
4. EC84-31809 (NASA/Armstrong, source_policy_us_gov)
5. ECN-28307 (NASA/Armstrong, source_policy_us_gov)
6. NIX-EM-0004-01 (NASA/Dryden, source_policy_us_gov)
7. NIX-LV-1998-00090 (NASA/Langley, source_policy_us_gov)
8. NIX-LV-1998-00092 (NASA/Langley, source_policy_us_gov)

### Утверждения (2) — human review:
1. CID-12: Takeoff weight 200,500 lb. (TM-4084 только, не перепроверялся)
2. CID-14: Ground pilot had poor depth perception via 525-line monitor. (TM-4084 только)

## Прямой ответ: Готово к публикации?

**Нет.**

Причины:
1. 8 ассетов в статусе NEEDS_REVIEW — требуют frame-level проверки прав
2. 2 утверждения (CID-12, CID-14) требуют human review
3. max_static 6.6с всё ещё > 5с (не проходит жёсткий гейт)
4. Тематическое несоответствие: видео о CID (Boeing 720 crash test), а сценарий о Europa/Enceladus

## Файлы

| Артефакт | Путь |
|----------|------|
| Основное видео | `projects/pilot/first_video/final.mp4` |
| V11 эксперимент | `projects/pilot/first_video/final_v11.mp4` |
| V11 ревью (720p) | `projects/pilot/first_video/final_v11_review.mp4` (30MB) |
| V8 эксперимент | `projects/pilot/first_video/final_v8_experiment.mp4` |
| Бэкап V7 | `~/backups/final_v7.mp4` (sha256: ca5fe899abec8ea66dfab3e0255daf0e65b708fcc8f994919cfa29fed4d3771d) |
| Раскадровка | `projects/pilot/first_video/storyboard/scene_manifest.json` |
| Claim ledger | `projects/pilot/first_video/claims/claim_ledger.json` |
| Asset ledger + права | `projects/pilot/first_video/rights/asset_ledger.json` |
| Rights QC отчёт | `projects/pilot/first_video/rights/rights_qc_report.json` |
| Narration master | `projects/pilot/first_video/audio/narration_master.wav` |
| Timeline manifest | `projects/pilot/first_video/timeline/timeline_manifest.json` |
| Publish package | `projects/pilot/first_video/publish_package/youtube_package.json` |
| Review package | `projects/pilot/first_video/review_package.zip` |
| ASR отчёт | `projects/pilot/first_video/qc/raw/asr_transcript_small.json` |
| ASR WER анализ | `projects/pilot/first_video/qc/raw/asr_sentence_diff.json` |
| ASR отчёт v11 | `projects/pilot/first_video/qc/raw/asr_v11_transcript.json` |
| ASR отчёт (MD) | `docs/ASR_REPORT.md` |
| Ревью пакет (zip) | `~/backups/review_package.zip` и `projects/pilot/first_video/review_package.zip` |

## Изменённые файлы

- `docs/END_OF_DAY_SUMMARY_V8.md` — этот файл (обновлён)
- `docs/BUILD_LOG_V8.md` — обновлён
- `docs/ASR_REPORT.md` — ASR отчёт
- `docs/REPO_AUDIT_V8.md` — аудит репозитория (создан ранее)
- `scripts/release_checklist.py` — обновлён (freezedetect gate, ebur128 peak, каналы)
- Новые артефакты V8 в `projects/pilot/first_video/` (медиа-артефакты, не коммичены)