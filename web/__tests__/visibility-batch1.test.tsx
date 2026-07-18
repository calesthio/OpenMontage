// Roadmap batch 1 (visibility): filmstrip accumulation, two-tier log
// helpers, honest-progress helpers, artifact renderers, decision
// normalization.

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  groupEventsByStage, aggregateEventRows, stageDurations, formatElapsed,
  Filmstrip, type SseEvent,
} from "@/components/job-status";
import { jobLifecycleReducer, initialJobLifecycleState } from "@/lib/job-lifecycle";
import { normalizeDecision, currentDecisions, assetMediaPath } from "@/lib/artifact-utils";
import { ArtifactView } from "@/components/artifact-view";

const ev = (seq: number, partial: Partial<SseEvent>): SseEvent =>
  ({ seq, type: "x", ts: seq, ...partial }) as SseEvent;

describe("reducer accumulates filmstrip assets and agent text", () => {
  it("collects asset_ready into state.assets with media urls", () => {
    let s = initialJobLifecycleState;
    s = jobLifecycleReducer(s, { type: "sse_event", event: ev(0, { type: "job_started", stages: ["assets"] }) });
    s = jobLifecycleReducer(s, {
      type: "sse_event",
      event: ev(1, {
        type: "asset_ready", stage: "assets", tool: "maas_image",
        kind: "image_generation", media_url: "/media/p/assets/image_generation/a.png",
        path: "/x/a.png", model: "flux-2",
      }),
    });
    s = jobLifecycleReducer(s, { type: "sse_event", event: ev(2, { type: "agent_text", text: "正在生成第 2 张图" }) });
    expect(s.assets).toHaveLength(1);
    expect(s.assets[0].mediaUrl).toBe("/media/p/assets/image_generation/a.png");
    expect(s.agentText).toBe("正在生成第 2 张图");
  });
});

describe("two-tier log helpers", () => {
  it("groups consecutive same-stage events and counts tools/assets/cost", () => {
    const groups = groupEventsByStage([
      ev(0, { type: "job_started" }),
      ev(1, { type: "stage_started", stage: "assets" }),
      ev(2, { type: "tool_call", stage: "assets", tool: "maas_video" }),
      ev(3, { type: "asset_ready", stage: "assets", tool: "maas_video", cost_cny: 1.5 }),
      ev(4, { type: "tool_call", stage: "assets", tool: "maas_video" }),
      ev(5, { type: "asset_ready", stage: "assets", tool: "maas_video", cost_cny: 2 }),
      ev(6, { type: "stage_started", stage: "compose" }),
    ]);
    expect(groups.map((g) => g.stage)).toEqual(["", "assets", "compose"]);
    const assets = groups[1];
    expect(assets.toolCalls).toBe(2);
    expect(assets.assetCount).toBe(2);
    expect(assets.costCny).toBeCloseTo(3.5);
    expect(assets.endTs - assets.startTs).toBe(4);
  });

  it("aggregates consecutive same-type/tool rows ×N and drops agent_text", () => {
    const rows = aggregateEventRows([
      ev(1, { type: "tool_call", tool: "maas_tts" }),
      ev(2, { type: "tool_call", tool: "maas_tts" }),
      ev(3, { type: "agent_text", text: "chatter" }),
      ev(4, { type: "tool_call", tool: "maas_tts" }),
      ev(5, { type: "tool_call", tool: "maas_video" }),
    ]);
    // agent_text is dropped; the run of maas_tts stays contiguous → ×3.
    expect(rows.map((r) => [r.ev.tool, r.count])).toEqual([
      ["maas_tts", 3],
      ["maas_video", 1],
    ]);
  });

  it("derives per-stage durations from started/completed pairs", () => {
    const d = stageDurations([
      ev(1, { type: "stage_started", stage: "research", ts: 100 }),
      ev(2, { type: "stage_completed", stage: "research", ts: 142 }),
      ev(3, { type: "stage_started", stage: "assets", ts: 150 }),
    ]);
    expect(d.research).toBe(42);
    expect(d.assets).toBeUndefined();
  });

  it("formats elapsed time", () => {
    expect(formatElapsed(65)).toBe("1:05");
    expect(formatElapsed(3723)).toBe("1:02:03");
  });
});

