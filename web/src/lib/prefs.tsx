// User preferences: unit system and colour theme (remembered in localStorage when available).
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { UnitSystem } from "./units";

type Theme = "light" | "dark";
type Prefs = { units: UnitSystem; setUnits: (u: UnitSystem) => void; theme: Theme; toggleTheme: () => void };

const PrefsContext = createContext<Prefs | null>(null);

function stored<T extends string>(key: string, fallback: T): T {
  try {
    return (localStorage.getItem(key) as T) || fallback;
  } catch {
    return fallback;
  }
}

function save(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* private mode: preference just isn't remembered */
  }
}

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [units, setUnitsState] = useState<UnitSystem>(() => stored<UnitSystem>("aa-units", "SI"));
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.classList.contains("dark") ? "dark" : "light",
  );

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  const value: Prefs = {
    units,
    setUnits: (u) => {
      setUnitsState(u);
      save("aa-units", u);
    },
    theme,
    toggleTheme: () =>
      setTheme((t) => {
        const next = t === "dark" ? "light" : "dark";
        save("aa-theme", next);
        return next;
      }),
  };
  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}

export function usePrefs(): Prefs {
  const ctx = useContext(PrefsContext);
  if (!ctx) throw new Error("usePrefs must be used inside PrefsProvider");
  return ctx;
}
