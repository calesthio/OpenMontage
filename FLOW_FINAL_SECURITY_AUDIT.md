# FLOW_FINAL_SECURITY_AUDIT.md

Финальный аудит обхода безопасности — Google Flow + Browser Use + MCP Security Proxy
=====================================================================================

Проект: `/workspaces/OpenMontage`
Дата аудита: 2026-11-01
Статус: Завершён

---

## 1. Аудит возможностей Kilo CLI

### Активные permissions (`/home/vscode/.config/kilo/kilo.jsonc`)

| Permission | Значение | Примечание |
|------------|----------|------------|
| `*` → `*` | `allow` | Глобальное разрешение |
| `read` | `allow` | Чтение файлов |
| `glob` | `allow` | Поиск файлов |
| `grep` | `allow` | Поиск содержимого |
| `todowrite` | `allow` | Списки задач |
| `edit` | `/workspaces/OpenMontage/**`: `allow`, `*`: `ask` | Редактирование файлов |
| `bash` | `*`: `ask`, конкретные команды: `allow` | Выполнение команд требует одобрения |
| `task` | `ask` | Запуск субагентов |
| `webfetch` | `ask` | Веб-запросы |
| `websearch` | `ask` | Веб-поиск |
| `skill` | `ask` | Навыки |
| `external_directory` | `ask` | Внешние директории |
| `lsp` | `deny` | LSP заблокирован |

### Доступные среды выполнения

| Среда | Путь | Версия | Статус |
|-------|------|--------|--------|
| Python 3 | `/usr/local/bin/python3` | 3.12.16 | ✅ Доступна |
| Node.js | `/usr/local/share/nvm/.../node` | v26.13.0 | ✅ Доступен |
| subprocess (Python) | — | — | ✅ Доступен |
| Playwright Python | — | — | ✅ Доступен |
| Playwright Node.js | — | — | ❌ Недоступен (ошибка загрузки модуля) |

### Активные MCP-серверы (7 шт.)

| Сервер | Команда | Статус | Прокси |
|--------|---------|--------|--------|
| browser-use | `python3 mcp_security_proxy.py ... -- /home/vscode/.local/bin/browser-use --mcp` | connected | ✅ Через прокси |
| gflow | `gflow mcp run --profile flow_remote --no-spend` | connected | ❌ Прямой (уже защищён --no-spend) |
| github | `/home/vscode/.local/bin/github-mcp-server stdio` | connected | ❌ Прямой |
| context7 | `npx -y @upstash/context7-mcp` | connected | ❌ Прямой |
| playwright | `python3 mcp_security_proxy.py ... -- npx -y @playwright/mcp@0.0.38` | connected | ✅ Через прокси |
| git | `mcp-server-git --repository /workspaces/OpenMontage` | connected | ❌ Прямой |
| filesystem | `npx -y @modelcontextprotocol/server-filesystem ...` | connected | ❌ Прямой |

### Переменные окружения Kilo

| Переменная | Значение |
|------------|----------|
| `GFLOW_CLI_HOME` | `/home/vscode/.local/share/gflow-cli` |
| `GFLOW_CLI_PROFILE` | `flow_remote` |
| `GFLOW_MCP_NO_SPEND` | `1` |

---

## 2. Проверенные пути обхода

Все пути обхода проверены безопасно (только чтение списка инструментов, никаких действий).

### Путь обхода 1: Прямой запуск browser-use (минуя прокси)

**Статус: ✅ ВОЗМОЖЕН**

```bash
/home/vscode/.local/bin/browser-use --mcp
```

**Результат:** Доступны все 16 инструментов, включая запрещённые:
- `browser_click` — клики по элементам (может.trigger генерацию)
- `browser_type` — ввод текста (может.submit форм)
- `browser_scroll` — прокрутка (изменение состояния)
- `browser_close_tab`, `browser_close_session`, `browser_close_all` — закрытие
- `retry_with_browser_use_agent` — агентские действия
- `browser_list_sessions` — управление сессиями

**Причина:** Binary доступен по абсолютному пути, bash permission `"*"`: `"ask"` — это гейт одобрения, не техническая блокировка.

### Путь обхода 2: Прямой запуск Playwright MCP (минуя прокси)

**Статус: ✅ ВОЗМОЖЕН**

```bash
npx -y @playwright/mcp@0.0.38
```

