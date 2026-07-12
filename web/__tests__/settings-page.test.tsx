import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import SettingsPage from "@/app/dashboard/settings/page";

const SERVER = "http://localhost:8000";

// Regression: the system-status card used to fetch health/jobs/brands/
// capabilities exactly once on mount (`useEffect(() => { load(); }, [])`
// with no interval). If the backend was down at load time and later
// recovered (or vice versa), the "● 离线"/"● 在线" badge stayed stuck until
// the user manually reloaded the whole page. Fixed by re-polling `load()` on
// a 30s interval, mirroring the dashboard job list's 8s polling pattern.
describe("SettingsPage periodic re-poll", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let serverUp: boolean;

  function jsonOk(body: unknown) {
    return Promise.resolve({ ok: true, json: async () => body } as Response);
  }

  beforeEach(() => {
    vi.useFakeTimers();
    serverUp = true;
    fetchMock = vi.fn(async (url: string) => {
      if (url === `${SERVER}/health`) {
        return jsonOk(serverUp ? { status: "ok", service: "openmontage" } : { status: "down" });
      }
      if (url === `${SERVER}/jobs`) {
        return jsonOk({ jobs: serverUp ? [{ job_id: "1" }, { job_id: "2" }] : [] });
      }
      if (url === `${SERVER}/brands`) {
        return jsonOk({ brand_kits: serverUp ? [{ name: "b1" }] : [] });
      }
      if (url === `${SERVER}/system/capabilities`) {
        return jsonOk({
          backends: {
            storage: { active: "local_fs", available: ["local_fs"], planned: [] },
            queue: { active: "in_process", available: ["in_process"], planned: [] },
            auth: { active: "none", available: ["none"], planned: [], enforced: false },
          },
          llm_model: "gpt-test",
          model_catalog: { video_models: [], image_models: [], tts_models: [] },
        });
      }
      return jsonOk({});
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("populates status on initial load", async () => {
    await act(async () => {
      render(<SettingsPage />);
      // Flush the initial async load() call scheduled inside useEffect.
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(screen.getByText("● 在线")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument(); // 历史项目数
    expect(screen.getByText("1")).toBeInTheDocument(); // 品牌 Kit 数
  });

  it("re-polls on the interval and updates the badge when backend state changes", async () => {
    await act(async () => {
      render(<SettingsPage />);
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByText("● 在线")).toBeInTheDocument();

    const callsAfterInitialLoad = fetchMock.mock.calls.length;

    // Backend goes down between polls.
    serverUp = false;

    // Advance past the 30s re-poll interval and flush the resulting promises.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30000);
    });

    expect(screen.getByText("● 离线")).toBeInTheDocument();
    // A second full round of health/jobs/brands/capabilities calls fired.
    expect(fetchMock.mock.calls.length).toBeGreaterThan(callsAfterInitialLoad);
  });

  it("clears the interval on unmount so no further polling occurs", async () => {
    const clearIntervalSpy = vi.spyOn(global, "clearInterval");
    let unmount!: () => void;
    await act(async () => {
      const result = render(<SettingsPage />);
      unmount = result.unmount;
      await vi.advanceTimersByTimeAsync(0);
    });

    unmount();

    expect(clearIntervalSpy).toHaveBeenCalled();
    clearIntervalSpy.mockRestore();
  });
});
