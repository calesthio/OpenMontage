"""Explicit tool/host/model constraints shared by capability selectors."""

from __future__ import annotations


def filter_explicit_route(inputs, candidates):
    tool_name = inputs.get("preferred_tool")
    host = inputs.get("hosting_provider")
    model_field = next(
        (f for f in ("model", "model_id", "model_name") if inputs.get(f)), None
    )
    model = inputs.get(model_field) if model_field else None
    selected = []
    unvouched = []  # targeted open-field tools that cannot vouch for `model`
    for tool in candidates:
        if tool_name and tool.name != tool_name:
            continue
        if host and getattr(tool, "hosting_provider", tool.provider) != host:
            continue
        if model:
            props = tool.input_schema.get("properties", {})
            models = set()
            for field in ("model", "model_id", "model_name"):
                models.update(props.get(field, {}).get("enum", []))
            models.update(getattr(tool, "_MODELS", {}))
            models.update(getattr(tool, "_MODEL_ALIASES", {}))
            models.update(tool.get_info().get("model_catalog", {}))
            # Free-form model fields can't be enumerated; such a tool may still
            # vouch for a specific value (e.g. piper: an installed voice or .onnx path).
            vouch = getattr(tool, "vouches_for_model", None)
            if model not in models and not (
                model_field in props and vouch and vouch(model)
            ):
                # An open field can accept a caller-pinned model without
                # claiming that unrelated free-form tools support it in auto mode.
                if not (
                    not models
                    and model_field in props
                    and (tool_name or tool.provider == inputs.get("preferred_provider"))
                ):
                    continue
                unvouched.append(tool)
        operation = inputs.get("generation_mode") or inputs.get("operation")
        routes = getattr(tool, "routes", None) or getattr(tool, "models", None)
        if isinstance(routes, dict) and operation and operation != "rank":
            model_routes = (
                routes.get(model, {}) if model else next(iter(routes.values()), {})
            )
            normalized = (
                "text_to_video"
                if operation == "generate" and tool.capability == "video_generation"
                else operation
            )
            if tool.capability == "image_generation":
                if normalized == "generate" and "text_to_image" in model_routes:
                    has_references = any(inputs.get(key) for key in (
                        "image_url", "image_urls", "image_path", "image_paths"
                    ))
                    normalized = "image_to_image" if has_references else "text_to_image"
                elif normalized == "edit" and "image_to_image" in model_routes:
                    normalized = "image_to_image"
            if normalized == "video_edit" and "video_to_video_edit" in model_routes:
                normalized = "video_to_video_edit"
            if normalized not in model_routes:
                continue
        if tool.capability == "image_generation":
            props = tool.input_schema.get("properties", {})
            if any(inputs.get(k) and k not in props for k in ("mask_path", "mask_url")):
                continue
            # Template tools (accepts_image_input) decide from the template the
            # request's ``workflow`` selects, not from the default's schema.
            accepts_image = getattr(tool, "accepts_image_input", None)
            if accepts_image is not None and accepts_image(inputs):
                props = {**props, "image_path": {}}
            if any(
                inputs.get(k) and k not in props and "images" not in props
                for k in ("image_path", "image_paths", "image_url", "image_urls")
            ):
                continue
            if operation == "precise_edit" and not (
                getattr(tool, "supports", {}).get("precise_edit")
                or isinstance(routes, dict)
                and any("precise_edit" in r for r in routes.values())
            ):
                continue
        selected.append(tool)
    # A tool that declares the model beats one that merely might accept it.
    vouched = [t for t in selected if t not in unvouched]
    return vouched or selected
