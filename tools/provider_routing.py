"""Explicit tool/host/model constraints shared by capability selectors."""

from __future__ import annotations


def _is_free_or_local(tool, inputs) -> bool:
    from tools.base_tool import ToolRuntime

    if tool.runtime in (ToolRuntime.LOCAL, ToolRuntime.LOCAL_GPU):
        return True
    try:
        return not tool.estimate_cost(inputs)
    except Exception:  # unpriced or unknown → treat as paid
        return False


def apply_paid_provider_policy(inputs, candidates):
    """Enforce ``routing.paid_provider_policy`` from relay_providers.yaml.

    ``relay_only`` keeps relay tools plus free/local tools, so a selector can
    never quietly bill a first-party vendor the user did not approve. A caller
    that has the user's explicit approval passes ``allow_non_relay_paid=True``.
    """
    try:
        from tools.relay.config import try_load_relay_config

        policy = try_load_relay_config().routing
    except Exception:
        return list(candidates)
    if not policy.relay_only or inputs.get("allow_non_relay_paid"):
        return list(candidates)
    return [
        tool
        for tool in candidates
        if getattr(tool, "is_relay_tool", False) or _is_free_or_local(tool, inputs)
    ]


def paid_policy_note(inputs) -> str:
    """Human-readable reason to append when a selector finds no provider."""
    try:
        from tools.relay.config import try_load_relay_config

        if try_load_relay_config().routing.relay_only and not inputs.get("allow_non_relay_paid"):
            return (
                " paid_provider_policy=relay_only: only relay tools and free/local tools are "
                "eligible. Check `python -m tools.relay check`, or pass "
                "allow_non_relay_paid=true after the user approves another paid vendor."
            )
    except Exception:
        pass
    return ""


def no_provider_message(base: str, inputs, all_candidates) -> str:
    """Explain an empty selection: missing key, unsupported op, or policy."""
    message = base
    wanted = inputs.get("preferred_tool")
    if wanted:
        tool = next((t for t in all_candidates if t.name == wanted), None)
        if tool is None:
            message += f" preferred_tool {wanted!r} is not registered."
        else:
            status = tool.get_status().value
            reason = ""
            try:
                reason = tool.get_info().get("status_reason") or ""
            except Exception:
                pass
            message += (
                f" preferred_tool {wanted!r} is {status}"
                + (f" ({reason})" if reason else "")
                + "; it does not match the requested operation/model, or is excluded. "
                "No other provider was tried."
            )
    return message + paid_policy_note(inputs)


def filter_explicit_route(inputs, candidates):
    candidates = apply_paid_provider_policy(inputs, candidates)
    tool_name = inputs.get("preferred_tool")
    host = inputs.get("hosting_provider")
    model = inputs.get("model") or inputs.get("model_id") or inputs.get("model_name")
    selected = []
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
            if model not in models:
                continue
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
            if normalized not in model_routes:
                continue
        if tool.capability == "image_generation":
            props = tool.input_schema.get("properties", {})
            if any(inputs.get(k) and k not in props for k in ("mask_path", "mask_url")):
                continue
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
    return selected
