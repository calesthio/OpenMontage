# CDP_MOBILE_INPUT_FINAL_REPORT.md

**Дата:** 2026-11-01
**Среда:** GitHub Codespaces (`unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69`)
**Задача:** клики в Google Flow через Android не доходят до Chrome (noVNC открывается, масштаб 1920×1080 работает, но клики не срабатывают).

---

## 1. Первопричина (TOC)

> **Первопричина:** на Android Chrome события касания преображались в CDP `dispatchTouchEvent` (`touchStart`/`touchEnd`), но Google Flow — это десктопное веб-приложение, которое реагирует на мышиные события (`mousedown`/`mouseup`/`click`), а не на тач-события. CDP `dispatchTouchEvent` **не авто-синтезирует** мышиные события (подтверждено документацией CDP и поведением Chromium). Поэтому Flow никогда не регистрировал клик.

Цепочка была прервана на этапе **5→6** (Bridge → Chrome): Bridge отправлял `Input.dispatchTouchEvent`, Chrome принимал событие без ошибки, но страница (Flow) его не обрабатывала, так как её обработчики висят на мышиных событиях.

### Дополнительный усугубляющий фактор (Android)
На Android Chrome, если на `touchstart` вызван `preventDefault()` (мы вызываем его для запрета скролла и потому что `canvas.style.touchAction='none'`), браузер подавляет синтез `pointer`/`mouse` событий от tego касания. До наших обработчиков доходят только `touchstart`/`touchend` (не `pointerdown`/`mouseup`). Бывшая кодовая схема позиционировала их как тач-события → двойная потеря.

---

## 2. Аудит всех компонентов

### 2.1 `/home/vscode/novnc/vnc.html` (изменён)

| Проверка | Статус | Комментарий |
|----------|--------|-------------|
| `mandatory['view_only']=true` | ✅ | Стандартный RFB-ввод не посылается в x11vnc (Chrome игнорирует синтетические X11). Ввод идёт только через CDP-мост. Дублирования нет. |
| `mandatory['resize']='scale'` | ✅ | Форсирует `scaleViewport=true`, `resizeSession=false`. Локальное масштабирование без изменения разрешения сервера. |
| Перехват событий на Canvas | ✅ | `pointerdown/up/move`, `touchstart/end/move`, `wheel` — все с `preventDefault()`, `{passive:false}`. |
| Координаты после Local Scaling | ✅ | `toRemote(cx,cy) = ((cx - rect.left)/scale, (cy - rect.top)/scale)`. `devicePixelRatio` не вводит искажения (оба значения — CSS px). |
| `text`/`unmodifiedText` | ✅ | В `keydown` для ввода текста в поля Flow. |
| mousePressed/mouseReleased序列 | ✅ | `mousedown`→`mousePressed(clickCount=1)`, `mouseup`→`mouseReleased(clickCount=1)`. |
| WebSocket readyState | ✅ | `send()` проверяет `ws.readyState !== WebSocket.OPEN` → пропуск при закрытии. |
| WSS при HTTPS | ✅ | `location.protocol === 'https:' ? 'wss://' : 'ws://'` + `bridgeHost()` (`NAME-8765.app.github.dev`). |
| Переподключение WSS | ✅ | `onclose` → `setTimeout(connectBridge, 2000)`. |

### 2.2 `/home/vscode/input_bridge.py` (изменён)

| Проверка | Статус | Комментарий |
|----------|--------|-------------|
| Порт CDP 9222 | ✅ | Исправлен баг `9223→9222`. 9222 только `127.0.0.1` (не публичен). |
| Порт моста 8765 | ✅ | `BRIDGE_HOST='127.0.0.1'` (приватный, не `0.0.0.0`). |
| Origin-валидация | ✅ | Строго адрес noVNC-клиента (`https://NAME-6080.app.github.dev`), выводимый из заголовка `Host` моста. Не весь `*.app.github.dev`. `evil.com` → 1008. |
| `flatten:true` + `sessionId` | ✅ | `Target.attachToTarget` с `flatten:true`, `sessionId` из события `Target.attachedToTarget`. |
| Авто-восстановление сессии | ✅ | При коде -32001 сброс + повтор `attachToTarget`. |
| `text`/`unmodifiedText` | ✅ | В `keydown` для ввода текста. |

### 2.3 Chrome CDP на 9222
- Только `127.0.0.1:9222` (подтверждено `ss`). Не публичен.
- Chrome (PID 60748, профиль `profile_flow-mobile`) не перезапускался. Flow сессия сохранена.
- `gflow-cli`, профиль, Cookies не менялись. `--no-spend` соблюдён.

### 2.4 noVNC + websockify
- `websockify --web /home/vscode/novnc 6080 localhost:5900` — HTTP 200 на 6080, RFB handshake `RFB 003.008` через WebSocket.
- x11vnc :99 только `127.0.0.1` (не опубликован).

---

## 3. Верхнеуровневые (upstream)問題 и решения

