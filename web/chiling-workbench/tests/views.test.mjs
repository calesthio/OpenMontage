import test from "node:test";
import assert from "node:assert/strict";

import { render as renderLoginView } from "../src/views/login.js";
import { render as renderDashboardView } from "../src/views/dashboard.js";
import { render as renderCreateView } from "../src/views/create.js";

function createState(overrides = {}) {
  return {
    form: {
      referenceUrl: "",
      referenceName: "reference.mp4",
      portraitName: "portrait.png",
      referencePreview: "./assets/reference-frame.png",
      duration: 15,
      count: 1,
      resolution: "480p",
      subtitleStyle: "short",
      script: "默认文案",
      ...overrides,
    },
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
