// T4 case 07 — Locally-defined custom hook.
//
// Should be detected by lint_source.py as warning r2hf/custom-hook.
// 0 blockers expected — the skill can attempt translation if the hook body
// is pure (derives from props/frame alone).
//
// Why this is a warning: custom hooks vary widely in what they do. Some are
// pure derivations of useCurrentFrame (translatable — inline the body); some
// wrap useState/useEffect (blocker — but those will be caught by the other
// rules independently). The warning prompts the agent to inspect the body.

import React from "react";
import { AbsoluteFill, useCurrentFrame, interpolate } from "remotion";

// Custom hook — pure derivation from frame, no state. Translates fine.
function useFadeIn(durationInFrames: number) {
  const frame = useCurrentFrame();
  return interpolate(frame, [0, durationInFrames], [0, 1], { extrapolateRight: "clamp" });
}

export const CustomHookDriven: React.FC = () => {
  const opacity = useFadeIn(30);
  return (
    <AbsoluteFill style={{ opacity }}>
      <div>fading in</div>
    </AbsoluteFill>
  );
};
