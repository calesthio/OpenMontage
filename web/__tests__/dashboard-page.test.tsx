import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import DashboardPage from "@/app/dashboard/page";

const SERVER = "http://localhost:8000";

function stubJobsFetch(jobs: Array<Record<string, unknown>>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url === `${SERVER}/jobs`) {
        return { ok: true, json: async () => ({ jobs }) } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    })
  );
}

function job(partial: Record<string, unknown>) {
  return {
    job_id: "job-1",
    project_name: "测试项目",
    content_type: "marketing_film",
    status: "queued",
    current_stage: null,
    created_at: 1_700_000_000,
    ...partial,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DashboardPage status badge", () => {
  it("renders 已取消 for a cancelled job instead of falling back to the queued badge", async () => {
    // Regression: the list page used to keep its own STATUS_META map without
    // a "cancelled" entry, and its lookup fell back to STATUS_META.queued —
    // so a cancelled job showed "排队中" on the dashboard list while its own
    // detail page correctly showed "已取消".
    stubJobsFetch([job({ status: "cancelled" })]);
    render(<DashboardPage />);

    // The status-filter <select> also contains an 已取消 <option> now — the
    // assertion targets the badge specifically.
    const badges = await screen.findAllByTestId("status-badge");
    expect(badges.some((b) => b.textContent === "已取消")).toBe(true);
    expect(screen.queryByText("排队中")).not.toBeInTheDocument();
  });

  it("renders the shared StatusBadge component for a known status", async () => {
    stubJobsFetch([job({ status: "completed" })]);
    render(<DashboardPage />);

    const badge = await screen.findByTestId("status-badge");
    expect(badge).toHaveTextContent("已完成");
  });
});

describe("DashboardPage content-type labels", () => {
  it("shows the wizard's Chinese labels for demo and short jobs instead of raw ids", async () => {
    // Regression: the page's hardcoded CONTENT_TYPE_LABEL copy lacked the
    // wizard's "demo" and "short" content types (lib/pipeline-picker.ts
    // CONTENT_TYPES), so those jobs rendered their raw content_type id.
    stubJobsFetch([
      job({ job_id: "job-demo", project_name: "Demo 项目", content_type: "demo" }),
      job({ job_id: "job-short", project_name: "Short 项目", content_type: "short" }),
    ]);
    render(<DashboardPage />);

    expect(await screen.findByText("产品演示")).toBeInTheDocument();
    expect(screen.getByText("短视频批量")).toBeInTheDocument();
    expect(screen.queryByText("demo")).not.toBeInTheDocument();
    expect(screen.queryByText("short")).not.toBeInTheDocument();
  });

  it("still falls back to the raw id for an unknown content type", async () => {
    stubJobsFetch([job({ content_type: "mystery_type" })]);
    render(<DashboardPage />);

    expect(await screen.findByText("mystery_type")).toBeInTheDocument();
  });
});
