// T4 case 04 — Imports from a third-party React UI library.
//
// Should be detected by lint_source.py as blocker r2hf/third-party-react-ui.
// The skill should refuse to translate.
//
// Why this is a blocker: a Material-UI Button (or any React UI library
// component) is a React-only abstraction with internal hooks, refs, and
// theme provider context. Translating it to HTML+CSS would require
// re-implementing the design system, which is out of scope for a video
// translation skill. Use the runtime interop pattern from PR #214 to keep
// these components rendering through Remotion's React tree.

import React from "react";
import { Button } from "@mui/material";
import { AbsoluteFill, useCurrentFrame, interpolate } from "remotion";

export const MuiDriven: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 30], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ opacity }}>
        <Button variant="contained" color="primary">
          Click me · frame {frame}
        </Button>
      </div>
    </AbsoluteFill>
  );
};
