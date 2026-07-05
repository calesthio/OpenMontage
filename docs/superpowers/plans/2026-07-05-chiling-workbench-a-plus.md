# Chiling Workbench A+ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the existing Chiling static Web workbench stable while modularizing the frontend, preserving Worker/API behavior, and improving second-development ergonomics.

**Architecture:** Keep `web/chiling-workbench` buildless and browser-native. Extract pure helpers, state construction, API-facing actions, reusable render components, and page views into ES modules under `web/chiling-workbench/src/`, while keeping `worker.py`, `api-client.js`, and documented API contracts intact.

**Tech Stack:** Static HTML, browser ES modules, plain JavaScript, CSS, Python contract tests, Node built-in test runner, existing local Worker.

**Non-goal:** No React/Vite migration in this implementation plan; that remains a future option after the static workbench is stable and modular.

---

## File Structure

Create these frontend module files:

- `web/chiling-workbench/src/format.js`: pure formatting and escaping helpers.
- `web/chiling-workbench/src/task-model.js`: pure task/status/stage derivation helpers.
- `web/chiling-workbench/src/state.js`: initial state factory and form defaults.
- `web/chiling-workbench/src/dom.js`: DOM query helpers and event delegation helpers.
- `web/chiling-workbench/src/components/topbar.js`: top navigation renderer.
- `web/chiling-workbench/src/components/ui.js`: shared buttons, panels, metrics, pills, media previews, and status rows.
- `web/chiling-workbench/src/views/login.js`: login page renderer.
- `web/chiling-workbench/src/views/dashboard.js`: production dashboard renderer.
- `web/chiling-workbench/src/views/create.js`: create-work page renderer.
- `web/chiling-workbench/src/views/review.js`: team review page renderer.
- `web/chiling-workbench/src/views/generating.js`: generation feedback renderer.
- `web/chiling-workbench/src/views/delivery.js`: delivery page renderer.
- `web/chiling-workbench/src/views/admin.js`: works, library, and data/admin renderers.
- `web/chiling-workbench/src/views/detail-drawer.js`: task detail drawer renderer.

Keep these existing files:

- `web/chiling-workbench/index.html`: app shell and script order.
- `web/chiling-workbench/app.js`: app bootstrap, routing, actions, polling, and render composition during the migration.
- `web/chiling-workbench/api-client.js`: API/localStorage adapter.
- `web/chiling-workbench/styles.css`: single CSS entrypoint, reorganized into sections.
- `web/chiling-workbench/worker.py`: local Worker/API bridge.

Add these tests:

- `web/chiling-workbench/tests/format.test.mjs`: Node tests for pure formatting helpers.
- `web/chiling-workbench/tests/task-model.test.mjs`: Node tests for task derivation helpers.
- `web/chiling-workbench/tests/state.test.mjs`: Node tests for initial state and form defaults.
- `tests/scripts/test_chiling_workbench_module_contract.py`: Python contract checks for module boundaries, safe UI copy, CSS organization, and script loading.

---

### Task 1: Add Pure Helper Modules With Tests

**Files:**
- Create: `web/chiling-workbench/tests/format.test.mjs`
- Create: `web/chiling-workbench/tests/task-model.test.mjs`
- Create: `web/chiling-workbench/src/format.js`
- Create: `web/chiling-workbench/src/task-model.js`
- Modify: `web/chiling-workbench/app.js`

- [ ] **Step 1: Write the failing format helper test**

Create `web/chiling-workbench/tests/format.test.mjs`:

```js
import test from "node:test";
import assert from "node:assert/strict";

import {
  clampNumber,
  escapeHtml,
  lineBreaks,
  normalizeSubtitleText,
  formatRelativeTime,
} from "../src/format.js";

test("clampNumber clamps invalid and out-of-range input", () => {
  assert.equal(clampNumber("20", 1, 15), 15);
  assert.equal(clampNumber("-2", 1, 15), 1);
  assert.equal(clampNumber("abc", 1, 15), 1);
});

test("escapeHtml escapes user-controlled content", () => {
  assert.equal(
    escapeHtml("<img src=x onerror=alert(1)> & 'quote'"),
    "&lt;img src=x onerror=alert(1)&gt; &amp; &#039;quote&#039;",
  );
});

test("lineBreaks escapes text before adding break tags", () => {
  assert.equal(lineBreaks("第一句\n<script>"), "第一句<br />&lt;script&gt;");
});

test("normalizeSubtitleText removes short-video subtitle punctuation", () => {
  assert.equal(normalizeSubtitleText("第一句。\n第二句，\n第三句!"), "第一句\n第二句\n第三句");
});

test("formatRelativeTime returns stable Chinese labels", () => {
  const now = 1_700_000_000_000;
  assert.equal(formatRelativeTime(now - 30_000, now), "刚刚");
  assert.equal(formatRelativeTime(now - 180_000, now), "3分钟前");
});
```

- [ ] **Step 2: Write the failing task model test**

Create `web/chiling-workbench/tests/task-model.test.mjs`:

