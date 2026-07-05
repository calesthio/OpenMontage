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
