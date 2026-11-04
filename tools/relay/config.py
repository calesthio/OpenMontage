"""Load and validate the relay provider config (``relay_providers.yaml``).

The config names relays (base URL + the *name* of the env var holding the key)
and the models each relay serves (protocol, declared capabilities, limits,
pricing). It never contains a secret: any literal key/token value is rejected,
so the file is safe to commit or paste into a chat.

Lookup order for the config file:
    1. ``OPENMONTAGE_RELAY_CONFIG`` (absolute or repo-relative path)
    2. ``<repo>/relay_providers.yaml``

A missing file is not an error — it simply means no relay tools exist.
A broken model entry is skipped and reported (``RelayConfig.errors``) so one
typo never takes the whole registry down.
"""

from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ENV = "OPENMONTAGE_RELAY_CONFIG"
DEFAULT_CONFIG_PATH = REPO_ROOT / "relay_providers.yaml"
POLICY_ENV = "OPENMONTAGE_PAID_PROVIDER_POLICY"

# --- vocabularies -----------------------------------------------------------

KIND_CAPABILITIES: dict[str, frozenset[str]] = {
    "image": frozenset({"text_to_image", "image_to_image"}),
    "video": frozenset(
        {"text_to_video", "image_to_video", "first_last_frame", "reference_to_video"}
    ),
    "tts": frozenset({"text_to_speech"}),
    # Text models are recorded for completeness (scripting / vision helpers).
    # The OpenMontage agent itself is the planner, so no BaseTool is built.
    "text": frozenset({"chat", "vision"}),
}

# protocol -> (kind, capabilities the protocol can express, default API root)
PROTOCOLS: dict[str, tuple[str, frozenset[str], str]] = {
    "openai_images": ("image", frozenset({"text_to_image", "image_to_image"}), "/v1"),
    "openai_videos": ("video", frozenset({"text_to_video", "image_to_video"}), "/v1"),
    "openai_video_generations": (
        "video",
        frozenset({"text_to_video", "image_to_video"}),
        "/v1",
    ),
    "ark_seedance": (
        "video",
        frozenset(
            {"text_to_video", "image_to_video", "first_last_frame", "reference_to_video"}
        ),
        "/api/v3",
    ),
    "generic_async": ("*", frozenset(), ""),
    "openai_speech": ("tts", frozenset({"text_to_speech"}), "/v1"),
    "openai_chat": ("text", frozenset({"chat", "vision"}), "/v1"),
}

IMAGE_INPUT_MODES = frozenset({"data_uri", "base64", "multipart", "url"})
PAID_POLICIES = frozenset({"any", "relay_only"})

_ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_SECRET_FIELD = re.compile(
    r"^(api[_-]?key|apikey|key|token|access[_-]?token|secret|password|authorization|bearer)$",
    re.I,
)
_SECRET_VALUE = re.compile(r"^(sk-|sk_|Bearer\s)[A-Za-z0-9_\-\.]{12,}")
_SLUG = re.compile(r"[^a-z0-9]+")


class RelayConfigError(ValueError):
    """The relay config file is unusable as a whole."""


# --- data model -------------------------------------------------------------


@dataclass
class Pricing:
    currency: str = "USD"
    cny_per_usd: float = 7.2
    per_request: Optional[float] = None
    per_image: Optional[float] = None
    per_second: Optional[float] = None
    per_1k_chars: Optional[float] = None

    @property
    def configured(self) -> bool:
        return any(
            v is not None
            for v in (self.per_request, self.per_image, self.per_second, self.per_1k_chars)
        )

    def to_usd(self, amount: float) -> float:
        if self.currency.upper() == "CNY":
            return amount / self.cny_per_usd
        return amount


@dataclass
class Relay:
    name: str
    base_url: str
    api_key_env: str
    display_name: str = ""
    auth_header: str = "Authorization"
    auth_scheme: str = "Bearer"
    extra_headers: dict[str, str] = field(default_factory=dict)
    extra_headers_env: dict[str, str] = field(default_factory=dict)
    live: bool = False
    allow_insecure_http: bool = False
    trust_env_proxy: bool = True

    def api_key(self) -> Optional[str]:
        value = os.environ.get(self.api_key_env, "").strip()
        return value or None

    @property
    def is_loopback(self) -> bool:
        return is_loopback_url(self.base_url)

    @property
    def billing_enabled(self) -> bool:
        """Real (billable) calls are allowed. A loopback relay is always a mock."""
        return self.live or self.is_loopback


