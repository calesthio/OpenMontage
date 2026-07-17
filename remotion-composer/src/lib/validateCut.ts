// Required-field table per cut.type, and the check that surfaces a mismatch.
//
// Why (audit 2026-07-16, visual review A3 — confirmed live twice): every
// SceneRenderer branch is guarded like `cut.type === "stat_card" && cut.stat`,
// so a cut that NAMES a type but omits its required field silently falls
// through to a later branch and renders as something else entirely. Real
// occurrences: 小兔子电视's `text_card` carrying a source mp4 and no text
// rendered as a raw video clip; an E2E test's `stat_card` with `text` instead
// of `stat` rendered as a plain text card, subtitle dropped. Both looked
// "fine" — just not what was authored, with nothing logged.
//
// This is deliberately NOT a hard failure: a render that mostly works is
// worth more than no render. The mismatch is logged to the render console
// (visible in video_compose's captured Remotion output) and collected for
// the on-screen dev overlay.

/** Required prop(s) per scene type. Mirrors SCENE_TYPES.md's "Required" column. */
export const CUT_REQUIRED_FIELDS: Record<string, string[]> = {
  text_card: ["text"],
  stat_card: ["stat"],
  callout: ["text"],
  comparison: ["leftLabel", "rightLabel", "leftValue", "rightValue"],
  hero_title: ["text"],
  bar_chart: ["chartData"],
  line_chart: ["chartSeries"],
  pie_chart: ["chartData"],
  kpi_grid: ["chartData"],
  progress_bar: ["progress"],
  anime_scene: ["images"],
  terminal_scene: ["steps"],
  screenshot_scene: ["backgroundImage", "screenshotSteps"],
};

export interface CutIssue {
  id: string;
  type: string;
  missing: string[];
  message: string;
}

/**
 * Returns an issue when `cut` names a known scene type but lacks a field that
 * type's renderer requires — i.e. when it is about to render as some OTHER
 * scene type. Unknown/absent types are not our business (a cut with only a
 * `source` legitimately routes by media kind).
 */
export function validateCut(cut: Record<string, unknown>): CutIssue | null {
  const type = typeof cut.type === "string" ? cut.type : "";
  const required = CUT_REQUIRED_FIELDS[type];
  if (!required) return null;

  const missing = required.filter((f) => {
    const v = cut[f];
    if (v === undefined || v === null || v === "") return true;
    if (Array.isArray(v) && v.length === 0) return true;
    return false;
  });
  if (missing.length === 0) return null;

  const id = typeof cut.id === "string" ? cut.id : "(unnamed cut)";
  return {
    id,
    type,
    missing,
    message:
      `cut ${id}: type "${type}" requires ${missing.map((m) => `\`${m}\``).join(", ")} — ` +
      `absent, so this scene will NOT render as a ${type}. See SCENE_TYPES.md.`,
  };
}

/** Validate every cut, logging each issue once. Returns all issues. */
export function validateCuts(cuts: Record<string, unknown>[]): CutIssue[] {
  const issues: CutIssue[] = [];
  for (const cut of cuts ?? []) {
    const issue = validateCut(cut);
    if (issue) {
      issues.push(issue);
      // eslint-disable-next-line no-console
      console.warn(`[openmontage] ${issue.message}`);
    }
  }
  return issues;
}
