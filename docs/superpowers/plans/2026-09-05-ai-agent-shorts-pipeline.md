# AI-agent Shorts Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Từ một file `episodes/<slug>.yaml`, tự động quay màn hình thật của agent (terminal / trình duyệt / chat web) thành các clip dọc, sinh brief và checkpoint để pipeline `screen-demo` có sẵn dựng tiếp thành Short 45-90s.

**Architecture:** Python chỉ làm ba việc: đọc và validate spec, quay từng bước ra `step_<n>.mp4` + `capture_log.json`, sinh `brief` schema-valid và ghi checkpoint `idea`. Mọi stage sau đó (script → compose) do agent điều khiển theo director skill của `screen-demo`, cộng thêm một runner skill nói rõ cách dùng capture_log. Không có orchestration trong Python (AGENT_GUIDE: "Python = tools + persistence").

**Tech Stack:** Python 3.11, PyYAML, jsonschema, Playwright (sync API, đã cài), FFmpeg gdigrab qua `tools.capture.screen_recorder`, Windows Terminal (`wt.exe`) + ctypes user32, pytest. Không thêm dependency mới.

**Spec:** `docs/superpowers/specs/2026-09-05-ai-agent-shorts-pipeline-design.md`

## Global Constraints

- Output mỗi bước: MP4 H.264 yuv420p, dọc. Browser/chat quay thẳng 1080x1920. Terminal quay 675x1200 (màn hình máy là 1920x1200, không đặt vừa cửa sổ 1920 cao); compose upscale lên 1080x1920.
- Không API trả tiền. Test không mở mạng (conftest chặn socket), không mở trình duyệt thật, không gọi `wt.exe`.
- `render_runtime: remotion`, `composition_mode: templated`, playbook `ai-agent-shorts` — ghi vào decision_log một lần ở stage `idea`.
- Tool class PascalCase không hậu tố Tool, gọi qua `.execute(dict)` trả `ToolResult`.
- Mọi file ghi dưới `projects/<slug>/` (gốc từ `lib.paths.PROJECTS_DIR`; test đặt env `OPENMONTAGE_PROJECTS_DIR` hoặc truyền `pipeline_dir=tmp_path`).
- Không dùng `--dangerously-skip-permissions` cho phiên Claude Code diễn viên; dùng `--permission-mode acceptEdits` + `--allowedTools` từ spec.
- Commit mỗi task, message dạng `feat:`/`test:`/`docs:`; chỉ `git add` file của task (KHÔNG dùng `git commit -a`, working tree có file người dùng đang sửa dở).

---

## File map

| File | Trách nhiệm |
|---|---|
| `episodes/__init__.py` | package marker (spec YAML của tập cũng nằm trong thư mục này) |
| `episodes/spec.py` | dataclass `EpisodeSpec`/`Step`, `load_spec()`, `SpecError` |
| `episodes/brief.py` | `brief_from_spec()` → dict schema-valid, `channel_decisions()` → decision_log |
| `episodes/terminal_window.py` | fragment Windows Terminal, mở/định vị/đóng cửa sổ, lệnh cho Claude Code diễn viên |
| `episodes/chat_surface.py` | selector claude.ai/chatgpt.com, `run_chat_step(page, ...)` |
| `tools/capture/episode_capture.py` | `EpisodeCapture(BaseTool)`: quay tất cả bước, ghi `capture_log.json`, ảnh kiểm tra |
| `episodes/__main__.py` | CLI `validate` / `capture` / `run` |
| `styles/ai-agent-shorts.yaml` | playbook chung cả kênh |
| `skills/pipelines/screen-demo/episode-runner.md` | hướng dẫn agent chạy script → compose từ capture_log |
| `episodes/smoke.yaml` | tập mẫu 1 bước browser tới trang tĩnh |

---

### Task 1: Episode spec loader + validator

**Files:**
- Create: `episodes/__init__.py`
- Create: `episodes/spec.py`
- Test: `tests/test_episode_spec.py`

**Interfaces:**
- Produces:
  - `SURFACES = ("terminal", "browser", "chat")`, `HOOK_SECONDS = 3`, `CTA_SECONDS = 3`
  - `class SpecError(ValueError)`
  - `@dataclass(frozen=True) Step(index:int, surface:str, action:str, narration:str, hold:int, url:str|None=None)`
  - `@dataclass(frozen=True) EpisodeSpec(slug, title, hook, voice, target_seconds:int, steps:tuple[Step,...], cta:str, review_capture:bool=True, approval_policy:str="guided", allowed_tools:tuple[str,...]=(), actor_cwd:str|None=None, path:Path|None=None)`
  - `load_spec(path: Path) -> EpisodeSpec` (raise `SpecError`)
  - `planned_seconds(spec) -> int` = HOOK + sum(hold) + CTA

- [ ] **Step 1: Viết test fail**

