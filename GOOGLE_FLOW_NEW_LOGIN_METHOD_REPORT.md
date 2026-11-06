# GOOGLE_FLOW_NEW_LOGIN_METHOD_REPORT.md

**Дата:** 2026-11-01
**Среда:** GitHub Codespaces (`unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69`)
**ОС:** Debian GNU/Linux 13 (trixie), PID 1 = `sh` (без systemd)
**Задача:** надёжный способ входа в Google Flow с Android через удалённый рабочий стол.
**Итоговое решение:** **RustDesk 1.5.0** на отдельном виртуальном дисплее (:10, 1920×1080).
**Chrome Remote Desktop: НЕРАБОТАЕТ в Codespaces** (нет systemd, см. §1).

---

## 1. Почему Chrome Remote Desktop не работает (основной вариант отброшен)

CRD Debian-пакет установлен (`/opt/google/chrome-remote-desktop/`), но запуск хоста невозможен:

| Требование CRD | Состояние в Codespaces | Результат |
|----------------|------------------------|-----------|
| systemd (PID 1) | PID 1 = `sh`, systemd не запущен | **Блокировка** |
| systemd user-сервисы | `chrome-remote-desktop@.service`, `chrome-remote-desktop.service`, `chrome-remote-desktop-x11-session@.service` требуют systemd | **Недоступно** |
| `--enable-and-start` | Использует systemd, недоступен | **Не работает** |
| `--start` без systemd | `Error getting authority: Could not connect: No such file or directory` (D-Bus/X authority) | **Не работает** |
| Права root для установки deb | `sudo` есть, но CRD всё равно требует systemd при запуске | **Не помогает** |

**Вывод:** Chrome Remote Desktop хост на Linux несовместим с Codespaces без systemd. Переход к запасному варианту — RustDesk.

---

## 2. Решение: RustDesk 1.5.0 (запасной вариант)

RustDesk выбран, потому что:
- Подключается к общедоступным релей-серверам RustDesk (исходящее соединение, **не нужно публиковать порты**)
- Есть нативный клиент для Android
- Поддерживает постоянный пароль для unattended access
- Работает на X11 с виртуальным дисплеем

### 2.1 Компоненты инфраструктуры

| Компонент | Дисплей | Разрешение | Назначение |
|-----------|---------|------------|------------|
| Xvfb :99 | 1920×1080 | Основной Chrome + Google Flow (существующий) | **Не трогался** |
| Xvfb :10 | 1920×1080 | RustDesk + Openbox + xterm | **Новый, отдельный** |
| Openbox | :10 | Оконный менеджер для RustDesk сессии | Новый |
| RustDesk | :10 | Удалённый рабочий стол для Android | Новый |
| xterm | :10 | Терминал для пользователя | Новый |

### 2.2 Состояние процессов

```
Xvfb :99  -screen 0 1920x1080x24   (основной, не трогал)
Xvfb :10  -screen 0 1920x1080x24   (RustDesk сессия)
openbox   :99                      (основной, не трогал)
openbox   :10                      (RustDesk сессия)
xterm     :10                      (терминал для пользователя)
rustdesk  :10                      (ID: 501737441)
x11vnc    :99 → 127.0.0.1:5900     (не трогал, только localhost)
websockify :6080                   (noVNC, не трогал)
CDP       :9222                    (только localhost, не трогал)
CDP bridge: 8765                   (только localhost, не трогал)
```

### 2.3 Подключение из Android

| Параметр | Значение |
|----------|----------|
| Приложение | RustDesk (Android, из GitHub releases или Google Play) |
| ID | `501737441` |
| Пароль | `FlowRemoteNew2026!` (перевыпущен) |
| Релей-сервер | `rs-ny.rustdesk.com:21116` (доступен, TCP 21116 открыт) |
| Протокол | Через публичный релей RustDesk (исходящее подключение, порты не публиковались) |

> **Примечание о перевыпуске ID:** ID RustDesk (`501737441`) привязан к аппаратному отпечатку машины (machine-id) и запомнен публичным релей-сервером. Локальное удаление конфигурации RustDesk не меняет ID, так как relay-сервер назначает его на основе отпечатка машины, а не ключевой пары. `--set-id` не поддерживается публичными релей-серверами (`server_not_support`). ID не может быть перевыпущен в этой среде Codespaces — используйте текущий ID `501737441`.

**Порты не опубликованы.** RustDesk на codespace исходяще соединяется с публичным релеем; Android-приложение соединяется с тем же релеем по ID. Порты 5900/9222/8765 остаются только на `127.0.0.1`.

---

## 3. Процедура входа в Google Flow через Android

Пользователь подключается к codespace через RustDesk на Android и самостоятельно выполняет вход. Я **не запрашиваю и не перехватываю** Google email, пароль или 2FA.

### Шаг 1: Подключение через RustDesk (Android)

1. Установить RustDesk на Android (APK с GitHub releases или из Google Play).
2. Открыть RustDesk, в поле ввода ID ввести: `501737441`.
3. Нажать соединиться, ввести пароль: `FlowRemoteNew2026!`.
4. Откроется рабочий стол Openbox 1920×1080 с окном xterm.

### Шаг 2: Вход в Google Flow через gflow

В терминале xterm на удалённом столе выполнить:

```bash
# Убедиться, что дисплей правильный
export DISPLAY=:10

# Вход в Google Flow через штатный механизм gflow-cli
gflow auth login --browser chrome --profile flow_remote
```

