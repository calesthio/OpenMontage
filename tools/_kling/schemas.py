"""Lightweight schema constants for Kling official providers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


DEFAULT_API_BASE_URL = "https://api-singapore.klingai.com"


class KlingProtocol(str, Enum):
    CLASSIC = "classic"
    TURBO = "turbo"


CLASSIC_PENDING_STATUSES = {"submitted", "processing"}
CLASSIC_SUCCESS_STATUS = "succeed"
CLASSIC_FAILURE_STATUS = "failed"
CLASSIC_STATUSES = [
    "submitted",
    "processing",
    "succeed",
    "failed",
]

TURBO_PENDING_STATUSES = {"submitted", "processing"}
TURBO_SUCCESS_STATUS = "succeeded"
TURBO_FAILURE_STATUS = "failed"
TURBO_STATUSES = [
    "submitted",
    "processing",
    "succeeded",
    "failed",
]

VIDEO_MODELS = [
    "kling-v1",
    "kling-v1-5",
    "kling-v1-6",
    "kling-v2-master",
    "kling-v2-1",
    "kling-v2-1-master",
    "kling-v2-5-turbo",
    "kling-v2-6",
    "kling-v3",
    "kling-video-o1",
    "kling-v3-omni",
]
CLASSIC_VIDEO_MODELS = [
    "kling-v1",
    "kling-v1-5",
    "kling-v1-6",
    "kling-v2-master",
    "kling-v2-1",
    "kling-v2-1-master",
    "kling-v2-5-turbo",
    "kling-v2-6",
    "kling-v3",
]
OMNI_VIDEO_MODELS = ["kling-video-o1", "kling-v3-omni"]

IMAGE_MODELS = [
    "kling-v1",
    "kling-v1-5",
    "kling-v2",
    "kling-v2-new",
    "kling-v2-1",
    "kling-v3",
    "kling-image-o1",
    "kling-v3-omni",
]
IMAGE_GENERATION_MODELS = [
    "kling-v1",
    "kling-v1-5",
    "kling-v2",
    "kling-v2-new",
    "kling-v2-1",
    "kling-v3",
]
OMNI_IMAGE_MODELS = ["kling-image-o1", "kling-v3-omni"]

VIDEO_DURATIONS = [str(value) for value in range(3, 16)]
VIDEO_ASPECT_RATIOS = ["16:9", "9:16", "1:1"]
VIDEO_RESOLUTIONS = ["720p", "1080p"]
VIDEO_MODES = ["std", "pro", "4k"]
SOUND_VALUES = ["on", "off"]

IMAGE_RESOLUTIONS = ["1k", "2k", "4k"]
IMAGE_ASPECT_RATIOS = ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3", "21:9", "auto"]
IMAGE_REFERENCE_TYPES = ["subject", "face"]
IMAGE_RESULT_TYPES = ["single", "series"]

RESULT_PATHS = {
    "classic_video": "data.task_result.videos[]",
    "classic_image": "data.task_result.images[]",
    "classic_audio": "data.task_result.audios[]",
    "turbo": "data[0].outputs[]",
}

TTS_LANGUAGES = ["zh", "en"]
TTS_SPEED_MIN = 0.5
TTS_SPEED_MAX = 2.0

AVATAR_MODES = ["std", "pro"]
LIP_SYNC_OPERATIONS = ["identify_face", "advanced_lip_sync", "full_lip_sync"]


@dataclass
class ClassicTaskResult:
    task_id: str
    status: str
    outputs: list[dict[str, Any]]


@dataclass
class TurboTaskResult:
    task_id: str
    status: str
    outputs: list[dict[str, Any]]