```python
# tests/test_episode_spec.py
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from episodes.spec import HOOK_SECONDS, CTA_SECONDS, SpecError, load_spec, planned_seconds

GOOD = {
    "slug": "doc-mail-moi-sang",
    "title": "Để AI đọc mail giúp bạn mỗi sáng",
    "hook": "Sáng nào cũng 40 mail chưa đọc? Giao cho agent.",
    "voice": "Ngọc Linh",
    "target_seconds": 60,
    "steps": [
        {"surface": "terminal", "action": "Tóm tắt 10 mail mới nhất", "narration": "Gõ một câu.", "hold": 8},
        {"surface": "browser", "url": "https://mail.google.com", "action": "Mở mail đầu", "narration": "Kết quả ở đây.", "hold": 6},
    ],
    "cta": "Theo dõi để xem tập sau.",
}


def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "ep.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return p


def test_loads_a_valid_spec(tmp_path):
    spec = load_spec(_write(tmp_path, GOOD))
    assert spec.slug == "doc-mail-moi-sang"
    assert [s.index for s in spec.steps] == [1, 2]
    assert spec.steps[1].url == "https://mail.google.com"
    assert spec.review_capture is True
    assert spec.approval_policy == "guided"
    assert planned_seconds(spec) == HOOK_SECONDS + 14 + CTA_SECONDS


def test_rejects_when_holds_exceed_target(tmp_path):
    data = {**GOOD, "target_seconds": 15}
    with pytest.raises(SpecError, match="target_seconds"):
        load_spec(_write(tmp_path, data))


def test_rejects_step_without_narration(tmp_path):
    steps = [dict(GOOD["steps"][0], narration="")] + GOOD["steps"][1:]
    with pytest.raises(SpecError, match="narration"):
        load_spec(_write(tmp_path, {**GOOD, "steps": steps}))


def test_rejects_browser_step_without_url(tmp_path):
    steps = [GOOD["steps"][0], {k: v for k, v in GOOD["steps"][1].items() if k != "url"}]
    with pytest.raises(SpecError, match="url"):
        load_spec(_write(tmp_path, {**GOOD, "steps": steps}))


def test_rejects_unknown_surface_and_bad_slug(tmp_path):
    with pytest.raises(SpecError, match="surface"):
        load_spec(_write(tmp_path, {**GOOD, "steps": [dict(GOOD["steps"][0], surface="desktop")]}))
    with pytest.raises(SpecError, match="slug"):
        load_spec(_write(tmp_path, {**GOOD, "slug": "Doc Mail"}))
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `python -m pytest tests/test_episode_spec.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'episodes'`

- [ ] **Step 3: Implement**

```python
# episodes/__init__.py
"""Episode specs (YAML) and the code that turns them into captured footage."""
```

```python
# episodes/spec.py
"""Episode spec: the single input of the AI-agent Shorts pipeline.

One YAML per episode. This module only loads and validates; it never records
or renders. See docs/superpowers/specs/2026-09-05-ai-agent-shorts-pipeline-design.md §1.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

SURFACES = ("terminal", "browser", "chat")
HOOK_SECONDS = 3
CTA_SECONDS = 3
_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class SpecError(ValueError):
    """The spec cannot be produced as written."""


@dataclass(frozen=True)
class Step:
    index: int
    surface: str
    action: str
    narration: str
    hold: int
    url: str | None = None


@dataclass(frozen=True)
class EpisodeSpec:
    slug: str
    title: str
    hook: str
    voice: str
    target_seconds: int
    steps: tuple[Step, ...]
    cta: str
    review_capture: bool = True
    approval_policy: str = "guided"
    allowed_tools: tuple[str, ...] = ()
    actor_cwd: str | None = None
    path: Path | None = None


def planned_seconds(spec: EpisodeSpec) -> int:
    return HOOK_SECONDS + sum(s.hold for s in spec.steps) + CTA_SECONDS


def _step(i: int, raw: dict) -> Step:
    surface = raw.get("surface")
    if surface not in SURFACES:
        raise SpecError(f"step {i}: surface must be one of {SURFACES}, got {surface!r}")
    if not str(raw.get("narration", "")).strip():
        raise SpecError(f"step {i}: narration is required")
    if not str(raw.get("action", "")).strip():
        raise SpecError(f"step {i}: action is required")
    hold = raw.get("hold")
    if not isinstance(hold, int) or hold <= 0:
        raise SpecError(f"step {i}: hold must be a positive integer")
    url = raw.get("url")
    if surface in ("browser", "chat") and not url:
        raise SpecError(f"step {i}: {surface} steps need a url")
    return Step(i, surface, raw["action"], raw["narration"], hold, url)


def load_spec(path: Path) -> EpisodeSpec:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for key in ("slug", "title", "hook", "voice", "target_seconds", "steps", "cta"):
        if key not in raw:
            raise SpecError(f"missing required field {key!r}")
    if not _SLUG_RE.match(str(raw["slug"])):
        raise SpecError("slug must be kebab-case (a-z, 0-9, '-')")
    if not raw["steps"]:
        raise SpecError("steps must not be empty")
    steps = tuple(_step(i + 1, s) for i, s in enumerate(raw["steps"]))
    spec = EpisodeSpec(
        slug=raw["slug"],
        title=raw["title"],
        hook=raw["hook"],
        voice=raw["voice"],
        target_seconds=int(raw["target_seconds"]),
        steps=steps,
        cta=raw["cta"],
        review_capture=bool(raw.get("review_capture", True)),
        approval_policy=str(raw.get("approval_policy", "guided")),
        allowed_tools=tuple(raw.get("allowed_tools", ())),
        actor_cwd=raw.get("actor_cwd"),
        path=path,
    )
    if spec.approval_policy not in ("guided", "auto"):
        raise SpecError("approval_policy must be 'guided' or 'auto'")
    if planned_seconds(spec) > spec.target_seconds:
        raise SpecError(
            f"hook({HOOK_SECONDS}) + holds({sum(s.hold for s in steps)}) + cta({CTA_SECONDS}) "
            f"= {planned_seconds(spec)}s exceeds target_seconds={spec.target_seconds}"
        )
    return spec
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `python -m pytest tests/test_episode_spec.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add episodes/__init__.py episodes/spec.py tests/test_episode_spec.py
git commit -m "feat(episodes): episode spec loader and validator"
```

---

### Task 2: Brief + decision log từ spec

**Files:**
- Create: `episodes/brief.py`
- Test: `tests/episodes/__init__.py` (rỗng), `tests/episodes/test_brief.py`

**Interfaces:**
- Consumes: `EpisodeSpec`, `Step` từ Task 1.
- Produces:
  - `PLAYBOOK = "ai-agent-shorts"`, `RENDER_RUNTIME = "remotion"`, `COMPOSITION_MODE = "templated"`
  - `brief_from_spec(spec) -> dict` — validate được bằng `schemas.artifacts.validate_artifact("brief", ...)`
  - `channel_decisions(spec) -> dict` — validate được với `"decision_log"`

- [ ] **Step 1: Viết test fail**

```python
# tests/episodes/test_brief.py
from __future__ import annotations

from episodes.brief import brief_from_spec, channel_decisions
from episodes.spec import EpisodeSpec, Step
from schemas.artifacts import validate_artifact

SPEC = EpisodeSpec(
    slug="doc-mail", title="Đọc mail", hook="Hook", voice="Ngọc Linh", target_seconds=60,
    steps=(Step(1, "terminal", "Tóm tắt mail", "Gõ một câu.", 8),
           Step(2, "chat", "Hỏi lại", "Hỏi thêm.", 6, url="https://claude.ai/new")),
    cta="Theo dõi.",
)


def test_brief_is_schema_valid_and_carries_channel_locks():
    brief = brief_from_spec(SPEC)
    validate_artifact("brief", brief)
    assert brief["target_platform"] == "tiktok"
    assert brief["target_duration_seconds"] == 60
    assert brief["key_points"] == ["Gõ một câu.", "Hỏi thêm."]
    meta = brief["metadata"]
    assert meta["production_mode"] == "real_capture"
    assert meta["render_runtime"] == "remotion"
    assert meta["composition_mode"] == "templated"
    assert meta["aspect_ratio"] == "9:16"
    assert meta["voice"] == "Ngọc Linh"
    assert [s["surface"] for s in meta["steps"]] == ["terminal", "chat"]


def test_channel_decisions_are_schema_valid_and_cover_the_three_locks():
    log = channel_decisions(SPEC)
    validate_artifact("decision_log", log)
    cats = {d["category"] for d in log["decisions"]}
    assert {"render_runtime_selection", "composition_mode", "playbook_selection"} <= cats
    runtime = next(d for d in log["decisions"] if d["category"] == "render_runtime_selection")
    assert {o["option_id"] for o in runtime["options_considered"]} == {"remotion", "hyperframes", "ffmpeg"}
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `python -m pytest tests/episodes/test_brief.py -v`
Expected: FAIL `No module named 'episodes.brief'`

- [ ] **Step 3: Implement**

```python
# episodes/brief.py
"""Derive the `idea` stage artifacts from an episode spec.

