# gflow CLI — полное техническое руководство

Установленная версия: `gflow 0.92.0` (PyPI пакет `gflow-cli`, путь `/home/vscode/.local/bin/gflow`).
Это driven-инструмент для Google Flow (Imagen для изображений, Veo для видео). Весь CLI — read-only по умолчанию кроме явных генераций; платящие операции защищены флагом `--no-spend` в MCP-режиме.

## 1. Группа команд и навигация

```
gflow [--version] [--verbose] <command> [subcommand] [options]
```

Команды (все подкоманды имеют `--help`):

| Команда | Назначение |
|---|---|
| `auth` | Управление сессиями/профилями Google Flow |
| `character` | Персонажи (CHARACTER entities) проекта |
| `credits` | Баланс кредитов (read-only, не тратит) |
| `data` | Локальная история медиа (каталог, download, sync, errors) |
| `docs` | Офлайн-документация gflow |
| `doctor` | Read-only проверка здоровья окружения (exit 33 при предупреждениях) |
| `image` | Генерация изображений через Imagen (t2i, i2i, batch, upload, upscale) |
| `instructions` | Карты инструкций проекта (Agent-Mode brief) |
| `mcp` | MCP-сервер (stdio `run`, настройка `setup`) |
| `models` | Каталог моделей изображений и видео |
| `movie` | Многосценарийный фильм из `movie.toml` (run, template) |
| `project` | Проекты Flow (create, list, rename, show) |
| `run` | Пакетная генерация изображений из JSON-конфига |
| `scene` | Сборка клипов в Scene Flow (create, show) |
| `serve` | HTTP MCP-сервер |
| `tools` | Prompt-инструменты (list, run, show) |
| `update` | Обновление CLI |
| `video` | Генерация видео через Veo (t2v, i2v, r2v, chain, extend, upscale) |

## 2. Авторизация и профили (`gflow auth`)

`gflow auth` (без подкоманды) показывает инвентарь профилей; если нет профилей — запускает `auth login`.

| Подкоманда | Назначение |
|---|---|
| `auth list` | Все профили и текущий default |
| `auth login` | Интерактивный вход в Flow (открывает браузер) |
| `auth logout` | Удалить сессию профиля (необратимо) |
| `auth renew` | Обновить сессию headlessly, без повторного входа |
| `auth status` | Есть ли сохранённая сессия и валидна ли она |
| `auth use <NAME>` | Установить профиль по умолчанию |

Профили хранятся в `/home/vscode/.local/share/gflow-cli/profile_<name>/`. Текущий профиль: `flow_remote`, аккаунт `vvv86357482@gmail.com` (верифицировано через `gflow auth status`).

**Важное окружение:** в Codespace/контейнере Chrome падает с песочником и в headed-режиме. Для любых команд, открывающих браузер (credits, image, video, character) необходимо:
- `GFLOW_CLI_HEADLESS=true` — без этого `--headless=False` и Chrome упадёт (`Operation not permitted` на пространствах имён).
- Системный Chrome по пути `/opt/google/chrome/chrome` уже обёрнут с `--no-sandbox` (требуется в этом контейнере).

## 3. Кредиты (`gflow credits`)

Read-only. Открывает `flow.google.com` в профиле и читает баланс из меню аккаунта. Ничего не тратит.

```
gflow credits user        # баланс текущего профиля
gflow credits list        # все профили
```

Результат例子:
```
Profile: flow_remote
Google account: vvv86357482@gmail.com
Credits: 50
```

## 4. Модели (`gflow models`)

```
gflow models              # таблица
gflow models --json       # JSON-каталог
```

### Изображения (Imagen)

| Модель | Алиасы | ref_cap | По умолчанию |
|---|---|---|---|
| NARWHAL (Nano Banana 2.1) | nano2, nano2.1, nano-2.1 | 10 | да |
| GEM_PIX_2 (Nano Banana Pro) | nano-pro | 10 | нет |
| IMAGEN_3_5 (Imagen 4) | image4, imagen4 | 3 | нет |
| HARBOR_SEAL (Nano Banana 2 Lite) | nano2-lite | 3 | нет |

