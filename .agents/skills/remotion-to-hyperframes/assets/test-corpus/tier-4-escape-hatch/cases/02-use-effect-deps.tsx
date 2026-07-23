// T4 case 02 — useEffect with non-empty deps performs side effects per render.
//
// Should be detected by lint_source.py as blocker r2hf/use-effect-deps.
// The skill should refuse to translate.
//
// Why this is a blocker: side effects (network, DOM mutation outside the
// rendered tree, timers) don't translate to a seek-driven model. HF assumes
// the page is fully rendered and pure between seeks.

import React, { useEffect, useRef } from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

export const SideEffectDriven: React.FC = () => {
  const frame = useCurrentFrame();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx?.fillRect(frame, frame, 10, 10);
  }, [frame]);

  return (
    <AbsoluteFill>
      <canvas ref={canvasRef} width={1280} height={720} />
    </AbsoluteFill>
  );
};