The brief is a pure transformation of the spec, so the agent never re-asks
what the episode is about. The three channel-wide locks (runtime, mode,
playbook) are logged once here with every considered option, per AGENT_GUIDE.
"""
from __future__ import annotations

from dataclasses import asdict

from episodes.spec import EpisodeSpec

PLAYBOOK = "ai-agent-shorts"
RENDER_RUNTIME = "remotion"
COMPOSITION_MODE = "templated"
TONE = "trẻ, thân thiện, nhanh, nói với người xem như bạn bè"


def brief_from_spec(spec: EpisodeSpec) -> dict:
    return {
        "version": "1.0",
        "title": spec.title,
        "hook": spec.hook,
        "key_points": [s.narration for s in spec.steps],
        "core_message": spec.title,
        "cta": spec.cta,
        "tone": TONE,
        "style": PLAYBOOK,
        "target_audience": "người đi làm muốn giao việc lặp lại cho AI agent",
        "target_platform": "tiktok",
        "target_duration_seconds": spec.target_seconds,
        "metadata": {
            "production_mode": "real_capture",
            "render_runtime": RENDER_RUNTIME,
            "composition_mode": COMPOSITION_MODE,
            "aspect_ratio": "9:16",
            "voice": spec.voice,
            "episode_spec": str(spec.path) if spec.path else None,
            "review_capture": spec.review_capture,
            "approval_policy": spec.approval_policy,
            "steps": [asdict(s) for s in spec.steps],
        },
    }


def _opt(option_id: str, label: str, score: float, reason: str, rejected: str | None = None) -> dict:
    o = {"option_id": option_id, "label": label, "score": score, "reason": reason}
    if rejected:
        o["rejected_because"] = rejected
    return o


def channel_decisions(spec: EpisodeSpec) -> dict:
    return {
        "version": "1.0",
        "project_id": spec.slug,
        "decisions": [
            {
                "decision_id": "d-001",
                "stage": "idea",
                "category": "render_runtime_selection",
                "subject": "Composition runtime for the channel",
                "options_considered": [
                    _opt("remotion", "Remotion", 0.9, "word-level captions and zoom-crop already exist"),
                    _opt("hyperframes", "HyperFrames", 0.5, "available on this machine",
                         "adds nothing for a captions-over-capture format"),
                    _opt("ffmpeg", "FFmpeg only", 0.2, "always available",
                         "no captions, no cards, no zoom"),
                ],
                "selected": "remotion",
                "reason": "Shorts = captions + zoom over real capture; Remotion has both stock",
                "user_visible": True,
                "user_approved": True,
            },
            {
                "decision_id": "d-002",
                "stage": "idea",
                "category": "composition_mode",
                "subject": "Authoring mode for the channel",
                "options_considered": [
                    _opt("templated", "Templated", 0.9, "3 episodes/week must look alike"),
                    _opt("atelier", "Atelier", 0.3, "bespoke look", "too costly per episode"),
                ],
                "selected": "templated",
                "reason": "channel consistency over per-episode novelty",
                "user_visible": True,
                "user_approved": True,
            },
            {
                "decision_id": "d-003",
                "stage": "idea",
                "category": "playbook_selection",
                "subject": "Style playbook for the channel",
                "options_considered": [
                    _opt(PLAYBOOK, "AI-agent Shorts", 0.9, "vertical, big captions, dark terminal-friendly"),
                    _opt("clean-professional", "Clean Professional", 0.4, "stock playbook",
                         "light palette fights dark terminal footage"),
                ],
                "selected": PLAYBOOK,
                "reason": "one playbook shared by every episode",
                "user_visible": True,
                "user_approved": True,
            },
        ],
    }
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `python -m pytest tests/episodes/test_brief.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add episodes/brief.py tests/episodes/__init__.py tests/episodes/test_brief.py
git commit -m "feat(episodes): derive brief and channel decision log from spec"
```

---

### Task 3: Playbook `ai-agent-shorts`

**Files:**
- Create: `styles/ai-agent-shorts.yaml`
- Test: `tests/styles/test_ai_agent_shorts_playbook.py`

**Interfaces:**
- Produces: playbook name `ai-agent-shorts` load được qua `styles.playbook_loader.load_playbook`.

- [ ] **Step 1: Viết test fail**

```python
# tests/styles/test_ai_agent_shorts_playbook.py
from styles.playbook_loader import list_playbooks, load_playbook, validate_playbook


def test_ai_agent_shorts_playbook_loads_and_validates():
    assert "ai-agent-shorts" in list_playbooks()
    pb = load_playbook("ai-agent-shorts")
    validate_playbook(pb)
    assert pb["identity"]["category"] == "screen-demo"
    assert pb["motion"]["pacing_rules"]["text_card_hold_seconds"] == 3
    assert pb["audio"]["music_volume"] <= 0.1
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `python -m pytest tests/styles/test_ai_agent_shorts_playbook.py -v`
Expected: FAIL (`"ai-agent-shorts" in list_playbooks()` is False)

- [ ] **Step 3: Viết playbook**

```yaml
# styles/ai-agent-shorts.yaml
identity:
  name: "AI-agent Shorts"
  category: screen-demo
  mood: nhanh, gần gũi, thực dụng
  pace: fast
  best_for: "Short 45-90s dọc, quay màn hình agent đang làm việc, phụ đề to, một mẹo mỗi tập"

visual_language:
  color_palette:
    primary: ["#22D3EE", "#0E7490"]
    accent: ["#FACC15", "#F97316"]
    background: "#0B1220"
    text: "#F8FAFC"
    muted: "#94A3B8"
  composition: dọc 9:16, footage chiếm 2/3 trên, phụ đề ở 1/3 dưới, không che dòng lệnh đang gõ
  texture: phẳng, tối, không grain

typography:
  headings:
    font: "Be Vietnam Pro"
    weight: 800
    tracking: "-0.01em"
  body:
    font: "Be Vietnam Pro"
    weight: 600
    line_height: 1.3
  code:
    font: "Cascadia Mono"
    weight: 400
  scale_system: "major_third"
  weight_matrix:
    title: 800
    heading: 800
    body: 600
    caption: 700

motion:
  transitions: [cut, fade]
  animation_style: "cắt thẳng, chỉ fade ở hook card và CTA card"
  pacing_rules:
    min_scene_hold_seconds: 2
    max_scene_hold_seconds: 12
    text_card_hold_seconds: 3
    stat_card_hold_seconds: 3
    transition_duration_seconds: 0.25
  entrance: "phụ đề pop-in theo từ (word-level), scale 0.9 -> 1.0"
  exit: "cut"

audio:
  voice_style: "trẻ, tự nhiên, nói nhanh vừa phải, không đọc như văn bản"
  music_mood: "lo-fi nhẹ, không lời, không có drop"
  music_volume: 0.06
  sfx_style: "không dùng"
  ducking_threshold_db: -6

asset_generation:
  image_prompt_prefix: "flat dark UI illustration, cyan accent, "
  image_negative_prompt: "photorealistic, light background, clutter"
  consistency_anchors:
    - "Nền tối #0B1220 cho mọi card"
    - "Cyan #22D3EE là màu nhấn duy nhất, vàng #FACC15 chỉ cho từ khoá trong phụ đề"
    - "Phụ đề luôn ở 1/3 dưới, tối đa 2 dòng, 5 từ mỗi dòng"

overlays:
  code_block:
    bg: "#0B1220"
    text: "#F8FAFC"
    highlight: "#FACC15"

quality_rules:
  - "Chữ trong footage terminal phải đọc được trên điện thoại sau khi upscale 675x1200 -> 1080x1920"
  - "Hook card đúng 3 giây, CTA card đúng 3 giây"
  - "Phụ đề không che dòng lệnh hoặc câu trả lời đang hiện"
  - "Không có đoạn im lặng quá 2 giây trên màn hình"
  - "Minimum contrast ratio 4.5:1 for all text"
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `python -m pytest tests/styles/test_ai_agent_shorts_playbook.py -v`
Expected: PASS. Nếu `validate_playbook` báo thiếu field, đọc `schemas/styles/playbook.schema.json` và bổ sung đúng field đó, không bỏ test.

- [ ] **Step 5: Commit**

```bash
git add styles/ai-agent-shorts.yaml tests/styles/test_ai_agent_shorts_playbook.py
git commit -m "feat(styles): ai-agent-shorts playbook"
```

---

### Task 4: Windows Terminal window helper

**Files:**
- Create: `episodes/terminal_window.py`
- Test: `tests/episodes/test_terminal_window.py`

**Interfaces:**
- Consumes: `EpisodeSpec`, `Step`.
- Produces:
  - `WINDOW_W, WINDOW_H = 675, 1200`; `PROFILE_NAME = "Episode"`
  - `fragment_path() -> Path` (`%LOCALAPPDATA%/Microsoft/Windows Terminal/Fragments/OpenMontage/episode.json`)
  - `ensure_fragment() -> Path` — ghi fragment nếu chưa có/khác
  - `actor_command(step, spec) -> list[str]` — lệnh chạy Claude Code diễn viên
  - `launch_command(step, spec, title) -> list[str]` — argv cho `wt.exe`
  - `open_terminal(step, spec, title, *, timeout_s=15) -> int` (hwnd), `place_window(hwnd) -> dict` (`{"x","y","width","height"}`), `close_window(hwnd)`

- [ ] **Step 1: Viết test fail**

```python
# tests/episodes/test_terminal_window.py
from __future__ import annotations

import json

from episodes import terminal_window as tw
from episodes.spec import EpisodeSpec, Step

SPEC = EpisodeSpec(
    slug="ep", title="t", hook="h", voice="v", target_seconds=60,
    steps=(Step(1, "terminal", "Tóm tắt mail", "n", 8),), cta="c",
    allowed_tools=("Bash(git *)", "Read"), actor_cwd="D:/demo-repo",
)


def test_fragment_declares_the_episode_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    path = tw.ensure_fragment()
    data = json.loads(path.read_text(encoding="utf-8"))
    profile = data["profiles"][0]
    assert profile["name"] == tw.PROFILE_NAME
    assert profile["font"]["size"] == 14
    assert path.parent.name == "OpenMontage"
    assert tw.ensure_fragment() == path  # idempotent


def test_actor_command_passes_prompt_and_permissions():
    cmd = tw.actor_command(SPEC.steps[0], SPEC)
    assert cmd[:2] == ["claude", "Tóm tắt mail"]
    assert cmd[cmd.index("--permission-mode") + 1] == "acceptEdits"
    assert "--dangerously-skip-permissions" not in cmd
    i = cmd.index("--allowedTools")
    assert cmd[i + 1:i + 3] == ["Bash(git *)", "Read"]


def test_launch_command_uses_the_profile_title_and_cwd():
    argv = tw.launch_command(SPEC.steps[0], SPEC, "EPISODE 1")
    assert argv[0] == "wt.exe"
    assert argv[argv.index("--profile") + 1] == tw.PROFILE_NAME
    assert argv[argv.index("--title") + 1] == "EPISODE 1"
    assert argv[argv.index("-d") + 1] == "D:/demo-repo"
    assert argv[argv.index("--") + 1] == "claude"
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `python -m pytest tests/episodes/test_terminal_window.py -v`
Expected: FAIL `No module named 'episodes.terminal_window'`

- [ ] **Step 3: Implement**

```python
# episodes/terminal_window.py
"""Open a Windows Terminal window sized for portrait capture and run the actor.