Соотношения сторон: `9:16`, `16:9`, `1:1`, `4:3`, `3:4`.

### Видео (Veo)

| Модель | Алиас | ref_cap | max_duration |
|---|---|---|---|
| omni_flash | omni-flash | 7 | 10с |
| veo_3_1_lite | veo-lite | 3 | 8с |
| veo_3_1_fast | veo-fast | 3 | 8с |
| veo_3_1_quality | veo-quality | 0 | 8с |
| veo_3_1_lite_lower_priority | veo-lite-lp | 3 | 8с |

`omni-flash` — единственная модель с `--duration 10`. `veo-quality` не поддерживает R2V (ref_cap=0).

## 5. Изображения (`gflow image`)

### 5.1 t2i — текст → изображение

```
gflow image t2i "ПРОМПТ" [--aspect R] [--model M] [-n N] [--out DIR] [-o FILE] [--project ID] [--reference-entity ID ...] [--json] [--transport T] [--profile P]
```

Ключевые параметры:

| Параметр | Значение по умолчанию | Допустимые значения | Примечание |
|---|---|---|---|
| `PROMPT` (positional,repeatable) | — | текст, 1–2000 символов | Несколько промптов = мульти-промпт режим |
| `--aspect` | `9:16` | `9:16`, `16:9`, `1:1`, `4:3`, `3:4` | |
| `--model` | `nano2` | `nano2`, `nano2.1`, `nano-2.1`, `nano-pro`, `nano2-lite`, `image4`, `imagen4` | |
| `-n/--count` | `1` | `1–4` | Сколько изображений на промпт |
| `--out` | `<output_dir>/images/<YYYY-MM-DD>/` | директория | Плоская запись `<media_name>_<n>.png` |
| `-o/--output` | — | путь к файлу | Только для одиночного промпта |
| `--project` | создаётся scratch-проект | ID существующего Flow-проекта | Требуется для locked entities/assets |
| `--reference-entity` | — | ID CHARACTER-сущности | Повторяется; shared ref-бюджет с `--ref` |
| `--json` | флаг | — | Машинный вывод вместо Rich-таблицы |
| `--transport` | `ui_automation` | см. `transport_choices()` | `GFLOW_CLI_TRANSPORT` или `GFLOW_CLI_EXPERIMENTAL_TRANSPORTS=1` |
| `--profile` | default | имя профиля | |
| `--tool` / `-i/--instruction` | — | prompt-инструмент | Агентный режим, 단 для одного промпта |
| `--jitter` | `0.5–1.5` с | `MIN-MAX` или `0` | Анти-бот пауза между промптами |

Пример (одно изображение, 16:9):
```
gflow image t2i "A bioluminescent deep-sea alien creature..." --aspect 16:9 -n 1 --out ./assets/generated
```

### 5.2 i2i — изображение → изображение (с референсами)

```
gflow image i2i "ПРОМПТ" --ref ПУТЬ_ИЛИ_UUID [--ref ...] [--aspect R] [--model M] [-n 1-4] [--out DIR] [-o FILE]
```

`--ref` обязателен и повторяемый. Локальный путь автозагружается; UUID уже загруженного актива передаётся как есть. Сумма `--ref` + `--reference-entity` не должна превышать `ref_cap` модели.

### 5.3 batch — пакетная генерация изображений (max 5 промптов)

```
gflow image batch --manifest ПУТЬ_К_ТОML_ИЛИ_JSON [--out DIR] [--continue-on-error/--fail-fast] [--profile P]
```

Максимум 5 промптов в одном батче. Поддерживает `--resume` (пропускает уже выполненные строки) и `--project` (в существующий проект, а не scratch).

### 5.4 upload — загрузка локального изображения

```
gflow image upload ПУТЬ_К_ФАЙЛУ [--profile P]
```

