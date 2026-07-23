import { Config } from "@remotion/cli/config";

// Match HyperFrames' default render so SSIM diffs measure translation
// fidelity, not encoder differences.
//
//   setVideoImageFormat("png") avoids the JPEG limited-range/full-range
//   colorspace flag (yuvj420p vs yuv420p) that otherwise costs ~0.05 SSIM.
//
//   setColorSpace("bt709") matches HF's BT.709 SDR output.
Config.setVideoImageFormat("png");
Config.setColorSpace("bt709");
Config.setOverwriteOutput(true);
Config.setConcurrency(1);