The actor is a *separate* Claude Code process (`claude "<prompt>"`), so the
session producing the video never records itself. Window geometry is fixed so
`screen_recorder` can capture exactly that region.

ponytail: 675x1200 because the machine's display is 1920x1200; compose upscales
to 1080x1920. Upgrade path: a portrait monitor, then record 1080x1920 directly.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import os
import subprocess
import time
from pathlib import Path

from episodes.spec import EpisodeSpec, Step

WINDOW_W, WINDOW_H = 675, 1200
PROFILE_NAME = "Episode"
_WM_CLOSE = 0x0010
_FRAGMENT = {
    "profiles": [
        {
            "name": PROFILE_NAME,
            "commandline": "cmd.exe",
            "font": {"face": "Cascadia Mono", "size": 14},
            "padding": "12",
            "scrollbarState": "hidden",
            "colorScheme": "One Half Dark",
        }
    ]
}


class TerminalError(RuntimeError):
    pass


def fragment_path() -> Path:
    return (Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Windows Terminal"
            / "Fragments" / "OpenMontage" / "episode.json")


def ensure_fragment() -> Path:
    """Windows Terminal reads fragments at startup; a new fragment needs one restart of wt."""
    path = fragment_path()
    text = json.dumps(_FRAGMENT, indent=2)
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return path


def actor_command(step: Step, spec: EpisodeSpec) -> list[str]:
    cmd = ["claude", step.action, "--permission-mode", "acceptEdits"]
    if spec.allowed_tools:
        cmd += ["--allowedTools", *spec.allowed_tools]
    return cmd


def launch_command(step: Step, spec: EpisodeSpec, title: str) -> list[str]:
    argv = ["wt.exe", "-w", "episode", "new-tab", "--profile", PROFILE_NAME, "--title", title]
    if spec.actor_cwd:
        argv += ["-d", spec.actor_cwd]
    return argv + ["--", *actor_command(step, spec)]


def _user32():
    u = ctypes.windll.user32
    u.SetProcessDPIAware()
    return u


def open_terminal(step: Step, spec: EpisodeSpec, title: str, *, timeout_s: float = 15) -> int:
    ensure_fragment()
    subprocess.Popen(launch_command(step, spec, title))
    u = _user32()
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        hwnd = u.FindWindowW(None, title)
        if hwnd:
            return hwnd
        time.sleep(0.25)
    raise TerminalError(f"Windows Terminal window titled {title!r} did not appear in {timeout_s}s")


def place_window(hwnd: int) -> dict:
    u = _user32()
    u.MoveWindow(hwnd, 0, 0, WINDOW_W, WINDOW_H, True)
    u.SetForegroundWindow(hwnd)
    rect = ctypes.wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(rect))
    return {"x": rect.left, "y": rect.top, "width": rect.right - rect.left, "height": rect.bottom - rect.top}


def close_window(hwnd: int) -> None:
    _user32().PostMessageW(hwnd, _WM_CLOSE, 0, 0)
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `python -m pytest tests/episodes/test_terminal_window.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add episodes/terminal_window.py tests/episodes/test_terminal_window.py
git commit -m "feat(episodes): Windows Terminal actor window helper"
```

---

### Task 5: Chat surface (claude.ai / chatgpt.com)

**Files:**
- Create: `episodes/chat_surface.py`
- Test: `tests/episodes/test_chat_surface.py`

**Interfaces:**
- Produces:
  - `CHAT_SITES: dict[str, dict]` keyed by host, values `{"input": css, "stop": css}`
  - `class ChatSurfaceError(RuntimeError)`
  - `site_for(url) -> dict` (raise `ChatSurfaceError` for unknown host)
  - `run_chat_step(page, url, prompt, hold_seconds, *, settle_ms=1500) -> None` — page là Playwright `Page` hoặc fake có `locator(css)` trả object với `.click()`, `.wait_for(state=, timeout=)`; `keyboard.type/press`; `wait_for_timeout(ms)`

- [ ] **Step 1: Viết test fail**

```python
# tests/episodes/test_chat_surface.py
from __future__ import annotations

import pytest

from episodes.chat_surface import ChatSurfaceError, run_chat_step, site_for


class FakeLocator:
    def __init__(self, log, css):
        self.log, self.css = log, css

    def click(self):
        self.log.append(("click", self.css))

    def wait_for(self, state, timeout):
        self.log.append(("wait", self.css, state))


class FakeKeyboard:
    def __init__(self, log):
        self.log = log

    def type(self, text):
        self.log.append(("type", text))

    def press(self, key):
        self.log.append(("press", key))


class FakePage:
    def __init__(self):
        self.log = []
        self.keyboard = FakeKeyboard(self.log)

    def locator(self, css):
        return FakeLocator(self.log, css)

    def wait_for_timeout(self, ms):
        self.log.append(("sleep", ms))


def test_site_for_known_hosts_and_rejects_unknown():
    assert "input" in site_for("https://claude.ai/new")
    assert "stop" in site_for("https://chatgpt.com/")
    with pytest.raises(ChatSurfaceError, match="chatgpt.com"):
        site_for("https://example.com")


def test_run_chat_step_types_sends_and_waits_for_streaming_to_finish():
    page = FakePage()
    run_chat_step(page, "https://claude.ai/new", "Xin chào", hold_seconds=6, settle_ms=100)
    stop = site_for("https://claude.ai/new")["stop"]
    assert ("type", "Xin chào") in page.log
    assert ("press", "Enter") in page.log
    waits = [e for e in page.log if e[0] == "wait" and e[1] == stop]
    assert [w[2] for w in waits] == ["visible", "hidden"]
    assert page.log[-1] == ("sleep", 100)
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `python -m pytest tests/episodes/test_chat_surface.py -v`
Expected: FAIL `No module named 'episodes.chat_surface'`

- [ ] **Step 3: Implement**

```python
# episodes/chat_surface.py
"""Drive a logged-in chat site (claude.ai / chatgpt.com) inside a recorded Playwright page.

ponytail: selectors are a constant table. When a site changes its DOM, edit here;
move to a YAML only if a third site shows up.
"""
from __future__ import annotations

from urllib.parse import urlparse

CHAT_SITES = {
    "claude.ai": {"input": "div[contenteditable='true']", "stop": "button[aria-label='Stop response']"},
    "chatgpt.com": {"input": "#prompt-textarea", "stop": "button[data-testid='stop-button']"},
}
_START_TIMEOUT_MS = 20_000
_EXTRA_STREAM_MS = 60_000


class ChatSurfaceError(RuntimeError):
    pass


def site_for(url: str) -> dict:
    host = urlparse(url).hostname or ""
    for known, sel in CHAT_SITES.items():
        if host == known or host.endswith("." + known):
            return sel
    raise ChatSurfaceError(f"no selectors for {host!r}; known: {', '.join(CHAT_SITES)}")


def run_chat_step(page, url: str, prompt: str, hold_seconds: int, *, settle_ms: int = 1500) -> None:
    sel = site_for(url)
    page.locator(sel["input"]).click()
    page.keyboard.type(prompt)
    page.keyboard.press("Enter")
    stop = page.locator(sel["stop"])
    stop.wait_for(state="visible", timeout=_START_TIMEOUT_MS)
    stop.wait_for(state="hidden", timeout=hold_seconds * 1000 + _EXTRA_STREAM_MS)
    page.wait_for_timeout(settle_ms)
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `python -m pytest tests/episodes/test_chat_surface.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add episodes/chat_surface.py tests/episodes/test_chat_surface.py
git commit -m "feat(episodes): chat surface driver for claude.ai and chatgpt.com"
```

---

### Task 6: Capture driver tool `episode_capture`

**Files:**
- Create: `tools/capture/episode_capture.py`
- Test: `tests/tools/test_episode_capture.py`

