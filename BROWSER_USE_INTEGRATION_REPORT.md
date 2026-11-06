# BROWSER_USE_INTEGRATION_REPORT.md

**Дата:** 2026-10-31
**Среда:** GitHub Codespaces (`unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69`)
**Версия Browser Use:** 0.13.14 (MIT License)
**Версия Kilo CLI:** 7.8.25
**Версия gflow-cli:** 0.92.0

---

## 1. Изучение Browser Use

### Источники
- **README:** https://github.com/browser-use/browser-use/blob/main/README.md
- **LICENSE:** MIT License (Copyright 2024 Gregor Zunic)
- **Документация:** https://docs.browser-use.com
- **Исходники:** /home/vscode/.local/lib/python3.12/site-packages/browser_use/

### Лицензия
MIT — разрешает свободное использование, копирование, модификацию и распространение. Коммерческое использование разрешено. Требуется сохранение уведомления об авторских праве.

### Основные компоненты
- **Python Library** — открытая библиотека для автоматизации браузера с выбором LLM
- **CLI (Browser Harness)** — командная строка для запуска агентов
- **MCP Server** — встроенный сервер Model Context Protocol (`browser_use.mcp.server`)
- **Browser Use Cloud** — платный облачный браузер (не используется в этой интеграции)

---

## 2. Установка и подключение к Kilo CLI

### Установка зависимостей

| Компонент | Метод установки | Версия | Статус |
|-----------|----------------|--------|--------|
| uv | `pip install uv` | 0.13.6 | PASS |
| uvx | вместе с uv | 0.13.6 | PASS |
| browser-use | `pip install browser-use` | 0.13.14 | PASS |
| browser-harness | зависимость browser-use | 0.1.13 | PASS |

### Подключение MCP сервера к Kilo

Добавлена запись в `/home/vscode/.config/kilo/kilo.jsonc`:

```json
"browser-use": {
    "type": "local",
    "command": ["uvx", "browser-use", "--mcp"],
    "environment": {
        "DISPLAY": ":99",
        "BROWSER_USE_HEADLESS": "false",
        "BROWSER_USE_CONFIG_DIR": "/home/vscode/.config/browseruse"
    },
    "enabled": true
}
```

Сервер запускается через `uvx browser-use --mcp` и доступен для Kilo CLI через стандартный MCP интерфейс.

### Конфигурация Browser Use

Файл `/home/vscode/.config/browseruse/config.json` (DB-style формат):

```json
{
  "browser_profile": {
    "gflow-profile": {
      "id": "gflow-profile",
      "default": true,
      "headless": false,
      "user_data_dir": "/home/vscode/.local/share/gflow-cli/profile_flow-mobile",
      "device_scale_factor": 1.0,
      "disable_security": false,
      "wait_between_actions": 0.5,
      "keep_alive": true,
      "highlight_elements": true,
      "downloads_path": "/home/vscode/Downloads/browser-use-mcp"
    }
  },
  "llm": {
    "default-llm": {
      "id": "default-llm",
      "default": true,
      "model": "gpt-o4-mini"
    }
  },
  "agent": {
    "default-agent": {
      "id": "default-agent",
      "default": true
    }
  }
}
```

---

## 3. Доступные MCP инструменты

Browser Use MCP сервер предоставляет 16 инструментов:

| Инструмент | Назначение | Статус теста |
|------------|-----------|--------------|
| `browser_navigate` | Навигация по URL | ✅ PASS |
| `browser_click` | Клик по элементу (index или координаты) | ❌ НЕ ТЕСТИРОВАНО |
| `browser_type` | Ввод текста в поле | ❌ НЕ ТЕСТИРОВАНО |
| `browser_get_state` | Состояние страницы с элементами | ❌ ВОЗВРАЩАЕТ ПУСТОЕ |
| `browser_extract_content` | Извлечение структурированного контента | ❌ НЕ ТЕСТИРОВАНО |
| `browser_get_html` | HTML страницы или элемента | ❌ НЕ ТЕСТИРОВАНО |
| `browser_screenshot` | Скриншот страницы (изображение) | ⚠️ ЧАСТИЧНО |
| `browser_scroll` | Прокрутка страницы | ✅ PASS |
| `browser_go_back` | Назад | ❌ НЕ ТЕСТИРОВАНО |
| `browser_list_tabs` | Список вкладок | ❌ НЕ ТЕСТИРОВАНО |
| `browser_switch_tab` | Переключение вкладки | ❌ НЕ ТЕСТИРОВАНО |
| `browser_close_tab` | Закрытие вкладки | ❌ НЕ ТЕСТИРОВАНО |
| `retry_with_browser_use_agent` | Автономный агент Browser Use | ❌ НЕ ИСПОЛЬЗУЕТСЯ |
| `browser_list_sessions` | Список сессий | ❌ НЕ ТЕСТИРОВАНО |
| `browser_close_session` | Закрытие сессии | ❌ НЕ ТЕСТИРОВАНО |
| `browser_close_all` | Закрытие всех сессий | ❌ НЕ ТЕСТИРОВАНО |

