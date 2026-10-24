"""Print a logo onto the blank wooden marker in a shot's opening frame.

The logo has to be a real object in the scene, not an overlay laid on the
finished clip: the camera drifts, so anything stamped onto the rendered video
slides off the board within a second. Stamping it into the frame that Flow
animates instead means the sign carries the logo natively for the whole shot.

Two things make it read as printed rather than pasted:

  * the logo is warped onto the board's actual quad, so it takes the board's
    perspective and tilt;
  * it is composited as a *multiply*, so the wood grain and the shadow across
    the board show through the ink the way real print does. Straight alpha
    compositing produces a flat sticker every time.

It composites over everything in front of the board as well as the board itself —
it has no idea a hand is in the way. Frame the shot so nothing crosses the face:
a hand resting at the board's bottom rim works, a thumb in the middle does not.

    python scripts/stamp_logo_on_sign.py <frame.png> <logo.rgba.png> <out.png>
"""

from __future__ import annotations

import argparse
import sys

import cv2
import numpy as np

INSET = 0.14           # margin left around the logo, as a fraction of the board
STRENGTH = 0.92        # <1 lets a little wood through the darkest ink


def order_quad(points: np.ndarray) -> np.ndarray:
    """Return the four corners as top-left, top-right, bottom-right, bottom-left."""
    total = points.sum(axis=1)
    diff = points[:, 0] - points[:, 1]
    return np.array([points[np.argmin(total)], points[np.argmax(diff)],
                     points[np.argmax(total)], points[np.argmin(diff)]], dtype=np.float32)


