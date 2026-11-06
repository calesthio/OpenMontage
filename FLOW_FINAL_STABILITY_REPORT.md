# FLOW_FINAL_STABILITY_REPORT.md

Финальный отчёт: архитектура Google Flow + Browser Use с независимыми профилями. Выполнено автономно, без генерации, без трат кредитов, без вывода секретов.

---

## 1. Итоговая схема процессов и профилей

### Процессы (рабочие)

| PID | Процесс | Роль | Дисплей/Порт |
|-----|---------|------|--------------|
| 6461 | Xvfb :10 | Виртуальный дисплей для RustDesk (предыдущее задание) | :10 |
| 19214 | rustdesk | RustDesk-хост (не трогал) | :10 |
| 146006 | Xvfb :99 | Виртуальный дисплей для Browser Use Chrome | :99 |
| 146072 | google-chrome | Chrome для Browser Use, профиль `flow-mobile` | CDP 9223 |
| 146088, 146090 | chrome_crashpad_handler | Вспомогательные процессы Chrome | — |

### Профили и их роли

| Профиль | Путь | Google-аккаунт | Роль | Используется в |
|---------|------|----------------|------|-----------------|
| `flow_remote` | `/home/vscode/.local/share/gflow-cli/profile_flow_remote` | `vvv86357482@gmail.com` (верифицировано) | Google Flow / gflow-cli | gflow MCP (`--profile flow_remote --no-spend`) |
| `flow-mobile` | `/home/vscode/.local/share/gflow-cli/profile_flow-mobile` | `vvv86357482@gmail.com` (верифицировано, ранее `unknown` → теперь известно) | Browser Use | Chrome на CDP 9223, отдельный процесс |

**Важно:** оба профиля авторизованы на **один и тот же аккаунт** `vvv86357482@gmail.com`, но это **разные профили** (разные user-data-dir). Это устраняет конфликт ProfileLease: gflow использует только `flow_remote`, Browser Use использует только `flow-mobile`.

### CDP-порты

| Порт | Статус | Использование |
|------|--------|---------------|
| 9222 | CLOSED | Ранее использовался для основного Chrome (остановлен) |
| 9223 | OPEN | Browser Use Chrome с профилем `flow-mobile` |

---

## 2. Выполненные исправления

### 2.1 gflow: профиль и защита от трат
- `/home/vscode/.local/share/gflow-cli/config.toml`: `default_profile = "flow-mobile"` → `"flow_remote"` (gflow теперь по умолчанию использует `flow_remote`).
- `/home/vscode/.config/kilo/kilo.jsonc` блок gflow: `gflow mcp run --profile flow_remote --no-spend`.
- kilo.jsonc env: `GFLOW_CLI_PROFILE=flow_remote`, `GFLOW_MCP_NO_SPEND=1`.
- `--no-spend` подтверждён: сообщение `[gflow] no-spend mode: generate tools not registered`, `generate_image`/`generate_video` не_registered (count=0 в tools/list).

### 2.2 Browser Use: отдельный профиль и порт
- `/home/vscode/.config/browseruse/config.json`: профиль переименован в `flow-mobile`, `cdp_url = http://127.0.0.1:9223`, `user_data_dir = .../profile_flow-mobile`.
- kilo.jsonc блок browser-use: `/home/vscode/.local/bin/browser-use --mcp` (прямой бинарник, не `uvx` — устранена причина тайм-аута 30 с).
- Запущен Chrome с `--user-data-dir=.../profile_flow-mobile --remote-debugging-port=9223` на Xvfb :99.

### 2.3 niche-finder (ранее)
- Удалена запись `niche-finder` из `/workspaces/OpenMontage/opencode.json`.

---

## 3. Изменённые конфигурации

| Файл | Изменение |
|------|-----------|
| `/home/vscode/.local/share/gflow-cli/config.toml` | `default_profile = "flow_remote"` |
| `/home/vscode/.config/kilo/kilo.jsonc` | gflow: `--profile flow_remote --no-spend`; env: `GFLOW_CLI_PROFILE=flow_remote`, `GFLOW_MCP_NO_SPEND=1`; browser-use: прямой бинарник |
| `/home/vscode/.config/browseruse/config.json` | профиль `flow-mobile`, cdp_url `9223`, user_data_dir `profile_flow-mobile` |
| Резервные копии | `/tmp/kilo/final-audit/backup-1051/` |

---

## 4. Состояние авторизации

| Профиль | `gflow auth status` | Аккаунт | Cookies |
|---------|---------------------|---------|---------|
| `flow_remote` | exit=0, `Flow session verified` | `vvv86357482@gmail.com` | present |
| `flow-mobile` | exit=0, `Flow session verified` | `vvv86357482@gmail.com` | present |

- Аккаунт не менялся. Cookies и данные авторизации не троганы.
- Генерация не запускалась, кредиты не трачены.

---

## 5. Проверка каждого MCP (`kilo mcp list`)

Все 7 серверов `✓ connected`. `niche-finder` удалён (было 8, стало 7).

| MCP | Команда | Статус |
|-----|---------|--------|
| browser-use | `/home/vscode/.local/bin/browser-use --mcp` | connected |
| gflow | `gflow mcp run --profile flow_remote --no-spend` | connected |
| github | `/home/vscode/.local/bin/github-mcp-server stdio` | connected |
| context7 | `npx -y @upstash/context7-mcp` | connected |
| playwright | `npx -y @playwright/mcp@0.0.38` | connected |
| git | `mcp-server-git --repository /workspaces/OpenMontage` | connected |
| filesystem | `npx -y @modelcontextprotocol/server-filesystem /workspaces/OpenMontage` | connected |

