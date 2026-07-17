import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import JobDetailPage from "@/app/dashboard/jobs/[jobId]/page";
import { AppToastProvider } from "@/components/ui/toast";

// The page calls useToastManager (approval-ladder notifications), which
// requires the provider the dashboard layout normally mounts.
function renderPage() {
  return render(
    <AppToastProvider>
      <JobDetailPage />
    </AppToastProvider>
  );
}

const SERVER = "http://localhost:8000";
const JOB_ID = "job123";

vi.mock("next/navigation", () => ({
  useParams: () => ({ jobId: JOB_ID }),
}));

// jsdom has no native EventSource — stand in a minimal, fully-controllable
// fake so tests can trigger onopen/onerror/onmessage deterministically.
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

function seqEvent(seq: number, partial: Record<string, unknown>) {
  return { seq, ts: 0, ...partial };
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);
  // jsdom doesn't implement scrollIntoView; the page calls it on every
  // events update, so stub it out rather than let it throw.
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("JobDetailPage SSE reconnect backoff", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === `${SERVER}/jobs/${JOB_ID}`) {
          return { ok: true, json: async () => ({}) } as Response;
        }
        return { ok: true, json: async () => ({}) } as Response;
      })
    );
  });

  it("doubles the reconnect delay on each consecutive failure, capped at 30s", async () => {
    renderPage();

    expect(FakeEventSource.instances).toHaveLength(1);

    // 1st failure -> waits the base 2s before reconnecting.
    act(() => { FakeEventSource.instances[0].onerror?.(); });
    act(() => { vi.advanceTimersByTime(1999); });
    expect(FakeEventSource.instances).toHaveLength(1);
    act(() => { vi.advanceTimersByTime(1); });
    expect(FakeEventSource.instances).toHaveLength(2);

    // 2nd consecutive failure (no success in between) -> waits 4s.
    act(() => { FakeEventSource.instances[1].onerror?.(); });
    act(() => { vi.advanceTimersByTime(3999); });
    expect(FakeEventSource.instances).toHaveLength(2);
    act(() => { vi.advanceTimersByTime(1); });
    expect(FakeEventSource.instances).toHaveLength(3);

    // 3rd consecutive failure -> waits 8s.
    act(() => { FakeEventSource.instances[2].onerror?.(); });
    act(() => { vi.advanceTimersByTime(7999); });
    expect(FakeEventSource.instances).toHaveLength(3);
    act(() => { vi.advanceTimersByTime(1); });
    expect(FakeEventSource.instances).toHaveLength(4);

    // 4th consecutive failure -> waits 16s.
    act(() => { FakeEventSource.instances[3].onerror?.(); });
    act(() => { vi.advanceTimersByTime(15999); });
    expect(FakeEventSource.instances).toHaveLength(4);
    act(() => { vi.advanceTimersByTime(1); });
    expect(FakeEventSource.instances).toHaveLength(5);

    // 5th consecutive failure -> would be 32s uncapped, but caps at 30s.
    act(() => { FakeEventSource.instances[4].onerror?.(); });
    act(() => { vi.advanceTimersByTime(29999); });
    expect(FakeEventSource.instances).toHaveLength(5);
    act(() => { vi.advanceTimersByTime(1); });
    expect(FakeEventSource.instances).toHaveLength(6);

    // 6th consecutive failure -> stays capped at 30s, never grows further.
    act(() => { FakeEventSource.instances[5].onerror?.(); });
    act(() => { vi.advanceTimersByTime(29999); });
    expect(FakeEventSource.instances).toHaveLength(6);
    act(() => { vi.advanceTimersByTime(1); });
    expect(FakeEventSource.instances).toHaveLength(7);
  });

  it("resets the backoff to the base interval once a connection succeeds", async () => {
    renderPage();

    // Grow the delay to 4s (one failure).
    act(() => { FakeEventSource.instances[0].onerror?.(); });
    act(() => { vi.advanceTimersByTime(2000); });
    expect(FakeEventSource.instances).toHaveLength(2);

    // This connection succeeds -> backoff resets to the 2s base.
    act(() => { FakeEventSource.instances[1].onopen?.(); });

    // Fails again — if the reset didn't happen this would need 4s; confirm
    // 2s (the base) is now sufficient.
    act(() => { FakeEventSource.instances[1].onerror?.(); });
    act(() => { vi.advanceTimersByTime(1999); });
    expect(FakeEventSource.instances).toHaveLength(2);
    act(() => { vi.advanceTimersByTime(1); });
    expect(FakeEventSource.instances).toHaveLength(3);
  });

  it("stops reconnecting once the stream ends on a genuine terminal event", async () => {
    renderPage();

    act(() => {
      FakeEventSource.instances[0].onmessage?.({
        data: JSON.stringify(seqEvent(1, { type: "job_completed", render_url: "/media/x.mp4" })),
      } as MessageEvent);
    });
    act(() => { FakeEventSource.instances[0].onerror?.(); });
    act(() => { vi.advanceTimersByTime(60000); });

    // No reconnect attempt was scheduled — the stream ended on a terminal event.
    expect(FakeEventSource.instances).toHaveLength(1);
  });
});

