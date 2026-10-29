"""Drive Google Flow through Playwright, attached to the user's own Chrome.

Google Flow has no public API for generation, so this attaches over CDP to a
real Chrome the user is signed into and drives the UI with genuinely trusted
input. Chrome must be started with `--remote-debugging-port` AND a non-default
`--user-data-dir`; since Chrome 136 the flag is ignored on the default profile.

Rewritten 2026-09-05. Flow moved from Next.js + tRPC on `labs.google/fx` to
Angular + batchexecute on `flow.google.com`, and authenticates by cookie rather
than by a bearer token. The old driver's API layer — `auth/session`,
`uploadImage`, `media.getMediaUrlRedirect` — is gone, and could not be repaired
by editing URLs: there is no token left to call `aisandbox-pa` with. So every
step is now UI-driven. Measured against the live app, not guessed:

* the prompt box is a `div[contenteditable]`, not a `<textarea>` — the only
  `<textarea>` on the page is `g-recaptcha-response`, which is what the old
  driver had been typing into;
* the whole settings popover is `[role=radio]` elements with no `aria-label`,
  so they are matched on a line of their own `innerText` ("videocam\nVideo");
* "upload" opens the OS file dialog and has no `<input type=file>` in the DOM,
  so it has to be caught with `expect_file_chooser`;
* a finished clip is a `flow-video-tile` in the grid, newest first, and that
  tile is the only reliable handle on it. The first version of this file
  identified clips by the `<video>` src instead, because the probe clip did
  mount a player on its own — and then the first real shot finished with its
  tile on screen, no player mounted, and the wait sat through all 810 seconds
  of its timeout for a clip that was already there. The player's src is not
  merely inconvenient but wrong: it changes host once a clip settles
  (`flow.google.com/asb/<token>`, not `flow-content.google/video/<id>`).

Getting the finished clip onto disk is the fiddliest part and the comments on
`download_clip`, `_download_tile` and `_catch_download` are the record of why
each step is shaped the way it is. The short version: the tile's own "Tải
xuống" → "720p Kích thước gốc", opened by hovering *across* the parent row,
found by `elementFromPoint` because those rows have no box, clicked from script
because a real click on them does nothing, and collected from a download
directory this driver names because `expect_download` never fires on a
CDP-attached browser.

The settings are always written and then read back off the pill. The tab was
found sitting on `x2` and `crop_16_9`: inheriting that would silently double
the credit cost of every clip and deliver landscape for a 9:16 series.
"""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Optional

DEFAULT_CDP = "http://127.0.0.1:9222"
FLOW_HOME = "https://flow.google.com/"
FLOW_HOST = "flow.google.com"

# A 200 with a tiny body is Flow's "not rendered yet" answer, not a video.
MIN_VIDEO_BYTES = 100_000

# Radio labels in the settings popover, keyed by what callers ask for.
ASPECT_LABEL = {"16:9": "16:9", "9:16": "9:16"}

# Image mode ("Hình ảnh") offers five aspects and reports them on the pill
# with Material Symbols names rather than the ratio itself.
IMAGE_MODE = "Hình ảnh"
IMAGE_ASPECT_PILL = {"16:9": "crop_16_9", "4:3": "crop_landscape", "1:1": "crop_square",
                     "3:4": "crop_portrait", "9:16": "crop_9_16"}
IMAGE_TILE = "flow-image-tile"
VIDEO_TILE = "flow-video-tile"
# A finished image downloads at "1K Kích thước gốc" — around 100–200 KB of JPEG.
MIN_IMAGE_BYTES = 20_000

NEW_PROJECT = ["Dự án mới", "New project"]
MODAL_ACCEPT = ["Chấp nhận", "Tôi chấp nhận", "Đồng ý", "Tiếp tục", "Đã hiểu",
                "Accept", "I accept", "I agree", "Agree", "Continue", "Got it"]

ADD_MEDIA_MENU = "Trình đơn thêm nội dung nghe nhìn"
UPLOAD_ITEM = "Tải lên"
START_FRAME_SLOT = "Bắt đầu"
END_FRAME_SLOT = "Kết thúc"
# Video mode's two sub-modes. "Khung hình" renders the start/end frame slots;
# "Thành phần" replaces them with prompt-chip references and is the only one
# that accepts more than two images.
FRAMES_SUBMODE = "Khung hình"
ELEMENTS_SUBMODE = "Thành phần"
FRAME_REMOVE = "Thành phần tạo hình ảnh"
ADD_TO_PROMPT = "Thêm vào câu lệnh"
# Image mode's own attach control, on the prompt bar rather than the toolbar.
# Video mode fills named "Bắt đầu"/"Kết thúc" slots; image mode has no slots and
# instead drops reference chips into the prompt box through this button.
PROMPT_ADD_ELEMENT = "Thêm thành phần vào ô nhập câu lệnh"
MEDIA_UPLOAD_ITEM = "Tải nội dung nghe nhìn lên"
# The attached reference itself. Measured 2026-09-13: the chip is a
# `button.chip-container` labelled just "Thành phần", wrapping an
# `img.chip-image` — NOT `FRAME_REMOVE` ("Thành phần tạo hình ảnh"), which
# belongs to video mode's frame slots. Checking for the wrong one reported a
# perfectly good attach as a failure.
REF_CHIP = "button.chip-container, img.chip-image"
# One chip renders as both nodes above, so REF_CHIP counts every chip twice.
# Use this when the number of chips is the thing being checked.
REF_CHIP_BUTTON = "button.chip-container"
SETTINGS_PILL = "Điều kiện kích hoạt cài đặt"
START_GENERATION = "Bắt đầu tạo"
MODEL_ROW = "Chọn nhóm mô hình"
TILE_MORE = ["Tuỳ chọn khác", "Lựa chọn khác", "More options"]
DOWNLOAD_ITEM = ["Tải xuống", "Download"]
NATIVE_SIZE = ["Kích thước gốc", "Original size"]
# Rows above the native one are upscales. "Nâng cấp" marks a tier the current plan
# does not include — clicking it opens a paywall instead of downloading.
UPSCALED = ["Đã tăng độ phân giải", "Upscaled"]
PLAN_GATED = ["Nâng cấp", "Upgrade"]
# Leading resolution token of a submenu row: "720p", "1080p", "1K", "2K", "4K".
RES_RE = re.compile(r"^\s*(\d+)\s*([pk])", re.I)

# Flow announces a refusal *in the tile it just made*, not in a dialog, so the
# wait sees a new caption and calls the generation finished. Without these
# words the run then failed at the download step with "the clip is not in the
# grid any more", quoting the apology as if it were a clip title.
FAILED_RE = re.compile(
    r"Không thành công|không tạo được video|Rất tiếc|"
    r"Sinh lại|Tạo lại|Generate again|failed|lâu hơn bình thường", re.I)

# Single-word Material Symbols ligatures that render as text inside a tile.
# Anything with an underscore is one too, and is dropped without being listed.
ICON_WORDS = frozenset({"favorite", "redo", "image", "videocam", "download",
                        "delete", "edit", "share", "add", "close", "history"})

# While a clip renders, its tile is captioned with a percentage followed by the
# whole prompt; when it finishes, Flow replaces that with a short title of its
# own. A wait that accepts the first caption it sees therefore records a name
# that no longer exists by the time the download looks for it.
PROGRESS_RE = re.compile(r"^\s*\d{1,3}\s*%")


def _caption(raw: str) -> str:
    """A tile's text with the Material Symbols ligatures stripped out.

    A tile reads "play_circle Gardener holding note" at rest and gains
    "favorite", "redo", "more_vert" and a second "play_circle" while the cursor
    is over it, so the raw text is not the same string twice running. Comparing
    it verbatim made a clip that was sitting in the grid look like a clip that
    had been deleted.
    """
    words = [w for w in " ".join((raw or "").split()).split(" ")
             if "_" not in w and w not in ICON_WORDS]
    return " ".join(words)