```js
import test from "node:test";
import assert from "node:assert/strict";

import {
  deriveStageList,
  taskStatusLabel,
  defaultDeliverables,
  getTaskTitle,
} from "../src/task-model.js";

test("deriveStageList maps progress to done active and waiting stages", () => {
  const stages = deriveStageList({ progress: 64 });
  assert.deepEqual(
    stages.map((stage) => [stage.name, stage.state]),
    [
      ["解析参考", "done"],
      ["整理文案", "done"],
      ["生成画面", "active"],
      ["合成字幕", "waiting"],
      ["质检交付", "waiting"],
    ],
  );
});

test("taskStatusLabel keeps user-safe production labels", () => {
  assert.equal(taskStatusLabel({ status: "completed" }), "已交付");
  assert.equal(taskStatusLabel({ status: "processing" }), "生产中");
  assert.equal(taskStatusLabel({ status: "queued" }), "排队中");
  assert.equal(taskStatusLabel({ status: "failed" }), "处理失败");
});

test("defaultDeliverables never exposes provider or internal pipeline names", () => {
  const deliverables = defaultDeliverables({ resolution: "480p" });
  const serialized = JSON.stringify(deliverables);
  assert.match(serialized, /成片文件/);
  assert.doesNotMatch(serialized, /RUNNINGHUB|DOUBAO|reference-video-analysis|seedance/i);
});

test("getTaskTitle uses safe business-facing titles", () => {
  assert.equal(getTaskTitle({ referenceUrl: "https://example.test/video" }), "参考视频复刻");
  assert.equal(getTaskTitle({ script: "第一句口播\n第二句" }), "第一句口播 · 口播复刻");
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
node --test web/chiling-workbench/tests/format.test.mjs web/chiling-workbench/tests/task-model.test.mjs
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/format.js` and `src/task-model.js`.

- [ ] **Step 4: Implement `src/format.js`**

Create `web/chiling-workbench/src/format.js`:

```js
export function clampNumber(number, min, max) {
  return Math.min(Math.max(Number(number) || min, min), max);
}

export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function lineBreaks(value) {
  return escapeHtml(value).replaceAll("\n", "<br />");
}

export function normalizeSubtitleText(text) {
  return String(text || "")
    .split("\n")
    .map((line) => line.trim().replace(/[，。！？、,.!?]+$/u, ""))
    .filter(Boolean)
    .join("\n");
}

export function formatRelativeTime(timestamp, now = Date.now()) {
  if (!timestamp) return "刚刚";
  const seconds = Math.max(0, Math.round((now - Number(timestamp)) / 1000));
  if (seconds < 60) return "刚刚";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}分钟前`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}小时前`;
  const days = Math.round(hours / 24);
  return `${days}天前`;
}
```

- [ ] **Step 5: Implement `src/task-model.js`**

Create `web/chiling-workbench/src/task-model.js`:

```js
const STAGE_NAMES = ["解析参考", "整理文案", "生成画面", "合成字幕", "质检交付"];
const STAGE_THRESHOLDS = [15, 34, 76, 92, 100];

function stageState(progress, index) {
  const start = index === 0 ? 0 : STAGE_THRESHOLDS[index - 1];
  const end = STAGE_THRESHOLDS[index];

  if (progress >= end) return "done";
  if (progress >= start) return "active";
  return "waiting";
}

export function deriveStageList(task = {}) {
  const progress = Number(task.progress || 0);
  return STAGE_NAMES.map((name, index) => {
    const state = stageState(progress, index);
    return {
      name,
      state,
      detail: state === "done" ? "完成" : state === "active" ? `${progress}%` : index === 4 ? "预计数分钟" : "等待",
    };
  });
}

export function taskStatusLabel(task = {}) {
  if (task.status === "completed") return "已交付";
  if (task.status === "processing") return "生产中";
  if (task.status === "queued") return "排队中";
  if (task.status === "failed") return "处理失败";
  return "待处理";
}

export function defaultDeliverables(payload = {}) {
  const resolution = payload.resolution || "480p";
  return [
    { title: "成片文件", subtitle: `${resolution} 视频，可直接发布`, action: "下载视频", url: "#" },
    { title: "字幕文件", subtitle: "可二次校对和归档", action: "下载字幕", url: "#" },
    { title: "审核记录", subtitle: "留存素材授权与审核意见", action: "查看记录", url: "#" },
  ];
}

export function getTaskTitle(payload = {}) {
  const scriptFirstLine = String(payload.script || "")
    .split("\n")
    .map((line) => line.trim())
    .find(Boolean);

  if (payload.referenceUrl) return "参考视频复刻";
  return scriptFirstLine ? `${scriptFirstLine.slice(0, 8)} · 口播复刻` : "新建口播复刻";
}
```

- [ ] **Step 6: Replace duplicate helper functions in `app.js`**

Modify the top of `web/chiling-workbench/app.js` to import helpers:

```js
import {
  clampNumber,
  escapeHtml,
  lineBreaks,
  normalizeSubtitleText,
  formatRelativeTime,
} from "./src/format.js";
import {
  defaultDeliverables,
  taskStatusLabel,
} from "./src/task-model.js";
```

Then remove the existing local definitions of `clamp`, `escapeHtml`, `lineBreaks`, `normalizeSubtitleText`, `formatRelativeTime`, `defaultDeliverables`, and `taskStatusLabel`. Replace calls to `clamp(...)` with `clampNumber(...)`.

- [ ] **Step 7: Load `app.js` as a browser module**

Modify `web/chiling-workbench/index.html`:

```html
<script src="./config.js" defer></script>
<script src="./api-client.js" defer></script>
<script src="./app.js" type="module"></script>
```

- [ ] **Step 8: Run tests and syntax checks**

Run:

