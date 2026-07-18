import { describe, it, expect } from "vitest";
import {
  CONTENT_TYPES, isPipelineAvailable, computeMorePipelines, toPipelineOption,
  type PipelineInfo,
} from "@/lib/pipeline-picker";

function pipe(name: string, over: Partial<PipelineInfo> = {}): PipelineInfo {
  return { name, description: `desc-${name}`, stages: ["research", "compose"], ...over };
}

describe("isPipelineAvailable", () => {
  it("treats everything as available before /pipelines has loaded (empty set)", () => {
    expect(isPipelineAvailable(new Set(), "cinematic")).toBe(true);
    expect(isPipelineAvailable(new Set(), "anything-at-all")).toBe(true);
  });

  it("gates on membership once names are known", () => {
    const names = new Set(["cinematic", "animated-explainer"]);
    expect(isPipelineAvailable(names, "cinematic")).toBe(true);
    expect(isPipelineAvailable(names, "screen-demo")).toBe(false);
  });
});

describe("computeMorePipelines", () => {
  it("excludes pipelines already featured in CONTENT_TYPES", () => {
    const featuredNames = CONTENT_TYPES.map((c) => c.pipeline);
    const all = [
      ...featuredNames.map((n) => pipe(n)),
      pipe("animation"),
      pipe("hybrid"),
    ];
    const more = computeMorePipelines(all);
    const moreNames = more.map((p) => p.name);
    expect(moreNames).toEqual(["animation", "hybrid"]);
    for (const n of featuredNames) expect(moreNames).not.toContain(n);
  });

  it("returns an empty list when every pipeline is featured", () => {
    const featuredNames = CONTENT_TYPES.map((c) => c.pipeline);
    const all = featuredNames.map((n) => pipe(n));
    expect(computeMorePipelines(all)).toEqual([]);
  });

  it("returns everything when nothing is featured (custom contentTypes)", () => {
    const all = [pipe("a"), pipe("b")];
    expect(computeMorePipelines(all, []).map((p) => p.name)).toEqual(["a", "b"]);
  });
});

describe("toPipelineOption", () => {
  it("maps a /pipelines entry to everything the wizard needs", () => {
    const opt = toPipelineOption(pipe("avatar-spokesperson", { description: "Talking avatar videos", stability: "beta" }));
    // id/pipeline both key off the engine name so submit + selection stay consistent
    expect(opt).toEqual({
      id: "avatar-spokesperson",
      label: "avatar-spokesperson",
      description: "Talking avatar videos",
      pipeline: "avatar-spokesperson",
      stability: "beta",
    });
  });

  it("carries through an absent stability as undefined", () => {
    const opt = toPipelineOption(pipe("clip-factory"));
    expect(opt.stability).toBeUndefined();
  });
});

describe("CONTENT_TYPES", () => {
  it("has no duplicate ids or pipeline names", () => {
    const ids = CONTENT_TYPES.map((c) => c.id);
    const pipelines = CONTENT_TYPES.map((c) => c.pipeline);
    expect(new Set(ids).size).toBe(ids.length);
    expect(new Set(pipelines).size).toBe(pipelines.length);
  });
});