**Результат:** Доступны все 18 инструментов, включая запрещённые:
- `browser_click`, `browser_type`, `browser_fill_form`, `browser_press_key`
- `browser_evaluate` — выполнение произвольного JavaScript
- `browser_file_upload` — загрузка файлов
- `browser_drag`, `browser_hover`, `browser_select_option`
- `browser_close`, `browser_resize`, `browser_handle_dialog`, `browser_install`

**Причина:** npx доступен, bash permission `"*"`: `"ask"`.

### Путь обхода 3: Прямой доступ к CDP 9223

**Статус: ✅ ВОЗМОЖЕН**

```bash
curl http://127.0.0.1:9223/json/version
```

**Результат:** Chrome CDP напрямую доступен, полностью обходит Browser Use прокси. Можно выполнять любые CDP операции (навигация, клики, ввод, скриншоты) без какого-либо посредника.

**Причина:** Chrome запущен с `--remote-debugging-port=9223` и привязан к localhost. CDP не требует аутентификации.

### Путь обхода 4: Python Playwright напрямую

**Статус: ✅ ВОЗМОЖЕН**

```python
from playwright.sync_api import sync_playwright
```

**Результат:** Python Playwright модуль доступен, можно управлять Chrome напрямую.

### Путь обхода 5: Node.js Playwright

**Статус: ❌ НЕДОСТУПЕН**

Модуль `playwright` для Node.js не загружается (ошибка CJS loader).

### Путь обхода 6: Прямой запуск gflow MCP (минуя прокси)

**Статус: ✅ ВОЗМОЖЕН, но защищён**

```bash
gflow mcp run --profile flow_remote --no-spend
```

**Результат:** gflow MCP доступен напрямую, но `--no-spend` скрывает генерационные инструменты (0 инструментов `generate_*` в tools/list). Защита на уровне флага, а не прокси.

### Путь обхода 7: Произвольный MCP-сервер

**Статус: ✅ ВОЗМОЖЕН**

Любой пользователь с одобрением bash может запустить любой MCP-сервер через `npx`, `python3`, или любой другой бинарник.

---

## 3. Устранённые обходы

| Обход | Статус | Действие |
|-------|--------|----------|
| Прямой browser-use через Kilo MCP config | ✅ Закрыт | Заменён на прокси в kilo.jsonc |
| Прямой Playwright через Kilo MCP config | ✅ Закрыт | Заменён на прокси в kilo.jsonc |
| gflow генерационные инструменты | ✅ Закрыт | `--no-spend` скрывает `generate_*` инструменты |
| Browser Use click/type/scroll через прокси | ✅ Закрыт | Не в allowlist прокси |
| Playwright click/type/evaluate через прокси | ✅ Закрыт | Не в allowlist прокси |
| Доступ к профилю flow_remote | ✅ Сохранён | Не изменён |
| Доступ к профилю flow-mobile | ✅ Сохранён | Не изменён |
| GFLOW_MCP_NO_SPEND=1 | ✅ Сохранён | В env и в команде gflow |

---

## 4. Оставшиеся возможные обходы (не устранены)

| Обход | Почему невозможно устранить технически | Риск |
|-------|----------------------------------------|------|
| Прямой запуск `/home/vscode/.local/bin/browser-use --mcp` | Binary на диске, bash `"*"`: `"ask"` требует одобрения пользователя, но не блокирует технически | Высокий — полный доступ ко всем 16 инструментам Browser Use |
| Прямой запуск `npx @playwright/mcp@0.0.38` | npx доступен, bash `"*"`: `"ask"` | Высокий — полный доступ ко всем 18 инструментам Playwright |
| Прямой доступ к CDP 9223 (`curl http://127.0.0.1:9223/...`) | Chrome привязан к localhost, CDP не требует аутентификации | Критический — обходит Browser Use полностью, доступ к браузеру без посредника |
| Python Playwright напрямую | Модуль установлен, доступен для импорта | Высокий — управление браузером без прокси |
| Запуск произвольного MCP-сервера | bash `"*"`: `"ask"` требует одобрения | Средний — зависит от сервера |
| Прямой запуск gflow без --no-spend | gflow бинарник на диске | Средний — генерационные инструменты станут доступны |

### Точная причина невозможности полной изоляции

**Kilo CLI работает в пользовательском пространстве Codespace без прав root.** Bash permission `"*"`: `"ask"` — это механизм одобрения на уровне агента, а не ограничение на уровне ОС. Пользователь с одобрением может:

1. Запустить любой бинарник напрямую
2. Подключиться к любому TCP порту (включая CDP 9223)
3. Импортировать любой Python модуль
4. Запустить любой Node.js скрипт

