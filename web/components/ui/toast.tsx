"use client";

// App-wide toast surface on Base UI's Toast primitives (installed since the
// UI kit landed but never mounted anywhere — roadmap 0.2 is its first real
// consumer: approval reminders / awaiting-approval notifications).
//
// Usage:
//   - <AppToastProvider> wraps the dashboard layout (once).
//   - Any client component calls `useToastManager().add({ title, description,
//     type })` — re-exported here so call sites import from one place.

import { Toast } from "@base-ui/react/toast";

// The package's value export lives on the Toast namespace object (its
// top-level `useToastManager` is type-only under isolatedModules).
export const useToastManager = Toast.useToastManager;

function ToastList() {
  const { toasts } = Toast.useToastManager();
  return (
    <>
      {toasts.map((t) => (
        <Toast.Root
          key={t.id}
          toast={t}
          className={`pointer-events-auto w-80 rounded-lg border p-3 shadow-lg bg-background ${
            t.type === "warning"
              ? "border-yellow-500/50"
              : t.type === "error"
              ? "border-red-500/50"
              : "border-border"
          }`}
        >
          <Toast.Title className="text-sm font-medium text-foreground" />
          <Toast.Description className="text-xs text-muted-foreground mt-0.5" />
          <Toast.Close
            className="absolute top-2 right-2 text-muted-foreground hover:text-foreground text-xs"
            aria-label="关闭通知"
          >
            ✕
          </Toast.Close>
        </Toast.Root>
      ))}
    </>
  );
}

export function AppToastProvider({ children }: { children: React.ReactNode }) {
  return (
    <Toast.Provider timeout={8000}>
      {children}
      <Toast.Portal>
        <Toast.Viewport className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 outline-none">
          <ToastList />
        </Toast.Viewport>
      </Toast.Portal>
    </Toast.Provider>
  );
}