@dataclass
class RelayModel:
    key: str  # unique id inside the config (tool name suffix)
    relay: Relay
    kind: str
    protocol: str
    model: str
    tool_name: str
    capabilities: frozenset[str]
    display_name: str = ""
    base_url: Optional[str] = None
    api_root: Optional[str] = None
    image_input: str = "data_uri"
    limits: dict[str, Any] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)
    pricing: Pricing = field(default_factory=Pricing)
    poll: dict[str, Any] = field(default_factory=dict)
    submit_timeout_seconds: float = 120.0
    request: dict[str, Any] = field(default_factory=dict)
    best_for: list[str] = field(default_factory=list)
    not_good_for: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    agent_skills: list[str] = field(default_factory=list)
    stability: str = "experimental"

    @property
    def endpoint(self) -> str:
        """Fully resolved API root for this model (no trailing slash)."""
        base = (self.base_url or self.relay.base_url).rstrip("/")
        root = self.api_root
        if root is None:
            root = PROTOCOLS[self.protocol][2]
        if root and urlsplit(base).path in ("", "/"):
            base = base + root
        return base

    @property
    def model_ids(self) -> list[str]:
        return [self.model, *[a for a in self.aliases if a != self.model]]

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def poll_setting(self, name: str, default: float) -> float:
        return float(self.poll.get(name, default))


@dataclass
class RoutingPolicy:
    paid_provider_policy: str = "any"

    @property
    def relay_only(self) -> bool:
        return self.effective_policy == "relay_only"

    @property
    def effective_policy(self) -> str:
        override = os.environ.get(POLICY_ENV, "").strip().lower()
        if override in PAID_POLICIES:
            return override
        return self.paid_provider_policy


@dataclass
class RelayConfig:
    path: Optional[Path]
    relays: dict[str, Relay] = field(default_factory=dict)
    models: list[RelayModel] = field(default_factory=list)
    routing: RoutingPolicy = field(default_factory=RoutingPolicy)
    errors: list[str] = field(default_factory=list)

    def models_of_kind(self, kind: str) -> list[RelayModel]:
        return [m for m in self.models if m.kind == kind]

    def get_model(self, tool_name: str) -> Optional[RelayModel]:
        return next((m for m in self.models if m.tool_name == tool_name), None)


# --- helpers ----------------------------------------------------------------


def is_loopback_url(url: str) -> bool:
    host = (urlsplit(url).hostname or "").strip("[]").lower()
    if host in {"localhost"} or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def config_path() -> Path:
    override = os.environ.get(CONFIG_ENV, "").strip()
    if override:
        path = Path(override).expanduser()
        return path if path.is_absolute() else REPO_ROOT / path
    return DEFAULT_CONFIG_PATH


def slugify(value: str) -> str:
    return _SLUG.sub("_", value.lower()).strip("_") or "model"


