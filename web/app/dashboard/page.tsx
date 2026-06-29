import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

// Mock projects for the vertical slice — replaced by DB query in M1-7
const MOCK_PROJECTS = [
  {
    id: "puppy-coffee-machine",
    name: "小狗牌咖啡机",
    contentType: "营销宣传片",
    status: "COMPLETED",
    updatedAt: "2026-06-28",
    thumb: null,
  },
];

const STATUS_LABEL: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  DRAFT:             { label: "草稿",   variant: "outline" },
  RUNNING:           { label: "生成中", variant: "default" },
  AWAITING_APPROVAL: { label: "待审批", variant: "secondary" },
  COMPLETED:         { label: "已完成", variant: "default" },
  FAILED:            { label: "失败",   variant: "destructive" },
};

export default function DashboardPage() {
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

      {MOCK_PROJECTS.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 border border-dashed border-border rounded-lg gap-4">
          <p className="text-muted-foreground text-sm">还没有项目</p>
          <Link href="/dashboard/new">
            <Button variant="outline">创建第一个视频</Button>
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {MOCK_PROJECTS.map((p) => {
            const s = STATUS_LABEL[p.status] ?? { label: p.status, variant: "outline" as const };
            return (
              <Link key={p.id} href={`/dashboard/jobs/${p.id}`}>
                <Card className="hover:border-foreground/30 transition-colors cursor-pointer h-full">
                  <div className="aspect-video bg-muted rounded-t-lg flex items-center justify-center">
                    <span className="text-muted-foreground text-xs">预览</span>
                  </div>
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <CardTitle className="text-base leading-tight">{p.name}</CardTitle>
                      <Badge variant={s.variant} className="shrink-0 text-xs">{s.label}</Badge>
                    </div>
                    <CardDescription className="text-xs">{p.contentType}</CardDescription>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <p className="text-xs text-muted-foreground">{p.updatedAt}</p>
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
