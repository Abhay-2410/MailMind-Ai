import type { ThemePreference } from "@/types/settings";

const STORAGE_KEY = "mailmind-theme";

export function getStoredTheme(): ThemePreference | null {
  const value = localStorage.getItem(STORAGE_KEY);
  if (value === "light" || value === "dark" || value === "system") {
    return value;
  }
  return null;
}

export function storeTheme(theme: ThemePreference): void {
  localStorage.setItem(STORAGE_KEY, theme);
}

function systemPrefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function resolveIsDark(theme: ThemePreference): boolean {
  if (theme === "dark") return true;
  if (theme === "light") return false;
  return systemPrefersDark();
}

export function applyTheme(theme: ThemePreference): void {
  const root = document.documentElement;
  const isDark = resolveIsDark(theme);
  root.classList.toggle("dark", isDark);
  root.style.colorScheme = isDark ? "dark" : "light";
  storeTheme(theme);
}
