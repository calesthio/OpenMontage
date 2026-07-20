"use client";

import { useEffect, useReducer, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";
import {
  StatusBadge, EventRow, stageLabel, VideoGallery, formatRemaining,
  Filmstrip, groupEventsByStage, aggregateEventRows, stageDurations,
  formatElapsed, eventLabel, EVENT_COLOR,
} from "@/components/job-status";
import { SERVER, apiRequest } from "@/lib/api";
import { jobLifecycleReducer, initialJobLifecycleState } from "@/lib/job-lifecycle";
import { useJobEvents } from "@/lib/use-job-events";
import { ApprovalPanel } from "@/components/approval-panel";
import { ArtifactView } from "@/components/artifact-view";
import { useToastManager } from "@/components/ui/toast";

/** Live countdown to the approval gate's hard expiry (the ladder's 7-day
 * window — see stage_runner's APPROVAL_EXPIRY_SECONDS). Ticks locally;
 * expiresAt comes from the awaiting_approval event. */
function ApprovalCountdownChip({ expiresAt }: { expiresAt: number }) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <span
      className="text-xs font-mono border px-2 py-0.5 rounded-full text-yellow-400 border-yellow-500/40 bg-yellow-500/10"
      title="超过此期限仍无人审批,任务将停止(绝不自动批准)"
    >
      ⏳ 审批剩余 {formatRemaining(expiresAt - now)}
    </span>
  );
}

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [state, dispatch] = useReducer(jobLifecycleReducer, initialJobLifecycleState);
  const { reconnect } = useJobEvents(jobId, dispatch);
  const toast = useToastManager();

  // Action state — retry/cancel/approve share this single actionError card.
  const [retrying, setRetrying] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [actionError, setActionError] = useState("");

  // Two-tier event log controls (roadmap 1.5).
  const [rawLog, setRawLog] = useState(false);
  const [stageFilter, setStageFilter] = useState<string | null>(null);

  // On-disk artifacts (roadmap 1.2): refreshed whenever a new artifact is
  // written or a stage completes, so approved artifacts stay inspectable.
  // stale_stages (roadmap 2.4): completed stages whose outputs predate an
  // edited upstream input.
  const [artifacts, setArtifacts] = useState<Record<string, unknown>>({});
  const [staleStages, setStaleStages] = useState<string[]>([]);
  const artifactVersion = state.events.filter(
    (e) => e.type === "artifact_written" || e.type === "stage_completed"
  ).length;
  useEffect(() => {
    apiRequest(`/jobs/${jobId}/artifacts`).then((r) => {
      if (r.ok && r.data?.artifacts) setArtifacts(r.data.artifacts);
      if (r.ok) setStaleStages(r.data?.stale_stages ?? []);
    });
  }, [jobId, artifactVersion, state.status]);

  // Timecode review comments (roadmap 3.5, Frame.io's first primitive):
  // focusing the composer pauses playback; the draft is pre-stamped with
  // the current playhead; pins seek on click; the whole list can be handed
  // to the revise flow verbatim ("0:14 音乐不对" is both a comment and a
  // surgical redo instruction).
  const videoAreaRef = useRef<HTMLDivElement>(null);
  const [comments, setComments] = useState<Array<{ t: number; text: string }>>([]);
  const [commentDraft, setCommentDraft] = useState("");
  const fmtTimecode = (t: number) =>
    `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
  function onCommentFocus() {
    const videos = videoAreaRef.current?.querySelectorAll("video");
    videos?.forEach((v) => v.pause());
    if (!commentDraft) {
      const v = videoAreaRef.current?.querySelector("video");
      setCommentDraft(`${fmtTimecode(v?.currentTime ?? 0)} `);
    }
  }
  function addComment() {
    const text = commentDraft.trim();
    if (!text) return;
    const m = text.match(/^(\d+):(\d{2})/);
    const t = m ? Number(m[1]) * 60 + Number(m[2]) : 0;
    setComments((prev) => [...prev, { t, text }]);
    setCommentDraft("");
  }
  function seekTo(t: number) {
    const v = videoAreaRef.current?.querySelector("video");
    if (v) {
      v.currentTime = t;
      v.pause();
    }
  }

  // Revise (roadmap 2.2): re-open a finished job at a chosen stage.
  const router = useRouter();
  const [reviseStage, setReviseStage] = useState("");
  const [reviseFeedback, setReviseFeedback] = useState("");
  const [revising, setRevising] = useState(false);
  async function handleRevise(stage: string, mode: "cascade" | "single", feedback = "") {
    setRevising(true);
    setActionError("");
    const res = await apiRequest(`/jobs/${jobId}/revise`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage, mode, feedback }),
    });
    setRevising(false);
    if (res.ok) {
      router.push(`/dashboard/jobs/${res.data.job_id}`);
    } else {
      setActionError(res.detail);
    }
  }

  // Honest elapsed clock (roadmap 1.6): ticks while the job is live.
  const [nowSec, setNowSec] = useState(() => Date.now() / 1000);
  const isLive = state.status === "running" || state.status === "awaiting_approval" || state.status === "queued";
  useEffect(() => {
    if (!isLive) return;
    const t = setInterval(() => setNowSec(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, [isLive]);

  const bottomRef = useRef<HTMLDivElement>(null);

  // Toast notifications for the approval ladder: one when a gate opens, one
  // per approval_reminder ping. Only for FRESH events — the SSE stream
  // replays history on reload, and toasting week-old reminders would bury
  // the user; ts-recency is the filter (30s covers reconnect jitter).
  const lastToastedSeq = useRef(-1);
  useEffect(() => {
    const ev = state.events[state.events.length - 1];
    if (!ev || ev.seq <= lastToastedSeq.current) return;
    if (ev.type !== "awaiting_approval" && ev.type !== "approval_reminder") return;
    if (Date.now() / 1000 - ev.ts > 30) return;
    lastToastedSeq.current = ev.seq;
    toast.add({
      type: "warning",
      title: ev.type === "awaiting_approval" ? "任务等待你的审批" : "审批提醒",
      description: `${stageLabel(ev.stage)}阶段${ev.type === "awaiting_approval" ? "已暂停,等待你的决定" : "仍在等待你的决定"}`,
    });
  }, [state.events, toast]);

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
  const isTerminal = state.status === "completed" || state.status === "failed" || state.status === "cancelled";

  // Honest progress signals (roadmap 1.6).
  const startedTs = state.events.find((e) => e.type === "job_started")?.ts ?? null;
  const terminalTs = [...state.events].reverse().find(
    (e) => e.type === "job_completed" || e.type === "job_failed" || e.type === "job_cancelled"
  )?.ts ?? null;
  const elapsed = startedTs != null ? (terminalTs ?? nowSec) - startedTs : null;
  const durations = stageDurations(state.events);
  // "镜头 4/12" during the assets stage: scene_plan gives the denominator,
  // visual asset_ready events in this stage the numerator.
  const scenePlanScenes = ((artifacts.scene_plan as { scenes?: unknown[] } | undefined)?.scenes ?? []).length;
  const assetsThisStage = state.assets.filter(
    (a) => a.stage === state.currentStage &&
      (a.kind === "video_generation" || a.kind === "image_generation")
  ).length;
  const showSceneProgress = state.currentStage === "assets" && scenePlanScenes > 0 && state.status === "running";

  return (
    <div className="p-8 max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight">{state.projectName ?? "加载中…"}</h1>
          <p className="text-muted-foreground text-sm mt-0.5 font-mono">{jobId}</p>
        </div>
        <div className="flex items-center gap-3">
          {elapsed != null && (
            <span
              className="text-xs font-mono border px-2 py-0.5 rounded-full text-muted-foreground border-border"
              title={terminalTs ? "任务总耗时" : "已运行时长"}
            >
              ⏱ {formatElapsed(elapsed)}
            </span>
          )}
          {state.status === "awaiting_approval" && state.approvalExpiresAt != null && (
            <ApprovalCountdownChip expiresAt={state.approvalExpiresAt} />
          )}
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
              disabled={cancelling || state.cancelRequested}
              className="border-red-500/40 text-red-400 hover:bg-red-500/10"
            >
              {cancelling || state.cancelRequested ? "取消中…" : "✕ 取消任务"}
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
                <button
                  key={s}
                  type="button"
                  onClick={() => setStageFilter(stageFilter === s ? null : s)}
                  title={`点击筛选 ${stageLabel(s)} 阶段的日志`}
                  className={`flex-1 flex flex-col items-center gap-1 cursor-pointer bg-transparent border-0 p-0 ${
                    stageFilter === s ? "opacity-100" : stageFilter ? "opacity-50" : ""
                  }`}
                >
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
                  {/* Completed stages show what they actually took (roadmap 1.6). */}
                  <span className="text-[9px] text-muted-foreground/70 font-mono h-3">
                    {durations[s] != null ? formatElapsed(durations[s]) : ""}
                  </span>
                </button>
              );
            })}
          </div>
          )}
          {showSceneProgress && (
            <p className="text-xs text-muted-foreground text-center mt-2" data-testid="scene-progress">
              镜头素材 {Math.min(assetsThisStage, scenePlanScenes)}/{scenePlanScenes}
            </p>
          )}
        </CardContent>
      </Card>

      {/* The agent's latest narration — a live "正在做什么" line instead of
          log chatter (roadmap 1.5). */}
      {state.agentText && isLive && (
        <p className="text-sm text-muted-foreground italic px-1" data-testid="agent-live-line">
          🤖 {state.agentText}
        </p>
      )}

      {/* Live filmstrip (roadmap 1.1): thumbnails pop in per asset_ready. */}
      {state.assets.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm text-muted-foreground font-medium">
              素材胶片条 · {state.assets.length}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Filmstrip serverBase={SERVER} assets={state.assets} />
          </CardContent>
        </Card>
      )}

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
          previewArtifact={state.previewArtifact}
          serverBase={SERVER}
          projectName={state.projectName}
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

      {/* Staleness (roadmap 2.4): a completed stage's output predates an
          edited upstream input — offer targeted re-runs. */}
      {isTerminal && staleStages.length > 0 && (
        <Card className="border-orange-500/40 bg-orange-500/5" data-testid="stale-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-base text-orange-400">⟳ 有阶段已过期</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs text-muted-foreground">
              上游产物被修改后,以下阶段的输出已经过期。可只重做该阶段,或连同其后所有阶段一起重做(未变化的素材会自动复用,不重复计费)。
            </p>
            {staleStages.map((s) => (
              <div key={s} className="flex items-center gap-2">
                <span className="text-sm flex-1">{stageLabel(s)}</span>
                <Button size="sm" variant="outline" disabled={revising}
                        onClick={() => handleRevise(s, "single")}>
                  仅重做此阶段
                </Button>
                <Button size="sm" variant="outline" disabled={revising}
                        onClick={() => handleRevise(s, "cascade")}>
                  重做此阶段及后续
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Revise (roadmap 2.2): success is not a dead end — re-open the run
          at any stage with feedback; a new generation begins. */}
      {isTerminal && state.stages.length > 0 && (
        <Card data-testid="revise-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm text-muted-foreground font-medium">↻ 修订(从某一阶段重新打开)</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col sm:flex-row gap-2">
            <select
              className="bg-muted/40 border border-border rounded px-2 py-1.5 text-sm"
              value={reviseStage}
              onChange={(e) => setReviseStage(e.target.value)}
              aria-label="选择要重做的阶段"
            >
              <option value="">选择阶段…</option>
              {state.stages.map((s) => (
                <option key={s} value={s}>{stageLabel(s)}</option>
              ))}
            </select>
            <input
              className="flex-1 bg-muted/40 border border-border rounded px-2 py-1.5 text-sm"
              placeholder="想改什么?例如:0:14 的音乐不对,换更克制的"
              value={reviseFeedback}
              onChange={(e) => setReviseFeedback(e.target.value)}
            />
            <Button
              size="sm"
              disabled={!reviseStage || revising}
              onClick={() => handleRevise(reviseStage, "cascade", reviseFeedback)}
            >
              {revising ? "创建中…" : "重新打开"}
            </Button>
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
            <div ref={videoAreaRef}>
              <VideoGallery serverBase={SERVER} url={state.renderUrl} urls={state.renderUrls} withDownload />
            </div>
            {/* Timecode review (roadmap 3.5) */}
            <div className="space-y-2 pt-1" data-testid="timecode-review">
              {comments.length > 0 && (
                <ul className="space-y-1">
                  {comments.map((c, i) => (
                    <li key={i} className="text-sm flex items-baseline gap-2">
                      <button
                        type="button"
                        onClick={() => seekTo(c.t)}
                        className="text-xs font-mono text-blue-400 hover:underline shrink-0"
                        title="跳转到该时间点"
                      >
                        {fmtTimecode(c.t)}
                      </button>
                      <span className="text-foreground/85">{c.text.replace(/^\d+:\d{2}\s*/, "")}</span>
                    </li>
                  ))}
                </ul>
              )}
              <div className="flex gap-2">
                <label className="sr-only" htmlFor="timecode-comment">时间码评论</label>
                <input
                  id="timecode-comment"
                  className="flex-1 bg-muted/40 border border-border rounded px-2 py-1.5 text-sm"
                  placeholder="点击输入即暂停,并自动带上当前时间码…"
                  value={commentDraft}
                  onFocus={onCommentFocus}
                  onChange={(e) => setCommentDraft(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") addComment(); }}
                />
                <Button size="sm" variant="outline" onClick={addComment} disabled={!commentDraft.trim()}>
                  钉住评论
                </Button>
                {comments.length > 0 && (
                  <Button
                    size="sm"
                    variant="outline"
                    title="把全部评论作为修订反馈填入下方的重新打开表单"
                    onClick={() => {
                      setReviseFeedback(comments.map((c) => c.text).join(";"));
                      setReviseStage((s) => s || "edit");
                    }}
                  >
                    填入修订 ↓
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Artifacts browser (roadmap 1.2): approved artifacts no longer
          vanish from the UI — everything on disk stays inspectable. */}
      {Object.keys(artifacts).length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm text-muted-foreground font-medium">已生成产物</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {Object.entries(artifacts).map(([name, value]) => (
              <details key={name} className="border border-border rounded-md px-3 py-2">
                <summary className="text-sm cursor-pointer select-none">{name}</summary>
                <div className="mt-2">
                  <ArtifactView name={name} value={value} serverBase={SERVER} projectName={state.projectName} />
                </div>
              </details>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Two-tier event log (roadmap 1.5): stage sections with one-line
          summaries; consecutive same-tool events collapse ×N; the raw flat
          log stays one toggle away. */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm text-muted-foreground font-medium">实时进度</CardTitle>
            <div className="flex items-center gap-3">
              {stageFilter && (
                <button
                  type="button"
                  className="text-xs text-yellow-400 hover:underline"
                  onClick={() => setStageFilter(null)}
                >
                  筛选: {stageLabel(stageFilter)} ✕
                </button>
              )}
              <label className="text-xs text-muted-foreground flex items-center gap-1 cursor-pointer">
                <input
                  type="checkbox"
                  checked={rawLog}
                  onChange={(e) => setRawLog(e.target.checked)}
                />
                原始日志
              </label>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-96 px-4 pb-4">
            {rawLog ? (
              <div className="space-y-1.5 font-mono text-xs">
                {state.events
                  .filter((ev) => !stageFilter || ev.stage === stageFilter)
                  .map((ev) => <EventRow key={ev.seq} ev={ev} />)}
              </div>
            ) : (
              <div className="space-y-2">
                {groupEventsByStage(state.events)
                  .filter((g) => !stageFilter || g.stage === stageFilter)
                  .map((g, gi, arr) => (
                    <details
                      key={`${g.stage}:${g.events[0]?.seq}`}
                      open={gi === arr.length - 1}
                      className="border border-border/60 rounded-md px-3 py-1.5"
                    >
                      <summary className="text-xs cursor-pointer select-none flex flex-wrap gap-x-2 items-baseline">
                        <span className="font-medium text-foreground/90">
                          {g.stage ? stageLabel(g.stage) : "系统"}
                        </span>
                        <span className="text-muted-foreground">
                          {[
                            g.toolCalls > 0 ? `${g.toolCalls} 次工具调用` : null,
                            g.assetCount > 0 ? `${g.assetCount} 个素材` : null,
                            g.costCny > 0 ? `¥${g.costCny.toFixed(2)}` : null,
                            g.endTs > g.startTs ? formatElapsed(g.endTs - g.startTs) : null,
                          ].filter(Boolean).join(" · ")}
                        </span>
                      </summary>
                      <div className="space-y-1 font-mono text-xs mt-1.5 pb-1">
                        {aggregateEventRows(g.events).map(({ ev, count }) => (
                          <div key={ev.seq} className="flex gap-2 items-start">
                            <span className="text-muted-foreground/50 shrink-0">
                              {new Date(ev.ts * 1000).toLocaleTimeString("zh-CN", { hour12: false })}
                            </span>
                            <span className={`shrink-0 ${EVENT_COLOR[ev.type] ?? "text-muted-foreground"}`}>
                              [{ev.type}]
                            </span>
                            <span className="text-foreground/70 break-all">
                              {eventLabel(ev)}
                              {count > 1 && <span className="text-muted-foreground"> ×{count}</span>}
                            </span>
                          </div>
                        ))}
                      </div>
                    </details>
                  ))}
              </div>
            )}
            {state.events.length === 0 && (
              <p className="text-muted-foreground py-4 text-center text-xs">等待任务启动…</p>
            )}
            <div ref={bottomRef} />
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