Загружает в библиотеку проекта, возвращает media UUID и габариты.

### 5.5 upscale — апскейл сгенерированного изображения

```
gflow image upscale <media_id> --scale 2k|4k [--project P] [--out_dir DIR]
```

4k требует Ultra-подписку; 2k доступно Pro/Plus. Бесплатно (апскейл изображения не тратит кредиты генерации).

### 5.6 Формат вывода и сохранение

- По умолчанию: `<output_dir>/images/<YYYY-MM-DD>/<media_name>_<n>.png`.
- `--out DIR`: плоская запись в указанную директорию.
- `-o FILE`: явный путь к файлу (single-prompt только).
- Все артефакты пишутся в локальный каталог gflow + дублируются на диск.

## 6. Видео (`gflow video`)

### 6.1 t2v — текст → видео

```
gflow video t2v "ПРОМПТ" [--aspect 9:16\|16:9] [--model M] [--duration 4\|6\|8\|10] [--resolution 360p\|720p] [-n 1-4] [--out-dir DIR] [-o FILE] [--project ID] [--reference-entity ID ...] [--json] [--profile P]
```

| Параметр | Default | Допустимо | Примечание |
|---|---|---|---|
| `--aspect` | `9:16` | `9:16`, `16:9` | |
| `--model` | default Flow | `omni-flash`, `veo-lite`, `veo-fast`, `veo-quality`, `veo-lite-lp` | Только `omni-flash` поддерживает `--duration 10` |
| `--duration` | default Flow | `4`, `6`, `8`, `10` | Отказ pre-submit (без списания) если нет контроля длительности |
| `--resolution` | default | `360p`, `720p` | Только для моделей со строкой разрешения (omni-flash) |
| `-n/--count` | `1` | `1–4` | >1 умножает стоимость кредитов |
| `--reference-entity` | — | CHARACTER ID | Только t2v/r2v (не i2v) |

### 6.2 i2v — изображение → видео (кадр + motion prompt)

```
gflow video i2v [ИЗОБРАЖЕНИЕ] "МОЦИОН_ПРОМПТ" [--initial-frame ПУТЬ\|UUID] [--end-frame ПУТЬ\|UUID] ...
```

Кадр может быть локальным файлом (валидируется как изображение) или media UUID. При `--initial-frame` достаточно только позиционного PROMPT. Поддерживает те же `--aspect`, `--model`, `--duration`, `--resolution`, `--count`, `--out-dir`, `-o`, `--json`, `--profile`, `--project`.

### 6.3 r2v — референс → видео (несколько изображений + промпт)

```
gflow video r2v "ПРОМПТ" --ref ПУТЬ [--ref ...] [--aspect R] [--model M] [--duration D] [--resolution R] [-n 1-4]
```

Лимиты референсов по модели: `omni-flash=7`, `veo-lite/fast/lite-lp=3`, `veo-quality=0` (R2V отвергается).

### 6.4 chain — цепочка клипов (последовательный I2V)

```
gflow video chain МАНИфест [--model veo-lite\|veo-fast\|veo-quality\|veo-lite-lp] [--max-links N] [--resume-from ID] [--jitter S] [--seed-offset MS] [--aspect 9:16\|16:9] [--yes] [--dry-run] [--out-dir DIR] [-o FILE] [--json] [--profile P]
```

Манифест — описание связей (links) в цепочке. Каждый следующий клип начинается с последнего кадра предыдущего (seed frame). `omni-flash` намеренно отсутствует (цепочки остаются на верифицированных Veo 3.1). Поддерживает `--resume-from` для восстановления после прерывания.

### 6.5 extend — продолжение клипа на +8 сек

```
gflow video extend <MEDIA_ID> "ПРОМПТ_1" ["ПРОМПТ_2" ...] [--aspect 9:16\|16:9] [-n/--segments 1-30] [--jitter S] [-o FILE] [--scene ID] [--resume-from ID] [--seed N] [--yes] [--dry-run] [--profile P] [--json]
```

