// Side panel of the pole-plan tab: verdict, counting criterion, statistics, contradictions, steps and pole table.
import { ChevronRight, CircleAlert, CircleCheck, TriangleAlert, Zap } from "lucide-react";
import { poleText, type PoleResult } from "../lib/polplan";
import { formatNumber } from "../lib/units";
import { cn } from "./ui";

function Stat({ label, value, testId, hint }: { label: string; value: string | number; testId: string; hint: string }) {
  return (
    <div className="rounded-xl border border-border bg-bg/50 px-3 py-2" data-testid={testId} title={hint}>
      <div className="text-xs text-muted">{label}</div>
      <div className="font-mono text-lg font-semibold">{value}</div>
    </div>
  );
}

export function PolePlanPanel({ result, stale }: { result: PoleResult; stale: boolean }) {
  const fmt = (v: number) => formatNumber(v, 4);
  const movable = result.movable;
  return (
    <div className={cn("space-y-4 transition-opacity", stale && "opacity-60")} data-testid="results">
      <div className={cn("flex items-start gap-2 rounded-xl border p-3 text-sm font-semibold", movable ? "border-fail/40 bg-fail/10 text-fail" : "border-ok/40 bg-ok/10 text-ok")}
        data-testid="pole-verdict" data-movable={movable}>
        {movable ? <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" /> : <CircleCheck className="mt-0.5 h-4 w-4 shrink-0" />}
        <span>{result.verdict}</span>
      </div>

      <section>
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Counting criterion</h3>
        <p className="rounded-lg bg-bg/60 px-3 py-2 font-mono text-sm" data-testid="pole-counting">{result.counting}</p>
        <div className="mt-2 grid grid-cols-5 gap-2">
          <Stat label="A" value={result.A} testId="stat-A" hint="Support reactions" />
          <Stat label="z" value={result.z} testId="stat-z" hint="Joint constraints" />
          <Stat label="k" value={result.k} testId="stat-k" hint="Rigid bodies" />
          <Stat label="U" value={result.U} testId="stat-U" hint="U = (A + z) − 3k" />
          <Stat label="dof" value={result.dof} testId="stat-dof" hint="Degrees of freedom (exact analysis)" />
        </div>
        <p className={cn("mt-2 flex items-start gap-1.5 text-xs", result.rules_agree ? "text-muted" : "text-fail")} data-testid="pole-agree" data-agree={result.rules_agree}>
          {result.rules_agree
            ? <><CircleCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ok" /> Rules and exact analysis agree.</>
            : <><CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" /> The pole rules and the exact small-displacement analysis disagree: trust the exact analysis (dof) and check the drawing.</>}
        </p>
      </section>

      {result.contradictions.length > 0 && (
        <section data-testid="pole-contradictions">
          <h3 className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted"><Zap className="h-3.5 w-3.5 text-fail" /> Contradictions</h3>
          <ul className="space-y-1.5">
            {result.contradictions.map((c, i) => (
              <li key={`${c.pole}${i}`} className="rounded-lg border border-fail/30 bg-fail/5 px-3 py-1.5 text-sm" data-testid="pole-contradiction">
                <span className="font-semibold text-fail">Pole {c.pole}</span>{" "}
                <span className="text-muted">(body {c.bodies.length ? c.bodies.join(", ") : c.body})</span>: {c.text}
              </li>
            ))}
          </ul>
        </section>
      )}

      <details className="group rounded-xl border border-border" data-testid="pole-steps">
        <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 text-sm font-medium">
          <ChevronRight className="h-4 w-4 transition group-open:rotate-90" /> Steps <span className="text-xs font-normal text-muted">({result.steps.length})</span>
        </summary>
        <ol className="list-decimal space-y-1.5 border-t border-border px-3 py-2 pl-8 text-sm">
          {result.steps.map((s, i) => <li key={i}>{s}</li>)}
        </ol>
      </details>

      <section>
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Poles</h3>
        {result.poles.length === 0 ? <p className="text-sm text-muted">{result.movable ? "No pole could be determined." : "Every body is immovable, so there are no poles to show."}</p> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="pole-table">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted">
                  <th className="py-1 pr-3 font-medium">Pole</th><th className="py-1 pr-3 font-medium">Position (m)</th><th className="py-1 font-medium">Source</th>
                </tr>
              </thead>
              <tbody>
                {result.poles.map((p) => (
                  <tr key={p.name} className="border-b border-border last:border-0" data-testid={`pole-row-${p.name}`}>
                    <td className="py-1 pr-3 font-mono font-semibold">{p.name}</td>
                    <td className="py-1 pr-3 font-mono">{poleText(p, fmt)}</td>
                    <td className="py-1 text-xs text-muted">{p.source === "rule" ? "pole rules" : "displacement analysis"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
