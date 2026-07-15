import { useEffect, useState } from "react";

export function getStoredTheme() {
  if (typeof window === "undefined") {
    return "dark";
  }
  return window.localStorage.getItem("app-theme") || "dark";
}

export function applyTheme(theme) {
  if (typeof window === "undefined") {
    return;
  }
  document.documentElement.dataset.theme = theme;
  window.localStorage.setItem("app-theme", theme);
}

export function useThemePreference() {
  const [theme, setTheme] = useState(getStoredTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  return { theme, setTheme };
}
