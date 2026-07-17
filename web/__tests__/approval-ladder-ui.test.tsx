// Roadmap 0.2/0.4 UI: approval countdown chip, ladder toasts, and the
// revisions_exhausted gate variant of the approval panel.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import JobDetailPage from "@/app/dashboard/jobs/[jobId]/page";
import { AppToastProvider } from "@/components/ui/toast";
import { ApprovalPanel } from "@/components/approval-panel";
import { formatRemaining } from "@/components/job-status";

const SERVER = "http://localhost:8000";
const JOB_ID = "job-ladder";

vi.mock("next/navigation", () => ({
  useParams: () => ({ jobId: JOB_ID }),
  useRouter: () => ({ push: vi.fn() }),
}));

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  close() {
    this.closed = true;
  }
}

function renderPage() {
  return render(
    <AppToastProvider>
      <JobDetailPage />
    </AppToastProvider>
  );
}

function pushEvent(partial: Record<string, unknown>) {
  const es = FakeEventSource.instances[0];
  act(() => {
    es.onopen?.();
    es.onmessage?.({ data: JSON.stringify(partial) } as MessageEvent);
  });
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => ({}) }) as Response)
  );
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("approval countdown chip + ladder toasts", () => {
  it("shows the countdown chip while awaiting approval, with the gate's expiry", async () => {
    renderPage();
    const now = Date.now() / 1000;
    pushEvent({
      seq: 0, type: "job_started", ts: now, stages: ["idea", "compose"],
    });
    pushEvent({
      seq: 1, type: "awaiting_approval", stage: "idea", ts: now,
      preview: { k: 1 }, expires_at: now + 7 * 24 * 3600, reminder_seconds: 1800,
    });
    const chip = await screen.findByText(/审批剩余/);
    expect(chip.textContent).toMatch(/6天23小时|7天0小时/);
  });

  it("toasts on a fresh awaiting_approval and on approval reminders", async () => {
    renderPage();
    const now = Date.now() / 1000;
    pushEvent({ seq: 0, type: "job_started", ts: now, stages: ["idea"] });
    pushEvent({
      seq: 1, type: "awaiting_approval", stage: "idea", ts: now,
      preview: null, expires_at: now + 1000,
    });
    expect(await screen.findByText("任务等待你的审批")).toBeTruthy();
    pushEvent({
      seq: 2, type: "approval_reminder", stage: "idea", ts: now,
      reminder_index: 1, waited_seconds: 1800, expires_at: now + 1000,
    });
    expect(await screen.findByText("审批提醒")).toBeTruthy();
  });

  it("does NOT toast for stale replayed events (page reload)", () => {
    renderPage();
    const staleTs = Date.now() / 1000 - 3600;
    pushEvent({ seq: 0, type: "job_started", ts: staleTs, stages: ["idea"] });
    pushEvent({
      seq: 1, type: "awaiting_approval", stage: "idea", ts: staleTs,
      preview: null, expires_at: staleTs + 1000,
    });
    expect(screen.queryByText("任务等待你的审批")).toBeNull();
  });
});

describe("revisions_exhausted gate panel", () => {
  it("offers accept-as-is vs stop, with no feedback requirement", () => {
    render(
      <ApprovalPanel
        jobId={JOB_ID}
        stage="idea"
        gate="revisions_exhausted"
        preview={{ revisions_used: 3, max_revisions: 3, text: "x" }}
        onError={() => {}}
        onApproved={() => {}}
      />
    );
    expect(screen.getByText(/修订次数已用尽/)).toBeTruthy();
    expect(screen.getByText("✓ 接受当前版本，继续生产")).toBeTruthy();
    const stop = screen.getByText("⛔ 终止任务");
    // Reject needs no feedback at this gate (nothing regenerates).
    expect((stop.closest("button") as HTMLButtonElement).disabled).toBe(false);
    // No inline-edit button — the preview here is an explanation, not the artifact.
    expect(screen.queryByText("✏ 直接编辑")).toBeNull();
  });
});

describe("formatRemaining", () => {
  it("formats days/hours/minutes/seconds tiers", () => {
    expect(formatRemaining(6 * 86400 + 23 * 3600)).toBe("6天23小时");
    expect(formatRemaining(3 * 3600 + 300)).toBe("3小时05分");
    expect(formatRemaining(1499)).toBe("24:59");
    expect(formatRemaining(0)).toBe("已到期");
  });
});
