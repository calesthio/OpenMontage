// T4 case 03 — calculateMetadata returns a Promise.
//
// Should be detected by lint_source.py as blocker r2hf/async-metadata.
// The skill should refuse to translate.
//
// Why this is a blocker: HF needs the composition's duration, dimensions,
// and props known up-front to produce HTML and seed the timeline. Async
// metadata fetched from a server at render time has no equivalent in HF —
// the metadata would need to be resolved at build time before the HTML is
// authored.

import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

interface Props {
  text: string;
}

export const AsyncMetadataDriven: React.FC<Props> = ({ text }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <div>
        {text} · frame {frame}
      </div>
    </AbsoluteFill>
  );
};

export const calculateMetadata = async ({ props }: { props: Props }) => {
  const response = await fetch(
    `https://api.example.com/duration?text=${encodeURIComponent(props.text)}`,
  );
  const { durationInFrames } = await response.json();
  return {
    durationInFrames,
    fps: 30,
  };
};
