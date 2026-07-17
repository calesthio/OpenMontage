"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  CONTENT_TYPES, isPipelineAvailable, computeMorePipelines, toPipelineOption,
  type PipelineInfo, type PipelineOption,
} from "@/lib/pipeline-picker";
import { modelLabel, FALLBACK_MODEL_CATALOG, type ModelCatalog } from "@/lib/model-catalog";
import { SERVER, apiRequest } from "@/lib/api";
import { PillSelect } from "@/components/pill-select";

const DEFAULT_VIDEO_MODEL = FALLBACK_MODEL_CATALOG.video_models[0];
const DEFAULT_IMAGE_MODEL = FALLBACK_MODEL_CATALOG.image_models[0];
const DEFAULT_TTS_MODEL = FALLBACK_MODEL_CATALOG.tts_models[0];

// Picks a video model different from `exclude`, for the comparison-mode
// second slot — guarantees the two pickers never default to the same model.
function otherVideoModel(exclude: string, videoModels: string[]): string {
  return videoModels.find((id) => id !== exclude) ?? videoModels[0];
}

type BrandKit = {
  kit_id: string;
  brand_name: string;
  slogan: string;
  reference_image_path?: string;
};
type Step = "type" | "wizard";

export default function NewProjectPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("type");
  const [selectedType, setSelectedType] = useState<PipelineOption | null>(null);
  const [brandKits, setBrandKits] = useState<BrandKit[]>([]);
  const [pipelines, setPipelines] = useState<PipelineInfo[]>([]);
  const [pipelinesLoadFailed, setPipelinesLoadFailed] = useState(false);
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
  const [submitError, setSubmitError] = useState("");

  const [modelCatalog, setModelCatalog] = useState<ModelCatalog>(FALLBACK_MODEL_CATALOG);
  const [videoModel, setVideoModel] = useState<string>(DEFAULT_VIDEO_MODEL);
  const [compareMode, setCompareMode] = useState(false);
  const [videoModelB, setVideoModelB] = useState<string>(
    () => otherVideoModel(DEFAULT_VIDEO_MODEL, FALLBACK_MODEL_CATALOG.video_models)
  );
  const [imageModel, setImageModel] = useState<string>(DEFAULT_IMAGE_MODEL);
  const [ttsModel, setTtsModel] = useState<string>(DEFAULT_TTS_MODEL);

  // IndexTTS V3-only emotion params (tools/audio/maas_tts.py's emo_alpha /
  // use_emo_text / emo_text / interval_silence) — meaningless for other TTS
  // models, so only sent when ttsModel is leapfast/indextts.
  const [emoAlpha, setEmoAlpha] = useState(1.0);
  const [useEmoText, setUseEmoText] = useState(false);
  const [emoText, setEmoText] = useState("");
  const [intervalSilence, setIntervalSilence] = useState(200);

  useEffect(() => {
    apiRequest("/brands").then((r) => {
      if (r.ok) {
        const kits = r.data.brand_kits ?? [];
        setBrandKits(kits);
        // Brand lock (roadmap 3.2, Synthesia's strongest enforcement
        // primitive): when the workspace HAS brand kits, a production is
        // always brand-locked — default to the first kit instead of
        // offering an unbranded escape hatch. Kit-less workspaces still
        // proceed unbranded (nothing to lock to).
        if (kits.length > 0) {
          setForm((f) => (f.brandKitId ? f : {
            ...f,
            brandKitId: kits[0].kit_id,
            brandName: f.brandName || kits[0].brand_name,
            slogan: f.slogan || kits[0].slogan,
          }));
        }
      }
    });
    // Only a network-level failure (status 0, backend unreachable) marks the
    // pipeline list as failed-to-load — this mirrors the original `.catch()`
    // placement, where a reachable backend answering non-OK JSON still
    // resolved the promise chain without tripping the failure flag.
    apiRequest("/pipelines").then((r) => {
      if (r.ok) setPipelines(r.data.pipelines ?? []);
      else if (r.status === 0) setPipelinesLoadFailed(true);
    });
    // Live model catalog — falls back to FALLBACK_MODEL_CATALOG (already the
    // initial state) if this hasn't resolved yet or fails, same pattern as
    // isPipelineAvailable's "show everything before /pipelines loads".
    apiRequest("/system/capabilities").then((r) => {
      if (r.ok && r.data.model_catalog) setModelCatalog(r.data.model_catalog);
    });
  }, []);

  const availableNames = new Set(pipelines.map((p) => p.name));
  const morePipelines = computeMorePipelines(pipelines);

  // Live cost estimate for the selected pipeline (roadmap 3.1).
  type Estimate = {
    sample_count: number; low_cny: number | null;
    typical_cny: number | null; high_cny: number | null;
  };
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const estimatePipeline = selectedType?.pipeline;
  useEffect(() => {
    if (!estimatePipeline) return;
    apiRequest("/system/estimate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pipeline: estimatePipeline }),
    }).then((r) => {
      if (r.ok) setEstimate(r.data);
    });
  }, [estimatePipeline]);

  const selectedKit = brandKits.find((k) => k.kit_id === form.brandKitId);

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
    setSubmitError("");

    try {
      // Deliberately raw fetch, not lib/api's apiRequest: this flow reads
      // data.job_id off the success body, and its error surface is richer
      // than the shared helper's normalized detail — the non-ok fallback
      // embeds the whole response body (JSON.stringify below) and the
      // network-error message carries a "创建失败：" prefix.
      const res = await fetch(`${SERVER}/jobs`, {
        method: "POST",
        credentials: "include",
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
            video_model: videoModel,
            image_model: imageModel,
            tts_model: ttsModel,
            ...(compareMode ? { video_model_variants: [videoModel, videoModelB] } : {}),
            ...(ttsModel === "leapfast/indextts" ? {
              tts_emotion: {
                emo_alpha: emoAlpha,
                // Only ask the backend for emotion-text-guided synthesis when
                // there's actually guiding text — sending use_emo_text: true
                // with no emo_text would ask maas_tts for emotion-text
                // guidance it has nothing to work from. If the checkbox is
                // checked but the field was left empty, this simply doesn't
                // enable it (mirrors the checkbox's own emptiness rather than
                // blocking submission for a non-required, secondary field).
                use_emo_text: useEmoText && emoText.trim().length > 0,
                ...(useEmoText && emoText.trim() ? { emo_text: emoText } : {}),
                interval_silence: intervalSilence,
              },
            } : {}),
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
        setSubmitError(data.detail ?? `创建失败 (HTTP ${res.status}): ${JSON.stringify(data)}`);
        setLoading(false);
      }
    } catch {
      setSubmitError("创建失败：网络错误，请检查后端是否可访问");
      setLoading(false);
    }
  }

  if (step === "type") {
    return (
      <div className="p-8 max-w-3xl">
        <h1 className="text-2xl font-bold tracking-tight mb-2">选择视频类型</h1>
        <p className="text-muted-foreground text-sm mb-8">选择要制作的视频类型，AI 会自动选择最合适的生产流程。</p>
        {pipelinesLoadFailed && (
          <p className="text-sm text-destructive border border-destructive/40 bg-destructive/10 rounded-md px-3 py-2 mb-6">
            无法加载可用流水线列表，请检查后端连接。
          </p>
        )}
        <div className="grid grid-cols-1 gap-3">
          {CONTENT_TYPES.map((ct) => {
            // Available once the engine reports the mapped pipeline (or before
            // /pipelines has loaded, so the UI isn't empty on first paint).
            // Once the fetch has genuinely failed, fail closed instead of
            // pretending the backend is reachable.
            const available = isPipelineAvailable(availableNames, ct.pipeline, pipelinesLoadFailed);
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
              {/* Brand lock (roadmap 3.2): with kits present there is no
                  "无品牌" escape hatch — switching kits is the only choice. */}
            </div>

            {selectedKit?.reference_image_path && (
              <div className="flex items-center gap-3 p-2 rounded-md border border-border bg-accent/40">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`${SERVER}/brand-media/${selectedKit.kit_id}/${selectedKit.reference_image_path}`}
                  alt="品牌参考图"
                  className="w-10 h-10 rounded object-cover border border-border shrink-0"
                />
                <p className="text-xs text-muted-foreground flex-1">
                  已设置参考图，将用于保持角色/产品外观一致。
                  <Link href="/dashboard/brands" className="underline hover:text-foreground ml-1">
                    修改
                  </Link>
                </p>
              </div>
            )}
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
          <h2 className="text-sm font-semibold text-foreground/70 uppercase tracking-wider">视频模型</h2>
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium block mb-1.5">模型</label>
              <PillSelect
                options={modelCatalog.video_models}
                value={videoModel}
                onChange={(id) => {
                  setVideoModel(id);
                  if (compareMode && id === videoModelB) {
                    setVideoModelB(otherVideoModel(id, modelCatalog.video_models));
                  }
                }}
                renderLabel={modelLabel}
              />
            </div>

            <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
              <input
                type="checkbox"
                checked={compareMode}
                onChange={(e) => {
                  const on = e.target.checked;
                  setCompareMode(on);
                  if (on && videoModelB === videoModel) {
                    setVideoModelB(otherVideoModel(videoModel, modelCatalog.video_models));
                  }
                }}
                className="h-4 w-4 rounded border-border"
              />
              对比模式（每个镜头会用两个模型各生成一次，便于直接比较）
            </label>

            {compareMode && (
              <div>
                <label className="text-sm font-medium block mb-1.5">对比模型 B</label>
                <PillSelect
                  options={modelCatalog.video_models}
                  value={videoModelB}
                  onChange={setVideoModelB}
                  disabledIds={[videoModel]}
                  renderLabel={modelLabel}
                />
              </div>
            )}
          </div>
        </div>

        <Separator />

        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-foreground/70 uppercase tracking-wider">图像模型</h2>
          <div className="space-y-3">
            <div>
              <PillSelect
                options={modelCatalog.image_models}
                value={imageModel}
                onChange={setImageModel}
                renderLabel={modelLabel}
              />
            </div>
          </div>
        </div>

        <Separator />

        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-foreground/70 uppercase tracking-wider">语音模型</h2>
          <div className="space-y-3">
            <div>
              <PillSelect
                options={modelCatalog.tts_models}
                value={ttsModel}
                onChange={setTtsModel}
                renderLabel={modelLabel}
              />
            </div>

            {ttsModel === "leapfast/indextts" && (
              <div className="space-y-3 pt-1">
                <div>
                  <label className="text-sm font-medium block mb-1.5">
                    情绪强度 emo_alpha: {emoAlpha.toFixed(1)}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={emoAlpha}
                    onChange={(e) => setEmoAlpha(parseFloat(e.target.value))}
                    className="w-full"
                  />
                  <p className="text-xs text-muted-foreground mt-1">0 = 平淡，1 = 情绪最强烈</p>
                </div>

                <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={useEmoText}
                    onChange={(e) => setUseEmoText(e.target.checked)}
                    className="h-4 w-4 rounded border-border"
                  />
                  使用情绪文字提示（emo_text）
                </label>

                {useEmoText && (
                  <div>
                    <Input
                      placeholder="例：兴奋、低声细语、悲伤…"
                      value={emoText}
                      onChange={(e) => setEmoText(e.target.value)}
                    />
                    {!emoText.trim() && (
                      <p className="text-xs text-muted-foreground mt-1">
                        留空则不会启用情绪文字引导（需要填写文字才能生效）。
                      </p>
                    )}
                  </div>
                )}

                <div>
                  <label className="text-sm font-medium block mb-1.5">
                    句间停顿 interval_silence: {intervalSilence}ms
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="2000"
                    step="50"
                    value={intervalSilence}
                    onChange={(e) => setIntervalSilence(parseInt(e.target.value, 10))}
                    className="w-full"
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        <Separator />

        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-foreground/70 uppercase tracking-wider">视频参数</h2>
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium block mb-1.5">时长</label>
              <PillSelect
                options={["15", "30", "60"]}
                value={form.duration}
                onChange={(d) => setForm(f => ({ ...f, duration: d }))}
                renderLabel={(d) => `${d}s`}
              />
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
              <p className="text-xs text-muted-foreground mt-1">
                视频类流水线通常涉及多次视频/图像模型调用，成本较高；预算设得过低（如个位数）可能在生产刚开始就触发预算门，并不代表出了问题。建议预算不低于 ¥50 起步，运行中可按需批准超支。
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

        {/* Decision-point pricing (roadmap 3.1): the estimated spend sits ON
            the commit button's doorstep, not discovered after the fact. */}
        {estimate && estimate.sample_count > 0 && (
          <p className="text-xs text-muted-foreground text-center" data-testid="estimate-chip">
            预计花费 ¥{estimate.low_cny}–¥{estimate.high_cny}
            (基于该流水线 {estimate.sample_count} 次历史运行,中位 ¥{estimate.typical_cny})
          </p>
        )}
        <Button type="submit" className="w-full" disabled={loading || !form.brandName}>
          {loading ? "提交中..." : "开始 AI 生产 →"}
        </Button>

        {/* Same red border/bg/text treatment as the job detail page's
            actionError card (approve/retry/save failures) — a failed job
            creation used to surface as a raw browser alert(), which is
            jarring and inconsistent with how the rest of the app reports
            request failures. */}
        {submitError && (
          <Card className="border-red-500/40 bg-red-500/5">
            <CardContent className="pt-4 pb-4">
              <p className="text-sm text-red-400">{submitError}</p>
            </CardContent>
          </Card>
        )}
      </form>
    </div>
  );
}
