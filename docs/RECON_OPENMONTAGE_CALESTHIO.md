# RECON_OPENMONTAGE_CALESTHIO — отчёт о разведке чужого репозитория

Источник: https://github.com/calesthio/OpenMontage (склон во временную папку `/tmp/openmontage-recon`, глубина 1, лицензия репозитория AGPL-3.0 — код НЕ копировался в наш репозиторий, отчёт только своими словами).
Статус: read-only разведка, не реализую перенос сам на этом этапе.

## А. SVG-риг → GSAP-таймлайн → Remotion + headless Chromium

### Где найдено
- `.agents/skills/svg-character-animation/SKILL.md` — контракт анимации SVG-рига.
- `tools/character/character_animation.py` — реализация рендера (BuildTool `character_animation`, ~40 KB).
- `skills/pipelines/character-animation/*` — директора конвейера (asset, character-design, compose, edit, executive-producer, proposal, research, rig-plan, scene, script).

### Как биндится SVG-риг к GSAP-таймлайну
1. **Повороты через `svgOrigin` (стабильные пивоты), а не через layout.** Каждая движущаяся часть SVG получает свой пивот: например, `.head` → `svgOrigin: "320 320"`, `.arm-right` → `"385 360"`, `.arm-left` → `"255 360"`. GSAP анимирует только трансформации (`x`, `y`, `scale`, `rotation`), nunca свойства компоновки.
2. **Паузированный таймлайн:** `gsap.timeline({ paused: true })`. Наполняется `tl.set(...)` для пивотов на t=0 и `tl.to(...)` / `tl.from(...)` для acting-битов с `repeat`/`yoyo` (моргание, поворот головы, махи рукой, дыхание).
3. **Привязка к кадру Remotion:** GSAP НЕ крутится через `requestAnimationFrame`. Таймлайн управляется с текущего кадра Remotion:
   ```tsx
   const frame = useCurrentFrame();
   const progress = frame / durationInFrames;
   timeline.progress(progress);
   ```
   То есть один GSAP-таймлайн на всю сцену, а Remotion просто прокручивает его progress от 0 до 1 по ходу проигрывания кадров.
4. **GSAP подключается с CDN:** `<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>` (в hyperframes-шаблоне) и `gsap@3.12.5` в более старой вариации.
5. **Рендер через headless Chromium (Playwright):** `tools/character/character_animation.py` открывает предварительный HTML-композит через `sync_playwright()`, снимает Opening/Middle/End кадры, проверяет консольные ошибки, видимость персонажей и дельты кадров (движение есть vs заморозка). Превью — только QA/отладочный артефакт, не путь рендера.
6. **Итоговый рендер:** через общий стек `video_compose` (Remotion / HyperFrames / FFmpeg), финальный MP4 в `projects/<project>/renders/final.mp4`.

## Б. Алгоритм «slideshow risk score» (6 параметров)

### Где найдено
- `lib/slideshow_risk.py` — функция `score_slideshow_risk(scenes, edit_decisions, renderer_family, render_runtime)`.
- Вызывается из `tools/video/video_compose.py`, метод `_pre_compose_validation`.

### Суть
Оценивает видеоплан по 6尺度м (каждая 0–5, меньше — лучше):

| # | Параметр | Что mierит |
|---|----------|------------|
| 1 | **repetition** | Повторение типов сцен, описаний, размера плана (>70% одного типа — штраф) |
| 2 | **decorative_visuals** | Сцены без `information_role`, `narrative_role`, `shot_intent` считаются декоративными |
| 3 | **weak_motion** | Камера движется, но без `shot_intent` (произвольное движение) |
| 4 | **weak_shot_intent** | Доля сцен без `shot_intent` (нет причины кадра/ reveal-ритма) |
| 5 | **typography_overreliance** | Доля текстовых/статистических карточек (`text_card`, `stat_card`, `kpi_grid`) |
| 6 | **unsupported_cinematic_claims** | Претензия на "кинематографичность" без `hero_moment`, движения камеры, освещения |

### Вердикты по среднему баллу (0–5)
- < 2.0 — strong (хорошо)
- < 3.0 — acceptable (допустимо)
- < 4.0 — revise (доработать)
- >= 4.0 — fail (как слайд-шоу, compositing блокируется)

## В. Логика pre-compose validation gate

### Где найдено
- `tools/video/video_compose.py`, метод `_pre_compose_validation(edit_decisions, resolved_cuts, scene_plan)`, вызывается в `_render` до старта композиции.

