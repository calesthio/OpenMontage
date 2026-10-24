"""JianYing draft generator tool for OpenMontage.

Bridges OpenMontage and Windows Content Studio with JianYing Pro.
Generates complete JianYing draft projects (video clips, voiceovers, BGM,
sound effects, styled subtitles, and transitions) and registers them into
root_meta_info.json so they appear immediately in JianYing's Recent Projects list.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolTier,
)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg"}


def get_default_jianying_drafts_path() -> Path:
    """Find default JianYing drafts directory on Windows."""
    env_path = os.environ.get("JIANYING_DRAFTS_PATH") or os.environ.get("JIANYING_DRAFT_PATH")
    if env_path:
        p = Path(env_path).resolve()
        if p.is_dir():
            return p

    app_data = os.environ.get("LOCALAPPDATA")
    if not app_data:
        app_data = str(Path.home() / "AppData" / "Local")

    default_path = Path(app_data) / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"
    return default_path


def get_default_jianying_exe() -> Optional[Path]:
    """Find default JianYing executable on Windows."""
    env_exe = os.environ.get("JIANYING_EXE")
    if env_exe and Path(env_exe).is_file():
        return Path(env_exe).resolve()

    app_data = os.environ.get("LOCALAPPDATA")
    if not app_data:
        app_data = str(Path.home() / "AppData" / "Local")

    candidates = [
        Path(app_data) / "JianyingPro" / "Apps" / "JianyingPro.exe",
        Path("C:/Program Files/JianyingPro/JianyingPro.exe"),
        Path("C:/Program Files (x86)/JianyingPro/JianyingPro.exe"),
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def register_draft_in_root_meta(
    draft_dir: Path,
    draft_id: str,
    draft_name: str,
    duration_us: int = 0,
    root_meta_file: Optional[Path] = None,
) -> bool:
    """Register draft into root_meta_info.json so JianYing displays it immediately in recent projects."""
    root_dir = draft_dir.parent
    if root_meta_file is None:
        root_meta_file = root_dir / "root_meta_info.json"

    if not root_meta_file.exists():
        meta = {
            "all_draft_store": [],
            "draft_ids": 0,
            "root_path": str(root_dir).replace("\\", "/"),
        }
    else:
        try:
            with open(root_meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            return False

    now_us = int(time.time() * 1000000)
    fold_str = str(draft_dir).replace("\\", "/")
    store = meta.get("all_draft_store", [])

    store = [
        item
        for item in store
        if item.get("draft_id") != draft_id and item.get("draft_fold_path") != fold_str
    ]

    entry = {
        "cloud_draft_cover": False,
        "cloud_draft_sync": False,
        "draft_cloud_last_action_download": False,
        "draft_cloud_purchase_info": "",
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "",
        "draft_cloud_videocut_purchase_info": "",
        "draft_cover": f"{fold_str}/draft_cover.jpg",
        "draft_fold_path": fold_str,
        "draft_id": draft_id,
        "draft_is_ai_shorts": False,
        "draft_is_cloud_temp_draft": False,
        "draft_is_infinite_canvas_draft": False,
        "draft_is_invisible": False,
        "draft_is_pippit_draft": False,
        "draft_is_web_article_video": False,
        "draft_json_file": f"{fold_str}/draft_content.json",
        "draft_name": draft_name,
        "draft_new_version": "",
        "draft_root_path": str(root_dir).replace("\\", "/"),
        "draft_timeline_materials_size": 0,
        "draft_type": "",
        "draft_web_article_video_enter_from": "",
        "pippit_avatar_url": "",
        "pippit_extra_info": "",
        "pippit_id": "",
        "pippit_user_name": "",
        "streaming_edit_draft_ready": True,
        "tm_draft_cloud_completed": "",
        "tm_draft_cloud_entry_id": -1,
        "tm_draft_cloud_modified": 0,
        "tm_draft_cloud_parent_entry_id": -1,
        "tm_draft_cloud_space_id": -1,
        "tm_draft_cloud_user_id": -1,
        "tm_draft_create": now_us,
        "tm_draft_modified": now_us,
        "tm_draft_removed": 0,
        "tm_duration": duration_us,
    }

    store.insert(0, entry)
    meta["all_draft_store"] = store
    meta["draft_ids"] = len(store)

    try:
        with open(root_meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
        return True
    except Exception:
        return False


def build_jianying_draft(
    draft_name: str,
    clips: List[Union[str, Dict[str, Any]]],
    voiceover: Optional[str] = None,
    bgm: Optional[str] = None,
    bgm_volume: float = 0.25,
    srt_path: Optional[str] = None,
    sfx_list: Optional[List[Dict[str, Any]]] = None,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    draft_root: Optional[Union[str, Path]] = None,
    auto_register: bool = True,
    default_image_duration_sec: float = 3.0,
) -> Dict[str, Any]:
    try:
        import pyJianYingDraft as pj
    except ImportError:
        raise RuntimeError(
            "pyJianYingDraft is required. Install via `pip install pyjianyingdraft`."
        )

    if draft_root is None:
        target_root = get_default_jianying_drafts_path()
    else:
        target_root = Path(draft_root).resolve()

    target_root.mkdir(parents=True, exist_ok=True)
    df = pj.DraftFolder(str(target_root))
    sf = df.create_draft(draft_name, width, height, fps=fps, allow_replace=True)

    video_track = sf.append_track(pj.TrackSpec(pj.TrackType.video, name="主视频轨"))

    audio_vo_track = None
    if voiceover:
        audio_vo_track = sf.append_track(pj.TrackSpec(pj.TrackType.audio, name="主配音轨"))

    audio_bgm_track = None
    if bgm:
        audio_bgm_track = sf.append_track(pj.TrackSpec(pj.TrackType.audio, name="BGM音乐轨"))

    audio_sfx_track = None
    if sfx_list:
        audio_sfx_track = sf.append_track(pj.TrackSpec(pj.TrackType.audio, name="音效轨"))

    current_video_time_us = 0
    added_clips = []

    trans_map = {
        "dissolve": getattr(pj.TransitionType, "叠化", None),
        "crossfade": getattr(pj.TransitionType, "叠化", None),
        "fade_black": getattr(pj.TransitionType, "闪黑", None),
        "fade_white": getattr(pj.TransitionType, "闪白", None),
        "叠化": getattr(pj.TransitionType, "叠化", None),
        "闪黑": getattr(pj.TransitionType, "闪黑", None),
        "闪白": getattr(pj.TransitionType, "闪白", None),
    }

    for idx, item in enumerate(clips):
        if isinstance(item, (str, Path)):
            clip_path = str(Path(item).resolve())
            duration_sec = None
            trans_name = None
        elif isinstance(item, dict):
            clip_path = str(Path(item.get("path") or item.get("media") or "").resolve())
            duration_sec = item.get("duration") or item.get("duration_sec")
            trans_name = item.get("transition")
        else:
            continue

        if not os.path.isfile(clip_path):
            continue

        ext = Path(clip_path).suffix.lower()
        is_image = ext in IMAGE_EXTENSIONS

        v_mat = pj.VideoMaterial(clip_path)

        if is_image:
            clip_dur_sec = float(duration_sec or default_image_duration_sec)
            clip_dur_us = int(clip_dur_sec * 1000000)
            target_tr = pj.Timerange(current_video_time_us, clip_dur_us)
            v_seg = pj.VideoSegment(v_mat, target_tr)
        else:
            if duration_sec:
                clip_dur_us = int(float(duration_sec) * 1000000)
                source_tr = pj.Timerange(0, clip_dur_us)
                target_tr = pj.Timerange(current_video_time_us, clip_dur_us)
                v_seg = pj.VideoSegment(v_mat, target_tr, source_timerange=source_tr)
            else:
                clip_dur_us = v_mat.duration
                target_tr = pj.Timerange(current_video_time_us, clip_dur_us)
                v_seg = pj.VideoSegment(v_mat, target_tr)

        if trans_name and trans_name in trans_map and trans_map[trans_name]:
            try:
                v_seg.add_transition(trans_map[trans_name], duration="0.5s")
            except Exception:
                pass

        sf.add_segment(v_seg, track=video_track)
        current_video_time_us += clip_dur_us
        added_clips.append({"path": clip_path, "duration_sec": clip_dur_us / 1000000})

    vo_duration_us = 0
    if voiceover and os.path.isfile(voiceover) and audio_vo_track:
        vo_mat = pj.AudioMaterial(str(Path(voiceover).resolve()))
        vo_duration_us = vo_mat.duration
        vo_seg = pj.AudioSegment(
            vo_mat,
            pj.Timerange(0, vo_duration_us),
            volume=1.0,
        )
        sf.add_segment(vo_seg, track=audio_vo_track)

    if bgm and os.path.isfile(bgm) and audio_bgm_track:
        bgm_mat = pj.AudioMaterial(str(Path(bgm).resolve()))
        total_timeline_duration = max(current_video_time_us, vo_duration_us)
        bgm_dur = min(bgm_mat.duration, total_timeline_duration)
        if bgm_dur > 0:
            bgm_seg = pj.AudioSegment(
                bgm_mat,
                pj.Timerange(0, bgm_dur),
                volume=max(0.0, min(1.0, float(bgm_volume))),
            )
            sf.add_segment(bgm_seg, track=audio_bgm_track)

    if sfx_list and audio_sfx_track:
        for sfx in sfx_list:
            s_path = str(Path(sfx.get("path") or "").resolve())
            if not os.path.isfile(s_path):
                continue
            start_us = int(float(sfx.get("start_sec", 0.0)) * 1000000)
            vol = float(sfx.get("volume", 0.8))
            s_mat = pj.AudioMaterial(s_path)
            s_dur = s_mat.duration
            s_seg = pj.AudioSegment(
                s_mat,
                pj.Timerange(start_us, s_dur),
                volume=vol,
            )
            sf.add_segment(s_seg, track=audio_sfx_track)

    if srt_path and os.path.isfile(srt_path):
        resolved_srt = str(Path(srt_path).resolve())
        text_style = pj.TextStyle(size=8.0, bold=True, color=(1.0, 1.0, 1.0))
        clip_settings = pj.ClipSettings(transform_y=-0.78)
        sf.import_srt(
            resolved_srt,
            "字幕轨",
            text_style=text_style,
            clip_settings=clip_settings,
        )

    sf.save()

    total_project_duration_us = max(current_video_time_us, vo_duration_us)
    draft_folder = target_root / draft_name

    draft_id = str(uuid.uuid4()).upper()
    registered = False
    if auto_register:
        registered = register_draft_in_root_meta(
            draft_folder,
            draft_id=draft_id,
            draft_name=draft_name,
            duration_us=total_project_duration_us,
        )

    return {
        "success": True,
        "draft_name": draft_name,
        "draft_path": str(draft_folder),
        "total_duration_sec": total_project_duration_us / 1000000,
        "clips_count": len(added_clips),
        "has_voiceover": bool(voiceover),
        "has_bgm": bool(bgm),
        "has_subtitles": bool(srt_path and os.path.isfile(srt_path)),
        "registered_in_root_meta": registered,
        "jianying_draft_root": str(target_root),
    }


class JianYingDraftExport(BaseTool):
    """OpenMontage tool to assemble cuts directly into JianYing Pro drafts."""

    name = "jianying_draft"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "video_post"
    provider = "jianying"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["py:pyJianYingDraft"]
    agent_skills = []

    capabilities = [
        "create_draft",
        "export_timeline",
        "import_srt",
        "auto_register",
        "launch_app",
    ]

    input_schema = {
        "type": "object",
        "properties": {
            "draft_name": {
                "type": "string",
                "description": "Name of the JianYing project draft to create",
            },
            "manifest_path": {
                "type": "string",
                "description": "Path to a JSON sceneplan/timeline manifest describing the project",
            },
            "clips": {
                "type": "array",
                "items": {
                    "oneOf": [
                        {"type": "string"},
                        {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "duration": {"type": "number"},
                                "transition": {"type": "string"},
                            },
                            "required": ["path"],
                        },
                    ]
                },
                "description": "List of video/image clip paths or objects",
            },
            "voiceover": {
                "type": "string",
                "description": "Path to main narration audio file (wav/mp3)",
            },
            "bgm": {
                "type": "string",
                "description": "Path to background music audio file",
            },
            "bgm_volume": {
                "type": "number",
                "default": 0.25,
                "description": "BGM volume between 0.0 and 1.0",
            },
            "srt_path": {
                "type": "string",
                "description": "Path to subtitle SRT file",
            },
            "width": {"type": "integer", "default": 1920},
            "height": {"type": "integer", "default": 1080},
            "fps": {"type": "integer", "default": 30},
            "launch_app": {
                "type": "boolean",
                "default": False,
                "description": "Whether to launch JianYing Pro desktop app upon completion",
            },
        },
    }

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        params = dict(inputs or {})

        manifest_path = params.get("manifest_path")
        if manifest_path and os.path.isfile(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
            for k, v in manifest_data.items():
                if k not in params or params[k] is None:
                    params[k] = v

        draft_name = params.get("draft_name") or f"OM_Project_{int(time.time())}"
        clips = params.get("clips") or []
        voiceover = params.get("voiceover")
        bgm = params.get("bgm")
        bgm_volume = params.get("bgm_volume", 0.25)
        srt_path = params.get("srt_path")
        width = params.get("width", 1920)
        height = params.get("height", 1080)
        fps = params.get("fps", 30)
        launch_app = params.get("launch_app", False)

        try:
            result = build_jianying_draft(
                draft_name=draft_name,
                clips=clips,
                voiceover=voiceover,
                bgm=bgm,
                bgm_volume=bgm_volume,
                srt_path=srt_path,
                width=width,
                height=height,
                fps=fps,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to build JianYing draft: {str(e)}",
            )

        if launch_app:
            exe_path = get_default_jianying_exe()
            if exe_path and exe_path.is_file():
                try:
                    subprocess.Popen([str(exe_path)])
                    result["jianying_launched"] = True
                except Exception as ex:
                    result["jianying_launched"] = False
                    result["launch_error"] = str(ex)

        draft_path = result.get("draft_path")
        return ToolResult(
            success=True,
            data=result,
            artifacts=[draft_path] if draft_path else [],
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="OpenMontage JianYing Draft CLI")
    parser.add_argument("--name", type=str, default=None, help="Draft name")
    parser.add_argument("--manifest", type=str, default=None, help="JSON manifest file")
    parser.add_argument("--clips", nargs="*", default=[], help="Video or image clip paths")
    parser.add_argument("--voiceover", type=str, default=None, help="Narration audio path")
    parser.add_argument("--bgm", type=str, default=None, help="BGM audio path")
    parser.add_argument("--bgm-volume", type=float, default=0.25, help="BGM volume (0.0 - 1.0)")
    parser.add_argument("--srt", type=str, default=None, help="Subtitle SRT file path")
    parser.add_argument("--launch", action="store_true", help="Launch JianYing Pro app after creation")
    parser.add_argument("--json", action="store_true", help="Output JSON result")

    args = parser.parse_args()

    tool = JianYingDraftExport()
    kwargs: Dict[str, Any] = {
        "draft_name": args.name or f"OM_Cut_{int(time.time())}",
        "manifest_path": args.manifest,
        "clips": args.clips,
        "voiceover": args.voiceover,
        "bgm": args.bgm,
        "bgm_volume": args.bgm_volume,
        "srt_path": args.srt,
        "launch_app": args.launch,
    }

    res = tool.execute(kwargs)
    if args.json:
        print(json.dumps(res.__dict__, ensure_ascii=False, indent=2))
    else:
        if res.success:
            print("✅ 剪映草稿已成功生成并注册！")
            print(f"工程名称: {res.data.get('draft_name')}")
            print(f"草稿路径: {res.data.get('draft_path')}")
            print(f"片段数量: {res.data.get('clips_count')}")
            print(f"总时长: {res.data.get('total_duration_sec'):.2f} 秒")
            print(f"最近项目就绪: {'已自动注入主页' if res.data.get('registered_in_root_meta') else '未注入'}")
            print("\n👉 打开【剪映专业版】，在主页最近项目即可直接进入工程进行后期精剪与终审！")
        else:
            print(f"❌ 生成失败: {res.error}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
