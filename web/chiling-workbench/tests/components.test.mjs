import test from "node:test";
import assert from "node:assert/strict";

import { button, phonePreview } from "../src/components/ui.js";
import { renderTopbar } from "../src/components/topbar.js";

test("button escapes content and emits only structured safe attributes", () => {
  const html = button("<保存>", {
    variant: "primary",
    type: "submit",
    className: "button--small danger\"x",
    disabled: true,
    ariaLabel: "保存 <草稿>",
    data: {
      route: "create<script>",
      taskId: "task&1",
      "bad name": "skip-me",
      "onClick": "skip-me-too",
    },
  });

  assert.match(html, /class="button button--primary button--small danger&quot;x"/);
  assert.match(html, /type="submit"/);
  assert.match(html, /disabled/);
  assert.match(html, /aria-label="保存 &lt;草稿&gt;"/);
  assert.match(html, /data-route="create&lt;script&gt;"/);
  assert.match(html, /data-task-id="task&amp;1"/);
  assert.match(html, />&lt;保存&gt;<\/button>/);
  assert.doesNotMatch(html, /bad name/);
  assert.doesNotMatch(html, /skip-me/);
  assert.doesNotMatch(html, /data-on-click/);
  assert.doesNotMatch(html, /attrs/);
});

test("phonePreview preserves phone markup and escapes image and label", () => {
  const html = phonePreview('image" onerror="alert(1)', "<封面>", "is-active");

  assert.match(html, /phone__screen/);
  assert.match(html, /phone__label/);
  assert.match(html, /phone__progress/);
  assert.match(html, /src="image&quot; onerror=&quot;alert\(1\)"/);
  assert.match(html, /alt="&lt;封面&gt;"/);
  assert.match(html, />&lt;封面&gt;<\/span>/);
});

test("renderTopbar preserves route navigation contract", () => {
  const html = renderTopbar({
    pages: [{ id: "dashboard", label: "生产台" }],
    activePage: "dashboard",
  });

  assert.match(html, /data-route="dashboard"/);
  assert.match(html, /data-route="create"/);
  assert.doesNotMatch(html, /data-nav/);
});
