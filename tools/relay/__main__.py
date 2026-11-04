"""Relay provider CLI.

    python -m tools.relay check            validate config + env vars (no network)
    python -m tools.relay list             tools built from the config, with capabilities
    python -m tools.relay models --relay R list model ids the relay serves to your key (GET /models, free)
    python -m tools.relay resume JOB.json  resume a pending job (polls + downloads, never resubmits)
    python -m tools.relay mock-server      run the loopback mock relay for manual testing

Output never contains key values — only env var names and whether they are set.
"""

from __future__ import annotations

import argparse
import json
import sys
import time


def _print(obj) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace") if hasattr(sys.stdout, "reconfigure") else None
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def cmd_check(_args) -> int:
    from tools.relay.config import config_path, load_relay_config

    path = config_path()
    try:
        config = load_relay_config(use_cache=False)
    except Exception as exc:  # noqa: BLE001
        _print({"config_path": str(path), "ok": False, "error": str(exc)})
        return 1
    relays = {
        name: {
            "base_url": relay.base_url,
            "api_key_env": relay.api_key_env,
            "api_key_set": bool(relay.api_key()),
            "live": relay.live,
            "billing_enabled": relay.billing_enabled,
            "proxy_from_env": relay.trust_env_proxy,
        }
        for name, relay in config.relays.items()
    }
    models = [
        {
            "tool": m.tool_name,
            "kind": m.kind,
            "relay": m.relay.name,
            "model": m.model,
            "protocol": m.protocol,
            "endpoint": m.endpoint,
            "capabilities": sorted(m.capabilities),
            "image_input": m.image_input,
            "priced": m.pricing.configured,
        }
        for m in config.models
    ]
    warnings = []
    for m in config.models:
        if not m.pricing.configured and m.kind != "text":
            warnings.append(f"{m.tool_name}: no pricing — calls need allow_unpriced=true and budget cannot track them")
    for name, info in relays.items():
        if not info["api_key_set"]:
            warnings.append(f"relay {name}: {info['api_key_env']} is not set in the environment/.env")
        if not info["billing_enabled"]:
            warnings.append(f"relay {name}: live is false — real calls refused until you enable it")
    _print({
        "config_path": str(path),
        "exists": path.is_file(),
        "ok": not config.errors,
        "paid_provider_policy": config.routing.effective_policy,
        "relays": relays,
        "models": models,
        "errors": config.errors,
        "warnings": warnings,
    })
    return 0 if not config.errors else 1


def cmd_list(_args) -> int:
    from tools.tool_registry import registry

    registry.discover()
    rows = []
    for tool in registry._tools.values():
        if not getattr(tool, "is_relay_tool", False):
            continue
        info = tool.get_info()
        rows.append({
            "tool": tool.name,
            "capability": tool.capability,
            "hosting_provider": tool.hosting_provider,
            "model": tool.relay_model.model,
            "status": info["status"],
            "status_reason": info.get("status_reason"),
            "supports": {k: v for k, v in tool.supports.items() if isinstance(v, bool)},
            "unsupported": info["relay"]["unsupported_capabilities"],
        })
    _print(sorted(rows, key=lambda r: r["tool"]))
    return 0


def cmd_models(args) -> int:
    from tools.relay.config import load_relay_config
    from tools.relay.engine import RelayHTTP

    config = load_relay_config(use_cache=False)
    relay_models = [m for m in config.models if m.relay.name == args.relay]
    if not relay_models:
        _print({"error": f"no models configured for relay {args.relay!r}"})
        return 1
    model = next((m for m in relay_models if m.protocol.startswith("openai")), relay_models[0])
    http = RelayHTTP(model)
    try:
        payload = http.get_json("/models")
    except Exception as exc:  # noqa: BLE001
        _print({"relay": args.relay, "error": http.redact(str(exc))})
        return 1
    ids = sorted(str(item.get("id") or item.get("model")) for item in payload.get("data", []) if isinstance(item, dict))
    configured = {m.model for m in relay_models}
    _print({
        "relay": args.relay,
        "endpoint": model.endpoint,
        "served_model_ids": ids,
        "configured_but_not_served": sorted(configured - set(ids)) if ids else "relay did not list models",
    })
    return 0


def cmd_resume(args) -> int:
    from pathlib import Path

    from tools.relay.engine import load_job
    from tools.tool_registry import registry

    job_path = Path(args.job_path)
    job = load_job(job_path)
    if not job:
        _print({"error": f"job file not found: {job_path}"})
        return 1
    registry.discover()
    tool = registry.get(job["tool"])
    if tool is None:
        _print({"error": f"tool {job['tool']} is not registered (relay config changed?)"})
        return 1
    result = tool.execute({"job_path": str(job_path), "resume_job": {"job_path": str(job_path)},
                           "output_path": job["output_path"], "prompt": "", "text": "",
                           **({"poll_timeout_seconds": args.timeout} if args.timeout else {})})
    _print({"success": result.success, "error": result.error, "data": result.data, "cost_usd": result.cost_usd})
    return 0 if result.success else 2


def cmd_mock(args) -> int:
    from tools.relay.mock_server import MockRelay

    relay = MockRelay(expected_key=args.key, port=args.port).start()
    print(f"mock relay listening on {relay.url}  (Authorization: Bearer {args.key or '<any>'})")
    print("Point a relay's base_url at it; loopback relays are always allowed without live: true. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        relay.stop()
    return 0


def main(argv=None) -> int:
    import tools.base_tool  # noqa: F401 — loads .env so key presence is reported correctly

    parser = argparse.ArgumentParser(prog="python -m tools.relay", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    p = sub.add_parser("models")
    p.add_argument("--relay", required=True)
    p.set_defaults(fn=cmd_models)
    p = sub.add_parser("resume")
    p.add_argument("job_path")
    p.add_argument("--timeout", type=float, default=None, help="poll timeout seconds for this resume")
    p.set_defaults(fn=cmd_resume)
    p = sub.add_parser("mock-server")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--key", default="test-key")
    p.set_defaults(fn=cmd_mock)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