def _same_text(needle: str, haystack: str) -> bool:
    """Vietnamese substring test that survives Unicode normalisation.

    Flow serves some labels with precomposed diacritics and some with combining
    marks, so `"Kích thước gốc" in text` is False against a string that renders
    identically and reads identically in a debugger. This cost most of a day:
    the driver reported "Flow did not open the download submenu" while a
    screenshot of the same instant showed it open and `elementFromPoint`
    returned the row.
    """
    return (unicodedata.normalize("NFC", needle).casefold()
            in unicodedata.normalize("NFC", haystack).casefold())


class FlowError(RuntimeError):
    """A step failed. The message always names the step that failed."""


class FlowDriver:
    """One Flow session. Use as a context manager."""

    def __init__(self, cdp_url: str = DEFAULT_CDP, project_url: Optional[str] = None):
        self.cdp_url = cdp_url
        self.project_url = project_url
        self._pw = None
        self._browser = None
        self.page = None
        self._started_at = time.time()

    # ----------------------------------------------------------- lifecycle

    def __enter__(self) -> "FlowDriver":
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.connect_over_cdp(self.cdp_url)
        except Exception as exc:
            self._pw.stop()
            raise FlowError(
                f"connect: no Chrome listening on {self.cdp_url}. Start it with\n"
                f'  chrome.exe --remote-debugging-port=9222 --user-data-dir="<a dedicated dir>"\n'
                f"(since Chrome 136 the port is ignored on the default profile.)\n"
                f"Underlying error: {exc}"
            ) from exc
        self.page = self._find_flow_page()
        return self

    def __exit__(self, *exc_info) -> None:
        # Only detach. The browser is the user's — never close their window.
        try:
            if self._browser:
                self._browser.close()
        finally:
            if self._pw:
                self._pw.stop()

    def _find_flow_page(self):
        pages = [p for ctx in self._browser.contexts for p in ctx.pages
                 if "accounts.google.com" not in p.url]
        if not pages:
            raise FlowError("connect: the browser has no open pages")

        # Order matters. The named project first: this browser routinely has
        # half a dozen project tabs open, and "any Flow tab" would drop an
        # episode's clips into whichever one happened to be first. Then any
        # project tab, which is already past the grid with its composer mounted,
        # and only then the home tab.
        wanted = [self.project_url] if self.project_url else []
        for want in wanted + ["/project/", ""]:
            for page in pages:
                if FLOW_HOST in page.url and want in page.url:
                    return page

        page = next((p for p in pages if p.url.startswith(("chrome://", "about:"))), None) \
            or self._browser.contexts[0].new_page()
        page.goto(self.project_url or FLOW_HOME, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(4000)
        if "accounts.google.com" in page.url:
            raise FlowError(
                "connect: this Chrome profile is not signed in to Google Flow. "
                "Sign in in that window, then retry — the profile keeps the session."
            )
        return page

    # -------------------------------------------------------------- basics

    def _visible(self, role: str, name: str):
        loc = self.page.get_by_role(role, name=name)
        return loc if loc.count() else None

    def _menu_item(self, text, scope=None):
        """First visible menu entry whose own text carries `text`.

        `text` may be a list of alternatives: Flow renders some menus in the
        account's language and some in the page's, so a label that exists is
        not necessarily the label this driver was written against.

        Not `get_by_role`: these entries render the Material Symbols ligature as
        a text node, so the accessible name is "upload Tải lên" for some and the
        bare icon for others, and Flow uses `button`, `[role=menuitem]` and
        `<a>` interchangeably for items sitting in the same menu.

        Returns a handle on the node, not `nth(i)`. A positional locator is only
        valid for the DOM it was counted against: opening the download submenu
        adds four buttons to the page, after which the index that had found
        "Tải xuống" resolved to something else, and the retry loop hovered that
        instead — closing the menu it was waiting for.
        """
        items = (scope or self.page).locator(
            "button, [role=menuitem], [role=option], a, flow-menu-item")
        for i in range(items.count()):
            item = items.nth(i)
            try:
                # A bounding box rather than `is_visible()`: cheaper, and the
                # same test the caller cares about, since anything without a box
                # cannot be clicked.
                if not item.bounding_box():
                    continue
                label = " ".join(item.inner_text(timeout=1500).split())
                wanted = [text] if isinstance(text, str) else text
                if any(_same_text(w, label) for w in wanted):
                    return item.element_handle()
            except Exception:
                continue
        return None

    def dismiss_modals(self) -> None:
        """Clear consent dialogs and banners; they swallow pointer events."""
        for _ in range(3):
            clicked = False
            for label in MODAL_ACCEPT:
                btn = self.page.get_by_role("button", name=label, exact=True)
                if btn.count() and btn.first.is_visible():
                    btn.first.click(timeout=5000)
                    self.page.wait_for_timeout(700)
                    clicked = True
                    break
            if not clicked:
                break
        # Angular leaves a transparent backdrop behind a dismissed overlay, and
        # it intercepts every later click with no visible sign that it is there.
        # It is clicked, not Escaped: a backdrop exists precisely to be clicked
        # through, and Escape leaves the transparent kind in place — after which
        # every following run failed on its first click, quoting the backdrop as
        # the thing intercepting pointer events.
        for _ in range(4):
            backdrop = self.page.locator(".cdk-overlay-backdrop")
            if not backdrop.count():
                break
            try:
                backdrop.last.click(timeout=3000, force=True)
            except Exception:
                self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(500)

    def _ensure_vi(self) -> None:
        """Force the Vietnamese UI, because every selector below is a VI label.

        Flow follows the Google account's display language, and it can flip to
        English on its own — after which the settings pill is called "Settings
        trigger" and every label lookup in this file fails with a message about
        a missing pill rather than about the language. `?hl=vi` pins it.
        """
        if self.page.evaluate("document.documentElement.lang") == "vi":
            return
        url = self.page.url.split("?")[0]
        self.page.goto(f"{url}?hl=vi", wait_until="domcontentloaded", timeout=60_000)
        self.page.wait_for_timeout(4000)

    def ensure_project(self) -> None:
        wrong_project = self.project_url and self.project_url not in self.page.url
        if wrong_project or "/project/" not in self.page.url:
            if self.project_url:
                self.page.goto(self.project_url, wait_until="domcontentloaded", timeout=60_000)
            else:
                self.dismiss_modals()
                for label in NEW_PROJECT:
                    btn = self.page.get_by_role("button", name=re.compile(re.escape(label)))
                    if btn.count():
                        btn.first.click(timeout=10_000)
                        break
                else:
                    raise FlowError("project: no open project and no 'Dự án mới' button")
            self.page.wait_for_timeout(4000)
        self._ensure_vi()
        self.dismiss_modals()

        # Last resort, and only here at the start of a clip where nothing is
        # staged yet: a reload is the one thing that always clears an overlay.
        # One clip failing mid-menu used to poison every clip after it — the
        # leftover backdrop swallowed the first click of the next attach, and a
        # run of seven came back with four generated and three that never began.
        if self.page.locator(".cdk-overlay-backdrop").count():
            self.page.reload(wait_until="domcontentloaded", timeout=60_000)
            self.page.wait_for_timeout(4000)
            self.dismiss_modals()

    def wait_prompt_bar(self, timeout_s: int = 90) -> None:
        try:
            self.page.locator('div[contenteditable="true"]').first.wait_for(
                state="visible", timeout=timeout_s * 1000)
        except Exception as exc:
            raise FlowError(f"prompt bar: never appeared within {timeout_s}s") from exc

    # ------------------------------------------------------------ settings

    def _open_panel(self) -> None:
        """Open the settings popover and prove it is open before touching it.

        Clicking the pill toggles, so a blind click on an already-open panel
        closes it and every following selector times out with a message about
        the radio rather than about the panel.
        """
        for _ in range(3):
            if self.page.locator("[role=radio]").count() >= 8:
                return
            pill = self._visible("button", SETTINGS_PILL)
            if pill is None:
                # The prompt bar mounts before its pill does; give it a moment
                # rather than failing on the first paint after a navigation.
                try:
                    self.page.get_by_role("button", name=SETTINGS_PILL).first.wait_for(
                        state="visible", timeout=15_000)
                except Exception as exc:
                    raise FlowError("settings: the settings pill is not on the page") from exc
                pill = self._visible("button", SETTINGS_PILL)
            try:
                pill.first.click(timeout=10_000)
            except Exception:
                # A leftover Angular backdrop from an earlier run swallows the real click
                # and Playwright just waits it out. Clear it, then click from script.
                self.dismiss_modals()
                self.page.evaluate(
                    """(label) => {
                        const b = [...document.querySelectorAll('button')]
                            .find(b => (b.getAttribute('aria-label') || '') === label);
                        if (b) b.click();
                    }""", SETTINGS_PILL)
            self.page.wait_for_timeout(1500)
        raise FlowError("settings: the settings popover would not stay open")

    def _set_radio(self, label: str, step: str) -> None:
        """Click the radio carrying `label` as a whole line of its own text.

        The radios have no `aria-label`, and their text is the Material Symbols
        ligature plus the label on separate lines ("videocam\nVideo"), so
        get_by_role(name=...) misses; and a substring match on the joined text
        would make "x1" match an "x10" if Flow ever offers one.
        """
        radios = self.page.locator("[role=radio]")
        for i in range(radios.count()):
            el = radios.nth(i)
            if label in [line.strip() for line in el.inner_text().split("\n")]:
                if el.get_attribute("aria-checked") != "true":
                    el.click(timeout=8000)
                    self.page.wait_for_timeout(400)
                return
        offered = " | ".join(sorted(
            {line.strip() for i in range(radios.count())
             for line in radios.nth(i).inner_text().split("\n") if line.strip()}))
        raise FlowError(f"settings: {step} — Flow does not offer {label!r}. It offers: {offered}")

    def _select_model(self, model: str, exact: bool = False) -> str:
        """Pick a model by label. `exact` compares whole labels, which the image
        family needs: "Nano Banana 2" is a substring of "Nano Banana 2 Lite"."""
        def hit(label: str) -> bool:
            return label == model if exact else bool(re.search(re.escape(model), label, re.I))

        row = self._visible("button", MODEL_ROW)
        if row is None:
            raise FlowError("settings: model dropdown not found in the settings popover")
        current = _clean_model_label(row.first.inner_text(timeout=3000))
        if hit(current):
            return current

        row.first.click(timeout=8000)
        self.page.wait_for_timeout(1000)
        options = self.page.locator("[role=menuitem], [role=option], [role=menuitemradio]")
        labels = []
        for i in range(options.count()):
            opt = options.nth(i)
            if not opt.is_visible():
                continue
            label = _clean_model_label(opt.inner_text(timeout=1500))
            labels.append(label)
            if hit(label):
                opt.click(timeout=8000)
                self.page.wait_for_timeout(1200)   # the popover re-renders
                return label
        # Never fall back to "any model": they differ in price, length and which
        # controls exist, so quietly using another is a silent wrong delivery.
        raise FlowError(
            f'settings: "{model}" is not one of Flow\'s models; the dropdown reads '
            f'"{current}" and offers: {" | ".join(labels) or "nothing"}')

    def apply_settings(self, *, aspect: str, model: str,
                       duration: Optional[str] = None,
                       resolution: Optional[str] = None,
                       count: int = 1,
                       submode: str = FRAMES_SUBMODE) -> dict[str, Any]:
        """Apply the video settings popover.

        `submode` picks between Flow's two video sub-modes, and they are not
        interchangeable: `FRAMES_SUBMODE` ("Khung hình") gives the composer its
        "Bắt đầu"/"Kết thúc" frame slots and is what `attach_image` fills, while
        `ELEMENTS_SUBMODE` ("Thành phần") drops that pair of slots and instead
        takes any number of reference images as prompt chips — the only one of
        the two that can carry more than a start and an end frame.
        """
        self._open_panel()

        self._set_radio("Video", "video mode")
        self._set_radio(submode, "video sub-mode")

        # Model first: it decides whether the duration and resolution rows exist
        # at all. The Omni models render both; the Veo ones render neither and
        # run at their own fixed length.
        chosen_model = self._select_model(model)

        if aspect not in ASPECT_LABEL:
            raise FlowError(f"settings: aspect {aspect} is not offered by Flow (16:9 or 9:16)")
        self._set_radio(ASPECT_LABEL[aspect], f"aspect {aspect}")

        if resolution:
            self._set_radio(resolution.lower(), f"resolution {resolution}")
        if duration:
            self._set_radio(f"{duration} giây", f"duration {duration}s")
        self._set_radio(f"x{count}", f"output count x{count}")

        panel_text = self.page.locator("[role=radio]").first.evaluate(
            "el => (el.closest('[class*=panel],[class*=popover],[role=dialog]')"
            " || document.body).innerText")
        hit = re.search(r"(\d+)\s*(tín dụng|credits?)", panel_text, re.I)
        credits = int(hit.group(1)) if hit else None

        pill = self._pill_text()
        self._close_panel()
        return {"model": chosen_model, "credits": credits, "pill": pill}

    def apply_image_settings(self, *, aspect: str, model: str, count: int = 1) -> dict[str, Any]:
        """Image mode: "Hình ảnh" + a Nano Banana model + aspect + output count.

        Measured 2026-09-05: the image popover has no sub-mode, no duration and
        no resolution rows, and reads "Quá trình tạo sẽ tốn 0 tín dụng" for every
        Nano Banana model — images do not draw on the daily allowance.
        """
        if aspect not in IMAGE_ASPECT_PILL:
            raise FlowError(f"settings: image aspect {aspect} is not offered by Flow "
                            f"({', '.join(IMAGE_ASPECT_PILL)})")
        self._open_panel()
        self._set_radio(IMAGE_MODE, "image mode")
        chosen_model = self._select_model(model, exact=True)
        self._set_radio(aspect, f"aspect {aspect}")
        self._set_radio(f"x{count}", f"output count x{count}")

        panel_text = self.page.locator("[role=radio]").first.evaluate(
            "el => (el.closest('[class*=panel],[class*=popover],[role=dialog]')"
            " || document.body).innerText")
        hit = re.search(r"(\d+)\s*(tín dụng|credits?)", panel_text, re.I)
        credits = int(hit.group(1)) if hit else None

        pill = self._pill_text()
        self._close_panel()
        return {"model": chosen_model, "credits": credits, "pill": pill}

    def verify_image_settings(self, *, aspect: str, count: int) -> None:
        pill = self._pill_text()
        want = [(IMAGE_ASPECT_PILL[aspect], f"aspect {aspect}"), (f"x{count}", f"output count x{count}")]
        missing = [why for token, why in want if token not in pill]
        if missing:
            raise FlowError(
                f"settings: Flow did not accept {', '.join(missing)} — "
                f'the pill still reads "{pill}". Nothing was generated.')

    def _pill_text(self) -> str:
        pill = self._visible("button", SETTINGS_PILL)
        if pill is None:
            raise FlowError("settings: the settings pill vanished before it could be read back")
        return " ".join(pill.first.inner_text().split())

    def verify_settings(self, *, aspect: str, duration: Optional[str],
                        resolution: Optional[str], count: int) -> None:
        """Read the pill back and refuse to spend credits on the wrong setting.

        The pill is the app's own summary of what the next click will buy, and
        it does not always agree with what the tab was left on: this one was
        found at `x2` and `crop_16_9` from an earlier session, which would have
        doubled the cost of every clip and delivered landscape for a portrait
        series. Asserting is cheaper than noticing after six clips.
        """
        pill = self._pill_text()
        want = [("crop_" + aspect.replace(":", "_"), f"aspect {aspect}"),
                (f"x{count}", f"output count x{count}")]
        if duration:
            want.append((f"{duration} giây", f"duration {duration}s"))
        if resolution:
            want.append((resolution.lower(), f"resolution {resolution}"))
        missing = [why for token, why in want if token not in pill]
        if missing:
            raise FlowError(
                f"settings: Flow did not accept {', '.join(missing)} — "
                f'the pill still reads "{pill}". Nothing was generated.')

    def _close_panel(self) -> None:
        for _ in range(4):
            if self.page.locator("[role=radio]").count() < 8:
                self.dismiss_modals()
                return
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(500)
        raise FlowError("settings: popover would not close (it blocks the editor)")

    # -------------------------------------------------------- reference image

    def _content_ids(self) -> set[str]:
        return set(self.page.evaluate(
            """() => [...document.querySelectorAll('img')]
                   .map(i => (i.src.match(/flow-content\\.google\\/image\\/([0-9a-f-]{36})/)||[])[1])
                   .filter(Boolean)"""))

    def attach_image(self, path: Path, end_path: Optional[Path] = None) -> str:
        """Put images in the composer's opening and, optionally, closing slot.

        Two steps per image, because in "Khung hình" mode the composer has no
        upload of its own: the prompt bar shows a "Bắt đầu" and a "Kết thúc"
        slot, and a slot can only choose something already in the project
        library. So the file goes into the library through the toolbar first,
        then into the slot through the picker.

        Each is uploaded under a fresh name every time. The picker identifies
        assets by filename, and re-uploading the same six frames across eight
        shots would leave the picker with eight rows called `a_tuoi_cay.jpg` and
        no way to say which one this shot meant.

        `end_path` fills the closing slot, which is how a chained sequence lands
        on an exact artwork instead of wherever the model drifts to.
        """
        start_name = self.upload_only(path)
        end_name = self.upload_only(end_path) if end_path else None
        return self.attach_uploaded(start_name, end_name)

    def upload_only(self, path: Path) -> str:
        """Send one image to the project library, without touching either slot.

        Split out of `attach_image` so a batch can pre-upload every shot's
        frame before any generation starts, instead of uploading one shot at
        a time in the middle of its own run. Returns the library's unique
        filename — pass it to `attach_uploaded` later, from any FlowDriver
        session, since the library lives on the project, not the tab.
        """
        unique = f"{path.stem}_{uuid.uuid4().hex[:8]}{path.suffix}"
        staged = Path(tempfile.gettempdir()) / unique
        shutil.copyfile(path, staged)
        try:
            self._upload_to_library(staged)
        finally:
            staged.unlink(missing_ok=True)
        return unique

    def attach_reference_images(self, paths: list[Path]) -> list[str]:
        """Attach reference images to the prompt bar. Returns library names.

        Used by image mode and by video's "Thành phần" sub-mode, which share
        this control. Neither has "Bắt đầu"/"Kết thúc" slots — `_fill_slot` does
        not apply, and a reference is not a start frame: it pins what a subject
        looks like without dictating frame one. Its attach control lives on the
        prompt bar itself
        (`PROMPT_ADD_ELEMENT`, the `add` button) and drops the picked assets in
        as reference chips beside the prompt text.

        **One asset per picker session.** Measured in video's elements sub-mode:
        clicking a library entry attaches it and closes the pane immediately —
        there is no multi-select and no "Thêm vào câu lệnh" confirm (the confirm
        click below is kept only because image mode may still show one). The
        pane also has no search box there, so its "Gần đây" list is whatever was
        rendered when it opened and never refreshes. Re-opening is therefore not
        just how the next asset is picked, it is the only way to see a file that
        finished uploading after the pane appeared — which is exactly how the
        first two-reference run failed, timing out on an asset that was in the
        library the whole time.

        A file is uploaded under a fresh unique name the first time it is seen —
        the picker identifies assets by filename, and re-using one name across
        runs leaves the list ambiguous — and that name is then remembered in
        `_upload_cache()`, so the same still attached to ten shots is uploaded
        once and picked out of the library nine times. A cached name that the
        picker no longer offers (the asset was deleted in Flow) just falls back
        to a fresh upload.
        """
        if not paths:
            return []
        self._clear_reference_chips()

        names = []
        for index, path in enumerate(paths):
            path = Path(path)
            name = self._cached_upload(path)
            # A short look for a remembered asset, a long one for a fresh upload:
            # the library takes a while to list a file it has only just accepted,
            # but one it accepted last week is either there now or gone for good.
            asset = self._pick_from_library(name, 30) if name else None
            if asset is None:
                name = self.upload_only(path)
                self._remember_upload(path, name)
                asset = self._pick_from_library(name, 90)
            if asset is None:
                raise FlowError(f"attach: {name} is not offered by the reference picker")
            names.append(name)
            asset.click(timeout=10_000)
            self.page.wait_for_timeout(1200)

            if self.page.locator(".cdk-overlay-pane").count():
                confirm = self._menu_item(
                    ADD_TO_PROMPT, self.page.locator(".cdk-overlay-pane").last)
                if confirm is not None:
                    confirm.click(timeout=10_000)
                    self.page.wait_for_timeout(1200)
            self.dismiss_modals()

            # A chip that did not land leaves the prompt a plain text-only run,
            # which silently ignores the reference the whole shot was built on —
            # the elements-mode twin of the empty-start-frame failure. Counting
            # matters as much as presence: a two-SKU shot that attaches one chip
            # renders a perfectly plausible clip carrying half the products.
            # `REF_CHIP` matches two nodes per chip, so chips are counted on the
            # button alone.
            landed = self.page.locator(REF_CHIP_BUTTON).count()
            if landed != index + 1:
                raise FlowError(
                    f"attach: {landed} reference chip(s) on the prompt bar after "
                    f"adding {name} — expected {index + 1}")
        return names

    def _pick_from_library(self, name: str, seconds: float):
        """Open the reference picker and hand back `name`'s entry, or None.

        Left open on success so the caller can click the entry; closed on
        failure. Re-opens on each pass because the pane's list is rendered once
        and never refreshed — see `attach_reference_images`.
        """
        deadline = time.time() + seconds
        while True:
            opener = self._visible("button", PROMPT_ADD_ELEMENT)
            if opener is None:
                raise FlowError(
                    f"attach: no {PROMPT_ADD_ELEMENT!r} button on the prompt bar "
                    '— Flow may not be in "Hình ảnh" mode or video\'s "Thành '
                    'phần" sub-mode')
            opener.first.click(timeout=10_000)
            self.page.wait_for_timeout(2000)
            pane = self.page.locator(".cdk-overlay-pane").last
            search = pane.get_by_placeholder(re.compile("Tìm kiếm|Search"))
            if search.count():
                search.first.fill(Path(name).stem)
                self.page.wait_for_timeout(2000)
            asset = self._menu_item(name, pane)
            if asset is not None:
                return asset
            self.dismiss_modals()
            if time.time() >= deadline:
                return None
            self.page.wait_for_timeout(3000)

    @staticmethod
    def _upload_cache() -> Path:
        return Path.home() / ".openmontage" / "flow_uploads.json"

    @staticmethod
    def _upload_key(path: Path) -> str:
        # Size and mtime, not a content hash: re-reading every reference image to
        # hash it costs more than the occasional redundant upload an edited file
        # with an unchanged mtime would cause.
        stat = path.stat()
        return f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"

    def _cached_upload(self, path: Path) -> Optional[str]:
        """The library name this exact file was last uploaded under, if any."""
        cache = self._upload_cache()
        if not cache.is_file():
            return None
        try:
            return json.loads(cache.read_text(encoding="utf-8")).get(self._upload_key(path))
        except (json.JSONDecodeError, OSError):
            return None  # a corrupt cache costs one upload, never a run

    def _remember_upload(self, path: Path, name: str) -> None:
        cache = self._upload_cache()
        try:
            known = json.loads(cache.read_text(encoding="utf-8")) if cache.is_file() else {}
        except (json.JSONDecodeError, OSError):
            known = {}
        known[self._upload_key(path)] = name
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(known, indent=1), encoding="utf-8")

    def _clear_reference_chips(self) -> None:
        """Remove any reference chips left on the prompt bar by an earlier run.

        The page outlives a FlowDriver, so without this the next image inherits
        the previous job's references and nothing in the output says why.
        """
        for _ in range(6):
            chips = self.page.locator(REF_CHIP_BUTTON)
            if not chips.count():
                return
            chips.first.click(timeout=10_000)
            self.page.wait_for_timeout(600)
        raise FlowError("attach: the prompt bar's reference chips would not clear")

    def attach_uploaded(self, filename: str, end_filename: Optional[str] = None) -> str:
        """Fill the composer's frame slots from assets already in the library."""
        self._clear_frames()
        names = []
        for name, slot in ((filename, START_FRAME_SLOT), (end_filename, END_FRAME_SLOT)):
            if name is None:
                continue
            self._fill_slot(slot, name)
            names.append(name)
        return " + ".join(names)

    def _upload_to_library(self, staged: Path) -> None:
        """Send one file to the project library through the toolbar.

        The upload item has no `<input type=file>` anywhere in the DOM — it
        opens the OS file dialog — so the only way in is `expect_file_chooser`.
        """
        before = self._content_ids()
        menu = self._visible("button", ADD_MEDIA_MENU)
        if menu is None:
            raise FlowError("attach: the toolbar add-media button is not on the page")
        menu.first.click(timeout=10_000)
        self.page.wait_for_timeout(900)

        upload = self._menu_item(UPLOAD_ITEM)
        if upload is None:
            raise FlowError(f"attach: no {UPLOAD_ITEM!r} item in the add-media menu")
        with self.page.expect_file_chooser(timeout=20_000) as chooser:
            upload.click(timeout=10_000)
        chooser.value.set_files(str(staged))

        deadline = time.time() + 120
        while time.time() < deadline:
            self.page.wait_for_timeout(2000)
            if self._content_ids() - before:
                self.dismiss_modals()
                return
        raise FlowError(f"attach: {staged.name} never reached the project library")

    def _clear_frames(self) -> None:
        """Empty both frame slots.

        The page outlives a FlowDriver — the tool builds one per clip against
        the same tab — so clip 02 arrives to find clip 01's artwork still
        loaded, and a filled slot has no "Bắt đầu" button left to click. Both
        are cleared rather than only the one about to be used: with two slots
        filled there are two identical remove buttons and nothing in the DOM
        says which belongs to which, so the only unambiguous state is empty.
        """
        for _ in range(4):
            remove = self._visible("button", FRAME_REMOVE)
            if remove is None:
                return
            remove.first.click(timeout=10_000)
            self.page.wait_for_timeout(1000)
        raise FlowError("attach: the frame slots would not empty")

    def _fill_slot(self, label: str, filename: str) -> None:
        slot = self.page.get_by_role("button", name=label, exact=True)
        if not slot.count():
            raise FlowError(
                f"attach: no empty {label!r} slot on the prompt bar — "
                'Flow may not be in "Khung hình" mode')
        slot.first.click(timeout=10_000)
        self.page.wait_for_timeout(1500)

        # The library accepts the file well before the picker lists it, so the
        # search is retyped until the asset shows up rather than asked once.
        # A single attempt passed by hand and failed on the first real shot.
        asset = None
        deadline = time.time() + 60
        while asset is None and time.time() < deadline:
            pane = self.page.locator(".cdk-overlay-pane").last
            search = pane.get_by_placeholder(re.compile("Tìm kiếm|Search"))
            if search.count():
                search.first.fill(Path(filename).stem)
            self.page.wait_for_timeout(2500)
            asset = self._menu_item(filename, pane)
        if asset is None:
            raise FlowError(f"attach: {filename} is not offered by the frame picker")
        asset.click(timeout=10_000)
        self.page.wait_for_timeout(700)

        # Picking an asset usually applies it and closes the picker on its own;
        # the "Thêm vào câu lệnh" button is only there for the multi-select case.
        # Requiring it made a successful attach look like a failure.
        if self.page.locator(".cdk-overlay-pane").count():
            confirm = self._menu_item(ADD_TO_PROMPT, self.page.locator(".cdk-overlay-pane").last)
            if confirm is not None:
                confirm.click(timeout=10_000)
        self.page.wait_for_timeout(1500)
        self.dismiss_modals()

        # An empty slot is a button carrying the slot's own label; a filled one
        # is not. Without this the run would generate text-to-video at full
        # price and ignore the artwork the whole clip is built on.
        if self.page.get_by_role("button", name=label, exact=True).count():
            raise FlowError(f"attach: {filename} did not land in the {label!r} slot")

    # -------------------------------------------------------------- prompt

    def _editor(self):
        editor = self.page.locator('div[contenteditable="true"]').first
        if not editor.count():
            raise FlowError("prompt: no contenteditable prompt box on the page")
        return editor

    def type_prompt(self, text: str) -> None:
        editor = self._editor()
        editor.click(timeout=10_000)
        self.page.wait_for_timeout(300)
        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Delete")
        # Typed key by key, because the editor is a ProseMirror instance that
        # ignores a value assignment. The timeout has to scale with the text:
        # the series prompts run past 2300 characters, and Playwright's 30s
        # default expires around the 1200th keystroke — mid-sentence, with the
        # settings already applied and nothing generated.
        editor.type(text, delay=1, timeout=60_000 + 30 * len(text))
        self.page.wait_for_timeout(600)

        got = " ".join(editor.inner_text().split())
        want = " ".join(text.split())
        if got[:80] != want[:80]:
            raise FlowError(
                f"prompt: the box did not take the text. It reads {got[:80]!r}, "
                f"expected {want[:80]!r}")

    # ---------------------------------------------------------- generation

    def _back_to_grid(self) -> None:
        """Leave the scene editor if the tab is in it.

        Clicking a tile navigates to `/project/<id>/edit/<scene>`, where there
        are no `flow-video-tile` elements at all. Every "the menu would not
        open" failure while this was written came from that: the page had moved
        and the grid selectors were being retried against a page that no longer
        had a grid. Note the editor's own download button is not a shortcut —
        it says "Tải cảnh xuống" and opens an "Exporting your scene…" render,
        which is a second pass over a clip that is already finished.
        """
        # Always navigate, even when already on the grid. Menus and their
        # transparent backdrops survive a failed run and then intercept the
        # first hover of the next one; a reload is the only state reset that
        # does not depend on Escape reaching the right overlay.
        target = self.project_url or self.page.url.split("/edit/")[0]
        for attempt in range(3):
            try:
                self.page.goto(target, wait_until="domcontentloaded", timeout=60_000)
                break
            except Exception as exc:
                # net::ERR_CONNECTION_CLOSED shows up on Flow's edge now and then;
                # a second attempt a few seconds later goes through.
                if attempt == 2:
                    raise FlowError(f"grid: could not reload {target}: {exc}") from exc
                self.page.wait_for_timeout(5000)
        self.page.wait_for_timeout(4000)
        self.dismiss_modals()

    def newest_clip(self) -> Optional[str]:
        """Caption of the newest clip in the project, or None if there is none.

        Identity comes from the tile, not from a `<video>` element. A finished
        clip does mount its own player *sometimes* — it did on the first probe,
        which is how the first version of this file came to trust it — but a
        real shot finished with its tile in the grid and no player mounted at
        all, and the wait sat there for its full 810 seconds while the clip it
        was waiting for was already on screen. Worse, the one player that *was*
        mounted belonged to an older clip and served a
        `flow.google.com/asb/<token>` url rather than the
        `flow-content.google/video/<id>` the probe had seen, so even the id
        pattern the driver was matching on was only true of a clip that had just
        been made.

        The grid is a `cdk-virtual-scroll-viewport`, so it is scrolled to the
        top first: tiles unmount as it moves, and new clips land at index 0.
        """
        return self._newest_tile(VIDEO_TILE)

    def newest_image(self) -> Optional[str]:
        """Caption of the newest image in the project (`flow-image-tile`)."""
        return self._newest_tile(IMAGE_TILE)

    def _newest_tile(self, tag: str) -> Optional[str]:
        self.page.evaluate(
            "() => { const v = document.querySelector('.cdk-virtual-scroll-viewport');"
            "        if (v) v.scrollTop = 0; }")
        self.page.wait_for_timeout(600)
        tiles = self.page.locator(tag)
        if not tiles.count():
            return None
        return _caption(tiles.first.inner_text())

    def submit(self) -> None:
        send = self._visible("button", START_GENERATION)
        if send is None:
            raise FlowError("submit: the generate button is not on the prompt bar")
        send.first.click(timeout=10_000)

    def wait_generation(self, before: Optional[str], timeout_s: float,
                        tag: str = VIDEO_TILE) -> str:
        """Wait for a render to be visibly in flight, then for it to land.

        The caption is not identity. Flow now titles a tile with a short
        model-authored summary, so re-running a shot with the same prompt
        produces the *same* caption every time and `newest != before` never
        fires. Counting mounted tiles does not help either: the grid is a
        `cdk-virtual-scroll-viewport`, so `locator(tag).count()` is how many
        tiles are mounted in the visible window, not how many exist. Comparing
        the top-3 caption *sequence* was the next attempt, and it aliases too —
        once three identical captions sit at the top, the sequence before and
        after a new arrival is the same list.

        What cannot alias is `flow-pending-tile`. Measured live on one image:

            t=10s  "67% <prompt>"                    pending=1
            t=30s  "99% <prompt>"                    pending=1
            t=40s  "Woman stripping hydrangea stem"  pending=0

        So wait for the render to start, then for it to stop. `before` only
        still matters for the case where the render finishes between two polls
        and was never observed in flight.
        """
        deadline = time.time() + timeout_s
        started = False
        while time.time() < deadline:
            self.page.wait_for_timeout(5000)
            newest = self._newest_tile(tag)
            in_flight = bool(self.page.locator("flow-pending-tile").count()) or                 bool(newest and PROGRESS_RE.match(newest))
            if in_flight:
                started = True
                continue
            if newest and (started or newest != before):
                if PROGRESS_RE.match(newest):
                    continue          # still rendering; the caption is not final
                if FAILED_RE.search(newest):
                    raise FlowError(
                        f"generation refused by Flow: {newest.strip()!r}. Flow says "
                        f"whether it charged for the attempt; read that line before "
                        f"assuming credits were spent.")
                # Settle before believing it. A tile appears while the clip is
                # still rendering, and downloading then would take a placeholder
                # under the finished shot's filename.
                self.page.wait_for_timeout(10_000)
                if self._newest_tile(tag) == newest:
                    return newest
        raise FlowError(f"generation timeout after {timeout_s:.0f}s")

    def _top_captions(self, tag: str, n: int) -> list[str]:
        self.page.evaluate(
            "() => { const v = document.querySelector('.cdk-virtual-scroll-viewport');"
            "        if (v) v.scrollTop = 0; }")
        self.page.wait_for_timeout(600)
        tiles = self.page.locator(tag)
        count = min(n, tiles.count())
        return [_caption(tiles.nth(i).inner_text()) for i in range(count)]

    def _open_tile_menu(self, tile) -> None:
        """Open a tile's "Tuỳ chọn khác" menu.

        Video tiles expose the button to `get_by_role`; image tiles render it
        only while hovered and its accessible name does not resolve, so it is
        found by aria-label and clicked from script.

        A single `.hover()` teleports the cursor straight to the tile's
        centre, and Flow's hover-reveal — already known flaky for the inner
        download submenu, see the mouse dance in `_download_tile` — turned
        out to be just as flaky for this outer toolbar. Confirmed live
        2026-09-10: a plain `.hover()` left "Tuỳ chọn khác" absent from the
        accessibility tree entirely, no error, just nothing revealed. The fix
        is the same one that already works below: move *across* the tile
        rather than jump to its middle, and retry a few times before falling
        back to the aria-label script click.
        """
        box = tile.bounding_box()
        if box is None:
            raise FlowError("download: the tile has no position on screen")
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        candidates = [tile.get_by_role("button", name=lbl) for lbl in TILE_MORE]
        for _ in range(4):
            self.page.mouse.move(box["x"] - 20, cy)
            self.page.wait_for_timeout(200)
            self.page.mouse.move(cx, cy)
            self.page.wait_for_timeout(900)
            hit = next((c for c in candidates if c.count()), None)
            if hit is not None:
                hit.first.click(timeout=10_000)
                self.page.wait_for_timeout(1200)
                return
        else:
            clicked = tile.evaluate(
                """(t, labels) => {
                    const b = [...t.querySelectorAll('button')].find(b => {
                        const a = b.getAttribute('aria-label') || '';
                        return labels.some(l => a.includes(l));
                    });
                    if (!b) return false;
                    b.click();
                    return true;
                }""", TILE_MORE)
            if not clicked:
                seen = tile.evaluate(
                    "t => [...t.querySelectorAll('button')]"
                    "      .map(b => b.getAttribute('aria-label')).filter(Boolean)")
                raise FlowError(
                    f"download: the tile has no options button. It offers: {seen}. "
                    f"Looked for any of {TILE_MORE} — Flow renders this toolbar in the "
                    f"account's language, not the page's, so a new locale needs adding.")
        self.page.wait_for_timeout(1200)

    @staticmethod
    def _pick_row(rows: list[str], quality: str) -> Optional[str]:
        """Choose the download row's text for `quality`.

        "native"  — the size the clip was rendered at, always included in the plan.
        "max"     — the highest resolution the plan actually allows: upscale rows are
                    fair game, rows marked "Nâng cấp" are not (they are a paywall).
        "1080p"   — an explicit tier; raises rather than silently taking another size,
        "2K", ...   because a silent downgrade is how a 4K promise ships at 720p.
        Rows whose leading token is not a resolution (e.g. "270p Ảnh GIF động" is,
        but a bare "Kích thước gốc" panel echo is not) are ignored.
        """
        native = next((t for t in rows if any(_same_text(x, t) for x in NATIVE_SIZE) and RES_RE.match(t)), None)
        if quality == "native":
            return native
        if quality != "max":
            # An explicit tier such as "1080p" or "2K": match the row's leading token.
            want = quality.strip().lower()
            exact = next((t for t in rows
                          if RES_RE.match(t) and (RES_RE.match(t).group(1) + RES_RE.match(t).group(2)).lower() == want
                          and not any(_same_text(x, t) for x in PLAN_GATED) and "GIF" not in t.upper()), None)
            if exact is None:
                raise FlowError(
                    f"download: Flow does not offer {quality!r} for this media. "
                    f"Offered: {' | '.join(rows) or 'nothing'}")
            return exact
        def px(text: str) -> int:
            m = RES_RE.match(text)
            if not m:
                return -1
            n = int(m.group(1))
            return n * 1000 if m.group(2).lower() == "k" else n
        allowed = [t for t in rows
                   if RES_RE.match(t) and not any(_same_text(x, t) for x in PLAN_GATED) and "GIF" not in t.upper()]
        if not allowed:
            return native
        best = max(allowed, key=px)
        return best if px(best) >= (px(native) if native else 0) else native

    def _download_tile(self, tile, out_path: Path, min_bytes: int, quality: str = "native",
                       attempts: int = 2) -> int:
        """Tile menu → "Tải xuống" → the row for `quality`, then collect the file.

        Flow's download submenu is a proper ARIA `menu` of `menuitem` rows now,
        not the boxless custom elements the pixel-sweep code this replaced had
        to fight with `elementFromPoint` across up to 64 point-probes per
        attempt. Confirmed live via accessibility snapshot and a real
        `get_by_role(...).click()`, 2026-09-10 — a genuine Playwright click
        lands and starts the download; the old code's "a real click does
        nothing here" note describes a UI Flow has since changed. Role-based
        locators auto-wait properly besides being faster, which is most of why
        this used to need a retry loop with a 300s blind wait at all.

        A click that starts no download is still recovered rather than eaten
        by one long wait: `_catch_download` waits 100s per attempt, and a miss
        reopens the tile menu from scratch (the outer hover dance in
        `_open_tile_menu` is untouched — that one's tuned against a specific
        past failure) and tries again.
        """
        last_err: Optional[FlowError] = None
        for attempt in range(1, attempts + 1):
            self._open_tile_menu(tile)
            entry = self._menu_item(DOWNLOAD_ITEM)
            if entry is None:
                raise FlowError(f"download: no entry matching {DOWNLOAD_ITEM} on the tile menu")

            rows: list[str] = []
            for _ in range(3):
                entry.hover(timeout=5000)
                self.page.wait_for_timeout(700)
                # Only rows this plan can actually click. Flow used to mark a
                # paywalled tier with the word "Nâng cấp" in the row; it now
                # ships the row `disabled` with its normal label, so the text
                # filter below let "4K Đã tăng độ phân giải" through and the
                # click sat waiting for an element that would never enable.
                rows = [t.strip() for t in self.page.evaluate(
                    """() => [...document.querySelectorAll('[role=menuitem]')]
                        .filter(b => !b.disabled
                                     && b.getAttribute('aria-disabled') !== 'true'
                                     && !(b.className || '').includes('menu-item-disabled'))
                        .map(b => (b.innerText || '').trim())""")
                       if RES_RE.match(t.strip())]
                if rows:
                    break
            chosen = self._pick_row(rows, quality)
            if chosen is None:
                offered = " | ".join(rows) or "nothing"
                raise FlowError(f"download: no usable size row in the download submenu. Offered: {offered}")
            self.last_download_row = chosen
            try:
                return self._catch_download(out_path, chosen, min_bytes, timeout_s=100)
            except FlowError as err:
                last_err = err
                if attempt >= attempts:
                    raise
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(800)
                self.dismiss_modals()
        raise last_err  # unreachable, satisfies type-checkers

    def download_images(self, out_paths: list[Path], quality: str = "native") -> list[int]:
        """Save the newest `len(out_paths)` images, newest first.

        An `xN` generation lands N tiles at the top of the grid, all captioned
        alike, so they are taken by position after one reload. Each download
        leaves a menu backdrop behind; Escape clears it before the next hover.
        """
        self._started_at = time.time()
        self._back_to_grid()
        self.dismiss_modals()
        tiles = self.page.locator(IMAGE_TILE)
        tiles.first.wait_for(state="visible", timeout=60_000)
        # No caption re-check here: `wait_generation` already proved the new
        # tile(s) landed at the top via the top-N sequence shift, same as the
        # video path. A second equality check against this reload's own
        # (possibly re-rendered) caption text is exactly the kind of check
        # that produced "the newest image is not the one this run generated"
        # against a tile that actually was the right one — confirmed live
        # 2026-09-13. Position after the reload is the trustworthy signal.
        sizes = []
        for i, out_path in enumerate(out_paths):
            if i >= tiles.count():
                raise FlowError(f"download: only {tiles.count()} image tiles in the grid, "
                                f"{len(out_paths)} were generated")
            self._started_at = time.time()
            sizes.append(self._download_tile(tiles.nth(i), out_path, MIN_IMAGE_BYTES, quality))
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(800)
            self.dismiss_modals()
        return sizes

    def download_clip(self, out_path: Path, caption: Optional[str] = None, quality: str = "native") -> int:
        """Save one clip using Flow's own download, at its native size.

        `caption` is the tile text `wait_generation` saw, and it is not
        optional in practice. This method reloads the grid first — the only
        reliable way to clear a stale overlay — and a reload throws away the
        state the wait had just confirmed: a pending tile that was sitting at
        index 0 is gone, and "the newest tile" is the *previous* shot again.
        That is not theoretical. Shot 02 of Ngày 7 came back as a byte-for-byte
        copy of shot 01, and only its duration gave it away.

        Not a fetch of the player's src: that url only exists while a player is
        mounted, changes host once the clip settles, and is signed with a short
        expiry. Flow's menu hands over the real file and does not care whether
        anything is playing.

        "720p Kích thước gốc" — original size — and never the 1080p or 4K
        entries beside it, which are labelled "Đã tăng độ phân giải" and are a
        second, paid pass over a clip that has already been paid for.
        """
        self._started_at = time.time()
        self._back_to_grid()
        self.dismiss_modals()
        tile = self._tile_for(caption)
        # "Tải xuống" opens its submenu on hover — but the hover has to be a
        # *movement across* the item, not a jump to its centre, and even then it
        # does not always take. `_download_tile` carries that dance.
        return self._download_tile(tile, out_path, MIN_VIDEO_BYTES, quality)

    def _tile_for(self, caption: Optional[str]):
        """The tile carrying `caption`, or the newest tile when none is given.

        Named rather than positional, because "index 0" means different clips
        before and after the reload this class performs, and downloading the
        wrong one produces a valid mp4 under the right filename (Ngày 7,
        shot 02 came back a byte-for-byte copy of shot 01).

        But the search is bounded to the top few tiles, not the whole grid.
        A genuinely new clip always lands within a handful of the top — Flow
        never buries it — while a project that has accumulated retries
        carries many *older* tiles sharing this shot's exact caption: Flow
        captions a tile with a short model-authored summary, not the prompt,
        so retrying one shot with identical or even reworded input produces
        the same caption on tile after tile. An unbounded scan happily
        matches whichever one it meets first, which on a cluttered grid can
        be several retries back. Confirmed 2026-09-10: chrome://downloads
        history showed only this driver's own genuinely-successful past
        downloads and nothing from the recent failed attempts at all — the
        click was landing on a tile whose menu never produced a real
        download, not on the fresh one.
        """
        self.page.locator("flow-video-tile").first.wait_for(
            state="visible", timeout=60_000)
        if caption is None:
            return self.page.locator("flow-video-tile").first

        window = 6
        deadline = time.time() + 90
        while time.time() < deadline:
            tiles = self.page.locator("flow-video-tile")
            for i in range(min(window, tiles.count())):
                tile = tiles.nth(i)
                if _caption(tile.inner_text()) == caption:
                    return tile
            self.page.wait_for_timeout(3000)
        raise FlowError(
            f"download: the clip this run generated is not among the top "
            f"{window} tiles. Looking for a tile reading {caption!r}. "
            f"Nothing was saved.")

    def _catch_download(self, out_path: Path, row_text: str,
                        min_bytes: int = MIN_VIDEO_BYTES,
                        timeout_s: float = 300) -> int:
        """Take the chosen row's file.

        The row is a real `menuitem` now, and a genuine Playwright click on it
        starts the download — verified live 2026-09-10. An older version of
        this method clicked via `elementFromPoint` + a script-dispatched
        `.click()` because a real mouse click supposedly landed and did
        nothing; that was true of an older Flow UI, not this one.

        The file is still collected from a directory this driver names, not
        from `expect_download`. That event never fires here — attaching over
        CDP does not give Playwright ownership of this browser's downloads.
        """
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sink = self._download_sink()
        self.page.get_by_role("menuitem", name=row_text, exact=True).first.click(timeout=5000)

        landed = self._wait_for_downloaded_file(sink, timeout_s=timeout_s)
        shutil.move(str(landed), str(out_path))

        size = out_path.stat().st_size
        if size < min_bytes:
            raise FlowError(f"download: {out_path.name} came back at {size} bytes, "
                            f"which is Flow's placeholder, not the media")
        return size

    def _download_sink(self) -> Path:
        """Point Chrome's downloads at a directory this driver owns.

        `Browser.setDownloadBehavior` has to be sent on a **browser-level** CDP
        session (`browser.new_browser_cdp_session()`) — a page-scoped session
        (`context.new_cdp_session(page)`) accepts the call without error and
        still applies the GUID naming, but silently ignores `downloadPath` on
        current Chrome (152.x). The observable symptom was a download that
        genuinely fired, landed in the user's real Downloads folder under a
        random-GUID `.tmp` name, and was never found — because this driver was
        watching a directory Chrome was never told about. Confirmed 2026-09-10
        by inspecting the live browser with Playwright MCP while the CDP call
        above raised nothing.
        """
        sink = Path(tempfile.gettempdir()) / "openmontage-flow-downloads"
        sink.mkdir(parents=True, exist_ok=True)
        try:
            session = self._browser.new_browser_cdp_session()
            session.send("Browser.setDownloadBehavior",
                         {"behavior": "allowAndName", "downloadPath": str(sink),
                          "eventsEnabled": True})
        except Exception:
            # Older endpoints only expose the page-level version.
            session = self.page.context.new_cdp_session(self.page)
            session.send("Page.setDownloadBehavior",
                         {"behavior": "allow", "downloadPath": str(sink)})
        return sink

    def _wait_for_downloaded_file(self, folder: Path, timeout_s: float = 300) -> Path:
        """Poll `folder` for a file that arrived after this shot started.

        `allowAndName` writes under a random GUID, and on current Chrome that
        file keeps a `.tmp` suffix even once complete — it is never renamed away
        and no sibling `.crdownload` marker exists either. So `.tmp` is not
        excluded here; instead "done" is "the same size on two checks in a
        row", which a still-downloading file fails and a finished one passes.
        """
        deadline = time.time() + timeout_s
        last_seen: dict[Path, int] = {}
        while time.time() < deadline:
            fresh = [f for f in folder.iterdir()
                     if f.is_file() and f.stat().st_mtime > self._started_at
                     and f.suffix != ".crdownload"
                     and not Path(str(f) + ".crdownload").exists()]
            for f in fresh:
                size = f.stat().st_size
                if last_seen.get(f) == size and size > 0:
                    self.page.wait_for_timeout(500)   # let the last block flush
                    return f
                last_seen[f] = size
            self.page.wait_for_timeout(1500)
        raise FlowError(f"download: nothing arrived in {folder} within {timeout_s:.0f}s")

    # ----------------------------------------------------------------- run

    def generate(self, job: dict[str, Any]) -> dict[str, Any]:
        """Drive one generation end to end. Returns what Flow actually did."""
        self.ensure_project()
        self.wait_prompt_bar()

        duration = job.get("duration")
        resolution = job.get("resolution")
        aspect = job.get("aspect_ratio", "16:9")

        # References and frame slots live in different sub-modes, so the choice
        # has to be made before the popover is closed, not after.
        refs = [Path(p) for p in (job.get("reference_images") or [])]
        applied = self.apply_settings(
            aspect=aspect,
            model=job.get("model_variant", "Quality"),
            duration=duration,
            resolution=resolution,
            submode=ELEMENTS_SUBMODE if refs else FRAMES_SUBMODE,
        )
        self.verify_settings(aspect=aspect, duration=duration,
                             resolution=resolution, count=1)

        media_ref = None
        if refs:
            media_ref = " + ".join(self.attach_reference_images(refs))
        elif job.get("operation") == "image_to_video":
            uploaded = job.get("asset_uploaded_name")
            if uploaded:
                media_ref = self.attach_uploaded(uploaded, job.get("end_asset_uploaded_name"))
            elif job.get("asset_path"):
                end = job.get("end_asset_path")
                media_ref = self.attach_image(Path(job["asset_path"]),
                                              Path(end) if end else None)

        self.type_prompt(job["prompt"])

        before = self.newest_clip()
        self.submit()
        media_id = self.wait_generation(
            before, float(job.get("timeout_seconds", 900)) - 90)
        # Position, not caption: `wait_generation` already proved the new clip is
        # at index 0 via the top-N sequence shift, and `download_clip` moves
        # straight from there into `_back_to_grid()` with nothing in between that
        # could reorder the list. Caption matching stays available as
        # `_tile_for`'s fallback (bounded to the top few tiles) for callers that
        # don't have this guarantee, but on a grid carrying many retries of the
        # same shot — same model-authored caption on every one — a caption
        # search can find an older tile before the fresh one. Verified
        # 2026-09-10: `download_clip(..., caption=None, ...)` against a tile the
        # generation loop had just confirmed pulled the right clip every time;
        # caption search had been missing it.
        size = self.download_clip(Path(job["output_path"]), None, job.get("quality", "native"))

        return {
            "output": job["output_path"],
            "bytes": size,
            "media_id": media_id,
            "reference_media_id": media_ref,
            "model": applied["model"],
            "credits": applied["credits"],
            "download_row": getattr(self, "last_download_row", None),
        }


    def _wait_no_pending(self, timeout_s: float = 180) -> None:
        """Let any in-flight generation (the user's, or agent mode's) settle.

        A `flow-pending-tile` sits over the prompt bar and intercepts pointer
        events, so a click on the chip or the pill lands on it instead.
        """
        deadline = time.time() + timeout_s
        while time.time() < deadline and self.page.locator("flow-pending-tile").count():
            self.page.wait_for_timeout(3000)

    def _agent_mode(self) -> Optional[bool]:
        """State of the "Tác nhân" chip, or None when the chip is absent."""
        chip = self.page.locator("flow-agent-mode-toggle-chip button")
        if not chip.count():
            return None
        return chip.first.get_attribute("aria-pressed") == "true"

    def _set_agent_mode(self, on: bool) -> None:
        if self._agent_mode() in (None, on):
            return
        self.page.locator("flow-agent-mode-toggle-chip button").first.click(timeout=8000)
        self.page.wait_for_timeout(1200)

    def generate_image(self, job: dict[str, Any]) -> dict[str, Any]:
        """Drive one image generation (x1..x4) end to end.

        job: prompt, model (full Flow label), aspect_ratio, count, output_paths
        (one per image), timeout_seconds.

        Flow's agent mode ("Tác nhân") replaces the prompt bar's settings pill
        with an instruction box, so it is switched off for the run and put back
        the way it was found.
        """
        self.ensure_project()
        self.wait_prompt_bar()
        self._wait_no_pending()
        agent_was_on = self._agent_mode()
        self._set_agent_mode(False)
        try:
            return self._generate_image(job)
        finally:
            if agent_was_on:
                try:
                    self._set_agent_mode(True)
                except Exception:
                    pass

    def _generate_image(self, job: dict[str, Any]) -> dict[str, Any]:
        aspect = job.get("aspect_ratio", "1:1")
        count = int(job.get("count", 1))
        applied = self.apply_image_settings(aspect=aspect, model=job["model"], count=count)
        self.verify_image_settings(aspect=aspect, count=count)

        refs = [Path(p) for p in (job.get("reference_images") or [])]
        media_ref = self.attach_reference_images(refs) if refs else []

        self.type_prompt(job["prompt"])
        before = self.newest_image()
        self.submit()
        caption = self.wait_generation(
            before, float(job.get("timeout_seconds", 600)) - 60, tag=IMAGE_TILE)
        # With xN the tiles finish at slightly different moments; wait for the
        # whole batch to stop reporting a percentage before downloading.
        if count > 1:
            deadline = time.time() + 180
            while time.time() < deadline:
                tiles = self.page.locator(IMAGE_TILE)
                captions = [_caption(tiles.nth(i).inner_text())
                            for i in range(min(count, tiles.count()))]
                if len(captions) == count and not any(PROGRESS_RE.match(c) for c in captions):
                    break
                self.page.wait_for_timeout(4000)
        sizes = self.download_images([Path(p) for p in job["output_paths"]], job.get("quality", "native"))
        return {
            "outputs": [str(p) for p in job["output_paths"]],
            "bytes": sizes,
            "media_id": caption,
            "reference_media_id": " + ".join(media_ref) if media_ref else None,
            "model": applied["model"],
            "credits": applied["credits"],
            "download_row": getattr(self, "last_download_row", None),
        }


def _clean_model_label(text: str) -> str:
    """Strip Flow's Material Symbols ligatures off a model label.

    The closed row reads "Omni 1.1 Flasharrow_drop_down" and an option reads
    "volume_up\nVeo 3.1 - Fast". The icon name is a lowercase token glued to
    the label with arbitrary whitespace.
    """
    cleaned = re.sub(r"^[a-z_]+\s*(?=[A-Z0-9])", "", (text or "").strip())
    cleaned = re.sub(r"\s*(arrow_drop_down|expand_more|unfold_more)\s*$", "", cleaned)
    return " ".join(cleaned.split())
