"use client";

import { useEffect, useReducer, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";
import { StatusBadge, EventRow, stageLabel, VideoGallery } from "@/components/job-status";
import { SERVER, apiRequest } from "@/lib/api";
import { jobLifecycleReducer, initialJobLifecycleState } from "@/lib/job-lifecycle";
import { useJobEvents } from "@/lib/use-job-events";
import { ApprovalPanel } from "@/components/approval-panel";

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [state, dispatch] = useReducer(jobLifecycleReducer, initialJobLifecycleState);
  const { reconnect } = useJobEvents(jobId, dispatch);

  // Action state — retry/cancel/approve share this single actionError card.
  const [retrying, setRetrying] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [actionError, setActionError] = useState("");

  const bottomRef = useRef<HTMLDivElement>(null);

  // Seed real state on mount via REST — the SSE stream alone only carries
  // events from lastEventId onward; the page title (and cost/status on a
  // fresh load) shouldn't have to wait for the full event replay to resolve.
  useEffect(() => {
    apiRequest(`/jobs/${jobId}`).then((r) => {
      if (!r.ok) return;
      dispatch({ type: "initial_fetch", job: r.data });
    });
  }, [jobId]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [state.events]);

  async function handleRetry() {
    setRetrying(true);
    setActionError("");
    const res = await apiRequest(`/jobs/${jobId}/retry`, { method: "POST" });
    if (res.ok) {
      dispatch({ type: "retry_succeeded" });
      // The previous EventSource already closed (the backend ended that
      // stream once it drained to the earlier terminal event) and nothing
      // was scheduled to reconnect it, so open a fresh one from where we
      // left off rather than just flipping a flag nothing reacts to.
      reconnect();
    } else {
      setActionError(res.detail);
    }
    setRetrying(false);
  }

  async function handleCancel() {
    setCancelling(true);
    setActionError("");
    const res = await apiRequest(`/jobs/${jobId}/cancel`, { method: "POST" });
    if (res.ok) {
      const body = res.data;
      if (body.status) {
        dispatch({ type: "cancel_resolved", status: body.status });
      }
    } else {
      setActionError(res.detail);
    }
    setCancelling(false);
  }

  const stageIndex = state.currentStage ? state.stages.indexOf(state.currentStage) : -1;
  const progress = stageIndex >= 0 && state.stages.length > 0
    ? Math.round(((stageIndex + 1) / state.stages.length) * 100)
    : 0;
  // Only offer cancellation while the job is still live / gated — not once
  // it has already reached a terminal state (completed/failed/cancelled).
  const isCancellable = state.status === "queued" || state.status === "running" || state.status === "awaiting_approval";

  return (
    <div className="p-8 max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight">{state.projectName ?? "加载中…"}</h1>
          <p className="text-muted-foreground text-sm mt-0.5 font-mono">{jobId}</p>
        </div>
        <div className="flex items-center gap-3">
          {(state.costCny > 0 || state.budgetCny != null) && (
            <span
              className={`text-xs font-mono border px-2 py-0.5 rounded-full ${
                state.budgetCny != null && state.costCny > state.budgetCny
                  ? "text-red-400 border-red-500/40 bg-red-500/10"
                  : "text-muted-foreground border-border"
              }`}
              title="工具调用累计成本(CNY)"
            >
              ¥{state.costCny.toFixed(4)}
              {state.budgetCny != null && ` / ¥${state.budgetCny.toFixed(2)} 预算`}
            </span>
          )}
          {isCancellable && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleCancel}
              disabled={cancelling}
              className="border-red-500/40 text-red-400 hover:bg-red-500/10"
            >
              {cancelling ? "取消中…" : "✕ 取消任务"}
            </Button>
          )}
          <StatusBadge status={state.status} />
        </div>
      </div>

      {/* Stage Stepper — driven by this job's real, ordered stage list */}
      <Card>
        <CardContent className="pt-6">
          <Progress value={progress} className="mb-4 h-1.5" />
          {state.stages.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-2">等待流水线启动…</p>
          ) : (
          <div className="flex gap-1">
            {state.stages.map((s, i) => {
              // job_completed carries no `stage` field (there's no single
              // "last" stage to attribute it to), so currentStage never
              // advances past the final real stage's own stage_completed
              // event — i < stageIndex alone would leave the last node
              // stuck rendering as "active" (its ordinal number) forever,
              // even once the job has genuinely finished.
              const done = i < stageIndex || (state.status === "completed" && i === stageIndex);
              const active = s === state.currentStage;
              const waiting = state.status === "awaiting_approval" && s === state.awaitingStage;
              return (
                <div key={s} className="flex-1 flex flex-col items-center gap-1">
                  <div className={`w-6 h-6 rounded-full text-xs flex items-center justify-center font-medium border transition-colors ${
                    waiting  ? "bg-yellow-500 border-yellow-500 text-white" :
                    done     ? "bg-foreground border-foreground text-background" :
                    active   ? "bg-primary border-primary text-primary-foreground" :
                               "border-border text-muted-foreground"
                  }`}>
                    {done ? "✓" : waiting ? "!" : i + 1}
                  </div>
                  <span className={`text-[10px] text-center ${active || waiting ? "text-foreground" : "text-muted-foreground"}`}>
                    {stageLabel(s)}
                  </span>
                </div>
              );
            })}
          </div>
          )}
        </CardContent>
      </Card>

      {/* Any failed approve/reject/retry call — surfaced instead of silently
          doing nothing (e.g. the job's real status moved on server-side, such
          as being marked failed by a server restart while this tab was idle). */}
      {actionError && (
        <Card className="border-red-500/40 bg-red-500/5">
          <CardContent className="pt-4 pb-4">
            <p className="text-sm text-red-400">{actionError}</p>
          </CardContent>
        </Card>
      )}

      {/* Failed state retry */}
      {state.status === "failed" && (
        <Card className="border-red-500/40 bg-red-500/5">
          <CardContent className="pt-4 pb-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-red-400">阶段失败</p>
              <p className="text-xs text-muted-foreground mt-0.5">可以从当前阶段重新触发（已生成的 artifacts 不会清除）</p>
            </div>
            <Button variant="outline" size="sm" onClick={handleRetry} disabled={retrying} className="border-red-500/40 text-red-400 hover:bg-red-500/10">
              {retrying ? "重试中…" : "↺ 重试"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Cancelled state — informational only; unlike the failed card above,
          there's no retry action (the backend only allows retrying "failed"
          jobs, not a deliberately cancelled one). */}
      {state.status === "cancelled" && (
        <Card className="border-border bg-muted/30">
          <CardContent className="pt-4 pb-4">
            <p className="text-sm font-medium text-muted-foreground">任务已取消</p>
          </CardContent>
        </Card>
      )}

      {/* Approval + inline edit panel — keyed on gate identity so a new gate
          (including one that repeats the same stage/gate string) remounts the
          panel pristine instead of needing manual resets here. */}
      {state.awaitingStage && (
        <ApprovalPanel
          key={`${state.awaitingStage}:${state.awaitingGate}:${state.awaitingGateSeq}`}
          jobId={jobId}
          stage={state.awaitingStage}
          gate={state.awaitingGate}
          preview={state.preview}
          onError={setActionError}
          onApproved={() => dispatch({ type: "approve_succeeded" })}
        />
      )}

      {/* Interim preview — the compose stage's own render, playable as soon as
          it exists, well before publish (packaging/distribution metadata)
          finishes. Hidden once the job fully completes (the final card below
          takes over). */}
      {state.previewRenderUrl && !state.renderUrl && (
        <Card className="border-blue-500/40 bg-blue-500/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-base text-blue-400">👁 合成预览（尚未发布）</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <VideoGallery serverBase={SERVER} url={state.previewRenderUrl} urls={state.previewRenderUrls} />
            <p className="text-xs text-muted-foreground">合成阶段已产出，后续阶段可能还会调整</p>
          </CardContent>
        </Card>
      )}

      {/* Final video */}
      {state.renderUrl && (
        <Card className="border-green-500/40 bg-green-500/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-base text-green-400">🎬 成片已就绪</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <VideoGallery serverBase={SERVER} url={state.renderUrl} urls={state.renderUrls} withDownload />
          </CardContent>
        </Card>
      )}

      {/* Event log */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm text-muted-foreground font-medium">实时进度</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-72 px-4 pb-4">
            <div className="space-y-1.5 font-mono text-xs">
              {state.events.map((ev) => <EventRow key={ev.seq} ev={ev} />)}
              {state.events.length === 0 && (
                <p className="text-muted-foreground py-4 text-center">等待任务启动…</p>
              )}
              <div ref={bottomRef} />
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
