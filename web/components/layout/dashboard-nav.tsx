"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "项目" },
  { href: "/dashboard/library", label: "媒体库" },
  { href: "/dashboard/usage", label: "用量" },
  { href: "/dashboard/brands", label: "品牌库" },
  { href: "/dashboard/settings", label: "设置" },
];

// "/dashboard" itself also covers the new-project wizard and job-detail
// routes, which live under it but aren't separate nav entries — without this,
// exact-match-only would leave no nav item highlighted while on those pages.
function isNavActive(pathname: string, href: string): boolean {
  if (href === "/dashboard") {
    return pathname === "/dashboard" || pathname.startsWith("/dashboard/new") || pathname.startsWith("/dashboard/jobs");
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function DashboardNav() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-row md:flex-col gap-1 overflow-x-auto">
      {NAV.map((item) => {
        const active = isNavActive(pathname, item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "px-3 py-2 rounded-md text-sm transition-colors",
              active
                ? "bg-accent text-foreground font-medium"
                : "text-muted-foreground hover:text-foreground hover:bg-accent"
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
