import { staticFile } from "remotion";
import { CinematicRendererProps } from "./types";

// Safe default for the Studio preview — pure title cards, no external assets.
// Prevents "browser threw an error while playing the video" when the demo
// mp4/mp3 files referenced in `signalFromTomorrowWithMusicFixture` below have
// not been dropped into `remotion-composer/public/`.
export const signalFromTomorrowDefaultFixture: CinematicRendererProps = {
  titleFontSize: 78,
  titleWidth: 1320,
  signalLineCount: 18,
  scenes: [
    {
      id: "intro",
      kind: "title",
      startSeconds: 0,
      durationSeconds: 4,
      text: "DROP MP4S INTO public/video/signal-from-tomorrow",
      accent: "#89d7ff",
      intensity: 0.9,
    },
    {
      id: "headline",
      kind: "title",
      startSeconds: 4,
      durationSeconds: 4,
      text: "YESTERDAY, THEY LAUNCHED.",
      accent: "#89d7ff",
      intensity: 1,
    },
    {
      id: "midline",
      kind: "title",
      startSeconds: 8,
      durationSeconds: 4,
      text: "THE SIGNAL CAME FROM EARTH.",
      accent: "#a6e6ff",
      intensity: 1.15,
    },
    {
      id: "outro",
      kind: "title",
      startSeconds: 12,
      durationSeconds: 4,
      text: "SIGNAL FROM TOMORROW",
      accent: "#d6f1ff",
      intensity: 0.9,
    },
  ],
};

// Reference fixture for the full audio + video demo. Requires the user to drop
// the matching assets into `remotion-composer/public/`:
//   public/video/signal-from-tomorrow/*.mp4
//   public/music/signal-from-tomorrow/cinematic_time_hans_zimmer_style.mp3
// Pass it as props at render time, e.g.:
//   npx remotion render SignalFromTomorrowWithMusic out.mp4 \
//     --props=./props/signal-from-tomorrow-with-music.json
export const signalFromTomorrowWithMusicFixture: CinematicRendererProps = {
  titleFontSize: 78,
  titleWidth: 1320,
  signalLineCount: 18,
  soundtrack: {
    src: staticFile(
      "music/signal-from-tomorrow/cinematic_time_hans_zimmer_style.mp3",
    ),
    volume: 0.42,
    fadeInSeconds: 1.5,
    fadeOutSeconds: 2.5,
  },
  scenes: [
    {
      id: "sc1",
      kind: "video",
      startSeconds: 0,
      durationSeconds: 4,
      src: staticFile("video/signal-from-tomorrow/sample_observatory_veo31_ref.mp4"),
      tone: "cold",
      trimBeforeSeconds: 1,
      fadeInFrames: 0,
    },
    {
      id: "sc2",
      kind: "video",
      startSeconds: 4,
      durationSeconds: 4,
      src: staticFile(
        "video/signal-from-tomorrow/sc2_mission_control_veo31_ref_8s.mp4",
      ),
      tone: "steel",
    },
    {
      id: "sc3",
      kind: "title",
      startSeconds: 8,
      durationSeconds: 3,
      text: "YESTERDAY, THEY LAUNCHED.",
      accent: "#89d7ff",
      intensity: 1,
    },
    {
      id: "sc4",
      kind: "video",
      startSeconds: 11,
      durationSeconds: 7,
      src: staticFile("video/signal-from-tomorrow/sc4_launch_departure_veo31_ref.mp4"),
      tone: "cold",
    },
    {
      id: "sc5",
      kind: "title",
      startSeconds: 18,
      durationSeconds: 3,
      text: "THE SIGNAL CAME FROM EARTH.",
      accent: "#a6e6ff",
      intensity: 1.15,
    },
    {
      id: "sc6",
      kind: "video",
      startSeconds: 21,
      durationSeconds: 6,
      src: staticFile(
        "video/signal-from-tomorrow/sc6_orbital_paradox_veo31_ref_8s.mp4",
      ),
      tone: "void",
    },
    {
      id: "sc7",
      kind: "title",
      startSeconds: 27,
      durationSeconds: 3,
      text: "SIGNAL FROM TOMORROW",
      accent: "#d6f1ff",
      intensity: 0.9,
    },
  ],
};