def find_board(image: np.ndarray, roi: tuple[int, int, int, int] | None = None) -> np.ndarray:
    """Locate the sign's flat face and return its quad.

    The board is the one large bright blob in a frame of dark soil. The stake
    below it is bright too and touches it, so a wide horizontal opening erases
    the stake — it is far narrower than the board — before the contour is fit.
    """
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mask = np.zeros(grey.shape, np.uint8)
    x0, y0, x1, y1 = roi or (0, 0, grey.shape[1], grey.shape[0])
    window = grey[y0:y1, x0:x1]
    # Otsu picks the wood/soil split without a hand-tuned constant that would
    # need retuning for every shot's exposure.
    level, _ = cv2.threshold(window, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask[y0:y1, x0:x1] = (window > level) * 255

    width = max(31, (x1 - x0) // 8 | 1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_RECT, (width, 5)))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if count < 2:
        raise SystemExit("no board-sized bright region found")
    best = max(range(1, count), key=lambda i: stats[i, cv2.CC_STAT_AREA])
    blob = (labels == best).astype(np.uint8)

    contour = max(cv2.findContours(blob, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0],
                  key=cv2.contourArea)
    return order_quad(best_quad(contour))


def best_quad(contour: np.ndarray) -> np.ndarray:
    """The four hull points that enclose the most area.

    A minimum-area *rectangle* is the wrong shape here: the board is seen at an
    angle, so its face is a trapezoid, and forcing a rectangle onto it tilts the
    logo by several pixels at the corners. Simplifying the convex hull down to a
    handful of candidates and taking the widest quadrilateral among them keeps
    the perspective, and tolerates the board's rounded corners — those only pull
    the fit slightly inward, which the inset absorbs.
    """
    hull = cv2.convexHull(contour)
    perimeter = cv2.arcLength(hull, True)
    for step in range(1, 40):
        points = cv2.approxPolyDP(hull, 0.004 * step * perimeter, True).reshape(-1, 2)
        if len(points) <= 10:
            break
    if len(points) < 4:
        raise SystemExit("board outline collapsed below four corners")

    from itertools import combinations
    quad = max(combinations(points, 4),
               key=lambda c: cv2.contourArea(np.array(c, np.float32)))
    # combinations() preserves hull order, which is already a simple polygon.
    return np.array(quad, np.float32)


def inset_quad(quad: np.ndarray, fraction: float) -> np.ndarray:
    centre = quad.mean(axis=0)
    return (centre + (quad - centre) * (1 - fraction)).astype(np.float32)


def fit_inside(quad: np.ndarray, aspect: float) -> np.ndarray:
    """Shrink the quad along one axis so a logo of `aspect` fills it without stretching."""
    top = np.linalg.norm(quad[1] - quad[0])
    left = np.linalg.norm(quad[3] - quad[0])
    scale_x, scale_y = 1.0, 1.0
    if top / left > aspect:
        scale_x = aspect * left / top
    else:
        scale_y = top / (aspect * left)
    centre = quad.mean(axis=0)
    out = quad - centre
    # The quad's own axes, so the shrink follows the board's perspective.
    ux = (quad[1] + quad[2]) / 2 - (quad[0] + quad[3]) / 2
    uy = (quad[3] + quad[2]) / 2 - (quad[0] + quad[1]) / 2
    ux, uy = ux / np.linalg.norm(ux), uy / np.linalg.norm(uy)
    proj_x, proj_y = out @ ux, out @ uy
    return (centre + np.outer(proj_x * scale_x, ux) + np.outer(proj_y * scale_y, uy)).astype(np.float32)


def stamp(frame: np.ndarray, logo: np.ndarray, quad: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    lh, lw = logo.shape[:2]
    source = np.array([[0, 0], [lw, 0], [lw, lh], [0, lh]], np.float32)
    matrix = cv2.getPerspectiveTransform(source, quad)

    warped = cv2.warpPerspective(logo, matrix, (width, height), flags=cv2.INTER_LANCZOS4,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255, 0))
    ink = warped[:, :, :3].astype(np.float32) / 255.0
    alpha = (warped[:, :, 3:4].astype(np.float32) / 255.0) * STRENGTH

    base = frame.astype(np.float32)
    return np.clip(base * (1 - alpha) + base * ink * alpha, 0, 255).astype(np.uint8)


def demo() -> None:
    """Self-check: a known bright quad on a dark field must be found within a few pixels."""
    canvas = np.full((400, 300, 3), 30, np.uint8)
    truth = np.array([[60, 80], [230, 110], [220, 250], [50, 220]], np.float32)
    cv2.fillConvexPoly(canvas, truth.astype(np.int32), (220, 215, 200))
    cv2.rectangle(canvas, (130, 250), (155, 380), (215, 210, 195), -1)   # the stake
    found = find_board(canvas)
    error = np.abs(found - order_quad(truth)).max()
    assert error < 8, f"board corners off by {error:.1f}px\n{found}"
    print("demo ok: board found within %.1fpx, stake ignored" % error)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("frame", nargs="?")
    parser.add_argument("logo", nargs="?")
    parser.add_argument("out", nargs="?")
    parser.add_argument("--roi", help="x0,y0,x1,y1 to search in, when the frame has other bright things")
    parser.add_argument("--inset", type=float, default=INSET)
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    if args.demo:
        demo()
        return 0
    if not (args.frame and args.logo and args.out):
        parser.error("frame, logo and out are required unless --demo")

    frame = cv2.imread(args.frame, cv2.IMREAD_COLOR)
    logo = cv2.imread(args.logo, cv2.IMREAD_UNCHANGED)
    if frame is None or logo is None:
        raise SystemExit("could not read frame or logo")
    if logo.shape[2] != 4:
        raise SystemExit("the logo needs an alpha channel")

    roi = tuple(int(v) for v in args.roi.split(",")) if args.roi else None
    quad = find_board(frame, roi)
    target = fit_inside(inset_quad(quad, args.inset), logo.shape[1] / logo.shape[0])
    cv2.imwrite(args.out, stamp(frame, logo, target))

    corners = " ".join(f"({x:.0f},{y:.0f})" for x, y in quad)
    print(f"board {corners}\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