Каждый промпт = один 8-секундный сегмент continuations. `--segments` или число промптов определяет количество. `--resume-from` позволяет продолжить прерванную сцену без повторного списания за уже выполненные сегменты. Требует подтверждения (`--yes` пропускает) и `--dry-run` показывает план без списания.

### 6.6 upscale видео

```
gflow video upscale <media_id> --scale 720p\|1080p\|270p [--out DIR] [--profile P]
```

1080p Full HD, 720p оригинал, 270p анимированный GIF. Апскейл видео — платная операция.

## 7. Персонажи (`gflow character`)

Персонажи — CHARACTER сущности в Flow-проекте, обеспечивающие визуальную идентичность между генерациями.

### 7.1 create

```
gflow character create --project ID --name ИМЯ --face-prompt "ПРОМПТ_ЛИЦА" [--body-prompt "ОДЕЖДА/ТЕЛО"] [--voice ИМЯ] [--personality ТЕКСТ] [--model nano2\|nanopro] [--format-prompt] [--profile P] [--locale LOCALE] [--json]
```

- Генерирует эталон лица (и тела), сохраняет сущность, возвращает `entity_id`, `workflow_ids`, `primary_media_ids`, пути к изображениям.
- `--body-prompt` оборачивается в инструкцию триптиха front/side/back.
- `persist-before-spend` сага — прерванный запуск восстанавливается.

### 7.2 list / show / rm / voices

```
gflow character list --project ID [--json]
gflow character show --project ID --id UUID|--name ИМЯ [--json]
gflow character rm --project ID --id UUID|--name ИМЯ [--yes] [--json]
gflow character voices [--json]
```

`voices` — каталог preset-голосов для Character TTS (имя, описание, sample_url).

## 8. Пакетная генерация изображений (`gflow run`)

JSON-конфиг с верхним ключом `prompts` (список). Максимум 50 промптов, в батче — максимум 5.

Схема конфига (`_ALLOWED_TOP_LEVEL_KEYS = {profile, transport, output_dir, project, prompts}`):

```json
{
  "profile": "flow_remote",
  "transport": "ui_automation",
  "output_dir": "./assets/generated",
  "project": "FLOW_PROJECT_ID",
  "prompts": [
    {
      "text": "Описание сцены...",
      "aspect_ratio": "16:9",
      "model": "nano2",
      "count": 1,
      "output_filename": "s001.png",
      "ref": "batch:0",
      "reference_entity": "CHAR_ID"
    }
  ]
}
```

Допустимые ключи промпта: `text`, `aspect_ratio`, `model`, `count`, `output_filename`, `ref`, `reference_entity`.
- `ref` может быть `batch:<индекс>` (ссылка на изображение предыдущей строки, count=1) или локальный путь к файлу.
- Запуск: `gflow run --config batch.json [--output-dir DIR] [--profile P] [--project ID] [--continue-on-error/--fail-fast] [--resume]`

`--resume` пропускает уже выполненные строки (файлы в output_dir записаны в локальном каталоге), что позволяет восстанавливаться после сбоя без повторной генерации.

## 9. movie.toml — многосценарийный фильм (`gflow movie`)

```
gflow movie template [выходной_файл.toml]     # starter template
gflow movie run movie.toml [--stitch] [--dry-run] [--profile P]
```

Структура `movie.toml`:

```toml
schema_version = 1
title = "Название фильма"
project = "FLOW_PROJECT_ID"
output_dir = "./out/film"

[style]
look = "кинематографический, мало глубины резкости"
palette = "тёплые золотые тона"
negative = "no text, no watermark"
suffix = "Дополнительный суффикс стиля."

  [style.variants.warm]
  suffix = "Теплый golden-hour оттенок."

[[characters]]
name = "Алиса"
appearance = "Молодая женщина с кудрявыми рыжими волосами, зелёные глаза"
voice = "alnilam"
  [characters.variants]
  silhouette = "только силуэт"

[[scenes]]
id = "s001"
action = "Описание действия сцены"
framing = "establishing"
camera = "slow pan"
lighting = "мягкий рассеянный"
mood = "таинственный"
negative = "дополнительный негатив"
characters = ["Алиса"]
variant = "warm"
dialogue = [{ speaker = "Алиса", line = "Мы на месте!", voice = "alnilam" }]
duration = 8
model = "omni-flash"
aspect = "16:9"
count = 1
style_variant = "warm"
style_suffix = "золотой свет"
```

