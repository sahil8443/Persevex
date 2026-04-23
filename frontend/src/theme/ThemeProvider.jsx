import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { applyTheme, getInitialTheme, THEME_STORAGE_KEY } from "./theme";

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    try {
      return getInitialTheme();
    } catch {
      return "light";
    }
  });

  useEffect(() => {
    applyTheme(theme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // ignore storage errors (private mode, policy, etc.)
    }
  }, [theme]);

  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === THEME_STORAGE_KEY && (e.newValue === "dark" || e.newValue === "light")) {
        setTheme(e.newValue);
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const value = useMemo(
    () => ({
      theme,
      setTheme,
      toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")),
      isDark: theme === "dark",
    }),
    [theme]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