describe("JobDetailPage inline artifact edit error handling", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (method === "GET" && url === `${SERVER}/jobs/${JOB_ID}`) {
          return { ok: true, json: async () => ({}) } as Response;
        }
        if (method === "POST" && url === `${SERVER}/jobs/${JOB_ID}/artifact`) {
          return {
            ok: false,
            status: 400,
            json: async () => ({ detail: "invalid stage: nope" }),
          } as Response;
        }
        return { ok: true, json: async () => ({}) } as Response;
      })
    );
  });

  async function openEditor() {
    renderPage();

    act(() => {
      FakeEventSource.instances[0].onmessage?.({
        data: JSON.stringify(
          seqEvent(1, {
            type: "awaiting_approval",
            stage: "idea",
            preview: { title: "draft idea" },
          })
        ),
      } as MessageEvent);
    });

    const editButton = await screen.findByRole("button", { name: /直接编辑/ });
    fireEvent.click(editButton);
  }

  it("surfaces the backend's 400 detail instead of silently doing nothing", async () => {
    await openEditor();

    const saveButton = screen.getByRole("button", { name: "保存修改" });
    fireEvent.click(saveButton);

    // Regression: a non-200 save response must not be swallowed — the user
    // needs to see the save didn't take effect, and why (e.g. the backend
    // rejected the stage name against the job's real pipeline stages).
    const errorNode = await screen.findByText("invalid stage: nope");
    expect(errorNode).toBeInTheDocument();
    // Same red border/bg treatment as the approve/retry actionError card.
    expect(errorNode.className).toContain("text-red-400");
    expect(errorNode.className).toContain("border-red-500/40");
  });
});

