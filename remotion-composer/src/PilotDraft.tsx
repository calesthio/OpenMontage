import * as React from "react";
import {
  AbsoluteFill,
  Audio,
  CalculateMetadataFunction,
  Img,
} from "remotion";
import { getAudioDurationInSeconds } from "@remotion/media-utils";
import { resolveAsset } from "./lib/resolveAsset";

export type PilotDraftProps = {
  // Cumulative start time (seconds) and duration (seconds) per section
  sections: Array<{
    id: string;
    title: string;
    startSeconds: number;
    durationSeconds: number;
  }>;
};

// Section metadata — titles from docs/openmontage/pilot/script.md
const SECTION_TITLES: Record<string, string> = {
  section_01: "Hook and the question",
  section_02: "The world: an ocean with no shores",
  section_03: "Energy: no sunlight, two answers",
  section_04: "Life near the ice: mats and filter-feeders",
  section_05: "Predators, and the logic of an arms race",
  section_06: "The deep, the vents, and the animals that stay",
  section_07: "Chance and law: would this world repeat?",
  section_08: "What blocks technology without land or fire",
  section_09: "What is science, and what is a guess",
  section_10: "Closing and a question for you",
};

// Draft pilot composition: one generated image per section, full-bleed,
// synchronized with its Kokoro narration audio. No transitions or effects —
// a raw cut-down for owner review.
export const PilotDraft: React.FC<PilotDraftProps> = ({
  sections,
}) => {
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {sections.map((section) => {
        const imgSrc = resolveAsset(`pilot/${section.id}.png`);
        const audioSrc = resolveAsset(`pilot/${section.id}.wav`);
        return (
          <React.Fragment key={section.id}>
            <Img
              src={imgSrc}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: "100%",
                objectFit: "cover",
                opacity: 1,
              }}
            />
            <Audio
              src={audioSrc}
              {...{ from: section.startSeconds } as React.ComponentProps<typeof Audio> & Record<string, unknown>}
            />
          </React.Fragment>
        );
      })}
    </AbsoluteFill>
  );
};

export const calculatePilotDraftMetadata: CalculateMetadataFunction<
  PilotDraftProps
> = async () => {
  const sections: PilotDraftProps["sections"] = [];
  let startSeconds = 0;

  for (const id of Object.keys(SECTION_TITLES)) {
    const durationInSeconds = await getAudioDurationInSeconds(
      resolveAsset(`pilot/${id}.wav`)
    );
    sections.push({
      id,
      title: SECTION_TITLES[id],
      startSeconds,
      durationSeconds: durationInSeconds,
    });
    startSeconds += durationInSeconds;
  }

  const totalSeconds = startSeconds;
  return {
    durationInFrames: Math.max(1, Math.ceil(totalSeconds * 30)),
    fps: 30,
    width: 1920,
    height: 1080,
  };
};

// Pre-computed static props for CLI rendering (durations measured via ffprobe)
export const PILOT_DRAFT_PROPS: PilotDraftProps = {
  sections: [
    { id: "section_01", title: "Hook and the question", startSeconds: 0, durationSeconds: 83.0 },
    { id: "section_02", title: "The world: an ocean with no shores", startSeconds: 83.0, durationSeconds: 129.4 },
    { id: "section_03", title: "Energy: no sunlight, two answers", startSeconds: 212.4, durationSeconds: 148.6 },
    { id: "section_04", title: "Life near the ice: mats and filter-feeders", startSeconds: 361.0, durationSeconds: 135.5 },
    { id: "section_05", title: "Predators, and the logic of an arms race", startSeconds: 496.5, durationSeconds: 132.9 },
    { id: "section_06", title: "The deep, the vents, and the animals that stay", startSeconds: 629.4, durationSeconds: 137.8 },
    { id: "section_07", title: "Chance and law: would this world repeat?", startSeconds: 767.2, durationSeconds: 99.9 },
    { id: "section_08", title: "What blocks technology without land or fire", startSeconds: 867.1, durationSeconds: 101.4 },
    { id: "section_09", title: "What is science, and what is a guess", startSeconds: 968.5, durationSeconds: 83.6 },
    { id: "section_10", title: "Closing and a question for you", startSeconds: 1052.1, durationSeconds: 47.8 },
  ],
};