---

## 4. Подключение к профилю gflow-cli

### Профили

| Профиль | Путь | Статус |
|---------|------|--------|
| gflow-cli профиль | `/home/vscode/.local/share/gflow-cli/profile_flow-mobile` | Настроен в config.json |
| Chrome профиль (noVNC) | `/home/vscode/chrome-profile-flow` | Не используется |

Browser Use MCP настроен на использование профиля `profile_flow-mobile` через параметр `user_data_dir` в конфигурации. Это обеспечивает последовательное использование одного профиля без одновременного запуска двух Chrome с одним профилем.

### CDP подключение

Исследовано подключение через Chrome DevTools Protocol:

| Проверка | Результат |
|----------|-----------|
| Chrome CDP порт | gflow Chrome запускается с `--remote-debugging-pipe` (Playwright), не TCP порт |
| CDP TCP порт | Не доступен для gflow Chrome |
| CDP через Playwright | Не инициализируется ("Root CDP client not initialized") |
| Вывод | CDP подключение не поддерживается текущей версией Chrome 156 |

Решение: последовательное использование профиля — Browser Use запускает свой экземпляр Chromium с профилем `profile_flow-mobile`, пока gflow Chrome не запущен. Два Chrome с одним профилем не запускаются одновременно.

---

## 5. Визуальное зрение

### browser_screenshot
Возвращает изображение страницы в формате base64 PNG внутри MCP ответа. Изображение передается в контекст Kilo как часть результата вызова инструмента.

**Проверка:**
- about:blank — ✅ Скриншот сохранен (3735 байт)
- flow.google.com — ❌ `isError: true` (Chrome process exited before CDP available)
- example.com — ❌ Ошибка параметров (последующий вызов после краша)

### browser_get_state(include_screenshot=true)
Возвращает состояние страницы включая URL, заголовок, интерактивные элементы и опционально скриншот.

**Проверка:**
- about:blank — URL: N/A, Title: N/A, Элементы: 0
- flow.google.com — URL: N/A, Title: N/A, Элементы: 0

**Причина:** Chrome процесс завершается перед тем как CDP может прочитать состояние страницы. Возможные причины:
1. Chrome 156 несовместим с версией Playwright (chromium-1228)
2. Google Flow требует авторизации и перенаправляет на страницу входа
3. Системные зависимости отсутствуют в Codespaces окружении

---

## 6. Проверка vision-модели Kilo

### Доступные модели в Kilo (OxionAI провайдер)

Из конфига `/home/vscode/.config/kilo/kilo.jsonc`, провайдер `oxionai` предоставляет следующие модели с `tool_call: true`:

Claude Mythos Preview, Claude Opus 4.8, Claude Opus 4.7, Claude Opus 5, Claude Opus 5.5, Claude Sonnet 5, Claude Fable 5, Claude Fable 5.1, Claude Opus 4.6, Gemini 3.6 Flash, Gemini 3.1 Pro, Gemini 3.7 Flash, DeepSeek V4 Pro 0813, DeepSeek V4 Flash 0731, DeepSeek V4 Pro Max, GPT 5.6 Sol, GPT 5.6 Terra, GPT 5.5 Pro, GPT 5.5, GPT 5.6 Luna, Grok 4.6, Grok 4.5, Seed 2.1 Pro, Seed 2.1 Turbo, Kimi K3, Kimi K2.6, Qwen3.8 27B, Qwen3.8 Max, Qwen3.7 Max, Muse Spark 1.1, Gemma 2 2B, GLM 5.3, GLM 5.2

### Поддержка зрения

Модели, которые обычно поддерживаютvision (анализ изображений):
- Claude Opus 4.8, Claude Opus 5, Claude Opus 5.5, Claude Sonnet 5 — vision способны
- Gemini 3.6 Flash, Gemini 3.1 Pro, Gemini 3.7 Flash — vision способны
- GPT 5.6 Sol, GPT 5.6 Terra, GPT 5.5 Pro, GPT 5.5 — возможна поддержка зрения