describe("JobDetailPage cancel job", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (method === "GET" && url === `${SERVER}/jobs/${JOB_ID}`) {
          return { ok: true, json: async () => ({}) } as Response;
        }
        if (method === "POST" && url === `${SERVER}/jobs/${JOB_ID}/cancel`) {
          // Contract: a queued/running job's status comes back UNCHANGED —
          // the real transition to "cancelled" arrives later via SSE.
          return { ok: true, json: async () => ({ job_id: JOB_ID, status: "queued" }) } as Response;
        }
        return { ok: true, json: async () => ({}) } as Response;
      })
    );
  });

  it("shows the cancel button while the job is queued (the default status on mount)", async () => {
    renderPage();
    expect(await screen.findByRole("button", { name: /取消任务/ })).toBeInTheDocument();
  });

  it("shows the cancel button during awaiting_approval", async () => {
    renderPage();
    act(() => {
      FakeEventSource.instances[0].onmessage?.({
        data: JSON.stringify(
          seqEvent(1, { type: "awaiting_approval", stage: "idea", preview: { title: "draft" } })
        ),
      } as MessageEvent);
    });
    expect(await screen.findByRole("button", { name: /取消任务/ })).toBeInTheDocument();
  });

  it("hides the cancel button once the job reaches a terminal status", async () => {
    renderPage();
    expect(await screen.findByRole("button", { name: /取消任务/ })).toBeInTheDocument();

    act(() => {
      FakeEventSource.instances[0].onmessage?.({
        data: JSON.stringify(seqEvent(1, { type: "job_completed", render_url: "/media/x.mp4" })),
      } as MessageEvent);
    });

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /取消任务/ })).not.toBeInTheDocument();
    });
  });

  it("POSTs to /jobs/{id}/cancel on click and shows a loading state while in flight", async () => {
    let resolvePost!: (v: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (method === "GET" && url === `${SERVER}/jobs/${JOB_ID}`) {
          return { ok: true, json: async () => ({}) } as Response;
        }
        if (method === "POST" && url === `${SERVER}/jobs/${JOB_ID}/cancel`) {
          return new Promise<Response>((resolve) => {
            resolvePost = resolve;
          });
        }
        return { ok: true, json: async () => ({}) } as Response;
      })
    );

    renderPage();
    const button = await screen.findByRole("button", { name: /取消任务/ });
    fireEvent.click(button);

    expect(await screen.findByRole("button", { name: /取消中/ })).toBeInTheDocument();

    resolvePost({ ok: true, json: async () => ({ job_id: JOB_ID, status: "queued" }) } as Response);

    // Request settled — button returns to its idle label (still cancellable,
    // since the response reported status unchanged).
    expect(await screen.findByRole("button", { name: /取消任务/ })).toBeInTheDocument();
  });

  it("resolves an awaiting_approval job to a terminal status immediately from the response body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (method === "GET" && url === `${SERVER}/jobs/${JOB_ID}`) {
          return { ok: true, json: async () => ({}) } as Response;
        }
        if (method === "POST" && url === `${SERVER}/jobs/${JOB_ID}/cancel`) {
          return { ok: true, json: async () => ({ job_id: JOB_ID, status: "cancelled" }) } as Response;
        }
        return { ok: true, json: async () => ({}) } as Response;
      })
    );

    renderPage();
    act(() => {
      FakeEventSource.instances[0].onmessage?.({
        data: JSON.stringify(
          seqEvent(1, { type: "awaiting_approval", stage: "idea", preview: { title: "draft" } })
        ),
      } as MessageEvent);
    });

    const button = await screen.findByRole("button", { name: /取消任务/ });
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByTestId("status-badge")).toHaveTextContent("已取消");
    });
    // The approval gate resolved to a terminal status, so its panel — and
    // the now-dead approve/reject buttons — must not linger on screen.
    expect(screen.queryByRole("button", { name: /批准/ })).not.toBeInTheDocument();
  });

  it("reflects the eventual cancellation of a queued/running job via the SSE stream", async () => {
    renderPage();
    const button = await screen.findByRole("button", { name: /取消任务/ });
    fireEvent.click(button);

    // Status unchanged immediately per contract (still queued).
    await waitFor(() => {
      expect(screen.getByTestId("status-badge")).toHaveTextContent("排队中");
    });

    act(() => {
      FakeEventSource.instances[0].onmessage?.({
        data: JSON.stringify(seqEvent(2, { type: "job_cancelled" })),
      } as MessageEvent);
    });

    await waitFor(() => {
      expect(screen.getByTestId("status-badge")).toHaveTextContent("已取消");
    });
  });

  it("surfaces a cancel failure via the shared action-error card", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (method === "GET" && url === `${SERVER}/jobs/${JOB_ID}`) {
          return { ok: true, json: async () => ({}) } as Response;
        }
        if (method === "POST" && url === `${SERVER}/jobs/${JOB_ID}/cancel`) {
          return { ok: false, status: 404, json: async () => ({ detail: "Job not found" }) } as Response;
        }
        return { ok: true, json: async () => ({}) } as Response;
      })
    );

    renderPage();
    const button = await screen.findByRole("button", { name: /取消任务/ });
    fireEvent.click(button);

    expect(await screen.findByText("Job not found")).toBeInTheDocument();
  });
});
