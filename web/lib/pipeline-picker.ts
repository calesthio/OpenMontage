// Pure logic for the new-job pipeline picker, extracted so it's testable
// without the fetch-driven page shell (mirrors components/job-status.tsx).

export type PipelineInfo = {
  name: string;
  description: string;
  category?: string;
  stability?: string;
  stages: string[];
};

export type PipelineOption = {
  id: string;
  label: string;
  description: string;
  pipeline: string;
  stability?: string;
};

// Friendly Chinese entry points mapped to engine pipelines.
export const CONTENT_TYPES: PipelineOption[] = [
  { id: "marketing_film", label: "营销宣传片", description: "品牌故事 · 产品发布 · 15-60 秒情感向短片", pipeline: "cinematic" },
  { id: "explainer",      label: "解说视频",   description: "动态图文 · 功能演示 · 教程",              pipeline: "animated-explainer" },
  { id: "podcast",        label: "播客剪辑",   description: "长音频 → 短视频精华片段",                pipeline: "podcast-repurpose" },
  { id: "demo",           label: "产品演示",   description: "屏幕录制 + AI 旁白讲解",                 pipeline: "screen-demo" },
  { id: "short",          label: "短视频批量", description: "长视频 → 多条竖屏短片",                  pipeline: "clip-factory" },
];

/**
 * A curated card is enabled once the engine reports its mapped pipeline.
 * Before /pipelines has loaded (availableNames is empty), everything is
 * enabled so the UI isn't all-disabled on first paint.
 */
export function isPipelineAvailable(availableNames: Set<string>, pipeline: string): boolean {
  return availableNames.size === 0 || availableNames.has(pipeline);
}

/** Engine pipelines with no curated Chinese card — offered directly. */
export function computeMorePipelines(
  pipelines: PipelineInfo[],
  contentTypes: PipelineOption[] = CONTENT_TYPES
): PipelineInfo[] {
  const featured = new Set(contentTypes.map((c) => c.pipeline));
  return pipelines.filter((p) => !featured.has(p.name));
}

/** Build the PipelineOption the picker needs from a raw /pipelines entry. */
export function toPipelineOption(p: PipelineInfo): PipelineOption {
  return {
    id: p.name,
    label: p.name,
    description: p.description,
    pipeline: p.name,
    stability: p.stability,
  };
}
