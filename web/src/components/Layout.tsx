import { Github, Menu, Moon, Search, Sun, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useEngine } from "../lib/engine";
import { usePrefs } from "../lib/prefs";
import { EngineStatus } from "./EngineStatus";
import { Wordmark } from "./Logo";
import { cn, SECTION_META } from "./ui";

const REPO = "https://github.com/areebahmed401/aa-engineering-toolkit";

const HEADER_BTN = "btn border border-white/15 p-2 text-white hover:bg-white/10";

export function Layout() {
  const { schema } = useEngine();
  const { units, setUnits, theme, toggleTheme } = usePrefs();
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  const sections = schema?.sections ?? {};
  const toolsBySection = useMemo(() => {
    const q = query.trim().toLowerCase();
    const out: Record<string, NonNullable<typeof schema>["tools"]> = {};
    for (const t of schema?.tools ?? []) {
      const hay = `${t.name} ${t.description} ${t.tags.join(" ")}`.toLowerCase();
      if (q && !hay.includes(q)) continue;
      (out[t.section] ??= []).push(t);
    }
    return out;
  }, [schema, query]);

  const sidebar = (
    <nav className="flex h-full flex-col gap-5 overflow-y-auto p-4" onClick={() => setMenuOpen(false)}>
      <label className="relative block" onClick={(e) => e.stopPropagation()}>
        <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted" />
        <input className="input pl-9" placeholder="Search tools…" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search tools" />
      </label>
      {Object.entries(sections).map(([id, name]) => {
        const meta = SECTION_META[id];
        const Icon = meta?.icon;
        const tools = toolsBySection[id] ?? [];
        return (
          <div key={id}>
            <div className="mb-1.5 flex items-center gap-2 px-2 text-xs font-semibold uppercase tracking-wide text-muted">
              {Icon && <Icon className={cn("h-3.5 w-3.5", meta.text)} />}
              {name}
            </div>
            {tools.length === 0 ? (
              <p className="px-2 text-xs italic text-muted">{query ? "No matches" : "Coming soon"}</p>
            ) : (
              <ul className="space-y-0.5">
                {tools.map((t) => (
                  <li key={t.id}>
                    <NavLink
                      to={`/tool/${t.id}`}
                      className={({ isActive }) =>
                        cn(
                          "block rounded-lg px-2 py-1.5 text-sm transition",
                          isActive ? "border-l-2 border-primary bg-primary/15 font-medium text-ink" : "border-l-2 border-transparent text-ink hover:bg-bg",
                        )
                      }
                    >
                      {t.name}
                    </NavLink>
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
      <a href={`${import.meta.env.BASE_URL}docs/`} className="rounded-lg px-2 py-1.5 text-sm text-ink hover:bg-bg md:hidden">
        Docs
      </a>
    </nav>
  );

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-black/40 bg-header text-white">
        <div className="flex h-14 items-center gap-3 px-4">
          <button className={HEADER_BTN + " lg:hidden"} onClick={() => setMenuOpen((o) => !o)} aria-label="Toggle menu">
            {menuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
          <Link to="/" className="shrink-0">
            <Wordmark />
          </Link>
          <nav className="ml-4 hidden items-center gap-1 md:flex">
            {Object.entries(sections).map(([id, name]) => {
              const first = toolsBySection[id]?.[0];
              const active = location.pathname.includes(`/tool/${id}.`);
              return (
                <Link
                  key={id}
                  to={first ? `/tool/${first.id}` : `/#${id}`}
                  className={cn("rounded-lg px-3 py-1.5 text-sm transition", active ? "bg-white/10 text-white" : "text-white/70 hover:text-white")}
                >
                  {name.split(" ")[0]}
                </Link>
              );
            })}
            <a href={`${import.meta.env.BASE_URL}docs/`} className="rounded-lg px-3 py-1.5 text-sm text-white/70 transition hover:text-white">
              Docs
            </a>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <div className="hidden sm:block">
              <EngineStatus compact />
            </div>
            <div className="flex rounded-lg border border-white/15 p-0.5 text-xs" role="group" aria-label="Unit system">
              {(["SI", "Imperial"] as const).map((u) => (
                <button
                  key={u}
                  className={cn("rounded-md px-2 py-1 transition", units === u ? "bg-primary text-on-primary" : "text-white/70 hover:text-white")}
                  onClick={() => setUnits(u)}
                  aria-pressed={units === u}
                >
                  {u}
                </button>
              ))}
            </div>
            <button className={HEADER_BTN} onClick={toggleTheme} aria-label="Toggle dark mode">
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <a className={HEADER_BTN + " hidden sm:inline-flex"} href={REPO} target="_blank" rel="noreferrer" aria-label="Source on GitHub">
              <Github className="h-4 w-4" />
            </a>
          </div>
        </div>
      </header>

      <div className="flex flex-1">
        <aside className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-64 shrink-0 border-r border-border bg-surface lg:block">{sidebar}</aside>
        {menuOpen && (
          <div className="fixed inset-0 top-14 z-20 bg-ink/30 lg:hidden" onClick={() => setMenuOpen(false)}>
            <aside className="h-full w-72 border-r border-border bg-surface" onClick={(e) => e.stopPropagation()}>
              {sidebar}
            </aside>
          </div>
        )}
        <main className="min-w-0 flex-1 px-4 py-6 sm:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
