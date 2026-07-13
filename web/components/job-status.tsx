// Presentational pieces for the job detail view, extracted so their mapping
// logic (status → label/style, event → colour/label) is unit-testable without
// the SSE-driven page shell.

import { Button } from "@/components/ui/button";

export type SseEvent = {
  seq: number;
  type: string;
  ts: number;
  stage?: string;
  text?: string;
  tool?: string;
  summary?: string;
  artifact?: string;
  preview?: unknown;
  render_url?: string;
  // A/B variant job only (see wizard's "对比模式" toggle): sibling dict
  // alongside render_url, keyed by a short model-derived slug (e.g.
  // "ltx-2-3"), one entry per variant. Absent/undefined for a normal
  // (non-variant) job — render_url alone remains authoritative there.
  render_urls?: Record<string, string>;
  message?: string;
  cost_cny?: number;
  budget_cny?: number | null;
  gate?: string;
  stages?: string[];
  // tool_call: best-effort, captured before _enforce_model_choice's autofill
  // may run. asset_ready: the fully-resolved model that actually produced
  // this asset, plus its real per-call cost — see tool_bridge.py.
  model?: string | null;
};

// The union of every top-level stage name across all 13 pipeline_defs/*.yaml
// manifests, plus "budget" (a synthetic pseudo-stage used only for the
// budget-gate approval event, not a real pipeline stage). Different pipelines
// use different stage sets — e.g. cinematic has research+proposal, most others
// collapse both into a single "idea" stage — so this must cover the union, not
// just cinematic's shape. Extend when a new pipeline introduces a new stage
// name; STAGE_LABELS lookups always fall back to the raw name (see
// stageLabel()) so an unmapped name degrades to something readable, never to
// the literal string "undefined".
const STAGE_LABELS: Record<string, string> = {
  research: "调研", proposal: "提案", idea: "创意提案", script: "脚本",
  scene_plan: "分镜", character_design: "角色设计", rig_plan: "绑定规划",
  assets: "素材", edit: "剪辑", compose: "合成", publish: "发布",
  budget: "预算",
};

/** Stage display label with a safe fallback — never renders "undefined". */
export function stageLabel(stage: string | null | undefined): string {
  if (!stage) return "";
  return STAGE_LABELS[stage] ?? stage;
}

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  queued:            { label: "排队中", cls: "bg-muted text-muted-foreground border-border" },
  running:           { label: "生成中", cls: "bg-blue-500/20 text-blue-400 border-blue-500/30" },
  awaiting_approval: { label: "待审批", cls: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30" },
  completed:         { label: "已完成", cls: "bg-green-500/20 text-green-400 border-green-500/30" },
  failed:            { label: "失败",   cls: "bg-red-500/20 text-red-400 border-red-500/30" },
  cancelled:         { label: "已取消", cls: "bg-slate-500/20 text-slate-400 border-slate-500/30" },
};

// Style for a status the backend sent that isn't in STATUS_MAP — kept
// separate from STATUS_MAP.queued so a future restyle of "queued" can't
// accidentally change what an unknown status looks like.
const NEUTRAL_STATUS_CLS = "bg-muted text-muted-foreground border-border";

// Exported (along with EVENT_TYPE_LABELS below) so the contract test in
// web/__tests__/job-status.test.tsx can assert every backend event type in
// schemas/events.json is either mapped here or deliberately allowlisted as
// muted — this drift class recurred twice (commit 33a0273 fixed 7 unmapped
// types; "warning" was unmapped again after that).
export const EVENT_COLOR: Record<string, string> = {
  stage_started: "text-blue-400", stage_completed: "text-green-400",
  tool_call: "text-purple-400", artifact_written: "text-cyan-400",
  asset_ready: "text-emerald-400", awaiting_approval: "text-yellow-400",
  stage_approved: "text-green-400", stage_rejected: "text-orange-400",
  job_completed: "text-green-400", job_failed: "text-red-400", error: "text-red-400",
  job_started: "text-blue-400", stage_skipped: "text-muted-foreground",
  stage_retry: "text-orange-400", cost_updated: "text-slate-400",
  preview_ready: "text-emerald-400", job_cancelled: "text-slate-400",
  budget_exceeded: "text-red-400", budget_precall_block: "text-orange-400",
  // warning: non-fatal anomaly (e.g. stage_runner.py's render_report
  // path-divergence check) — orange like the other "attention but not
  // failure" types (stage_retry, budget_precall_block), so it's visually
  // distinct from muted chatter.
  warning: "text-orange-400",
};

// Chinese labels for event types that never carry a summary/text/artifact/
// message field from the backend (see server/app/runner/stage_runner.py and
// tool_bridge.py) — without this, eventLabel's fallback chain bottoms out on
// the raw English `type` string.
export const EVENT_TYPE_LABELS: Record<string, string> = {
  job_started: "任务开始", stage_skipped: "跳过阶段", stage_retry: "阶段重试",
  cost_updated: "费用更新", preview_ready: "预览就绪",
  budget_exceeded: "预算超限", budget_precall_block: "预算预检拦截",
  asset_ready: "素材生成完成", job_cancelled: "任务已取消",
  // The only current "warning" emit site (stage_runner.py's render_report
  // path-divergence check) always carries a message, so eventLabel shows
  // that; this label is the safety net for any future no-message warning.
  warning: "警告",
};