```bash
node --test web/chiling-workbench/tests/format.test.mjs web/chiling-workbench/tests/task-model.test.mjs
.venv/bin/python -m pytest tests/scripts/test_chiling_frontend_queue_contract.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add web/chiling-workbench/index.html web/chiling-workbench/app.js web/chiling-workbench/src/format.js web/chiling-workbench/src/task-model.js web/chiling-workbench/tests/format.test.mjs web/chiling-workbench/tests/task-model.test.mjs
git commit -m "Modularize Chiling workbench pure helpers"
```

---

### Task 2: Extract Initial State and Form Defaults

**Files:**
- Create: `web/chiling-workbench/tests/state.test.mjs`
- Create: `web/chiling-workbench/src/state.js`
- Modify: `web/chiling-workbench/app.js`

- [ ] **Step 1: Write the failing state test**

Create `web/chiling-workbench/tests/state.test.mjs`:

```js
import test from "node:test";
import assert from "node:assert/strict";

import { createInitialState, createDefaultForm } from "../src/state.js";

test("createDefaultForm returns safe editable production defaults", () => {
  const form = createDefaultForm({
    referenceFrame: "./assets/reference-frame.png",
    portraitFrame: "./assets/portrait.png",
  });

  assert.equal(form.duration, 15);
  assert.equal(form.resolution, "480p");
  assert.equal(form.count, 1);
  assert.equal(form.subtitleStyle, "short");
  assert.equal(form.referencePreview, "./assets/reference-frame.png");
  assert.equal(form.portraitPreview, "./assets/portrait.png");
  assert.match(form.script, /不妨留个关注/);
});

test("createInitialState preserves current task id from storage", () => {
  const storage = new Map([["chiling-workbench.current-task-id", "task_123"]]);
  const state = createInitialState({
    storage: { getItem: (key) => storage.get(key) || "" },
    referenceFrame: "./ref.png",
    portraitFrame: "./portrait.png",
  });

  assert.equal(state.loggedIn, false);
  assert.equal(state.page, "login");
  assert.equal(state.currentTaskId, "task_123");
  assert.deepEqual(state.tasks, []);
  assert.equal(state.detailDrawerOpen, false);
  assert.equal(state.form.referencePreview, "./ref.png");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
node --test web/chiling-workbench/tests/state.test.mjs
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/state.js`.

- [ ] **Step 3: Implement `src/state.js`**

Create `web/chiling-workbench/src/state.js`:

```js
export function createDefaultForm({ referenceFrame, portraitFrame }) {
  return {
    referenceUrl: "",
    duration: 15,
    resolution: "480p",
    count: 1,
    subtitleStyle: "short",
    referenceName: "参考视频已就绪",
    portraitName: "肖像图已就绪",
    referencePreview: referenceFrame,
    portraitPreview: portraitFrame,
    analysisSummary: "等待参考解析后生成摘要。",
    script:
      "在这些案子上面\n我积累了充足的实战经验\n如果你身边刚好缺一位靠谱律师朋友\n不妨留个关注",
  };
}

export function createInitialState({ storage, referenceFrame, portraitFrame }) {
  return {
    loggedIn: false,
    page: "login",
    progress: 0,
    taskPoller: null,
    currentTaskId: storage.getItem("chiling-workbench.current-task-id") || "",
    currentTask: null,
    deliverables: [],
    tasks: [],
    queueEntries: [],
    productionRequests: [],
    productionServiceStatus: null,
    productionServiceConfiguration: null,
    productionAuditLog: null,
    taskDetail: null,
    detailDrawerOpen: false,
    operationPanel: null,
    reviewDraft: null,
    productionPrep: null,
    generationPhrase: "",
    productionRequestPhrase: "",
    isSubmitting: false,
    form: createDefaultForm({ referenceFrame, portraitFrame }),
  };
}
```

- [ ] **Step 4: Use `createInitialState` in `app.js`**

Modify the top of `web/chiling-workbench/app.js`:

```js
import { createInitialState } from "./src/state.js";
```

Replace the inline `const state = { ... }` block with:

```js
const state = createInitialState({
  storage: window.localStorage,
  referenceFrame,
  portraitFrame,
});
```

- [ ] **Step 5: Run tests**

Run:

```bash
node --test web/chiling-workbench/tests/state.test.mjs web/chiling-workbench/tests/format.test.mjs web/chiling-workbench/tests/task-model.test.mjs
.venv/bin/python -m pytest tests/scripts/test_chiling_frontend_queue_contract.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/chiling-workbench/app.js web/chiling-workbench/src/state.js web/chiling-workbench/tests/state.test.mjs
git commit -m "Extract Chiling workbench state defaults"
```

---

### Task 3: Add Module Boundary Contract Tests

**Files:**
- Create: `tests/scripts/test_chiling_workbench_module_contract.py`
- Modify: `web/chiling-workbench/app.js`
- Modify: `web/chiling-workbench/index.html`

- [ ] **Step 1: Write the failing module contract test**

Create `tests/scripts/test_chiling_workbench_module_contract.py`:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKBENCH = ROOT / "web" / "chiling-workbench"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_chiling_workbench_uses_browser_modules_for_app_code():
    index = read(WORKBENCH / "index.html")
    app = read(WORKBENCH / "app.js")

    assert '<script src="./app.js" type="module"></script>' in index
    assert 'from "./src/format.js"' in app
    assert 'from "./src/task-model.js"' in app
    assert 'from "./src/state.js"' in app


