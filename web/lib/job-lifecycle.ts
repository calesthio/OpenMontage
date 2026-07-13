// Pure state machine for the job detail page — extracted so the reducer is
// testable without the SSE-driven page shell (mirrors lib/pipeline-picker.ts).
// Every transition here used to live as a hand-updated chain of individual
// useState calls inside the page's ~55-line SSE es.onmessage if-chain, plus a
// few more scattered across the REST-driven handlers (retry/cancel/approve).
// Consolidating them into one reducer is what makes an asymmetric reset (see
// "approve_succeeded" below — a real bug found and fixed by this extraction)
// visible and preventable, instead of a silent gap between two independent
// setState calls that happen to usually be followed by an SSE event that
// papers over the inconsistency.

import type { SseEvent } from "@/components/job-status";

export type JobLifecycleState = {
  projectName: string | null;
  events: SseEvent[];
  currentStage: string | null;
  // The pipeline's real, ordered stage list — sent by the backend on
  // job_started (server/app/runner/stage_runner.py "stages": [...]). Different
  // pipelines have different stage counts/names (5 for documentary-montage, 9
  // for screen-demo, etc.), so this must come from the job itself, not a
  // hardcoded constant shaped after one pipeline.
  stages: string[];
  status: string;
  awaitingStage: string | null;
  // Distinguishes which kind of gate is pending: undefined/"stage" for the
  // ordinary end-of-stage artifact review, "budget" for an overspend
  // ceiling, "sample_preview" for a mid-stage checkpoint (e.g.
  // asset-director.md's "generate one sample, confirm before batching").
  // Each renders differently (see ApprovalPanel) — the same `awaiting_approval`
  // event type carries a differently-shaped `preview` depending on this field.
  awaitingGate: string | null;
  // The seq of the awaiting_approval event that produced the CURRENT
  // awaitingStage/awaitingGate/preview trio. Exists only so the page can key
  // <ApprovalPanel> on gate identity (stage+gate+this seq) and get a forced
  // remount on every new gate — including a new gate that happens to repeat
  // the same stage/gate string as the previous one — instead of hand-resetting
  // the panel's local edit state from here.
  awaitingGateSeq: number | null;
  preview: Record<string, unknown> | null;
  renderUrl: string | null;
  // Interim preview: the compose stage's own render, playable as soon as it's
  // produced — well before publish (packaging/distribution metadata) finishes.
  // Distinct from renderUrl, which is only set once the whole job completes.
  previewRenderUrl: string | null;
  // A/B variant job only: sibling plural dicts alongside renderUrl/
  // previewRenderUrl, keyed by a short model-derived slug (e.g. "ltx-2-3").
  // Null/empty for a normal (non-variant) job — the singular fields above
  // remain the source of truth for that case.
  renderUrls: Record<string, string> | null;
  previewRenderUrls: Record<string, string> | null;
  costCny: number;
  budgetCny: number | null;
};

export const initialJobLifecycleState: JobLifecycleState = {
  projectName: null,
  events: [],
  currentStage: null,
  stages: [],
  status: "queued",
  awaitingStage: null,
  awaitingGate: null,
  awaitingGateSeq: null,
  preview: null,
  renderUrl: null,
  previewRenderUrl: null,
  renderUrls: null,
  previewRenderUrls: null,
  costCny: 0,
  budgetCny: null,
};

/** The subset of the GET /jobs/:id response this reducer cares about. */
export type InitialJobFetch = {
  project_name?: string | null;
  render_url?: string | null;
  preview_render_url?: string | null;
  render_urls?: Record<string, string> | null;
  preview_render_urls?: Record<string, string> | null;
};

export type JobLifecycleAction =
  // Seed real state on mount via REST — the SSE stream alone only carries
  // events from lastEventId onward; the page title (and cost/status on a
  // fresh load) shouldn't have to wait for the full event replay to resolve.
  | { type: "initial_fetch"; job: InitialJobFetch }
  // Every SSE message, unparsed into per-type actions here rather than in the
  // hook that owns the EventSource connection — that keeps the hook a thin
  // transport (parse + dispatch) and puts the actual mapping, and its
  // rationale, in one place: this switch.
  | { type: "sse_event"; event: SseEvent }
  // REST-driven paths that mutate lifecycle state outside the SSE stream:
  | { type: "retry_succeeded" }
  | { type: "approve_succeeded" }
  | { type: "cancel_resolved"; status: string };

