# Результаты A/B-теста консистентности персонажа (Kaggle T4)

**Источник протокола:** `tools/kaggle_bridge/jobs/consistency-ab-test/test_protocol.json`  
**Ядро:** `forts845/om-consistency-ab-test` (версия 6)  
**Прогон:** 2026-10-26T14:56:12Z → 15:17:25Z  
**Окружение ядра:** Kaggle Tesla T4, 14.56 ГБ VRAM, torch 2.11.0+cu128, diffusers 0.40.0, CUDA доступен.  
**Артефакты:** `tools/kaggle_bridge/jobs/consistency-ab-test/results.json` + 45 PNG (Test A) + `ref_character.png`.

## 0. Сверка лицензии (Шаг 0)

`docs/openmontage/image_gen/LICENSE_EVIDENCE.md` **не упоминает DreamShaper XL**. В таблице лицензий только SDXL-Lightning, stabilityai/stable-diffusion-xl-base-1.0 (Open RAIL++-M, commercial YES), FLUX.1-schnell, Z-Image-Turbo, FLUX.2-klein-4B.  
Внутренний документ не даёт ясности по лицензии DreamShaper XL → **DreamShaper XL запрещён как база для этого теста**. База — SDXL Base 1.0 (лицензия Open RAIL++-M, commercial YES, зафиксировано в LICENSE_EVIDENCE.md).  
Запрещено по протоколу: DreamShaper XL (база), IP-Adapter FaceID, PhotoMaker V2, PuLID (все три — InsightFace), Character LoRA (решение владельца, не часть теста).

## Матрица тестов

| Тест | Конфигурация | OOM? | Картин | Пик VRAM | Время/кадр | Вердикт |
|------|-------------|------|--------|----------|------------|---------|
| A — baseline | SDXL Base 1.0, 768×768, fp16, vae_slicing+tiling+model_cpu_offload, **без адаптера** | Нет | 45/45 | **5 196 МБ** | ~20.1 с | **ПРОЙДЁН (контрольная точка)** |
| B — IP-Adapter Plus Face SDXL ViT-h | A + `ip-adapter-plus-face_sdxl_vit-h` (scale 0.7) | Нет | 0/45 | 5 106 МБ | — | Не пригоден (ошибка интеграции адаптера) |
| C — IP-Adapter Plus SDXL ViT-h (full-body) | A + `ip-adapter-plus_sdxl_vit-h` (scale 0.7) | Нет | 0/45 | 5 106 МБ | — | Не пригоден (ошибка интеграции адаптера) |
| D — комбинация Plus + Plus Face | A + Plus (0.7) + Plus Face (0.25) | Нет | 0/45 | 9 945,9 МБ | — | Не пригоден (пик близко к лимиту T4) |

Генерация велась для 5 фиксированных seed (42, 123, 777, 2026, 9001) × 9 сценариев:
`crowd portrait close-up`, `side profile`, `full body standing`, `dynamic action pose`, `different lighting`, `different emotion`, `different outfit detail visible`, `different background`, `group scene with other character`.

Имена файлов: `<test>_<seed>_<scenario>.png` (например, `A_baseline_42_crowd_portrait_close_up.png`).

## Пояснение по Тестам Б/В/Г

Тесты Б и В **не упали с OOM** (пик 5 106 МБ — значительно ниже утреннего результата 13,9 ГБ, благодаря vae_slicing/tiling/model_cpu_offload), но **не выпустили ни одной картинки**: `diffusers 0.40` + `h94/IP-Adapter` несовместимы по API `ip_adapter_image_embeds` (ошибки подряд: размерность матриц 1664 vs 1280, тип `list` vs `Tensor`, ранг 2D vs 3D/4D, `not enough values to unpack`). Каждый прогон чистил одну ошибку и открывал следующую — это несостыковка интеграции адаптера, а не нехватка памяти.

Тест Г (комбинация) не имеет смысла запускать, пока Б и В не выдают картинки; кроме того пик комбинации 9 945,9 МБ близко к лимиту T4 (14,56 ГБ) — риск OOM на реальных сценах高.

## Шаг 6 — оценка консистентности (6 категорий × сценарии, шкала 1–5)

Оценка возможна только по **сгенерированным изображениям**. Картинки есть только у Теста A. У Б/В/Г — 0 картин, поэтому таблицы по категориям для них не заполняются (NOT_CHECKED, требуется доработка адаптера и повторный прогон).

**Тест A (baseline, без адаптера):** human visual scoring ещё не выполнено — требуется просмотр владельцем 45 PNG в `tools/kaggle_bridge/jobs/consistency-ab-test/`. Структура таблицы для заполнения (по каждому сценарию, 1–5):

| Категория | crowd close-up | side profile | full body | dynamic pose | diff. lighting | diff. emotion | diff. outfit | diff. background | group scene |
|-----------|---------------|--------------|-----------|--------------|----------------|---------------|--------------|------------------|-------------|
| face/hair | — | — | — | — | — | — | — | — | — |
| outfit | — | — | — | — | — | — | — | — | — |
| silhouette | — | — | — | — | — | — | — | — | — |
| accessories | — | — | — | — | — | — | — | — | — |
| line-art style consistency | — | — | — | — | — | — | — | — | — |
| scene fit | — | — | — | — | — | — | — | — | — |

`—` = NOT_CHECKED (предметно-ориентированная визуальная оценка владельцем, не автоматическая).

## Шаг 7 — итоговый отчёт

**Какой тест прошёл без OOM с лучшим пиком VRAM:**  
Тест A — единственный, который и не упал с OOM, и выпустил картинки (45/45). Пик 5 196 МБ (5,2 ГБ) — комфортно в лимите T4 14,56 ГБ. Тесты Б/В/Г не дают картин (ошибка интеграции IP-Adapter), поэтому «лучший по пику» среди них не имеет значения.

**Где «плывёт» консистентность:**  
Не определится по сгенерированным кадрам, т.к. адаптеры не отработали. Тест A без адаптера не обеспечивает консистентность персонажа по определению (задаётся только сидом+pромптом). IP-Adapter Plus Face / Plus не запустились из-за несовместимости `image_embeds` API с diffusers 0.40.

**Рекомендация для пилотного эпизода:**  
Использовать **Тест A (SDXL Base 1.0, 768×768, fp16, vae_slicing + vae_tiling + model_cpu_offload, без IP-Adapter)** как базу для пилота, консистентность — через фиксированный seed + единый промпт персонажа (PROJECT_PLAN §8, O8 вариант «а»). IP-Adapter-консистентность отложить на отдельный timebox после пилота (вариант «б»), с предварительным исправлением интеграции `h94/IP-Adapter` под diffusers 0.40. Комбинировать адаптеры (Тест Д) не рекомендовать: пик 9,9 ГБ близко к потолку T4 и интеграция нерабочая.

**Заблокировано:** визуальная оценка консистентности — пока нет исправленных картинок Б/В/Г; владельцу следует просмотреть 45 PNG Теста A и выставить оценки 1–5 по таблице выше.
