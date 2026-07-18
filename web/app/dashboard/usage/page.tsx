"use client";

// Usage rollup (roadmap 3.1): spend by pipeline / project / tool. Nobody
// pays monthly for a system that can't tell them where the money went.

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiRequest } from "@/lib/api";

type Bucket = { jobs?: number; calls?: number; cost_cny: number };
type Usage = {
  total_cny: number;
  by_pipeline: Record<string, Bucket>;
  by_project: Record<string, Bucket>;
  by_tool: Record<string, Bucket>;
};

function BucketTable({ title, unit, data }: { title: string; unit: string; data: Record<string, Bucket> }) {
  const rows = Object.entries(data).sort((a, b) => b[1].cost_cny - a[1].cost_cny);
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm text-muted-foreground font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="text-xs text-muted-foreground">暂无数据</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-muted-foreground text-left">
                <th className="pb-2 font-medium">名称</th>
                <th className="pb-2 font-medium text-right">{unit}</th>
                <th className="pb-2 font-medium text-right">花费</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([name, b]) => (
                <tr key={name} className="border-t border-border/60">
                  <td className="py-1.5 pr-2 break-all">{name}</td>
                  <td className="py-1.5 text-right text-muted-foreground">{b.jobs ?? b.calls ?? 0}</td>
                  <td className="py-1.5 text-right font-mono">¥{b.cost_cny.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

export default function UsagePage() {
  const [usage, setUsage] = useState<Usage | null>(null);
  useEffect(() => {
    apiRequest("/system/usage").then((r) => {
      if (r.ok) setUsage(r.data);
    });
  }, []);

  return (
    <div className="p-4 md:p-8 max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">用量与花费</h1>
        <p className="text-muted-foreground text-sm mt-1">
          按流水线 / 项目 / 工具的真实支出(来自任务账本与逐条成本日志)
        </p>
      </div>
      {usage == null ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : (
        <>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">累计花费</p>
              <p className="text-3xl font-bold font-mono mt-1">¥{usage.total_cny.toFixed(2)}</p>
            </CardContent>
          </Card>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <BucketTable title="按流水线" unit="任务数" data={usage.by_pipeline} />
            <BucketTable title="按项目" unit="任务数" data={usage.by_project} />
          </div>
          <BucketTable title="按工具(逐条成本日志)" unit="调用数" data={usage.by_tool} />
        </>
      )}
    </div>
  );
}