**Interfaces:**
- Consumes: `load_spec`, `Step` (T1); `open_terminal/place_window/close_window` (T4); `run_chat_step` (T5); `tools.capture.screen_recorder.ScreenRecorder`.
- Produces:
  - `class EpisodeCapture(BaseTool)`, `name = "episode_capture"`, `capability = "screen_capture"`, `provider = "openmontage"`
  - inputs: `{"spec_path": str, "project_dir": str, "steps": [int] (optional)}`
  - output data: `{"capture_log": <path>, "steps": [...], "check_frame": <path>}`; file `<project_dir>/artifacts/capture_log.json`
  - module functions monkeypatch được: `record_terminal(step, spec, out_path) -> None`, `record_browser(step, spec, out_path, actions_dir) -> None`, `extract_check_frame(video, png) -> None`, `load_action(actions_dir, step) -> callable`
  - `class CaptureError(RuntimeError)`
  - `PAD_SECONDS = 10`, `VIEWPORT = {"width": 1080, "height": 1920}`, `USER_DATA_DIR = REPO_ROOT / ".playwright-episode-profile"`

- [ ] **Step 1: Viết test fail**

```python
# tests/tools/test_episode_capture.py
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from tools.capture import episode_capture as ec
from tools.capture.episode_capture import CaptureError, EpisodeCapture

SPEC = {
    "slug": "ep", "title": "t", "hook": "h", "voice": "v", "target_seconds": 60, "cta": "c",
    "steps": [
        {"surface": "terminal", "action": "a", "narration": "n1", "hold": 5},
        {"surface": "browser", "url": "https://example.com", "action": "b", "narration": "n2", "hold": 5},
        {"surface": "chat", "url": "https://claude.ai/new", "action": "c", "narration": "n3", "hold": 5},
    ],
}


@pytest.fixture
def project(tmp_path, monkeypatch):
    spec_path = tmp_path / "ep.yaml"
    spec_path.write_text(yaml.safe_dump(SPEC), encoding="utf-8")
    project_dir = tmp_path / "projects" / "ep"
    calls = []

    def fake_terminal(step, spec, out_path):
        calls.append(("terminal", step.index))
        Path(out_path).write_bytes(b"mp4")

    def fake_browser(step, spec, out_path, actions_dir):
        calls.append((step.surface, step.index))
        Path(out_path).write_bytes(b"mp4")

    def fake_frame(video, png):
        Path(png).write_bytes(b"png")

    monkeypatch.setattr(ec, "record_terminal", fake_terminal)
    monkeypatch.setattr(ec, "record_browser", fake_browser)
    monkeypatch.setattr(ec, "extract_check_frame", fake_frame)
    return spec_path, project_dir, calls


def test_records_every_step_and_writes_capture_log(project):
    spec_path, project_dir, calls = project
    result = EpisodeCapture().execute({"spec_path": str(spec_path), "project_dir": str(project_dir)})
    assert result.success, result.error
    assert calls == [("terminal", 1), ("browser", 2), ("chat", 3)]
    log = json.loads((project_dir / "artifacts" / "capture_log.json").read_text(encoding="utf-8"))
    assert log["slug"] == "ep"
    assert [s["file"] for s in log["steps"]] == [
        "assets/video/step_1.mp4", "assets/video/step_2.mp4", "assets/video/step_3.mp4"]
    assert all({"started_at", "ended_at", "duration_seconds", "surface", "narration"} <= set(s) for s in log["steps"])
    assert (project_dir / "assets" / "images" / "capture_check.png").exists()
    assert result.data["check_frame"].endswith("capture_check.png")


def test_steps_filter_rerecords_only_that_step_and_keeps_the_rest_of_the_log(project):
    spec_path, project_dir, calls = project
    EpisodeCapture().execute({"spec_path": str(spec_path), "project_dir": str(project_dir)})
    calls.clear()
    result = EpisodeCapture().execute({"spec_path": str(spec_path), "project_dir": str(project_dir), "steps": [2]})
    assert result.success
    assert calls == [("browser", 2)]
    log = json.loads((project_dir / "artifacts" / "capture_log.json").read_text(encoding="utf-8"))
    assert [s["index"] for s in log["steps"]] == [1, 2, 3]


def test_failure_keeps_earlier_steps_and_names_the_broken_one(project, monkeypatch):
    spec_path, project_dir, calls = project

    def broken(step, spec, out_path, actions_dir):
        raise CaptureError("page never loaded")

    monkeypatch.setattr(ec, "record_browser", broken)
    result = EpisodeCapture().execute({"spec_path": str(spec_path), "project_dir": str(project_dir)})
    assert not result.success
    assert "step 2" in result.error and "page never loaded" in result.error
    assert (project_dir / "assets" / "video" / "step_1.mp4").exists()
    log = json.loads((project_dir / "artifacts" / "capture_log.json").read_text(encoding="utf-8"))
    assert [s["index"] for s in log["steps"]] == [1]


def test_missing_browser_action_script_is_a_clear_blocker(tmp_path):
    from episodes.spec import Step
    step = Step(2, "browser", "b", "n", 5, url="https://example.com")
    with pytest.raises(CaptureError, match=r"step_2\.py"):
        ec.load_action(tmp_path, step)
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `python -m pytest tests/tools/test_episode_capture.py -v`
Expected: FAIL `No module named 'tools.capture.episode_capture'`

- [ ] **Step 3: Implement**

```python
# tools/capture/episode_capture.py
"""Record every step of an episode spec as a portrait MP4 and write capture_log.json.

Three surfaces, one output shape:
  terminal  -> Windows Terminal actor window + ffmpeg gdigrab (screen_recorder)
  browser   -> Playwright persistent context, viewport 1080x1920, recordVideo
  chat      -> same as browser, driven by episodes.chat_surface

Browser steps need an action script the agent writes at capture time:
`<project_dir>/capture/step_<n>.py` defining `run(page)`. Chat steps don't.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from episodes.chat_surface import run_chat_step
from episodes.spec import EpisodeSpec, Step, load_spec
from episodes.terminal_window import close_window, open_terminal, place_window
from lib.paths import REPO_ROOT
from tools.base_tool import (
    BaseTool, Determinism, ExecutionMode, ResourceProfile, ToolResult, ToolRuntime, ToolStability, ToolTier,
)

PAD_SECONDS = 10
VIEWPORT = {"width": 1080, "height": 1920}
USER_DATA_DIR = REPO_ROOT / ".playwright-episode-profile"
LOG_NAME = "capture_log.json"


class CaptureError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- surface recorders (module-level so tests can monkeypatch) -------------

def record_terminal(step: Step, spec: EpisodeSpec, out_path: Path) -> None:
    from tools.capture.screen_recorder import ScreenRecorder  # noqa: PLC0415

    hwnd = open_terminal(step, spec, f"EPISODE {step.index}")
    try:
        region = place_window(hwnd)
        result = ScreenRecorder().execute({
            "output_path": str(out_path),
            "duration_seconds": step.hold + PAD_SECONDS,
            "fps": 30,
            "capture_audio": False,
            "region": region,
        })
    finally:
        close_window(hwnd)
    if not result.success:
        raise CaptureError(result.error or "screen_recorder failed")


def load_action(actions_dir: Path, step: Step):
    script = Path(actions_dir) / f"step_{step.index}.py"
    if not script.exists():
        raise CaptureError(
            f"browser step {step.index} needs {script} defining run(page); "
            f"write it from the step's action: {step.action!r}"
        )
    mod_spec = importlib.util.spec_from_file_location(f"episode_action_{step.index}", script)
    module = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(module)
    if not hasattr(module, "run"):
        raise CaptureError(f"{script} must define run(page)")
    return module.run


def _webm_to_mp4(webm: Path, mp4: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(webm), "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-an", str(mp4)],
        check=True, capture_output=True,
    )


def record_browser(step: Step, spec: EpisodeSpec, out_path: Path, actions_dir: Path) -> None:
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    action = None if step.surface == "chat" else load_action(actions_dir, step)
    video_dir = out_path.parent / "_pw"
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(USER_DATA_DIR), headless=False, viewport=VIEWPORT,
            record_video_dir=str(video_dir), record_video_size=VIEWPORT,
        )
        page = ctx.new_page()
        try:
            page.goto(step.url, wait_until="domcontentloaded")
            if action is None:
                run_chat_step(page, step.url, step.action, step.hold)
            else:
                action(page)
            page.wait_for_timeout(1000)
        except Exception as exc:  # many playwright error classes; name the step, keep the cause
            raise CaptureError(str(exc)) from exc
        finally:
            video = page.video
            ctx.close()
    _webm_to_mp4(Path(video.path()), out_path)
    shutil.rmtree(video_dir, ignore_errors=True)


def extract_check_frame(video: Path, png: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-i", str(video), "-frames:v", "1", str(png)], check=True, capture_output=True)


def _probe_seconds(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=20,
        ).stdout.strip()
        return round(float(out), 2)
    except (ValueError, subprocess.SubprocessError, FileNotFoundError):
        return 0.0  # fake files in tests / probe unavailable; the edit stage re-probes anyway


# ---- the tool ---------------------------------------------------------------

class EpisodeCapture(BaseTool):
    name = "episode_capture"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "screen_capture"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL
    dependencies = ["binary:ffmpeg", "python:playwright"]
    install_instructions = (
        "pip install playwright && python -m playwright install chromium; Windows Terminal (wt.exe) on PATH"
    )
    capabilities = ["record_episode_steps"]
    best_for = ["AI-agent Shorts: record each spec step of a real agent session as portrait footage"]
    not_good_for = ["synthetic terminal demos (use TerminalScene)", "landscape captures"]
    input_schema = {
        "type": "object",
        "required": ["spec_path", "project_dir"],
        "properties": {
            "spec_path": {"type": "string"},
            "project_dir": {"type": "string", "description": "projects/<slug>"},
            "steps": {"type": "array", "items": {"type": "integer"},
                      "description": "1-based indices to (re)record; default all"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {"capture_log": {"type": "string"}, "check_frame": {"type": "string"}},
    }
    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=1024, disk_mb=1000, network_required=False)
    side_effects = ["opens windows", "creates_file"]

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        spec = load_spec(Path(inputs["spec_path"]))
        project_dir = Path(inputs["project_dir"])
        video_dir = project_dir / "assets" / "video"
        actions_dir = project_dir / "capture"
        log_path = project_dir / "artifacts" / LOG_NAME
        video_dir.mkdir(parents=True, exist_ok=True)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        wanted = set(inputs.get("steps") or [s.index for s in spec.steps])
        previous = json.loads(log_path.read_text(encoding="utf-8"))["steps"] if log_path.exists() else []
        entries = {e["index"]: e for e in previous if e["index"] not in wanted}

        for step in spec.steps:
            if step.index not in wanted:
                continue
            out = video_dir / f"step_{step.index}.mp4"
            started = _now()
            try:
                if step.surface == "terminal":
                    record_terminal(step, spec, out)
                else:
                    record_browser(step, spec, out, actions_dir)
            except CaptureError as exc:
                self._write_log(log_path, spec, entries)
                return ToolResult(success=False, error=f"step {step.index} ({step.surface}) failed: {exc}")
            entries[step.index] = {
                "index": step.index, "surface": step.surface, "narration": step.narration,
                "file": f"assets/video/step_{step.index}.mp4",
                "started_at": started, "ended_at": _now(),
                "duration_seconds": _probe_seconds(out),
            }

        check = project_dir / "assets" / "images" / "capture_check.png"
        check.parent.mkdir(parents=True, exist_ok=True)
        first = video_dir / "step_1.mp4"
        if first.exists():
            extract_check_frame(first, check)
        self._write_log(log_path, spec, entries)
        ordered = [entries[i] for i in sorted(entries)]
        return ToolResult(
            success=True,
            data={"capture_log": str(log_path), "steps": ordered, "check_frame": str(check)},
            artifacts=[str(log_path), *(str(video_dir / f"step_{i}.mp4") for i in sorted(entries))],
        )

    @staticmethod
    def _write_log(log_path: Path, spec: EpisodeSpec, entries: dict[int, dict]) -> None:
        payload = {"slug": spec.slug, "steps": [entries[i] for i in sorted(entries)]}
        log_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `python -m pytest tests/tools/test_episode_capture.py -v`
Expected: 4 PASS

- [ ] **Step 5: Xác nhận registry nhận tool và không làm hỏng discover**

Run: `python -c "from tools.tool_registry import registry; registry.discover(); t=registry.get('episode_capture'); print(t.name, t.get_status())"`
Expected: in `episode_capture available` (hoặc `unavailable` nếu thiếu playwright — không được crash).

- [ ] **Step 6: Commit**

```bash
git add tools/capture/episode_capture.py tests/tools/test_episode_capture.py
git commit -m "feat(capture): episode_capture tool records spec steps as portrait footage"
```

---

### Task 7: CLI `python -m episodes`

**Files:**
- Create: `episodes/__main__.py`
- Test: `tests/episodes/test_cli.py`

**Interfaces:**
- Consumes: `load_spec`, `planned_seconds`, `SpecError` (T1); `brief_from_spec`, `channel_decisions`, `PLAYBOOK` (T2); `EpisodeCapture` (T6); `lib.checkpoint.init_project/write_checkpoint`; `lib.paths.PROJECTS_DIR`.
- Produces:
  - `main(argv) -> int` với subcommands `validate <spec>`, `capture <spec> [--step N ...]`, `run <spec>`
  - `open_board(slug)` (monkeypatch được)
  - `run` = validate → `init_project(slug, title=..., pipeline_type="screen-demo", style_playbook=PLAYBOOK)` → `open_board` (lỗi bỏ qua) → capture → ghi checkpoint `idea` với `brief` + `decision_log` (`awaiting_human` nếu `approval_policy == "guided"`, `completed` + `human_approved=True` nếu `auto`) → in "NEXT: read skills/pipelines/screen-demo/episode-runner.md"

- [ ] **Step 1: Đọc `lib/checkpoint.py:194` (`_checkpoint_path`) để biết file checkpoint `idea` nằm ở đâu.** Dùng đường dẫn đó trong helper `_idea_checkpoint` của test bên dưới thay cho hàm tạm.

- [ ] **Step 2: Viết test fail**

```python
# tests/episodes/test_cli.py
from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
import yaml

SPEC = {
    "slug": "ep", "title": "Tập mẫu", "hook": "h", "voice": "v", "target_seconds": 60, "cta": "c",
    "steps": [{"surface": "chat", "url": "https://claude.ai/new", "action": "a", "narration": "n", "hold": 5}],
}


def _idea_checkpoint(project: Path) -> dict:
    # Replace with the exact path from lib.checkpoint._checkpoint_path (Step 1). Do not glob.
    from lib.checkpoint import _checkpoint_path
    return json.loads(_checkpoint_path(project.parent, project.name, "idea").read_text(encoding="utf-8"))


@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_PROJECTS_DIR", str(tmp_path / "projects"))
    import lib.paths, lib.checkpoint, episodes.__main__ as m  # noqa: E401
    importlib.reload(lib.paths)
    importlib.reload(lib.checkpoint)
    importlib.reload(m)
    spec_path = tmp_path / "ep.yaml"
    spec_path.write_text(yaml.safe_dump(SPEC), encoding="utf-8")

    def fake_capture(self, inputs):
        from tools.base_tool import ToolResult
        pd = Path(inputs["project_dir"])
        (pd / "artifacts").mkdir(parents=True, exist_ok=True)
        (pd / "artifacts" / "capture_log.json").write_text('{"slug":"ep","steps":[]}', encoding="utf-8")
        return ToolResult(success=True, data={"capture_log": str(pd / "artifacts" / "capture_log.json")})

    monkeypatch.setattr(m.EpisodeCapture, "execute", fake_capture)
    monkeypatch.setattr(m, "open_board", lambda slug: None)
    return m, spec_path, tmp_path / "projects"


def test_validate_reports_ok_and_errors(cli, capsys, tmp_path):
    m, spec_path, _ = cli
    assert m.main(["validate", str(spec_path)]) == 0
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({**SPEC, "target_seconds": 5}), encoding="utf-8")
    assert m.main(["validate", str(bad)]) == 2
    assert "target_seconds" in capsys.readouterr().out


def test_run_inits_project_captures_and_writes_idea_checkpoint_awaiting_human(cli):
    m, spec_path, projects = cli
    assert m.main(["run", str(spec_path)]) == 0
    project = projects / "ep"
    assert (project / "project.json").exists()
    assert (project / "artifacts" / "capture_log.json").exists()
    ckpt = _idea_checkpoint(project)
    assert ckpt["status"] == "awaiting_human"
    assert ckpt["artifacts"]["brief"]["title"] == "Tập mẫu"


def test_run_with_auto_policy_completes_idea(cli):
    m, spec_path, projects = cli
    spec_path.write_text(yaml.safe_dump({**SPEC, "approval_policy": "auto"}), encoding="utf-8")
    assert m.main(["run", str(spec_path)]) == 0
    ckpt = _idea_checkpoint(projects / "ep")
    assert ckpt["status"] == "completed"
    assert ckpt["human_approved"] is True


def test_run_stops_with_blocker_when_capture_fails(cli, capsys, monkeypatch):
    m, spec_path, _ = cli

    def failing(self, inputs):
        from tools.base_tool import ToolResult
        return ToolResult(success=False, error="step 1 (chat) failed: page never loaded")

    monkeypatch.setattr(m.EpisodeCapture, "execute", failing)
    assert m.main(["run", str(spec_path)]) == 1
    assert "BLOCKER" in capsys.readouterr().out
```

- [ ] **Step 3: Chạy test, xác nhận fail**

Run: `python -m pytest tests/episodes/test_cli.py -v`
Expected: FAIL `No module named 'episodes.__main__'`

- [ ] **Step 4: Implement**

```python
# episodes/__main__.py
"""CLI: validate / capture / run an episode spec.