Для полной изоляции требуются меры на уровне ОС (seccomp, AppArmor, network namespaces,隔离 CDP порта), которые выходят за пределы Codespace без прав root.

---

## 5. Архитектурное решение (рекомендация)

Для полной изоляции требуются меры вне Codespace:

| Уровень | Решение | Что блокирует |
|---------|---------|---------------|
| ОС (сетевой) | Network namespace, изоляция порта 9223 | Прямой доступ к CDP |
| ОС (процессы) | seccomp профиль, ограничение execve | Прямой запуск browser-use/Playwright |
| ОС (файловая) | AppArmor, ограничение доступа к бинарникам | Запуск неавторизованных MCP-серверов |
| Инфраструктура | Колорация Chrome в отдельном контейнере, CDP через Unix socket | Прямой TCP доступ к CDP |

Внутри Codespacemaximum достижимая защита:
1. ✅ Прокси для всех MCP через kilo.jsonc (сделано)
2. ✅ `--no-spend` для gflow (сделано)
3. ✅ Allowlist на границе прокси (сделано)
4. ⚠️ Bash `"*"`: `"ask"` — требует пользовательского одобрения
5. ⚠️ Прямой доступ к CDP — не блокируется без прав root

---

## 6. Проверка сохранности рабочей системы

| Компонент | Проверка | Результат |
|-----------|----------|-----------|
| Профиль `flow_remote` | `gflow auth status --profile flow_remote` | ✅ Верифицировано, vvv86357482@gmail.com |
| Профиль `flow-mobile` | Не изменён | ✅ Цел |
| Google-авторизация | Не менялась | ✅ Сохранена |
| `GFLOW_MCP_NO_SPEND=1` | В env и в команде | ✅ Сохранён |
| `--no-spend` | В команде gflow mcp run | ✅ Сохранён |
| Generate tools в gflow | 0 инструментов в tools/list | ✅ Скрыты |
| Flow Job Manager | `from lib.flow_job_manager import FlowJobManager` | ✅ Работает |
| MCP Security Proxy | 13 тестов пройдены | ✅ Работает |
| Browser Use через прокси | 7 инструментов в allowlist | ✅ Работает |
| Playwright через прокси | 8 инструментов в allowlist | ✅ Работает |

---

## 7. Результаты тестов

### MCP Security Proxy тесты (`tests/test_mcp_security_proxy.py`)

| # | Тест | Статус |
|---|------|--------|
| 1 | MCP initialize через прокси | PASS |
| 2 | tools/list показывает только разрешённые | PASS |
| 3 | Заблокированный tools/call отклоняется | PASS |
| 4 | Разрешённый tools/call работает | PASS |
| 5 | Неизвестный инструмент блокируется | PASS |
| 6 | Ошибка дочернего процесса обрабатывается | PASS |
| 7 | Перезапуск MCP не повреждает соединения | PASS |
| 8 | gflow no-spend продолжает работать | PASS |
| 9 | Playwright не обходит защиту (через прокси) | PASS |
| 10 | Browser Use не обходит защиту (через прокси) | PASS |
| 11 | Audit log не содержит секретов | PASS |
| 12 | Пустой allowlist вызывает ошибку прокси | PASS |
| 13 | Реальная интеграция Browser Use (Chrome + CDP 9223) | PASS |

**Итого: 13/13 PASS**

### Flow Job Manager тесты

| Suite | Результат |
|-------|-----------|
| `tests/test_flow_job_manager.py` | 23 passed, 2 skipped |
| `tests/test_flow_job_manager_mock.py` | 8 passed |
| `tests/test_flow_load.py` | 6 passed |

### Бypass тесты (읽ение только)

| Путь обхода | Доступен | Защита через прокси |
|-------------|----------|---------------------|
| Прямой browser-use | ✅ Да | ❌ Не защищено (только через Kilo config) |
| Прямой Playwright | ✅ Да | ❌ Не защищено (только через Kilo config) |
| Прямой CDP 9223 | ✅ Да | ❌ Не защищено |
| Python Playwright | ✅ Да | ❌ Не защищено |
| gflow без --no-spend | ✅ Да | ⚠️ --no-spend в команде, но бинарник доступен |

---

## 7. Фактический уровень защиты