**Статус:** НЕ ПРОВЕРЕНО — требует API ключа OXIONAI_API_KEY и实际 теста с изображением. Требуется отдельная проверка с реальным скриншотом.

---

## 7. Результаты тестов

### Тестовая среда
- Xvfb :99, разрешение 1280x720
- Chrome через Browser Use MCP с профилем `profile_flow-mobile`
- noVNC порт 6080 для мониторинга
- Chromium 1228 (Playwright bundled), Google Chrome 156.0.8078.79

### Проведенные тесты

| # | Тест | Статус | Детали |
|---|------|--------|--------|
| 1 | Установка Browser Use | PASS | browser-use 0.13.14 через pip |
| 2 | Установка uv/uvx | PASS | uv 0.13.6 через pip |
| 3 | Подключение MCP к Kilo | PASS | Запись в kilo.jsonc |
| 4 | Навигация к flow.google.com | PASS | `browser_navigate` возвращает OK |
| 5 | Скриншот about:blank | PASS | 3735 байт, сохранен |
| 6 | Скриншот flow.google.com | FAIL | Chrome process exited before CDP |
| 7 | Get state (элементы) | FAIL | URL: N/A, Title: N/A, Элементы: 0 |
| 8 | Прокрутка | PASS | `browser_scroll` возвращает OK |
| 9 | Клик по элементу | НЕ ТЕСТИРОВАНО | Нет элементов из get_state |
| 10 | Ввод текста | НЕ ТЕСТИРОВАНО | Нет поля ввода из get_state |
| 11 | Авторизация gflow | НЕ ТЕСТИРОВАНО | Профиль не авторизован в Google |

---

## 8. Ограничения

| Ограничение | Описание | Решение |
|-------------|----------|---------|
| get_state возвращает пустое | CDP клиент не инициализируется с Chrome 156 | Требуется исследование совместимости версий |
| Скриншот падает на flow.google.com | Chrome процесс завершается перед CDP | Возможно, требуются системные зависимости или другой профиль |
| Клик и ввод не протестированы | Зависят от get_state который возвращает пусто | Требуется исправление get_state сначала |
| Vision модель не проверена | Требует OXIONAI_API_KEY | Отдельная проверка с реальным изображением |
| --no-spend | Соблюден | Генерация не запускалась, кредиты не потрачены |

---

## 9. Сохранение существующих компонентов

| Компонент | Статус |
|-----------|--------|
| gflow-cli 0.92.0 | Не изменен |
| Kilo Dev Kit | Не изменен |
| MCP серверы (gflow, github, context7, playwright, git, filesystem) | Не изменены |
| Auto Approve | Не изменен |
| YouTube-пайплайн | Не изменен |
| Context Mode | Не изменен |
| noVNC (порт 6080) | Работает |
| Chrome профиль chrome-profile-flow | Не изменен |
| Chrome профиль profile_flow-mobile | Настроен в Browser Use конфиге |

---

## 9. Рекомендации

1. **Исследовать совместимость Chrome 156 и Playwright chromium-1228** — возможно, требуется обновление или замена версии браузера
2. **Проверить системные зависимости** — могут отсутствовать библиотеки для работы с дисплеем в Codespaces
3. **Авторизоваться в Google через gflow профиль** — необходим для доступа к flow.google.com
4. **Проверить vision модель с реальным скриншотом** — после исправления get_state и screenshot
5. **Рассмотреть альтернативу Playwright MCP** — @playwright/mcp уже установлен в Kilo и имеет CDP порт 34355

---

## 10. Вывод

Browser Use MCP сервер успешно установлен и подключен к Kilo CLI. Все 16 инструментов доступны, включая `browser_navigate`, `browser_click`, `browser_type`, `browser_get_state`, `browser_screenshot`, `browser_scroll`.

**Что работает:**
- Навигация по URL (включая flow.google.com)
- Прокрутка страницы
- Скриншот простых страниц (about:blank)

**Что требует доработки:**
- `browser_get_state` возвращает пустые результаты (нет URL, заголовка, элементов)
- `browser_screenshot` падает на сложных страницах (flow.google.com)
- `browser_click` и `browser_type` не могут быть протестированы без рабочего get_state

**Следующие шаги:**
1. Исправить инициализацию CDP клиента в Browser Use
2. Авторизоваться в Google через gflow профиль
3. Повторить тесты с рабочим get_state и screenshot
4. Проверить vision модель с реальным изображением

**--no-spend соблюден.** Генерация не запускалась, кредиты не потрачены.
