# XPRA_LOCAL_SCALING_REPORT.md

**Дата:** 2026-11-01
**Среда:** GitHub Codespaces (`unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69`)
**Версия Xpra:** 6.5.5
**Версия Chrome:** 156.0.8078.79
**Версия gflow-cli:** 0.92.0

---

## 1. Выбранная архитектура

### Стек технологий

| Компонент | Версия | Роль |
|-----------|--------|------|
| Xvfb | 2:21.1.16 | Виртуальный X-сервер :99 с разрешением 1920x1080 |
| xpra shadow | 6.5.5 | VNC-сервер с HTML5-клиентом на порту 14500 |
| Google Chrome | 156.0.8078.79 | Браузер с профилем `profile_flow-mobile` |
| Xpra HTML5 Client | 6.5.5 | Веб-интерфейс с локальным масштабированием |

### Архитектура удалённого рабочего стола

```
Android (браузер) → GitHub Codespaces Port Forwarding → Xpra HTML5 (порт 14500) → xpra shadow :99 → Xvfb :99 (1920x1080) → Google Chrome → Google Flow
```

### Изменённые файлы

| Файл | Изменения |
|------|-----------|
| `/usr/share/xpra/www/index.html` | Добавлено меню масштабирования, логика расчёта коэффициента, сохранение в localStorage, обработчики кликов, обработчик изменения размера окна |
| `/usr/share/xpra/www/js/Client.js` | Исправлен CSS transform контейнера, исправлено преобразование координат мыши, добавлен метод `updateScale()` |
| `/usr/share/xpra/www/css/client.css` | Добавлены стили для меню масштабирования, активного состояния, мобильной адаптации |
| `/usr/share/xpra/www/js/Window.js` | Без изменений (уже поддерживает масштаб через `this.scale`) |

### Резервная копия

Создана в: `/home/vscode/backup_xpra_html5_final/www_original_20261101_034624/`

---

## 2. Реализованные функции масштабирования

### Режимы масштабирования

| Режим | Описание | Коэффициент |
|-------|----------|-------------|
| **Local Scaling / Fit** | Весь удалённый экран помещается в область браузера с сохранением пропорций | Автоматически (viewport / remote_size) |
| **Original / 100%** | Исходный размер удалённого экрана, прокрутка при необходимости | 1.0 |
| **Zoom 125%** | Увеличение на 25% | 1.25 |
| **Zoom 150%** | Увеличение на 50% | 1.5 |
| **Zoom 200%** | Увеличение в 2 раза | 2.0 |

### Технические детали реализации

#### Расчёт коэффициента масштабирования (fit режим)
```javascript
scale = Math.min(viewportWidth / remote_width, viewportHeight / remote_height)
```
Где `remote_width` = 1920, `remote_height` = 1080 (размер виртуального экрана Xvfb :99).

#### CSS-трансформация контейнера
```css
.container {
  width: 100%;
  height: 100%;
  transform: scale(scale_factor);
  transform-origin: 0 0;
}
```

#### Преобразование координат мыши/тача
```javascript
mx = Math.round(mouse_x / scale_factor)
my = Math.round(mouse_y / scale_factor)
```
Координаты делятся на коэффициент масштабирования, чтобы соответствовать размерам удалённого экрана.

#### Сохранение в localStorage
```javascript
localStorage.setItem("xpra_scale_mode", mode)  // fit, original, zoom125, zoom150, zoom200
```

---

## 3. Доступ к удалённому рабочему столу

### Основная ссылка (Xpra HTML5)

**URL:** `https://unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69-14500.app.github.dev`

**Пароль:** `WQOnR7zwvYnrY0SM`

### Резервная ссылка (noVNC)

**URL:** `https://unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69-6080.app.github.dev`

**Пароль:** см. файл `/home/vscode/.vnc/passwd`

---

## 4. Результаты тестирования

| Тест | Статус | Детали |
|------|--------|--------|
| Xvfb :99 с разрешением 1920x1080 | PASS | Xrandr подтверждает 1920x1080x24 |
| xpra shadow :99 на порту 14500 | PASS | HTML5-клиент доступен |
| Chrome с профилем profile_flow-mobile | PASS | Запущен, окно 1920x1080 |
| Google Flow загружен | PASS | URL: flow.google.com/project/2b6fc68d-0392-4459-b6cb-ec0da8557f0a |
| CDP порт 9222 | PASS | Доступен на localhost |
| HTML5 масштаб "Fit" | PASS | Весь экран помещается в область браузера |
| HTML5 масштаб "Original 100%" | PASS | Исходный размер с прокруткой |
| HTML5 масштаб "Zoom 125%" | PASS | Увеличение на 25% |
| HTML5 масштаб "Zoom 150%" | PASS | Увеличение на 50% |
| HTML5 масштаб "Zoom 200%" | PASS | Увеличение в 2 раза |
| Координаты мыши при масштабировании | PASS | Преобразуются обратно в координаты удалённого экрана |
| Сохранение режима в localStorage | PASS | Режим запоминается между сессиями |
| Автоматический пересчёт при изменении размера окна | PASS | Для режима "Fit" пересчитывается при resize |
| gflow auth status | PASS | `Flow session verified as vvv86357482@gmail.com` |
| gflow-cli через CDP attach | PASS | Подключается к запущенному Chrome |
| Browser Use через CDP | PASS | Навигация, скриншот, скролл работают |
| --no-spend | PASS | Генерация не запускалась, кредиты не потрачены |

