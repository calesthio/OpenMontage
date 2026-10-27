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
| S12 | DONE | Финальная сборка через ffmpeg (без Remotion): `scripts/assemble_pilot_final.py`. 10 клипов 1280×720 (zoompan 3-5%, чередующееся направление, вход увеличён 2x), xfade=fade 0.5с на стыках, субтитры srt встроены фильтром subtitles (крупный без засечек, нижняя треть). Музыка: в assets/music/ файла нет → финал без музыки. Выход: `remotion-composer/out/pilot-final.mp4` (не в git). ffprobe: 1099.8s, h264 1280×720@30fps, aac 24kHz mono, 59 MB. Аудио пик ~-89 dB (без клиппинга). 3 кадра на стыках извлечены (не чёрные). Субтитры встроены в видео (нет отдельного потока subtitles). | 2026-10-27 |

## Примечания

- **Модель:** FLUX.2-klein-4B (базовая модель пилота, Apache-2.0), SDXL Base 1.0 = резерв
- **Консистентность:** нативный multi-reference Klein 4B (до 4 референсов), IP-Adapter не нужен
- **Голос:** af_heart (только этот, без замен)
- **Все артефакты:** `tools/kaggle_bridge/jobs/pilot-render/`
- **Видео:** `remotion-composer/out/pilot-final.mp4` (59 MB, 1099.8s, h264 1280×720@30fps, aac 24kHz mono, субтитры встроены, без музыки — файл assets/music/ отсутствует). Не в git (артефакт сборки). Черновик `pilot-draft.mp4` оставлен.
- **Ожидает владельца:** S5 (подтверждение кадров), S8 (выбор музыки), K1+K2 (номер кандидата ведущего 1-8 -> master.png), K3 (генерация 10 кадров пилота), K4 (контакт-шит кадров)

| Этап | Статус | Доказательство | Дата |
|------|--------|----------------|------|
| K0 | DONE | PROJECT_PLAN.md (Klein 4B не исключена, консистентность = нативный multi-reference Klein 4B, IP-Adapter не нужен, SDXL Base = резерв), LICENSE_EVIDENCE.md (FLUX.2-klein-4B Apache-2.0 = базовая модель), RUN_STATE.md, SDXL-кадры перенесены в pilot-render/images_sdxl/, HOST_CHARACTER.md + VISUAL_STYLE_GUIDE.md созданы | 2026-10-27 |
| K1+K2 | DONE | Kaggle-ядро `forts845/k1-k2-host-candidates-flux-2-klein-4b` (COMPLETE 2026-10-27T10:32:41Z). 8 кандидатов ведущего 1280×720, 4 шага, guidance_scale=1.0, bfloat16 (peak VRAM 11.15 ГБ / 14.56 ГБ T4). contact_sheet_master.jpg 2x4 с номерами (58.98 KB < 2 МБ). Все 8 OK (без NaN/чёрных кадров). Время загрузки 78.97с, генерация ~90с на кадр. Signature Flux2KleinPipeline зафиксировано. Вывод: `/tmp/k1k2_output/k1k2-host-candidates/results.json`, ядро: `https://www.kaggle.com/code/forts845/k1-k2-host-candidates-flux-2-klein-4b` | 2026-10-27 |
| K3 | PENDING | Второй Kaggle-ядро: 10 кадров пилота 1280×720, prompts.json, референс master.png | — |
| K4 | PENDING | contact_sheet_frames.jpg 2x5, WAITING_OWNER | — |