def _find_secrets(node: Any, trail: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            here = f"{trail}.{k}" if trail else str(k)
            if _SECRET_FIELD.match(str(k)) and isinstance(v, str) and v.strip():
                found.append(here)
            else:
                found.extend(_find_secrets(v, here))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            found.extend(_find_secrets(v, f"{trail}[{i}]"))
    elif isinstance(node, str) and _SECRET_VALUE.match(node.strip()):
        found.append(trail)
    return found


def _validate_url(url: str, *, allow_http: bool, where: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError(f"{where}: base_url must be an http(s) URL, got {url!r}")
    if parts.username or parts.password:
        raise ValueError(f"{where}: base_url must not embed credentials")
    if parts.query and re.search(r"(key|token|secret)=", parts.query, re.I):
        raise ValueError(f"{where}: base_url must not carry a key in its query string")
    if parts.scheme == "http" and not (allow_http or is_loopback_url(url)):
        raise ValueError(
            f"{where}: plain http is refused for non-local relays "
            "(set allow_insecure_http: true only if you understand the key travels in clear text)"
        )


def _str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def _parse_relay(name: str, raw: dict[str, Any]) -> Relay:
    where = f"relays.{name}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_\-]{0,40}", name):
        raise ValueError(f"{where}: relay name must be alphanumeric/_/- (max 41 chars)")
    base_url = str(raw.get("base_url") or "").strip()
    api_key_env = str(raw.get("api_key_env") or "").strip()
    if not base_url:
        raise ValueError(f"{where}: base_url is required")
    if not _ENV_NAME.match(api_key_env):
        raise ValueError(
            f"{where}: api_key_env must be an ENV_VAR_NAME (e.g. MYRELAY_API_KEY), "
            "never the key itself"
        )
    allow_http = bool(raw.get("allow_insecure_http", False))
    _validate_url(base_url, allow_http=allow_http, where=where)
    headers_env = {str(k): str(v) for k, v in (raw.get("extra_headers_env") or {}).items()}
    for header, env in headers_env.items():
        if not _ENV_NAME.match(env):
            raise ValueError(f"{where}.extra_headers_env.{header}: value must be an env var name")
    return Relay(
        name=name,
        base_url=base_url.rstrip("/"),
        api_key_env=api_key_env,
        display_name=str(raw.get("display_name") or name),
        auth_header=str(raw.get("auth_header", "Authorization")),
        auth_scheme=str(raw.get("auth_scheme", "Bearer")),
        extra_headers={str(k): str(v) for k, v in (raw.get("extra_headers") or {}).items()},
        extra_headers_env=headers_env,
        live=bool(raw.get("live", False)),
        allow_insecure_http=allow_http,
        trust_env_proxy=bool(raw.get("trust_env_proxy", True)),
    )


def _parse_pricing(raw: Any) -> Pricing:
    raw = raw or {}
    def num(name: str) -> Optional[float]:
        value = raw.get(name)
        if value is None:
            return None
        value = float(value)
        if value < 0:
            raise ValueError(f"pricing.{name} must be >= 0")
        return value
    currency = str(raw.get("currency", "USD")).upper()
    if currency not in {"USD", "CNY"}:
        raise ValueError("pricing.currency must be USD or CNY")
    return Pricing(
        currency=currency,
        cny_per_usd=float(raw.get("cny_per_usd", 7.2)),
        per_request=num("per_request"),
        per_image=num("per_image"),
        per_second=num("per_second"),
        per_1k_chars=num("per_1k_chars"),
    )


def _template_vars(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for v in node.values():
            found |= _template_vars(v)
    elif isinstance(node, list):
        for v in node:
            found |= _template_vars(v)
    elif isinstance(node, str):
        found |= set(re.findall(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}", node))
    return found


# Template variables a generic request must reference before a capability is
# allowed. Declaring image_to_video without wiring the first frame into the
# request would silently drop the user's image — exactly what we refuse.
_GENERIC_REQUIRES = {
    "image_to_video": {"first_frame", "first_frame_file"},
    "first_last_frame": {"last_frame", "last_frame_file"},
    "reference_to_video": {"reference_images"},
    "image_to_image": {"images", "first_frame", "first_frame_file"},
}


def _parse_model(relay: Relay, raw: dict[str, Any], index: int) -> RelayModel:
    where = f"relays.{relay.name}.models[{index}]"
    protocol = str(raw.get("protocol") or "").strip()
    if protocol not in PROTOCOLS:
        raise ValueError(f"{where}: protocol must be one of {sorted(PROTOCOLS)}")
    proto_kind, proto_caps, _ = PROTOCOLS[protocol]
    kind = str(raw.get("kind") or (proto_kind if proto_kind != "*" else "")).strip()
    if kind not in KIND_CAPABILITIES:
        raise ValueError(f"{where}: kind must be one of {sorted(KIND_CAPABILITIES)}")
    if proto_kind not in {"*", kind}:
        raise ValueError(f"{where}: protocol {protocol} serves kind {proto_kind}, not {kind}")
    if protocol == "generic_async" and kind not in {"image", "video"}:
        raise ValueError(f"{where}: generic_async currently serves image or video models")

    model_id = str(raw.get("model") or "").strip()
    if not model_id or any(c.isspace() for c in model_id):
        raise ValueError(f"{where}: model (the relay's exact model id) is required")

    caps = set(_str_list(raw.get("capabilities")))
    if not caps:
        raise ValueError(
            f"{where}: capabilities must be declared explicitly "
            f"(choose from {sorted(KIND_CAPABILITIES[kind])})"
        )
    unknown = caps - KIND_CAPABILITIES[kind]
    if unknown:
        raise ValueError(f"{where}: unknown capabilities for {kind}: {sorted(unknown)}")
    if proto_caps and not caps <= proto_caps:
        raise ValueError(
            f"{where}: protocol {protocol} cannot express {sorted(caps - proto_caps)}"
        )
    if "first_last_frame" in caps and "image_to_video" not in caps:
        raise ValueError(f"{where}: first_last_frame requires image_to_video")

    request = raw.get("request") or {}
    if protocol == "generic_async":
        submit = request.get("submit") or {}
        if not submit.get("path"):
            raise ValueError(f"{where}: generic_async needs request.submit.path")
        used = _template_vars(submit)
        for cap, needs in _GENERIC_REQUIRES.items():
            if cap in caps and not (used & needs):
                raise ValueError(
                    f"{where}: declares {cap} but request.submit never references "
                    f"any of {sorted(needs)} — the input would be silently dropped"
                )

    image_input = str(raw.get("image_input", "data_uri"))
    if image_input not in IMAGE_INPUT_MODES:
        raise ValueError(f"{where}: image_input must be one of {sorted(IMAGE_INPUT_MODES)}")
    if image_input == "multipart" and protocol not in {"openai_videos", "openai_images", "generic_async"}:
        raise ValueError(f"{where}: image_input multipart is not available for {protocol}")

    base_url = raw.get("base_url")
    if base_url:
        _validate_url(str(base_url), allow_http=relay.allow_insecure_http, where=where)

    key = slugify(str(raw.get("name") or model_id))
    tool_name = str(raw.get("tool_name") or f"relay_{slugify(relay.name)}_{key}")
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,80}", tool_name):
        raise ValueError(f"{where}: tool_name must be snake_case ({tool_name!r})")

    limits = dict(raw.get("limits") or {})
    poll = dict(raw.get("poll") or {})
    for name in ("interval_seconds", "timeout_seconds"):
        if name in poll and float(poll[name]) <= 0:
            raise ValueError(f"{where}: poll.{name} must be > 0")

    return RelayModel(
        key=key,
        relay=relay,
        kind=kind,
        protocol=protocol,
        model=model_id,
        tool_name=tool_name,
        capabilities=frozenset(caps),
        display_name=str(raw.get("display_name") or model_id),
        base_url=str(base_url).rstrip("/") if base_url else None,
        api_root=raw.get("api_root"),
        image_input=image_input,
        limits=limits,
        defaults=dict(raw.get("defaults") or {}),
        pricing=_parse_pricing(raw.get("pricing")),
        poll=poll,
        submit_timeout_seconds=float(raw.get("submit_timeout_seconds", 120)),
        request=request,
        best_for=_str_list(raw.get("best_for")),
        not_good_for=_str_list(raw.get("not_good_for")),
        aliases=_str_list(raw.get("aliases")),
        agent_skills=_str_list(raw.get("agent_skills")),
        stability=str(raw.get("stability", "experimental")),
    )


def parse_relay_config(data: Any, path: Optional[Path] = None) -> RelayConfig:
    """Validate an already-loaded YAML document."""
    if data is None:
        return RelayConfig(path=path)
    if not isinstance(data, dict):
        raise RelayConfigError("relay config must be a mapping")
    secrets = _find_secrets(data)
    if secrets:
        raise RelayConfigError(
            "relay config contains literal secrets at "
            + ", ".join(secrets)
            + ". Put keys in .env / environment variables and reference them with api_key_env."
        )

    config = RelayConfig(path=path)
    routing = data.get("routing") or {}
    policy = str(routing.get("paid_provider_policy", "any")).strip().lower()
    if policy not in PAID_POLICIES:
        raise RelayConfigError(f"routing.paid_provider_policy must be one of {sorted(PAID_POLICIES)}")
    config.routing = RoutingPolicy(paid_provider_policy=policy)

    seen_tools: set[str] = set()
    for name, raw in (data.get("relays") or {}).items():
        if not isinstance(raw, dict) or raw.get("enabled") is False:
            continue
        try:
            relay = _parse_relay(str(name), raw)
        except (ValueError, TypeError) as exc:
            config.errors.append(str(exc))
            continue
        config.relays[relay.name] = relay
        for index, model_raw in enumerate(raw.get("models") or []):
            if not isinstance(model_raw, dict) or model_raw.get("enabled") is False:
                continue
            try:
                model = _parse_model(relay, model_raw, index)
            except (ValueError, TypeError) as exc:
                config.errors.append(str(exc))
                continue
            if model.tool_name in seen_tools:
                config.errors.append(
                    f"relays.{relay.name}.models[{index}]: duplicate tool_name {model.tool_name}"
                )
                continue
            seen_tools.add(model.tool_name)
            config.models.append(model)
    return config


_CACHE: dict[str, tuple[float, RelayConfig]] = {}


def load_relay_config(path: Optional[Path] = None, *, use_cache: bool = True) -> RelayConfig:
    """Load the relay config; returns an empty config when the file is absent."""
    target = Path(path) if path else config_path()
    if not target.is_file():
        return RelayConfig(path=target)
    mtime = target.stat().st_mtime
    cache_key = str(target.resolve())
    if use_cache and cache_key in _CACHE and _CACHE[cache_key][0] == mtime:
        return _CACHE[cache_key][1]
    import yaml

    with open(target, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    config = parse_relay_config(data, target)
    _CACHE[cache_key] = (mtime, config)
    return config


def try_load_relay_config() -> RelayConfig:
    """Registry-safe loader: a broken file becomes a reported error, not a crash."""
    try:
        return load_relay_config()
    except Exception as exc:  # noqa: BLE001 — must never break tool discovery
        config = RelayConfig(path=config_path())
        config.errors.append(f"relay config unusable: {exc}")
        return config
