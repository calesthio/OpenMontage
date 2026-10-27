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
| S5 | WAITING_OWNER | 10 кадров готовы к просмотру владельцем. Нужно подтверждение ОК или номера кадров для перегенерации. | 2026-10-27 |
| S6 | IN_PROGRESS | Remotion композиция `PilotDraft` создана (`remotion-composer/src/PilotDraft.tsx`), зарегистрирована в Root.tsx. Рендер запущен в фоне, остановлен на ~920/32994 кадров (~3%). Нужно дореNDERить. | 2026-10-27 |
| S7 | PENDING | Субтитры SRT по тексту сценария и реальным длительностям аудио. Наложение в Remotion. | — |
| S8 | WAITING_OWNER | Музыкальная подложка — владелец выбирает вручную из YouTube Audio Library. Папка: `assets/music/`. Если файла нет — финал без музыки. | — |
| S9 | PENDING | Финальный рендер. Если >90 MB — не коммитить видео, только код/конфиги. Путь к видео записать здесь. | — |
| S10 | PENDING | `docs/openmontage/pilot/PUBLISH.md`: 5 вариантов заголовка, описание, теги, промпт для превью, главы по таймкодам. | — |
| S11 | PENDING | Проверка готового видео навыком video-review (если есть в .kilo/skills/). Выписать проблемы без исправления без подтверждения. | — |

## Примечания

- **Модель:** SDXL Base 1.0 (klein 4B заблокирован на diffusers 0.37.0)
- **Консистентность:** фиксированный text-prompt (без IP-Adapter)
- **Голос:** af_heart (только этот, без замен)
- **Все артефакты:** `tools/kaggle_bridge/jobs/pilot-render/`
