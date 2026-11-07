export type CinematicTone = "cold" | "steel" | "void" | "neutral";

export interface CinematicBaseScene {
  id: string;
  startSeconds: number;
  durationSeconds: number;
}

export interface CinematicVideoScene extends CinematicBaseScene {
  kind: "video";
  src: string;
  tone?: CinematicTone;
  trimBeforeSeconds?: number;
  trimAfterSeconds?: number;
  playbackRate?: number;
  filter?: string;
  fadeInFrames?: number;
  fadeOutFrames?: number;
}

export interface CinematicTitleScene extends CinematicBaseScene {
  kind: "title";
  text: string;
  accent?: string;
  intensity?: number;
  backgroundSrc?: string;
  backgroundTrimBeforeSeconds?: number;
  backgroundTrimAfterSeconds?: number;
  variant?: "plate" | "overlay";
}

export type CinematicScene = CinematicVideoScene | CinematicTitleScene;

export interface CinematicSoundtrack {
  src: string;
  volume?: number;
  trimBeforeSeconds?: number;
  trimAfterSeconds?: number;
  fadeInSeconds?: number;
  fadeOutSeconds?: number;
}

export interface CinematicWordCaption {
  word: string;
  startMs: number;
  endMs: number;
  pageBreakAfter?: boolean;
}

export interface CinematicCaptionConfig {
  words: CinematicWordCaption[];
  // "karaoke" renders PhraseCaptions; anything else keeps CaptionOverlay.
  style?: string;
  wordsPerPage?: number;
  fontSize?: number;
  color?: string;
  highlightColor?: string;
  backgroundColor?: string;
  // PhraseCaptions only
  fontFamily?: string;
  dimColor?: string;
  maxCharsPerCue?: number;
  holdSeconds?: number;
  position?: "bottom-center" | "top-center" | "center";
}

export interface CinematicRendererProps {
  [key: string]: unknown;
  scenes: CinematicScene[];
  titleFontSize?: number;
  titleWidth?: number;
  signalLineCount?: number;
  soundtrack?: CinematicSoundtrack;
  music?: CinematicSoundtrack;
  captions?: CinematicCaptionConfig;
}
