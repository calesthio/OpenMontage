import test from "node:test";
import assert from "node:assert/strict";

import { render as renderLoginView } from "../src/views/login.js";
import { render as renderDashboardView } from "../src/views/dashboard.js";
import { render as renderCreateView } from "../src/views/create.js";
import { render as renderReviewView } from "../src/views/review.js";
import { render as renderGeneratingView } from "../src/views/generating.js";
import { render as renderDeliveryView } from "../src/views/delivery.js";
import { render as renderAdminView } from "../src/views/admin.js";
import { render as renderTaskDetailDrawerView } from "../src/views/detail-drawer.js";
import { normalizeDeliveryUrl } from "../src/action-safety.js";

function createState(overrides = {}) {
  const formDefaults = {
    referenceUrl: "",
    referenceName: "reference.mp4",
    portraitName: "portrait.png",
    referencePreview: "./assets/reference-frame.png",
    portraitPreview: "./assets/portrait.png",
    duration: 15,
    count: 1,
    resolution: "480p",
    subtitleStyle: "short",
    analysisSummary: "默认摘要",
    script: "默认文案",
  };
  const formKeys = new Set(Object.keys(formDefaults));
  const rootOverrides = { ...overrides };
  const formOverrides = { ...(overrides.form || {}) };

  formKeys.forEach((key) => {
    if (key in rootOverrides) {
      formOverrides[key] = rootOverrides[key];
      delete rootOverrides[key];
    }
  });
  delete rootOverrides.form;

  return {
    progress: 0,
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
    ...rootOverrides,
    form: { ...formDefaults, ...formOverrides },
  };
}

test("renderLoginView returns login page shell and form hook", () => {
  const html = renderLoginView({ state: createState() });

  assert.match(html, /<main class="page page--login">/);
  assert.match(html, /data-login-form/);
});

test("renderDashboardView escapes reference URL and preserves dashboard hooks", () => {
  const state = createState({
    referenceUrl: 'https://example.test/"<script>alert(1)</script>',
  });
  const html = renderDashboardView({
    state,
    referenceFrame: './assets/reference"frame.png',
  });

  assert.match(html, /value="https:\/\/example\.test\/&quot;&lt;script&gt;alert\(1\)&lt;\/script&gt;"/);
  assert.doesNotMatch(html, /<script>alert\(1\)<\/script>/);
  assert.match(html, /src="\.\/assets\/reference&quot;frame\.png"/);
  assert.match(html, /data-quick-import/);
  assert.match(html, /data-route="review"/);
});

test("renderCreateView escapes form values and preserves create hooks", () => {
  const state = createState({
    referenceUrl: 'https://example.test/"<script>alert(1)</script>',
    script: '<img src=x onerror="alert(1)">',
    referenceName: 'reference"><script>alert(1)</script>.mp4',
    portraitName: 'portrait"><script>alert(2)</script>.png',
  });
  const html = renderCreateView({ state });

  assert.match(html, /value="https:\/\/example\.test\/&quot;&lt;script&gt;alert\(1\)&lt;\/script&gt;"/);
  assert.match(html, /&lt;img src=x onerror=&quot;alert\(1\)&quot;&gt;/);
  assert.match(html, /reference&quot;&gt;&lt;script&gt;alert\(1\)&lt;\/script&gt;\.mp4/);
  assert.match(html, /portrait&quot;&gt;&lt;script&gt;alert\(2\)&lt;\/script&gt;\.png/);
  assert.doesNotMatch(html, /<script>alert/);
  assert.doesNotMatch(html, /<img src=x/);
  assert.match(html, /data-save-form/);
  assert.match(html, /data-to-review/);
  assert.match(html, /type="file" accept="video\/\*" data-file-input="reference"/);
  assert.match(html, /type="file" accept="image\/\*" data-file-input="portrait"/);
});

