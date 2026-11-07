import { loadFont } from "@remotion/google-fonts/IBMPlexSansArabic";

// Arabic/Hebrew and other RTL scripts need a font that actually ships Arabic
// glyphs (Space Grotesk/Inter don't) and correct joining — IBM Plex Sans
// Arabic matches Rooya's own site typography (rooyadairy.com).
export const { fontFamily: arabicFontFamily } = loadFont("normal", {
  weights: ["400", "600", "700"],
  subsets: ["arabic", "latin"],
});

const RTL_PATTERN = /[֑-߿יִ-﷽ﹰ-ﻼ]/;

export function isRTLText(text: string | undefined | null): boolean {
  return !!text && RTL_PATTERN.test(text);
}
