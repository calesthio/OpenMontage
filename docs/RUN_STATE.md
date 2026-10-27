# RUN_STATE — OpenMontage Pilot Production

**Ветка:** `kilo/mega-100`  
**Репозиторий:** sora73636-stack/OpenMontage  
**Цель:** Готовое видео пилота "What Would Life Look Like on an Ocean Planet With No Land?"

## Таблица этапов

| Этап | Статус | Доказательство | Дата |
|------|--------|----------------|------|
| S1 | DONE | `docs/PROJECT_PLAN.md` обновлён (коммит fe11d5e): состояние по 18 стадиям, результаты консистентности, 10 кадров пилота, аудио, Remotion черновик | 2026-10-27 |
| S2 | DONE | IP-Adapter Plus/Plus Face через официальный API протестирован на Kaggle T4 — ошибка `mat1 and mat2 shapes cannot be multiplied (514x1664 and 1280x1280)`, 0 годных кадров. Fallback зафиксирован: SDXL Base 1.0 + фиксированный text-prompt. `docs/openmontage/image_gen/EPISODE_IMAGE_PIPELINE.md` §10. | 2026-10-27 |
| S3 | DONE | 10 кадров сгенерированы одним Kaggle-ядром `forts845/om-pilot-render` v2: `tools/kaggle_bridge/jobs/pilot-render/images/section_01.png`…`section_10.png`, 10/10 OK, пик VRAM 5196 MB. `RESULTS.md` сохранён. | 2026-10-27 |
| S4 | DONE | 10 аудио-файлов через Kokoro af_heart: `tools/kaggle_bridge/jobs/pilot-render/audio/section_01.wav`…`section_10.wav`, итого 1099.9s. `RESULTS.md` сохранён. | 2026-10-27 |
| S5 | WAITING_OWNER | 10 кадров готовы к просмотру владельцем. Нотификация отправлена в board. Нужно подтверждение ОК или номера кадров для перегенерации. | 2026-10-27 |
| S6 | IN_PROGRESS | Remotion композиция `PilotDraft` создана (`remotion-composer/src/PilotDraft.tsx`), зарегистрирована в Root.tsx. Рендер запущен в фоне (320×240, h264, crf 28), ~6% завершён, ориентировочно ~27 мин remaining. Деревья обновлены: субтитры добавлены в код, но текущий рендер без них. | 2026-10-27 |
| S7 | DONE | SRT файл создан: `tools/kaggle_bridge/jobs/pilot-render/audio/subtitles.srt` (10 записей, итого 1099.8с). Субтитры добавлены в `remotion-composer/src/PilotDraft.tsx` (SectionText компонент). TypeScript компилируется без ошибок. | 2026-10-27 |
| S8 | WAITING_OWNER | Музыкальная подложка — владелец выбирает вручную из YouTube Audio Library. Папка: `assets/music/`. Если файла нет — финал без музыки. | — |
| S9 | PENDING | Финальный рендер. Планируется через ffmpeg (быстрее Remotion через Chrome headless). Если >90 MB — не коммитить видео, только код/конфиги. | — |
| S10 | DONE | `docs/openmontage/pilot/PUBLISH.md` создан: 5 вариантов заголовка, описание, теги, промпт для превью, главы по таймкодам, метаданные. | 2026-10-27 |
| S11 | PENDING | Проверка готового видео через `video-pipeline-ffmpeg` / `youtube-quality-gate` навыки. Выписать проблемы без исправления без подтверждения. | — |

## Примечания

- **Модель:** SDXL Base 1.0 (klein 4B заблокирован на diffusers 0.37.0)
- **Консистентность:** фиксированный text-prompt (без IP-Adapter)
- **Голос:** af_heart (только этот, без замен)
- **Все артефакты:** `tools/kaggle_bridge/jobs/pilot-render/`
- **Рендер:** Remotion через Chrome headless медленный (~28 мин на 320×240). Для S9 planned ffmpeg directo.
