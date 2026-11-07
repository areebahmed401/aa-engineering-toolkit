import { ArrowRight, Cpu, Link2, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { EngineStatus } from "../components/EngineStatus";
import { LogoMark } from "../components/Logo";
import { Badge, cn, SECTION_META, Spinner } from "../components/ui";
import { BRAND_GOLD } from "../lib/brandColors";
import { useEngine } from "../lib/engine";

export function Home() {
  const { schema } = useEngine();
  if (!schema) return <div className="flex items-center gap-2 text-muted"><Spinner /> Loading…</div>;

  const sectionCount = Object.keys(schema.sections).length;

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <section className="relative overflow-hidden rounded-3xl border border-border bg-surface p-6 sm:p-8">
        <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full brand-gradient opacity-15 blur-3xl" />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-6">
          <LogoMark size={56} ink="currentColor" />
          <div className="space-y-2">
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
              <span className="aa-outline" style={{ color: BRAND_GOLD }}>AA</span> Engineering Toolkit
            </h1>
            <p className="max-w-2xl text-muted">
              Thermodynamics, fluids, structural, electrical and ASME calculations, running entirely in your browser.
              Every tool is validated against a cited textbook or standard.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Badge>{schema.tools.length} tools</Badge>
              <Badge>{sectionCount} disciplines</Badge>
              <EngineStatus />
            </div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {Object.entries(schema.sections).map(([id, name]) => {
          const meta = SECTION_META[id];
          const Icon = meta.icon;
          const tools = schema.tools.filter((t) => t.section === id);
          const soon = tools.length === 0;
          return (
            <div key={id} id={id} className={cn("card relative flex flex-col overflow-hidden p-5 pt-6", soon && "opacity-80")}>
              <div className={cn("absolute inset-x-0 top-0 h-[3px]", meta.color)} />
              <div className="mb-3 flex items-center gap-3">
                <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-white", meta.color)}>
                  <Icon className="h-5 w-5" />
                </span>
                <h2 className="font-semibold">{name}</h2>
                <Badge className="ml-auto">{soon ? "Soon" : tools.length}</Badge>
              </div>
              <p className="mb-4 text-sm text-muted">{meta.blurb}</p>
              {soon ? (
                <div className="rounded-lg border border-dashed border-border px-3 py-4 text-center text-sm italic text-muted">
                  Coming soon
                </div>
              ) : (
                <ul className="space-y-1">
                  {tools.map((t) => (
                    <li key={t.id}>
                      <Link
                        to={`/tool/${t.id}`}
                        className="group flex items-center justify-between rounded-lg px-2 py-1.5 text-sm transition hover:bg-bg focus-visible:bg-bg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                      >
                        {t.name}
                        <ArrowRight className="h-3.5 w-3.5 opacity-40 transition group-hover:translate-x-0.5 group-hover:opacity-100 group-focus-visible:translate-x-0.5 group-focus-visible:opacity-100" />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </section>

      <section className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {[
          { icon: Cpu, title: "Runs in your browser", text: "Python (Pyodide) runs locally. Nothing you enter leaves your device." },
          { icon: Link2, title: "Shareable calculations", text: "Copy a link that reproduces your inputs, or download a report." },
          { icon: ShieldCheck, title: "Validated", text: "Each tool has a test against a cited reference. Results are for preliminary design." },
        ].map(({ icon: I, title, text }) => (
          <div key={title} className="card p-3">
            <h3 className="mb-1 flex items-center gap-2 text-sm font-semibold">
              <I className="h-4 w-4 shrink-0 text-primary-ink" />
              {title}
            </h3>
            <p className="text-xs text-muted">{text}</p>
          </div>
        ))}
      </section>

      <p className="text-center text-xs text-muted">
        v{schema.version} · MIT licence · Preliminary design aid: verify results against the governing codes and standards.
      </p>
    </div>
  );
}