/** " · model · ¥cost" suffix, omitting whichever half is missing. Shared by
 * tool_call (model only, cost not known yet) and asset_ready (both, once the
 * call has actually succeeded) so the live log shows what's generating
 * without the operator digging through inputs_preview. */
function modelCostSuffix(ev: SseEvent): string {
  const parts: string[] = [];
  if (ev.model) parts.push(ev.model);
  if (typeof ev.cost_cny === "number") parts.push(`¥${ev.cost_cny.toFixed(4)}`);
  return parts.length ? ` · ${parts.join(" · ")}` : "";
}

/** The human-facing label chosen for an event row (precedence matters). */
export function eventLabel(ev: SseEvent): string {
  if (ev.type === "tool_call" || ev.type === "asset_ready") {
    const base = ev.summary ?? (ev.tool ? `${EVENT_TYPE_LABELS[ev.type]}: ${ev.tool}` : EVENT_TYPE_LABELS[ev.type]);
    return `${base}${modelCostSuffix(ev)}`;
  }
  return ev.summary ?? ev.text ?? ev.artifact ?? ev.message ?? EVENT_TYPE_LABELS[ev.type] ?? ev.type;
}

/**
 * The backend returns render/preview URLs as root-relative paths
 * ("/media/...") meant for ITS OWN origin (the FastAPI server's static
 * mount). A bare <video src="/media/...">  resolves against the CURRENT
 * page's origin instead — the Next.js dev server, on a different port/host
 * — which 404s and the video silently fails to load (confirmed live:
 * readyState 0, networkState NETWORK_NO_SOURCE, no visible error to the
 * user beyond a blank player). Root-relative media paths must be resolved
 * against the backend origin explicitly.
 */
export function mediaUrl(serverBase: string, path: string | null | undefined): string | null {
  if (!path) return null;
  if (/^https?:\/\//i.test(path) || path.startsWith("//")) return path;   // already absolute
  const base = serverBase.endsWith("/") ? serverBase.slice(0, -1) : serverBase;
  return `${base}${path.startsWith("/") ? "" : "/"}${path}`;
}

/**
 * Renders a job's render/preview video(s) — unifying what used to be two
 * parallel code paths on the job detail page (one for the interim
 * compose-stage preview, one for the final completed render), each hand-
 * duplicating the singular-vs-A/B-variants branch. `urls` (the A/B variants
 * dict, keyed by model-derived slug — see SseEvent.render_urls above) takes
 * precedence when non-empty; `url` (the singular field) is the source of
 * truth otherwise. `withDownload` gates the per-video download button, shown
 * only for the final render, never the interim preview.
 */
export function VideoGallery({
  serverBase,
  url,
  urls,
  withDownload = false,
}: {
  serverBase: string;
  url: string | null;
  urls?: Record<string, string> | null;
  withDownload?: boolean;
}) {
  // Matches the two call sites' previous inline spacing: the final-render
  // grid item (video + label + download button) used space-y-2; the
  // interim-preview grid item (video + label only) used space-y-1.
  const itemSpacing = withDownload ? "space-y-2" : "space-y-1";

  if (urls && Object.keys(urls).length > 0) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {Object.entries(urls).map(([slug, u]) => (
          <div key={slug} className={itemSpacing}>
            <video src={mediaUrl(serverBase, u) ?? undefined} controls className="w-full rounded-lg bg-black aspect-video" />
            <span className="text-xs text-muted-foreground block">版本: {slug}</span>
            {withDownload && (
              <a href={mediaUrl(serverBase, u) ?? undefined} download>
                <Button variant="outline" className="w-full">下载 MP4</Button>
              </a>
            )}
          </div>
        ))}
      </div>
    );
  }

  return (
    <>
      <video src={mediaUrl(serverBase, url) ?? undefined} controls className="w-full rounded-lg bg-black aspect-video" />
      {withDownload && (
        <a href={mediaUrl(serverBase, url) ?? undefined} download>
          <Button variant="outline" className="w-full">下载 MP4</Button>
        </a>
      )}
    </>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const s = STATUS_MAP[status];
  return (
    <span
      data-testid="status-badge"
      className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${s?.cls ?? NEUTRAL_STATUS_CLS}`}
    >
      {s?.label ?? status}
    </span>
  );
}

export function EventRow({ ev }: { ev: SseEvent }) {
  const color = EVENT_COLOR[ev.type] ?? "text-muted-foreground";
  const ts = new Date(ev.ts * 1000).toLocaleTimeString("zh-CN", { hour12: false });
  return (
    <div className="flex gap-2 items-start">
      <span className="text-muted-foreground/50 shrink-0">{ts}</span>
      <span className={`shrink-0 ${color}`}>[{ev.stage ?? ev.type}]</span>
      <span className="text-foreground/70 break-all">{eventLabel(ev)}</span>
    </div>
  );
}
