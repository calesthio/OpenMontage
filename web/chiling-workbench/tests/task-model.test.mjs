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
