import { ChevronDown, Github, Menu, Moon, PanelLeftClose, PanelLeftOpen, Search, Sun, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useEngine } from "../lib/engine";
import { buildNav } from "../lib/nav";
import { usePrefs } from "../lib/prefs";
import { EngineStatus } from "./EngineStatus";
import { Wordmark } from "./Logo";
import { cn, SECTION_META } from "./ui";

const REPO = "https://github.com/areebahmed401/aa-engineering-toolkit";

const HEADER_BTN = "btn border border-white/15 p-2 text-white hover:bg-white/10";

const OPEN_KEY = "aa-sidebar-open";

function loadOpen(): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(OPEN_KEY) ?? "{}") as Record<string, boolean>;
  } catch {
    return {};
  }
}

function saveOpen(state: Record<string, boolean>) {
  try {
    localStorage.setItem(OPEN_KEY, JSON.stringify(state));
  } catch {
    /* private mode: just not remembered */
  }
}

export function Layout() {
  const { schema } = useEngine();
  const { units, setUnits, theme, toggleTheme, sidebarCollapsed, setSidebarCollapsed } = usePrefs();
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  const sections = schema?.sections ?? {};
  const tools = schema?.tools ?? [];
  const nav = useMemo(() => buildNav(schema?.tools ?? [], query), [schema, query]);
  const firstTool = (id: string) => tools.find((t) => t.section === id);
  const searching = query.trim() !== "";

  // Which sections are expanded (remembered); the section holding the current route opens on navigation.
  const [openState, setOpenState] = useState<Record<string, boolean>>(loadOpen);
  const setOpen = (id: string, open: boolean) =>
    setOpenState((prev) => {
      const next = { ...prev, [id]: open };
      saveOpen(next);
      return next;
    });
  const currentSection = location.pathname.startsWith("/structural") ? "structural" : /^\/tool\/([a-z_]+)\./.exec(location.pathname)?.[1];
  useEffect(() => {
    if (currentSection) setOpenState((prev) => (prev[currentSection] === false ? { ...prev, [currentSection]: true } : prev));
  }, [currentSection]);

  // Ctrl/Cmd+B toggles the desktop panel (ignored while typing)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.altKey || e.key.toLowerCase() !== "b") return;
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable)) return;
      e.preventDefault();
      setSidebarCollapsed(!sidebarCollapsed);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sidebarCollapsed, setSidebarCollapsed]);

  const tab = new URLSearchParams(location.search).get("tab") ?? "section";
  const isActive = (to: string) => {
    const [path, search = ""] = to.split("?");
    if (location.pathname !== path) return false;
    return !search || new URLSearchParams(search).get("tab") === tab;
  };

  const sidebar = (
    <nav
      data-testid="sidebar"
      className="flex h-full flex-col gap-3 overflow-y-auto p-4"
      onClick={(e) => {
        if ((e.target as HTMLElement).closest("a")) setMenuOpen(false);
      }}
    >
      <div className="flex items-center gap-2">
        <label className="relative block min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted" />
          <input className="input pl-9" placeholder="Search tools…" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search tools" />
        </label>
        <button
          data-testid="sidebar-collapse"
          className="btn hidden shrink-0 p-2 text-muted hover:bg-bg hover:text-ink lg:inline-flex"
          onClick={() => setSidebarCollapsed(true)}
          aria-label="Collapse sidebar"
          title="Collapse sidebar (Ctrl+B)"
        >
          <PanelLeftClose className="h-4 w-4" />
        </button>
      </div>
      {Object.entries(sections).map(([id, name]) => {
        const meta = SECTION_META[id];
        const Icon = meta?.icon;
        const sec = nav[id];
        if (searching && !sec) return null;
        const open = searching || (openState[id] ?? true);
        const count = sec?.count ?? 0;
        return (
          <div key={id} data-testid={`sidebar-section-${id}`}>
            <button
              className="flex w-full items-center gap-2 rounded-lg px-2 py-1 text-xs font-semibold uppercase tracking-wide text-muted transition hover:bg-bg hover:text-ink"
              aria-expanded={open}
              aria-controls={`sidebar-panel-${id}`}
              onClick={() => !searching && setOpen(id, !open)}
            >
              {Icon && <Icon className={cn("h-3.5 w-3.5", meta.text)} />}
              <span className="flex-1 text-left">{name}</span>
              {count > 0 && <span className="rounded-full bg-bg px-1.5 py-0.5 text-[10px] font-medium normal-case tracking-normal">{count}</span>}
              <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", !open && "-rotate-90")} />
            </button>
            <div id={`sidebar-panel-${id}`} hidden={!open} className="mt-1">
              {!sec ? (
                <p className="px-2 text-xs italic text-muted">Coming soon</p>
              ) : (
                sec.groups.map((g) => (
                  <div key={g.label} className="mb-2">
                    <div className="px-2 pb-0.5 pt-1 text-[11px] font-medium text-muted">{g.label}</div>
                    <ul className="space-y-0.5">
                      {g.items.map((it) => (
                        <li key={it.key}>
                          <Link
                            to={it.to}
                            aria-current={isActive(it.to) ? "page" : undefined}
                            className={cn(
                              "block rounded-lg px-2 py-1.5 text-sm transition",
                              isActive(it.to) ? "border-l-2 border-primary bg-primary/15 font-medium text-ink" : "border-l-2 border-transparent text-ink hover:bg-bg",
                            )}
                          >
                            {it.label}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))
              )}
            </div>
          </div>
        );
      })}
      {searching && Object.keys(nav).length === 0 && <p className="px-2 text-xs italic text-muted">No matches</p>}
      <a href={`${import.meta.env.BASE_URL}docs/`} className="rounded-lg px-2 py-1.5 text-sm text-ink hover:bg-bg md:hidden">
        Docs
      </a>
    </nav>
  );

  const rail = (
    <div data-testid="sidebar-rail" className="flex h-full flex-col items-center gap-2 py-4">
      <button
        className="btn p-2 text-muted hover:bg-bg hover:text-ink"
        onClick={() => setSidebarCollapsed(false)}
        aria-label="Expand sidebar"
        title="Expand sidebar (Ctrl+B)"
      >
        <PanelLeftOpen className="h-4 w-4" />
      </button>
      {Object.entries(sections).map(([id, name]) => {
        const meta = SECTION_META[id];
        const Icon = meta?.icon;
        return (
          <button
            key={id}
            className={cn("btn p-2 hover:bg-bg", currentSection === id && "bg-primary/15")}
            title={name}
            aria-label={name}
            onClick={() => {
              setOpen(id, true);
              setSidebarCollapsed(false);
            }}
          >
            {Icon && <Icon className={cn("h-4 w-4", meta.text)} />}
          </button>
        );
      })}
    </div>
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
              const first = firstTool(id);
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
        <aside
          className={cn(
            "sticky top-14 hidden h-[calc(100vh-3.5rem)] shrink-0 overflow-hidden border-r border-border bg-surface transition-[width] duration-200 lg:block",
            sidebarCollapsed ? "w-14" : "w-64",
          )}
        >
          {sidebarCollapsed ? rail : sidebar}
        </aside>
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