def test_chiling_workbench_keeps_user_safe_frontend_boundaries():
    source = "\n".join(
        read(path)
        for path in [
            WORKBENCH / "app.js",
            WORKBENCH / "src" / "format.js",
            WORKBENCH / "src" / "task-model.js",
            WORKBENCH / "src" / "state.js",
        ]
    )

    assert "RUNNINGHUB" not in source
    assert "DOUBAO" not in source
    assert "ARK_API_KEY" not in source
    assert "CHILING_PRODUCTION_SERVICE" not in source
    assert "reference-video-analysis" not in source
```

- [ ] **Step 2: Run test to verify it fails or passes for the current migration state**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_workbench_module_contract.py -q
```

Expected after Tasks 1 and 2: PASS. If it fails, fix the exact boundary named by the assertion before continuing.

- [ ] **Step 3: Add the new test to focused verification commands**

Document this command in the task notes for future execution:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_frontend_queue_contract.py tests/scripts/test_chiling_workbench_module_contract.py -q
```

- [ ] **Step 4: Commit**

```bash
git add tests/scripts/test_chiling_workbench_module_contract.py
git commit -m "Add Chiling workbench module contract tests"
```

---

### Task 4: Extract Shared Components

**Files:**
- Create: `web/chiling-workbench/src/components/ui.js`
- Create: `web/chiling-workbench/src/components/topbar.js`
- Modify: `web/chiling-workbench/app.js`
- Modify: `tests/scripts/test_chiling_workbench_module_contract.py`

- [ ] **Step 1: Extend the contract test for component modules**

Modify `tests/scripts/test_chiling_workbench_module_contract.py`:

```python
def test_chiling_workbench_has_shared_component_modules():
    app = read(WORKBENCH / "app.js")
    ui = read(WORKBENCH / "src" / "components" / "ui.js")
    topbar = read(WORKBENCH / "src" / "components" / "topbar.js")

    assert 'from "./src/components/ui.js"' in app
    assert 'from "./src/components/topbar.js"' in app
    assert "export function button" in ui
    assert "export function panel" in ui
    assert "export function phonePreview" in ui
    assert "export function metric" in ui
    assert "export function renderTopbar" in topbar
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_workbench_module_contract.py::test_chiling_workbench_has_shared_component_modules -q
```

Expected: FAIL because component modules do not exist.

- [ ] **Step 3: Create `src/components/ui.js`**

Create `web/chiling-workbench/src/components/ui.js`:

```js
import { escapeHtml } from "../format.js";

export function button(label, { variant = "secondary", attrs = "" } = {}) {
  const variantClass = variant === "primary" ? "button--primary" : variant === "small" ? "button--small" : "";
  return `<button class="button ${variantClass}" ${attrs}>${escapeHtml(label)}</button>`;
}

export function panel(content, { className = "", title = "" } = {}) {
  const heading = title ? `<h2 class="section-title">${escapeHtml(title)}</h2>` : "";
  return `<section class="panel ${className}">${heading}${content}</section>`;
}

export function phonePreview(image, label, modifier = "") {
  return `
    <div class="phone ${modifier}">
      <img src="${escapeHtml(image)}" alt="${escapeHtml(label)}" />
      <span>${escapeHtml(label)}</span>
    </div>
  `;
}

export function metric(label, value, helper) {
  return `
    <div class="metric">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(helper)}</small>
    </div>
  `;
}

export function pill(label, className = "") {
  return `<span class="pill ${className}">${escapeHtml(label)}</span>`;
}
```

- [ ] **Step 4: Create `src/components/topbar.js`**

Create `web/chiling-workbench/src/components/topbar.js`:

```js
import { escapeHtml } from "../format.js";

export function renderTopbar({ pages, activePage }) {
  const nav = pages
    .map((page) => {
      const activeClass = page.id === activePage ? "is-active" : "";
      return `<button class="nav__item ${activeClass}" data-nav="${escapeHtml(page.id)}">${escapeHtml(page.label)}</button>`;
    })
    .join("");

  return `
    <header class="topbar">
      <div class="brand">
        <strong class="brand__name">赤灵AI运营工作台</strong>
        <span class="brand__tagline">内容复刻 · 审核 · 交付</span>
      </div>
      <nav class="nav" aria-label="主导航">${nav}</nav>
      <div class="topbar__spacer"></div>
      <button class="button button--primary" data-nav="create">新建</button>
    </header>
  `;
}
```

- [ ] **Step 5: Import components in `app.js` and replace local helpers gradually**

Modify `web/chiling-workbench/app.js`:

```js
import { button, metric, panel, phonePreview, pill } from "./src/components/ui.js";
import { renderTopbar } from "./src/components/topbar.js";
```

Update `shell(content, activePage = state.page)` to call `renderTopbar({ pages, activePage })` instead of building topbar markup inline.

Do not replace every local helper in this task. Replace only `shell` and the local `phonePreview` helper first, then run tests.

- [ ] **Step 6: Run tests**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_workbench_module_contract.py tests/scripts/test_chiling_frontend_queue_contract.py -q
node --test web/chiling-workbench/tests/format.test.mjs web/chiling-workbench/tests/task-model.test.mjs web/chiling-workbench/tests/state.test.mjs
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add web/chiling-workbench/app.js web/chiling-workbench/src/components/ui.js web/chiling-workbench/src/components/topbar.js tests/scripts/test_chiling_workbench_module_contract.py
git commit -m "Extract Chiling workbench shared components"
```

---

### Task 5: Extract DOM Event Helpers

**Files:**
- Create: `web/chiling-workbench/src/dom.js`
- Modify: `web/chiling-workbench/app.js`
- Modify: `tests/scripts/test_chiling_workbench_module_contract.py`

