# External Tooling Integration — OpenMontage

**Дата:** 2026-11-04  
**Модель:** Reflection Beam 1.0  
**Цель:** аудит внешних репозиториев, выбор полезных возможностей и их интеграция в фабрику (без второго рендерера, без платных API).

## 1. Изученные репозитории

| Репозиторий | Лицензия | Полезные возможности | Решение |
|---|---|---|---|
| iart-ai/explainer-video-skills | MIT | Структура сценария (problem→solution→how→payoff), VO timing (~2.3 w/s), caption sync, style system | Адаптировать в навык/директора; не копировать код |
| iart-ai/data-animation-skills | MIT | Data-driven keyframing, counters, bar chart race, frame-driven values | Использовать принципы в Remotion-сценах; не добавлять renderer |
| iart-ai/manim-skills | MIT | ManimCE математическая анимация, LaTeX, updaters, 3D | Уже есть `math_animate`; использовать опционально |
| cth9191/animate | MIT | Режиссура, storyboard, grammar, review checks, contact sheets | Адаптировать чеклисты и review-процедуры |
| charlie947/motion-graphics-skills | MIT | Motion design промпты, loop, export | Использовать как справочник по motion |
| kabo-sh/kabo-plugins | Apache 2.0 | Creator research схемы, конкурентный анализ | Реализован `youtube_competitor_research` |
| jdwit/ytstudio-cli | MIT | Управление каналом и аналитика | Подготовить будущую интеграцию (stub), без ключей |
| jdepoix/youtube-transcript-api | MIT | Публичные субтитры | Установлен; `transcript_fetcher` AVAILABLE |

## 2. Интегрированные улучшения

- Установлены `youtube-transcript-api` и `yt-dlp` (бесплатно) → `transcript_fetcher`, `video_downloader` AVAILABLE.
- Добавлен инструмент `tools/analysis/youtube_competitor_research.py` (yt-dlp + transcript API) для исследования тем/конкурентов/хуков.
- Добавлен навык `.kilo/skills/youtube-competitor-research/SKILL.md`.
- Обновлён `FIRST_VIDEO_MASTER_PLAN.md` (раздел 8.1, архитектура конвейера).
- Тесты: `tests/tools/test_youtube_competitor_research.py`.

## 3. Будущая интеграция YouTube Analytics / ytstudio-cli

- Статус: подготовлено на уровне документации. Прямая интеграция требует OAuth-ключей и согласования владельца.
- План: создать `tools/publishers/ytstudio_bridge.py` (stub), который вызывает ytstudio-cli только при наличии `YTSTUDIO_*` env и согласия; до этого — ручной экспорт пакета.
- Не включать автопубликацию; соблюдать Zero-Cost Gate и human approval.

## 4. Проверка кадров (Frame QC)

- Используются существующие `visual_qa`, `frame_sampler`, `scene_detect`; добавлять новые инструменты только при необходимости.
- Рекомендуемый цикл: render stills → contact sheet → ffprobe full decode → blackdetect/freezedetect/silencedetect/ebur128.

## 5. Оставшиеся проблемы

- Manim не установлен (нет LaTeX) — `math_animate` остаётся UNAVAILABLE; использовать диаграммы через `diagram_gen` или установить manim+texlive по согласованию.
- Нет зарегистрированного web-search инструмента; исследование зависит от `youtube_competitor_research` и ручных источников.
- Remotion `node_modules` пуст — использовать FFmpeg/HyperFrames; не устанавливать второй рендерер.
- `music_library/` отсутствует; музыкальное решение recorded as silence.

## 6. Лицензии и коммерческое использование

Все внешние репозитории имеют MIT или Apache 2.0 — коммерческое использование разрешено. Код не копировался; реализованы оригинальные адаптации. Сторонние зависимости (yt-dlp, youtube-transcript-api) — MIT/Unlicense, бесплатны.