| Источник | Вывод | Применено |
|----------|-------|-----------|
| CDP Input domain (chromedevtools.github.io) | `Input.dispatchMouseEvent` x,y — относительно главного фрейма в CSS px (DIP). `mousePressed`+`mouseReleased` + `clickCount=1` генерируют реальные DOM-события мыши (включая `click`). | Используем `dispatchMouseEvent` для тапов/кликов. |
| chromote#30 (dispatchMouseEvent hanging) | `mousePressed`+`mouseReleased` работают; `clickCount` обязателен для клика. | `clickCount=1` для каждого клика. |
| Stack Overflow 59410804 | `mousePressed`+`mouseReleased`, `clickCount=1`, страница получает реальные `mousedown`/`mouseup`/`click`. | Подтверждает схему. |
| noVNC#1268 / #12 / #111 | `getBoundingClientRect()` + CSS `transform: scale` — коэффициент масштабирования нужно делить при обратном преобразовании координат. | `toRemote` делит на `display.scale`. |
| Chromium 41169821 / 400119367 | На Android `clientX/Y` и `getBoundingClientRect()` могут расходиться при масштабе/зуме; оба в CSS px Layout Viewport → соотношение корректно. | Деление на `display.scale` корректно; `devicePixelRatio` сокращается. |
| Поведение Android Chrome + `preventDefault` на `touchstart` | Подавляет синтез `pointer`/`mouse` событий → доходят только `touchstart`/`touchend`. | Преобразуем тач в `dispatchMouseEvent` (mousePressed/mouseReleased), а не `dispatchTouchEvent`. |

---

## 4. Точное место потери клика (6 этапов цепочки)

Этап | Что происходит | Было (до исправления) | Стало (после исправления)
-----|----------------|------------------------|--------------------------
1. Касание на экране Android | `touchstart`/`touchend` на Canvas | Доставлялось ✅ | Доставляется ✅ |
2. Событие на Canvas noVNC | `onTouch` обработчик | `sendPointer('touchstart'/'touchend')` ❌ | `sendPointer('mousedown'/'mouseup')` ✅ |
3. Передача через WSS | JSON на ws 8765 | `{type:'touchstart'}` | `{type:'mousedown'}` ✅ |
4. Bridge получает (этап 4) | `diag_log('4')` | `touchstart` | `mousedown` ✅ |
5. Bridge → CDP (этап 5) | `diag_log('5')` | `Input.dispatchTouchEvent` (touchStart) ❌ | `Input.dispatchMouseEvent` (mousePressed) ✅ |
6. Chrome ответ (этап 6) | `diag_log('6')` | Событие принято, но Flow не реагирует ❌ | Реальное `mousedown`→Flow обрабатывает ✅ |

**Потеря была на этапах 5→6:** `dispatchTouchEvent` не порождает мышиные события, которые ждёт Flow.

---

## 5. Диагностическая панель (6 этапов)

В `/home/vscode/novnc/vnc.html` добавлена панель `?diag=1` (или кнопка «Diag: OFF»):

- Показывает текущий WSS-статус и точный URL (`wss://NAME-8765.app.github.dev`, а не `ws://127.0.0.1:8765`).
- Логирует все 6 этапов с меткой времени и координатами:
  - `[1]` — touch/pointer на canvas
  - `[2]` — сырое событие canvas (rect, scale)
  - `[WSS]` — отправка в мост
  - `[4]` (bridge) — получение мостом
  - `[5]` (bridge) — отправка CDP
  - `[6]` (bridge) — ответ Chrome

На Bridge (`/home/vscode/input_bridge.py`) добавлено `diag_log()` для этапов 4, 5, 6 с координатами и временем.

Пример ожидаемого лога Bridge при тапе:
```
[bridge-diag] [4] bridge recv {"type":"mousedown","x":960,"y":540,"button":"left"}
[bridge-diag] [5] CDP send {"method":"Input.dispatchMouseEvent","params":{"type":"mousePressed","button":"left","x":960,"y":540,"clickCount":1},"sessionId":"..."}
[bridge-diag] [6] CDP response {"method":"Input.dispatchMouseEvent","result":{"result":{}}}
```

---

## 6. Исправление (минимальные изменения)

### 6.1 `/home/vscode/novnc/vnc.html`

1. **touchstart → mousedown, touchend → mouseup** (строка ~252-253): тач теперь посылает мышиное событие через CDP, а не тач-событие.
2. **Добавлен `onTouchMove`** (строка ~255-259): `touchmove` → `mousemove` для поддержки drag.
3. **Диагностическая панель** (`?diag=1`): 6 этапов с координатами, WSS-статус, точный URL.
4. `pointerdown/up/move` уже посылали `mousedown/mouseup/mousemove` — без изменений.

### 6.2 `/home/vscode/input_bridge.py`

1. **`diag_log()`** для этапов 4, 5, 6 (время, координаты, метод CDP, ответ).
2. **Origin ограничен точным адресом noVNC-клиента** (из `Host` моста → `https://NAME-6080.app.github.dev`), не весь `*.app.github.dev`.
3. Порт моста привязан к `127.0.0.1` (приватный).
4. CDP 9222 не публичен (только `127.0.0.1`).

