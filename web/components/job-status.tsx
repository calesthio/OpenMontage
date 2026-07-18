// Presentational pieces for the job detail view, extracted so their mapping
// logic (status → label/style, event → colour/label) is unit-testable without
// the SSE-driven page shell.

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
  message?: string;
  cost_cny?: number;
  budget_cny?: number | null;
  gate?: string;
  stages?: string[];
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
};

const EVENT_COLOR: Record<string, string> = {
  stage_started: "text-blue-400", stage_completed: "text-green-400",
  tool_call: "text-purple-400", artifact_written: "text-cyan-400",
  asset_ready: "text-emerald-400", awaiting_approval: "text-yellow-400",
  stage_approved: "text-green-400", stage_rejected: "text-orange-400",
  job_completed: "text-green-400", job_failed: "text-red-400", error: "text-red-400",
};

/** The human-facing label chosen for an event row (precedence matters). */
export function eventLabel(ev: SseEvent): string {
  return ev.summary ?? ev.text ?? ev.artifact ?? ev.message ?? ev.type;
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
  if (/^https?:\/\//i.test(path)) return path;   // already absolute
  return `${serverBase}${path.startsWith("/") ? "" : "/"}${path}`;
}

export function StatusBadge({ status }: { status: string }) {
  const s = STATUS_MAP[status] ?? STATUS_MAP.queued;
  return (
    <span
      data-testid="status-badge"
      className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${s.cls}`}
    >
      {s.label}
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