| Компонент | Уровень защиты | Комментарий |
|-----------|---------------|-------------|
| Gflow (MCP через kilo.jsonc) | 🟢 Высокий | --no-spend, профиль flow_remote, generate tools скрыты |
| Browser Use (через прокси в Kilo) | 🟡 Средний | Прокси фильтрует инструменты, но прямой запуск возможен через bash |
| Playwright (через прокси в Kilo) | 🟡 Средний | Прокси фильтрует инструменты, но прямой запуск возможен через bash |
| CDP 9223 | 🔴 Низкий | Прямой TCP доступ, не требует аутентификации |
| Общий уровень | 🟡 Средний | Защита на уровне конфигурации Kilo, но не на уровне ОС |

**Важно:** Не заявляйте о полной защите. Обход возможен через:
1. Прямой запуск бинарников (bash `"*"`: `"ask"`)
2. Прямой доступ к CDP 9223
3. Python Playwright напрямую

---

## 8. Команды восстановления

### Проверить состояние прокси

```bash
kilo mcp list
```

### Перезапустить Chrome (если CDP 9223 недоступен)

```bash
DISPLAY=:99 google-chrome --remote-debugging-port=9223 \
  --user-data-dir=/home/vscode/.local/share/gflow-cli/profile_flow-mobile \
  --no-sandbox --disable-gpu --disable-dev-shm-usage \
  --window-size=1920,1080 --no-first-run &
```

### Проверить gflow через прокси

```bash
GFLOW_CLI_PROFILE=flow_remote GFLOW_MCP_NO_SPEND=1 \
gflow auth status --profile flow_remote
```

### Проверить Browser Use через прокси

```bash
timeout 10 env DISPLAY=:99 BROWSER_USE_HEADLESS=false \
BROWSER_USE_CONFIG_DIR=/home/vscode/.config/browseruse \
BU_CDP_URL=http://127.0.0.1:9223 \
python3 /workspaces/OpenMontage/lib/mcp_security_proxy.py \
browser-use browser_navigate,browser_get_state,browser_extract_content, \
browser_screenshot,browser_list_tabs,browser_switch_tab,browser_go_back \
-- /home/vscode/.local/bin/browser-use --mcp
```

### Запустить все тесты безопасности

```bash
/usr/local/py-utils/bin/pytest tests/test_mcp_security_proxy.py -v
/usr/local/py-utils/bin/pytest tests/test_flow_job_manager.py -v
/usr/local/py-utils/bin/pytest tests/test_flow_job_manager_mock.py -v
```

### Отключить прокси (резервный вариант, требует осторожности)

Отредактируйте `/home/vscode/.config/kilo/kilo.jsonc`, заменив команды прокси на прямые:
- Browser Use: `["/home/vscode/.local/bin/browser-use", "--mcp"]`
- Playwright: `["npx", "-y", "@playwright/mcp@0.0.38"]`

---

## 9. Файлы аудита

| Файл | Описание |
|------|----------|
| `/workspaces/OpenMontage/lib/mcp_security_proxy.py` | MCP Security Proxy |
| `/workspaces/OpenMontage/config/mcp-allowlist-browser-use.env` | Allowlist Browser Use |
| `/workspaces/OpenMontage/config/mcp-allowlist-playwright.env` | Allowlist Playwright |
| `/workspaces/OpenMontage/tests/test_mcp_security_proxy.py` | Тесты прокси (13 тестов) |
| `/workspaces/OpenMontage/FLOW_MCP_SECURITY_REPORT.md` | Отчёт о прокси |
| `/workspaces/OpenMontage/FLOW_FINAL_SECURITY_AUDIT.md` | Этот отчёт |
| `/home/vscode/.config/kilo/kilo.jsonc` | Конфигурация Kilo с прокси |
| `/workspaces/OpenMontage/pytest.ini` | Конфигурация pytest с marker integration |

---

## 10. Вывод

**MCP Security Proxy реализован и работает корректно на уровне конфигурации Kilo.** Browser Use и Playwright routed через прокси с strict allowlist. gflow защищён `--no-spend`.

**Однако, полная защита от обхода невозможна в текущем Codespace без прав root.** Пользователь с одобрением bash может:
1. Запустить browser-use/Playwright напрямую
2. Подключиться к CDP 9223 напрямую
3. Использовать Python Playwright напрямую

**Рекомендация:** Рассматривайте текущую защиту как уровень конфигурации приложения, а не как границу безопасности на уровне ОС. Для полной изоляции требуются меры на уровне ОС (сетевые неймспейсы, seccomp, контейнеризация Chrome).
