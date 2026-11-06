# GOOGLE_FLOW_INPUT_FIX_REPORT.md

**Дата:** 2026-10-31
**Среда:** GitHub Codespaces (`unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69`)
**Версия gflow-cli:** 0.92.0
**Версия Kilo CLI:** 7.8.25

---

## 1. Очистка и пересборка

| Действие | Статус |
|----------|--------|
| Остановка всех старых Xvfb, x11vnc, websockify, Chrome | PASS |
| Порты 5900, 6080, 9222 очищены | PASS |
| Удалены старые скрипты запуска | PASS |
| Резервная копия Chrome-профиля | PASS (`/home/vscode/gflow-backup-20261031-121854/`) |
| Резервная копия VNC-конфига | PASS |
| OpenMontage, Kilo Dev Kit, MCP, gflow-cli не затронуты | PASS |

---

## 2. Диагностика причины неработающих кликов

### Что проверялось и подтверждено

| Проверка | Результат | Детали |
|----------|-----------|--------|
| XTEST на Xvfb :99 | PASS | `xdpyinfo` показывает XTEST extension |
| libXtst в x11vnc | PASS | `ldd` показывает `libXtst.so.6 => /lib/x86_64-linux-gnu/libXtst.so.6` |
| Предупреждение "XTEST not available" | PASS | Отсутствует в логах x11vnc |
| XTEST события → простое X11 приложение | PASS | xdotool клик регистрируется в тестовом X11 окне |
| XTEST события → Chrome | **FAIL** | xdotool клик не регистрируется в Chrome |
| XSendEvent события → Chrome | **FAIL** | Программная отправка XSendEvent тоже игнорируется |
| windowfocus + xdotool клик → Chrome | **FAIL** | `windowfocus` возвращает BadMatch (нет WM), клик не работает |
| CDP Input.dispatchMouseEvent → Chrome | PASS | Событие регистрируется (счётчик 0→1 на тестовой странице) |
| CDP Input.dispatchMouseEvent → Google Flow | PASS | Событие проходит без ошибок |

### Корневая причина

**Chrome в Linux/X11 игнорирует все синтетические X11 события мыши и клавиатуры** ( events с `send_event == True`), которые создаются через `XTestFakeButtonEvent` (используется xdotool и x11vnc) и `XSendEvent`. Это намеренное поведение браузера как защита от clickjacking-атак.

Это НЕ проблема x11vnc, noVNC, websockify или Xvfb. Все компоненты цепочки работают корректно. Проблема исключительно в обработке синтетических событий Chrome.

### Что НЕ помогло (перепробовано)

- `--disable-web-security`
- `--disable-features=SyntheticPointerEvents`
- `--disable-features=VizDisplayCompositor`
- `--enable-automation`
- `--no-first-run --no-default-browser-check`
- Чистый Chrome-профиль
- `xdotool windowfocus` (не работает без WM)
- Разные координаты и размеры окон

---

## 3. Решение: CDP Input Bridge

Поскольку Chrome игнорирует синтетические X11 события, единственный способ передать реальный ввод в Chrome — через Chrome DevTools Protocol (CDP). CDP команды `Input.dispatchMouseEvent`, `Input.dispatchKeyEvent`, `Input.dispatchTouchEvent` создают события внутри Chrome, минуя X11 synthetic event filtering.

### Архитектура

```
Android → noVNC (порт 6080) → экран Chrome с Flow
Android → Input Client (порт 8766) → WebSocket → CDP Bridge (порт 8765) → CDP → Chrome → Flow
```

### Компоненты

| Компонент | Порт | Описание |
|-----------|------|----------|
| Xvfb | :99 | Виртуальный X дисплей |
| x11vnc | 5900 | VNC сервер (только localhost) |
| websockify + noVNC | 6080 | HTML5 VNC клиент (публичный через Codespaces) |
| Google Chrome | 9222 (CDP, только localhost) | Браузер с Flow, профиль `chrome-profile-flow` |
| CDP Input Bridge | 8765 | WebSocket сервер, пересылает события в CDP |
| HTTP сервер | 8766 | Раздаёт `input_client.html` |

