import {
  AbsoluteFill,
  Audio,
  CalculateMetadataFunction,
  Img,
  useVideoConfig,
} from "remotion";
import { getAudioDurationInSeconds } from "@remotion/media-utils";
import { resolveAsset } from "./lib/resolveAsset";

export type PilotScene1Props = {
  frameSrc: string;
  audioSrc: string;
};

// Minimal pilot scene: a single generated frame held full-bleed for the full
// duration of the Kokoro narration, with the narration audio baked in.
export const PilotScene1: React.FC<PilotScene1Props> = ({
  frameSrc,
  audioSrc,
}) => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <Img
        src={resolveAsset(frameSrc)}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
      <Audio src={resolveAsset(audioSrc)} />
    </AbsoluteFill>
  );
};

export const calculatePilotScene1Metadata: CalculateMetadataFunction<
  PilotScene1Props
> = async ({ props }) => {
  const durationInSeconds = await getAudioDurationInSeconds(
    resolveAsset(props.audioSrc)
  );
  return {
    durationInFrames: Math.max(1, Math.ceil(durationInSeconds * 30)),
    fps: 30,
    width: 1920,
    height: 1080,
  };
};
