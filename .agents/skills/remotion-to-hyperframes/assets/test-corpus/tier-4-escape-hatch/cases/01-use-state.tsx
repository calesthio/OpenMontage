// T4 case 01 — useState drives animation.
//
// Should be detected by lint_source.py as blocker r2hf/use-state.
// The skill should refuse to translate and recommend the runtime interop
// pattern from PR #214.
//
// Why this is a blocker: useState is React's component-local mutable state.
// HF's seek-driven model produces deterministic frames from a single time
// value — there's no per-frame React render cycle to update state on.

import React, { useState } from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

export const StateDriven: React.FC = () => {
  const frame = useCurrentFrame();
  const [hue, setHue] = useState(0);

  // Even if this looks innocuous, the setHue call breaks determinism: HF
  // can't reproduce React state mutations across seeks.
  if (frame % 30 === 0 && hue < 360) {
    setHue((h) => h + 30);
  }

  return (
    <AbsoluteFill style={{ background: `hsl(${hue}, 80%, 50%)` }}>
      <div>frame {frame}</div>
    </AbsoluteFill>
  );
};
