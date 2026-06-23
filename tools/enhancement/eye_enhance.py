"""Eye enhancement tool using MediaPipe Face Mesh + OpenCV.

Targets the eye region for talking-head footage:
- Under-eye dark circle brightening
- Eye/iris sharpening and brightening
- Subtle under-eye smoothing

Uses MediaPipe Face Mesh (468 landmarks) to precisely locate eye regions,
then applies targeted OpenCV adjustments. Processes video frame-by-frame.

Falls back to FFmpeg region-based filters if MediaPipe is not installed.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolStatus,
    ToolTier,
)

# MediaPipe Face Mesh landmark indices for eye regions.
# These form polygons around each eye area.
# Lower eyelid landmarks (used to define the under-eye region):
LEFT_LOWER_EYELID = [33, 7, 163, 144, 145, 153, 154, 155, 133]
RIGHT_LOWER_EYELID = [263, 249, 390, 373, 374, 380, 381, 382, 362]

# Full eye contour (used for iris/eye brightening):
LEFT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
RIGHT_EYE = [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466]

# Iris landmarks (available when refine_landmarks=True, indices 468-477):
LEFT_IRIS = [468, 469, 470, 471, 472]
RIGHT_IRIS = [473, 474, 475, 476, 477]


class EyeEnhance(BaseTool):
    name = "eye_enhance"
    version = "0.1.0"
    tier = ToolTier.ENHANCE
    capability = "enhancement"
    provider = "mediapipe"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg"]
    install_instructions = (
        "For best results install MediaPipe and OpenCV:\n"
        "pip install mediapipe opencv-python numpy\n\n"
        "Without MediaPipe, falls back to FFmpeg eye-region filter (less precise)."
    )
    agent_skills = ["ffmpeg"]

    capabilities = [
        "under_eye_brightening",
        "dark_circle_removal",
        "eye_sharpening",
        "eye_brightening",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {"type": "string"},
            "output_path": {"type": "string"},
            "operations": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["dark_circles", "brighten_eyes", "sharpen_eyes"],
                },
                "default": ["dark_circles", "brighten_eyes"],
                "description": "Which enhancements to apply",
            },
            "dark_circle_intensity": {
                "type": "number",
                "default": 0.4,
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Strength of dark circle removal (0=none, 1=max)",
            },
            "eye_brighten_intensity": {
                "type": "number",
                "default": 0.3,
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Strength of eye brightening (0=none, 1=max)",
            },
            "sharpen_intensity": {
                "type": "number",
                "default": 0.3,
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Strength of eye sharpening (0=none, 1=max)",
            },
            "codec": {"type": "string", "default": "libx264"},
            "crf": {"type": "integer", "default": 18},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=2048, vram_mb=0, disk_mb=4000, network_required=False
    )
    idempotency_key_fields = [
        "input_path", "operations", "dark_circle_intensity",
        "eye_brighten_intensity", "sharpen_intensity",
    ]
    side_effects = ["writes enhanced video to output_path"]
    user_visible_verification = [
        "Compare eyes in before/after — enhancement should be subtle and natural",
        "Check for artifacts around eye region (halos, color shifts)",
        "Verify enhancement doesn't make eyes look unnatural",
    ]

    def _has_mediapipe(self) -> bool:
        try:
            import mediapipe  # noqa: F401
            return True
        except ImportError:
            return False

    def _has_opencv(self) -> bool:
        try:
            import cv2  # noqa: F401
            import numpy  # noqa: F401
            return True
        except ImportError:
            return False

    def get_status(self) -> ToolStatus:
        if self._has_mediapipe() and self._has_opencv():
            return ToolStatus.AVAILABLE
        if self._has_opencv():
            return ToolStatus.DEGRADED
        return ToolStatus.UNAVAILABLE

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")

        operations = inputs.get("operations", ["dark_circles", "brighten_eyes"])  # noqa: F841
        output_path = Path(
            inputs.get("output_path", str(input_path.with_stem(f"{input_path.stem}_eye_enhanced")))
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        start = time.time()

        if self._has_mediapipe() and self._has_opencv():
            result = self._enhance_mediapipe(input_path, output_path, inputs)
        elif self._has_opencv():
            result = self._enhance_opencv_only(input_path, output_path, inputs)
        else:
            result = self._enhance_ffmpeg_fallback(input_path, output_path, inputs)

        if not result.success:
            return result

        elapsed = time.time() - start
        result.duration_seconds = round(elapsed, 2)
        return result

    def _enhance_mediapipe(
        self, input_path: Path, output_path: Path, inputs: dict[str, Any]
    ) -> ToolResult:
        """Full MediaPipe Face Mesh + OpenCV pipeline for precise eye enhancement."""
        import cv2
        import mediapipe as mp

        operations = inputs.get("operations", ["dark_circles", "brighten_eyes"])
        dark_intensity = inputs.get("dark_circle_intensity", 0.4)
        brighten_intensity = inputs.get("eye_brighten_intensity", 0.3)
        sharpen_intensity = inputs.get("sharpen_intensity", 0.3)
        codec_fourcc = inputs.get("codec", "libx264")  # noqa: F841
        crf = inputs.get("crf", 18)

        mp_face_mesh = mp.solutions.face_mesh

        cap = cv2.VideoCapture(str(input_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))  # noqa: F841

        # Write to temp file, then mux audio via FFmpeg
        temp_video = output_path.parent / f".{output_path.stem}_temp.mp4"

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(temp_video), fourcc, fps, (width, height))

        frames_processed = 0
        frames_enhanced = 0

        with mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,  # Enables iris landmarks (468-477)
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        ) as face_mesh:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frames_processed += 1
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(rgb)

                if results.multi_face_landmarks:
                    landmarks = results.multi_face_landmarks[0]
                    frame = self._apply_eye_enhancements(
                        frame, landmarks, width, height,
                        operations, dark_intensity, brighten_intensity, sharpen_intensity,
                    )
                    frames_enhanced += 1

                writer.write(frame)

        cap.release()
        writer.release()

        # Mux original audio back with FFmpeg
        cmd = [
            "ffmpeg", "-y",
            "-i", str(temp_video),
            "-i", str(input_path),
            "-c:v", "libx264", "-crf", str(crf), "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            "-map", "0:v:0", "-map", "1:a:0?",
            "-shortest",
            str(output_path),
        ]

        try:
            self.run_command(cmd, timeout=600)
        except Exception as e:
            return ToolResult(success=False, error=f"Audio mux failed: {e}")
        finally:
            if temp_video.exists():
                temp_video.unlink()

        return ToolResult(
            success=True,
            data={
                "input": str(input_path),
                "output": str(output_path),
                "method": "mediapipe_face_mesh",
                "frames_processed": frames_processed,
                "frames_enhanced": frames_enhanced,
                "operations": operations,
            },
            artifacts=[str(output_path)],
        )

    def _apply_eye_enhancements(
        self,
        frame,
        landmarks,
        width: int,
        height: int,
        operations: list[str],
        dark_intensity: float,
        brighten_intensity: float,
        sharpen_intensity: float,
    ):
        """Apply eye enhancements to a single frame using detected landmarks."""
        import numpy as np

        result = frame.copy()

        # Convert landmarks to pixel coordinates
        def lm_to_px(indices):
            points = []
            for idx in indices:
                if idx < len(landmarks.landmark):
                    lm = landmarks.landmark[idx]
                    points.append((int(lm.x * width), int(lm.y * height)))
            return np.array(points, dtype=np.int32)

        for side in ["left", "right"]:
            lower_lid = lm_to_px(LEFT_LOWER_EYELID if side == "left" else RIGHT_LOWER_EYELID)
            eye_contour = lm_to_px(LEFT_EYE if side == "left" else RIGHT_EYE)

            if len(lower_lid) < 3 or len(eye_contour) < 3:
                continue

            # Under-eye region: expand lower eyelid downward
            if "dark_circles" in operations:
                result = self._remove_dark_circles(
                    result, lower_lid, width, height, dark_intensity
                )

            if "brighten_eyes" in operations:
                iris = lm_to_px(LEFT_IRIS if side == "left" else RIGHT_IRIS)
                result = self._brighten_eyes(
                    result, eye_contour, iris, brighten_intensity
                )

            if "sharpen_eyes" in operations:
                result = self._sharpen_eyes(
                    result, eye_contour, sharpen_intensity
                )

        return result

    def _remove_dark_circles(
        self, frame, lower_lid_points, width: int, height: int, intensity: float
    ):
        """Brighten the under-eye area to reduce dark circles."""
        import cv2
        import numpy as np

        # Create under-eye region by shifting lower eyelid points downward
        under_eye = lower_lid_points.copy()
        # Shift down by ~15% of face height (approximate eye-to-cheek distance)
        shift = max(5, int(height * 0.025))
        under_eye_shifted = under_eye.copy()
        under_eye_shifted[:, 1] += shift

        # Create polygon from lower lid + shifted points (forms a band)
        polygon = np.vstack([lower_lid_points, under_eye_shifted[::-1]])

        # Create soft mask
        mask = np.zeros(frame.shape[:2], dtype=np.float32)
        cv2.fillPoly(mask, [polygon], 1.0)
        # Gaussian blur for soft edges
        blur_size = max(15, int(width * 0.02)) | 1  # Ensure odd
        mask = cv2.GaussianBlur(mask, (blur_size, blur_size), 0)

        # Apply brightening in LAB color space (perceptually uniform)
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB).astype(np.float32)
        # Boost L channel (lightness) in the masked region
        boost = 25 * intensity  # 0-25 range
        lab[:, :, 0] += mask * boost
        lab[:, :, 0] = np.clip(lab[:, :, 0], 0, 255)

        # Also reduce saturation slightly (dark circles are often purplish)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] -= mask * (20 * intensity)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)

        # Blend: use LAB for brightness, HSV for desaturation
        brightened = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)
        desaturated = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

        # Combine: weighted blend of both adjustments
        mask_3ch = np.stack([mask] * 3, axis=-1)
        combined = frame.astype(np.float32)
        combined = combined * (1 - mask_3ch * intensity) + \
                   (brightened.astype(np.float32) * 0.6 + desaturated.astype(np.float32) * 0.4) * (mask_3ch * intensity)

        return np.clip(combined, 0, 255).astype(np.uint8)

    def _brighten_eyes(self, frame, eye_contour, iris_points, intensity: float):
        """Subtly brighten the eye/sclera area."""
        import cv2
        import numpy as np

        if len(eye_contour) < 3:
            return frame

        # Create mask from eye contour
        mask = np.zeros(frame.shape[:2], dtype=np.float32)
        cv2.fillPoly(mask, [eye_contour], 1.0)
        blur_size = max(5, int(frame.shape[1] * 0.005)) | 1
        mask = cv2.GaussianBlur(mask, (blur_size, blur_size), 0)

        # Brighten in LAB space
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB).astype(np.float32)
        boost = 15 * intensity
        lab[:, :, 0] += mask * boost
        lab[:, :, 0] = np.clip(lab[:, :, 0], 0, 255)

        brightened = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)

        mask_3ch = np.stack([mask] * 3, axis=-1)
        result = frame.astype(np.float32) * (1 - mask_3ch * intensity) + \
                 brightened.astype(np.float32) * (mask_3ch * intensity)

        return np.clip(result, 0, 255).astype(np.uint8)

    def _sharpen_eyes(self, frame, eye_contour, intensity: float):
        """Sharpen the eye region for more detail."""
        import cv2
        import numpy as np

        if len(eye_contour) < 3:
            return frame

        # Create mask
        mask = np.zeros(frame.shape[:2], dtype=np.float32)
        cv2.fillPoly(mask, [eye_contour], 1.0)
        # Expand slightly for natural blend
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.dilate(mask, kernel, iterations=1)
        blur_size = max(5, int(frame.shape[1] * 0.005)) | 1
        mask = cv2.GaussianBlur(mask, (blur_size, blur_size), 0)

        # Unsharp mask for sharpening
        blur = cv2.GaussianBlur(frame, (0, 0), 3)
        sharpened = cv2.addWeighted(frame, 1.0 + intensity, blur, -intensity, 0)

        mask_3ch = np.stack([mask] * 3, axis=-1)
        result = frame.astype(np.float32) * (1 - mask_3ch) + \
                 sharpened.astype(np.float32) * mask_3ch

        return np.clip(result, 0, 255).astype(np.uint8)

    def _enhance_opencv_only(
        self, input_path: Path, output_path: Path, inputs: dict[str, Any]
    ) -> ToolResult:
        """Fallback: OpenCV Haar cascade for face detection + generic eye region enhancement."""
        import cv2
        import numpy as np

        operations = inputs.get("operations", ["dark_circles", "brighten_eyes"])
        dark_intensity = inputs.get("dark_circle_intensity", 0.4)
        crf = inputs.get("crf", 18)

        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        eye_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_eye.xml"
        )

        cap = cv2.VideoCapture(str(input_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        temp_video = output_path.parent / f".{output_path.stem}_temp.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(temp_video), fourcc, fps, (width, height))

        frames_processed = 0
        frames_enhanced = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frames_processed += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))

            if len(faces) > 0:
                # Use largest face
                areas = [w * h for (_, _, w, h) in faces]
                fi = areas.index(max(areas))
                fx, fy, fw, fh = faces[fi]

                # Detect eyes within face region
                face_roi_gray = gray[fy:fy + fh, fx:fx + fw]
                eyes = eye_cascade.detectMultiScale(face_roi_gray, 1.1, 5, minSize=(20, 20))

                for (ex, ey, ew, eh) in eyes:
                    # Under-eye region: below the detected eye box
                    under_y = fy + ey + eh
                    under_h = max(5, int(eh * 0.4))
                    under_x = fx + ex
                    under_w = ew

                    if under_y + under_h <= height and under_x + under_w <= width:
                        if "dark_circles" in operations:
                            # Create soft mask for under-eye
                            mask = np.zeros((height, width), dtype=np.float32)
                            cv2.ellipse(
                                mask,
                                (under_x + under_w // 2, under_y + under_h // 2),
                                (under_w // 2, under_h // 2),
                                0, 0, 360, 1.0, -1,
                            )
                            mask = cv2.GaussianBlur(mask, (15, 15), 0)

                            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB).astype(np.float32)
                            lab[:, :, 0] += mask * (25 * dark_intensity)
                            lab[:, :, 0] = np.clip(lab[:, :, 0], 0, 255)
                            frame = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)

                frames_enhanced += 1

            writer.write(frame)

        cap.release()
        writer.release()

        # Mux audio
        cmd = [
            "ffmpeg", "-y",
            "-i", str(temp_video),
            "-i", str(input_path),
            "-c:v", "libx264", "-crf", str(crf), "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            "-map", "0:v:0", "-map", "1:a:0?",
            "-shortest",
            str(output_path),
        ]

        try:
            self.run_command(cmd, timeout=600)
        except Exception as e:
            return ToolResult(success=False, error=f"Audio mux failed: {e}")
        finally:
            if temp_video.exists():
                temp_video.unlink()

        return ToolResult(
            success=True,
            data={
                "input": str(input_path),
                "output": str(output_path),
                "method": "opencv_haar_cascade",
                "frames_processed": frames_processed,
                "frames_enhanced": frames_enhanced,
                "operations": operations,
            },
            artifacts=[str(output_path)],
        )

    def _enhance_ffmpeg_fallback(
        self, input_path: Path, output_path: Path, inputs: dict[str, Any]
    ) -> ToolResult:
        """Last resort: FFmpeg-only. Applies general face-area enhancement (not eye-specific)."""
        crf = inputs.get("crf", 18)
        intensity = inputs.get("dark_circle_intensity", 0.4)

        # General brightness + contrast lift for the whole frame
        # Not eye-specific but better than nothing
        brightness = 0.02 * intensity
        contrast = 1.0 + (0.05 * intensity)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", f"eq=brightness={brightness}:contrast={contrast}",
            "-c:v", "libx264", "-crf", str(crf), "-preset", "fast",
            "-c:a", "copy",
            str(output_path),
        ]

        try:
            self.run_command(cmd, timeout=600)
        except Exception as e:
            return ToolResult(success=False, error=f"FFmpeg fallback failed: {e}")

        return ToolResult(
            success=True,
            data={
                "input": str(input_path),
                "output": str(output_path),
                "method": "ffmpeg_global_brightness",
                "operations": ["global_brightness_contrast"],
                "note": "Install mediapipe + opencv-python for precise eye-region enhancement",
            },
            artifacts=[str(output_path)],
        )

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        """Eye enhancement is roughly 0.5x-1x realtime depending on resolution."""
        return 90.0