### Что именно проверяет и на основании чего блокирует
1. **Delivery promise violation.** Если в `edit_decisions.metadata.delivery_promise` есть требование движения (например, «не более X% статичных кадров»), валидирует реальные каты через `lib.delivery_promise.DeliveryPromise.validate_cuts(resolved_cuts)`. Нарушение → **BLOCK**.
2. **Slideshow risk score.** Если `score_slideshow_risk(...)` возвращает verdict `fail` (среднее ≥ 4.0) → **BLOCK** с текстом, что план выглядит как слайд-шоу и его нужно переработать перед рендером. Вердикт `revise` → только предупреждение (лог), не блокирует.
3. **Отсутствие renderer_family.** Если в `edit_decisions` нет `renderer_family` (должно быть зафиксировано на этапе proposal и заморожено до compose) → **BLOCK**.

Результат: непустой список блоков → возвращается `ToolResult(success=False, error=...)` и рендер не стартует. Пусто → `None`, рендер продолжается.

## Г. Применимость к нашей архитектуре (SVG Stickman + Remotion)

Наш репозиторий уже содержит:
- `lib/stickman_rig.py` — чистый Python-эмиттер SVG-рига (Риги-профиль, позы, экспрессии, Scene ledger, checkpoint/hash-кэш).
- `remotion-composer/` — Remotion-проект с `Root.tsx`, где зарегистрированы композиции (Explainer, PilotDraft, CinematicRenderer и др.).
- `tools/qa/qc.py`, `tools/illustration/illustration_qc.py`, `tools/qa/release_gate.py` — существующий QC/релиз-гейт.

Что из calesthio/OpenMontage применимо напрямую как идея:
1. **Паузированный GSAP-таймлайн, управляемый прогрессом кадра Remotion** (`frame / durationInFrames → timeline.progress`) — естественно ложится на наш Stickman SVG-риг: каждый пивот partes задаём через `svgOrigin`, весь acting-бит — один `gsap.timeline({ paused: true })`, Remotionだけ прокручивает progress. Это даст 진짜 анимацию конечностей внутри сцены, а не статическую наложку поверх кадра (как у нас сейчас в V2/V3).
2. **Slideshow risk score (6 параметров)** — можно перенести как отдельную QC-функцию в `tools/illustration/illustration_qc.py` или `tools/qa/qc.py`, проверяющую план сцен до генерации/рендера. Пороги и названия размерностей можно отестировать на нашем сценарии.
3. **Pre-compose validation gate** — можно встроить между этапом раскадровки и генерацией ассетов: проверка delivery-promise (доля статичных кадров), slideshow-риск, и обязательность `renderer_family` в edit_decisions. Блокирует переход к рендеру, если scen eplan не проходит.

## Д. Черновой план переноса КАК ИДЕИ (не копипаста)

1. **QC: slideshow risk.** Написать свою реализацию 6-параметровой оценки под нашу схему сцен (не копировать `lib/slideshow_risk.py` дословно, а переписать под наши поля `scene_plan`/`edit_decisions`). Добавить вызов в QC перед рендером; порог fail ≥ 4.0 — блокирует генерацию/рендер.
2. **Pre-compose gate.** Добавить проверку перед переходом от раскадровки к генерации: (a) delivery-promise (доля статичных/движущихся кадров соответствует заявленному типу монтажа), (b) slideshow-риск, (c) `renderer_family` зафиксирован. Нарушение — остановка с сообщением, не silenzioso.
3. **Stickman + Remotion анимация.** Переписать привязку нашего SVG-рига к Remotion: `gsap.timeline({ paused: true })`, пивоты через `svgOrigin` на части Stickman, `progress = frame / durationInFrames`. Рендер превью через Playwright/headless Chromium, финал — через Remotion+FFmpeg (второй рендерер не создаём, по нашему плану).
4. **Никакого копипасты.** Весь код пишется под наши модули (`lib/stickman_rig.py`, `remotion-composer/`, `tools/qa/`), лицензия AGPL-3.0 чужого репозитория не подтягивается.

## Е. Что удалено
Временный клон `/tmp/openmontage-recon` удалён после написания отчёта (выполнено отдельным шагом, см.ниже).

## Статус этапа 0.5
Отчёт написан. Перенос НЕ реализован — жду вашего подтверждения, какие пункты из этого отчёта брать в работу (переход к Этапу 1).