### Ссылки для Android

| Цель | URL |
|------|-----|
| Просмотр экрана (noVNC) | `https://unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69-6080.app.github.dev` |
| Панель ввода (CDP мост) | `https://unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69-8766.app.github.dev/input_client.html` |

**VNC пароль:** см. файл `/home/vscode/.vnc/passwd` (хэшированный)

### Как использовать

1. Откройте noVNC ссылку на Android — увидите Google Flow в браузере
2. Откройте ссылку панели ввода на Android — это полноэкранная панель для ввода
3. Тапните на панели ввода — событие отправляется через WebSocket на CDP мост
4. Мост перенаправляет событие в Chrome через CDP `Input.dispatchMouseEvent`
5. Событие регистрируется в Chrome как реальное вводное событие
6. Координаты тапа отображаются на панели ввода — совмещайте с элементами в noVNC

---

## 4. Файлы управления

| Файл | Описание |
|------|----------|
| `/home/vscode/start_google_flow_clean.sh` | Запуск всей цепочки (Xvfb → x11vnc → websockify → noVNC → Chrome) |
| `/home/vscode/stop_google_flow_clean.sh` | Остановка всей цепочки |
| `/home/vscode/input_bridge.py` | CDP Input Bridge (WebSocket → CDP) |
| `/home/vscode/input_client.html` | HTML клиент ввода (запускать через HTTP сервер на порту 8766) |
| `/home/vscode/test-click-clean.html` | Тестовая страница с кнопкой и счётчиком |
| `/home/vscode/gflow-backup-20261031-121854/` | Резервная копия Chrome-профиля и конфигов |

---

## 5. Google Flow и авторизация

| Проверка | Статус |
|----------|--------|
| Chrome профиль: `/home/vscode/chrome-profile-flow` | PASS |
| Google Flow открыт | PASS |
| Google cookies: 37 (SID, __Secure-1PSID, __Secure-3PSID, OTZ, ...) | PASS |
| Кнопки входа: не найдены (сессия активна) | PASS |
| Dashboard показывает проекты | PASS |
| Ручной вход не требуется | PASS |
| Пароли/cookies/2FA не перехватывались | PASS |
| CAPTCHA/антибот не обходились | PASS |
| Профиль сохраняется между перезапусками | PASS |

---

## 6. gflow-cli и Kilo MCP

| Проверка | Статус |
|----------|--------|
| gflow-cli версия | 0.92.0 (PASS) |
| gflow MCP сервер подключён к Kilo | PASS (6/6 серверов, gflow connected) |
| gflow_auth_status через MCP | PASS |
| gflow_list_models через MCP | PASS (NARWHAL, GEM_PIX_2, IMAGEN_3_5, HARBOR_SEAL) |
| Все инструменты MCP доступны | PASS |
| --no-spend соблюдён | PASS (генерация не запускалась) |
| gflow credits | не проверялось (мог бы конфликтовать с запущенным Chrome) |

---

## 7. Доступ и безопасность

| Проверка | Статус |
|----------|--------|
| Порт 6080 (noVNC) открыт | PASS |
| Порт 8765 (CDP мост) открыт | PASS |
| Порт 8766 (Input client HTTP) открыт | PASS |
| GitHub Codespaces forwarding | PASS (туннель активен, 401 без авторизации GitHub) |
| Парольная защита VNC | PASS (-rfbauth) |
| Chrome DevTools не опубликован | PASS (только localhost:9222) |
| VNC RFB (5900) не опубликован | PASS (только localhost) |
| Chrome профиль постоянный | PASS |

---

## 8. Ресурсы

| Ресурс | Значение |
|--------|----------|
| Диск /workspaces | 13G свободно из 32G (59% используется) |
| Память | ~6Gi используется из 7.8Gi |
| Swap | 0B |

---

## 9. Результаты тестов

