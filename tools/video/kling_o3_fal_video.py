"""All published Kling O3 video routes through fal.ai.

Standard, Pro and 4K each expose text, image, image-reference, video edit
and video-reference modes. No automatic retries of paid submissions; FalMedia
persists a queue checkpoint and supports GET-only resume after acceptance.
"""
from tools.fal_media import CONTRACTS, FalMedia


class KlingO3FalVideo(FalMedia):
    name = "kling_o3_fal_video"
    capability = "video_generation"
    capabilities = [
        "text_to_video", "image_to_video", "reference_to_video",
        "video_to_video_edit", "video_to_video_reference",
    ]
    supports = {operation: True for operation in (
        "text_to_video", "image_to_video", "reference_to_video",
        "video_to_video_edit", "video_to_video_reference",
    )}
    best_for = ["Kling O3 video generation, reference continuity and editing via fal.ai"]
    routes = {
        f"kling-o3-{tier}": {
            "text_to_video": f"fal-ai/kling-video/o3/{tier}/text-to-video",
            "image_to_video": f"fal-ai/kling-video/o3/{tier}/image-to-video",
            "reference_to_video": f"fal-ai/kling-video/o3/{tier}/reference-to-video",
            "video_to_video_edit": f"fal-ai/kling-video/o3/{tier}/video-to-video/edit",
            "video_to_video_reference": f"fal-ai/kling-video/o3/{tier}/video-to-video/reference",
        }
        for tier in ("standard", "pro", "4k")
    }

    def build_request(self, inputs):
        model = inputs.get("model", next(iter(self.routes)))
        operation = inputs.get("generation_mode") or inputs.get("operation")
        if operation == "video_edit":  # video_selector's legacy edit spelling
            operation = "video_to_video_edit"
        if not operation:
            if inputs.get("video_url") or inputs.get("reference_video_url"):
                raise ValueError("Select video_to_video_edit or video_to_video_reference explicitly")
            if any(inputs.get(key) for key in ("image_url", "image_path")):
                operation = "image_to_video"
            elif any(inputs.get(key) for key in (
                "image_urls", "image_paths", "start_image_url", "elements",
                "reference_image_urls", "reference_image_paths",
            )):
                operation = "reference_to_video"
            else:
                operation = "text_to_video"
        endpoint = self.routes.get(model, {}).get(operation)
        if not endpoint:
            raise ValueError(f"Unsupported model/operation: {model}/{operation}")
        if operation in {"text_to_video", "image_to_video", "reference_to_video"}:
            if inputs.get("prompt") is not None and inputs.get("multi_prompt") is not None:
                raise ValueError("Provide prompt or multi_prompt, not both")
        native = dict(inputs)
        aliases = {
            "reference_image_path", "reference_image_paths", "reference_image_url",
            "reference_image_urls", "reference_video_url", "reference_video_path",
            "reference_video_urls", "reference_video_paths", "reference_audio_urls",
            "reference_audio_paths", "last_image_url", "last_image_path",
            "video_path", "image_list", "video_list", "element_list",
        }
        if operation == "image_to_video":
            if native.get("reference_image_path"):
                if native.get("image_path") or native.get("image_url"):
                    raise ValueError("Provide only one first-frame image")
                native["image_path"] = native.pop("reference_image_path")
            if native.get("reference_image_url"):
                if native.get("image_url") or native.get("image_path"):
                    raise ValueError("Provide only one first-frame image")
                native["image_url"] = native.pop("reference_image_url")
        if operation in {"reference_to_video", "video_to_video_edit", "video_to_video_reference"}:
            urls = list(native.get("image_urls") or [])
            paths = list(native.get("image_paths") or [])
            urls.extend(native.pop("reference_image_urls", []) or [])
            paths.extend(native.pop("reference_image_paths", []) or [])
            if native.get("reference_image_url"):
                urls.append(native.pop("reference_image_url"))
            if native.get("reference_image_path"):
                paths.append(native.pop("reference_image_path"))
            if urls:
                native["image_urls"] = urls
            if paths:
                native["image_paths"] = paths
        if operation in {"image_to_video", "reference_to_video"}:
            if native.get("last_image_url") or native.get("last_image_path"):
                if native.get("end_image_url") or (native.get("last_image_url") and native.get("last_image_path")):
                    raise ValueError("Provide only one last-frame image")
                if native.get("last_image_url"):
                    native["end_image_url"] = native.pop("last_image_url")
                else:
                    from tools.schema_media import local_image
                    native["end_image_url"] = local_image(native.pop("last_image_path"))
        if operation in {"video_to_video_edit", "video_to_video_reference"} and native.get("reference_video_url"):
            if native.get("video_url"):
                raise ValueError("Provide only one source video URL")
            native["video_url"] = native.pop("reference_video_url")
        unsupported = sorted(key for key in aliases if native.get(key))
        if unsupported:
            raise ValueError(f"{endpoint} does not accept {', '.join(unsupported)}")
        props = CONTRACTS[endpoint]["input_schema"]["properties"]
        native_fields = {
            field
            for operations in self.routes.values()
            for route in operations.values()
            for field in CONTRACTS[route]["input_schema"]["properties"]
        }
        unexpected = native_fields.intersection(native).difference(props)
        if native.get("image_url") and operation == "reference_to_video":
            raise ValueError("Use start_image_url for the first frame; image_urls are references")
        if unexpected and not (unexpected == {"image_url"} and "image_urls" in props):
            raise ValueError(f"{endpoint} does not accept {', '.join(sorted(unexpected))}")
        return super().build_request({**native, "operation": operation, "generation_mode": operation})
