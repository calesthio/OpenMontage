// T4 case 06 — Patterns that warn but don't block.
//
// Should be detected by lint_source.py with:
//   - r2hf/delay-render (warning) — drop the call; HF handles asset readiness
//   - r2hf/use-callback (warning) — decorative, drop the wrapper
//   - r2hf/use-memo    (warning) — decorative, drop the wrapper
//
// 0 blockers expected — the skill should still translate this composition
// after dropping the wrappers. delayRender is paired with continueRender via
// an empty-deps useEffect (mount-once side effect), which doesn't trip the
// use-effect-deps blocker.

import React, { useCallback, useMemo } from "react";
import { AbsoluteFill, delayRender, continueRender, useCurrentFrame, interpolate } from "remotion";

const handle = delayRender();
// Resolve the handle once at module load — no per-frame side effects.
queueMicrotask(() => continueRender(handle));

export const WarningsOnly: React.FC = () => {
  const frame = useCurrentFrame();

  // useCallback / useMemo — decorative for render-perf in React, no equivalent
  // needed in the seek-driven HF model.
  const opacity = useMemo(
    () => interpolate(frame, [0, 30], [0, 1], { extrapolateRight: "clamp" }),
    [frame],
  );
  const onMount = useCallback(() => {}, []);

  return (
    <AbsoluteFill style={{ opacity }} onClick={onMount}>
      <div>frame {frame}</div>
    </AbsoluteFill>
  );
};
