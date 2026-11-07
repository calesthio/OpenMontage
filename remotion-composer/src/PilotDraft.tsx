import * as React from "react";
import {
  AbsoluteFill,
  Audio,
  CalculateMetadataFunction,
  Img,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { getAudioDurationInSeconds } from "@remotion/media-utils";
import { resolveAsset } from "./lib/resolveAsset";

export type PilotDraftProps = {
  // Cumulative start time (seconds) and duration (seconds) per section
  sections: Array<{
    id: string;
    title: string;
    text: string;
    startSeconds: number;
    durationSeconds: number;
  }>;
};

// Section metadata — titles and full narration text from docs/openmontage/pilot/script.md
const SECTION_DATA: Record<string, { title: string; text: string }> = {
  section_01: {
    title: "Hook and the question",
    text: "Start with a simple question: could life exist in an ocean that has never seen the sky? On Jupiter's moon Europa, a global saltwater ocean lies hidden beneath a completely frozen crust. That crust is tens of miles thick, and the ocean surface beneath it is frozen solid. Yet the ocean underneath holds more than twice as much water as all of Earth's oceans combined.",
  },
  section_02: {
    title: "The world: an ocean with no shores",
    text: "It stays liquid not because of sunlight, but because Jupiter's gravity flexes the moon and heats it from within. Sunlight never reaches that water, so nothing down there has ever seen a sunrise. So the question becomes sharper: what could live in a dark ocean sealed under ice?",
  },
  section_03: {
    title: "Energy: no sunlight, two answers",
    text: "Europa is not even the only one: Saturn's moon Enceladus hides a global salty ocean beneath its icy crust. Enceladus even sprays that ocean into space through cracks near its south pole.",
  },
  section_04: {
    title: "Life near the ice: mats and filter-feeders",
    text: "On Earth, we already know what life can do without sunlight, because the deep sea has an answer.",
  },
  section_05: {
    title: "Predators, and the logic of an arms race",
    text: "This episode follows that answer outward, from a vent on our own sea floor to an ocean we have never touched.",
  },
  section_06: {
    title: "The deep, the vents, and the animals that stay",
    text: "Some of what follows is measured, and some of it is invented, and we will mark the difference every time.",
  },
  section_07: {
    title: "Chance and law: would this world repeat?",
    text: "By the end, you can decide which parts you believe.",
  },
  section_08: {
    title: "What blocks technology without land or fire",
    text: "Two of the least remarkable-looking moons in the solar system may be the most interesting.",
  },
  section_09: {
    title: "What is science, and what is a guess",
    text: "Thank you for watching.",
  },
  section_10: {
    title: "Closing and a question for you",
    text: "What would you look for in an ocean under ice?",
  },
};

// Simple section text overlay — shows narration text at bottom during each section
const SectionText: React.FC<{
  text: string;
  startMs: number;
  endMs: number;
}> = ({ text, startMs, endMs }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentMs = (frame / fps) * 1000;

  const show = currentMs >= startMs && currentMs < endMs;
  if (!show) return null;

  const progress = (currentMs - startMs) / (endMs - startMs);
  const entrance = spring({ frame, fps, config: { damping: 20, stiffness: 150 } });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: 120,
      }}
    >
      <div
        style={{
          opacity: Math.min(entrance, 1),
          transform: `translateY(${interpolate(progress, [0, 1], [30, 0])}px)`,
          backgroundColor: "rgba(0, 0, 0, 0.6)",
          borderRadius: 8,
          padding: "16px 32px",
          maxWidth: "90%",
          textAlign: "center",
          color: "#F8FAFC",
          fontSize: 28,
          fontWeight: 600,
          lineHeight: 1.4,
          whiteSpace: "pre-wrap",
          textShadow: "0 2px 4px rgba(0,0,0,0.5)",
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};

// Draft pilot composition: one generated image per section, full-bleed,
// synchronized with its Kokoro narration audio. Section text shown as subtitles.
// Soft transitions via opacity cross-fade between sections.
export const PilotDraft: React.FC<PilotDraftProps> = ({
  sections,
}) => {
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {sections.map((section, idx) => {
        const imgSrc = resolveAsset(`pilot/${section.id}.png`);
        const audioSrc = resolveAsset(`pilot/${section.id}.wav`);
        const sectionStartMs = section.startSeconds * 1000;
        const sectionEndMs = (section.startSeconds + section.durationSeconds) * 1000;

        // Soft cross-fade: 0.5s fade-in at start, 0.5s fade-out at end
        const fadeInDuration = 0.5;
        const fadeOutDuration = 0.5;
        const isFirst = idx === 0;
        const isLast = idx === sections.length - 1;

        const imgOpacity = spring({
          frame: useCurrentFrame(),
          fps: useVideoConfig().fps,
          config: { damping: 25, stiffness: 200 },
        });

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
                opacity: isFirst
                  ? 1
                  : interpolate(imgOpacity, [0, 1], [0, 1]),
              }}
            />
            <Audio
              src={audioSrc}
              {...{ from: section.startSeconds } as React.ComponentProps<
                typeof Audio
              > &
                Record<string, unknown>}
            />
            <SectionText
              text={section.text}
              startMs={sectionStartMs}
              endMs={sectionEndMs}
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

  for (const id of Object.keys(SECTION_DATA)) {
    const durationInSeconds = await getAudioDurationInSeconds(
      resolveAsset(`pilot/${id}.wav`)
    );
    sections.push({
      id,
      title: SECTION_DATA[id].title,
      text: SECTION_DATA[id].text,
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
    { id: "section_01", title: "Hook and the question", text: SECTION_DATA.section_01.text, startSeconds: 0, durationSeconds: 83.0 },
    { id: "section_02", title: "The world: an ocean with no shores", text: SECTION_DATA.section_02.text, startSeconds: 83.0, durationSeconds: 129.4 },
    { id: "section_03", title: "Energy: no sunlight, two answers", text: SECTION_DATA.section_03.text, startSeconds: 212.4, durationSeconds: 148.6 },
    { id: "section_04", title: "Life near the ice: mats and filter-feeders", text: SECTION_DATA.section_04.text, startSeconds: 361.0, durationSeconds: 135.5 },
    { id: "section_05", title: "Predators, and the logic of an arms race", text: SECTION_DATA.section_05.text, startSeconds: 496.5, durationSeconds: 132.9 },
    { id: "section_06", title: "The deep, the vents, and the animals that stay", text: SECTION_DATA.section_06.text, startSeconds: 629.4, durationSeconds: 137.8 },
    { id: "section_07", title: "Chance and law: would this world repeat?", text: SECTION_DATA.section_07.text, startSeconds: 767.2, durationSeconds: 99.9 },
    { id: "section_08", title: "What blocks technology without land or fire", text: SECTION_DATA.section_08.text, startSeconds: 867.1, durationSeconds: 101.4 },
    { id: "section_09", title: "What is science, and what is a guess", text: SECTION_DATA.section_09.text, startSeconds: 968.5, durationSeconds: 83.6 },
    { id: "section_10", title: "Closing and a question for you", text: SECTION_DATA.section_10.text, startSeconds: 1052.1, durationSeconds: 47.8 },
  ],
};