test("renderReviewView preserves workflow hooks and escapes queue fields", () => {
  const state = createState({
    script: '<script>alert(1)</script>',
    analysisSummary: '<img src=x onerror="alert(1)">',
    queueEntries: [
      {
        taskId: 'task"><script>alert(2)</script>',
        title: 'Queue <script>alert(3)</script>',
        statusLabel: 'Status "<script>alert(4)</script>',
        sourceState: '<img src=x>',
        nextAction: "Next <script>",
        blockingNote: 'Blocked "now"',
        route: 'generating" onmouseover="alert(5)',
      },
    ],
    productionRequests: [
      {
        taskId: 'prod"><script>alert(6)</script>',
        title: "Request <script>",
        statusLabel: "<img src=x>",
        nextAction: 'Run "manual"',
        executionStarted: true,
      },
    ],
    productionServiceStatus: {
      status: "ready",
      ready: true,
      executionAllowed: true,
      summary: "Summary <script>",
      nextAction: '<img src=x onerror="alert(7)">',
      checks: [{ state: "blocked", label: "Check <script>", message: "<img src=x>" }],
    },
    reviewDraft: {
      operatorHint: "Hint <script>",
      subtitleRule: '<img src=x onerror="alert(8)">',
    },
  });
  const html = renderReviewView({ state });

  assert.match(html, /data-refresh-queue/);
  assert.match(html, /data-save-review/);
  assert.match(html, /data-start-generation/);
  assert.match(html, /Queue &lt;script&gt;alert\(3\)&lt;\/script&gt;/);
  assert.match(html, /data-open-task-detail="task&quot;&gt;&lt;script&gt;alert\(2\)&lt;\/script&gt;"/);
  assert.match(html, /data-open-route="generating"/);
  assert.doesNotMatch(html, /data-open-route="generating&quot; onmouseover/);
  assert.doesNotMatch(html, /<script>alert/);
  assert.doesNotMatch(html, /<img src=x/);
});

test("renderGeneratingView preserves production hooks and escapes task data", () => {
  const state = createState({
    progress: '125"><script>alert(0)</script>',
    generationPhrase: '确认"><script>alert(1)</script>',
    productionRequestPhrase: '提交"><script>alert(2)</script>',
    currentTask: {
      id: 'task"><script>alert(3)</script>',
      status: "processing",
      progress: 44,
      payload: { count: '2<script>', duration: '15<script>', resolution: '720p<script>' },
      review: { status: "approved" },
      stages: [{ name: "Stage <script>", detail: '<img src=x onerror="alert(4)">', state: 'active"><script>' }],
    },
    operationPanel: {
      operatorHint: 'Hint <script>alert(5)</script>',
      steps: [
        {
          id: 'op"><script>alert(6)</script>',
          title: "Step <script>",
          state: "ready",
          stateLabel: '<img src=x>',
          actionLabel: 'Run "now"',
          description: "Description <script>",
          canExecute: true,
        },
      ],
    },
    productionPrep: {
      status: "ready",
      operatorHint: "Prep <script>",
      constraints: { batchCount: "2<script>", durationSeconds: "15<script>", resolution: "720p<script>" },
      assets: { referenceName: "ref <script>", portraitName: "<img src=x>" },
      review: { scriptLines: ["line <script>"] },
    },
  });
  const html = renderGeneratingView({ state });

  assert.match(html, /data-progress-ring/);
  assert.match(html, /data-generation-phrase/);
  assert.match(html, /data-submit-production-request/);
  assert.match(html, /data-progress="100"/);
  assert.match(html, /style="--progress: 100;"/);
  assert.doesNotMatch(html, /125&quot;&gt;&lt;script&gt;alert\(0\)&lt;\/script&gt;/);
  assert.match(html, /task&quot;&gt;&lt;script&gt;alert\(3\)&lt;\/script&gt;/);
  assert.match(html, /Stage &lt;script&gt;/);
  assert.doesNotMatch(html, /<script>alert/);
  assert.doesNotMatch(html, /<img src=x/);
});

test("renderDeliveryView preserves delivery hooks and escapes deliverables", () => {
  const state = createState({
    currentTask: {
      id: 'delivery"><script>alert(1)</script>',
      title: "Title <script>",
      payload: { resolution: "720p" },
    },
    deliverables: [
      {
        title: "File <script>",
        subtitle: '<img src=x onerror="alert(2)">',
        action: 'Copy "now"',
        url: 'https://example.test/"><script>alert(3)</script>',
      },
    ],
  });
  const html = renderDeliveryView({ state });

  assert.match(html, /data-delivery-action="Copy &quot;now&quot;"/);
  assert.match(html, /Title &lt;script&gt;/);
  assert.match(html, /https:\/\/example\.test\/%22%3E%3Cscript%3Ealert\(3\)%3C\/script%3E/);
  assert.doesNotMatch(html, /<script>alert/);
  assert.doesNotMatch(html, /<img src=x/);
});

test("renderDeliveryView omits unsafe delivery URLs from action hooks", () => {
  const state = createState({
    deliverables: [
      {
        title: "Unsafe link",
        subtitle: "Should not open",
        action: "复制",
        url: 'javascript:alert("x")',
      },
    ],
  });
  const html = renderDeliveryView({ state });

  assert.match(html, /data-delivery-url=""/);
  assert.doesNotMatch(html, /javascript:alert/);
});

test("normalizeDeliveryUrl allows only safe delivery URL schemes", () => {
  const base = "https://workbench.example/base/page";

  assert.equal(normalizeDeliveryUrl("https://cdn.example/file.mp4", base), "https://cdn.example/file.mp4");
  assert.equal(normalizeDeliveryUrl("http://cdn.example/file.mp4", base), "http://cdn.example/file.mp4");
  assert.equal(normalizeDeliveryUrl("/deliveries/file.mp4", base), "https://workbench.example/deliveries/file.mp4");
  assert.equal(normalizeDeliveryUrl("./file.mp4", base), "https://workbench.example/base/file.mp4");
  assert.equal(normalizeDeliveryUrl("blob:https://workbench.example/object-id", base), "blob:https://workbench.example/object-id");
  assert.equal(normalizeDeliveryUrl("blob:https://evil.example/object-id", base), "");
  assert.equal(normalizeDeliveryUrl('javascript:alert("x")', base), "");
  assert.equal(normalizeDeliveryUrl("data:text/html,evil", base), "");
  assert.equal(normalizeDeliveryUrl("ftp://example.test/file", base), "");
  assert.equal(normalizeDeliveryUrl("//evil.example/file.mp4", base), "");
});

test("renderAdminView renders admin pages and escapes task, audit, and config fields", () => {
  const state = createState({
    tasks: [
      {
        id: 'work"><script>alert(1)</script>',
        title: "Work <script>",
        status: "completed",
        progress: 100,
        createdAt: Date.now(),
      },
    ],
    productionServiceConfiguration: {
      status: { status: "ready" },
      items: [{ state: "blocked", label: "Config <script>", description: '<img src=x onerror="alert(2)">' }],
      adminChecklist: ["Todo <script>"],
      guardrails: ['Guard "rail" <script>'],
    },
    productionAuditLog: {
      events: [
        {
          state: "blocked",
          label: "Audit <script>",
          title: '<img src=x onerror="alert(3)">',
          detail: "Detail <script>",
          actor: 'Actor "name"',
          at: Date.now(),
        },
      ],
    },
  });
  const worksHtml = renderAdminView({ state, page: "works", referenceFrame: "./ref.png", portraitFrame: "./portrait.png" });
  const libraryHtml = renderAdminView({ state, page: "library", referenceFrame: './ref"><script>.png', portraitFrame: "./portrait.png" });
  const dataHtml = renderAdminView({ state, page: "data", referenceFrame: "./ref.png", portraitFrame: "./portrait.png" });
  const combined = `${worksHtml}${libraryHtml}${dataHtml}`;

  assert.match(worksHtml, /data-open-task-detail="work&quot;&gt;&lt;script&gt;alert\(1\)&lt;\/script&gt;"/);
  assert.match(libraryHtml, /src="\.\/ref&quot;&gt;&lt;script&gt;\.png"/);
  assert.match(dataHtml, /data-refresh-production-service-configuration/);
  assert.match(dataHtml, /data-refresh-production-audit-log/);
  assert.match(dataHtml, /Config &lt;script&gt;/);
  assert.match(dataHtml, /Audit &lt;script&gt;/);
  assert.doesNotMatch(combined, /<script>alert/);
  assert.doesNotMatch(combined, /<img src=x/);
});

test("renderTaskDetailDrawerView returns empty when closed and escapes drawer fields", () => {
  assert.equal(renderTaskDetailDrawerView({ state: createState() }), "");

  const html = renderTaskDetailDrawerView({
    state: createState({
      detailDrawerOpen: true,
      taskDetail: {
        title: 'Drawer"><script>alert(1)</script>',
        statusLabel: "<img src=x>",
        progress: '50"><script>',
        sections: [
          {
            title: "Section <script>",
            state: "ready",
            items: [{ state: "blocked", label: "Label <script>", value: '<img src=x onerror="alert(2)">' }],
          },
        ],
      },
    }),
  });

  assert.match(html, /data-close-task-detail/);
  assert.match(html, /Drawer&quot;&gt;&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.match(html, /Section &lt;script&gt;/);
  assert.doesNotMatch(html, /<script>alert/);
  assert.doesNotMatch(html, /<img src=x/);
});
