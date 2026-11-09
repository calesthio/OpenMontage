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

После прохождения входа в браузере `gflow doctor` может сообщать `Google Flow login is required`, несмотря на наличие cookies (`flow.google.com: OSID, __Secure-OSID` и `google.com: SID, LSID, PSID`). Причины posibles:

1. Страница `flow.google.com` не успела загрузиться (SPA) — подождать 20–30 с и повторить `gflow doctor` один раз.
2. На странице отображается экран приветствия/согласия Flow, который требует ручного нажатия через VNC.
3. Chrome, запущенный вручную, удерживает профиль (SingletonLock) — убить вручную launched Chrome и повторить `gflow doctor`.

Не запускать `gflow doctor` в цикле — каждый вызов закрывает окно входа и перезапускает автоматизацию, что ломает сессию.

## Что НЕ делать

- Не запускать `gflow doctor` в цикле длительностью 25 минут.
- Не выводить значения cookies/токенов.
- Не коммитить `.gflow/` в git.
- Не запускать видеогенерацию (Veo-кредиты).