- [ ] **Step 1: Extend module contract test for DOM helpers**

Add to `tests/scripts/test_chiling_workbench_module_contract.py`:

```python
def test_chiling_workbench_dom_helper_module_exists():
    app = read(WORKBENCH / "app.js")
    dom = read(WORKBENCH / "src" / "dom.js")

    assert 'from "./src/dom.js"' in app
    assert "export function find" in dom
    assert "export function findAll" in dom
    assert "export function bindDelegatedClick" in dom
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_workbench_module_contract.py::test_chiling_workbench_dom_helper_module_exists -q
```

Expected: FAIL because `src/dom.js` does not exist.

- [ ] **Step 3: Create `src/dom.js`**

Create `web/chiling-workbench/src/dom.js`:

```js
export function find(root, selector) {
  return root.querySelector(selector);
}

export function findAll(root, selector) {
  return Array.from(root.querySelectorAll(selector));
}

export function bindDelegatedClick(root, selector, handler) {
  root.addEventListener("click", (event) => {
    const target = event.target.closest(selector);
    if (!target || !root.contains(target)) return;
    handler(event, target);
  });
}
```

- [ ] **Step 4: Import DOM helpers in `app.js`**

Modify `web/chiling-workbench/app.js`:

```js
import { bindDelegatedClick, find, findAll } from "./src/dom.js";
```

Replace straightforward `document.querySelector(...)` and `document.querySelectorAll(...)` calls inside `bindEvents()` with `find(document, ...)` and `findAll(document, ...)`. Keep behavior identical in this task.

