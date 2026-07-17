"use client";

// Structured artifact renderers (roadmap 1.2): the approval panel used to
// show every artifact — a 12-image asset manifest included — as one raw JSON
// box. Each canonical artifact type gets a purpose-built view; everything
// falls back to a readable key-value summary, and the raw JSON stays one
// click away behind a <details> ("</> 查看原始 JSON").

import { mediaUrl } from "@/components/job-status";
import { assetMediaPath, currentDecisions, type DecisionEntry } from "@/lib/artifact-utils";

type Dict = Record<string, unknown>;

function fmtSeconds(v: unknown): string {
  return typeof v === "number" ? `${Math.round(v * 10) / 10}s` : "";
}

// ── script ───────────────────────────────────────────────────────────────────

function ScriptView({ value }: { value: Dict }) {
  const sections = (value.sections as Dict[]) || [];
  if (!sections.length) return null;
  return (
    <div className="space-y-2" data-testid="artifact-script">
      {typeof value.title === "string" && (
        <p className="text-sm font-medium">{value.title}
          {typeof value.total_duration_seconds === "number" && (
            <span className="text-xs text-muted-foreground ml-2">
              共 {fmtSeconds(value.total_duration_seconds)}
            </span>
          )}
        </p>
      )}
      {sections.map((s, i) => (
        <div key={(s.id as string) ?? i} className="bg-muted/40 rounded p-2.5">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs font-medium text-muted-foreground">
              {(s.label as string) || (s.id as string) || `段落 ${i + 1}`}
            </span>
            <span className="text-[10px] text-muted-foreground font-mono shrink-0">
              {fmtSeconds(s.start_seconds)}–{fmtSeconds(s.end_seconds)}
            </span>
          </div>
          <p className="text-sm mt-1 whitespace-pre-wrap">{s.text as string}</p>
          {typeof s.speaker_directions === "string" && s.speaker_directions && (
            <p className="text-xs text-muted-foreground mt-1">🎙 {s.speaker_directions}</p>
          )}
        </div>
      ))}
    </div>
  );
}

// ── scene_plan ───────────────────────────────────────────────────────────────

