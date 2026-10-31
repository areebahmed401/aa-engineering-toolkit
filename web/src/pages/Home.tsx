import { ArrowRight, Cpu, Link2, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { EngineStatus } from "../components/EngineStatus";
import { LogoMark } from "../components/Logo";
import { cn, SECTION_META, Spinner } from "../components/ui";
import { useEngine } from "../lib/engine";

export function Home() {
  const { schema } = useEngine();
  if (!schema) return <div className="flex items-center gap-2 text-muted"><Spinner /> Loading…</div>;

  return (
    <div className="mx-auto max-w-6xl space-y-10">
      <section className="relative overflow-hidden rounded-3xl border border-border bg-surface p-8 sm:p-12">
        <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full brand-gradient opacity-15 blur-3xl" />
        <div className="relative flex flex-col gap-6 sm:flex-row sm:items-center">
          <LogoMark size={72} />
          <div className="space-y-3">
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
              <span className="bg-clip-text text-transparent brand-gradient">AA</span> Engineering Toolkit
            </h1>
            <p className="max-w-2xl text-muted">
              Thermodynamics, fluids, structural, electrical and ASME calculations, running entirely in your browser.
              Every tool is validated against a cited textbook or standard.
            </p>
            <EngineStatus />
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {Object.entries(schema.sections).map(([id, name]) => {
          const meta = SECTION_META[id];
          const Icon = meta.icon;
          const tools = schema.tools.filter((t) => t.section === id);
          return (
            <div key={id} id={id} className="card flex flex-col p-5">
              <div className="mb-3 flex items-center gap-3">
                <span className={cn("flex h-9 w-9 items-center justify-center rounded-xl text-white", meta.color)}>
                  <Icon className="h-5 w-5" />
                </span>
                <div>
                  <h2 className="font-semibold">{name}</h2>
                  <p className="text-xs text-muted">{tools.length ? `${tools.length} tools` : "Coming soon"}</p>
                </div>
              </div>
              <p className="mb-4 text-sm text-muted">{meta.blurb}</p>
              <ul className="mt-auto space-y-1">
                {tools.map((t) => (
                  <li key={t.id}>
                    <Link to={`/tool/${t.id}`} className="group flex items-center justify-between rounded-lg px-2 py-1.5 text-sm hover:bg-bg">
                      {t.name}
                      <ArrowRight className="h-3.5 w-3.5 text-muted opacity-0 transition group-hover:opacity-100" />
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </section>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {[
          { icon: Cpu, title: "Runs in your browser", text: "Python (Pyodide) runs locally. Nothing you enter leaves your device." },
          { icon: Link2, title: "Shareable calculations", text: "Copy a link that reproduces your inputs, or download a report." },
          { icon: ShieldCheck, title: "Validated", text: "Each tool has a test against a cited reference. Results are for preliminary design." },
        ].map(({ icon: I, title, text }) => (
          <div key={title} className="card p-5">
            <I className="mb-2 h-5 w-5 text-primary" />
            <h3 className="mb-1 text-sm font-semibold">{title}</h3>
            <p className="text-sm text-muted">{text}</p>
          </div>
        ))}
      </section>

      <p className="text-center text-xs text-muted">
        v{schema.version} · MIT licence · Preliminary design aid: verify results against the governing codes and standards.
      </p>
    </div>
  );
}
