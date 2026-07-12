"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { modelLabel, type ModelCatalog } from "@/lib/model-catalog";

const SERVER = process.env.NEXT_PUBLIC_SERVER_URL ?? "http://localhost:8000";

type HealthData = { status: string; service: string };
type SystemInfo = { serverOk: boolean; jobs: number; brands: number };
type Seam = { active: string; available: string[]; planned: string[]; enforced?: boolean };
type Backends = { storage: Seam; queue: Seam; auth: Seam };

// Turns a live model_catalog id list into the same "MaaS · A / B / C" display
// string this page always showed, without hardcoding the id→label mapping or
// the id list itself a second time (the wizard is the other consumer).
function catalogSummary(ids: string[] | undefined, suffix = ""): string {
  if (!ids || ids.length === 0) return "加载中…";
  return `MaaS · ${ids.map(modelLabel).join(" / ")}${suffix}`;
}

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
  // No hardcoded fallback list here either, for the same reason as llmModel —
  // the wizard and this page used to each hardcode an independent copy of
  // this catalog, which could silently drift.
  const [modelCatalog, setModelCatalog] = useState<ModelCatalog | null>(null);

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
      if (caps.status === "fulfilled" && caps.value?.model_catalog) {
        setModelCatalog(caps.value.model_catalog as ModelCatalog);
      }
    }
    // Async fetch: setState happens after await, not synchronously in the effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    // Re-poll periodically so the online/offline badge (and job/brand counts)
    // recover on their own if the backend was down at mount time or goes
    // down/up later, mirroring the dashboard job list's 8s polling pattern.
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  const env = {
    "LLM 模型": llmModel ?? "加载中…",
    "视频生成": catalogSummary(modelCatalog?.video_models, " (CNY 计费)"),
    "图像生成": catalogSummary(modelCatalog?.image_models),
    "语音合成": catalogSummary(modelCatalog?.tts_models),
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
                // storage/queue are genuinely what's running for every
                // operation; auth is configured but not enforced by any
                // route (no Depends() checks it) — showing the same green
                // "运行中" badge for auth would claim requests are
                // authenticated when they aren't.
                const notEnforced = seam.enforced === false;
                return (
                  <div key={key} className="flex items-start gap-3">
                    <span className={`mt-1 w-2 h-2 rounded-full shrink-0 ${notEnforced ? "bg-yellow-400" : "bg-green-400"}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium">{meta.title}</span>
                        {notEnforced ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded border font-medium bg-yellow-500/15 text-yellow-500 border-yellow-500/30">
                            {seam.active} · 未在 API 层强制生效
                          </span>
                        ) : (
                          <span className="text-[10px] px-1.5 py-0.5 rounded border font-medium bg-green-500/15 text-green-400 border-green-500/30">
                            运行中: {seam.active}
                          </span>
                        )}
                        {seam.planned.map((p) => (
                          <span key={p} className="text-[10px] px-1.5 py-0.5 rounded border font-medium bg-muted text-muted-foreground border-border">
                            {p} · 规划中
                          </span>
                        ))}
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {notEnforced
                          ? "本地单人工具，未对 API 请求做身份校验——任何能访问这个进程的请求都会被处理。"
                          : `${meta.desc} — 接口已预留 (server/app/interfaces)，切换实现无需改调用方。`}
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
