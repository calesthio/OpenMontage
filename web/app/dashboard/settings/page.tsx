"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const SERVER = process.env.NEXT_PUBLIC_SERVER_URL ?? "http://localhost:8000";

type HealthData = { status: string; service: string };
type SystemInfo = { serverOk: boolean; jobs: number; brands: number };

export default function SettingsPage() {
  const [info, setInfo] = useState<SystemInfo | null>(null);

  useEffect(() => {
    async function load() {
      const [health, jobs, brands] = await Promise.allSettled([
        fetch(`${SERVER}/health`).then((r) => r.json() as Promise<HealthData>),
        fetch(`${SERVER}/jobs`).then((r) => r.json()),
        fetch(`${SERVER}/brands`).then((r) => r.json()),
      ]);
      setInfo({
        serverOk: health.status === "fulfilled" && health.value.status === "ok",
        jobs: jobs.status === "fulfilled" ? (jobs.value.jobs?.length ?? 0) : 0,
        brands: brands.status === "fulfilled" ? (brands.value.brand_kits?.length ?? 0) : 0,
      });
    }
    load();
  }, []);

  const env = {
    "LLM 模型": "anthropic/claude-sonnet-4.6",
    "视频生成": "MaaS · LTX-2.3",
    "图像生成": "MaaS · Flux2",
    "语音合成": "MaaS · qwen3-tts-flash / IndexTTS",
    "文件存储": "本地文件系统 (projects/)",
    "认证方式": "团队口令 v1",
    "数据库": "内存 JobStore (v1)",
  };

  const roadmap = [
    { id: "Q3-1", label: "任务队列", desc: "Redis + Celery 替换 BackgroundTasks，支持重启恢复", status: "planned" },
    { id: "Q3-2", label: "对象存储", desc: "S3/OSS 替换本地 projects/ 目录，多实例共享", status: "planned" },
    { id: "Q3-3", label: "OAuth 认证", desc: "企业 SSO / GitHub OAuth 替换团队口令", status: "planned" },
    { id: "Q3-4", label: "Postgres 迁移", desc: "JobStore 持久化到 Postgres，Prisma 已就绪", status: "ready" },
    { id: "Q4-1", label: "多 pipeline 支持", desc: "解说视频、播客剪辑、产品演示流程", status: "planned" },
    { id: "Q4-2", label: "成本预算门", desc: "每任务预算上限，超额暂停等待批准", status: "planned" },
  ];

  return (
    <div className="p-8 max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">设置</h1>
        <p className="text-muted-foreground text-sm mt-1">系统状态与演进路线</p>
      </div>

      {/* System status */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">系统状态</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm">AI 生产服务器</span>
            {info === null ? (
              <span className="text-xs text-muted-foreground">检查中…</span>
            ) : (
              <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${info.serverOk ? "bg-green-500/15 text-green-400 border-green-500/30" : "bg-red-500/15 text-red-400 border-red-500/30"}`}>
                {info.serverOk ? "● 在线" : "● 离线"}
              </span>
            )}
          </div>
          {info && (
            <>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">历史项目数</span>
                <span className="font-mono">{info.jobs}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">品牌 Kit 数</span>
                <span className="font-mono">{info.brands}</span>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Stack */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">当前技术栈</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2.5">
            {Object.entries(env).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{k}</span>
                <span className="text-foreground font-mono text-xs">{v}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Roadmap — M5-3 evolution interfaces */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">演进路线 (M5-3)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {roadmap.map((item) => (
              <div key={item.id} className="flex items-start gap-3">
                <span className={`mt-0.5 w-2 h-2 rounded-full shrink-0 ${item.status === "ready" ? "bg-yellow-400" : "bg-muted-foreground/30"}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{item.label}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${item.status === "ready" ? "bg-yellow-500/15 text-yellow-400 border-yellow-500/30" : "bg-muted text-muted-foreground border-border"}`}>
                      {item.status === "ready" ? "接口已预留" : "规划中"}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