`run` stops after the idea checkpoint on purpose. Stages script..compose are
agent-driven (director skills), not Python — see AGENT_GUIDE "Python = tools +
persistence" and skills/pipelines/screen-demo/episode-runner.md.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from episodes.brief import PLAYBOOK, brief_from_spec, channel_decisions
from episodes.spec import SpecError, load_spec, planned_seconds
from lib.checkpoint import init_project, write_checkpoint
from lib.paths import PROJECTS_DIR
from tools.capture.episode_capture import EpisodeCapture

PIPELINE = "screen-demo"
RUNNER_SKILL = "skills/pipelines/screen-demo/episode-runner.md"


def open_board(slug: str) -> None:
    """Backlot is an observer, never a blocker."""
    try:
        subprocess.Popen([sys.executable, "-m", "backlot", "open", slug])
    except Exception as exc:  # noqa: BLE001
        print(f"backlot open failed (continuing): {exc}")


def cmd_validate(spec_path: Path) -> int:
    try:
        spec = load_spec(spec_path)
    except SpecError as exc:
        print(f"INVALID: {exc}")
        return 2
    print(f"OK {spec.slug}: {len(spec.steps)} steps, planned {planned_seconds(spec)}s / target {spec.target_seconds}s")
    return 0


def cmd_capture(spec_path: Path, steps: list[int] | None) -> int:
    spec = load_spec(spec_path)
    project_dir = PROJECTS_DIR / spec.slug
    inputs = {"spec_path": str(spec_path), "project_dir": str(project_dir)}
    if steps:
        inputs["steps"] = steps
    result = EpisodeCapture().execute(inputs)
    if not result.success:
        print(f"BLOCKER: {result.error}")
        print("Fix the cause, then re-run: python -m episodes capture <spec> --step <n>")
        return 1
    print(f"captured -> {result.data['capture_log']}")
    return 0


