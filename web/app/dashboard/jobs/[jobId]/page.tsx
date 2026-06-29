"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";

const STAGES = ["research", "proposal", "script", "scene_plan", "assets", "edit", "compose", "publish"];
const STAGE_LABELS: Record<string, string> = {
  research: "调研", proposal: "提案", script: "脚本",
  scene_plan: "分镜", assets: "素材", edit: "剪辑",
  compose: "合成", publish: "发布",
};

type SseEvent = {
  seq: number;
  type: string;
  ts: number;
  stage?: string;
  text?: string;
  tool?: string;
  summary?: string;
  artifact?: string;
  preview?: unknown;
  render_url?: string;
  message?: string;
  feedback?: string;
};

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [events, setEvents] = useState<SseEvent[]>([]);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("queued");
  const [awaitingStage, setAwaitingStage] = useState<string | null>(null);
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [renderUrl, setRenderUrl] = useState<string | null>(null);
  const [feedback, setFeedback] = useState("");
  const [approving, setApproving] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const lastSeqRef = useRef(-1);

  useEffect(() => {
    const SERVER = process.env.NEXT_PUBLIC_SERVER_URL ?? "http://localhost:8000";
    const connect = () => {
      const url = `${SERVER}/jobs/${jobId}/events?lastEventId=${lastSeqRef.current}`;
      const es = new EventSource(url);

      es.onmessage = (e) => {
        const ev: SseEvent = JSON.parse(e.data);
        lastSeqRef.current = ev.seq;
        setEvents((prev) => [...prev, ev]);

        if (ev.stage) setCurrentStage(ev.stage);
        if (ev.type === "job_started") setStatus("running");
        if (ev.type === "stage_started") setStatus("running");
        if (ev.type === "awaiting_approval") {
          setStatus("awaiting_approval");
          setAwaitingStage(ev.stage ?? null);
          setPreview((ev.preview as Record<string, unknown>) ?? null);
        }
        if (ev.type === "stage_approved" || ev.type === "stage_rejected") {
          setAwaitingStage(null);
          setStatus("running");
        }
        if (ev.type === "job_completed") {
          setStatus("completed");
          setRenderUrl(ev.render_url ?? null);
          es.close();
        }
        if (ev.type === "job_failed") {
          setStatus("failed");
          es.close();
        }
      };

      es.onerror = () => {
        es.close();
        // Reconnect after 2s if job still running
        if (!["completed", "failed"].includes(status)) {
          setTimeout(connect, 2000);
        }
      };

      return es;
    };

    const es = connect();
    return () => es.close();
  }, [jobId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  async function handleApproval(action: "approve" | "reject") {
    setApproving(true);
    const SERVER = process.env.NEXT_PUBLIC_SERVER_URL ?? "http://localhost:8000";
    await fetch(`${SERVER}/jobs/${jobId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, feedback }),
    });
    setFeedback("");
    setApproving(false);
    if (action === "approve") setAwaitingStage(null);
  }

  const stageIndex = currentStage ? STAGES.indexOf(currentStage) : -1;
  const progress = stageIndex >= 0 ? Math.round(((stageIndex + 1) / STAGES.length) * 100) : 0;

  return (
    <div className="p-8 max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight">{jobId}</h1>
          <p className="text-muted-foreground text-sm mt-0.5">Job ID: {jobId}</p>
        </div>
        <StatusBadge status={status} />
      </div>

      {/* Stepper */}
      <Card>
        <CardContent className="pt-6">
          <Progress value={progress} className="mb-4 h-1.5" />
          <div className="flex gap-1">
            {STAGES.map((s, i) => {
              const done = i < stageIndex;
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
                    {STAGE_LABELS[s]}
                  </span>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Approval panel */}
      {awaitingStage && (
        <Card className="border-yellow-500/40 bg-yellow-500/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <span className="text-yellow-400">⏸</span>
              {STAGE_LABELS[awaitingStage]} — 等待你的审批
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {preview && (
              <pre className="text-xs bg-muted/50 rounded p-3 overflow-auto max-h-48 whitespace-pre-wrap">
                {JSON.stringify(preview, null, 2)}
              </pre>
            )}
            <Textarea
              placeholder="（可选）写下反馈，让 AI 修改后重来..."
              rows={2}
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
            />
            <div className="flex gap-3">
              <Button onClick={() => handleApproval("approve")} disabled={approving} className="flex-1">
                ✓ 批准，继续生产
              </Button>
              <Button
                variant="outline"
                onClick={() => handleApproval("reject")}
                disabled={approving || !feedback}
                className="flex-1"
              >
                ↩ 打回重做
              </Button>
            </div>
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
            <video src={renderUrl} controls className="w-full rounded-lg bg-black aspect-video" />
            <a href={renderUrl} download>
              <Button variant="outline" className="w-full">下载 MP4</Button>
            </a>
          </CardContent>
        </Card>
      )}

      {/* Event stream */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm text-muted-foreground font-medium">实时进度</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-72 px-4 pb-4">
            <div className="space-y-1.5 font-mono text-xs">
              {events.map((ev) => (
                <EventRow key={ev.seq} ev={ev} />
              ))}
              {events.length === 0 && (
                <p className="text-muted-foreground py-4 text-center">等待任务启动...</p>
              )}
              <div ref={bottomRef} />
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const MAP: Record<string, { label: string; class: string }> = {
    queued:            { label: "排队中",   class: "bg-muted text-muted-foreground" },
    running:           { label: "生成中",   class: "bg-blue-500/20 text-blue-400 border-blue-500/30" },
    awaiting_approval: { label: "待审批",   class: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30" },
    completed:         { label: "已完成",   class: "bg-green-500/20 text-green-400 border-green-500/30" },
    failed:            { label: "失败",     class: "bg-red-500/20 text-red-400 border-red-500/30" },
  };
  const s = MAP[status] ?? { label: status, class: "bg-muted text-muted-foreground" };
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${s.class}`}>
      {s.label}
    </span>
  );
}

function EventRow({ ev }: { ev: SseEvent }) {
  const typeColor: Record<string, string> = {
    stage_started:     "text-blue-400",
    stage_completed:   "text-green-400",
    tool_call:         "text-purple-400",
    artifact_written:  "text-cyan-400",
    asset_ready:       "text-emerald-400",
    awaiting_approval: "text-yellow-400",
    stage_approved:    "text-green-400",
    stage_rejected:    "text-orange-400",
    agent_text:        "text-muted-foreground",
    job_completed:     "text-green-400",
    job_failed:        "text-red-400",
    error:             "text-red-400",
  };
  const color = typeColor[ev.type] ?? "text-muted-foreground";
  const ts = new Date(ev.ts * 1000).toLocaleTimeString("zh-CN", { hour12: false });

  const label = ev.summary ?? ev.text ?? ev.artifact ?? ev.message ?? ev.type;

  return (
    <div className="flex gap-2 items-start">
      <span className="text-muted-foreground/50 shrink-0">{ts}</span>
      <span className={`shrink-0 ${color}`}>[{ev.stage ?? ev.type}]</span>
      <span className="text-foreground/70 break-all">{label}</span>
    </div>
  );
}
