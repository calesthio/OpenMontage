"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";
import { StatusBadge, EventRow, stageLabel, mediaUrl, type SseEvent } from "@/components/job-status";

const SERVER = process.env.NEXT_PUBLIC_SERVER_URL ?? "http://localhost:8000";

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [projectName, setProjectName] = useState<string | null>(null);
  const [events, setEvents] = useState<SseEvent[]>([]);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  // The pipeline's real, ordered stage list — sent by the backend on
  // job_started (server/app/runner/stage_runner.py "stages": [...]). Different
  // pipelines have different stage counts/names (5 for documentary-montage, 9
  // for screen-demo, etc.), so this must come from the job itself, not a
  // hardcoded constant shaped after one pipeline.
  const [stages, setStages] = useState<string[]>([]);
  const [status, setStatus] = useState<string>("queued");
  const [awaitingStage, setAwaitingStage] = useState<string | null>(null);
  // Distinguishes which kind of gate is pending: undefined/"stage" for the
  // ordinary end-of-stage artifact review, "budget" for an overspend
  // ceiling, "sample_preview" for a mid-stage checkpoint (e.g.
  // asset-director.md's "generate one sample, confirm before batching").
  // Each renders differently below — the same `awaiting_approval` event
  // type carries a differently-shaped `preview` depending on this field.
  const [awaitingGate, setAwaitingGate] = useState<string | null>(null);
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [renderUrl, setRenderUrl] = useState<string | null>(null);
  // Interim preview: the compose stage's own render, playable as soon as it's
  // produced — well before publish (packaging/distribution metadata) finishes.
  // Distinct from renderUrl, which is only set once the whole job completes.
  const [previewRenderUrl, setPreviewRenderUrl] = useState<string | null>(null);
  // A/B variant job only: sibling plural dicts alongside renderUrl/
  // previewRenderUrl, keyed by a short model-derived slug (e.g. "ltx-2-3").
  // Null/empty for a normal (non-variant) job — the singular fields above
  // remain the source of truth for that case.
  const [renderUrls, setRenderUrls] = useState<Record<string, string> | null>(null);
  const [previewRenderUrls, setPreviewRenderUrls] = useState<Record<string, string> | null>(null);
  const [costCny, setCostCny] = useState<number>(0);
  const [budgetCny, setBudgetCny] = useState<number | null>(null);

  // Approval state
  const [feedback, setFeedback] = useState("");
  const [approving, setApproving] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [actionError, setActionError] = useState("");

  // Inline edit state
  const [editMode, setEditMode] = useState(false);
  const [editJson, setEditJson] = useState("");
  const [editError, setEditError] = useState("");
  const [saving, setSaving] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const lastSeqRef = useRef(-1);
  const lastEventTypeRef = useRef<string | null>(null); // type of the most recently processed event
  const doneRef = useRef(false);        // job reached a terminal state
  const cancelledRef = useRef(false);   // component unmounted — stop reconnecting
  const connectRef = useRef<(() => EventSource | null) | null>(null);
  const esRef = useRef<EventSource | null>(null);   // the currently live connection, if any

  // Seed real state on mount via REST — the SSE stream alone only carries
  // events from lastEventId onward; the page title (and cost/status on a
  // fresh load) shouldn't have to wait for the full event replay to resolve.
  useEffect(() => {
    fetch(`${SERVER}/jobs/${jobId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((job) => {
        if (!job) return;
        if (job.project_name) setProjectName(job.project_name);
        if (job.render_url) setRenderUrl(job.render_url);
        if (job.preview_render_url) setPreviewRenderUrl(job.preview_render_url);
        if (job.render_urls) setRenderUrls(job.render_urls);
        if (job.preview_render_urls) setPreviewRenderUrls(job.preview_render_urls);
      })
      .catch(() => {});
  }, [jobId]);

  useEffect(() => {
    cancelledRef.current = false;
    const connect = () => {
      if (cancelledRef.current) return null;
      const url = `${SERVER}/jobs/${jobId}/events?lastEventId=${lastSeqRef.current}`;
      const es = new EventSource(url);
      esRef.current = es;
      es.onmessage = (e) => {
        const ev: SseEvent = JSON.parse(e.data);
        lastSeqRef.current = ev.seq;
        lastEventTypeRef.current = ev.type;
        setEvents((prev) => [...prev, ev]);
        if (ev.stage) setCurrentStage(ev.stage);
        if (ev.type === "job_started") {
          setStatus("running");
          if (ev.stages?.length) setStages(ev.stages);
        }
        if (ev.type === "stage_started") setStatus("running");
        if (ev.type === "awaiting_approval") {
          setStatus("awaiting_approval");
          setAwaitingStage(ev.stage ?? null);
          setAwaitingGate(ev.gate ?? null);
          const p = ev.preview as Record<string, unknown> | null;
          setPreview(p ?? null);
          setEditJson(p ? JSON.stringify(p, null, 2) : "");
          setEditMode(false);
          setEditError("");
        }
        if (ev.type === "stage_approved" || ev.type === "stage_rejected") {
          setAwaitingStage(null);
          setAwaitingGate(null);
          setStatus("running");
          setEditMode(false);
        }
        if (ev.type === "cost_updated" && ev.cost_cny != null) {
          setCostCny(ev.cost_cny);
          if (ev.budget_cny != null) setBudgetCny(ev.budget_cny);
        }
        if (ev.type === "preview_ready") {
          setPreviewRenderUrl(ev.render_url ?? null);
          setPreviewRenderUrls(ev.render_urls ?? null);
        }
        if (ev.type === "job_completed") {
          setStatus("completed");
          setRenderUrl(ev.render_url ?? null);
          setRenderUrls(ev.render_urls ?? null);
        }
        if (ev.type === "job_failed") {
          // Confirmed live: the budget gate's reject/timeout path (and any
          // other gate) jumps straight to job_failed with no intervening
          // stage_approved/stage_rejected — without this, the approval
          // panel stayed on screen showing dead Approve/Reject buttons
          // (POSTing to them 404s once the job is no longer
          // awaiting_approval) side-by-side with the failed/retry card.
          setStatus("failed");
          setAwaitingStage(null);
          setAwaitingGate(null);
        }
      };
      es.onerror = () => {
        es.close();
        // A replay (or any reconnect spanning more than one retry cycle) can
        // contain an OLD job_failed from an earlier, since-superseded attempt
        // followed by many more events from a later retry that finished
        // differently (even a real job_completed) — see the matching comment
        // in server/app/routers/events.py. So don't treat job_failed/
        // job_completed as terminal at the moment they're seen; only stop
        // reconnecting once the connection actually ends on one of them,
        // which is exactly when the backend intentionally closed the stream.
        const endedOnTerminalEvent =
          lastEventTypeRef.current === "job_completed" || lastEventTypeRef.current === "job_failed";
        if (endedOnTerminalEvent) {
          doneRef.current = true;
          return;
        }
        // Reconnect only while the job is live and the view is still mounted.
        // (Uses refs, not the captured `status`, which would be stale here.)
        if (!doneRef.current && !cancelledRef.current) {
          setTimeout(() => { if (!cancelledRef.current && !doneRef.current) connect(); }, 2000);
        }
      };
      return es;
    };
    connectRef.current = connect;
    connect();
    return () => { cancelledRef.current = true; esRef.current?.close(); };
  }, [jobId]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [events]);

  async function handleRetry() {
    setRetrying(true);
    setActionError("");
    const res = await fetch(`${SERVER}/jobs/${jobId}/retry`, { method: "POST" });
    setRetrying(false);
    if (res.ok) {
      setStatus("queued");
      // The previous EventSource already closed (the backend ended that
      // stream once it drained to the earlier terminal event) and nothing
      // was scheduled to reconnect it, so open a fresh one from where we
      // left off rather than just flipping a flag nothing reacts to.
      doneRef.current = false;
      connectRef.current?.();
    } else {
      const body = await res.json().catch(() => ({}));
      setActionError(body.detail ?? `重试失败 (HTTP ${res.status})`);
    }
  }

  async function handleApproval(action: "approve" | "reject") {
    setApproving(true);
    setActionError("");
    const res = await fetch(`${SERVER}/jobs/${jobId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, feedback }),
    });
    setApproving(false);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setActionError(
        body.detail ?? `操作失败 (HTTP ${res.status}) — 任务状态可能已变化，请刷新页面查看最新状态`
      );
      return;
    }
    setFeedback("");
    if (action === "approve") setAwaitingStage(null);
  }

  async function handleSaveEdit() {
    setEditError("");
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(editJson);
    } catch {
      setEditError("JSON 格式错误，请检查");
      return;
    }
    setSaving(true);
    // Persist edited artifact via the save-artifact endpoint
    const res = await fetch(`${SERVER}/jobs/${jobId}/artifact`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage: awaitingStage, content: parsed }),
    });
    setSaving(false);
    if (res.ok) {
      setPreview(parsed);
      setEditMode(false);
    } else {
      setEditError("保存失败，请重试");
    }
  }

  const stageIndex = currentStage ? stages.indexOf(currentStage) : -1;
  const progress = stageIndex >= 0 && stages.length > 0
    ? Math.round(((stageIndex + 1) / stages.length) * 100)
    : 0;
  const isBudgetGate = awaitingGate === "budget";
  const isSamplePreviewGate = awaitingGate === "sample_preview";
  const samplePreview = isSamplePreviewGate
    ? (preview as { text?: string; iteration?: number; max_iterations?: number } | null)
    : null;

  return (
    <div className="p-8 max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight">{projectName ?? "加载中…"}</h1>
          <p className="text-muted-foreground text-sm mt-0.5 font-mono">{jobId}</p>
        </div>
        <div className="flex items-center gap-3">
          {(costCny > 0 || budgetCny != null) && (
            <span
              className={`text-xs font-mono border px-2 py-0.5 rounded-full ${
                budgetCny != null && costCny > budgetCny
                  ? "text-red-400 border-red-500/40 bg-red-500/10"
                  : "text-muted-foreground border-border"
              }`}
              title="工具调用累计成本(CNY)"
            >
              ¥{costCny.toFixed(4)}
              {budgetCny != null && ` / ¥${budgetCny.toFixed(2)} 预算`}
            </span>
          )}
          <StatusBadge status={status} />
        </div>
      </div>

      {/* Stage Stepper — driven by this job's real, ordered stage list */}
      <Card>
        <CardContent className="pt-6">
          <Progress value={progress} className="mb-4 h-1.5" />
          {stages.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-2">等待流水线启动…</p>
          ) : (
          <div className="flex gap-1">
            {stages.map((s, i) => {
              // job_completed carries no `stage` field (there's no single
              // "last" stage to attribute it to), so currentStage never
              // advances past the final real stage's own stage_completed
              // event — i < stageIndex alone would leave the last node
              // stuck rendering as "active" (its ordinal number) forever,
              // even once the job has genuinely finished.
              const done = i < stageIndex || (status === "completed" && i === stageIndex);
              const active = s === currentStage;
              const waiting = status === "awaiting_approval" && s === awaitingStage;
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
      {status === "failed" && (
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

      {/* Approval + inline edit panel */}
      {awaitingStage && (
        <Card className="border-yellow-500/40 bg-yellow-500/5">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <span className="text-yellow-400">⏸</span>
                {isBudgetGate
                  ? "预算超支 — 需要你确认是否继续"
                  : isSamplePreviewGate
                  ? `${stageLabel(awaitingStage)} — AI 请求确认样品${samplePreview?.max_iterations ? `（第 ${samplePreview.iteration}/${samplePreview.max_iterations} 轮）` : ""}`
                  : `${stageLabel(awaitingStage)} — 等待你的审批`}
              </CardTitle>
              {preview && !isBudgetGate && !isSamplePreviewGate && (
                <Button
                  size="sm"
                  variant="outline"
                  className="text-xs"
                  onClick={() => { setEditMode(!editMode); setEditError(""); }}
                >
                  {editMode ? "取消编辑" : "✏ 直接编辑"}
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Sample-preview gate: the agent's own message, not a raw
                artifact JSON — there's nothing to inline-edit yet, the
                stage hasn't produced its artifact. */}
            {isSamplePreviewGate && samplePreview?.text && (
              <p className="text-sm text-foreground/90 bg-muted/50 rounded p-3 whitespace-pre-wrap">
                {samplePreview.text}
              </p>
            )}
            {/* Preview / editor (ordinary stage-boundary gate only) */}
            {preview && !editMode && !isSamplePreviewGate && (
              <pre className="text-xs bg-muted/50 rounded p-3 overflow-auto max-h-64 whitespace-pre-wrap">
                {JSON.stringify(preview, null, 2)}
              </pre>
            )}
            {editMode && (
              <div className="space-y-2">
                <Textarea
                  className="font-mono text-xs h-64 resize-none"
                  value={editJson}
                  onChange={(e) => setEditJson(e.target.value)}
                />
                {editError && <p className="text-xs text-destructive">{editError}</p>}
                <div className="flex gap-2">
                  <Button size="sm" onClick={handleSaveEdit} disabled={saving}>
                    {saving ? "保存中…" : "保存修改"}
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => { setEditMode(false); setEditJson(JSON.stringify(preview, null, 2)); }}>
                    还原
                  </Button>
                </div>
              </div>
            )}

            {/* Feedback textarea — not shown for the budget gate */}
            {!editMode && !isBudgetGate && (
              <Textarea
                placeholder="（可选）写下反馈，让 AI 修改后重来…"
                rows={2}
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
              />
            )}

            {/* Action buttons */}
            {!editMode && (
              <div className="flex gap-3">
                <Button onClick={() => handleApproval("approve")} disabled={approving} className="flex-1">
                  {isBudgetGate ? "✓ 批准超支，继续生产" : "✓ 批准，继续生产"}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => handleApproval("reject")}
                  disabled={approving || (!isBudgetGate && !feedback)}
                  className="flex-1"
                >
                  {isBudgetGate ? "⛔ 终止任务" : "↩ 打回重做"}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Interim preview — the compose stage's own render, playable as soon as
          it exists, well before publish (packaging/distribution metadata)
          finishes. Hidden once the job fully completes (the final card below
          takes over). */}
      {previewRenderUrl && !renderUrl && (
        <Card className="border-blue-500/40 bg-blue-500/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-base text-blue-400">👁 合成预览（尚未发布）</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            {previewRenderUrls && Object.keys(previewRenderUrls).length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {Object.entries(previewRenderUrls).map(([slug, url]) => (
                  <div key={slug} className="space-y-1">
                    <video src={mediaUrl(SERVER, url) ?? undefined} controls className="w-full rounded-lg bg-black aspect-video" />
                    <span className="text-xs text-muted-foreground block">版本: {slug}</span>
                  </div>
                ))}
              </div>
            ) : (
              <video src={mediaUrl(SERVER, previewRenderUrl) ?? undefined} controls className="w-full rounded-lg bg-black aspect-video" />
            )}
            <p className="text-xs text-muted-foreground">合成阶段已产出，后续阶段可能还会调整</p>
          </CardContent>
        </Card>
      )}

      {/* Final video */}
      {renderUrl && (
        <Card className="border-green-500/40 bg-green-500/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-base text-green-400">🎬 成片已就绪</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {renderUrls && Object.keys(renderUrls).length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {Object.entries(renderUrls).map(([slug, url]) => (
                  <div key={slug} className="space-y-2">
                    <video src={mediaUrl(SERVER, url) ?? undefined} controls className="w-full rounded-lg bg-black aspect-video" />
                    <span className="text-xs text-muted-foreground block">版本: {slug}</span>
                    <a href={mediaUrl(SERVER, url) ?? undefined} download>
                      <Button variant="outline" className="w-full">下载 MP4</Button>
                    </a>
                  </div>
                ))}
              </div>
            ) : (
              <>
                <video src={mediaUrl(SERVER, renderUrl) ?? undefined} controls className="w-full rounded-lg bg-black aspect-video" />
                <a href={mediaUrl(SERVER, renderUrl) ?? undefined} download>
                  <Button variant="outline" className="w-full">下载 MP4</Button>
                </a>
              </>
            )}
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
              {events.map((ev) => <EventRow key={ev.seq} ev={ev} />)}
              {events.length === 0 && (
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

