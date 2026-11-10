# Google Flow (gflow) — авторизация

**Версия gflow:** 1.3.0 (`@lechcher/gflow-cli`, npx/npm)
**Профиль:** `/workspaces/OpenMontage/.gflow/profiles/default`
**git:** папка `.gflow/` добавлена в `.gitignore` (через `git check-ignore` подтверждено, секреты/куки не попадают в репозиторий).

## Процедура входа (повторяемая)

```bash
# 1. Виртуальный экран (требуется для Chrome)
Xvfb :99 -screen 0 1280x800x24 &
x11vnc -display :99 -localhost -forever -shared -nopw &
websockify --web /usr/share/novnc 6080 localhost:5900 &
# VNC: https://${CODESPACE_NAME}-6080.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}/vnc.html?autoconnect=1&resize=scale

# 2. Вход в Google Flow через Chrome (одно окно, без отладки)
GFLOW_CHROME_PATH=/opt/google/chrome/chrome DISPLAY=:99 gflow auth login --profile default
# В открывшемся Chrome: flow.google.com → войти в Google → подтвердить 2FA → принять условия Flow

# 3. Проверка готовности (один раз, без цикла)
GFLOW_CHROME_PATH=/opt/google/chrome/chrome DISPLAY=:99 gflow doctor --headed

# 4. После успеха — только чтение баланса
GFLOW_CHROME_PATH=/opt/google/chrome/chrome DISPLAY=:99 gflow credits user

# 5. Остановка виртуального экрана
pkill -f "x11vnc -display :99"
pkill -f "websockify.*6080"
pkill -f "Xvfb :99"
```

## Безопасность

- Никогда не выводить (`cat`/`print`/`echo`) cookies, профиль, токены, `Local State`, `DevToolsActivePort`.
- `.gflow/` в `.gitignore` — не коммитить профиль, куки, кэш.
- Не использовать stealth/anti-detect приёмы, не копировать cookies вручную.
- Veo-кредиты не тратить — только `gflow credits user` (чтение) и одна тестовая картинка (`gflow image t2i ...`).
- Видео не запускать.

## Известная проблема (документирована)

После прохождения входа в браузере `gflow doctor` может сообщать `Google Flow login is required`, несмотря на наличие cookies (`flow.google.com: OSID, __Secure-OSID` и `google.com: SID, LSID, PSID`). Причины:

1. Страница `flow.google.com` не успела загрузиться (SPA) — подождать 20–30 с и повторить `gflow doctor` один раз.
2. На странице отображается экран приветствия/согласия Flow, который требует ручного нажатия через VNC.
3. Chrome, запущенный вручную, удерживает профиль (SingletonLock) — убить вручную launched Chrome и повторить `gflow doctor`.
4. **Интерфейс Flow на русском языке**, а gflow v1.3.0 ищет английские селекторы (`new project`, `Start generation`). `gflow doctor` проходит Flow-проверку, но `gflow image` падает с `Could not find the Flow prompt box` — селектор `newProjectButton` (`/new project|Новый проект|Создать|Отправить/i`) не находит кнопку «Новый проект» на русском UI, либо клик не срабатывает из-за перекрывающих диалогов согласия.

Не запускать `gflow doctor` в цикле — каждый вызов закрывает окно входа и перезапускает автоматизацию, что ломает сессию.

## Локальный патч с русскими локаторами (не в системную установку)

Пакет скопирован в `~/gflow-local/` (не в системную установку npm). В `~/gflow-local/dist/src/flow/locators.js` добавлены русские варианты:

- `dashboardMarker` / `newProjectButton`: `/new project|Новый проект|Создать|Отправить/i`
- `submitButton` / `characterCreateButton`: `/Start generation|Начать генерацию|Создать|Отправить|arrow_forward/i`
- `agentInstructionsButton`: `/Agent instructions|Инструкции для агента/i`
- `addIngredientButton`: `/Add ingredients to the prompt box|Добавить ингредиенты в окно запроса/i`
- `settingsSaveButton`: `/Save|Сохранить/i`
- Маркеры ошибок: добавлены русские паттерны (`необычн`, `кредит`, `политик`, `ошибк`, `подтвержд` и др.)

В `~/gflow-local/dist/src/flow/page.js`:
- `open()`: не делает `goto` если уже на `flow.google.com`; после загрузки вызывает `dismissConsentDialogs()` (3 попытки с паузой 500 мс).
- `dismissConsentDialogs()`: клик по кнопкам `ОК`, `Включить`, `Закрыть сообщение`, `Закрыть баннер`, `Отмена`, `OK`, `Enable`, `Close message`, `Close banner`, `Cancel`.
- `ensureProject()`: после клика «Новый проект» — 5 попыток dismissed dialogs + waitFor promptBox с таймаутом 5 с.
- `assertReady()`: пропускает DOM-проверку (знак готовости подтверждён через куки и ручную навигацию).

Запуск локальной копии: `cd ~/gflow-local && node run.js <command>`.

## Альтернатива (работает)

Прямая CDP-автоматизация Chrome с профилем gflow подтверждена рабочей: вход, диалоги, «Новый проект», ввод промпта, клик «Начать генерацию», загрузка результата — выполнено успешно через WebSocket DevTools API. Генерация одной тестовой картинки `simple blue circle on white` (16:9) подтверждена.

## Что НЕ делать

- Не запускать `gflow doctor` в цикле длительностью 25 минут.
- Не выводить значения cookies/токенов.
- Не коммитить `.gflow/` в git.
- Не запускать видеогенерацию (Veo-кредиты).