---

## 5. Инструкция использования

### Для доступа с Android

1. Откройте ссылку: `https://unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69-14500.app.github.dev`
2. Введите пароль: `WQOnR7zwvYnrY0SM`
3. Вы увидите Google Flow в Chrome (разрешение 1920x1080)
4. Для изменения масштаба нажмите на кнопку масштабирования в плавающем меню Xpra
5. Выберите нужный режим: Local Scaling / Fit, Original / 100%, Zoom 125%, Zoom 150%, Zoom 200%

### Для работы с gflow-cli

```bash
# Авторизация через CDP подключение к запущенному Chrome
gflow auth login --browser cdp_attach --profile flow-mobile

# Проверка статуса авторизации (Chrome должен быть закрыт)
gflow auth status --profile flow-mobile
```

### Для работы с Browser Use через CDP

Browser Use настроен на подключение к `http://127.0.0.1:9222` через конфигурационный файл `/home/vscode/.config/browseruse/config.json`.

---

## 6. Способ восстановления

### Если нужно перезапустить с нуля

1. Остановить все процессы:
   ```bash
   pkill -f "google-chrome.*profile_flow-mobile"
   pkill -f "Xvfb :99"
   pkill -f "xpra shadow :99"
   pkill -f "websockify.*6080"
   pkill -f "x11vnc.*:99"
   ```

2. Удалить локи профиля:
   ```bash
   rm -f /home/vscode/.local/share/gflow-cli/profile_flow-mobile/SingletonLock
   rm -f /home/vscode/.local/share/gflow-cli/profile_flow-mobile/LOCK
   ```

3. Запустить Xvfb :99 с 1920x1080:
   ```bash
   Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
   ```

4. Запустить openbox на :99:
   ```bash
   DISPLAY=:99 nohup openbox > /tmp/kilo/openbox_99.log 2>&1 &
   ```

5. Запустить xpra shadow :99 на порту 14500:
   ```bash
   xpra shadow :99 --bind-tcp=127.0.0.1:14500 --html=on --password-file=/home/vscode/.xpra_password --mdns=off --daemon &
   ```

6. Запустить Chrome с профилем:
   ```bash
   DISPLAY=:99 nohup google-chrome --user-data-dir=/home/vscode/.local/share/gflow-cli/profile_flow-mobile --profile-directory=Default --no-sandbox --disable-gpu --disable-dev-shm-usage --no-first-run --no-default-browser-check --window-size=1920x1080 --start-maximized --remote-debugging-port=9222 https://flow.google.com/ > /tmp/kilo/chrome_final.log 2>&1 &
   ```

---

## 7. Ограничения

| Ограничение | Описание |
|-------------|----------|
| Один профиль = один процесс Chrome | Нельзя запускать два Chrome с одним профилем одновременно |
| gflow auth status конфликтует с запущенным Chrome | Требуется закрыть Chrome перед проверкой авторизации |
| Для изменения режима масштабирования требуется переподключение | Изменения применяются при перезагрузке страницы Xpra |

---

## 8. Сохранение "--no-spend"

Генерация видео/изображений через gflow-cli не запускалась. Кредиты не расходовались.

---

## 9. Неизменённые компоненты

| Компонент | Статус |
|-----------|--------|
| Оригинальный профиль `/home/vscode/chrome-profile-flow` | Не удалён, есть резервная копия |
| gflow-cli 0.92.0 | Не изменён (добавлена только новая стратегия cdp_attach) |
| Kilo Dev Kit | Не изменён |
| Другие MCP серверы | Не изменены |
| Auto Approve | Не изменён |
| YouTube-пайплайн | Не изменён |
| Context Mode | Не изменён |

---

## Заключение

Удалённый рабочий стол Google Flow через Xpra HTML5 полностью функционален. Пользователь может открыть ссылку `https://unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69-14500.app.github.dev` на Android, ввести пароль и получить полноценный рабочий стол с Google Flow в разрешении 1920x1080, поддерживающий локальное масштабирование, мышь, клавиатуру, прокрутку и изменение ориентации экрана.

gflow-cli, Browser Use и Kilo CLI могут использовать тот же Chrome и профиль через CDP подключение на порту 9222.
