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
};

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
