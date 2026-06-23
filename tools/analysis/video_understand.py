"""Video/image understanding tool using vision-language models.

Analyzes images or video frames using CLIP, BLIP-2, or LLaVA. Supports
frame description, visual question answering, quality assessment, and
scene classification. Primary use case: visual QA for automated video review.
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}

SCENE_CATEGORIES = [
    "indoor", "outdoor", "landscape", "cityscape", "portrait",
    "action", "close-up", "aerial", "underwater", "night",
    "studio", "nature", "urban", "abstract", "text-overlay",
]


class VideoUnderstand(BaseTool):
    name = "video_understand"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "analysis"
    provider = "transformers"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = ["python:transformers", "python:torch"]
    install_instructions = (
        "pip install transformers torch  # For CLIP/BLIP-2 visual understanding"
    )
    agent_skills = ["video-understand"]

    capabilities = [
        "image_description",
        "visual_qa",
        "quality_assessment",
        "scene_classification",
        "object_detection",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {
                "type": "string",
                "description": "Path to image or video file",
            },
            "query": {
                "type": "string",
                "description": "Question to answer about the visual content (for VQA mode)",
            },
            "mode": {
                "type": "string",
                "enum": ["describe", "qa", "quality", "classify"],
                "default": "describe",
                "description": (
                    "describe: generate caption; qa: answer query about content; "
                    "quality: assess technical quality; classify: classify scene type"
                ),
            },
            "model": {
                "type": "string",
                "enum": ["clip", "blip2", "llava"],
                "default": "clip",
                "description": "Which vision-language model to use",
            },
            "frame_indices": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "For video input, which frames to analyze. "
                    "If not provided, samples key frames at even intervals."
                ),
            },
            "max_frames": {
                "type": "integer",
                "default": 5,
                "description": "Maximum number of frames to analyze from video",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "frames": {
                "type": "array",
                "description": "Per-frame analysis results",
            },
            "summary": {"type": "string"},
            "mode": {"type": "string"},
            "model": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2,
        ram_mb=4096,
        vram_mb=2048,
        disk_mb=1000,
        network_required=False,
    )

    idempotency_key_fields = ["input_path", "mode", "model", "query"]
    side_effects = []
    fallback = None
    user_visible_verification = [
        "Compare generated descriptions against actual visual content",
        "Verify quality scores match perceived image quality",
    ]

    def get_status(self) -> ToolStatus:
        """Check if transformers and torch are both importable."""
        try:
            import transformers  # noqa: F401
            import torch  # noqa: F401
            return ToolStatus.AVAILABLE
        except ImportError:
            return ToolStatus.UNAVAILABLE

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        """Estimate runtime in seconds based on mode and frame count."""
        max_frames = inputs.get("max_frames", 5)
        mode = inputs.get("mode", "describe")
        if mode == "quality":
            return max_frames * 0.5  # quality metrics are fast
        return max_frames * 5.0  # VLM inference per frame

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        mode = inputs.get("mode", "describe")
        model_name = inputs.get("model", "clip")
        query = inputs.get("query")
        frame_indices = inputs.get("frame_indices")
        max_frames = inputs.get("max_frames", 5)

        if not input_path.exists():
            return ToolResult(
                success=False,
                error=f"Input file not found: {input_path}",
            )

        suffix = input_path.suffix.lower()
        is_video = suffix in VIDEO_EXTENSIONS
        is_image = suffix in IMAGE_EXTENSIONS

        if not is_video and not is_image:
            return ToolResult(
                success=False,
                error=(
                    f"Unsupported file type: {suffix}. "
                    f"Supported: {sorted(VIDEO_EXTENSIONS | IMAGE_EXTENSIONS)}"
                ),
            )

        if mode == "qa" and not query:
            return ToolResult(
                success=False,
                error="Query is required for 'qa' mode.",
            )

        start = time.time()

        # --- Load frames ---
        try:
            frames = self._load_frames(
                input_path, is_video, frame_indices, max_frames
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to load frames: {e}")

        if not frames:
            return ToolResult(success=False, error="No frames could be extracted.")

        # --- Analyze each frame ---
        try:
            if mode == "quality":
                frame_results = self._analyze_quality(frames)
            elif mode == "describe":
                frame_results = self._analyze_describe(frames, model_name)
            elif mode == "qa":
                frame_results = self._analyze_qa(frames, model_name, query)
            elif mode == "classify":
                frame_results = self._analyze_classify(frames, model_name)
            else:
                return ToolResult(success=False, error=f"Unknown mode: {mode}")
        except ImportError as e:
            return ToolResult(
                success=False,
                error=f"Missing dependency for {model_name}: {e}",
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Analysis failed: {e}")

        elapsed = time.time() - start

        # --- Build summary ---
        summary = self._build_summary(frame_results, mode)

        return ToolResult(
            success=True,
            data={
                "frames": frame_results,
                "summary": summary,
                "mode": mode,
                "model": model_name if mode != "quality" else "metrics",
                "frame_count": len(frame_results),
            },
            duration_seconds=round(elapsed, 2),
            model=model_name if mode != "quality" else None,
        )

    # ------------------------------------------------------------------
    # Frame extraction
    # ------------------------------------------------------------------

    def _load_frames(
        self,
        input_path: Path,
        is_video: bool,
        frame_indices: list[int] | None,
        max_frames: int,
    ) -> list:
        """Load PIL Image objects from an image or video file."""
        from PIL import Image

        if not is_video:
            return [Image.open(input_path).convert("RGB")]

        return self._extract_video_frames(input_path, frame_indices, max_frames)

    def _extract_video_frames(
        self,
        video_path: Path,
        frame_indices: list[int] | None,
        max_frames: int,
    ) -> list:
        """Extract frames from a video file using ffmpeg."""
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)

            if frame_indices:
                # Extract specific frames using select filter
                frames_to_extract = frame_indices[:max_frames]
                select_expr = "+".join(
                    f"eq(n\\,{idx})" for idx in frames_to_extract
                )
                cmd = [
                    "ffmpeg", "-i", str(video_path),
                    "-vf", f"select='{select_expr}'",
                    "-vsync", "vfr",
                    str(tmp / "frame_%04d.png"),
                    "-y", "-loglevel", "error",
                ]
            else:
                # Get total frame count first
                probe_cmd = [  # noqa: F841
                    "ffmpeg", "-i", str(video_path),
                    "-map", "0:v:0", "-c", "copy", "-f", "null", "-",
                ]
                # Sample at even intervals using fps filter
                # Use a select filter that picks frames at even intervals
                cmd = [
                    "ffmpeg", "-i", str(video_path),
                    "-frames:v", str(max_frames),
                    "-vf", f"thumbnail={max_frames}",
                    str(tmp / "frame_%04d.png"),
                    "-y", "-loglevel", "error",
                ]

            subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            # Load extracted frames
            frame_files = sorted(tmp.glob("frame_*.png"))
            images = []
            for f in frame_files[:max_frames]:
                images.append(Image.open(f).convert("RGB"))

            return images

    # ------------------------------------------------------------------
    # Quality assessment (uses PIL/numpy, no VLM needed)
    # ------------------------------------------------------------------

    def _analyze_quality(self, frames: list) -> list[dict[str, Any]]:
        """Assess technical quality using simple image metrics."""
        import numpy as np

        results = []
        for i, img in enumerate(frames):
            arr = np.array(img, dtype=np.float64)
            gray = np.mean(arr, axis=2)

            # Blur detection: Laplacian variance (low = blurry)
            # Manual Laplacian approximation using numpy
            laplacian_kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]])
            from scipy.signal import convolve2d
            laplacian = convolve2d(gray, laplacian_kernel, mode="valid")
            blur_score = float(np.var(laplacian))

            # Brightness: mean pixel value (0-255 scale)
            brightness = float(np.mean(arr))

            # Contrast: standard deviation of pixel values
            contrast = float(np.std(arr))

            # Classify quality
            quality_issues = []
            if blur_score < 100:
                quality_issues.append("blurry")
            if brightness < 40:
                quality_issues.append("underexposed")
            elif brightness > 220:
                quality_issues.append("overexposed")
            if contrast < 30:
                quality_issues.append("low_contrast")

            quality_label = "good" if not quality_issues else "issues_detected"

            results.append({
                "frame_index": i,
                "blur_score": round(blur_score, 2),
                "brightness": round(brightness, 2),
                "contrast": round(contrast, 2),
                "quality": quality_label,
                "issues": quality_issues,
                "resolution": f"{img.width}x{img.height}",
            })

        return results

    # ------------------------------------------------------------------
    # VLM-based analysis modes
    # ------------------------------------------------------------------

    def _load_model(self, model_name: str):
        """Load the requested vision-language model and processor."""
        import torch
        from transformers import (
            CLIPProcessor,
            CLIPModel,
            Blip2Processor,
            Blip2ForConditionalGeneration,
            AutoProcessor,
            AutoModelForCausalLM,
        )

        device = "cuda" if torch.cuda.is_available() else "cpu"

        if model_name == "clip":
            model_id = "openai/clip-vit-base-patch32"
            processor = CLIPProcessor.from_pretrained(model_id)
            model = CLIPModel.from_pretrained(model_id).to(device)
            return model, processor, device

        if model_name == "blip2":
            model_id = "Salesforce/blip2-opt-2.7b"
            processor = Blip2Processor.from_pretrained(model_id)
            model = Blip2ForConditionalGeneration.from_pretrained(
                model_id, torch_dtype=torch.float16 if device == "cuda" else torch.float32
            ).to(device)
            return model, processor, device

        if model_name == "llava":
            model_id = "llava-hf/llava-1.5-7b-hf"
            processor = AutoProcessor.from_pretrained(model_id)
            model = AutoModelForCausalLM.from_pretrained(
                model_id, torch_dtype=torch.float16 if device == "cuda" else torch.float32
            ).to(device)
            return model, processor, device

        raise ValueError(f"Unknown model: {model_name}")

    def _analyze_describe(
        self, frames: list, model_name: str
    ) -> list[dict[str, Any]]:
        """Generate captions for each frame."""
        import torch

        model, processor, device = self._load_model(model_name)
        results = []

        for i, img in enumerate(frames):
            if model_name == "clip":
                # CLIP is not a captioning model; use zero-shot classification
                # with generic scene descriptions as a caption proxy
                candidate_texts = [
                    "a photo of a person", "a photo of a landscape",
                    "a photo of an object", "a photo of text",
                    "a photo of an animal", "a photo of a building",
                    "a photo of food", "a photo of a vehicle",
                    "an abstract image", "a dark scene", "a bright scene",
                ]
                clip_inputs = processor(
                    text=candidate_texts, images=img, return_tensors="pt", padding=True
                ).to(device)
                with torch.no_grad():
                    outputs = model(**clip_inputs)
                probs = outputs.logits_per_image.softmax(dim=1)[0]
                top_idx = probs.argmax().item()
                caption = candidate_texts[top_idx]
                confidence = round(probs[top_idx].item(), 3)
                results.append({
                    "frame_index": i,
                    "description": caption,
                    "confidence": confidence,
                })

            elif model_name in ("blip2", "llava"):
                inputs = processor(images=img, return_tensors="pt").to(device)
                with torch.no_grad():
                    generated_ids = model.generate(**inputs, max_new_tokens=50)
                caption = processor.batch_decode(
                    generated_ids, skip_special_tokens=True
                )[0].strip()
                results.append({
                    "frame_index": i,
                    "description": caption,
                })

        return results

    def _analyze_qa(
        self, frames: list, model_name: str, query: str
    ) -> list[dict[str, Any]]:
        """Answer a question about each frame."""
        import torch

        model, processor, device = self._load_model(model_name)
        results = []

        for i, img in enumerate(frames):
            if model_name == "clip":
                # Use query as one candidate and its negation as another
                candidates = [query, f"not {query}"]
                clip_inputs = processor(
                    text=candidates, images=img, return_tensors="pt", padding=True
                ).to(device)
                with torch.no_grad():
                    outputs = model(**clip_inputs)
                probs = outputs.logits_per_image.softmax(dim=1)[0]
                yes_prob = probs[0].item()
                results.append({
                    "frame_index": i,
                    "query": query,
                    "answer": "yes" if yes_prob > 0.5 else "no",
                    "confidence": round(max(yes_prob, 1 - yes_prob), 3),
                })

            elif model_name in ("blip2", "llava"):
                prompt = f"Question: {query} Answer:"
                inputs = processor(
                    images=img, text=prompt, return_tensors="pt"
                ).to(device)
                with torch.no_grad():
                    generated_ids = model.generate(**inputs, max_new_tokens=50)
                answer = processor.batch_decode(
                    generated_ids, skip_special_tokens=True
                )[0].strip()
                # Remove the prompt echo if present
                if answer.startswith(prompt):
                    answer = answer[len(prompt):].strip()
                results.append({
                    "frame_index": i,
                    "query": query,
                    "answer": answer,
                })

        return results

    def _analyze_classify(
        self, frames: list, model_name: str
    ) -> list[dict[str, Any]]:
        """Classify each frame into scene categories."""
        import torch

        model, processor, device = self._load_model(model_name)
        results = []

        for i, img in enumerate(frames):
            if model_name == "clip":
                candidate_texts = [f"a {cat} scene" for cat in SCENE_CATEGORIES]
                clip_inputs = processor(
                    text=candidate_texts, images=img, return_tensors="pt", padding=True
                ).to(device)
                with torch.no_grad():
                    outputs = model(**clip_inputs)
                probs = outputs.logits_per_image.softmax(dim=1)[0]

                scored = sorted(
                    zip(SCENE_CATEGORIES, probs.tolist()),
                    key=lambda x: x[1],
                    reverse=True,
                )
                results.append({
                    "frame_index": i,
                    "top_category": scored[0][0],
                    "confidence": round(scored[0][1], 3),
                    "categories": [
                        {"label": label, "score": round(score, 3)}
                        for label, score in scored[:5]
                    ],
                })

            elif model_name in ("blip2", "llava"):
                prompt = (
                    "Classify this image into one of these categories: "
                    + ", ".join(SCENE_CATEGORIES)
                    + ". Category:"
                )
                inputs = processor(
                    images=img, text=prompt, return_tensors="pt"
                ).to(device)
                with torch.no_grad():
                    generated_ids = model.generate(**inputs, max_new_tokens=20)
                category = processor.batch_decode(
                    generated_ids, skip_special_tokens=True
                )[0].strip()
                if category.startswith(prompt):
                    category = category[len(prompt):].strip()
                results.append({
                    "frame_index": i,
                    "top_category": category,
                })

        return results

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _build_summary(
        self, frame_results: list[dict[str, Any]], mode: str
    ) -> str:
        """Build a human-readable summary from per-frame results."""
        n = len(frame_results)

        if mode == "describe":
            descriptions = [r.get("description", "") for r in frame_results]
            if n == 1:
                return descriptions[0]
            return f"Analyzed {n} frames. Descriptions: " + "; ".join(descriptions)

        if mode == "qa":
            answers = [r.get("answer", "") for r in frame_results]
            if n == 1:
                return answers[0]
            return f"Analyzed {n} frames. Answers: " + "; ".join(answers)

        if mode == "quality":
            issues_all = []
            for r in frame_results:
                issues_all.extend(r.get("issues", []))
            if not issues_all:
                return f"All {n} frame(s) passed quality checks."
            unique_issues = sorted(set(issues_all))
            return (
                f"Analyzed {n} frame(s). Issues found: {', '.join(unique_issues)}."
            )

        if mode == "classify":
            categories = [r.get("top_category", "unknown") for r in frame_results]
            if n == 1:
                return f"Scene classified as: {categories[0]}"
            return (
                f"Analyzed {n} frames. Scene categories: "
                + ", ".join(categories)
            )

        return f"Analyzed {n} frame(s)."
