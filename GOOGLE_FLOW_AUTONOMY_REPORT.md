# GOOGLE_FLOW_AUTONOMY_REPORT.md

**Дата:** 2026-10-31
**Среда:** GitHub Codespaces (`unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69`)
**Версия gflow-cli:** 0.92.0
**Версия Kilo CLI:** 7.8.25

---

## 1. Статус авторизации gflow vs Chrome

| Компонент | Статус | Детали |
|-----------|--------|--------|
| Chrome профиль (`chrome-profile-flow`) | АВТОРИЗОВАН | 37 Google cookies, Flow dashboard виден через CDP |
| gflow профиль (`profile_flow-mobile`) | НЕ АВТОРИЗОВАН | `gflow auth status`: "No sign-in detected" |
| Связь между профилями | ОТДЕЛЬНЫЕ | gflow использует Playwright, не Chrome — сессии не gemeinsamen |

**Ключевой вывод:** Chrome в noVNC авторизован в Google Flow, но gflow-cli использует СВОЙ отдельный Playwright-профиль, который не авторизован. gflow не может автоматически подхватить Chrome-сессию.

---

## 2. gflow_auth_status

```
profile: /home/vscode/.local/share/gflow-cli/profile_flow-mobile
exists: True
cookies_present: True
cookies_path: /home/vscode/.local/share/gflow-cli/profile_flow-mobile/Default/Cookies
browser_engine: playwright
Probing Flow session...
No sign-in detected. Run gflow auth login --profile flow-mobile to refresh the session.
```

- Профиль существует, cookies-файл есть, но сессия не валидна
- `gflow auth renew` не работает — профиль заблокирован (Chrome держит X11 дисплей / профиль)
- Требуется ручной вход: `gflow auth login --profile flow-mobile --browser chrome`

---

## 3. gflow_list_models (через MCP и CLI)

### Image модели (4):
| Название | Метка | Aliases | ref_cap | По умолчанию |
|----------|-------|---------|---------|-------------|
| NARWHAL | Nano Banana 2.1 | nano2, nano2.1, nano-2.1 | 10 | ✓ |
| GEM_PIX_2 | Nano Banana Pro | nano-pro | 10 | |
| IMAGEN_3_5 | Imagen 4 | image4, imagen4 | 3 | |
| HARBOR_SEAL | Nano Banana 2 Lite | nano2-lite | 3 | |

### Video модели (5):
| Название | Метка | Aliases | ref_cap |
|----------|-------|---------|---------|
| omni_flash | N/A | omni-flash | 7 |
| veo_3_1_lite | N/A | veo-lite | 3 |
| veo_3_1_fast | N/A | veo-fast | 3 |
| veo_3_1_quality | N/A | veo-quality | 0 |
| veo_3_1_lite_lower_priority | N/A | veo-lite-lp | 3 |

**Статус:** PASS — модели доступны для просмотра без авторизации.

---

## 4. Kilo MCP → gflow интеграция

| Проверка | Статус |
|----------|--------|
| gflow MCP сервер в `kilo mcp list` | ✓ connected |
| gflow_auth_status через gflow CLI | Работает (показывает неавторизован) |
| gflow_list_models через gflow CLI | Работает (список моделей) |
| `kilo mcp call` команда | Не существует — MCP инструменты вызываются через агентский интерфейс Kilo, а не через `kilo mcp call` |
| gflow MCP tools/list (stdio) | 0 инструментов (особенность сервера) |

**Вывод:** gflow MCP сервер подключён к Kilo, но прямые вызовы инструментов через `kilo mcp call` не поддерживаются этим клиентом. Инструменты gflow доступны через прямое выполнение `gflow` CLI.

---

## 5. Доступность операций генерации (без фактического запуска)

| Операция | Команда | Требует авторизации | Требует кредиты | Статус |
|----------|---------|---------------------|-----------------|--------|
| Image T2I | `gflow image t2i` | Да | Да | Заблокировано |
| Image I2I | `gflow image i2i` | Да | Да | Заблокировано |
| Image batch | `gflow image batch` | Да | Да | Заблокировано |
| Image upscale | `gflow image upscale` | Да | Да | Заблокировано |
| Video T2V | `gflow video t2v` | Да | Да | Заблокировано |
| Video I2V | `gflow video i2v` | Да | Да | Заблокировано |
| Video R2V | `gflow video r2v` | Да | Да | Заблокировано |
| Video chain | `gflow video chain` | Да | Да | Заблокировано |
| Video extend | `gflow video extend` | Да | Да | Заблокировано |
| Video upscale | `gflow video upscale` | Да | Да | Заблокировано |

**gflow credits:** 0 кредитов, профиль заблокирован (`ProfileLockedError` — Chrome держит профиль).