Конфликтов портов/профилей между MCP не обнаружено.

---

## 6. Результаты интеграционных тестов

### Последовательные тесты

| # | Тест | Результат |
|---|------|-----------|
| 1 | `gflow auth status --profile flow_remote` | exit=0, сессия верифицирована |
| 2 | Browser Use `browser_list_tabs` (CDP 9223) | 1 вкладка (about:blank) |
| 3 | Browser Use `browser_get_state` (CDP 9223) | STATE_LEN=309, URL about:blank, вьюпорт 1919×936 |
| 4 | Browser Use `browser_screenshot` (CDP 9223) | 26,684 байта скриншота |
| 5 | gflow read-only MCP (`tools/list` с `--no-spend`) | generate-инструменты отсутствуют (count=0) |

### Одновременный тест (gflow + Browser Use параллельно)

| Компонент | Результат |
|-----------|-----------|
| gflow auth status (flow_remote) | exit=0, сессия верифицирована |
| Browser Use (flow-mobile, CDP 9223) | SESSION ok, скриншот 26,552 байта |

**Отсутствие проблем:** не было `ProfileLockedError`, конфликтов user-data-dir, CDP disconnect, зависших MCP-процессов, конфликтов виртуальных дисплеев.

---

## 7. Проверка cdp_attach в gflow-cli

`cdp_attach` существует в `gflow_cli/auth/cdp_attach.py` как класс `CDPAttachStrategy` — это **стратегия авторизации** (`gflow auth login` через реальный Chrome с CDP), **не** режим подключения gflow MCP к внешнему уже запущенному Chrome. Это opt-in транспорт для входа, не для обхода ProfileLease.

**Решение:** не внедрять `cdp_attach` как экспериментальный транспорт. Основная архитектура построена на **независимых профилях** (gflow→flow_remote, Browser Use→flow-mobile), что устраняет конфликт без экспериментального транспорта.

---

## 8. Надёжность

- **Автоматический запуск MCP:** все 7 MCP подключаются через `kilo mcp list` (connected).
- **Процессы после перезапуска терминала:** MCP-серверы запускаются kilo при подключении (stdio transport), Chrome и Xvfb :99 — отдельные процессы, необходимые для Browser Use.
- **Сохранность профилей:** оба профиля (`flow_remote`, `flow-mobile`) сохранены, блокировки освобождены после остановки тестовых процессов.
- **Мониторинг:** скрипт `/home/vscode/flow-monitor-bg.sh` (pid 112301, persistent) продолжает проверки до 10 циклов, логи в `/tmp/kilo/flow-audit/monitor.log`. Бесконечных циклов перезапусков нет.

---

## 9. Оставшиеся действия, требующие человека

1. **Chrome для Browser Use** (PID 146072, CDP 9223, профиль `flow-mobile`) сейчас запущен и необходим для работы Browser Use. После завершения сессии его можно остановить (`pkill -f 'google-chrome.*9223'`), но тогда Browser Use потеряет возможность подключиться до перезапуска Chrome.
2. **При перезапуске Codespace:** нужно заново запустить Xvfb :99 и Chrome с профилем `flow-mobile` на CDP 9223, чтобы Browser Use заработал. gflow и все MCP работают без Chrome.
3. **Профиль `flow-mobile` авторизован** на тот же аккаунт, что и `flow_remote`. Дополнительная интерактивная авторизация не требуется.

---

## 10. Инструкции восстановления после перезапуска Codespace

```bash
# 1. Восстановить Xvfb :99 для Browser Use Chrome
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
sleep 2

# 2. Запустить Chrome с профилем flow-mobile на CDP 9223
DISPLAY=:99 google-chrome --remote-debugging-port=9223 \
  --user-data-dir=/home/vscode/.local/share/gflow-cli/profile_flow-mobile \
  --no-sandbox --disable-gpu --disable-dev-shm-usage \
  --window-size=1920,1080 --no-first-run &
sleep 10

# 3. Проверить CDP 9223
curl -s http://127.0.0.1:9223/json/version

# 4. gflow и все MCP доступны автоматически через kilo:
kilo mcp list

# 5. gflow auth (профиль flow_remote, по умолчанию):
GFLOW_CLI_PROFILE=flow_remote gflow auth status --profile flow_remote
```

**Остановить мониторинг:** `pkill -f flow-monitor-bg.sh` (или `background_process stop bgp_196a35df10011Mq90dO47fzquj`).

**Остановить Chrome Browser Use:** `pkill -f 'google-chrome.*9223'` (после этого Browser Use потеряет подключение до перезапуска Chrome).

---

## Итоговый статус

**Google Flow + Browser Use стабильно работают одновременно на независимых профилях:**

- ✅ gflow: профиль `flow_remote`, `--no-spend`, generate-инструменты скрыты, auth верифицирован.
- ✅ Browser Use: профиль `flow-mobile`, Chrome на CDP 9223, реальные вызовы (вкладки, состояние, скриншот) подтверждены.
- ✅ Одновременная работа: конфликтов профилей нет, `ProfileLockedError` отсутствует.
- ✅ Все 7 MCP подключены, `niche-finder` удалён.
- ✅ Генерация не запускалась, кредиты не трачены, аккаунт и авторизация не изменены.

**Остаток:** Chrome с профилем `flow-mobile` на CDP 9223 запущен и требуется для Browser Use; после перезапуска Codespace нужно перезапустить Xvfb :99 и Chrome (см. инструкции восстановления).
