# GOOGLE_FLOW_AUTH_FINAL_REPORT.md

**Дата:** 2026-10-31
**Среда:** GitHub Codespaces (`unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69`)
**Версия gflow-cli:** 0.92.0
**Версия Kilo CLI:** 7.8.25

---

## 1. Синтаксис gflow auth login

Проверено через `gflow auth login --help`:

```
Usage: gflow auth login [OPTIONS]

  One-time interactive sign-in. Opens a browser window.

Options:
  --profile TEXT                  Profile name. Defaults to the resolved
                                  default (env > config > auto).
  --browser [auto|chrome|internal]
                                  Browser strategy for login. 'chrome'
                                  bypasses Google secure blocks.
  --account TEXT                  Assert that login authenticates as this
                                  exact Google account (email address).
```

**Используемая команда:**
```
DISPLAY=:99 gflow auth login --browser chrome --profile flow-mobile
```

---

## 2. Пути профилей

| Параметр | Значение |
|----------|----------|
| GFLOW_CLI_HOME | не задан (используется значение по умолчанию) |
| gflow CLI home | `/home/vscode/.local/share/gflow-cli/` |
| gflow профиль | `/home/vscode/.local/share/gflow-cli/profile_flow-mobile` |
| gflow config | `/home/vscode/.local/share/gflow-cli/config.toml` (`default_profile = "flow-mobile"`) |
| Chrome профиль (noVNC) | `/home/vscode/chrome-profile-flow` |

**Профили РАЗНЫЕ:** gflow использует свой Playwright-профиль, не Chrome-профиль. Cookies не общие.

---

## 3. Запуск браузера gflow-cli на Xvfb :99

| Проверка | Статус |
|----------|--------|
| gflow auth login процесс | Запущен (PID 231715) |
| Chrome с профилем gflow | Запущен (PID 219402 ранее, перезапущен через gflow) |
| DISPLAY | :99 (единый для всей цепочки) |
| Окно Chrome видно на Xvfb | PASS (заголовок: "Google Flow - AI Creative Studio...") |
| Размер окна | 1920x1080 |
| Окно отображается в noVNC | PASS (порт 6080) |

---

## 4. CDP Input Bridge для gflow Chrome

| Проверка | Статус |
|----------|--------|
| CDP порт gflow Chrome | Не Exposé (используется `--remote-debugging-pipe` через Playwright) |
| CDP TCP порт | Не доступен |
| CDP Input Bridge | НЕ РАБОТАЕТ с браузером gflow-cli |
| Причина | Chrome 156 не экспонирует CDP домены (Runtime, Input, Page) на TCP порту. Все запросы к CDP возвращают `'Method wasn't found`. |

**Решение:** CDP Input Bridge не может направлять клики в браузер gflow-cli. Клики через noVNC (X11 synthetic events) также блокируются Chrome как защита от clickjacking.

---

## 5. Ссылки для Android

| Цель | URL |
|------|-----|
| noVNC — просмотр экрана Google Flow | `https://unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69-6080.app.github.dev` |
| Input Client — панель ввода | `https://unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69-8766.app.github.dev/input_client.html` |
| VNC пароль | см. файл `/home/vscode/.vnc/passwd` |

---

## 6. Процесс авторизации (для пользователя)

1. Откройте noVNC ссылку на Android
2. Введите VNC пароль (из `/home/vscode/.vnc/passwd`)
3. Вы увидите окно Chrome с профилем gflow (`profile_flow-mobile`) и страницу Google Flow
4. Пройдите вход в Google (email, пароль, 2FA если требуется)
5. Продолжайте до загрузки редактора Flow (кнопки и проекты должны появиться)
6. gflow автоматически зафиксирует вход и закроет браузер
7. После этого запустите `gflow auth status` для проверки

**Важно:** gflow требует не просто входа в Google, а полной авторизации в Flow (загрузка редактора с проектами).

---

## 7. Проверка после входа

| Команда | Ожидаемый результат |
|---------|---------------------|
| `gflow auth status` | Сессия подтверждена, cookies валидны |
| `gflow auth list` | Профиль flow-mobile со статусом authenticated |
| `gflow credits` | Баланс кредитов (если профиль не заблокирован) |
| `gflow_auth_status` через MCP | Результат аутентификации |

---

## 8. Текущее состояние авторизации (до входа пользователя)

| Проверка | Статус |
|----------|--------|
| gflow auth status | No sign-in detected (профиль существует, но не авторизован) |
| gflow auth list | flow-mobile — present, не авторизован |
| gflow credits | ProfileLockedError (браузер gflow запущен, держит блокировку профиля) |

---

## 9. Ограничения (критически важно)

| Ограничение | Описание |
|-------------|----------|
| Клики через noVNC в Chrome | Chrome блокирует синтетические X11 мыши-события (защита от clickjacking). xdotool, x11vnc, XSendEvent — все игнорируются Chrome. |
| CDP Input Bridge | Chrome 156 не экспонирует CDP домены (Input, Runtime, Page) на TCP порту. Мост не может направлять клики в браузер gflow-cli. |
| Авторизация gflow | Требует интерактивного входа в Google через браузер. Нельзя автоматизировать без участия пользователя. |
| --no-spend | Соблюдён. Генерация не запускалась, кредиты не потрачены. |

---

## 10. Что Kilo может делать автономно после авторизации

| Операция | Автономно? |
|----------|------------|
| `gflow models` | ✅ Да (не требует auth) |
| `gflow docs` | ✅ Да (офлайн) |
| `gflow project list/create/show` | ✅ Да (локальный каталог) |
| `gflow data list/media/prune` | ✅ Да (локальный каталог) |
| `gflow image t2i/i2i/batch` | ❌ Нет (требует auth + кредиты) |
| `gflow video t2v/i2v/r2v/chain` | ❌ Нет (требует auth + кредиты) |
| `gflow auth status` | ✅ Да (read-only, статус авторизации) |

---

## 11. Файлы и скрипты

| Файл | Назначение |
|------|------------|
| `/home/vscode/input_bridge.py` | CDP Input Bridge (не функционален с gflow Chrome из-за ограничений Chrome 156) |
| `/home/vscode/input_client.html` | HTML клиент ввода (доступен по ссылке, но CDP мост не работает) |
| `/home/vscode/start_google_flow_clean.sh` | Запуск цепочки Xvfb → x11vnc → websockify → noVNC → Chrome |
| `/home/vscode/stop_google_flow_clean.sh` | Остановка цепочки |
| `/home/vscode/gflow-backup-20261031-121854/` | Резервная копия профилей и конфигов |

---

## 12. Вывод

Система частично готова к использованию:

**Готово:**
- gflow Chrome с профилем `profile_flow-mobile` запущен на Xvfb :99
- Окно видно через noVNC на порту 6080
- gflow auth login процесс запущен и ждёт входа пользователя
- --no-spend соблюдён

**Требует действий пользователя:**
- Пройти вход в Google через noVNC (ссылка выше)
- Завершить авторизацию в Flow (до загрузки редактора)
- Запустить `gflow auth status` для проверки

**Не работает:**
- CDP Input Bridge с браузером gflow-cli (Chrome 156 не экспонирует CDP домены)
- Клики через noVNC в Chrome (блокировка синтетических X11 событий)

**Существующие агенты, Context Mode, Auto Approve, OxionAI, MCP и YouTube-пайплайн не затронуты.**
