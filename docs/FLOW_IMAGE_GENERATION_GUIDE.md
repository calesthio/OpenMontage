# Google Flow — генерация изображений (CDP-автоматизация)

## Назначение

Генерация изображений через Google Flow (Nano Banana 2.1) с помощью прямой автоматизации Chrome через DevTools Protocol (CDP). Стандартный CLI `gflow image` не работает из-за несоответствия языкового интерфейса (Flow на русском, селекторы на английском). CDP-скрипт обходит эту проблему.

## Требования

- Google Chrome с профилем gflow, в котором уже выполнен вход в аккаунт Google
- Дистанционная отладка Chrome (`--remote-debugging-port=0`)
- Виртуальный экран Xvfb (для безголевого запуска)

## 1. Подготовка окружения

### Запуск виртуального экрана

```bash
export DISPLAY=:99
Xvfb :99 -screen 0 1280x800x24 &
```

### Запуск Chrome с профилем gflow

```bash
export GFLOW_CHROME_PATH=/opt/google/chrome/chrome
nohup /opt/google/chrome/chrome \
  --user-data-dir=/workspaces/OpenMontage/.gflow/profiles/default \
  --remote-debugging-port=0 \
  --remote-allow-origins=* \
  --no-first-run \
  --no-default-browser-check \
  --disable-blink-features=AutomationControlled \
  --lang=en-US \
  --accept-lang=en-US \
  https://flow.google.com \
  > /tmp/chrome_debug.log 2>&1 &
```

### Получение порта DevTools и page-id

```bash
# Порт DevTools (первая строка файла)
cat /workspaces/OpenMontage/.gflow/profiles/default/DevToolsActivePort

# Page ID для flow.google.com
curl -s http://127.0.0.1:<PORT>/json/list | python3 -c "
import sys,json
data=json.load(sys.stdin)
for t in data:
    if t.get('type')=='page' and 'flow.google.com' in t.get('url',''):
        print(t['id'])
"
```

## 2. Запуск генерации

### Подготовка файла с промптами

Формат: JSON-массив строк. Каждый промпт должен содержать описание стиля и объект.

Пример `prompts.json`:

```json
[
  "photorealistic, cinematic documentary still, deep teal shadows, warm highlights, no text, no logos: cross-section of Europa's icy shell revealing subsurface ocean",
  "photorealistic, cinematic documentary still, deep teal shadows, warm highlights, no text, no logos: Enceladus south pole plume venting into space",
  "photorealistic, cinematic documentary still, deep teal shadows, warm highlights, no text, no logos: hydrothermal vent on ocean floor with mineral chimneys",
  "photorealistic, cinematic documentary still, deep teal shadows, warm highlights, no text, no logos: Europa surface ice cracks and ridges"
]
```

### Запуск скрипта

```bash
python scripts/flow_cdp_image.py \
  --prompts-file prompts.json \
  --out-dir work/flow_images \
  --ws-port <PORT> \
  --page-id <PAGE-ID> \
  --timeout 120 \
  --delay 25
```

Параметры:
- `--prompts-file` — файл со списком промптов (макс. 12)
- `--out-dir` — директория для вывода (рекомендуется `work/flow_images`)
- `--ws-port` — порт DevTools Chrome
- `--page-id` — ID страницы flow.google.com
- `--timeout` — время ожидания генерации в секундах (по умолчанию 120)
- `--delay` — пауза между промптами в секундах (по умолчанию 25, диапазон 20-30)

## 3. Что делает скрипт

1. Подключается к Chrome через CDP WebSocket
2. Закрывает русскоязычные диалоги согласия (ОК, Включить, Отмена и т.д.)
3. Создаёт новый проект ("Новый проект") если нужно
4. Очищает поле ввода и вводит промпт через `Input.insertText` (не JS — фреймворк редактора не видит JS-присваивание)
5. Отправляет запрос через `Input.dispatchKeyEvent Enter` (не JS-клик — фреймворк не всегда регистрирует JS-клики)
6. Ждёт появления НОВЫХ плиток изображений (отслеживает `data-media-id` до и после отправки)
7. Скачивает каждое изображение через `fetch()` в контексте страницы (имеет доступ к куки)
8. Сравнивает пиксельный хеш (16×16 MD5) с уже известными — дубликаты отбрасываются
9. Отбрасывает чёрные кадры (доля чёрных пикселей > 50%)
10. Конвертирует в настоящий PNG через PIL (без ресайза)
11. Записывает запись в `manifests/ai_images.json`

## 4. Проверка результата

Каждое сгенерированное изображение проверяется по:

- **SHA-256** — криптографический хэш файла
- **Пиксельный хеш** — MD5 от reducción до 16×16 (обнаружение дубликатов)
- **Разрешение** — должно быть не менее 1344×768 для 16:9 (генерируется 1376×768)
- **Доля чёрных пикселей** — не более 50% (чёрные кадры отбрасываются)
- **Формат** — PNG (конвертируется через PIL из WebP, полученного от Flow)

Пример проверки:

```bash
python3 -c "
from PIL import Image
import hashlib, os
im = Image.open('work/flow_images/<тема>_<n>.png')
print(f'Size: {im.size}, Mode: {im.mode}, Format: {im.format}')
with open('work/flow_images/<тема>_<n>.png', 'rb') as f:
    print(f'SHA-256: {hashlib.sha256(f.read()).hexdigest()}')
"
```

## 5. Лимиты

- **Не более 8 генераций за один запуск** (скрытая дневная квота изображений Flow)
- **Не более 12 промптов в одном файле**
- **Пауза 20-30 секунд между промптами**
- **Veo/видео не используются**
- **Публикация не выполняется** — только владелец аккаунта может публиковать

## 6. Права и маркировка

Все сгенерированные изображения помечаются как:

- `visual_class: AI_RECONSTRUCTION`
- `visual_claim: AI_RECONSTRUCTION`
- `disclosure_required: true`
- `labels: ["AI-generated visualization"]`

В манифесте `manifests/ai_images.json` каждая запись содержит полные метаданные включая `sha256`, `phash`, `file_size_bytes`, `display_width`, `display_height`, `created_at`.

## 7. Остановка сервисов

После завершения генерации:

```bash
pkill -f "chrome.*gflow/profiles/default" 2>/dev/null || true
pkill -f "Xvfb :99" 2>/dev/null || true
pkill -f "x11vnc -display :99" 2>/dev/null || true
pkill -f "websockify.*6080" 2>/dev/null || true
```

## 8. Неполадки и их решение

### Русский интерфейса Flow

gflow v1.3.0 ищет английские селекторы (`new project`, `Start generation`), но Flow отображается на русском. CDP-скрипт использует русские надписи («Новый проект», «Начать генерацию») для работы с интерфейсом.

### Ввод промпта через CDP

Редактор Flow построен на фреймворке, который не видит программые присваивания через JS (`pb.textContent = ...`). Используется `CDP Input.insertText`, который реально вводит текст в focussed поле.

### Отправка промпта

JS-клик на кнопку «Начать генерацию» не всегда регистрируется фреймворком. Используется `CDP Input.dispatchKeyEvent Enter` — нажатие клавиши Enter в focussed поле.

### Дубликаты и чёрные кадры

Скрипт отслеживает `data-media-id` плиток до и после отправки промпта, скачивает только НОВЫЕ изображения. Каждое изображение проверяется на пиксельный хеш (дубликаты отбрасываются) и долю чёрных пикселей (чёрные кадры отбрасываются).

### "Login required"

Если сессия слетела (Chrome был перезапущен без сохранения профиля), нужно снова войти в Google через браузер с профилем `.gflow/profiles/default`. При необходимости использовать VNC (порт 6081) для ручного входа:

```bash
x11vnc -display :99 -localhost -forever -shared -nopw &
websockify --web /usr/share/novnc 6081 localhost:5900 &
```
Ссылка: `https://${CODESPACE_NAME}-6081.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}/vnc.html?autoconnect=1&resize=scale`

## 9. Пример результата

Манифест `manifests/ai_images.json` содержит записи вида:

```json
{
  "asset_id": "f2a971ff",
  "prompt": "photorealistic, cinematic documentary still, deep teal shadows, warm highlights, no text, no logos: cross-section of Europa's icy shell revealing subsurface ocean",
  "model": "Nano Banana 2.1",
  "source_type": "newly_generated",
  "asset_origin": "newly_generated",
  "provider": "google-flow",
  "file_path": "work/flow_images/europa_cross_section_1.png",
  "file_size_bytes": 1297278,
  "sha256": "f2a971fffde015fc...",
  "phash": "63cecb9d2848",
  "display_width": 1376,
  "display_height": 768,
  "visual_class": "AI_RECONSTRUCTION",
  "visual_claim": "AI_RECONSTRUCTION",
  "disclosure_required": true,
  "created_at": "2026-11-10T02:41:11Z",
  "labels": ["AI-generated visualization"]
}
```

## 10. Архив

Все сгенерированные изображения архивируются:

```bash
tar czf ~/backups/flow_images_2026-11-10.tar.gz -C work flow_images
```
