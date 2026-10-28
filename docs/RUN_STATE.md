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
| S12 | DONE | Финальная сборка v4 через ffmpeg (без Remotion): `scripts/assemble_pilot_final_v4.py`. 78 клипов Klein 1280×720 (один на бит 12-18с, zoompan 3-5%, вход увеличён 2x, жёсткая склейка concat), субтитры subtitles_bits.srt (324 блока, 2-5с, ≤42 симв./стр, шрифт 38px, нижняя треть, обводка 2px, original_size=1280x720). Аудио: мастеринг acompressor(thr=-24dB,ratio=3)+alimiter+loudnorm(I=-16:TP=-1.5:LRA=7), ebur128 до I=-25.6 LUFS/TPK=-4.9, после I=-15.7 LUFS/TPK=-1.5. Музыка: assets/music/ пуст → без музыки. Выход: `remotion-composer/out/pilot-final.mp4` (не в git). ffprobe: 1099.8s, h264 1280×720@30fps, aac 96000Hz mono, 58.6 MB. max_volume -0.7 dB (без клиппинга). 5 кадров с субтитрами: /tmp/subtitle_frames/sub_01-03.jpg | 2026-10-28 |

## Примечания

- **Модель:** FLUX.2-klein-4B (базовая модель пилота, Apache-2.0), SDXL Base 1.0 = резерв
- **Консистентность:** нативный multi-reference Klein 4B (до 4 референсов), IP-Adapter не нужен
- **Голос:** af_heart (только этот, без замен)
- **Все артефакты:** `tools/kaggle_bridge/jobs/pilot-render/`
- **Видео:** `remotion-composer/out/pilot-final.mp4` (58.6 MB, 1099.8s, h264 1280×720@30fps, aac 96000Hz mono, субтитры встроены, без музыки — файл assets/music/ отсутствует). Не в git (артефакт сборки). Черновик `pilot-draft.mp4` оставлен.
- **Ожидает владельца:** S5 (подтверждение кадров), S8 (выбор музыки), K1+K2 (номер кандидата ведущего 1-8 -> master.png), K5b (3-5 ссылки на видео конкурентов для анализа темпа)

| Этап | Статус | Доказательство | Дата |
|------|--------|----------------|------|
| K0 | DONE | PROJECT_PLAN.md (Klein 4B не исключена, консистентность = нативный multi-reference Klein 4B, IP-Adapter не нужен, SDXL Base = резерв), LICENSE_EVIDENCE.md (FLUX.2-klein-4B Apache-2.0 = базовая модель), RUN_STATE.md, SDXL-кадры перенесены в pilot-render/images_sdxl/, HOST_CHARACTER.md + VISUAL_STYLE_GUIDE.md созданы | 2026-10-27 |
| K1+K2 | DONE | Kaggle-ядро `forts845/k1-k2-host-candidates-flux-2-klein-4b` (COMPLETE 2026-10-27T10:32:41Z). 8 кандидатов ведущего 1280×720, 4 шага, guidance_scale=1.0, bfloat16 (peak VRAM 11.15 ГБ / 14.56 ГБ T4). contact_sheet_master.jpg 2x4 с номерами (58.98 KB < 2 МБ). Все 8 OK (без NaN/чёрных кадров). Время загрузки 78.97с, генерация ~90с на кадр. Signature Flux2KleinPipeline зафиксировано. Вывод: `/tmp/k1k2_output/k1k2-host-candidates/results.json`, ядро: `https://www.kaggle.com/code/forts845/k1-k2-host-candidates-flux-2-klein-4b` | 2026-10-27 |
| K3 | DONE | shot_list.json: 78 битов по 12-18с на 10 разделов (≈60-90 кадров). 3 Kaggle ядра (секции 1-4: 35 кадров, 5-7: 26, 8-10: 17), все COMPLETE. bfloat16, peak VRAM 11.15 ГБ, ~90с/кадр, общее GPU ~117 мин (<2ч). Все 78 кадров OK (без NaN/чёрных). Кадры: `tools/kaggle_bridge/jobs/pilot-render/frames_klein/sNN_BNNN.png` | 2026-10-28 |
| K4 | DONE | 7 контактных листов 4x3 с номерами (кадры 1-78), каждый <2 МБ: `tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein/contact_sheet_klein_01-07.jpg` | 2026-10-28 |
| K5 | PENDING | Konkurrenz-анализ темпов и монтажа (science-grounded speculation / "what if" научпоп): 3-5 ссылок от владельца, замеры WPM и длины блока мыслей по транскриптам, сравнение с pilot-final.mp4, рекомендация числами | — |
| K5a | BLOCKED | Инструменты: MCP YouTube не найден, yt-dlp не установлен. Нужен выбор владельца (подключить MCP или установить yt-dlp) | — |
| K5b | BLOCKED | Владелец называет 3-5 ссылок на видео конкурентов. Без ссылок — стоп, не выбираю каналы сам | — |
| K5c | BLOCKED | Замеры: длина видео, слов/мин, средняя длина главы/блока мысли → `docs/openmontage/research/competitor_notes.md` | — |
| K5d | BLOCKED | Сравнение с pilot-final.mp4 (1099.8 с, 78 битов по 12-18 с), вывод числами о корректировке темпа | — |
| K5e | BLOCKED | Рекомендация числами владельцу; shot_list.json не меняется без подтверждения | — |
