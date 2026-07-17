"use client";

// The three gate variants (ordinary stage-boundary / budget / sample_preview)
// plus the inline artifact editor, extracted out of the job detail page.
// This component owns its own edit/feedback state and is meant to be
// remounted by the parent via a `key` derived from gate identity (stage +
// gate + the awaiting_approval event's seq — see JobLifecycleState.
// awaitingGateSeq) whenever a new gate arrives. That remount is what resets
// editMode/editJson/editError/feedback "for free" — the SSE handler used to
// reset these by hand on every new awaiting_approval event; deleting those
// manual resets (rather than moving them) is the point of this extraction.

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { stageLabel } from "@/components/job-status";
import { apiRequest } from "@/lib/api";

type SamplePreview = { text?: string; iteration?: number; max_iterations?: number };
type RevisionsExhaustedPreview = { text?: string; revisions_used?: number; max_revisions?: number };

export function ApprovalPanel({
  jobId,
  stage,
  gate,
  preview,
  onError,
  onApproved,
}: {
  jobId: string;
  stage: string;
  gate: string | null;
  preview: Record<string, unknown> | null;
  /** Bubbles an approve/reject/save-edit failure up to the page's shared
   * actionError card (also used by the retry/cancel actions). Pass "" to
   * clear it before a new request, matching the page's previous behavior. */
  onError: (detail: string) => void;
  /** Signals a successful approve so the page can clear awaitingStage/
   * awaitingGate immediately instead of waiting on the SSE round-trip
   * (stage_approved) — see jobLifecycleReducer's "approve_succeeded". */
  onApproved: () => void;
}) {
  // Approval state
  const [feedback, setFeedback] = useState("");
  const [approving, setApproving] = useState(false);

  // Inline edit state. currentPreview starts from the `preview` prop but can
  // be overridden by a successful save-edit — there is no new gate event on
  // save (you're still resolving the SAME gate), so this can't rely on the
  // remount-on-new-gate trick the way editMode/editJson/editError do.
  const [currentPreview, setCurrentPreview] = useState(preview);
  const [editMode, setEditMode] = useState(false);
  const [editJson, setEditJson] = useState(preview ? JSON.stringify(preview, null, 2) : "");
  const [editError, setEditError] = useState("");
  const [saving, setSaving] = useState(false);

  const isBudgetGate = gate === "budget";
  const isSamplePreviewGate = gate === "sample_preview";
  // Revision budget exhausted (orchestration.max_revisions_per_stage):
  // approve = accept the latest artifact as-is; reject = stop the job.
  // Reject needs no feedback here (nothing will be regenerated), same as
  // the budget gate.
  const isRevisionsExhaustedGate = gate === "revisions_exhausted";
  const samplePreview = isSamplePreviewGate ? (currentPreview as SamplePreview | null) : null;
  const revisionsPreview = isRevisionsExhaustedGate
    ? (currentPreview as RevisionsExhaustedPreview | null)
    : null;

  async function handleApproval(action: "approve" | "reject") {
    setApproving(true);
    onError("");
    const res = await apiRequest(`/jobs/${jobId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, feedback }),
    });
    if (!res.ok) {
      // A non-ok here usually means the job's real status moved on
      // server-side while this tab was idle (gate already resolved, job
      // failed, etc.) — the backend's detail explains which.
      onError(res.detail);
      setApproving(false);
      return;
    }
    setFeedback("");
    if (action === "approve") onApproved();
    setApproving(false);
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
    const res = await apiRequest(`/jobs/${jobId}/artifact`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage, content: parsed }),
    });
    if (res.ok) {
      setCurrentPreview(parsed);
      setEditMode(false);
    } else {
      // Surface the backend's actual reason (e.g. the artifact-save
      // endpoint's 400 for a stage name that isn't one of this job's
      // real pipeline stages) instead of a generic message that hides
      // why the save silently did nothing.
      setEditError(res.detail);
    }
    setSaving(false);
  }

  return (
    <Card className="border-yellow-500/40 bg-yellow-500/5">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <span className="text-yellow-400">⏸</span>
            {isBudgetGate
              ? "预算超支 — 需要你确认是否继续"
              : isSamplePreviewGate
              ? `${stageLabel(stage)} — AI 请求确认样品${samplePreview?.max_iterations ? `（第 ${samplePreview.iteration}/${samplePreview.max_iterations} 轮）` : ""}`
              : isRevisionsExhaustedGate
              ? `${stageLabel(stage)} — 修订次数已用尽${revisionsPreview?.max_revisions ? `（${revisionsPreview.revisions_used}/${revisionsPreview.max_revisions}）` : ""}`
              : `${stageLabel(stage)} — 等待你的审批`}
          </CardTitle>
          {currentPreview && !isBudgetGate && !isSamplePreviewGate && !isRevisionsExhaustedGate && (
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
        {/* Revisions-exhausted gate: an explanation, not an artifact — the
            latest artifact was already reviewed at the previous gate. */}
        {isRevisionsExhaustedGate && (
          <p className="text-sm text-foreground/90 bg-muted/50 rounded p-3 whitespace-pre-wrap">
            该阶段的修订次数已达上限。批准将采用当前版本继续生产;打回将停止整个任务。
          </p>
        )}
        {/* Preview / editor (ordinary stage-boundary gate only) */}
        {currentPreview && !editMode && !isSamplePreviewGate && !isRevisionsExhaustedGate && (
          <pre className="text-xs bg-muted/50 rounded p-3 overflow-auto max-h-64 whitespace-pre-wrap">
            {JSON.stringify(currentPreview, null, 2)}
          </pre>
        )}
        {editMode && (
          <div className="space-y-2">
            <Textarea
              className="font-mono text-xs h-64 resize-none"
              value={editJson}
              onChange={(e) => setEditJson(e.target.value)}
            />
            {/* Same red border/bg/text treatment as the top-level
                actionError card used for approve/retry failures — the
                save-artifact endpoint's non-200 response (e.g. a stage
                name rejected by the backend's pipeline-stage check)
                must not disappear silently; the user needs to see the
                save didn't actually take effect. */}
            {editError && (
              <div className="text-sm text-red-400 border border-red-500/40 bg-red-500/10 rounded px-3 py-2">
                {editError}
              </div>
            )}
            <div className="flex gap-2">
              <Button size="sm" onClick={handleSaveEdit} disabled={saving}>
                {saving ? "保存中…" : "保存修改"}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => { setEditMode(false); setEditJson(JSON.stringify(currentPreview, null, 2)); }}
              >
                还原
              </Button>
            </div>
          </div>
        )}

        {/* Feedback textarea — not shown for the budget / revisions-
            exhausted gates (neither path regenerates on reject) */}
        {!editMode && !isBudgetGate && !isRevisionsExhaustedGate && (
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
              {isBudgetGate
                ? "✓ 批准超支，继续生产"
                : isRevisionsExhaustedGate
                ? "✓ 接受当前版本，继续生产"
                : "✓ 批准，继续生产"}
            </Button>
            <Button
              variant="outline"
              onClick={() => handleApproval("reject")}
              disabled={approving || (!isBudgetGate && !isRevisionsExhaustedGate && !feedback)}
              className="flex-1"
            >
              {isBudgetGate || isRevisionsExhaustedGate ? "⛔ 终止任务" : "↩ 打回重做"}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
