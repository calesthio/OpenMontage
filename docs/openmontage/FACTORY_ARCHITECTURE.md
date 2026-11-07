# OpenMontage Factory Architecture

**Версия:** 1.0  
**Статус:** Production design  
**Репозиторий:** sora73636-stack/OpenMontage, ветка `kilo/mega-100`  
**Цель:** Одна команда превращает утверждённую тему в видео, готовое к ручной публикации на YouTube.

---

## 1. Философия

> **Агент — это оркестратор.** Нет отдельного кода-оркестратора. Кодинг-агент (Kilo/OpenCode) вызывает стадии фабрики как инструменты. Каждая стадия — независимый модуль с чекпоинтом, валидацией и fail-closed поведением.

### Граница ответственности (категории A / B / C)

| Категория | Кто принимает решения | Что делает агент |
|-----------|----------------------|------------------|
| **A** — Агент полностью сам | Не требуется | Все технические шаги: парсинг, генерация, монтаж, мастеринг, QC, упаковка |
| **B** — Одно решение владельца → агент | Номер мастер-референса, одобрение кадров, файл музыки | Сразу после получения решения — закрепляет, перегенерирует, миксует, собирает |
| **C** — Только владелец, никогда | Лицо персонажа, выбор трека, ссылки конкуренты, имя, голос, темп TTS | Агент НЕ принимает эти решения ни при каких обстоятельствах |

---

## 2. Десять слоев фабрики (L1–L10)

| Слой | Название | Ответственность | Категория |
|------|----------|-----------------|-----------|
| L1 | Niche & topic intelligence | Исследование ниши, проверка спроса, шаблоны эпизодов | A |
| L2 | Evidence & scripting | Реестр утверждений, сценарий с claim_id, валидация | A |
| L3 | Visual sources & rights | Реестр источников, права, адаптеры, лицензии | A (+ owner на C2) |
| L4 | AI illustration | Генерация кадров на Kaggle T4, манифест, QC иллюстраций | A |
| L5 | Voice & audio | Kokoro TTS, мастеринг, субтитры, forced alignment | A |
| L6 | Editing & render | EDL, ffmpeg сборка, переходы,グラфика | A |
| L7 | Quality gates | ffprobe, full_decode, blackdetect, silencedetect, ebur128 | A |
| L8 | Packaging | YouTube метаданные, титры, превью, кредиты | A |
| L9 | Owner review | Contact sheets, ревью пакет, чек-лист владельца | B |
| L10 | Operations | Analytics, уроки, evals, менее 800 MB диска | A |

---

## 3. Стадии конвейера (ordo executii)

```
zero_cost_gate → claim_ledger_check → script_validation →
footage_manifest_rights → narration → subtitles → edl →
speculative_gate → render → finish_audio → qc →
release_gate → package_draft
```

Каждая стадия:
1. Пишет чекпоинт (`checkpoint_<stage>.json`) со статусом `completed` / `awaiting_human` / `BLOCKED`
2. Логирует wall-time и дисковое пространство
3. Поддерживает resume с последней завершённой стадии
4. Fail-closed: неполная стадия = BLOCKED, конвейер останавливается

---

## 4. Категория A — выполняется агентом без ожидания

### A1. Сборка видео (`scripts/assemble_pilot_final.py`)
- 78 кадров Klein + аудио + субтитры → `pilot-final.mp4`
- Параметры через CLI, нет hardcoded `/tmp/` путей
- FFmpeg конкатенация с zoompan, сабтитры встроены

### A2. YouTube метаданные (`scripts/package_factory.py`)
- Читает `PUBLISH.md` + `shot_list.json`
- Генерирует `youtube_package.json`: заголовки, описание, теги, главы, статус draft

### A3. Технический QC (`tools/qa/qc_pilot_final.py`)
- ffprobe: разрешение, FPS, кодек, аудиопоток
- full_decode, blackdetect, silencedetect, ebur128 (loudness + true peak)

