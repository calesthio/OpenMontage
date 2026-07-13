import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  StatusBadge, EventRow, eventLabel, stageLabel, mediaUrl,
  EVENT_COLOR, EVENT_TYPE_LABELS, type SseEvent,
} from "@/components/job-status";
// The canonical backend event-type list, shared with the server suite —
// server/tests/test_event_types.py asserts this fixture matches the actual
// emit-site literals in stage_runner.py / tool_bridge.py / events.py, and
// the test below asserts the frontend maps cover it. Together they make
// backend↔frontend event-type drift a CI failure instead of a silent
// muted-gray row (this drift recurred twice: commit 33a0273, then "warning").
import eventsFixture from "../../schemas/events.json";

function ev(partial: Partial<SseEvent>): SseEvent {
  return { seq: 0, type: "stage_started", ts: 0, ...partial };
}

describe("StatusBadge", () => {
  it("renders the Chinese label for each known status", () => {
    const cases: [string, string][] = [
      ["queued", "排队中"],
      ["running", "生成中"],
      ["awaiting_approval", "待审批"],
      ["completed", "已完成"],
      ["failed", "失败"],
    ];
    for (const [status, label] of cases) {
      const { unmount } = render(<StatusBadge status={status} />);
      expect(screen.getByTestId("status-badge")).toHaveTextContent(label);
      unmount();
    }
  });

  it("renders the raw status string with a neutral style for an unknown status, not the queued label", () => {
    render(<StatusBadge status="who_knows" />);
    const badge = screen.getByTestId("status-badge");
    expect(badge).toHaveTextContent("who_knows");
    expect(badge.className).toContain("bg-muted");
  });

  it("applies the status-specific colour class", () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByTestId("status-badge").className).toContain("text-red-400");
  });
});

describe("eventLabel precedence", () => {
  it("prefers summary over everything else", () => {
    expect(eventLabel(ev({ summary: "S", text: "T", artifact: "A", message: "M" }))).toBe("S");
  });
  it("falls through summary → text → artifact → message → type", () => {
    expect(eventLabel(ev({ text: "T", artifact: "A", message: "M" }))).toBe("T");
    expect(eventLabel(ev({ artifact: "A", message: "M" }))).toBe("A");
    expect(eventLabel(ev({ message: "M" }))).toBe("M");
    expect(eventLabel(ev({ type: "job_failed" }))).toBe("job_failed");
  });

  it("uses a Chinese label for backend event types that carry no summary/text/artifact/message", () => {
    // Regression: budget_precall_block, cost_updated, job_started,
    // stage_skipped, stage_retry, preview_ready, and budget_exceeded are
    // emitted by the runner with no free-text field, so this used to leak
    // the raw English type string straight into the UI.
    const cases: [string, string][] = [
      ["budget_precall_block", "预算预检拦截"],
      ["cost_updated", "费用更新"],
      ["job_started", "任务开始"],
      ["stage_skipped", "跳过阶段"],
      ["stage_retry", "阶段重试"],
      ["preview_ready", "预览就绪"],
      ["budget_exceeded", "预算超限"],
    ];
    for (const [type, label] of cases) {
      expect(eventLabel(ev({ type }))).toBe(label);
    }
  });

  it("appends model and cost to tool_call/asset_ready so the live log shows what's actually generating", () => {
    // tool_call: model known before the call resolves, cost not yet.
    expect(
      eventLabel(ev({ type: "tool_call", tool: "maas_video", summary: "调用工具 maas_video", model: "leapfast/ltx-2.3" }))
    ).toBe("调用工具 maas_video · leapfast/ltx-2.3");

    // asset_ready: backend never sets summary for this type — falls back to
    // a Chinese label + tool name, then appends the resolved model and the
    // real per-call cost once the call has actually succeeded.
    expect(
      eventLabel(ev({ type: "asset_ready", tool: "maas_video", model: "leapfast/ltx-2.3", cost_cny: 0.35 }))
    ).toBe("素材生成完成: maas_video · leapfast/ltx-2.3 · ¥0.3500");

    // Neither field present (e.g. a non-billed/local tool) — no dangling " · ".
    expect(eventLabel(ev({ type: "asset_ready", tool: "music_search" }))).toBe("素材生成完成: music_search");
  });
});

describe("backend event-type contract (schemas/events.json)", () => {
  it("maps every backend event type in EVENT_COLOR unless deliberately allowlisted as muted", () => {
    // Regression: unmapped types render muted-gray with no Chinese label,
    // indistinguishable from chatter — "warning" shipped that way, which
    // defeated its purpose as a warning.
    const mutedOk = new Set(eventsFixture.muted_ok);
    const unmapped = eventsFixture.event_types.filter(
      (t) => !(t in EVENT_COLOR) && !mutedOk.has(t)
    );
    expect(
      unmapped,
      "Backend event types with no EVENT_COLOR entry and not in muted_ok — " +
        "either add them to EVENT_COLOR (and EVENT_TYPE_LABELS if they can " +
        "arrive without a text field) in web/components/job-status.tsx, or " +
        "add them to muted_ok in schemas/events.json if muted rendering is intentional"
    ).toEqual([]);
  });

  it("keeps muted_ok honest — every entry genuinely has no EVENT_COLOR entry", () => {
    // Without this, the allowlist could rot into covering types that are in
    // fact mapped, silently weakening the assertion above.
    const stale = eventsFixture.muted_ok.filter((t) => t in EVENT_COLOR);
    expect(
      stale,
      "muted_ok entries that DO have an EVENT_COLOR entry — remove them from " +
        "muted_ok in schemas/events.json"
    ).toEqual([]);
  });

  it("gives every EVENT_TYPE_LABELS entry a colour too — a labelled type is never muted", () => {
    // EVENT_TYPE_LABELS exists precisely for types that carry no text field;
    // such a type showing up muted-gray is the exact defect this contract
    // guards against, so a label without a colour is always a mistake.
    const uncoloured = Object.keys(EVENT_TYPE_LABELS).filter((t) => !(t in EVENT_COLOR));
    expect(uncoloured).toEqual([]);
  });
});

