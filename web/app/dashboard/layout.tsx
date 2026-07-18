import { Separator } from "@/components/ui/separator";
import { DashboardNav } from "@/components/layout/dashboard-nav";
import { AppToastProvider } from "@/components/ui/toast";
import { ThemeToggle } from "@/components/theme-toggle";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppToastProvider>
      <div className="flex flex-col md:flex-row h-screen bg-background">
        {/* Sidebar */}
        <aside className="w-full md:w-56 shrink-0 border-b md:border-b-0 md:border-r border-border flex flex-col py-6 px-4 gap-6">
          <div className="px-2">
            <span className="text-lg font-bold tracking-tight text-foreground">xSmartCut</span>
            <p className="text-xs text-muted-foreground mt-0.5">AI 视频生产平台</p>
          </div>
          <Separator />
          <DashboardNav />
          <div className="mt-auto">
            <ThemeToggle />
          </div>
        </aside>

        {/* Main */}
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </AppToastProvider>
  );
}
