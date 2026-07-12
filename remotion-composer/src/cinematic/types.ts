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
  /** "cover" (default) fills the frame and crops overflow. "contain" fits
   * the whole source without cropping, pillarboxed/letterboxed against the
   * scene background — use for portrait-sourced clips in a landscape canvas. */
  fit?: "cover" | "contain";
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

export interface CinematicGridCell {
  src: string;
  trimBeforeSeconds?: number;
  trimAfterSeconds?: number;
  filter?: string;
}

export interface CinematicGridScene extends CinematicBaseScene {
  kind: "grid";
  /** 2 or 3 clips played simultaneously side by side, full height each —
   * for portrait-sourced clips that would otherwise sit in a lot of empty
   * pillarbox space alone. */
  cells: CinematicGridCell[];
  /** Pixel gap between cells (and outer margin). Default 6. */
  gapPx?: number;
  fadeInFrames?: number;
  fadeOutFrames?: number;
}

export type CinematicScene = CinematicVideoScene | CinematicTitleScene | CinematicGridScene;

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
}

export interface CinematicCaptionConfig {
  words: CinematicWordCaption[];
  wordsPerPage?: number;
  fontSize?: number;
  color?: string;
  highlightColor?: string;
  backgroundColor?: string;
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
