"use client";

// Cross-project media library (roadmap 3.3): every asset_manifest entry
// (prompt/model/cost/provenance) aggregated and searchable.

import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { mediaUrl } from "@/components/job-status";
import { SERVER, apiRequest } from "@/lib/api";

type LibraryAsset = {
  project: string;
  id: string | null;
  type: string | null;
  path: string;
  media_url: string | null;
  prompt: string | null;
  model: string | null;
  cost_usd: number | null;
};

export default function LibraryPage() {
  const [assets, setAssets] = useState<LibraryAsset[]>([]);
  const [projects, setProjects] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [project, setProject] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (project) params.set("project", project);
    const t = setTimeout(() => {
      apiRequest(`/library/assets?${params.toString()}`).then((r) => {
        if (r.ok) {
          setAssets(r.data.assets ?? []);
          setProjects(r.data.projects ?? []);
          setTotal(r.data.total ?? 0);
        }
        setLoading(false);
      });
    }, 250);   // debounce typing
    return () => clearTimeout(t);
  }, [q, project]);

  return (
    <div className="p-4 md:p-8 max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">媒体库</h1>
        <p className="text-muted-foreground text-sm mt-1">
          跨项目的生成素材索引(提示词 / 模型 / 成本 / 来源),共 {total} 条
        </p>
      </div>
      <div className="flex flex-col sm:flex-row gap-2">
        <label className="sr-only" htmlFor="library-search">搜索素材</label>
        <Input
          id="library-search"
          placeholder="按提示词 / 模型 / 项目搜索…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="sm:max-w-sm"
        />
        <label className="sr-only" htmlFor="library-project">按项目筛选</label>
        <select
          id="library-project"
          className="bg-muted/40 border border-border rounded px-2 py-1.5 text-sm"
          value={project}
          onChange={(e) => setProject(e.target.value)}
        >
          <option value="">全部项目</option>
          {projects.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : assets.length === 0 ? (
        <p className="text-sm text-muted-foreground border border-dashed border-border rounded-lg p-8 text-center">
          没有匹配的素材
        </p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {assets.map((a, i) => {
            const url = mediaUrl(SERVER, a.media_url);
            const isImage = (a.type ?? "").includes("image") || /\.(png|jpe?g|webp)$/i.test(a.path);
            const isVideo = (a.type ?? "").includes("video") || /\.(mp4|webm|mov)$/i.test(a.path);
            return (
              <div key={`${a.project}-${a.id}-${i}`} className="bg-muted/40 rounded-md overflow-hidden">
                {url && isImage ? (
                  <img src={url} alt={a.prompt ?? a.path} className="w-full h-28 object-cover bg-black" loading="lazy" />
                ) : url && isVideo ? (
                  <video src={url} muted preload="metadata" controls className="w-full h-28 object-cover bg-black" />
                ) : (
                  <div className="w-full h-28 flex items-center justify-center text-2xl bg-muted/60" aria-hidden>🎵</div>
                )}
                <div className="p-2 space-y-0.5">
                  <p className="text-[11px] truncate" title={a.prompt ?? ""}>{a.prompt || a.path.split("/").pop()}</p>
                  <p className="text-[10px] text-muted-foreground truncate">
                    {[a.project, a.model, a.cost_usd != null ? `¥${a.cost_usd.toFixed(2)}` : null]
                      .filter(Boolean).join(" · ")}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
