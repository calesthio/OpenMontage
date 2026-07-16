// Motion design tokens — THE single source of easing curves and durations
// for every composition in this package.
//
// Why this exists (audit 2026-07-16, Wave 1): camera motion and progress
// interpolations were raw linear (`interpolate` with no `easing`), which is
// the classic "slideshow, not cinema" tell — while durations and spring
// configs were scattered magic numbers per component. Product-grade template
// systems (CapCut, Creatomate) never expose linear motion; Material Design's
// measured values put UI transitions at 150-375ms with decelerate-in /
// accelerate-out curves, and video (viewed at distance, non-interactive)
// reads best in the upper half of that range.
//
// Rules for components:
//  - NEVER call interpolate() for perceived MOTION (position/scale/opacity
//    of a moving element) without an easing from this file. Linear is only
//    acceptable for time-proportional data (progress bars, countdowns).
//  - NEVER inline a bezier or duration literal — add a token here instead.

import { Easing } from "remotion";

/** Decelerate — entrances: element arrives fast, settles gently. */
export const EASE_OUT = Easing.bezier(0, 0, 0.2, 1);

/** Accelerate — exits: element leaves slow, accelerates away. */
export const EASE_IN = Easing.bezier(0.4, 0, 1, 1);

/** Standard curve — transforms that start AND end on screen (camera moves,
 *  Ken Burns, pans, scale emphasis). */
export const EASE_IN_OUT = Easing.bezier(0.4, 0, 0.2, 1);

/** Entrance duration (seconds). */
export const DUR_ENTER_S = 0.35;

/** Exit duration (seconds). */
export const DUR_EXIT_S = 0.25;

/** Scene-to-scene transition duration (seconds). */
export const DUR_TRANSITION_S = 0.4;

/** Default spring for content entrances — matches the settle feel of
 *  EASE_OUT at DUR_ENTER_S. */
export const SPRING_ENTER = { damping: 18, stiffness: 80 } as const;
