"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const SERVER = process.env.NEXT_PUBLIC_SERVER_URL ?? "http://localhost:8000";

type HealthData = { status: string; service: string };
type SystemInfo = { serverOk: boolean; jobs: number; brands: number };
type Seam = { active: string; available: string[]; planned: string[] };
type Backends = { storage: Seam; queue: Seam; auth: Seam };

const SEAM_LABELS: Record<keyof Backends, { title: string; desc: string }> = {
  queue: { title: "任务队列", desc: "驱动流水线执行的调度层" },
  storage: { title: "对象存储", desc: "工件 / 素材 / 成片的存储与分发" },
  auth: { title: "身份认证", desc: "访问控制方式" },
};

export default function SettingsPage() {
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [backends, setBackends] = useState<Backends | null>(null);
  // No hardcoded fallback string here on purpose — a stale literal is
  // exactly the bug this fixes (MAAS_LLM_MODEL can override the default,
  // and the page should never claim a model isn't the one actually running).
  const [llmModel, setLlmModel] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      const [health, jobs, brands, caps] = await Promise.allSettled([
        fetch(`${SERVER}/health`).then((r) => r.json() as Promise<HealthData>),
        fetch(`${SERVER}/jobs`).then((r) => r.json()),
        fetch(`${SERVER}/brands`).then((r) => r.json()),
        fetch(`${SERVER}/system/capabilities`).then((r) => r.json()),
      ]);
      setInfo({
        serverOk: health.status === "fulfilled" && health.value.status === "ok",
        jobs: jobs.status === "fulfilled" ? (jobs.value.jobs?.length ?? 0) : 0,
        brands: brands.status === "fulfilled" ? (brands.value.brand_kits?.length ?? 0) : 0,
      });
      if (caps.status === "fulfilled" && caps.value?.backends) {
        setBackends(caps.value.backends as Backends);
      }
      if (caps.status === "fulfilled" && caps.value?.llm_model) {
        setLlmModel(caps.value.llm_model as string);
      }
    }
    load();
  }, []);

  const env = {
    "LLM 模型": llmModel ?? "加载中…",
    "视频生成": "MaaS · LTX-2.3 / Wan2.2 / Seedance (CNY 计费)",
    "图像生成": "MaaS · Flux2 / NanoBanana",
    "语音合成": "MaaS · qwen3-tts-flash / IndexTTS",
    "成本追踪": "cost_tracker 原账本 (cost_log.json)",
  };

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

      {/* Evolution seams — live from /system/capabilities (M5-3) */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">演进接口 (M5-3)</CardTitle>
        </CardHeader>
        <CardContent>
          {backends === null ? (
            <p className="text-xs text-muted-foreground">读取后端能力中…</p>
          ) : (
            <div className="space-y-4">
              {(Object.keys(SEAM_LABELS) as (keyof Backends)[]).map((key) => {
                const seam = backends[key];
                const meta = SEAM_LABELS[key];
                return (
                  <div key={key} className="flex items-start gap-3">
                    <span className="mt-1 w-2 h-2 rounded-full shrink-0 bg-green-400" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium">{meta.title}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded border font-medium bg-green-500/15 text-green-400 border-green-500/30">
                          运行中: {seam.active}
                        </span>
                        {seam.planned.map((p) => (
                          <span key={p} className="text-[10px] px-1.5 py-0.5 rounded border font-medium bg-muted text-muted-foreground border-border">
                            {p} · 规划中
                          </span>
                        ))}
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {meta.desc} — 接口已预留 (server/app/interfaces)，切换实现无需改调用方。
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
