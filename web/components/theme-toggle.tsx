"use client";

// Light/dark theme toggle (roadmap 3.6): the light tokens have been sitting
// in globals.css (:root) all along while the root layout hardcodes the
// `dark` class. This toggles the class on <html> and remembers the choice —
// no dependency, no touching the root layout.

import { useEffect, useState } from "react";

const STORAGE_KEY = "om-theme";

export function ThemeToggle() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") {
      setTheme(saved);
      document.documentElement.classList.toggle("dark", saved === "dark");
    }
  }, []);

  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.classList.toggle("dark", next === "dark");
    window.localStorage.setItem(STORAGE_KEY, next);
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={theme === "dark" ? "切换到浅色主题" : "切换到深色主题"}
      className="px-3 py-2 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-accent text-left"
    >
      {theme === "dark" ? "☀ 浅色主题" : "🌙 深色主题"}
    </button>
  );
}