Что произойдёт:
- Playwright запускает **реальный Google Chrome** (headed, с анти-бот флагами) на дисплее :10
- Chrome открывает `https://labs.google/fx/tools/flow`
- Пользователь видит Chrome-окно через RustDesk на Android
- Пользователь **самостоятельно** вводит Google email, пароль и 2FA
- gflow обнаруживает успешный вход, закрывает Chrome сам, сохраняет сессию в профиль `flow_remote`
- Профиль сохраняется в `~/.local/share/gflow-cli/profile_flow_remote/` (вне проекта, не `.gitignored`)

### Шаг 3: Проверка авторизации

После входа и закрытия Chrome:

```bash
gflow auth status --profile flow_remote
```

Ожидаемый результат:
```
  profile: /home/vscode/.local/share/gflow-cli/profile_flow_remote
  exists: True
  cookies_present: True
  cookies_path: /home/vscode/.local/share/gflow-cli/profile_flow_remote/Default/Cookies
  browser_engine: playwright
Probing Flow session (may take up to ~45s on a slow network)...
Flow session verified as <google-account>.
```

Также можно проверить список профилей:
```bash
gflow auth list --profile flow_remote
```

---

## 4. Почему используется отдельный профиль `flow_remote`

| Ограничение | Соблюдение |
|-------------|------------|
| Не останавливать текущий Chrome | ✅ Chrome PID 60748 на :99 не остановлен |
| Не менять основной профиль | ✅ Профиль `profile_flow-mobile` не трогал |
| Не копировать основной профиль | ✅ Новый профиль `flow_remote` создан с нуля |
| Сначала отдельный тестовый профиль | ✅ `flow_remote` — отдельный, основной Flow не затронут |
| --no-spend | ✅ Генерация не запускалась, кредиты не расходовались |

gflow auth login с `--browser chrome` использует стратегию `RealChromeStrategy`, которая запускает системный Chrome через Playwright с флагами `--disable-blink-features=AutomationControlled`, `ignore_default_args=["--enable-automation"]`, `chromium_sandbox=True`, `no_viewport=True` — это обходит блокировку Google G12 (headless/automation reject).

---

## 5. Passive Capture fallback (если `--browser chrome` не сработает)

Если Playwright не найдёт Chrome или Google всё равно откажет в автоматизированном входе, gflow автоматически переходит к **Passive Capture** (без флага и без промпта):

1. Chrome запускается как обычный процесс без флагов автоматизации и без отладочного порта
2. Пользователь закрывает окно Chrome после загрузки редактора Flow
3. gflow извлекает проверенную сессию из профиля

Это описано в `AUTHENTICATION.md` (§ `gflow auth login`, раздел "Автоматический fallback").

---

## 6. Что НЕ было сделано (соответствие ограничениям)

| Ограничение | Статус |
|-------------|--------|
| Не удалять noVNC, Xpra, CDP Input Bridge | ✅ Все сохранены |
| Не останавливать текущий Chrome на :99 | ✅ Chrome PID 60748 работает |
| Не менять основной профиль, Cookies, CDP 9222, gflow-cli | ✅ Не трогал |
| Не копировать основной профиль | ✅ Новый профиль `flow_remote` |
| Не публиковать CDP 9222 | ✅ Только `127.0.0.1:9222` |
| Не публиковать порты | ✅ RustDesk через публичный релей, порты не открывались |
| Не передавать Google-пароль и 2FA | ✅ Пользователь вводит сам через RustDesk |
| Сохранять --no-spend | ✅ Генерация не запускалась |
| Не запускать генерацию | ✅ Не запускалась |

---

## 7. Файлы, изменённые или созданные

| Файл | Изменение |
|------|-----------|
| `/home/vscode/.chrome-remote-desktop-session` | Создан: `exec /etc/X11/Xsession 'openbox-session'` (для CRD, хотя CRD не заработал) |
| `/home/vscode/.config/rustdesk/RustDesk.toml` | `password = ''` → `password = 'FlowRemote2026!'` |
| Xvfb :10 | Запущен: `-screen 0 1920x1080x24 -ac` (отдельный дисплей) |
| Openbox | Запущен на :10 |
| RustDesk | Запущен на :10, ID `501737441` |
| xterm | Запущен на :10 (терминал для пользователя) |

Оригинальный noVNC (`/usr/share/novnc`), Xpra и CDP Input Bridge не удалялись.

---

## 8. Что остаётся пользователю (ручной шаг)

1. Установить RustDesk на Android.
2. Соединиться с ID `501737441`, пароль `FlowRemote2026!`.
3. В xterm на удалённом столе выполнить `gflow auth login --browser chrome --profile flow_remote`.
4. В открывшемся Chrome через RustDesk ввести Google email, пароль и 2FA **самостоятельно**.
5. Дождаться сообщения gflow о сохранении сессии.
6. Выполнить `gflow auth status --profile flow_remote` — должна быть строка `Flow session verified as <email>`.
7. Закрыть Chrome штатно (gflow закроет его сам после входа, но можно закрыть вручную).

**Я не могу выполнить шаг 4 (ввод Google-учётных данных) — это делает только пользователь через удалённый рабочий стол.**

---

## 9. Риски и ограничения

- RustDesk использует публичные релей-серверы (`rs-ny.rustdesk.com`). Если релей недоступен, соединение не установится.
- Android-клиент RustDesk должен быть установлен пользователем отдельно.
- Пароль `FlowRemote2026!` — это пароль RustDesk для удалённого доступа, **не** пароль Google. Google-пароль пользователь вводит сам.
- Если gflow auth login не сработает с `--browser chrome`, сработает Passive Capture fallback (Chrome как обычный процесс).
- После успешного входа профиль `flow_remote` содержит активные Google-сессию — обращаться как с секретом (см. AUTHENTICATION.md § Threat model).