function ScenePlanView({ value }: { value: Dict }) {
  const scenes = (value.scenes as Dict[]) || [];
  if (!scenes.length) return null;
  return (
    <div className="space-y-1.5" data-testid="artifact-scene-plan">
      {scenes.map((s, i) => (
        <div key={(s.id as string) ?? i} className="bg-muted/40 rounded p-2.5 flex gap-3">
          <span className="text-xs font-mono text-muted-foreground shrink-0 pt-0.5">
            {i + 1}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm">{(s.description as string) || (s.id as string)}</p>
            <p className="text-[10px] text-muted-foreground mt-0.5 truncate">
              {[
                s.type,
                `${fmtSeconds(s.start_seconds)}–${fmtSeconds(s.end_seconds)}`,
                s.framing,
                s.movement,
              ].filter(Boolean).join(" · ")}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── asset_manifest ───────────────────────────────────────────────────────────

function AssetManifestView({
  value, serverBase, projectName, rejectedIds, onToggleReject,
}: {
  value: Dict;
  serverBase: string;
  projectName: string | null;
  /** Per-scene keep/reroll (roadmap 2.3): ids marked for regeneration. */
  rejectedIds?: string[];
  onToggleReject?: (id: string) => void;
}) {
  const assets = (value.assets as Dict[]) || [];
  if (!assets.length) return null;
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2" data-testid="artifact-asset-manifest">
      {assets.map((a, i) => {
        const path = (a.path as string) || "";
        const url = mediaUrl(serverBase, assetMediaPath(projectName, path));
        const type = (a.type as string) || "";
        const isImage = type.includes("image") || /\.(png|jpe?g|webp)$/i.test(path);
        const isVideo = type.includes("video") || /\.(mp4|webm|mov)$/i.test(path);
        const id = (a.id as string) ?? String(i);
        const rejected = rejectedIds?.includes(id) ?? false;
        return (
          <div
            key={id}
            className={`bg-muted/40 rounded-md overflow-hidden ${rejected ? "ring-2 ring-orange-500/70" : ""}`}
          >
            {url && isImage ? (
              <img src={url} alt={(a.prompt as string) || path} title={(a.prompt as string) || ""}
                   className="w-full h-24 object-cover bg-black" loading="lazy" />
            ) : url && isVideo ? (
              <video src={url} muted preload="metadata" controls className="w-full h-24 object-cover bg-black" />
            ) : (
              <div className="w-full h-24 flex items-center justify-center text-2xl bg-muted/60" aria-hidden>
                {type.includes("audio") || type.includes("music") || type.includes("narration") ? "🎵" : "📄"}
              </div>
            )}
            <div className="p-1.5 space-y-0.5">
              <p className="text-[10px] truncate" title={(a.prompt as string) || ""}>
                {(a.prompt as string) || (a.id as string) || path.split("/").pop()}
              </p>
              <p className="text-[10px] text-muted-foreground truncate">
                {[a.model as string, typeof a.cost_usd === "number" ? `¥${(a.cost_usd as number).toFixed(2)}` : null]
                  .filter(Boolean).join(" · ")}
              </p>
              {onToggleReject && (
                // Midjourney's U/V pair in domain language: 采用 keeps (free
                // — the cache reuses it), 换一版 marks for paid reroll.
                <button
                  type="button"
                  onClick={() => onToggleReject(id)}
                  className={`w-full text-[11px] rounded border px-1 py-0.5 mt-0.5 ${
                    rejected
                      ? "border-orange-500/70 text-orange-400"
                      : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {rejected ? "↻ 将换一版(点击改为采用)" : "✓ 采用(点击换一版)"}
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── decision_log ─────────────────────────────────────────────────────────────

function DecisionLogView({ value }: { value: Dict }) {
  const decisions = currentDecisions(((value.decisions as DecisionEntry[]) || []));
  if (!decisions.length) return null;
  return (
    <div className="space-y-2" data-testid="artifact-decision-log">
      {decisions.slice(0, 10).map((d, i) => {
        const pickLabel =
          d.options.find((o) => (o.option_id ?? o.label) === d.selected)?.label || d.selected;
        const alts = d.options.filter((o) => (o.option_id ?? o.label) !== d.selected);
        return (
          <div key={i} className="bg-muted/40 rounded p-2.5">
            <p className="text-[10px] text-muted-foreground">
              {d.category}
              {d.confidence != null && ` · 置信度 ${Math.round(d.confidence * 100)}%`}
              {d.revised > 0 && <span className="text-yellow-400"> · 已修订</span>}
            </p>
            <p className="text-sm mt-0.5">
              {d.subject} <span className="text-muted-foreground">→</span>{" "}
              <span className="font-medium">{pickLabel}</span>
            </p>
            {d.reason && (
              <p className="text-xs text-muted-foreground mt-1 whitespace-pre-wrap">{d.reason}</p>
            )}
            {alts.length > 0 && (
              <p className="text-[10px] text-muted-foreground mt-1">
                也考虑过:{alts.slice(0, 3).map((o) => o.label ?? o.option_id).join(" · ")}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── generic fallback ─────────────────────────────────────────────────────────

function KeyValueView({ value }: { value: Dict }) {
  const entries = Object.entries(value).filter(([k]) => k !== "version");
  if (!entries.length) return null;
  return (
    <div className="space-y-1" data-testid="artifact-keyvalue">
      {entries.slice(0, 12).map(([k, v]) => (
        <div key={k} className="flex gap-2 text-sm">
          <span className="text-muted-foreground shrink-0">{k}:</span>
          <span className="min-w-0 break-words">
            {typeof v === "string" ? v
              : typeof v === "number" || typeof v === "boolean" ? String(v)
              : Array.isArray(v) ? `[${v.length} 项]`
              : v == null ? "—" : "{…}"}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── registry + shell ─────────────────────────────────────────────────────────

export function ArtifactView({
  name,
  value,
  serverBase,
  projectName,
  rejectedIds,
  onToggleReject,
}: {
  name: string | null;
  value: unknown;
  serverBase: string;
  projectName: string | null;
  /** asset_manifest only: per-scene keep/reroll selection (roadmap 2.3). */
  rejectedIds?: string[];
  onToggleReject?: (id: string) => void;
}) {
  if (value == null || typeof value !== "object") return null;
  const v = value as Dict;
  let structured: React.ReactNode = null;
  if (name === "script") structured = <ScriptView value={v} />;
  else if (name === "scene_plan") structured = <ScenePlanView value={v} />;
  else if (name === "asset_manifest")
    structured = (
      <AssetManifestView
        value={v}
        serverBase={serverBase}
        projectName={projectName}
        rejectedIds={rejectedIds}
        onToggleReject={onToggleReject}
      />
    );
  else if (name === "decision_log") structured = <DecisionLogView value={v} />;
  else structured = <KeyValueView value={v} />;

  return (
    <div className="space-y-2">
      {structured && <div className="max-h-96 overflow-auto">{structured}</div>}
      <details>
        <summary className="text-xs text-muted-foreground cursor-pointer select-none">
          {"</> 查看原始 JSON"}
        </summary>
        <pre className="text-xs bg-muted/50 rounded p-3 overflow-auto max-h-64 whitespace-pre-wrap mt-1">
          {JSON.stringify(value, null, 2)}
        </pre>
      </details>
    </div>
  );
}
