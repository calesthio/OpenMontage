import test from "node:test";
import assert from "node:assert/strict";

import { createPollingController } from "../src/polling.js";

test("polling controller uses injected timers and clamps completion navigation to generating page", () => {
  const state = {
    page: "generating",
    taskPoller: 7,
  };
  const cleared = [];
  const refreshes = [];
  let intervalCallback = null;
  const polling = createPollingController({
    state,
    refreshCurrentTask: (options) => refreshes.push(options),
    timers: {
      clearInterval: (id) => cleared.push(id),
      setInterval: (callback, delay) => {
        intervalCallback = callback;
        assert.equal(delay, 1000);
        return 42;
      },
    },
  });

  polling.startTaskPolling({ navigateOnComplete: true });

  assert.deepEqual(cleared, [7]);
  assert.deepEqual(refreshes, [{ navigateOnComplete: true }]);
  assert.equal(state.taskPoller, 42);

  intervalCallback();
  assert.deepEqual(refreshes.at(-1), { navigateOnComplete: true });

  state.page = "delivery";
  intervalCallback();
  assert.deepEqual(refreshes.at(-1), { navigateOnComplete: false });

  polling.stopTaskPolling();
  assert.deepEqual(cleared, [7, 42]);
  assert.equal(state.taskPoller, null);
});
