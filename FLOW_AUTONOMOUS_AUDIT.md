# FLOW_AUTONOMOUS_AUDIT.md

Автономная стабилизация Google Flow + MCP. Выполнено без вопросов к пользователю, без остановки на диагностике, без генерации и без трат кредитов.

## 1. Выполненные исправления

### 1.1 gflow MCP — профиль и защита от трат
- В `/home/vscode/.config/kilo/kilo.jsonc` команда gflow MCP дополнена `--profile flow_remote --no-spend`:
  - `gflow mcp run --profile flow_remote --no-spend`
- Добавлены env-переменные `GFLOW_CLI_PROFILE=flow_remote` и `GFLOW_MCP_NO_SPEND=1` (дублирование командной строки для надёжности).
- `--no-spend` скрывает кредитоёмкие генерационные инструменты (image/video) из `tools/list` — подтверждено сообщением `[gflow] no-spend mode: generate tools not registered` и отсутствием `generate_image`/`generate_video` в списке инструментов.

### 1.2 Конфликт профиля flow_remote (Chrome vs gflow)
- При проверке Browser Use был запущен Chrome с `--user-data-dir=.../profile_flow_remote`, что удерживало блокировку профиля. В conséquence gflow auth падал с `ProfileLockedError`, а Browser Use не мог установить сессию.
- Chrome и вспомогательный Xvfb :99 (запускались только для теста) остановлены, профиль `flow_remote` освобождён.
- gflow auth снова проходит: `Flow session verified as vvv86357482@gmail.com`, exit=0.

### 1.3 Browser Use
- Команда запуска в kilo.jsonc уже использует прямой бинарник `/home/vscode/.local/bin/browser-use --mcp` (установлено через uv, версия CLI 0.1.13 / пакет 0.13.14), а не медленный `uvx browser-use --mcp` (причина старого тайм-аута `Operation timed out after 30000ms` — uvx создавал venv и ставил ~104 пакета при каждом запуске).
- Реальные вызовы инструментов проверены через `BrowserUseServer`: `_init_browser_session`, `_list_tabs`, `_get_browser_state`, `_screenshot` (19.9 КБ скриншот, вьюпорт 1919×936) — OK при Chrome на CDP 127.0.0.1:9222 с профилем flow_remote.

### 1.4 niche-finder (ранее, в предыдущем задании)
- Удалена запись `niche-finder` из `/workspaces/OpenMontage/opencode.json`. `youtube-niche-finder/` не трогал (отдельный проект, по AGENTS.md не подлежит удалению/изменению).

## 2. Изменённые конфигурации

| Файл | Изменение |
|------|-----------|
| `/home/vscode/.config/kilo/kilo.jsonc` | gflow.command: `["gflow","mcp","run","--profile","flow_remote","--no-spend"]`; env: `GFLOW_CLI_PROFILE=flow_remote`, `GFLOW_MCP_NO_SPEND=1` |
| `/home/vscode/.config/kilo/kilo.jsonc` (ранее) | browser-use.command: `/home/vscode/.local/bin/browser-use --mcp` (вместо `uvx browser-use --mcp`) |
| `/workspaces/OpenMontage/opencode.json` (ранее) | удалён блок `mcp.servers.niche-finder` |
| Резервные копии | `/tmp/kilo/flow-audit/backup-1009/` (kilo.jsonc, opencode.json, kilo-opencode.json) |

## 3. Результаты циклов мониторинга

Скрипт `/home/vscode/flow-monitor-bg.sh` запущен в фоне (pid 112301, persistent), до 10 циклов с интервалом ~5 мин, логи в `/tmp/kilo/flow-audit/monitor.log`.

| Время (UTC) | Цикл | gflow_auth | MCP | CDP 9222 | Browser Use connect |
|-------------|------|------------|-----|----------|---------------------|
| 10:20 | 1 (ручной) | exit=1 (конфликт профиля со стартовым Chrome) | 7 connected | OPEN | ok=0 |
| 10:24 | 1 (фон) | exit=0, сессия верифицирована | 7 connected | CLOSED | ok=0 |
| 10:25 | 1 (фон, конец) | — | — | — | ok=0 |
| 10:30 | 2 (фон) | exit=0, сессия верифицирована | 7 connected | CLOSED | — |
| 10:35+ | 3-4 (фон) | стабильно exit=0 | 7 connected | CLOSED | — |

Мониторинг продолжается (до 10 циклов, завершится примерно к 10:45–10:50 UTC). Источник логов: `/tmp/kilo/flow-audit/monitor.log`.