Поля сцены (`Scene`): `id`, `action`, `title`, `setting`, `framing` (из `FRAMING`), `camera`, `lighting`, `mood`, `negative`, `characters` (имена), `variant`, `dialogue` (список `DialogueLine`), `duration` (4/6/8/10), `model`, `aspect` (по умолчанию `16:9`), `count` (по умолчанию 1), `style_variant`, `style_suffix`, `instructions`.

Порядок сборки промпта (`compose_prompt`): prefix + action + subject(+variant) + setting + look + palette + lighting + framing+camera + mood + dialogue + negative + suffix.

`--stitch` — опциональная жёсткая конкатенация клипов ffmpeg (предпросмотр, не релиз). `--dry-run` — план без API-вызовов. Состояние запуска пишется в `<stem>-state.json` для восстановления после сбоя.

## 10. Инструкции проекта (`gflow instructions`)

Карты инструкций (Agent-Mode brief) управляют каждой генерацией в проекте. Требуют `--project`.

| Подкоманда | Назначение |
|---|---|
| `instructions add --project ID --title T --text T [--ref ...] [--enabled]` | Добавить карту |
| `instructions apply --project ID` | Полная синхронизация из TOML/JSON файла |
| `instructions list --project ID` | Список карт |
| `instructions enable/disable --project ID --id|--title` | Включить/выключить карту |
| `instructions rm --project ID --id|--title` | Удалить карту |
| `instructions toggle-mode --project ID --enabled` | Главный переключатель brief |

Бесплатно (добавление/список/переключение/удаление не тратят кредиты).

## 11. Данные и каталог (`gflow data`)

| Подкоманда | Назначение |
|---|---|
| `data list` | Записи каталога локальной истории медиа |
| `data media <media_id>` | Метаданные локального актива по media UUID |
| `data download <media_id>` | Скачать уже сгенерированное видео с Flow по media ID |
| `data sync` | Сверка безымянных строк каталога с удалённым проектом Flow |
| `data errors` | История неудачных операций: экспорт/архив |
| `data prune` | Удалить строки local_files, путь которых исчез с диска |

## 12. Проекты Flow (`gflow project`)

| Подкоманда | Назначение |
|---|---|
| `project create` | Новый Flow-проект (двусторонняя синхронизация заголовка) |
| `project list` | Список записанных локально проектов |
| `project rename <ID>` | Переименование с синхронизацией |
| `project show <ID>` | Детали по ID |

## 13. MCP-сервер (`gflow mcp run` / `gflow serve`)

- `gflow mcp run` — stdio-транспорт для IDE/агентов (Kilo).
- `gflow serve --port 8000` — HTTP/MCP Streamable HTTP (+ устаревший SSE).
- `--no-spend` скрывает кредитные генерационные инструменты из `tools/list`.
- Переменная `GFLOW_MCP_NO_SPEND=1` то же самое.

Доступные read-only инструменты gflow MCP: `gflow_auth_status`, `gflow_list_projects`, `gflow_list_models`, `gflow_get_credits`. Генерационные (`gflow_generate_image`, `gflow_generate_video`) скрыты под `--no-spend`.

В OpenMontage дополнительный уровень защиты — `lib/mcp_security_proxy.py` с default-deny allowlist (см. PROJECT_STATE_HANDOFF.md §11).

## 14. Инструменты (`gflow tools`)