describe("warning events", () => {
  // Regression: the "warning" type (stage_runner.py's render_report
  // path-divergence check) was unmapped — muted-gray, no Chinese label.
  it("renders orange like the other attention-but-not-failure types", () => {
    render(<EventRow ev={ev({ type: "warning", stage: "compose", message: "路径不一致" })} />);
    expect(screen.getByText("[compose]").className).toContain("text-orange-400");
  });

  it("shows the backend message when present, and the Chinese label when not", () => {
    // The current emit site always carries a message; the label is the
    // safety net for any future no-message warning.
    expect(eventLabel(ev({ type: "warning", message: "路径不一致" }))).toBe("路径不一致");
    expect(eventLabel(ev({ type: "warning" }))).toBe("警告");
  });
});

describe("stageLabel", () => {
  it("maps every stage name used across all pipeline_defs manifests", () => {
    // The union of top-level stage names across all 13 engine pipelines, plus
    // the synthetic "budget" gate — see server/app/pipeline_catalog.py.
    const known = [
      "research", "proposal", "idea", "script", "scene_plan",
      "character_design", "rig_plan", "assets", "edit", "compose",
      "publish", "budget",
    ];
    for (const s of known) {
      const label = stageLabel(s);
      expect(label).not.toBe("");
      expect(label).not.toBe("undefined");
    }
  });

  it("falls back to the raw name for an unmapped stage — never the literal 'undefined'", () => {
    // Regression: STAGE_LABELS[awaitingStage] with no fallback used to render
    // the JS string "undefined" for any pipeline stage outside the hardcoded map.
    expect(stageLabel("some_future_stage")).toBe("some_future_stage");
  });

  it("returns an empty string for null/undefined input", () => {
    expect(stageLabel(null)).toBe("");
    expect(stageLabel(undefined)).toBe("");
  });
});

describe("EventRow", () => {
  it("shows the [stage] tag and the chosen label", () => {
    render(<EventRow ev={ev({ stage: "research", summary: "调研完成" })} />);
    expect(screen.getByText("[research]")).toBeInTheDocument();
    expect(screen.getByText("调研完成")).toBeInTheDocument();
  });

  it("falls back to type for the tag when no stage is present", () => {
    render(<EventRow ev={ev({ type: "job_completed", stage: undefined, message: "done" })} />);
    expect(screen.getByText("[job_completed]")).toBeInTheDocument();
  });
});

describe("mediaUrl", () => {
  // Regression: found live — a bare <video src="/media/..."> resolves
  // against the CURRENT page's origin (the Next.js dev server), not the
  // backend's, since the backend returns root-relative paths meant for its
  // OWN static mount. The video silently failed to load (readyState 0,
  // networkState NETWORK_NO_SOURCE) with no visible error to the user.
  const SERVER = "http://localhost:8010";

  it("prefixes a root-relative backend path with the server origin", () => {
    expect(mediaUrl(SERVER, "/media/proj/renders/final.mp4"))
      .toBe("http://localhost:8010/media/proj/renders/final.mp4");
  });

  it("leaves an already-absolute URL untouched", () => {
    expect(mediaUrl(SERVER, "https://cdn.example.com/final.mp4"))
      .toBe("https://cdn.example.com/final.mp4");
    expect(mediaUrl(SERVER, "http://other-host/final.mp4"))
      .toBe("http://other-host/final.mp4");
  });

  it("leaves a protocol-relative URL untouched instead of double-prefixing it", () => {
    expect(mediaUrl(SERVER, "//cdn.example.com/final.mp4"))
      .toBe("//cdn.example.com/final.mp4");
  });

  it("strips a trailing slash from serverBase before prefixing", () => {
    expect(mediaUrl("http://localhost:8010/", "/media/proj/renders/final.mp4"))
      .toBe("http://localhost:8010/media/proj/renders/final.mp4");
  });

  it("returns null for null/undefined/empty input", () => {
    expect(mediaUrl(SERVER, null)).toBeNull();
    expect(mediaUrl(SERVER, undefined)).toBeNull();
    expect(mediaUrl(SERVER, "")).toBeNull();
  });

  it("inserts a separating slash for a path missing the leading one", () => {
    expect(mediaUrl(SERVER, "media/x.mp4")).toBe("http://localhost:8010/media/x.mp4");
  });
});