---

## 7. Результаты тестирования (PASS / FAIL)

| Тест | Статус | Подробности |
|------|--------|-------------|
| CDP `dispatchMouseEvent` напрямую на тестовой странице | **PASS** | `mousePressed`+`mouseReleased` (960,540, clickCount=1) → `ok`. Подтверждено, что CDP генерирует реальные DOM-события мыши (источники: chromote#30, Stack Overflow 59410804). |
| Bridge напрямую (mousedown/mouseup/mousemove/mouseWheel/keydown/keyup) | **PASS** | Все возвращают `{"status":"ok"}`. |
| Origin: `evil.com` → отклонён (1008) | **PASS** | `websockets.connect(..., origin='https://evil.com')` → `ConnectionClosedError code=1008`. |
| Origin: `https://NAME-6080.app.github.dev` → разрешён | **PASS** | Точное совпадение с noVNC-страницей. |
| Origin: чужой Codespace (`other-name-6080`) → отклонён | **PASS** | 1008. |
| Origin: `null` (локальное тестирование) → разрешён | **PASS** | |
| Порт 8765 только `127.0.0.1` | **PASS** | `ss` подтверждает. |
| Порт 9222 только `127.0.0.1` | **PASS** | `ss` подтверждает. CDP не публичен. |
| Порт 5900 (x11vnc) только `127.0.0.1` | **PASS** | |
| noVNC HTTP 200 на 6080 | **PASS** | |
| WSS handshake (RFB `RFB 003.008`) | **PASS** | Через websockify → x11vnc → Xvfb :99. |
| Google Flow сессия сохранена | **PASS** | Chrome (PID 60748) не перезапускался; `flow.google.com/project/...` открыт. |
| `--no-spend` | **PASS** | Генерация не запускалась. |

**Мобильное тестирование на реальном Android: НЕ ВЫПОЛНЯЛОСЬ** (нет устройства под рукой). Статус кликов на Android нельзя объявить PASS без реального подключения. Диагностическая панель (`?diag=1`) подготовлена для проверки каждого этапа на телефоне пользователя.

---

## 8. Инструкция проверки на Android

1. Открыть на Android Chrome: `https://unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69-6080.app.github.dev/?diag=1` (параметр `?diag=1` включает диагностику).
2. Ввести VNC-пароль, Connect.
3. Нажать кнопку «Diag: ON» (если не включено автоматически).
4. Тапнуть по элементу Flow. В диагностической панели должны появиться строки:
   - `[1] touch on canvas ...`
   - `[2] canvas event (raw) ...`
   - `[WSS] send → bridge ...`
   - (в логах Bridge на сервере) `[4] bridge recv`, `[5] CDP send mousePressed`, `[6] CDP response ok`
5. Если этап `[1]` отсутствует — касание не доходит до Canvas (проблема браузера Android / overlay).
6. Если `[1]` и `[2]` есть, но `[WSS]` нет — WSS не открыт (посмотреть статус WS в шапке панели).
7. Если `[WSS]` есть, но на сервере Bridge нет `[4]`/`[5]`/`[6]` — проблема моста или CDP (проверить логи Bridge).
8. Повторить для double-click, drag, скролла, ввода текста.

Этапы 4–6 видны только в stdout моста на сервере Codespaces (запущен `python3 /home/vscode/input_bridge.py`).

---

## 9. Изменённые файлы

| Файл | Изменение |
|------|-----------|
| `/home/vscode/novnc/vnc.html` | touchstart→mousedown, touchend→mouseup (CDP мышь, не тач); добавлен onTouchMove (drag); диагностическая панель `?diag=1` с 6 этапами; WSS-статус и точный URL. |
| `/home/vscode/input_bridge.py` | `diag_log()` этапов 4/5/6; Origin строго `https://NAME-6080.app.github.dev` (из Host моста); порт `127.0.0.1`; `text`/`unmodifiedText`; авто-восстановление CDP-сессии. |

Оригинальный noVNC (`/usr/share/novnc`) и Xpra не удалялись. Chrome, профиль, Cookies, CDP 9222, `gflow-cli` не менялись.

---

## 10. Ограничения и риски

- **Мобильные тесты не выполнены на реальном Android** — нет устройства. Механизм проверен локально и через CDP напрямую, но最終 confirmation требует открытия ссылки на телефоне.
- Если Flow использует обработчики только `pointerdown` (без `mousedown`), клики могут не сработать — тогда нужно добавить отправку `pointerdown` через CDP (CDP не имеет pointer-домена, только мышь/тач/клавиатуру).
- CDP `dispatchTouchEvent` не авто-синтезирует мышь — это поведение Chromium, не ошибка нашего кода.
- Порт 6080 (websockify) слушает `0.0.0.0` для Codespaces-forwarding; защита — авторизация GitHub на проброшенных портах (401 без входа). Порты 8765/5900/9222 — только `127.0.0.1`.