---

## 6. Автономные операции Kilo (без участия человека)

| Операция | Команда | Автономно? | Комментарий |
|----------|---------|------------|-------------|
| Список моделей gflow | `gflow models` | ✅ DA | Не требует auth |
| Документация gflow | `gflow docs` | ✅ DA | Офлайн, read-only |
| Список проектов | `gflow project list` | ✅ DA | Локальный каталог (пуст) |
| Создать проект | `gflow project create` | ✅ DA | Локально, без auth |
| Переименовать проект | `gflow project rename` | ✅ DA | Локально |
| Показать проект | `gflow project show` | ✅ DA | Локально |
| Список медиа | `gflow data list` | ✅ DA | Локальный каталог |
| Метаданные медиа | `gflow data media` | ✅ DA | Локально |
| Синхронизация каталога | `gflow data sync` | ⚠️ Частично | Требует auth для удалённой синхронизации |
| Скачать медиа | `gflow data download` | ⚠️ Частично | Требует auth + media ID |
| Проверить авторизацию | `gflow auth status` | ✅ DA | Read-only, показывает статус |
| Обновить сессию | `gflow auth renew` | ❌ НЕТ | Конфликтует с Chrome, профиль не авторизован |
| Войти в систему | `gflow auth login` | ❌ НЕТ | Требует интерактивного входа |
| Генерация изображения | `gflow image t2i/i2i` | ❌ НЕТ | Требует auth + кредиты (0) |
| Генерация видео | `gflow video t2v/i2v` | ❌ НЕТ | Требует auth + кредиты (0) |
| Проверить кредиты | `gflow credits` | ❌ НЕТ | ProfileLockedError |

---

## 7. Сохранение результатов в OpenMontage

| Механизм | Статус | Детали |
|----------|--------|--------|
| Локальный каталог gflow (`gflow data list`) | ✅ Доступен | Хранится в `/home/vscode/.local/share/gflow-cli/` |
| `gflow data download` | ⚠️ Требует auth | Нужна авторизованная сессия + media ID |
| Запись в рабочее пространство OpenMontage | ✅ Доступно | Файловая система `/workspaces/OpenMontage` доступна для записи |
| Автоматическое сохранение сгенерированного контента | ❌ НЕТ | Генерация заблокирована (нет auth, нет кредитов) |

---

## 8. CDP Input Bridge

Можно отключить — он был нужен только для ручных кликов через noVNC, которые не работают в Chrome из-за блокировки синтетических X11 событий. Для автономной работы он не требуется.

**Процессы для остановки:**
- `input_bridge.py` (порт 8765)
- `http.server` на порту 8766

noVNC (порт 6080) оставляем для просмотра и ручной авторизации.

---

## 8. Итог: что Kilo может делать автономно, а что нет

### ✅ Полностью автономно (без участия человека):

1. **Просмотр списка моделей** — `gflow models` (image + video)
2. **Чтение документации** — `gflow docs` (офлайн)
3. **Управление локальными проектами** — `gflow project list/create/rename/show`
4. **Управление локальным каталогом медиа** — `gflow data list/media/errors/prune`
5. **Проверка статуса авторизации** — `gflow auth status` (read-only)
6. **Запись файлов в OpenMontage** — файловая система доступна для записи

### ❌ Требует ручного участия человека:

1. **Авторизация gflow** — `gflow auth login --profile flow-mobile --browser chrome` (необходимо войти в Google аккаунт)
2. **Обновление сессии** — `gflow auth renew` (конфликтует с запущенным Chrome)
3. **Проверка кредитов** — `gflow credits` (ProfileLockedError из-за Chrome)
4. **Генерация изображений** — `gflow image t2i/i2i/batch/upscale` (нет auth, 0 кредитов)
5. **Генерация видео** — `gflow video t2v/i2v/r2v/chain/extend/upscale` (нет auth, 0 кредитов)
6. **Скачивание сгенерированного контента** — `gflow data download` (требует auth + media ID)

### 🔗 noVNC нужен только для:
- Просмотра экрана Google Flow (порт 6080)
- Ручной авторизации в Google (через Chrome в noVNC)

---

## 9. --no-spend

Соблюдён. Генерация не запускалась, кредиты не потрачены. gflow credits: 0.

---

## 10. Рекомендация

1. Оставить noVNC (порт 6080) для просмотра и ручной авторизации
2. Отключить CDP Input Bridge (порты 8765, 8766) — не нужен для автономной работы
3. Для автономной работы Kilo доступны только только только операции чтения и локального управления проектами
4. Любая генерация требует: (a) ручной вход в Google через gflow auth login, (b) наличие кредитов (сейчас 0)