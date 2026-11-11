"""Where HTML compositions load GSAP from.

HyperFrames compositions, the character preview page and the Three.js world
load GSAP with a <script> tag. `make setup` installs the pinned `gsap` npm
package in remotion-composer/ (see its package.json); `stage_gsap` copies that
build next to the HTML so a render needs no network. Without the install it
returns the pinned CDN URL, which needs network at render time.

GSAP is distributed under its own "Standard 'no charge' license"
(https://gsap.com/standard-license), so the repository installs it from npm
instead of committing a copy.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

GSAP_VERSION = "3.14.2"
GSAP_FILENAME = "gsap.min.js"
GSAP_CDN_URL = f"https://cdn.jsdelivr.net/npm/gsap@{GSAP_VERSION}/dist/{GSAP_FILENAME}"

_REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_GSAP_PATH = _REPO_ROOT / "remotion-composer" / "node_modules" / "gsap" / "dist" / GSAP_FILENAME

logger = logging.getLogger(__name__)


def stage_gsap(target_dir: Path) -> str:
    """Copy the local GSAP build into ``target_dir``; return the script src.

    The src is the bare file name, relative to an HTML file in
    ``target_dir``. When GSAP is not installed locally the pinned CDN URL is
    returned and nothing is copied.
    """
    if not LOCAL_GSAP_PATH.is_file():
        logger.warning(
            "GSAP is not installed locally (%s); using %s, which needs network "
            "at render time. Run `make setup` or `npm install` in remotion-composer/.",
            LOCAL_GSAP_PATH,
            GSAP_CDN_URL,
        )
        return GSAP_CDN_URL
    shutil.copyfile(LOCAL_GSAP_PATH, Path(target_dir) / GSAP_FILENAME)
    return GSAP_FILENAME