describe("Filmstrip", () => {
  it("renders one item per asset with media", () => {
    render(
      <Filmstrip
        serverBase="http://localhost:8000"
        assets={[
          { seq: 1, stage: "assets", tool: "maas_image", kind: "image_generation", mediaUrl: "/media/p/a.png", path: "a.png", model: "flux" },
          { seq: 2, stage: "assets", tool: "maas_tts", kind: "tts", mediaUrl: "/media/p/n.mp3", path: "n.mp3", model: null },
        ]}
      />
    );
    expect(screen.getAllByTestId("filmstrip-item")).toHaveLength(2);
    const img = document.querySelector("img");
    expect(img?.getAttribute("src")).toBe("http://localhost:8000/media/p/a.png");
  });
});

describe("decision normalization (mirror of backlot shim)", () => {
  it("reads recommendation/rationale spellings and string options", () => {
    const n = normalizeDecision({
      category: "voice_selection",
      subject: "Narration TTS provider",
      recommendation: "chirp3",
      rationale: "更自然的中文韵律",
      options_considered: ["chirp3", "openai_onyx"],
    });
    expect(n.selected).toBe("chirp3");
    expect(n.reason).toBe("更自然的中文韵律");
    expect(n.options[0]).toEqual({ option_id: "chirp3", label: "chirp3" });
  });

  it("collapses to the latest entry per (category, subject) pair", () => {
    const cur = currentDecisions([
      { category: "voice_selection", subject: "s", selected: "openai_onyx" },
      { category: "voice_selection", subject: "s", selected: "chirp3" },
      { category: "provider_selection", subject: "p", selected: "flux" },
    ]);
    expect(cur).toHaveLength(2);
    const voice = cur.find((d) => d.category === "voice_selection")!;
    expect(voice.selected).toBe("chirp3");
    expect(voice.revised).toBe(1);
  });
});

describe("assetMediaPath", () => {
  it("maps absolute, repo-relative, and project-relative paths", () => {
    expect(assetMediaPath("p", "/Users/x/om/projects/p/assets/v.mp4")).toBe("/media/p/assets/v.mp4");
    expect(assetMediaPath("p", "projects/p/assets/v.mp4")).toBe("/media/p/assets/v.mp4");
    expect(assetMediaPath("p", "assets/v.mp4")).toBe("/media/p/assets/v.mp4");
    expect(assetMediaPath("p", "/tmp/outside.mp4")).toBeNull();
  });
});

describe("ArtifactView renderers", () => {
  it("renders script sections structurally", () => {
    render(
      <ArtifactView
        name="script"
        value={{ title: "T", sections: [{ id: "s1", label: "开场", text: "大家好", start_seconds: 0, end_seconds: 4 }] }}
        serverBase=""
        projectName="p"
      />
    );
    expect(screen.getByTestId("artifact-script")).toBeTruthy();
    expect(screen.getByText("大家好")).toBeTruthy();
  });

  it("renders scene_plan as a shot list", () => {
    render(
      <ArtifactView
        name="scene_plan"
        value={{ scenes: [{ id: "sc1", type: "video", description: "开场镜头", start_seconds: 0, end_seconds: 3 }] }}
        serverBase=""
        projectName="p"
      />
    );
    expect(screen.getByTestId("artifact-scene-plan")).toBeTruthy();
    expect(screen.getByText("开场镜头")).toBeTruthy();
  });

  it("renders asset_manifest as a thumbnail grid with prompt/model/cost", () => {
    render(
      <ArtifactView
        name="asset_manifest"
        value={{
          assets: [{
            id: "a1", type: "image", path: "assets/images/x.png",
            prompt: "一只机器兔", model: "flux-2", cost_usd: 0.4,
          }],
        }}
        serverBase="http://s"
        projectName="p"
      />
    );
    expect(screen.getByTestId("artifact-asset-manifest")).toBeTruthy();
    const img = document.querySelector("img");
    expect(img?.getAttribute("src")).toBe("http://s/media/p/assets/images/x.png");
    expect(screen.getAllByText(/flux-2/).length).toBeGreaterThan(0);
  });

  it("renders decision_log with normalized picks", () => {
    render(
      <ArtifactView
        name="decision_log"
        value={{ decisions: [{ category: "provider_selection", subject: "tts provider", recommendation: "elevenlabs", rationale: "best fit" }] }}
        serverBase=""
        projectName="p"
      />
    );
    expect(screen.getByTestId("artifact-decision-log")).toBeTruthy();
    expect(screen.getByText("elevenlabs")).toBeTruthy();
    expect(screen.getByText("best fit")).toBeTruthy();
  });

  it("always keeps raw JSON one click away", () => {
    render(<ArtifactView name="script" value={{ sections: [] }} serverBase="" projectName="p" />);
    expect(screen.getByText("</> 查看原始 JSON")).toBeTruthy();
  });
});
