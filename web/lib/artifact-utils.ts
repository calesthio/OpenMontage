// Shared helpers for rendering pipeline artifacts in the web UI
// (roadmap 1.2/1.4). Mirrors backlot/ui/board.js's normalizeDecision — the
// two renderers must agree on what a decision entry means.

export type DecisionEntry = {
  category?: string;
  subject?: string;
  selected?: string;
  reason?: string;
  confidence?: number;
  stage?: string;
  options_considered?: Array<
    string | { option_id?: string; label?: string; score?: number; rejected_because?: string }
  >;
  [key: string]: unknown;
};

export type NormalizedDecision = {
  category: string;
  subject: string;
  selected: string;
  reason: string;
  confidence?: number;
  options: Array<{ option_id?: string; label?: string; score?: number; rejected_because?: string }>;
  revised: number;
  raw: DecisionEntry;
};

/**
 * Real runs write the same decision under several field spellings — the
 * schema deliberately accepts recommendation/rationale/notes as additional
 * properties, and options_considered entries may be bare strings. Reading
 * only `selected`/`reason` left 6 of 7 real projects rendering blank rails.
 */
export function normalizeDecision(d: DecisionEntry): Omit<NormalizedDecision, "revised"> {
  const selected =
    (d.selected as string) ??
    (d["recommendation"] as string) ??
    (d["choice"] as string) ??
    "";
  const reason =
    (d.reason as string) ??
    (d["recommendation_rationale"] as string) ??
    (d["rationale"] as string) ??
    (d["notes"] as string) ??
    "";
  const options = (d.options_considered || []).map((o) =>
    typeof o === "string" ? { option_id: o, label: o } : o
  );
  return {
    category: d.category || "decision",
    subject: d.subject || "",
    selected,
    reason,
    confidence: typeof d.confidence === "number" ? d.confidence : undefined,
    options,
    raw: d,
  };
}

/**
 * Collapse a decision log to the CURRENT entry per (category, subject) pair
 * — the log is append-only history; a changed decision appends a new entry
 * with the same pair (see AGENT_GUIDE.md "Re-log Changed Decisions").
 * Returns latest-first, with `revised` counting superseded entries.
 */
export function currentDecisions(decisions: DecisionEntry[]): NormalizedDecision[] {
  const current = new Map<string, NormalizedDecision & { order: number }>();
  decisions.forEach((d, i) => {
    const n = normalizeDecision(d);
    const key = `${n.category}::${n.subject}`;
    const prev = current.get(key);
    current.set(key, { ...n, order: i, revised: prev ? prev.revised + 1 : 0 });
  });
  return [...current.values()].sort((a, b) => b.order - a.order);
}

/**
 * Best-effort mapping of an artifact-manifest path to the FastAPI /media
 * mount. Paths in real manifests appear as absolute paths, project-relative
 * ("assets/video/x.mp4"), or repo-relative ("projects/<name>/assets/...").
 */
export function assetMediaPath(projectName: string | null, path: string | null | undefined): string | null {
  if (!path || !projectName) return null;
  const norm = path.replace(/\\/g, "/");
  const marker = `projects/${projectName}/`;
  const idx = norm.indexOf(marker);
  if (idx >= 0) return `/media/${projectName}/${norm.slice(idx + marker.length)}`;
  if (!norm.startsWith("/")) return `/media/${projectName}/${norm}`;
  return null;   // absolute path outside the project — not servable
}
