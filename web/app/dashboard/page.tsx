"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type Job = {
  job_id: string;
  project_name: string;
  content_type: string;
  status: string;
  current_stage: string | null;
  created_at: number;
  brand_info?: { brand_name?: string };
};

const STATUS_META: Record<string, { label: string; cls: string }> = {
  queued:            { label: "排队中", cls: "bg-muted text-muted-foreground border-border" },
  running:           { label: "生成中", cls: "bg-blue-500/15 text-blue-400 border-blue-500/30" },
  awaiting_approval: { label: "待审批", cls: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30" },
  completed:         { label: "已完成", cls: "bg-green-500/15 text-green-400 border-green-500/30" },
  failed:            { label: "失败",   cls: "bg-red-500/15 text-red-400 border-red-500/30" },
};

const CONTENT_TYPE_LABEL: Record<string, string> = {
  marketing_film: "营销宣传片",
  explainer: "解说视频",
  podcast: "播客剪辑",
};

export default function DashboardPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  async function fetchJobs() {
    const SERVER = process.env.NEXT_PUBLIC_SERVER_URL ?? "http://localhost:8000";
    try {
      const res = await fetch(`${SERVER}/jobs`);
      if (res.ok) {
        const data = await res.json();
        setJobs(data.jobs ?? []);
      }
    } catch {}
    setLoading(false);
  }

  useEffect(() => {
    fetchJobs();
    // Poll every 8s so status badges update
    const id = setInterval(fetchJobs, 8000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">我的项目</h1>
          <p className="text-muted-foreground text-sm mt-1">AI 驱动的视频生产任务</p>
        </div>
        <Link href="/dashboard/new">
          <Button>+ 新建视频</Button>
        </Link>
      </div>

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

      {!loading && jobs.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {jobs.map((job) => {
            const s = STATUS_META[job.status] ?? STATUS_META.queued;
            const brandName = job.brand_info?.brand_name ?? job.project_name;
            const contentLabel = CONTENT_TYPE_LABEL[job.content_type] ?? job.content_type;
            const date = new Date(job.created_at * 1000).toLocaleDateString("zh-CN");
            return (
              <Link key={job.job_id} href={`/dashboard/jobs/${job.job_id}`}>
                <Card className="hover:border-foreground/30 transition-colors cursor-pointer h-full">
                  <div className="aspect-video bg-muted rounded-t-lg flex items-center justify-center relative overflow-hidden">
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
                    <span className="text-muted-foreground/40 text-xs">
                      {job.status === "completed" ? "🎬" : job.current_stage ?? ""}
                    </span>
                  </div>
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <CardTitle className="text-base leading-tight">{brandName}</CardTitle>
                      <span className={`shrink-0 text-[11px] px-2 py-0.5 rounded-full border font-medium ${s.cls}`}>
                        {s.label}
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
