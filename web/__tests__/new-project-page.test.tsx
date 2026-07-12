import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import NewProjectPage from "@/app/dashboard/new/page";

const SERVER = "http://localhost:8000";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// Builds a fetch stub that answers /brands, /pipelines and /system/capabilities
// with harmless empty payloads (the wizard falls back to FALLBACK_MODEL_CATALOG
// when /system/capabilities doesn't resolve a model_catalog, same as prod),
// and routes POST /jobs to the caller-supplied handler so each test can
// control the job-creation response.
function mockFetch(jobsHandler: (init?: RequestInit) => Response | Promise<Response>) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (method === "GET" && url === `${SERVER}/brands`) {
      return { ok: true, json: async () => ({ brand_kits: [] }) } as Response;
    }
    if (method === "GET" && url === `${SERVER}/pipelines`) {
      return { ok: true, json: async () => ({ pipelines: [] }) } as Response;
    }
    if (method === "POST" && url === `${SERVER}/jobs`) {
      return jobsHandler(init);
    }
    return { ok: true, json: async () => ({}) } as Response;
  });
}

async function goToWizardAndFillBrand() {
  render(<NewProjectPage />);
  const marketingCard = await screen.findByText("营销宣传片");
  fireEvent.click(marketingCard);
  const brandNameInput = await screen.findByPlaceholderText("例：小狗牌咖啡机");
  fireEvent.change(brandNameInput, { target: { value: "我的品牌" } });
}

describe("NewProjectPage job-creation failure handling", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("surfaces a network failure inline (not via alert) and resets the loading flag", async () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    vi.stubGlobal(
      "fetch",
      mockFetch(() => Promise.reject(new Error("network down")))
    );

    await goToWizardAndFillBrand();
    fireEvent.click(screen.getByRole("button", { name: /开始 AI 生产/ }));

    // Regression: this used to be a raw browser alert() instead of the
    // styled inline error-card pattern used elsewhere in the app (e.g. the
    // job detail page's approve/retry failure handling).
    expect(
      await screen.findByText("创建失败：网络错误，请检查后端是否可访问")
    ).toBeInTheDocument();
    expect(alertSpy).not.toHaveBeenCalled();

    // Without a try/catch around the rejected fetch, `loading` was never
    // reset and the button stayed stuck on "提交中…" forever.
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /开始 AI 生产/ })).toBeEnabled();
    });

    alertSpy.mockRestore();
  });

  it("surfaces a non-ok job-creation response inline instead of via alert()", async () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    vi.stubGlobal(
      "fetch",
      mockFetch(
        async () =>
          ({
            ok: false,
            status: 400,
            json: async () => ({ detail: "预算不能为负数" }),
          }) as Response
      )
    );

    await goToWizardAndFillBrand();
    fireEvent.click(screen.getByRole("button", { name: /开始 AI 生产/ }));

    expect(await screen.findByText("预算不能为负数")).toBeInTheDocument();
    expect(alertSpy).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /开始 AI 生产/ })).toBeEnabled();
    });

    alertSpy.mockRestore();
  });
});

describe("NewProjectPage IndexTTS emo_text/use_emo_text consistency", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does not send use_emo_text: true when emo_text is left empty", async () => {
    let sentBody: { options?: { tts_emotion?: Record<string, unknown> } } | null = null;
    vi.stubGlobal(
      "fetch",
      mockFetch(async (init) => {
        sentBody = JSON.parse((init?.body as string) ?? "{}");
        return { ok: true, json: async () => ({ job_id: "job-1" }) } as Response;
      })
    );

    await goToWizardAndFillBrand();

    fireEvent.click(screen.getByRole("button", { name: "IndexTTS" }));
    fireEvent.click(screen.getByRole("checkbox", { name: /使用情绪文字提示/ }));

    // The half-configured state (checked, no text) should be visibly
    // explained, not silently sent to the backend as a working config.
    expect(
      await screen.findByText("留空则不会启用情绪文字引导（需要填写文字才能生效）。")
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /开始 AI 生产/ }));

    await waitFor(() => expect(sentBody).not.toBeNull());
    // Regression: this used to send use_emo_text: true with no emo_text,
    // asking maas_tts for emotion-text-guided synthesis with nothing to
    // guide it.
    expect(sentBody!.options!.tts_emotion!.use_emo_text).toBe(false);
    expect(sentBody!.options!.tts_emotion!.emo_text).toBeUndefined();
  });

  it("sends use_emo_text: true with emo_text when the field is filled in", async () => {
    let sentBody: { options?: { tts_emotion?: Record<string, unknown> } } | null = null;
    vi.stubGlobal(
      "fetch",
      mockFetch(async (init) => {
        sentBody = JSON.parse((init?.body as string) ?? "{}");
        return { ok: true, json: async () => ({ job_id: "job-1" }) } as Response;
      })
    );

    await goToWizardAndFillBrand();

    fireEvent.click(screen.getByRole("button", { name: "IndexTTS" }));
    fireEvent.click(screen.getByRole("checkbox", { name: /使用情绪文字提示/ }));
    fireEvent.change(screen.getByPlaceholderText("例：兴奋、低声细语、悲伤…"), {
      target: { value: "兴奋" },
    });

    fireEvent.click(screen.getByRole("button", { name: /开始 AI 生产/ }));

    await waitFor(() => expect(sentBody).not.toBeNull());
    expect(sentBody!.options!.tts_emotion!.use_emo_text).toBe(true);
    expect(sentBody!.options!.tts_emotion!.emo_text).toBe("兴奋");
  });
});

describe("NewProjectPage budget-gate guidance", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows a static minimum-budget hint near the budget field", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch(async () => ({ ok: true, json: async () => ({}) }) as Response)
    );

    await goToWizardAndFillBrand();

    expect(screen.getByText(/建议预算不低于 ¥50 起步/)).toBeInTheDocument();
  });
});