- [ ] **Step 5: Run tests**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_workbench_module_contract.py tests/scripts/test_chiling_frontend_queue_contract.py -q
node --test web/chiling-workbench/tests/*.test.mjs
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/chiling-workbench/app.js web/chiling-workbench/src/dom.js tests/scripts/test_chiling_workbench_module_contract.py
git commit -m "Extract Chiling workbench DOM helpers"
```

---

### Task 6: Extract Page Views in Two Safe Batches

**Files:**
- Create: `web/chiling-workbench/src/views/login.js`
- Create: `web/chiling-workbench/src/views/dashboard.js`
- Create: `web/chiling-workbench/src/views/create.js`
- Create: `web/chiling-workbench/src/views/review.js`
- Create: `web/chiling-workbench/src/views/generating.js`
- Create: `web/chiling-workbench/src/views/delivery.js`
- Create: `web/chiling-workbench/src/views/admin.js`
- Create: `web/chiling-workbench/src/views/detail-drawer.js`
- Modify: `web/chiling-workbench/app.js`
- Modify: `tests/scripts/test_chiling_workbench_module_contract.py`

- [ ] **Step 1: Extend contract test for primary view modules**

Add to `tests/scripts/test_chiling_workbench_module_contract.py`:

```python
def test_chiling_workbench_primary_view_modules_exist():
    app = read(WORKBENCH / "app.js")

    for module_name in ["login", "dashboard", "create"]:
        path = WORKBENCH / "src" / "views" / f"{module_name}.js"
        assert path.is_file(), module_name
        assert f'from "./src/views/{module_name}.js"' in app
        assert "export function render" in read(path)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_workbench_module_contract.py::test_chiling_workbench_primary_view_modules_exist -q
```

Expected: FAIL because primary view modules do not exist.

- [ ] **Step 3: Extract login/dashboard/create renderers**

Create each primary view module with this shape:

```js
import { escapeHtml, lineBreaks } from "../format.js";
import { phonePreview, metric, pill } from "../components/ui.js";

export function render({ state }) {
  return `
    <!-- move the existing page markup here with state passed explicitly -->
  `;
}
```

Move the current bodies of `renderLogin`, `renderDashboard`, and `renderCreate` from `app.js` into:

- `web/chiling-workbench/src/views/login.js`
- `web/chiling-workbench/src/views/dashboard.js`
- `web/chiling-workbench/src/views/create.js`

Replace app imports:

```js
import { render as renderLoginView } from "./src/views/login.js";
import { render as renderDashboardView } from "./src/views/dashboard.js";
import { render as renderCreateView } from "./src/views/create.js";
```

Replace the old functions in `app.js`:

```js
function renderLogin() {
  return renderLoginView({ state });
}

function renderDashboard() {
  return shell(renderDashboardView({ state }), "dashboard");
}

function renderCreate() {
  return shell(renderCreateView({ state }), "create");
}
```

- [ ] **Step 4: Run tests after primary view extraction**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_workbench_module_contract.py tests/scripts/test_chiling_frontend_queue_contract.py -q
node --test web/chiling-workbench/tests/*.test.mjs
```

Expected: PASS.

- [ ] **Step 5: Commit primary view extraction**

```bash
git add web/chiling-workbench/app.js web/chiling-workbench/src/views/login.js web/chiling-workbench/src/views/dashboard.js web/chiling-workbench/src/views/create.js tests/scripts/test_chiling_workbench_module_contract.py
git commit -m "Extract Chiling workbench primary views"
```

- [ ] **Step 6: Extend contract test for workflow/admin view modules**

Add to `tests/scripts/test_chiling_workbench_module_contract.py`:

```python
def test_chiling_workbench_workflow_view_modules_exist():
    app = read(WORKBENCH / "app.js")

    for module_name in ["review", "generating", "delivery", "admin", "detail-drawer"]:
        path = WORKBENCH / "src" / "views" / f"{module_name}.js"
        assert path.is_file(), module_name
        assert "export function render" in read(path)

    assert 'from "./src/views/review.js"' in app
    assert 'from "./src/views/generating.js"' in app
    assert 'from "./src/views/delivery.js"' in app
    assert 'from "./src/views/admin.js"' in app
    assert 'from "./src/views/detail-drawer.js"' in app
```

- [ ] **Step 7: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_workbench_module_contract.py::test_chiling_workbench_workflow_view_modules_exist -q
```

Expected: FAIL because workflow/admin view modules do not exist.

- [ ] **Step 8: Extract workflow and admin views**

Move these current render functions from `app.js`:

- `renderReview` into `src/views/review.js`
- `renderGenerating` into `src/views/generating.js`
- `renderDelivery` into `src/views/delivery.js`
- `renderWorks`, `renderLibrary`, `renderData`, `renderProductionAuditLogPanel`, and `renderProductionServiceConfigurationPanel` into `src/views/admin.js`
- `renderTaskDetailDrawer` and `renderTaskDetailSection` into `src/views/detail-drawer.js`

Use the same adapter pattern as primary views:

```js
function renderReview() {
  return shell(renderReviewView({ state }), "review");
}
```

Keep action functions and polling in `app.js` during this task.

- [ ] **Step 9: Run tests after workflow/admin view extraction**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_workbench_module_contract.py tests/scripts/test_chiling_frontend_queue_contract.py -q
node --test web/chiling-workbench/tests/*.test.mjs
```

Expected: PASS.

- [ ] **Step 10: Commit workflow/admin view extraction**

```bash
git add web/chiling-workbench/app.js web/chiling-workbench/src/views tests/scripts/test_chiling_workbench_module_contract.py
git commit -m "Extract Chiling workbench workflow views"
```

---

### Task 7: Extract Actions and Polling Boundaries

**Files:**
- Create: `web/chiling-workbench/src/actions.js`
- Create: `web/chiling-workbench/src/polling.js`
- Modify: `web/chiling-workbench/app.js`
- Modify: `tests/scripts/test_chiling_workbench_module_contract.py`

- [ ] **Step 1: Extend module contract test for action boundaries**

Add to `tests/scripts/test_chiling_workbench_module_contract.py`:

```python
def test_chiling_workbench_action_and_polling_modules_exist():
    app = read(WORKBENCH / "app.js")
    actions = read(WORKBENCH / "src" / "actions.js")
    polling = read(WORKBENCH / "src" / "polling.js")

    assert 'from "./src/actions.js"' in app
    assert 'from "./src/polling.js"' in app
    assert "export function createActions" in actions
    assert "export function createPollingController" in polling
    assert "window.ChilingTaskApi" not in polling
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_workbench_module_contract.py::test_chiling_workbench_action_and_polling_modules_exist -q
```

Expected: FAIL because `actions.js` and `polling.js` do not exist.

- [ ] **Step 3: Create `src/actions.js` with dependency injection**

Create `web/chiling-workbench/src/actions.js`:

```js
import { normalizeSubtitleText } from "./format.js";

export function createActions({ state, api, storage, render, showToast, refresh }) {
  function buildTaskPayload() {
    return {
      referenceUrl: state.form.referenceUrl,
      duration: state.form.duration,
      resolution: state.form.resolution,
      count: state.form.count,
      subtitleStyle: state.form.subtitleStyle,
      script: normalizeSubtitleText(state.form.script),
      analysisSummary: state.form.analysisSummary,
      referenceName: state.form.referenceName,
      portraitName: state.form.portraitName,
    };
  }

  async function startGeneration() {
    if (state.isSubmitting) return;
    state.isSubmitting = true;
    render();

    try {
      state.form.script = normalizeSubtitleText(state.form.script);
      const task = await api.createTask(buildTaskPayload());
      state.currentTask = task;
      state.currentTaskId = task.id;
      state.progress = task.progress || 0;
      storage.setItem("chiling-workbench.current-task-id", task.id);
      await refresh.afterTaskCreated(task);
      state.isSubmitting = false;
      state.page = "generating";
      window.history.replaceState(null, "", "#generating");
      render();
      showToast("任务已提交", "生产任务已进入队列，完成后会进入交付区。");
      refresh.startTaskPolling({ navigateOnComplete: true });
    } catch (error) {
      state.isSubmitting = false;
      render();
      showToast("提交失败", error.message || "任务创建失败，请稍后重试。");
    }
  }

  return {
    buildTaskPayload,
    startGeneration,
  };
}
```

Move additional action functions from `app.js` into `actions.js` only after `startGeneration` is green. Use the same dependency injection shape for review approval, generation approval, production request, claim, complete, execute, and operation action.

- [ ] **Step 4: Create `src/polling.js`**

Create `web/chiling-workbench/src/polling.js`:

```js
export function createPollingController({ state, refreshCurrentTask }) {
  function stopTaskPolling() {
    if (!state.taskPoller) return;
    window.clearInterval(state.taskPoller);
    state.taskPoller = null;
  }

  function startTaskPolling({ navigateOnComplete = false } = {}) {
    stopTaskPolling();
    refreshCurrentTask({ navigateOnComplete });
    state.taskPoller = window.setInterval(() => {
      refreshCurrentTask({ navigateOnComplete: navigateOnComplete && state.page === "generating" });
    }, 1000);
  }

  return {
    startTaskPolling,
    stopTaskPolling,
  };
}
```

- [ ] **Step 5: Wire modules into `app.js`**

In `web/chiling-workbench/app.js`, import:

```js
import { createActions } from "./src/actions.js";
import { createPollingController } from "./src/polling.js";
```

Create action and polling instances after refresh functions are defined:

```js
const polling = createPollingController({ state, refreshCurrentTask });
const actions = createActions({
  state,
  api: window.ChilingTaskApi,
  storage: window.localStorage,
  render,
  showToast,
  refresh: {
    afterTaskCreated: async (task) => {
      state.tasks = await window.ChilingTaskApi.listTasks();
      state.queueEntries = await window.ChilingTaskApi.listQueue();
      state.productionRequests = await window.ChilingTaskApi.listProductionRequests();
      state.productionServiceStatus = await window.ChilingTaskApi.listProductionServiceStatus();
      state.operationPanel = await window.ChilingTaskApi.listOperations(task.id);
      state.productionPrep = null;
      await refreshReviewDraft(task.id);
    },
    startTaskPolling: polling.startTaskPolling,
  },
});
```

Then replace `startGeneration()` calls with `actions.startGeneration()` and polling calls with `polling.startTaskPolling()` / `polling.stopTaskPolling()`.

- [ ] **Step 6: Run tests**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_workbench_module_contract.py tests/scripts/test_chiling_frontend_queue_contract.py -q
node --test web/chiling-workbench/tests/*.test.mjs
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add web/chiling-workbench/app.js web/chiling-workbench/src/actions.js web/chiling-workbench/src/polling.js tests/scripts/test_chiling_workbench_module_contract.py
git commit -m "Extract Chiling workbench action boundaries"
```

---

### Task 8: Reorganize CSS and Add Responsive Baseline

**Files:**
- Modify: `web/chiling-workbench/styles.css`
- Modify: `tests/scripts/test_chiling_workbench_module_contract.py`

- [ ] **Step 1: Add CSS organization contract test**

Add to `tests/scripts/test_chiling_workbench_module_contract.py`:

```python
def test_chiling_workbench_css_has_a_plus_sections_and_responsive_rules():
    styles = read(WORKBENCH / "styles.css")

    for marker in [
        "/* 1. Design tokens */",
        "/* 2. Base */",
        "/* 3. Layout */",
        "/* 4. Components */",
        "/* 5. Pages */",
        "/* 6. Responsive */",
    ]:
        assert marker in styles

    assert "@media (max-width: 1180px)" in styles
    assert "@media (max-width: 760px)" in styles
    assert "min-width: 0" in styles
    assert "overflow-wrap: anywhere" in styles
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_workbench_module_contract.py::test_chiling_workbench_css_has_a_plus_sections_and_responsive_rules -q
```

Expected: FAIL until CSS section markers and responsive rules exist.

- [ ] **Step 3: Reorganize `styles.css` into named sections**

Edit `web/chiling-workbench/styles.css` so it starts with:

```css
/* 1. Design tokens */
:root {
  color-scheme: light;
  --bg: #f5f5f7;
  --surface: rgba(255, 255, 255, 0.88);
  --surface-solid: #ffffff;
  --surface-soft: #fbfbfd;
  --ink: #1d1d1f;
  --ink-soft: #343437;
  --muted: #6e6e73;
  --muted-light: #9a9aa0;
  --line: #e5e5ea;
  --line-strong: #d8d8df;
  --red: #d73532;
  --red-soft: #fff0ef;
  --blue: #007aff;
  --blue-soft: #eef6ff;
  --green: #34c759;
  --green-soft: #ecfaf0;
  --amber: #ff9f0a;
  --amber-soft: #fff7e8;
  --shadow: 0 28px 76px rgba(0, 0, 0, 0.075);
  --shadow-soft: 0 16px 42px rgba(0, 0, 0, 0.055);
  --radius-lg: 34px;
  --radius-md: 24px;
  --radius-sm: 18px;
}
```

Place existing reset and typography under `/* 2. Base */`, app shell and grids under `/* 3. Layout */`, buttons/panels/pills/phones/progress/drawers under `/* 4. Components */`, page-specific selectors under `/* 5. Pages */`, and media queries under `/* 6. Responsive */`.

- [ ] **Step 4: Add tablet and mobile responsive rules**

Add to the end of `web/chiling-workbench/styles.css`:

```css
/* 6. Responsive */
@media (max-width: 1180px) {
  body {
    min-width: 0;
  }

  .app-shell {
    padding: 24px;
  }

  .topbar,
  .login-header {
    flex-wrap: wrap;
    height: auto;
    min-height: 66px;
  }

  .brand,
  .login-brand {
    min-width: 0;
  }

  .content-grid,
  .review-grid,
  .login-grid {
    grid-template-columns: 1fr;
  }

  .panel--login,
  .panel--overview {
    min-height: auto;
  }
}

