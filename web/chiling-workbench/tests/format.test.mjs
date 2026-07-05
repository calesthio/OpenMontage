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