def cmd_run(spec_path: Path) -> int:
    if cmd_validate(spec_path) != 0:
        return 2
    spec = load_spec(spec_path)
    init_project(spec.slug, title=spec.title, pipeline_type=PIPELINE, style_playbook=PLAYBOOK)
    open_board(spec.slug)
    rc = cmd_capture(spec_path, None)
    if rc != 0:
        return rc
    auto = spec.approval_policy == "auto"
    write_checkpoint(
        PROJECTS_DIR, spec.slug, "idea",
        "completed" if auto else "awaiting_human",
        {"brief": brief_from_spec(spec), "decision_log": channel_decisions(spec)},
        pipeline_type=PIPELINE, style_playbook=PLAYBOOK,
        human_approval_required=True, human_approved=auto,
        metadata={"capture_log": "artifacts/capture_log.json", "check_frame": "assets/images/capture_check.png"},
    )
    print(f"idea checkpoint written ({'completed' if auto else 'awaiting_human'}).")
    print(f"NEXT: read {RUNNER_SKILL} and drive script -> compose.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m episodes")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("validate", "capture", "run"):
        p = sub.add_parser(name)
        p.add_argument("spec", type=Path)
        if name == "capture":
            p.add_argument("--step", type=int, action="append", dest="steps")
    args = parser.parse_args(argv)
    if args.cmd == "validate":
        return cmd_validate(args.spec)
    if args.cmd == "capture":
        return cmd_capture(args.spec, args.steps)
    return cmd_run(args.spec)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Chạy test, xác nhận pass**

Run: `python -m pytest tests/episodes/test_cli.py -v`
Expected: 4 PASS. Nếu `write_checkpoint` từ chối `awaiting_human` + `decision_log` hay yêu cầu thêm field, đọc lỗi từ `lib/checkpoint.py` và sửa lời gọi trong `__main__.py`, không sửa `checkpoint.py`.

- [ ] **Step 6: Commit**

```bash
git add episodes/__main__.py tests/episodes/test_cli.py
git commit -m "feat(episodes): CLI validate/capture/run writes idea checkpoint"
```

---

### Task 8: Runner skill + README + tập mẫu smoke + AGENT_GUIDE entry

**Files:**
- Create: `skills/pipelines/screen-demo/episode-runner.md`
- Create: `episodes/smoke.yaml`
- Create: `episodes/README.md`
- Modify: `AGENT_GUIDE.md` — thêm mục "Episode Entry Point" ngay sau mục "Reference Video Entry Point".
- Test: `tests/episodes/test_smoke_spec.py`

- [ ] **Step 1: Viết test fail**

```python
# tests/episodes/test_smoke_spec.py
from pathlib import Path

from episodes.spec import load_spec


def test_smoke_spec_is_valid_and_single_browser_step():
    spec = load_spec(Path("episodes/smoke.yaml"))
    assert spec.slug == "smoke"
    assert [s.surface for s in spec.steps] == ["browser"]
    assert spec.steps[0].url.startswith("https://example.com")
    assert spec.approval_policy == "auto"


def test_runner_skill_exists_and_names_the_key_rules():
    text = Path("skills/pipelines/screen-demo/episode-runner.md").read_text(encoding="utf-8")
    for needle in ("capture_log.json", "675x1200", "1080x1920", "silence_cutter", "tts_selector", "approval_policy"):
        assert needle in text, needle


def test_agent_guide_routes_episode_requests():
    text = Path("AGENT_GUIDE.md").read_text(encoding="utf-8")
    assert "episodes/README.md" in text
    assert "episode-runner.md" in text
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `python -m pytest tests/episodes/test_smoke_spec.py -v`
Expected: FAIL (file không tồn tại)

- [ ] **Step 3: Viết smoke spec**

```yaml
# episodes/smoke.yaml
slug: smoke
title: "Smoke: một bước trình duyệt"
hook: "Kiểm tra pipeline chạy được."
voice: "Ngọc Linh"
target_seconds: 30
review_capture: false
approval_policy: auto
steps:
  - surface: browser
    url: "https://example.com"
    action: "Cuộn nhẹ xuống rồi lên"
    narration: "Đây là bước kiểm tra, trang tĩnh, không đăng nhập."
    hold: 6
cta: "Nếu thấy clip này, pipeline sống."
```

- [ ] **Step 4: Viết README**

```markdown
# Episodes — kênh AI-agent Shorts

Mỗi tập là một file YAML ở đây. Chạy:

    python -m episodes validate episodes/<slug>.yaml
    python -m episodes run      episodes/<slug>.yaml            # init + board + capture + idea checkpoint
    python -m episodes capture  episodes/<slug>.yaml --step 2   # quay lại một bước

Trước khi `run` một tập có bước `browser`: viết `projects/<slug>/capture/step_<n>.py`
với `def run(page): ...` (Playwright sync API) dịch từ `action` của bước đó.
Bước `chat` và `terminal` không cần script.

Một lần duy nhất trên máy:
1. `python -m playwright install chromium` (đã có).
2. Đăng nhập Gmail / claude.ai / ChatGPT vào profile của kênh:
   `python -c "from playwright.sync_api import sync_playwright as s; p=s().start(); c=p.chromium.launch_persistent_context('.playwright-episode-profile', headless=False); input('login xong thì Enter'); c.close()"`
3. Windows Terminal: sau lần chạy đầu (fragment `Episode` được ghi), đóng và mở lại wt một lần.
4. Repo diễn viên (`actor_cwd` trong spec): mở `claude` trong đó một lần và chấp nhận "trust folder".

Sau `run`, agent đọc `skills/pipelines/screen-demo/episode-runner.md` và chạy tiếp
script → compose. Video ra ở `projects/<slug>/renders/final.mp4`.
```

- [ ] **Step 5: Viết runner skill**

```markdown
# Episode Runner — AI-agent Shorts trên pipeline screen-demo

