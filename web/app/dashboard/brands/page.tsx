"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
// Everything here goes through lib/api's apiRequest and branches on `ok`
// explicitly. The previous raw-fetch version only caught NETWORK failures
// (which throw) — an HTTP-level failure like a 404/422 on the PATCH resolved
// normally, was never checked, and fell straight through to the "close the
// form" success path, silently discarding the user's edits (audit 2026-07-15,
// BUG-12). apiRequest also sends credentials, required once the backend
// enforces the session token.
import { SERVER, apiRequest } from "@/lib/api";

type BrandKit = {
  kit_id: string;
  brand_name: string;
  slogan: string;
  industry: string;
  tone_keywords: string[];
  color_palette: string[];
  target_audience: string;
  logo_url: string;
  style_notes: string;
  voice_id?: string;
  colors?: { bg?: string; fg?: string; accent?: string; text?: string };
  logo_light_url?: string;
  logo_dark_url?: string;
  reference_image_path?: string;
  updated_at: number;
};

export default function BrandsPage() {
  const [kits, setKits] = useState<BrandKit[]>([]);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<BrandKit | null>(null);
  const [form, setForm] = useState(emptyForm());
  const [saving, setSaving] = useState(false);
  const [refImageFile, setRefImageFile] = useState<File | null>(null);
  const [refImagePreview, setRefImagePreview] = useState<string | null>(null);
  // The backend always writes a re-uploaded reference image to the same
  // fixed relative path, so a fresh upload returns a byte-identical URL to
  // the one already in state — the <img> never re-fetches. Bumping this on
  // every successful upload gives the <img src> a query param that changes
  // even when the underlying path doesn't.
  const [refImageVersion, setRefImageVersion] = useState(0);
  const [uploadingRefImage, setUploadingRefImage] = useState(false);
  const [refImageError, setRefImageError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  function emptyForm() {
    return {
      brand_name: "", slogan: "", industry: "",
      tone_keywords: "", color_palette: "", target_audience: "",
      logo_url: "", style_notes: "",
      voice_id: "", logo_light_url: "", logo_dark_url: "",
      color_bg: "", color_fg: "", color_accent: "", color_text: "",
    };
  }

  async function load(): Promise<boolean> {
    const res = await apiRequest("/brands");
    if (res.ok) setKits(res.data.brand_kits ?? []);
    return res.ok;
  }

  // Async fetch: setState happens after await, not synchronously in the effect.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(); }, []);

  function startCreate() {
    setForm(emptyForm());
    setEditing(null);
    setCreating(true);
    setRefImageFile(null);
    setRefImagePreview(null);
    setRefImageVersion(0);
    setRefImageError(null);
    setSaveError(null);
  }

  function startEdit(kit: BrandKit) {
    setForm({
      brand_name: kit.brand_name,
      slogan: kit.slogan,
      industry: kit.industry,
      tone_keywords: kit.tone_keywords.join(", "),
      color_palette: kit.color_palette.join(", "),
      target_audience: kit.target_audience,
      logo_url: kit.logo_url,
      style_notes: kit.style_notes,
      voice_id: kit.voice_id ?? "",
      logo_light_url: kit.logo_light_url ?? "",
      logo_dark_url: kit.logo_dark_url ?? "",
      color_bg: kit.colors?.bg ?? "",
      color_fg: kit.colors?.fg ?? "",
      color_accent: kit.colors?.accent ?? "",
      color_text: kit.colors?.text ?? "",
    });
    setEditing(kit);
    setCreating(true);
    setRefImageFile(null);
    setRefImagePreview(kit.reference_image_path ? `${SERVER}/brand-media/${kit.kit_id}/${kit.reference_image_path}` : null);
    setRefImageVersion(0);
    setRefImageError(null);
    setSaveError(null);
  }

  async function handleUploadReferenceImage() {
    if (!editing || !refImageFile) return;
    setUploadingRefImage(true);
    setRefImageError(null);
    const body = new FormData();
    body.append("file", refImageFile);
    const res = await apiRequest(`/brands/${editing.kit_id}/reference-image`, {
      method: "POST",
      body,
    });
    if (!res.ok) {
      // Surface the backend's specific reason (file too large / not an
      // image) instead of a generic retry message that hides it.
      setRefImageError(`上传失败：${res.detail}`);
    } else {
      setRefImagePreview(`${SERVER}${res.data.reference_image_url}`);
      setRefImageVersion((v) => v + 1);
      setRefImageFile(null);
    }
    setUploadingRefImage(false);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaveError(null);
    const { color_bg, color_fg, color_accent, color_text, ...rest } = form;
    const roleColors = Object.fromEntries(
      Object.entries({ bg: color_bg, fg: color_fg, accent: color_accent, text: color_text })
        .filter(([, v]) => v.trim())
    );
    const payload = {
      ...rest,
      colors: roleColors,
      tone_keywords: form.tone_keywords.split(",").map((s) => s.trim()).filter(Boolean),
      color_palette: form.color_palette.split(",").map((s) => s.trim()).filter(Boolean),
    };
    try {
      if (editing) {
        const res = await apiRequest(`/brands/${editing.kit_id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          // Keep the form open with the user's edits — a 404 (kit deleted
          // in another tab) or 422 previously fell through to the success
          // path and silently discarded them.
          setSaveError(`保存失败：${res.detail}`);
          return;
        }
      } else {
        const createRes = await apiRequest("/brands", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!createRes.ok) {
          setSaveError(`创建失败：${createRes.detail}`);
          return;
        }
        if (refImageFile) {
          // Immediately follow up with the reference-image upload so the
          // whole thing reads as one atomic "create brand kit with
          // reference image" action to the user, instead of two separate
          // steps they'd otherwise have to discover (create, then re-open
          // to attach an image).
          const newKit: BrandKit = createRes.data;
          const uploadBody = new FormData();
          uploadBody.append("file", refImageFile);
          const uploadRes = await apiRequest(`/brands/${newKit.kit_id}/reference-image`, {
            method: "POST",
            body: uploadBody,
          });
          if (!uploadRes.ok) {
            // The kit itself was created successfully — don't roll that
            // back or silently swallow the follow-up failure. Drop into
            // edit mode for the new kit so the error stays visible and a
            // retry (via the now-available upload button, or a plain
            // re-save) acts on the existing kit instead of creating a
            // duplicate.
            setSaveError("品牌 Kit 已创建，但参考图上传失败，请重试上传");
            setEditing(newKit);
            await load();
            return;
          }
        }
      }
      if (!(await load())) {
        // Saved, but the list refresh failed — keep the form open with an
        // honest message rather than closing onto a stale list.
        setSaveError("已保存，但刷新列表失败，请手动刷新页面");
        return;
      }
      setCreating(false);
      setEditing(null);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(kit_id: string) {
    if (!confirm("确定删除？")) return;
    setListError(null);
    const res = await apiRequest(`/brands/${kit_id}`, { method: "DELETE" });
    if (!res.ok) {
      setListError(`删除失败：${res.detail}`);
      return;
    }
    if (!(await load())) setListError("已删除，但刷新列表失败，请手动刷新页面");
  }

  return (
    <div className="p-8 max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">品牌库</h1>
          <p className="text-muted-foreground text-sm mt-1">保存品牌资产，AI 自动引用生成风格一致的视频</p>
        </div>
        {!creating && (
          <Button onClick={startCreate}>+ 新建品牌 Kit</Button>
        )}
      </div>

      {/* Create / Edit form */}
      {creating && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{editing ? "编辑品牌 Kit" : "新建品牌 Kit"}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSave} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium block mb-1.5">品牌名称 *</label>
                  <Input required value={form.brand_name} onChange={(e) => setForm(f => ({ ...f, brand_name: e.target.value }))} placeholder="小狗牌咖啡机" />
                </div>
                <div>
                  <label className="text-sm font-medium block mb-1.5">行业</label>
                  <Input value={form.industry} onChange={(e) => setForm(f => ({ ...f, industry: e.target.value }))} placeholder="消费电子 / 快消 / 科技…" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium block mb-1.5">Slogan</label>
                  <Input value={form.slogan} onChange={(e) => setForm(f => ({ ...f, slogan: e.target.value }))} placeholder="好咖啡，不只属于咖啡馆" />
                </div>
                <div>
                  <label className="text-sm font-medium block mb-1.5" htmlFor="bk-logo">Logo URL</label>
                  <Input id="bk-logo" value={form.logo_url} onChange={(e) => setForm(f => ({ ...f, logo_url: e.target.value }))} placeholder="https://…/logo.png" />
                </div>
                <div>
                  <label className="text-sm font-medium block mb-1.5" htmlFor="bk-voice">品牌旁白音色 voice_id</label>
                  <Input id="bk-voice" value={form.voice_id} onChange={(e) => setForm(f => ({ ...f, voice_id: e.target.value }))} placeholder="例如 qwen3-tts-flash:cherry — 同品牌所有视频用同一旁白" />
                </div>
                <div>
                  <label className="text-sm font-medium block mb-1.5" htmlFor="bk-logo-light">浅色场景 Logo URL</label>
                  <Input id="bk-logo-light" value={form.logo_light_url} onChange={(e) => setForm(f => ({ ...f, logo_light_url: e.target.value }))} placeholder="深色 logo,用于浅色背景" />
                </div>
                <div>
                  <label className="text-sm font-medium block mb-1.5" htmlFor="bk-logo-dark">深色场景 Logo URL</label>
                  <Input id="bk-logo-dark" value={form.logo_dark_url} onChange={(e) => setForm(f => ({ ...f, logo_dark_url: e.target.value }))} placeholder="浅色 logo,用于深色背景" />
                </div>
                <div className="sm:col-span-2">
                  <span className="text-sm font-medium block mb-1.5">角色化品牌色(渲染器按角色取用,而非猜测)</span>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {([["color_bg", "背景 bg"], ["color_fg", "前景 fg"], ["color_accent", "强调 accent"], ["color_text", "正文 text"]] as const).map(([key, label]) => (
                      <div key={key}>
                        <label className="text-xs text-muted-foreground block mb-1" htmlFor={`bk-${key}`}>{label}</label>
                        <Input id={`bk-${key}`} value={form[key]} onChange={(e) => setForm(f => ({ ...f, [key]: e.target.value }))} placeholder="#RRGGBB" />
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium block mb-1.5">情感关键词（逗号分隔）</label>
                  <Input value={form.tone_keywords} onChange={(e) => setForm(f => ({ ...f, tone_keywords: e.target.value }))} placeholder="温暖, 仪式感, 品质" />
                </div>
                <div>
                  <label className="text-sm font-medium block mb-1.5">品牌色彩（Hex，逗号分隔）</label>
                  <Input value={form.color_palette} onChange={(e) => setForm(f => ({ ...f, color_palette: e.target.value }))} placeholder="#1A1A1A, #C8A96E, #F5F0E8" />
                </div>
              </div>
              <div>
                <label className="text-sm font-medium block mb-1.5">目标受众</label>
                <Input value={form.target_audience} onChange={(e) => setForm(f => ({ ...f, target_audience: e.target.value }))} placeholder="25-40 岁都市白领，注重生活品质" />
              </div>
              <div>
                <label className="text-sm font-medium block mb-1.5">风格备注</label>
                <Textarea rows={2} value={form.style_notes} onChange={(e) => setForm(f => ({ ...f, style_notes: e.target.value }))} placeholder="慢镜头、暖调、微距特写、无旁白…" />
              </div>
              {/* Rendered in both create and edit mode now — the upload
                endpoint needs an existing kit_id, so in create mode the
                manual "上传参考图" button (which calls
                handleUploadReferenceImage, requiring `editing`) is swapped
                for a hint that the file will be attached automatically once
                the kit is saved; see the create branch of handleSave. */}
              <div>
                <label className="text-sm font-medium block mb-1.5">参考图</label>
                <div className="flex items-center gap-3">
                  {refImagePreview && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={refImageVersion > 0 ? `${refImagePreview}?t=${refImageVersion}` : refImagePreview}
                      alt="参考图预览"
                      className="w-24 h-24 object-cover rounded border border-border"
                    />
                  )}
                  <div className="flex flex-col gap-2 items-start">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => setRefImageFile(e.target.files?.[0] ?? null)}
                      className="text-xs"
                    />
                    {editing ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={!refImageFile || uploadingRefImage}
                        onClick={handleUploadReferenceImage}
                      >
                        {uploadingRefImage ? "上传中…" : "上传参考图"}
                      </Button>
                    ) : (
                      refImageFile && (
                        <p className="text-xs text-muted-foreground">将在保存品牌 Kit 时自动上传</p>
                      )
                    )}
                    {refImageError && <p className="text-xs text-destructive">{refImageError}</p>}
                  </div>
                </div>
              </div>
              {saveError && <p className="text-xs text-destructive">{saveError}</p>}
              <div className="flex gap-3 pt-2">
                <Button type="submit" disabled={saving}>{saving ? "保存中…" : "保存"}</Button>
                <Button type="button" variant="outline" onClick={() => { setCreating(false); setEditing(null); }}>取消</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {listError && <p className="text-xs text-destructive">{listError}</p>}

      {/* Kit list */}
      {kits.length === 0 && !creating && (
        <div className="flex flex-col items-center justify-center h-48 border border-dashed border-border rounded-lg gap-3">
          <p className="text-muted-foreground text-sm">还没有品牌 Kit</p>
          <Button variant="outline" onClick={startCreate}>创建第一个</Button>
        </div>
      )}

      <div className="space-y-3">
        {kits.map((kit) => (
          <Card key={kit.kit_id} className="hover:border-foreground/20 transition-colors">
            <CardContent className="pt-4 pb-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-semibold text-sm">{kit.brand_name}</h3>
                    {kit.industry && (
                      <span className="text-xs text-muted-foreground border border-border rounded px-1.5 py-0.5">{kit.industry}</span>
                    )}
                  </div>
                  {kit.slogan && (
                    <p className="text-xs text-muted-foreground mt-0.5 italic">&ldquo;{kit.slogan}&rdquo;</p>
                  )}
                  <div className="flex gap-3 mt-2 flex-wrap items-center">
                    {kit.tone_keywords.slice(0, 4).map((k) => (
                      <span key={k} className="text-xs bg-muted px-2 py-0.5 rounded-full">{k}</span>
                    ))}
                    {kit.tone_keywords.length > 4 && (
                      <span className="text-xs text-muted-foreground">+{kit.tone_keywords.length - 4}</span>
                    )}
                    {kit.color_palette.slice(0, 4).map((c) => (
                      <span
                        key={c}
                        className="w-4 h-4 rounded-full border border-border inline-block"
                        style={{ backgroundColor: c }}
                        title={c}
                      />
                    ))}
                    {kit.color_palette.length > 4 && (
                      <span
                        className="text-xs text-muted-foreground"
                        title={`还有 ${kit.color_palette.length - 4} 个颜色`}
                      >
                        +{kit.color_palette.length - 4}
                      </span>
                    )}
                  </div>
                  {kit.target_audience && (
                    <p className="text-xs text-muted-foreground mt-1.5">受众：{kit.target_audience}</p>
                  )}
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button size="sm" variant="outline" onClick={() => startEdit(kit)}>编辑</Button>
                  <Button size="sm" variant="outline" className="text-destructive border-destructive/40 hover:bg-destructive/10" onClick={() => handleDelete(kit.kit_id)}>删除</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
