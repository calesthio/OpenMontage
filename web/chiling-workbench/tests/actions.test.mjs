import test from "node:test";
import assert from "node:assert/strict";

import { createActions } from "../src/actions.js";

function createActionHarness({ createTask } = {}) {
  const calls = {
    render: 0,
    storage: [],
    toasts: [],
    refreshed: [],
    polling: [],
  };
  const state = {
    isSubmitting: false,
    form: {
      referenceUrl: "https://example.test/ref.mp4",
      duration: 8,
      resolution: "720p",
      count: 2,
      subtitleStyle: "bold",
      script: "第一句。\n第二句!",
      analysisSummary: "轻快口播",
      referenceName: "参考.mp4",
      portraitName: "肖像.png",
    },
    currentTask: null,
    currentTaskId: "",
    progress: 0,
    page: "review",
  };
  const api = {
    createTask: createTask || (async (payload) => ({ id: "task-1", progress: 12, payload })),
  };
  const actions = createActions({
    state,
    api,
    storage: {
      setItem: (key, value) => calls.storage.push([key, value]),
    },
    render: () => {
      calls.render += 1;
    },
    showToast: (title, message) => calls.toasts.push([title, message]),
    refresh: {
      afterTaskCreated: async (task) => calls.refreshed.push(task.id),
      startTaskPolling: (options) => calls.polling.push(options),
    },
  });

  return { actions, calls, state };
}

test("buildTaskPayload normalizes editable form fields without browser globals", () => {
  const { actions } = createActionHarness();

  assert.deepEqual(actions.buildTaskPayload(), {
    referenceUrl: "https://example.test/ref.mp4",
    duration: 8,
    resolution: "720p",
    count: 2,
    subtitleStyle: "bold",
    script: "第一句\n第二句",
    analysisSummary: "轻快口播",
    referenceName: "参考.mp4",
    portraitName: "肖像.png",
  });
});

test("startGeneration creates a task and starts polling through injected dependencies", async () => {
  const { actions, calls, state } = createActionHarness();

  await actions.startGeneration();

  assert.equal(state.currentTaskId, "task-1");
  assert.equal(state.progress, 12);
  assert.equal(state.page, "generating");
  assert.equal(state.isSubmitting, false);
  assert.equal(state.form.script, "第一句\n第二句");
  assert.deepEqual(calls.storage, [["chiling-workbench.current-task-id", "task-1"]]);
  assert.deepEqual(calls.refreshed, ["task-1"]);
  assert.deepEqual(calls.polling, [{ navigateOnComplete: true }]);
  assert.deepEqual(calls.toasts.at(-1), ["任务已提交", "生产任务已进入队列，完成后会进入交付区。"]);
  assert.equal(calls.render, 2);
});

test("startGeneration resets submitting state and keeps the current page on failure", async () => {
  const { actions, calls, state } = createActionHarness({
    createTask: async () => {
      throw new Error("network down");
    },
  });

  await actions.startGeneration();

  assert.equal(state.isSubmitting, false);
  assert.equal(state.currentTaskId, "");
  assert.equal(state.page, "review");
  assert.deepEqual(calls.refreshed, []);
  assert.deepEqual(calls.polling, []);
  assert.deepEqual(calls.toasts.at(-1), ["提交失败", "network down"]);
  assert.equal(calls.render, 2);
});