@media (max-width: 760px) {
  .app-shell {
    padding: 16px;
  }

  .page {
    padding: 28px 0 0;
  }

  .topbar {
    gap: 14px;
    padding: 18px;
  }

  .nav {
    width: 100%;
    overflow-x: auto;
    padding-bottom: 4px;
  }

  .hero-title,
  .section-title--large {
    font-size: 34px;
    line-height: 1.12;
  }

  .panel,
  .panel--login,
  .panel--overview {
    border-radius: 24px;
    padding: 28px;
  }

  .task-detail-drawer {
    inset: 0;
    width: auto;
    border-radius: 0;
  }

  button,
  input,
  textarea,
  select,
  .button,
  .nav__item,
  .pill,
  .metric,
  .task-row {
    min-width: 0;
  }

  .task-row,
  .queue-row,
  .production-request,
  .delivery-card {
    overflow-wrap: anywhere;
  }
}
```

If existing selectors use different names, adapt only selector names while preserving the responsive behavior.

- [ ] **Step 5: Run tests and CSS check**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_workbench_module_contract.py tests/scripts/test_chiling_frontend_queue_contract.py -q
git diff --check -- web/chiling-workbench/styles.css
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/chiling-workbench/styles.css tests/scripts/test_chiling_workbench_module_contract.py
git commit -m "Organize Chiling workbench responsive styles"
```

