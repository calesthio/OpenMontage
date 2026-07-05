import test from "node:test";
import assert from "node:assert/strict";

import { bindDelegatedClick, find, findAll } from "../src/dom.js";

function createRoot({ contains = () => true } = {}) {
  const listeners = new Map();

  return {
    listeners,
    contains,
    addEventListener(type, listener) {
      listeners.set(type, listener);
    },
    removeEventListener(type, listener) {
      if (listeners.get(type) === listener) {
        listeners.delete(type);
      }
    },
  };
}

test("find delegates to root.querySelector", () => {
  const root = {
    querySelector(selector) {
      return { selector };
    },
  };

  assert.deepEqual(find(root, "[data-action]"), { selector: "[data-action]" });
});

test("findAll returns a real array from querySelectorAll", () => {
  const first = { id: "first" };
  const second = { id: "second" };
  const root = {
    querySelectorAll(selector) {
      assert.equal(selector, "[data-item]");
      return {
        0: first,
        1: second,
        length: 2,
      };
    },
  };

  const result = findAll(root, "[data-item]");

  assert.ok(Array.isArray(result));
  assert.deepEqual(result, [first, second]);
});

test("bindDelegatedClick calls handler with event and closest matching target", () => {
  const matchedTarget = { id: "matched" };
  const root = createRoot();
  let receivedEvent;
  let receivedTarget;

  bindDelegatedClick(root, "[data-action]", (event, target) => {
    receivedEvent = event;
    receivedTarget = target;
  });

  const event = {
    target: {
      closest(selector) {
        assert.equal(selector, "[data-action]");
        return matchedTarget;
      },
    },
  };
  root.listeners.get("click")(event);

  assert.equal(receivedEvent, event);
  assert.equal(receivedTarget, matchedTarget);
});

test("bindDelegatedClick ignores outside and non-contained targets", () => {
  const outsideTarget = { id: "outside" };
  const root = createRoot({ contains: (target) => target !== outsideTarget });
  let callCount = 0;

  bindDelegatedClick(root, "[data-action]", () => {
    callCount += 1;
  });

  root.listeners.get("click")({
    target: {
      closest() {
        return null;
      },
    },
  });
  root.listeners.get("click")({
    target: {
      closest() {
        return outsideTarget;
      },
    },
  });

  assert.equal(callCount, 0);
});

test("bindDelegatedClick handles non-Element-like targets and parentElement closest", () => {
  const matchedTarget = { id: "matched" };
  const root = createRoot();
  const targets = [];

  bindDelegatedClick(root, "[data-action]", (event, target) => {
    targets.push(target);
  });

  assert.doesNotThrow(() => {
    root.listeners.get("click")({ target: { nodeType: 3 } });
  });

  root.listeners.get("click")({
    target: {
      nodeType: 3,
      parentElement: {
        closest(selector) {
          assert.equal(selector, "[data-action]");
          return matchedTarget;
        },
      },
    },
  });

  assert.deepEqual(targets, [matchedTarget]);
});

test("bindDelegatedClick returns an unbind function that removes the listener", () => {
  const root = createRoot();

  const unbind = bindDelegatedClick(root, "[data-action]", () => {});
  assert.equal(typeof unbind, "function");
  assert.equal(typeof root.listeners.get("click"), "function");

  unbind();

  assert.equal(root.listeners.has("click"), false);
});
