import type { ReactNode } from "react";

// Shared button-pill selector for the new-project wizard's repeated
// choose-one-of-N groups (video/image/TTS model pickers, the A/B compare
// model B picker, and the duration picker). Each call site keeps its own
// domain knowledge — label lookup via `renderLabel`, which ids are
// unavailable via `disabledIds`, and any onChange side effects (e.g. the
// video-model picker nudging model B off a now-conflicting choice) — this
// component only owns the pill markup and the active/disabled state classes,
// kept identical to the pre-extraction per-group JSX so none of the groups
// change appearance or behavior.
type PillSelectProps = {
  options: string[];
  value: string;
  onChange: (id: string) => void;
  disabledIds?: string[] | Set<string>;
  renderLabel?: (id: string) => ReactNode;
};

export function PillSelect({
  options,
  value,
  onChange,
  disabledIds,
  renderLabel = (id) => id,
}: PillSelectProps) {
  const disabledSet = disabledIds instanceof Set ? disabledIds : new Set(disabledIds ?? []);
  return (
    <div className="flex gap-2 flex-wrap">
      {options.map((id) => {
        const isDisabled = disabledSet.has(id);
        const selected = value === id;
        return (
          <button
            key={id}
            type="button"
            disabled={isDisabled}
            onClick={() => onChange(id)}
            // Selection state must not be color-only (roadmap 3.6 /
            // WCAG 1.4.1): aria-pressed for assistive tech, a ✓ glyph for
            // everyone else.
            aria-pressed={selected}
            className={`px-4 py-1.5 rounded-md text-sm border transition-colors ${
              isDisabled
                ? "border-border/40 opacity-40 cursor-not-allowed"
                : selected
                  ? "bg-foreground text-background border-foreground"
                  : "border-border hover:border-foreground/40"
            }`}
          >
            {selected && <span aria-hidden>✓ </span>}
            {renderLabel(id)}
          </button>
        );
      })}
    </div>
  );
}