Đọc skill này ngay sau `python -m episodes run` thành công. Bạn đang ở checkpoint
`idea` (`awaiting_human` nếu `approval_policy: guided`, `completed` nếu `auto`).
Từ đây chạy đúng các director skill của screen-demo; skill này chỉ nói phần khác biệt.

## Đầu vào có sẵn trong `projects/<slug>/`
- `artifacts/capture_log.json` — mỗi step: `file`, `surface`, `narration`, `duration_seconds`.
- `assets/video/step_<n>.mp4` — browser/chat: 1080x1920. terminal: **675x1200**.
- `assets/images/capture_check.png` — khung hình đầu để duyệt lộ dữ liệu.
- Brief trong checkpoint idea: `metadata.steps`, `metadata.voice`; ba lock runtime/mode/playbook đã nằm trong decision_log.

## Gate idea (guided)
Trình cho người dùng: `capture_check.png`, danh sách step + thời lượng thật, câu hỏi
"quay lại bước nào không?". Quay lại: `python -m episodes capture <spec> --step n`.
Khi được duyệt: ghi lại checkpoint idea `completed`, `human_approved=True`. KẾT THÚC LƯỢT trước khi làm tiếp.

## script
Không transcribe. Với mỗi step n: xem `step_n.mp4` (`frame_sampler` 3-4 khung), so với
`narration` trong spec, **sửa câu cho khớp output thật** (tên file, con số, câu trả lời của agent).
Sections:
- `hook` 0-3s, text = brief.hook
- mỗi step: start = mốc cộng dồn, end = start + hold (không phải `duration_seconds`; phần thừa cắt ở edit)
- `cta` 3s cuối
Gate script bắt buộc (manifest). Trình các câu đã sửa.

## scene_plan
Một scene `screen_recording` mỗi step + `text_card` cho hook và cta.
- terminal: zoom vào 40% dưới của khung (nơi output mới nhất), scale 1.6 để 675→1080.
- browser/chat: không zoom, không crop.

## assets
- Narration: `tts_selector` với `provider: vieneu`, `voice` = brief.metadata.voice, một file mỗi section.
  Nghe thử câu hook trước; gate assets bắt buộc.
- Phụ đề: `subtitle_gen` word-level từ narration, style theo playbook `ai-agent-shorts`.
- Nhạc: `music_library/` trước; trống thì `pixabay_music` tìm "lofi calm no vocals", tải một lần
  vào `music_library/ai-agent-shorts-bed.mp3`, volume theo playbook 0.06.

## edit
- `silence_cutter` mode `speed_up`, `min_silence_duration: 2.0`, `silence_speed_factor: 3.0` trên từng step
  sau khi ghép audio TTS (im lặng = agent đang nghĩ). Step câm hoàn toàn: mode `mark` rồi cắt theo capture_log.
- Cắt đệm cuối mỗi step: out = min(hold, duration thật).
- Tổng sau edit ≤ `target_seconds`. Vượt: báo con số, đề xuất cắt bước nào, **không tự cắt**.

## compose
- `render_runtime: remotion`, `composition_mode: templated`, `compose_target: {"width": 1080, "height": 1920, "fit": "cover"}`.
- Kiểm tra chữ terminal đọc được sau upscale trên một khung 1080x1920; không đạt → blocker, đề xuất tăng font profile Episode.
- Output `renders/final.mp4`, ffprobe phải ra 1080x1920.

## approval_policy: auto
Bỏ gate idea và script. Gate assets vẫn giữ theo manifest.
```

- [ ] **Step 6: Sửa AGENT_GUIDE.md** — chèn sau mục "Reference Video Entry Point" (trước "Rule Zero"):

```markdown
## Episode Entry Point (AI-agent Shorts channel)

When the user says "chạy tập <slug>", "làm tập mới cho kênh", or points at `episodes/*.yaml`:
read `episodes/README.md`, then `skills/pipelines/screen-demo/episode-runner.md`. Capture is
`python -m episodes run`; everything after the idea checkpoint is the normal screen-demo pipeline.
```

- [ ] **Step 7: Chạy test, xác nhận pass**

Run: `python -m pytest tests/episodes/test_smoke_spec.py -v`
Expected: 3 PASS

- [ ] **Step 8: Commit**

```bash
git add episodes/smoke.yaml episodes/README.md skills/pipelines/screen-demo/episode-runner.md AGENT_GUIDE.md tests/episodes/test_smoke_spec.py
git commit -m "docs(episodes): runner skill, README, smoke spec, AGENT_GUIDE entry point"
```

---

### Task 9: Smoke thật (live, ngoài pytest, không commit)

- [ ] **Step 1: Chạy cả bộ test mới**

Run: `python -m pytest tests/test_episode_spec.py tests/episodes tests/tools/test_episode_capture.py tests/styles/test_ai_agent_shorts_playbook.py -q`
Expected: all PASS

- [ ] **Step 2: Viết action script cho bước browser của smoke**

```python
# projects/smoke/capture/step_1.py   (tạo thư mục projects/smoke/capture/ trước)
def run(page):
    page.wait_for_selector("h1")
    page.mouse.wheel(0, 300)
    page.wait_for_timeout(1500)
    page.mouse.wheel(0, -300)
    page.wait_for_timeout(1500)
```

- [ ] **Step 3: Chạy smoke**

Run: `python -m episodes run episodes/smoke.yaml`
Expected: `captured -> projects/smoke/artifacts/capture_log.json` và `idea checkpoint written (completed)`.
Kiểm: `ffprobe -v error -show_entries stream=width,height -of csv=p=0 projects/smoke/assets/video/step_1.mp4` → `1080,1920`.

- [ ] **Step 4: Smoke terminal (cần wt + claude)**

Tạo `episodes/smoke-terminal.yaml` tạm (không commit) với một step `terminal`,
`action: "In ra 5 dòng chào bằng tiếng Việt rồi dừng"`, `hold: 8`, `actor_cwd` trỏ tới một thư mục trống đã trust.
Run: `python -m episodes capture episodes/smoke-terminal.yaml`
Expected: `step_1.mp4` gần 675x1200 (viền cửa sổ có thể lệch vài px; nếu lệch, ghi con số thật vào runner skill).

- [ ] **Step 5: Đi tiếp bằng agent**

Đọc `skills/pipelines/screen-demo/episode-runner.md`, chạy script → compose cho `smoke`.
Expected: `projects/smoke/renders/final.mp4` 1080x1920, có hook card, phụ đề, CTA card.

---

## Self-review

**Spec coverage**
- §1 spec YAML + validate → T1. `review_capture`, `approval_policy` → T1 + T7.
- §2 capture driver: terminal (T4 + T6), browser (T6), chat (T5 + T6), ảnh kiểm tra (T6; lấy từ khung đầu step 1 sau khi quay thay vì chụp trước — đơn giản hoá có chủ ý, gate vẫn xảy ra trước hậu kỳ), blocker không tự đổi sang TerminalScene (T6 trả error, T7 in BLOCKER).
- §3 hậu kỳ: không stage mới; khác biệt từng stage nằm trong runner skill (T8); playbook (T3); ba lock ghi decision_log (T2 + T7).
- §4 lệnh chạy (T7), gate (T7 + T8), lỗi giữ step đã ghi + quay lại một bước (T6 `steps` + T7 `--step`), vượt thời lượng không tự cắt (T8), chi phí 0 (T6 `estimate_cost`).
- §5 kiểm thử: `test_episode_spec.py` (T1), `test_episode_capture.py` (T6), smoke end-to-end (T8 spec + T9).
- Khác spec một chỗ, có chủ ý: spec nói `python -m episodes run` "giao cho pipeline screen-demo chạy từ idea tới compose". Python dừng ở checkpoint idea vì AGENT_GUIDE cấm orchestration trong Python; phần còn lại agent chạy theo runner skill. Với người dùng kết quả như nhau.

**Placeholder scan**: không có TBD/TODO. T7 Step 1 yêu cầu đọc `_checkpoint_path` thật trước khi viết test; helper trong test đã gọi đúng hàm đó.

**Type consistency**: `Step(index, surface, action, narration, hold, url)` thống nhất T1/T2/T4/T6. `record_terminal(step, spec, out_path)`, `record_browser(step, spec, out_path, actions_dir)`, `load_action(actions_dir, step)` khớp giữa implementation và test T6. `EpisodeCapture.execute` inputs `spec_path/project_dir/steps` khớp T7. `open_board(slug)` khớp test T7.