`gflow tools list` — каталог prompt-инструментов; `gflow tools show <имя>` — детали; `gflow tools run <имя> ...` — выполнение. Требуют `GFLOW_CLI_LLM_API_KEY` и/или `GFLOW_CLI_LLM_BASE_URL` (OpenAI-совместимый эндпоинт); при отсутствии fallback к исходному промпту.

## 15. health-check (`gflow doctor`)

```
gflow doctor [--json]
```

Read-only диагностика каталога, БД и окружения. Exit 0 при чистоте, 33 при предупреждениях/ошибках. Ничего не мигрирует и не пишет.

## 16. Переменные окружения

| Переменная | Назначение |
|---|---|
| `GFLOW_CLI_HEADLESS=true` | Запуск браузера headless (обязательно в CI/контейнере без дисплея) |
| `GFLOW_CLI_LEASE_WAIT_SECONDS=N` | Ожидание освобождения блокировки профиля |
| `GFLOW_CLI_JITTER_RANGE=N-M` | Диапазон анти-бот паузы |
| `GFLOW_CLI_TRANSPORT=T` | Транспорт по умолчанию |
| `GFLOW_CLI_PROJECT_NAME=T` | Название проекта по умолчанию |
| `GFLOW_CLI_BROWSER_PROXY=T` | Прокси браузера |
| `GFLOW_CLI_LLM_API_KEY` / `GFLOW_CLI_LLM_BASE_URL` | Для prompt-инструментов |
| `GFLOW_MCP_NO_SPEND=1` | Скрыть генерационные инструменты в MCP |
| `GFLOW_CLI_DAEMON_TOKEN` / `GFLOW_DAEMON_TOKEN` | Токен для `gflow serve` на non-loopback хосте |
| `CHROME_BINARY` | Путь к бинарному файлу Chrome (override) |

## 17. Обработка ошибок и восстановление

- Коды выхода: `0` — успех; `11` — ошибка профиля/конфигурации; `2` — ошибка аргументов Click; `33` — doctor warning/fail.
- `--continue-on-error` (по умолчанию)继续 после сбоя отдельного промпта; `--fail-fast` останавливает батч.
- `--resume` (run и chain) пропускает уже выполненные строки/ссылки.
- `movie.toml` пишет `<stem>-state.json` для восстановления после краша без повторного списания.
- `gflow data errors` ведёт историю неудач; `data sync` восстанавливает каталог.
- Локальный каталог и метаданные позволяют сверить, что файл реально сохранён (`data media <id>`).

## 18. Рабочие примеры команд

### Одно изображение (16:9)
```bash
GFLOW_CLI_HEADLESS=true gflow image t2i "A unique bioluminescent deep-sea alien creature..." --aspect 16:9 -n 1 --out ./assets/generated
```

### Пакет 100 изображений через JSON
```bash
# batch.json с 100 строками prompts[]
GFLOW_CLI_HEADLESS=true gflow run --config batch.json --output-dir ./assets/generated --profile flow_remote --continue-on-error
```

### Создание персонажа
```bash
GFLOW_CLI_HEADLESS=true gflow character create --project <PROJECT_ID> --name "Deep Sea Mascot" --face-prompt "bioluminescent alien face, lantern head" --body-prompt "six tendrils, two pairs of fins, deep navy teal" --model nano2 --json
```

### Видео из текста (16:9, 8 сек)
```bash
GFLOW_CLI_HEADLESS=true gflow video t2v "alien creature swims in deep ocean" --aspect 16:9 --duration 8 --model omni-flash -n 1 --out-dir ./assets/video
```

### Видео из изображения (i2v)
```bash
GFLOW_CLI_HEADLESS=true gflow video i2v ./assets/generated/s001.png "camera slowly pushes in on the creature" --aspect 16:9 --duration 8 --out-dir ./assets/video
```

### Цепочка клипов (chain)
```bash
GFLOW_CLI_HEADLESS=true gflow video chain links.json --model veo-lite --aspect 16:9 --resume-from <CHAIN_ID> --dry-run
```
