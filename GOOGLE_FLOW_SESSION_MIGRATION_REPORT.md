# GOOGLE_FLOW_SESSION_MIGRATION_REPORT.md

**Дата:** 2026-10-31
**Среда:** GitHub Codespaces (`unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69`)
**Версия gflow-cli:** 0.92.0
**Версия Kilo CLI:** 7.8.25
**Версия Browser Use:** 0.13.14

---

## 1. Аудит профилей и конфигов

### Путти профилей до миграции

| Профиль | Путь | Состояние авторизации | Cookies |
|---------|------|----------------------|---------|
| Оригинальный Chrome | `/home/vscode/chrome-profile-flow` | Авторизован (37 Google cookies) | 36,864 байт |
| gflow-cli | `/home/vscode/.local/share/gflow-cli/profile_flow-mobile` | Не авторизован (account=unknown) | 20,480 байт |

### Переменные окружения

| Переменная | До миграции | После миграции |
|------------|-------------|----------------|
| GFLOW_CLI_HOME | не設置но | `/home/vscode/.local/share/gflow-cli` (в kilo.jsonc) |
| GFLOW_CLI_PROFILE | не設置но | `flow-mobile` (в kilo.jsonc) |

### Файлы профиля gflow-cli

| Файл | Содержимое |
|------|------------|
| `.gflow_browser_strategy` | `chrome` |
| `.gflow_account` | пусто (не существует) |
| `config.toml` | `default_profile = "flow-mobile"` |

---

## 2. Резервные копии

Созданы в `/home/vscode/backup_flow_migration/20261031_160415/`:

| Файл/папка | Описание |
|------------|----------|
| `chrome-profile-flow/` | Полная копия оригинального Chrome профиля |
| `profile_flow-mobile_original/` | Полная копия исходного gflow профиля (до миграции) |
| `config.toml` | Конфигурация gflow-cli |
| `browseruse_config.json` | Конфигурация Browser Use |

Оригинальный профиль `/home/vscode/chrome-profile-flow` **не удалён** и доступен в резервной копии.

---

## 3. Перенос профиля

### Процедура

1. Остановлен Chrome (PID 303972) с профилем `profile_flow-mobile`
2. Удалены процесс-зависимые файлы: `SingletonLock`, `LOCK`, `Cookies-journal`, `Local State-journal`
3. Целевой профиль `profile_flow-mobile` очищен
4. Все файлы скопированы из `chrome-profile-flow` в `profile_flow-mobile` (включая Cookies, Local State, CertificateRevocation и все остальные данные)
5. Проверено отсутствие лок-файлов

### Файлы, скопированные из оригинального профиля

| Файл | Размер | Значение |
|------|--------|----------|
| `Default/Cookies` | 36,864 байта | Google сессионные cookies (авторизация) |
| `Local State` | 10,555 байт | Настройки профиля Chrome |
| `Default/` | 45 подпапок | Данные веб-сайтов, локальное хранилище |
| `CertificateRevocation/` | 3 подпапки | Сертификаты отзыва |

---

## 4. Регистрация профиля в gflow-cli

### Проверка файлов профиля

| Файл | Значение |
|------|----------|
| `.gflow_browser_strategy` | `chrome` (использовать системный Chrome) |
| `.gflow_account` | отсутствует (не требуется для существующего профиля) |

### Процедура регистрации

gflow-cli автоматически обнаружил профиль при проверке `gflow auth status`. Дополнительная регистрация через `gflow auth login` **не требуется**, так как профиль уже содержит валидные cookies сессии Google Flow.

---

## 5. Конфигурация компонентов

### gflow-cli

| Параметр | Значение |
|----------|----------|
| `GFLOW_CLI_HOME` | `/home/vscode/.local/share/gflow-cli` (в kilo.jsonc env) |
| `GFLOW_CLI_PROFILE` | `flow-mobile` (в kilo.jsonc env) |
| Профиль по умолчанию | `flow-mobile` (в config.toml) |
| Путь профиля | `/home/vscode/.local/share/gflow-cli/profile_flow-mobile` |

### Browser Use

| Параметр | Значение |
|----------|----------|
| `user_data_dir` | `/home/vscode/.local/share/gflow-cli/profile_flow-mobile` |
| `profile_directory` | `Default` |
| `executable_path` | `/usr/bin/google-chrome` |
| `headless` | `false` |
| Config файл | `/home/vscode/.config/browseruse/config.json` |

### Kilo CLI

| Параметр | Значение |
|----------|----------|
| gflow MCP сервер | connected ✓ |
| GFLOW_CLI_HOME | `/home/vscode/.local/share/gflow-cli` |
| GFLOW_CLI_PROFILE | `flow-mobile` |
| Config файл | `/home/vscode/.config/kilo/kilo.jsonc` |

---

## 6. Проверка результатов

### gflow auth status (Chrome закрыт)

```
profile: /home/vscode/.local/share/gflow-cli/profile_flow-mobile
exists: True
cookies_present: True
browser_engine: playwright
Flow session verified as vvv86357482@gmail.com
```

