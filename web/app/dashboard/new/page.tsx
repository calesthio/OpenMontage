"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  CONTENT_TYPES, isPipelineAvailable, computeMorePipelines, toPipelineOption,
  type PipelineInfo, type PipelineOption,
} from "@/lib/pipeline-picker";

const SERVER = process.env.NEXT_PUBLIC_SERVER_URL ?? "http://localhost:8000";

type BrandKit = { kit_id: string; brand_name: string; slogan: string };
type Step = "type" | "wizard";

export default function NewProjectPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("type");
  const [selectedType, setSelectedType] = useState<PipelineOption | null>(null);
  const [brandKits, setBrandKits] = useState<BrandKit[]>([]);
  const [pipelines, setPipelines] = useState<PipelineInfo[]>([]);
  const [form, setForm] = useState({
    projectName: "",
    brandName: "",
    slogan: "",
    duration: "30",
    notes: "",
    brandKitId: "",
    budgetCny: "",
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${SERVER}/brands`)
      .then((r) => r.json())
      .then((d) => setBrandKits(d.brand_kits ?? []))
      .catch(() => {});
    fetch(`${SERVER}/pipelines`)
      .then((r) => r.json())
      .then((d) => setPipelines(d.pipelines ?? []))
      .catch(() => {});
  }, []);

  const availableNames = new Set(pipelines.map((p) => p.name));
  const morePipelines = computeMorePipelines(pipelines);

  function applyKit(kit: BrandKit) {
    setForm((f) => ({
      ...f,
      brandKitId: kit.kit_id,
      brandName: kit.brand_name,
      slogan: kit.slogan,
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedType) return;
    setLoading(true);

    const res = await fetch(`${SERVER}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_name: form.projectName || form.brandName.replace(/\s+/g, "-"),
        content_type: selectedType.id,
        pipeline: selectedType.pipeline,
        brand_info: {
          brand_name: form.brandName,
          slogan: form.slogan,
          notes: form.notes,
        },
        options: {
          duration_seconds: parseInt(form.duration),
          video_model: "leapfast/ltx-2.3",
          image_model: "leapfast/flux2",
          tts_model: "qwen3-tts-flash",
          ...(form.brandKitId ? { brand_kit_id: form.brandKitId } : {}),
          ...(form.budgetCny && Number(form.budgetCny) > 0
            ? { budget_cny: Number(form.budgetCny) }
            : {}),
        },
      }),
    });

    const data = await res.json();
    if (res.ok && data.job_id) {
      router.push(`/dashboard/jobs/${data.job_id}`);
    } else {
      alert("创建失败: " + JSON.stringify(data));
      setLoading(false);
    }
  }

  if (step === "type") {
    return (
      <div className="p-8 max-w-3xl">
        <h1 className="text-2xl font-bold tracking-tight mb-2">选择视频类型</h1>
        <p className="text-muted-foreground text-sm mb-8">选择要制作的视频类型，AI 会自动选择最合适的生产流程。</p>
        <div className="grid grid-cols-1 gap-3">
          {CONTENT_TYPES.map((ct) => {
            // Available once the engine reports the mapped pipeline (or before
            // /pipelines has loaded, so the UI isn't empty on first paint).
            const available = isPipelineAvailable(availableNames, ct.pipeline);
            return (
              <button
                key={ct.id}
                disabled={!available}
                onClick={() => { setSelectedType(ct); setStep("wizard"); }}
                className={`text-left p-4 rounded-lg border transition-colors ${
                  available
                    ? "border-border hover:border-foreground/40 hover:bg-accent cursor-pointer"
                    : "border-border/40 opacity-40 cursor-not-allowed"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{ct.label}</span>
                      {!available && <Badge variant="outline" className="text-xs">未启用</Badge>}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">{ct.description}</p>
                  </div>
                  {available && <span className="text-muted-foreground text-lg">→</span>}
                </div>
              </button>
            );
          })}
        </div>

        {morePipelines.length > 0 && (
          <div className="mt-8">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
              更多引擎流水线
            </h2>
            <div className="grid grid-cols-1 gap-3">
              {morePipelines.map((p) => (
                <button
                  key={p.name}
                  onClick={() => {
                    setSelectedType(toPipelineOption(p));
                    setStep("wizard");
                  }}
                  className="text-left p-4 rounded-lg border border-border hover:border-foreground/40 hover:bg-accent cursor-pointer transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-sm font-mono">{p.name}</span>
                        {p.stability && p.stability !== "production" && (
                          <Badge variant="outline" className="text-xs">{p.stability}</Badge>
                        )}
                        <span className="text-xs text-muted-foreground">{p.stages.length} 阶段</span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{p.description}</p>
                    </div>
                    <span className="text-muted-foreground text-lg">→</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="p-8 max-w-xl">
      <button
        onClick={() => setStep("type")}
        className="text-sm text-muted-foreground hover:text-foreground mb-6 flex items-center gap-1"
      >
        ← 重新选择类型
      </button>

      <h1 className="text-2xl font-bold tracking-tight mb-1">{selectedType?.label}</h1>
      <p className="text-muted-foreground text-sm mb-8">{selectedType?.description}</p>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Brand Kit selector */}
        {brandKits.length > 0 && (
          <div className="space-y-2">
            <h2 className="text-sm font-semibold text-foreground/70 uppercase tracking-wider">快速套用品牌 Kit</h2>
            <div className="flex gap-2 flex-wrap">
              {brandKits.map((kit) => (
                <button
                  key={kit.kit_id}
                  type="button"
                  onClick={() => applyKit(kit)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    form.brandKitId === kit.kit_id
                      ? "bg-foreground text-background border-foreground"
                      : "border-border hover:border-foreground/40"
                  }`}
                >
                  {kit.brand_name}
                </button>
              ))}
              {form.brandKitId && (
                <button
                  type="button"
                  onClick={() => setForm(f => ({ ...f, brandKitId: "" }))}
                  className="text-xs px-3 py-1.5 text-muted-foreground hover:text-foreground"
                >
                  × 清除
                </button>
              )}
            </div>
          </div>
        )}

        {brandKits.length > 0 && <Separator />}

        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-foreground/70 uppercase tracking-wider">品牌信息</h2>
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium block mb-1.5">品牌 / 产品名称 *</label>
              <Input
                required
                placeholder="例：小狗牌咖啡机"
                value={form.brandName}
                onChange={(e) => setForm(f => ({ ...f, brandName: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-sm font-medium block mb-1.5">项目名称（选填）</label>
              <Input
                placeholder="留空则自动生成"
                value={form.projectName}
                onChange={(e) => setForm(f => ({ ...f, projectName: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-sm font-medium block mb-1.5">品牌 Slogan（选填）</label>
              <Input
                placeholder="例：好咖啡，不只属于咖啡馆"
                value={form.slogan}
                onChange={(e) => setForm(f => ({ ...f, slogan: e.target.value }))}
              />
            </div>
          </div>
        </div>

        <Separator />

        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-foreground/70 uppercase tracking-wider">视频参数</h2>
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium block mb-1.5">时长</label>
              <div className="flex gap-2">
                {["15", "30", "60"].map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setForm(f => ({ ...f, duration: d }))}
                    className={`px-4 py-1.5 rounded-md text-sm border transition-colors ${
                      form.duration === d
                        ? "bg-foreground text-background border-foreground"
                        : "border-border hover:border-foreground/40"
                    }`}
                  >
                    {d}s
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-sm font-medium block mb-1.5">预算上限 ¥（选填）</label>
              <Input
                type="number"
                min="0"
                step="0.5"
                placeholder="例如 50 — 累计成本超过后暂停等待确认"
                value={form.budgetCny}
                onChange={(e) => setForm(f => ({ ...f, budgetCny: e.target.value }))}
              />
              <p className="text-xs text-muted-foreground mt-1">
                MaaS 按 CNY 计费。留空则不设预算门。
              </p>
            </div>
            <div>
              <label className="text-sm font-medium block mb-1.5">补充说明（选填）</label>
              <Textarea
                placeholder="目标受众、情感基调、参考风格等..."
                rows={3}
                value={form.notes}
                onChange={(e) => setForm(f => ({ ...f, notes: e.target.value }))}
              />
            </div>
          </div>
        </div>

        <Button type="submit" className="w-full" disabled={loading || !form.brandName}>
          {loading ? "提交中..." : "开始 AI 生产 →"}
        </Button>
      </form>
    </div>
  );
}
