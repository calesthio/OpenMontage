// Roadmap batch 2 UI: per-scene keep/reroll at the assets gate.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ApprovalPanel } from "@/components/approval-panel";

const SERVER = "http://localhost:8000";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({}) }) as Response));
});
afterEach(() => {
  vi.unstubAllGlobals();
});

const manifestPreview = {
  assets: [
    { id: "a1", type: "image", path: "assets/images/1.png", prompt: "镜头一" },
    { id: "a2", type: "image", path: "assets/images/2.png", prompt: "镜头二" },
  ],
};

function renderAssetsGate() {
  return render(
    <ApprovalPanel
      jobId="j1"
      stage="assets"
      gate={null}
      preview={manifestPreview}
      previewArtifact="asset_manifest"
      serverBase={SERVER}
      projectName="p"
      onError={() => {}}
      onApproved={() => {}}
    />
  );
}

describe("per-scene keep/reroll at the assets gate", () => {
  it("marks assets for reroll and sends rejected_asset_ids on reject", async () => {
    renderAssetsGate();
    const toggles = screen.getAllByText("✓ 采用(点击换一版)");
    expect(toggles).toHaveLength(2);
    fireEvent.click(toggles[1]);   // mark a2 for reroll
    expect(screen.getByText("↻ 将换一版(点击改为采用)")).toBeTruthy();

    const rejectBtn = screen.getByText("↻ 重做选中的 1 个素材");
    // No feedback text required once specific assets are marked.
    expect((rejectBtn.closest("button") as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(rejectBtn);

    await waitFor(() => {
      const call = (fetch as ReturnType<typeof vi.fn>).mock.calls.find(
        ([url]) => String(url).includes("/approve")
      );
      expect(call).toBeTruthy();
      const body = JSON.parse(call![1].body as string);
      expect(body.action).toBe("reject");
      expect(body.rejected_asset_ids).toEqual(["a2"]);
    });
  });

  it("keeps the plain reject flow requiring feedback when nothing is marked", () => {
    renderAssetsGate();
    const rejectBtn = screen.getByText("↩ 打回重做");
    expect((rejectBtn.closest("button") as HTMLButtonElement).disabled).toBe(true);
  });
});