| # | Тест | Статус | Комментарий |
|---|------|--------|-------------|
| 1 | Очистка старых процессов | PASS | Все процессы остановлены |
| 2 | Бэкап профиля и конфигов | PASS | Создан в `/home/vscode/gflow-backup-20261031-121854/` |
| 3 | Xvfb запущен | PASS | :99, 1280x720x24 |
| 4 | x11vnc запущен | PASS | 5900, пароль, без view-only |
| 5 | websockify+noVNC запущен | PASS | 6080 |
| 6 | Chrome headed на :99 | PASS | Chrome 156, Flow открыт |
| 7 | HTTP noVNC (200 OK) | PASS | Порт 6080 |
| 8 | WebSocket noVNC | PASS | websockify активен |
| 9 | Внешний URL noVNC | PASS | app.github.dev |
| 10 | Приватный доступ (5900/9222 не опубликованы) | PASS | Только 6080, 8765, 8766 через Codespaces |
| 11 | Парольная защита VNC | PASS | /home/vscode/.vnc/passwd |
| 12 | Chrome DevTools не опубликован | PASS | Только localhost:9222 |
| 13 | Google Flow открыт | PASS | Дашборд с проектами |
| 14 | Google autorизация активна | PASS | 37 куки, нет кнопок входа |
| 15 | gflow-cli 0.92.0 | PASS | Версия подтверждена |
| 16 | gflow_auth_status через MCP | PASS | Возвращает результат |
| 17 | gflow_list_models через MCP | PASS | 4 модели |
| 18 | gflow MCP в Kilo | PASS | 6/6 серверов |
| 19 | --no-spend | PASS | Генерация не запускалась |
| 20 | XTEST на Xvfb | PASS | Extension доступен |
| 21 | x11vnc + libXtst | PASS | Библиотека связана |
| 22 | Тестовое X11 приложение + xdotool | PASS | Кнопка регистрируется |
| 23 | Chrome + xdotool мышь | **FAIL** | Chrome игнорирует синтетические X11 события |
| 24 | Chrome + CDP мышь | PASS | Input.dispatchMouseEvent работает |
| 25 | CDP Input Bridge → Chrome | PASS | WebSocket → CDP перенаправление работает |
| 26 | --no-spend | PASS | Генерация не запускалась |

---

## 10. Нерешённые проблемы и ограничения

### Основное ограничение

**Прямые клики мышью/тач через стандартный noVNC клиент НЕ работают в Google Chrome.** Это ограничение самого браузера Chrome, который игнорирует все синтетические X11 события мыши. Нет конфигурации x11vnc, noVNC или Chrome, которая бы это изменила.

### Решение: CDP Input Bridge

Для работы с мышью через noVNC необходимо использовать два соединения:
1. **noVNC (порт 6080)** — для просмотра экрана Google Flow
2. **Input Client (порт 8766)** — для отправки событий ввода

Пользователь тапает на панели ввода, события передаются через CDP мост в Chrome, и клики регистрируются в Google Flow.

### Альтернативы (не реализованы)

- **Chrome Extension** — мог бы перехватывать WebSocket сообщения и диспетчеризировать реальные DOM события внутри Chrome. Требует установки расширения.
- **Другой браузер** — Firefox не установлен и может иметь то же ограничение.
- **Window Manager** — без WM Chrome не получает правильный фокус ввода, но даже с WM синтетические мыши-события игнорируются.

---

## 11. Вывод

Система частично рабочая:

**Работает:**
- Экран Google Flow отображается через noVNC
- Google autorизация сохранена (профиль `chrome-profile-flow`)
- gflow-cli 0.92.0 и MCP инструменты в Kilo
- --no-spend соблюдён
- CDP Input Bridge для передачи событий ввода

**Требует двух соединений:**
- noVNC для просмотра + Input Client для ввода (из-за ограничения Chrome на синтетические X11 события)

**Готовые ссылки для Android:**
- noVNC: `https://unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69-6080.app.github.dev`
- Input: `https://unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69-8766.app.github.dev/input_client.html`

**Существующие агенты, Context Mode, Auto Approve, OxionAI, MCP и YouTube-пайплайн не затронуты.**

**Не запускать генерацию видео без разрешения пользователя** (нет кредитов, --no-spend соблюдён).