| Проверка | Статус | Детали |
|----------|--------|--------|
| Профиль существует | PASS | `/home/vscode/.local/share/gflow-cli/profile_flow-mobile` |
| Cookies присутствуют | PASS | `Default/Cookies` (36,864 байта) |
| Сессия Flow валидна | PASS | `vvv86357482@gmail.com` |
| Событие авторизации | PASS | `auth_migrated_host_fallback_authenticated` |

### gflow auth status (Chrome запущен с профилем)

| Проверка | Статус | Детали |
|----------|--------|--------|
| gflow auth status | ProfileLockedError | Ожидаемо — Chrome использует профиль |

**Это не ошибка авторизации, а ожидаемое поведение:** один профиль не может быть открыт в двух процессах Chrome одновременно. Когда Chrome закрыт, gflow-cli видит авторизованную сессию.

### Browser Use (с user_data_dir, Chrome закрыт)

| Проверка | Статус | Детали |
|----------|--------|--------|
| Навигация (example.com) | PASS | `OK` |
| Get state (URL, title, elements) | PASS | URL, title, interactive_elements возвращаются |
| Скриншот | PASS | Возвращается изображение |

### Browser Use (с cdp_url, Chrome запущен)

| Проверка | Статус | Детали |
|----------|--------|--------|
| Навигация | PASS | `OK` |
| Get state | ⚠️ Ограничение | Invalid request parameters (известная проблема с Chrome 156 + CDP) |

### Kilo MCP

| Проверка | Статус | Детали |
|----------|--------|--------|
| gflow MCP сервер | PASS | `connected` |
| gflow mcp run | PASS | Доступен |

### noVNC

| Проверка | Статус | Детали |
|----------|--------|--------|
| URL | PASS | `https://unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69-6080.app.github.dev` |
| Chrome отображает Flow | PASS | `https://flow.google.com/` |
| CDP порт 9224 | PASS | Доступен локально |

---

## 7. Ограничение: один профиль = один процесс

Критически важное ограничение Chrome: один профиль пользователя не может быть открыт в двух независимых процессах Chrome одновременно.

### Режимы работы

| Режим | Chrome (noVNC) | gflow-cli / Browser Use | Когда использовать |
|-------|---------------|------------------------|-------------------|
| Режим просмотра | Запущен с профилем | ❌ ProfileLockedError | Пользователь смотрит Flow через noVNC |
| Режим автоматизации | Закрыт | ✅ Работает через Playwright | gflow-cli, Browser Use, Kilo MCP |

### Организация последовательного использования

1. **Для просмотра через noVNC:** Запустить Chrome с профилем `profile_flow-mobile` на Xvfb :99
2. **Для автоматизации (gflow-cli, Browser Use):** Закрыть Chrome, затем запустить gflow-cli или Browser Use — они запустят свой экземпляр Chrome с тем же профилем
3. **Переключение:** Всегда закрывать Chrome перед переключением режима

---

## 8. --no-spend

| Проверка | Статус |
|----------|--------|
| Генерация не запускалась | PASS |
| Кредиты не расходовались | PASS |
| gflow auth login не выполнялся (сессия уже была валидна) | PASS |

---

## 9. Неизменённые компоненты

| Компонент | Статус |
|-----------|--------|
| Оригинальный профиль `/home/vscode/chrome-profile-flow` | Не удалён, есть резервная копия |
| Kilo Dev Kit | Не изменён |
| Другие MCP серверы (github, context7, playwright, git, filesystem) | Не изменены |
| Auto Approve | Не изменён |
| YouTube-пайплайн | Не изменён |
| Context Mode | Не изменён |

---

## 10. Итог

### Что достигнуто

| Цель | Статус |
|------|--------|
| Профиль перенесён из chrome-profile-flow в profile_flow-mobile | PASS |
| gflow auth status показывает авторизованную сессию | PASS |
| gflow MCP подключён к Kilo | PASS |
| Browser Use работает с профилем (user_data_dir) | PASS |
| Chrome запущен с профилем для noVNC | PASS |
| --no-spend соблюдён | PASS |

### Готовые ссылки

| Цель | URL |
|------|-----|
| noVNC (просмотр Google Flow) | `https://unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69-6080.app.github.dev` |
| VNC пароль | см. `/home/vscode/.vnc/passwd` |

### Рекомендации по использованию

1. Для просмотра Flow через noVNC: Chrome уже запущен с профилем, откройте ссылку noVNC
2. Для работы с gflow-cli/Browser Use: закройте Chrome (noVNC), затем запустите `gflow auth status` или Browser Use — они будут использовать тот же профиль `profile_flow-mobile`
3. Для возврата к просмотру: снова запустите Chrome с профилем `profile_flow-mobile`

**Сессия Google Flow авторизована как `vvv86357482@gmail.com` и готова к использованию через gflow-cli, Kilo MCP и Browser Use.**
