// Run: npm test  (node --experimental-strip-types --test)
//
// Regression cases are the two real incidents this validator exists for:
// 小兔子电视's text_card carrying a source mp4 and no text (rendered as a raw
// video clip), and an E2E test's stat_card passing `text` instead of `stat`
// (rendered as a plain text card, subtitle silently dropped).

import assert from "node:assert/strict";
import { test } from "node:test";

import { validateCut, validateCuts, CUT_REQUIRED_FIELDS } from "./validateCut.ts";

test("flags a stat_card that passes text instead of stat", () => {
  const issue = validateCut({ id: "c2", type: "stat_card", text: "87%", subtitle: "x" });
  assert.ok(issue);
  assert.equal(issue.type, "stat_card");
  assert.deepEqual(issue.missing, ["stat"]);
  assert.match(issue.message, /will NOT render as a stat_card/);
});

test("flags the 小兔子电视 case: text_card with a source but no text", () => {
  const issue = validateCut({ id: "sc5_endcard", type: "text_card", source: "/x/clip.mp4" });
  assert.ok(issue);
  assert.deepEqual(issue.missing, ["text"]);
});

test("passes a well-formed cut of every known type", () => {
  const samples: Record<string, Record<string, unknown>> = {
    text_card: { text: "hi" },
    stat_card: { stat: "87%" },
    callout: { text: "hi" },
    comparison: { leftLabel: "a", rightLabel: "b", leftValue: "1", rightValue: "2" },
    hero_title: { text: "hi" },
    bar_chart: { chartData: [{ label: "a", value: 1 }] },
    line_chart: { chartSeries: [{ label: "s", data: [] }] },
    pie_chart: { chartData: [{ label: "a", value: 1 }] },
    kpi_grid: { chartData: [{ label: "a", value: 1 }] },
    progress_bar: { progress: 0.5 },
    anime_scene: { images: ["/a.png"] },
    terminal_scene: { steps: [{ cmd: "ls" }] },
    screenshot_scene: { backgroundImage: "/a.png", screenshotSteps: [{ kind: "cursor" }] },
  };
  for (const type of Object.keys(CUT_REQUIRED_FIELDS)) {
    assert.ok(samples[type], `test is missing a sample for ${type}`);
    assert.equal(validateCut({ id: type, type, ...samples[type] }), null, type);
  }
});

test("progress_bar: 0 is a legitimate value, not 'missing'", () => {
  assert.equal(validateCut({ id: "p", type: "progress_bar", progress: 0 }), null);
});

test("an empty required array counts as missing", () => {
  const issue = validateCut({ id: "a", type: "anime_scene", images: [] });
  assert.ok(issue);
  assert.deepEqual(issue.missing, ["images"]);
});

test("ignores cuts with no type — they route by media kind", () => {
  assert.equal(validateCut({ id: "plain", source: "/x/clip.mp4" }), null);
});

test("ignores unknown types rather than inventing a contract", () => {
  assert.equal(validateCut({ id: "u", type: "someday_scene" }), null);
});

test("validateCuts collects every issue and tolerates an empty list", () => {
  const issues = validateCuts([
    { id: "a", type: "stat_card" },
    { id: "b", type: "text_card", text: "ok" },
    { id: "c", type: "bar_chart" },
  ]);
  assert.deepEqual(issues.map((i) => i.id), ["a", "c"]);
  assert.deepEqual(validateCuts([]), []);
});