### A4. Инвентаризация (`scripts/audit_pilot_artifacts.py`)
- Проверка всех 78 кадров, 10 аудио, SRT, контакт-листов, mastered_full.wav

### A5. Структура эпизода (`projects/<topic>/`)
- `frames/`, `audio/`, `subtitles/`, `manifests/`, `rights/`, `output/`, `renders/`

---

## 5. Категория B — одно решение владельца, дальше агент

| # | Решение владельца | Путь к материалам | Что делает агент после получения |
|---|-------------------|-------------------|----------------------------------|
| B1 | Номер мастер-референса ведущего (1–8) | `tools/kaggle_bridge/jobs/consistency-ab-test/contact_sheet_master_v2.jpg` | Закрепляет в `projects/pilot/manifests/master_reference.json`, перегенерирует зависимые кадры |
| B1a | Одобрение 78 кадров Klein | 7 контакт-листов: `tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein/contact_sheet_klein_01-07.jpg` | Запуск финальной сборки A1 |
| B2 | Файл музыки из YouTube Audio Library | `assets/music/` | Копирует трек, микширует в видео, обновляет метаданные с кредитами |

---

## 6. Категория C — только владелец, никогда не автоматизируется

| # | Решение | Почему не ИИ |
|---|---------|-------------|
| C1 | Лицо ведущего (выбор из 8 кандидатов) | Творческое/кастинговое решение |
| C2 | Музыкальная подложка (лицензия + трек) | Юридическое решение, авторское право |
| C3 | Ссылки на 3–5 видео конкурентов | Стратегическое решение владельца |
| C4 | Имя ведущего | Творческое решение |
| C5 | Голос: `af_heart` или отдельный рассказчик | Решение о формате подачи |
| C6 | Темп TTS: 18:20 или ~20–21 мин | Решение о длительности |

---

## 7. Критерий готовности «фабрика работает автономно»

Запуск одной команды после получения B1, B1a, B2 производит видео, готовое к публикации:
```
python3 scripts/run_factory.py --topic pilot --owner-decisions b1=3,b1a=ok,b2=assets/music/track.mp3
```

Все промежуточные проверки (QC, метаданные, права) автоматизированы. Публикация в YouTube Studio — вручную владельцем (не OAuth, не авто-загрузка).

---

## 8. Директории

```
docs/openmontage/
  FACTORY_ARCHITECTURE.md (этот файл)
  FACTORY_GAP_AUDIT.md (результат F0 аудита)
  niches/speculative_evolution/{profile.yaml, STYLE_BIBLE.md, creatures/*.yaml}
  evidence/<episode>/CLAIM_LEDGER.md
  <episode>/{script.md, artifacts/{edit_decisions.json, subtitles.srt, credits.txt, rights_records.json, qa_report.json}}
  footage/SOURCE_REGISTRY.md
  image_gen/{PROMPTING_FACTS.md, LICENSE_EVIDENCE.md, AI_IMAGE_POLICY.md}
  package/<episode>/  analytics/
tools/{kaggle_bridge,qa,audio,illustration,adapters}/
scripts/run_factory.py review_pack.py rebuild_slice_assets.sh
projects/<episode>/  (gitignored media)
.kilo/{agents,skills}
```

---

## 9. Hard rules (никогда не relaxing)

1. Только FOSS и коммерчески разрешённые лицензии (Apache-2.0, OpenRAIL++, US gov)
2. Публикация только вручную в YouTube Studio — нет OAuth, нет авто-загрузки
3. Каждая фактическая фраза имеет claim_id из реестра утверждений
4. AI-иллюстрации всегда помечены, никогда не как реальное видео
5. Fail-closed QC: NOT_RUN / BLOCKED ≠ PASS
6. Checkpoint после каждой стадии, resume поддерживается
7. Диск ≥ 800 MB свободно, иначе остановка
8. Нет секретов в коде — только переменные окружения
