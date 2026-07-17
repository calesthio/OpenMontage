"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge, stageLabel, mediaUrl } from "@/components/job-status";
import { CONTENT_TYPES } from "@/lib/pipeline-picker";
import { SERVER, apiRequest } from "@/lib/api";

type Job = {
  job_id: string;
  project_name: string;
  content_type: string;
  status: string;
  current_stage: string | null;
  created_at: number;
  brand_info?: { brand_name?: string };
  render_url?: string | null;
  preview_render_url?: string | null;
};

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

// Derived from the wizard's CONTENT_TYPES so this list can never drift out of
// sync with it again — this page used to hardcode its own copy, which lacked
// the "demo" and "short" entries, so those jobs showed raw ids. Unknown ids
// still fall back to the raw content_type at the lookup site below.
const CONTENT_TYPE_LABEL: Record<string, string> = Object.fromEntries(
  CONTENT_TYPES.map((ct) => [ct.id, ct.label])
);

export default function DashboardPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  async function fetchJobs() {
    const res = await apiRequest("/jobs");
    if (res.ok) setJobs(res.data.jobs ?? []);
    setLoading(false);
  }

  async function handleDelete(e: React.MouseEvent, job: Job) {
    // The card is wrapped in a Link — keep the click from navigating.
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(`删除任务记录 “${job.project_name}”?(不会删除磁盘上的项目产物)`)) return;
    const res = await apiRequest(`/jobs/${job.job_id}`, { method: "DELETE" });
    if (res.ok) fetchJobs();
  }

  useEffect(() => {
    // Async fetch: setState happens after await, not synchronously in the effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchJobs();
    // Poll every 8s so status badges update
    const id = setInterval(fetchJobs, 8000);
    return () => clearInterval(id);
  }, []);

  const shown = jobs.filter((j) => {
    if (statusFilter && j.status !== statusFilter) return false;
    if (q) {
      const needle = q.toLowerCase();
      const hay = `${j.project_name} ${j.brand_info?.brand_name ?? ""} ${j.content_type}`.toLowerCase();
      if (!hay.includes(needle)) return false;
    }
    return true;
  });

  return (
    <div className="p-4 md:p-8 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">我的项目</h1>
          <p className="text-muted-foreground text-sm mt-1">AI 驱动的视频生产任务</p>
        </div>
        <Link href="/dashboard/new">
          <Button>+ 新建视频</Button>
        </Link>
      </div>

      {jobs.length > 0 && (
        <div className="flex flex-col sm:flex-row gap-2 mb-6">
          <label className="sr-only" htmlFor="job-search">搜索项目</label>
          <input
            id="job-search"
            className="bg-muted/40 border border-border rounded px-3 py-1.5 text-sm sm:max-w-xs"
            placeholder="搜索项目名 / 品牌…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <label className="sr-only" htmlFor="job-status-filter">按状态筛选</label>
          <select
            id="job-status-filter"
            className="bg-muted/40 border border-border rounded px-2 py-1.5 text-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">全部状态</option>
            <option value="running">生成中</option>
            <option value="awaiting_approval">待审批</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
            <option value="cancelled">已取消</option>
          </select>
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">加载中…</div>
      )}

      {!loading && jobs.length === 0 && (
        <div className="flex flex-col items-center justify-center h-64 border border-dashed border-border rounded-lg gap-4">
          <p className="text-muted-foreground text-sm">还没有项目</p>
          <Link href="/dashboard/new">
            <Button variant="outline">创建第一个视频</Button>
          </Link>
        </div>
      )}

      {!loading && jobs.length > 0 && shown.length === 0 && (
        <p className="text-sm text-muted-foreground border border-dashed border-border rounded-lg p-8 text-center">
          没有匹配的项目
        </p>
      )}

      {!loading && shown.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {shown.map((job) => {
            const displayName = job.project_name || job.brand_info?.brand_name || job.job_id;
            const contentLabel = CONTENT_TYPE_LABEL[job.content_type] ?? job.content_type;
            const date = new Date(job.created_at * 1000).toLocaleDateString("zh-CN");
            const poster = job.render_url || job.preview_render_url;
            return (
              <Link key={job.job_id} href={`/dashboard/jobs/${job.job_id}`}>
                <Card className="hover:border-foreground/30 transition-colors cursor-pointer h-full">
                  <div className="aspect-video bg-muted rounded-t-lg flex items-center justify-center relative overflow-hidden">
                    {/* Real poster frame (roadmap 3.6): the render's own
                        first frame via preload=metadata — not an emoji. */}
                    {poster ? (
                      <video
                        src={mediaUrl(SERVER, poster) ?? undefined}
                        muted
                        preload="metadata"
                        className="absolute inset-0 w-full h-full object-cover"
                      />
                    ) : null}
                    {job.status === "running" && (
                      <div className="absolute inset-0 flex items-center justify-center gap-1">
                        {[0, 1, 2].map((i) => (
                          <span
                            key={i}
                            className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce"
                            style={{ animationDelay: `${i * 0.15}s` }}
                          />
                        ))}
                      </div>
                    )}
                    {!poster && (
                      <span className="text-muted-foreground/40 text-xs">
                        {job.status === "completed" ? "🎬" : stageLabel(job.current_stage)}
                      </span>
                    )}
                    {TERMINAL.has(job.status) && (
                      <button
                        type="button"
                        onClick={(e) => handleDelete(e, job)}
                        aria-label={`删除任务 ${displayName}`}
                        title="删除任务记录"
                        className="absolute top-1.5 right-1.5 w-6 h-6 rounded-full bg-black/50 text-white/80 hover:bg-red-500/80 text-xs"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <CardTitle className="text-base leading-tight">{displayName}</CardTitle>
                      {/* Shared badge from job-status.tsx — this page used to
                          hardcode a near-identical STATUS_META map that lacked
                          "cancelled", so a cancelled job fell back to the
                          "排队中" (queued) badge here while its own detail
                          page correctly showed "已取消". The shrink-0 wrapper
                          keeps the badge from collapsing next to a long
                          project title, as the old inline span did. */}
                      <span className="shrink-0">
                        <StatusBadge status={job.status} />
                      </span>
                    </div>
                    <CardDescription className="text-xs">{contentLabel}</CardDescription>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <p className="text-xs text-muted-foreground">{date}</p>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
