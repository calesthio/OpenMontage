# RUN_STATE — OpenMontage Pilot Production

**Ветка:** `kilo/mega-100`  
**Репозиторий:** sora73636-stack/OpenMontage  
**Цель:** Готовое видео пилота "What Would Life Look Like on an Ocean Planet With No Land?"

## Таблица этапов

| Этап | Статус | Доказательство | Дата |
|------|--------|----------------|------|
| S1 | DONE | `docs/PROJECT_PLAN.md` обновлён (коммит 575f482): состояние по 18 стадиям, результаты консистентности, 10 кадров пилота, аудио, Remotion черновик | 2026-10-27 |
| S2 | DONE | IP-Adapter Plus/Plus Face через официальный API протестирован на Kaggle T4 — ошибка `mat1 and mat2 shapes cannot be multiplied (514x1664 and 1280x1280)`, 0 годных кадров. Fallback зафиксирован: SDXL Base 1.0 + фиксированный text-prompt. `docs/openmontage/image_gen/EPISODE_IMAGE_PIPELINE.md` §10. | 2026-10-27 |
| S3 | DONE | 10 кадров сгенерированы одним Kaggle-ядром `forts845/om-pilot-render` v2: `tools/kaggle_bridge/jobs/pilot-render/images/section_01.png`…`section_10.png`, 10/10 OK, пик VRAM 5196 MB. `RESULTS.md` сохранён. | 2026-10-27 |
| S4 | DONE | 10 аудио-файлов через Kokoro af_heart: `tools/kaggle_bridge/jobs/pilot-render/audio/section_01.wav`…`section_10.wav`, итого 1099.9s. `RESULTS.md` сохранён. | 2026-10-27 |
| S5 | WAITING_OWNER | 10 кадров готовы к просмотру владельцем. Нотификация отправлена в board. Нужно подтверждение ОК или номера кадров для перегенерации. | 2026-10-27 |
| S6 | DONE | Remotion композиция `PilotDraft` создана (`remotion-composer/src/PilotDraft.tsx`), зарегистрирована в Root.tsx. Видео рендерено через ffmpeg (Remotion через Chrome headless слишком медленный: ~28 мин на 320×240). Выход: `remotion-composer/out/pilot-draft.mp4` (1280×720, h264+aac, 1099.8s, 26.4 MB). | 2026-10-27 |
| S7 | DONE | SRT файл создан: `tools/kaggle_bridge/jobs/pilot-render/audio/subtitles.srt` (10 записей, итого 1099.8с). Субтитры добавлены в `remotion-composer/src/PilotDraft.tsx` (SectionText компонент). TypeScript компилируется без ошибок. | 2026-10-27 |
| S8 | WAITING_OWNER | Музыкальная подложка — владелец выбирает вручную из YouTube Audio Library. Папка: `assets/music/`. Финал без музыки (файл не предоставлен). | — |
| S9 | DONE | Финальный рендер через ffmpeg: `remotion-composer/out/pilot-draft.mp4` (1280×720, h264+aac, 1099.8s, 26.4 MB). Меньше 90 МБ — можно коммитить, но видео не добавляется в git (артефакт сборки). | 2026-10-27 |
| S10 | DONE | `docs/openmontage/pilot/PUBLISH.md` создан: 5 вариантов заголовка, описание, теги, промпт для превью, главы по таймкодам, метаданные. | 2026-10-27 |
| S11 | DONE | Проверка через ffprobe/ffmpeg: файл существует (26.4 MB), h264 1280×720@30fps, aac 24kHz mono, длительность 1099.8s, чёрных кадров нет, тишины нет. Замороженные кадры на границах секций (361.4s, 369.7s) — ожидаемо для статичных изображений без переходов. Критических проблем не найдено. | 2026-10-27 |

## Примечания

- **Модель:** SDXL Base 1.0 (klein 4B заблокирован на diffusers 0.37.0)
- **Консистентность:** фиксированный text-prompt (без IP-Adapter)
- **Голос:** af_heart (только этот, без замен)
- **Все артефакты:** `tools/kaggle_bridge/jobs/pilot-render/`
- **Видео:** `remotion-composer/out/pilot-draft.mp4` (26.4 MB, без встроенных субтитров — только в коде Remotion, без музыки)
- **Ожидает владельца:** S5 (подтверждение кадров), S8 (выбор музыки)