---

### Task 9: Browser Smoke and Final A+ Verification

**Files:**
- Modify: `web/chiling-workbench/README.md`
- Modify: `design-qa.md`

- [ ] **Step 1: Run focused automated verification**

Run:

```bash
node --test web/chiling-workbench/tests/*.test.mjs
.venv/bin/python -m pytest tests/scripts/test_chiling_frontend_queue_contract.py tests/scripts/test_chiling_workbench_module_contract.py tests/scripts/test_chiling_worker_bridge.py -q
.venv/bin/python -m py_compile web/chiling-workbench/worker.py web/chiling-workbench/pipeline_bridge.py
git diff --check
```

Expected:

- Node tests pass.
- Python contract tests pass.
- Worker HTTP smoke may skip if local port binding is unavailable in the sandbox.
- Python compile passes.
- `git diff --check` is clean.

- [ ] **Step 2: Run static app smoke in a browser**

Start a local static server:

```bash
cd /Users/a60/Documents/自动化视频/OpenMontage/web/chiling-workbench
python3 -m http.server 5174
```

Open:

```text
http://127.0.0.1:5174
```

Verify:

- Login page loads.
- Login moves to `#dashboard`.
- Quick import opens `#create`.
- Create page accepts reference URL, duration, resolution, count, and script edits.
- Review page shows queue, production service status, review draft, and safety gates.
- Confirm generation creates a task and opens generating feedback.
- Delivery page shows deliverable cards.
- Task detail drawer opens and closes.

- [ ] **Step 3: Capture browser QA screenshots**

Capture or refresh these screenshots under `web/chiling-workbench/qa-screenshots/`:

```text
login-a-plus.png
dashboard-a-plus.png
create-a-plus.png
review-a-plus.png
generating-a-plus.png
delivery-a-plus.png
mobile-dashboard-a-plus.png
mobile-review-a-plus.png
```

Do not commit generated QA screenshots unless the team wants them as permanent visual fixtures. If screenshots are only local QA artifacts, keep them ignored.

- [ ] **Step 4: Compare against accepted v5 mockups**

Use these accepted concept files:

```text
docs/ui-mockups/chiling-product-v5-login.png
docs/ui-mockups/chiling-product-v5-dashboard.png
docs/ui-mockups/chiling-product-v5-create.png
docs/ui-mockups/chiling-product-v5-generating-feedback.png
docs/ui-mockups/chiling-product-v5-review.png
docs/ui-mockups/chiling-product-v5-delivery.png
```

Check at least these points:

- Brand/nav copy remains `赤灵AI运营工作台`, `生产台`, `作品`, `素材库`, `团队审核`, `数据`, `新建`.
- Main surface remains light, quiet, and v5-like rather than v4 dark/glow.
- Current task and generation progress are visible and readable.
- Review page keeps left preview, editable copy, and right review/gate information.
- Production service and paid generation controls remain user-safe.
- Mobile viewport has no horizontal text/control overlap.

- [ ] **Step 5: Update QA docs**

Modify `design-qa.md` with a short A+ section:

```markdown
## Chiling Workbench A+ QA

- A+ approach keeps the static Web app and Worker/API bridge.
- Frontend modules now separate helpers, state, actions, components, and views.
- Static smoke checked login, dashboard, create, review, generating, delivery, and task detail drawer.
- Paid generation remains gated by review and production confirmation phrases.
- Browser QA compared the app against the v5 mockup set under `docs/ui-mockups/`.
```

Modify `web/chiling-workbench/README.md` to add:

```markdown
## A+ frontend structure

The workbench remains buildless. `app.js` bootstraps the app and imports browser-native modules from `src/`.

- `src/format.js` and `src/task-model.js` contain pure helpers.
- `src/state.js` creates initial state and default form data.
- `src/components/` contains reusable UI renderers.
- `src/views/` contains page-level renderers.
- `api-client.js` remains the API/localStorage adapter.
- `worker.py` remains the local Worker/API bridge.
```

- [ ] **Step 6: Commit final QA/docs**

```bash
git add web/chiling-workbench/README.md design-qa.md
git commit -m "Document Chiling workbench A+ frontend structure"
```

---

## Final Verification Checklist

Run before reporting completion:

```bash
git status --short
node --test web/chiling-workbench/tests/*.test.mjs
.venv/bin/python -m pytest tests/scripts/test_chiling_frontend_queue_contract.py tests/scripts/test_chiling_workbench_module_contract.py tests/scripts/test_chiling_worker_bridge.py -q
.venv/bin/python -m py_compile web/chiling-workbench/worker.py web/chiling-workbench/pipeline_bridge.py
git diff --check
```

Expected:

- Worktree has only intended changes or is clean after final commit.
- Node tests pass.
- Python tests pass or the HTTP smoke skip is explained by local port permissions.
- Python compile passes.
- Diff check is clean.

Do not claim A+ completion until the browser smoke has also been run and compared against the v5 mockups.
