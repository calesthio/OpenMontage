"""Strict zero-cost gate for factory runs.

Master Plan section 9 ("Бюджет и сеть: строгий режим $0"):

- By default the mode is ``strict_zero_cost=true``.
- Before every network/model operation, verify the allowed provider,
  endpoint, model/route, current free-tier terms and the known cost.
- ``cost_usd = null``, an unknown route or unclear pricing means BLOCK,
  not FREE.
- Paid fallbacks are forbidden without explicit separate user approval.
- Auth / billing / rate-limit errors must never silently switch route.
- Secrets are never written to logs, artifacts or diagnostics.

The gate is deliberately fail-closed: a caller that knows nothing about
the cost of an operation gets ``BLOCKED``, because "we did not check" is
exactly the state that produces surprise bills. Local, non-metered work
(LOCAL runtime, no external endpoint) is the only path that passes
without an explicit cost of ``0.0`` and a declared route.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional

STRICT_ZERO_COST = "strict_zero_cost"
BUDGETED = "budgeted"


class ZeroCostViolation(Exception):
    """Raised when an operation would violate the strict zero-cost mode."""


# Failure taxonomy. Master Plan section 6 requires empty results and
# transport/auth/rate-limit errors to stay distinguishable — an adapter
# that collapses an exception into "no results" is a bug, not a feature.
AUTH_ERROR = "auth_error"
BILLING_ERROR = "billing_error"
RATE_LIMITED = "rate_limited"
TRANSPORT_ERROR = "transport_error"
NO_RESULTS = "no_results"
UNKNOWN_FAILURE = "unknown_failure"

_NON_REROUTABLE = frozenset(
    {AUTH_ERROR, BILLING_ERROR, RATE_LIMITED, TRANSPORT_ERROR, UNKNOWN_FAILURE}
)


@dataclass(frozen=True)
class ToolFacts:
    """What the gate needs to know about one operation.

    ``cost_usd=None`` means "not established". It does NOT mean free.
    ``route`` is the concrete endpoint/model path the call would take;
    ``None`` means the caller could not name it, which is a block.
    """

    tool: str
    operation: str = "execute"
    provider: Optional[str] = None
    runtime: str = "api"
    route: Optional[str] = None
    cost_usd: Optional[float] = None
    status: str = "available"
    secrets_involved: bool = False

    @property
    def cost_known(self) -> bool:
        return self.cost_usd is not None

    @property
    def route_known(self) -> bool:
        return bool(self.route)

    @property
    def is_local(self) -> bool:
        return str(self.runtime).lower() in {"local", "local_gpu"}


@dataclass(frozen=True)
class GateDecision:
    """Result of a gate evaluation. ``verdict`` is ``allowed`` or ``blocked``."""

    verdict: str
    tool: str
    operation: str
    reason: str
    cost_usd: Optional[float] = None
    route: Optional[str] = None
    mode: str = STRICT_ZERO_COST

    @property
    def allowed(self) -> bool:
        return self.verdict == "allowed"

    @property
    def blocked(self) -> bool:
        return self.verdict == "blocked"

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "tool": self.tool,
            "operation": self.operation,
            "reason": self.reason,
            "cost_usd": self.cost_usd,
            "route": self.route,
            "mode": self.mode,
        }


def facts_from_registry(
    tool_name: str,
    operation: str = "execute",
    *,
    cost_usd: Optional[float] = None,
    route: Optional[str] = None,
) -> ToolFacts:
    """Build :class:`ToolFacts` from the tool registry.

    The registry is the source of truth for runtime and status. Cost is
    deliberately NOT invented here: unless the caller states a cost, it
    stays ``None`` so the gate blocks the call rather than assuming it is
    free. Tools that carry an explicit ``cost_usd=0.0`` (local ffmpeg work,
    no-key archive sources) pass with their declared route.
    """

    from tools.tool_registry import registry  # local import: avoid cycles

    if not registry._tools:
        registry.discover()

    tool = registry._tools.get(tool_name)
    if tool is None:
        return ToolFacts(
            tool=tool_name,
            operation=operation,
            status="unknown",
            route=route,
            cost_usd=cost_usd,
        )

    info: Mapping[str, Any] = tool.get_info() or {}
    return ToolFacts(
        tool=tool_name,
        operation=operation,
        provider=str(info.get("provider") or ""),
        runtime=str(info.get("runtime") or "api").lower(),
        route=route or str(info.get("route") or "") or None,
        cost_usd=cost_usd,
        status=str(info.get("status") or "unknown"),
    )


def evaluate_call(
    facts: ToolFacts,
    *,
    mode: str = STRICT_ZERO_COST,
    user_approved: bool = False,
) -> GateDecision:
    """Decide whether one call may proceed.

    Strict zero-cost rules, in order:

    1. The route must be known. An unnamed endpoint is a block.
    2. The cost must be known. ``None`` is a block, never "free".
    3. In strict mode any non-zero cost is a block unless the user
       explicitly approved that specific paid action.
    4. A tool that is not ``available`` is a block — the caller must
       surface the unavailable provider instead of routing around it.
    """

    if facts.status not in {"available", "ok"}:
        return GateDecision(
            "blocked",
            facts.tool,
            facts.operation,
            f"tool status is {facts.status!r} — surface the provider as a setup request instead of substituting a route",
            facts.cost_usd,
            facts.route,
            mode,
        )

    if not facts.route_known:
        return GateDecision(
            "blocked",
            facts.tool,
            facts.operation,
            "unknown route — strict zero-cost mode blocks unnamed endpoints",
            facts.cost_usd,
            facts.route,
            mode,
        )

    if not facts.cost_known:
        return GateDecision(
            "blocked",
            facts.tool,
            facts.operation,
            "cost_usd is null — unknown pricing means BLOCK, not FREE",
            None,
            facts.route,
            mode,
        )

    cost = float(facts.cost_usd or 0.0)
    if cost < 0:
        return GateDecision(
            "blocked",
            facts.tool,
            facts.operation,
            "negative cost is not a valid estimate",
            cost,
            facts.route,
            mode,
        )

    if cost == 0.0:
        return GateDecision(
            "allowed",
            facts.tool,
            facts.operation,
            "zero-cost route with a declared endpoint",
            cost,
            facts.route,
            mode,
        )

    if mode == STRICT_ZERO_COST and not user_approved:
        return GateDecision(
            "blocked",
            facts.tool,
            facts.operation,
            (
                f"estimated ${cost:.4f} exceeds strict zero-cost mode; "
                "paid actions need explicit, separate user approval"
            ),
            cost,
            facts.route,
            mode,
        )

    return GateDecision(
        "allowed",
        facts.tool,
        facts.operation,
        "user explicitly approved this paid action",
        cost,
        facts.route,
        mode,
    )


def assert_zero_cost(
    facts: ToolFacts,
    *,
    mode: str = STRICT_ZERO_COST,
    user_approved: bool = False,
) -> GateDecision:
    """Evaluate a call and raise :class:`ZeroCostViolation` when blocked."""

    decision = evaluate_call(facts, mode=mode, user_approved=user_approved)
    if decision.blocked:
        raise ZeroCostViolation(
            f"{facts.tool}.{facts.operation} blocked in {mode}: {decision.reason}"
        )
    return decision


def evaluate_batch(
    calls: Iterable[ToolFacts],
    *,
    mode: str = STRICT_ZERO_COST,
    user_approved: bool = False,
) -> list[GateDecision]:
    """Evaluate many calls; useful for preflighting a whole stage plan."""

    return [
        evaluate_call(facts, mode=mode, user_approved=user_approved)
        for facts in calls
    ]


def classify_failure(status_code: Optional[int] = None, message: str = "") -> str:
    """Map a provider failure onto the factory failure taxonomy.

    Keeps ``no_results`` distinct from transport/auth/billing problems:
    "the search found nothing" and "the search could not run" are
    different facts and must never be reported the same way.
    """

    if status_code is None and not message:
        return UNKNOWN_FAILURE

    code = int(status_code) if status_code is not None else 0
    text = (message or "").lower()

    if code in {401, 403} or "unauthorized" in text or "forbidden" in text or "api key" in text:
        return AUTH_ERROR
    if code == 429 or "rate limit" in text or "too many requests" in text:
        return RATE_LIMITED
    if code in {402, 409} or (
        "insufficient" in text and ("credit" in text or "balance" in text or "quota" in text)
    ):
        return BILLING_ERROR
    if "billing" in text or "payment required" in text or "quota exceeded" in text:
        return BILLING_ERROR
    if code >= 500 or "timeout" in text or "connection" in text or "temporarily unavailable" in text:
        return TRANSPORT_ERROR
    if code and 400 <= code < 500:
        return TRANSPORT_ERROR
    return UNKNOWN_FAILURE


def reroute_allowed(failure: str) -> bool:
    """Whether a failure may silently switch to another provider/route.

    Always False. Auth, billing, rate-limit, transport and unknown
    failures are operator decisions: the run stops and reports, it does
    not quietly try the next billable vendor. ``failure`` is accepted so
    callers can log which taxonomy entry produced the refusal.
    """

    _ = failure  # taxonomy is recorded by the caller; the answer never varies
    return False


# Exception type names the corpus builder and its adapters surface as
# ``"TypeName: message"`` strings. Mapped so a search log line can be
# classified without re-raising the exception.
_EXCEPTION_CLASSES = {
    "httperror": AUTH_ERROR,
    "authenticationerror": AUTH_ERROR,
    "permissionerror": AUTH_ERROR,
    "ratelimiterror": RATE_LIMITED,
    "toomanyrequests": RATE_LIMITED,
    "quotaexceeded": BILLING_ERROR,
    "paymentrequired": BILLING_ERROR,
    "insufficientcredits": BILLING_ERROR,
    "timeout": TRANSPORT_ERROR,
    "timelimiterror": TRANSPORT_ERROR,
    "connectionerror": TRANSPORT_ERROR,
    "connectionreseterror": TRANSPORT_ERROR,
    "urlerror": TRANSPORT_ERROR,
    "chunkedencodingerror": TRANSPORT_ERROR,
}


def classify_search_record(record: Mapping[str, Any]) -> str:
    """Classify a search/download error record onto the failure taxonomy.

    ``record`` is the shape ``corpus_builder`` writes:
    ``{"phase": "search", "source": ..., "query": ..., "error": "TypeName: msg"}``.
    Post-search phases may carry an explicit ``"class"`` hint
    (``license_rejected`` / ``download_error`` / ``invalid_media``).
    """

    if not isinstance(record, Mapping):
        return UNKNOWN_FAILURE

    hint = str(record.get("class") or "").strip().lower()
    if hint in {
        NO_RESULTS,
        "license_rejected",
        "download_error",
        "invalid_media",
        AUTH_ERROR,
        BILLING_ERROR,
        RATE_LIMITED,
        TRANSPORT_ERROR,
    }:
        return hint

    message = str(record.get("error") or "")
    if not message:
        return UNKNOWN_FAILURE

    # A status code in the message is the most specific signal: an
    # "HTTPError: 429" is a rate limit, not an auth failure, even though the
    # exception type alone would suggest auth.
    status_code = _extract_status_code(message)
    if status_code is not None:
        return classify_failure(status_code, message)

    type_name = message.split(":", 1)[0].strip().lower()
    if type_name in _EXCEPTION_CLASSES:
        return _EXCEPTION_CLASSES[type_name]

    return classify_failure(None, message)


def _extract_status_code(message: str) -> Optional[int]:
    for token in message.replace(",", " ").split():
        if token.isdigit() and 100 <= int(token) <= 599:
            return int(token)
    lowered = message.lower()
    for code in ("401", "403", "429", "402", "500", "502", "503", "504"):
        if code in lowered:
            return int(code)
    return None


def search_stats_summary(
    searched: Iterable[tuple[str, str]],
    error_records: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Per-query result classes for the footage stage's manifest metadata.

    ``searched`` is the list of ``(source_name, query)`` pairs that were
    attempted. A pair that appears only here — no error record — is
    ``no_results``: the query genuinely matched nothing. A pair with an
    error record is classified from the taxonomy. The two are never merged,
    which is exactly the distinction Master Plan section 6.5 requires.
    """

    records = [r for r in error_records if isinstance(r, Mapping)]
    errored_keys = {(str(r.get("source")), str(r.get("query"))) for r in records}

    per_class: dict[str, int] = {}
    references: list[dict[str, str]] = []
    for source, query in searched:
        key = (str(source), str(query))
        if key in errored_keys:
            match = next(
                r
                for r in records
                if (str(r.get("source")), str(r.get("query"))) == key
            )
            failure = classify_search_record(match)
        else:
            failure = NO_RESULTS
        per_class[failure] = per_class.get(failure, 0) + 1
        references.append({"source": key[0], "query": key[1], "class": failure})

    return {
        "attempted": len(references),
        "per_class": per_class,
        "no_results_count": per_class.get(NO_RESULTS, 0),
        "error_count": len(references) - per_class.get(NO_RESULTS, 0),
        "queries": references,
    }