export function jobLifecycleReducer(
  state: JobLifecycleState,
  action: JobLifecycleAction
): JobLifecycleState {
  switch (action.type) {
    case "initial_fetch": {
      const job = action.job;
      return {
        ...state,
        projectName: job.project_name ? job.project_name : state.projectName,
        renderUrl: job.render_url ? job.render_url : state.renderUrl,
        previewRenderUrl: job.preview_render_url ? job.preview_render_url : state.previewRenderUrl,
        renderUrls: job.render_urls ? job.render_urls : state.renderUrls,
        previewRenderUrls: job.preview_render_urls ? job.preview_render_urls : state.previewRenderUrls,
      };
    }

    case "retry_succeeded":
      return { ...state, status: "queued" };

    case "approve_succeeded":
      // Immediate UI feedback: don't make the operator wait on the SSE
      // round-trip (stage_approved) just to see the panel close. Reset BOTH
      // awaitingStage and awaitingGate (and the seq that keys the panel)
      // together here — resetting only awaitingStage and leaving awaitingGate
      // stale (e.g. stuck as "budget") was the exact asymmetry this reducer
      // was built to catch: the panel itself is gated on awaitingStage so the
      // bug was invisible on screen, but the stale awaitingGate lingered in
      // state until the next awaiting_approval/terminal event happened to
      // overwrite it.
      return { ...state, awaitingStage: null, awaitingGate: null, awaitingGateSeq: null };

    case "cancel_resolved": {
      // Contract: a queued/running job comes back with its status
      // UNCHANGED (cancellation happens asynchronously — the SSE
      // job_cancelled event, or the next poll, reflects the real
      // transition once it lands). An awaiting_approval job resolves
      // immediately to a terminal status, so reflect that right away
      // instead of waiting on a stream event that won't arrive for an
      // already-resolved gate.
      const status = action.status;
      const stillLive = status === "queued" || status === "running" || status === "awaiting_approval";
      return {
        ...state,
        status,
        awaitingStage: stillLive ? state.awaitingStage : null,
        awaitingGate: stillLive ? state.awaitingGate : null,
        awaitingGateSeq: stillLive ? state.awaitingGateSeq : null,
      };
    }

    case "sse_event":
      return applySseEvent(state, action.event);

    default:
      return state;
  }
}

function applySseEvent(state: JobLifecycleState, ev: SseEvent): JobLifecycleState {
  const next: JobLifecycleState = {
    ...state,
    events: [...state.events, ev],
    currentStage: ev.stage ? ev.stage : state.currentStage,
  };
  switch (ev.type) {
    case "job_started":
      next.status = "running";
      if (ev.stages?.length) next.stages = ev.stages;
      break;

    case "stage_started":
      next.status = "running";
      break;

    case "awaiting_approval":
      next.status = "awaiting_approval";
      next.awaitingStage = ev.stage ?? null;
      next.awaitingGate = ev.gate ?? null;
      next.awaitingGateSeq = ev.seq;
      next.preview = (ev.preview as Record<string, unknown> | null) ?? null;
      break;

    case "stage_approved":
    case "stage_rejected":
      next.awaitingStage = null;
      next.awaitingGate = null;
      next.awaitingGateSeq = null;
      next.status = "running";
      break;

    case "cost_updated":
      if (ev.cost_cny != null) {
        next.costCny = ev.cost_cny;
        if (ev.budget_cny != null) next.budgetCny = ev.budget_cny;
      }
      break;

    case "preview_ready":
      next.previewRenderUrl = ev.render_url ?? null;
      next.previewRenderUrls = ev.render_urls ?? null;
      break;

    case "job_completed":
      next.status = "completed";
      next.renderUrl = ev.render_url ?? null;
      next.renderUrls = ev.render_urls ?? null;
      break;

    case "job_failed":
      // Confirmed live: the budget gate's reject/timeout path (and any
      // other gate) jumps straight to job_failed with no intervening
      // stage_approved/stage_rejected — without this, the approval
      // panel stayed on screen showing dead Approve/Reject buttons
      // (POSTing to them 404s once the job is no longer
      // awaiting_approval) side-by-side with the failed/retry card.
      next.status = "failed";
      next.awaitingStage = null;
      next.awaitingGate = null;
      next.awaitingGateSeq = null;
      break;

    case "job_cancelled":
      // Mirrors job_completed/job_failed above: a queued/running job's
      // cancellation resolves asynchronously (see the cancel_resolved
      // action, dispatched from the page's handleCancel) — this is how
      // that eventual transition actually reaches the page.
      next.status = "cancelled";
      next.awaitingStage = null;
      next.awaitingGate = null;
      next.awaitingGateSeq = null;
      break;
  }
  return next;
}