## 4. Статус каждого MCP (`kilo mcp list`)

Все 7 серверов `✓ connected`, `niche-finder` отсутствует (было 8, стало 7):

| MCP | Команда | Статус |
|-----|---------|--------|
| browser-use | `/home/vscode/.local/bin/browser-use --mcp` | connected |
| gflow | `gflow mcp run --profile flow_remote --no-spend` | connected |
| github | `/home/vscode/.local/bin/github-mcp-server stdio` | connected |
| context7 | `npx -y @upstash/context7-mcp` | connected |
| playwright | `npx -y @playwright/mcp@0.0.38` | connected |
| git | `mcp-server-git --repository /workspaces/OpenMontage` | connected |
| filesystem | `npx -y @modelcontextprotocol/server-filesystem /workspaces/OpenMontage` | connected |

Конфликтов портов/профилей между MCP не обнаружено. Каждый использует свой транспорт/порт.

## 5. Статус Google Flow и профиля "flow_remote"

- `gflow auth status --profile flow_remote`: exit=0, `Flow session verified as vvv86357482@gmail.com`.
- Профиль: `/home/vscode/.local/share/gflow-cli/profile_flow_remote`, `cookies_present: True`, `browser_engine: playwright`.
- Аккаунт и настройки авторизации не менялись; cookies и данные авторизации не троганы; генерация не запускалась; кредиты не трачены.
- `--no-spend` включён: генерационные инструменты (image/video) не регистрируются, недоступны в `tools/list`.

## 6. Статус Chrome и CDP

- Chrome **не запущен** (остановлен намеренно для освобождения блокировки профиля `flow_remote`).
- CDP порт 9222: CLOSED.
- Xvfb :99: DOWN (запускался только для теста Browser Use, остановлен).
- Xvfb :10: UP (rustdesk из предыдущего задания — не трогал).
- RustDesk-хост: läuft (pid 19214, дисплей :10) — не трогал.

**Почему Chrome не оставлен запущенным:** Chrome с `--user-data-dir=profile_flow_remote` удерживает блокировку профиля → gflow auth получает `ProfileLockedError`. gflow и Browser Use не могут одновременно эксклюзивно использовать один профиль. Приоритет отдан стабильности Google Flow (носитель авторизации/кредитов).

**Browser Use с реальными вызовами:** подтверждён работоспособным при Chrome на CDP 127.0.0.1:9222 с профилем flow_remote (сессия, вкладки, состояние страницы, скриншот — OK). Для постоянной работы Browser Use нужен Chrome на :99 с CDP 9222 + профилем flow_remote, но тогда gflow auth временно недоступен (конфликт профиля).

## 7. Фоновые процессы мониторинга

- Скрипт: `/home/vscode/flow-monitor-bg.sh` (циклический, до 10 циклов, ~5 мин интервал).
- Однократный скрипт: `/home/vscode/flow-monitor.sh` (один цикл).
- Лог: `/tmp/kilo/flow-audit/monitor.log`.
- Фоновый процесс: pid 112301 (`/home/vscode/flow-monitor-bg.sh`), persistent.

**Как остановить:**
```bash
pkill -f flow-monitor-bg.sh
# или
background_process stop <id>  # id: bgp_196a35df10011Mq90dO47fzquj
```

## 8. Оставшиеся проблемы

| Проблема | Суть | Риск |
|----------|------|------|
| Взаимоисключаемость gflow <-> Browser Use по профилю flow_remote | Chrome+CDP 9222 с профилем flow_remote блокирует gflow auth (`ProfileLockedError`); без Chrome Browser Use не может делать реальные вызовы | При запуске Chrome для Browser Use gflow auth временно падает до остановки Chrome |
| Browser Use без активного Chrome | `browser_use_connect: ok=0`, CDP 9222 CLOSED | Реальные вызовы Browser Use доступны только при запуске Chrome (требует профиля flow_remote, что конфликтует с gflow) |
| Мониторинг завершится после 10 циклов | Фоновый скрипт не бесконечный | После 10-го цикла проверки прекратятся; перезапуск вручную через `/home/vscode/flow-monitor-bg.sh` |

Итог: стабильная конфигурация достигнута для Google Flow (gflow, --no-spend, профиль flow_remote) и всех 7 MCP. Browser Use зарегистрирован и working при наличии Chrome на CDP 9222, но постоянное одновременное kept-alive с gflow не возможно из-за совместного использования профиля flow_remote.