def failure_note(failure: str) -> str:
    """Operator-facing note for a classified failure."""

    notes = {
        AUTH_ERROR: "credentials missing or rejected — surface as a setup request, never reroute",
        BILLING_ERROR: "provider refused on billing grounds — stop and report, never reroute",
        RATE_LIMITED: "rate limited — back off and retry the same route, never reroute",
        TRANSPORT_ERROR: "transport failure — retry the same route with backoff, never reroute",
        NO_RESULTS: "the query genuinely returned nothing — a fact to record, not an error to hide",
        UNKNOWN_FAILURE: "unclassified failure — treat as blocked until it is understood",
    }
    return notes.get(failure, notes[UNKNOWN_FAILURE])


@dataclass
class RunBudgetLedger:
    """Per-run record of what the gate allowed and what it blocked.

    Persisted so the run's report can prove no paid route was invoked,
    instead of asserting it.
    """

    mode: str = STRICT_ZERO_COST
    decisions: list[GateDecision] = field(default_factory=list)

    def record(self, decision: GateDecision) -> GateDecision:
        self.decisions.append(decision)
        return decision

    @property
    def blocked(self) -> list[GateDecision]:
        return [d for d in self.decisions if d.blocked]

    @property
    def allowed(self) -> list[GateDecision]:
        return [d for d in self.decisions if d.allowed]

    @property
    def total_cost_usd(self) -> float:
        return round(sum(float(d.cost_usd or 0.0) for d in self.allowed), 6)

    def summary(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "allowed": len(self.allowed),
            "blocked": len(self.blocked),
            "total_cost_usd": self.total_cost_usd,
            "blocked_reasons": [d.as_dict() for d in self.blocked],
        }
