// Dedicated page for asme.vessel_design: a step-by-step pressure vessel builder.
import {
  BookOpen, Calculator, Check, ChevronLeft, ChevronRight, CircleCheck, CircleX, FileDown, Link2, RotateCcw, TriangleAlert,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ChartView } from "../components/ChartView";
import { ResultsView } from "../components/ResultsView";
import { ToolForm, type FieldErrors } from "../components/ToolForm";
import { cn, SECTION_META, Spinner } from "../components/ui";
import { useEngine } from "../lib/engine";
import { usePrefs } from "../lib/prefs";
import { download, markdownReport } from "../lib/report";
import { defaultValues, fieldsFromSchema, type FieldSpec } from "../lib/schema";
import type { ResultField, RunResponse } from "../lib/types";
import { decodeInputs, encodeInputs } from "../lib/urlState";
import { field, vesselReportSections, withUnit, type VesselCheck, type VesselPart } from "../lib/vessel";

export const VESSEL_TOOL_ID = "asme.vessel_design";

const STEPS = [
  { key: "conditions", title: "Design conditions", hint: "Internal and external design pressure and temperature." },
  { key: "material", title: "Material, S and CA", hint: "Allowable stress S from ASME II-D (you verify it), corrosion allowance and mill undertolerance." },
  { key: "shell", title: "Shell", hint: "Cylinder or sphere, inside diameter, length and joint efficiency (UW-12). Leave the thickness blank to pick the next standard plate." },
  { key: "heads", title: "Heads", hint: "Both ends get the same head. Torispherical defaults to L = D, r = 0.06L (UG-32(d)); flat heads use the Fig. UG-34 factor C." },
  { key: "nozzles", title: "Nozzles", hint: "Set-in nozzles checked by UG-37 area replacement (simplified, F = 1)." },
  { key: "external", title: "External pressure", hint: "Only used when the external design pressure is above zero. Read factor B from the II-D material chart; without it the elastic formula is used." },
  { key: "results", title: "Results", hint: "" },
] as const;

const KEY_RESULTS: [string, string][] = [
  ["mawp", "Vessel MAWP"],
  ["hydro_test_pressure", "Hydrotest pressure"],
  ["shell_t_nominal", "Shell plate"],
  ["head_t_nominal", "Head plate"],
  ["external_allowable", "Allowable external P"],
  ["nozzles_passing", "Nozzles passing"],
];

export function VesselDesign() {
  const [params, setParams] = useSearchParams();
  const { schema, progress, run } = useEngine();
  const { units } = usePrefs();
  const tool = schema?.tools.find((t) => t.id === VESSEL_TOOL_ID);

  const fields = useMemo(() => (tool ? fieldsFromSchema(tool.inputs) : []), [tool]);
  const defaults = useMemo(() => defaultValues(fields), [fields]);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [loaded, setLoaded] = useState(false);
  const [step, setStep] = useState(0);
  const [response, setResponse] = useState<RunResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const autoRan = useRef<string | null>(null);

  useEffect(() => {
    if (!tool) return;
    setValues({ ...defaults, ...decodeInputs(params.get("i")) });
    setLoaded(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tool, defaults]);

  const calculate = async (inputs = values) => {
    if (!tool) return;
    setBusy(true);
    const encoded = encodeInputs(inputs, defaults);
    setParams(encoded ? { i: encoded } : {}, { replace: true });
    const res = await run(tool.id, inputs);
    setResponse(res);
    setBusy(false);
    if (res.ok) setStep(STEPS.length - 1);
  };

  // shared links calculate automatically once Python is ready
  useEffect(() => {
    const link = params.get("i");
    if (tool && link && loaded && progress.stage === "ready" && autoRan.current !== link) {
      autoRan.current = link;
      void calculate(values);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tool, progress.stage, loaded]);

  if (!schema) return <div className="flex items-center gap-2 text-muted"><Spinner /> Loading tools…</div>;
  if (!tool) {
    return (
      <div className="card p-6">
        <p className="mb-2 font-semibold">Vessel builder not found in this build</p>
        <Link className="text-primary-ink underline" to="/">Back to all tools</Link>
      </div>
    );
  }

  const meta = SECTION_META[tool.section];
  const Icon = meta?.icon;
  const errors: FieldErrors = {};
  if (response && !response.ok && response.error.fields) {
    for (const f of response.error.fields) errors[f.loc.join(".")] = f.msg;
  }
  const stepHasError = (key: string) => Object.keys(errors).some((k) => k.startsWith(`${key}.`) || k === key);
  const ready = progress.stage === "ready";
  const result = response?.ok ? response.result.fields : null;
  const current = STEPS[step];

  const shareLink = () => {
    const encoded = encodeInputs(values, defaults);
    return `${location.origin}${location.pathname}#/tool/${tool.id}${encoded ? `?i=${encoded}` : ""}`;
  };

  const copyLink = async () => {
    const url = shareLink();
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      window.prompt("Copy this link", url);
    }
  };

  const exportReport = () => {
    if (!response?.ok) return;
    const summary = response.result.fields.filter((f) => f.summary);
    const md = markdownReport({ tool, fields, values, results: summary, system: units, version: schema.version, link: shareLink() });
    download("pressure_vessel.md", md + "\n" + vesselReportSections(response.result.fields, units), "text/markdown");
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
          {Icon && <Icon className={cn("h-4 w-4", meta.text)} />}
          <span>{schema.sections[tool.section]}</span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight">{tool.name}</h1>
        <p className="max-w-3xl text-muted">{tool.description}</p>
        <div className="flex max-w-4xl gap-2 rounded-xl border border-warn/40 bg-warn/5 p-3 text-xs" data-testid="vessel-disclaimer">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
          <span>
            <span className="font-semibold">Preliminary sizing only.</span> Equations follow ASME BPVC Section VIII Division 1;
            verify every result against the current code edition. Allowable stresses (Section II-D) and the UG-28 chart factors
            are your inputs: no code tables are reproduced here. Supports, nozzle loads, UG-45 and flange ratings are not checked.
          </span>
        </div>
      </header>

      <nav className="card flex gap-1 overflow-x-auto p-2" aria-label="Builder steps">
        {STEPS.map((s, i) => {
          const hasError = stepHasError(s.key);
          const isResult = s.key === "results";
          return (
            <button
              key={s.key}
              type="button"
              onClick={() => setStep(i)}
              data-testid={`step-${s.key}`}
              aria-current={i === step ? "step" : undefined}
              className={cn(
                "flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm transition",
                i === step ? "bg-primary text-on-primary" : "text-muted hover:bg-bg hover:text-ink",
              )}
            >
              <span className={cn("flex h-5 w-5 items-center justify-center rounded-full text-xs font-semibold",
                i === step ? "bg-white/20" : hasError ? "bg-fail/15 text-fail" : "bg-bg")}>
                {isResult && result ? (field(result, "status") === "PASS" ? <Check className="h-3 w-3" /> : "!") : i + 1}
              </span>
              {s.title}
            </button>
          );
        })}
      </nav>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,7fr)_minmax(0,4fr)]">
        <section className="card p-5">
          <form onSubmit={(e) => { e.preventDefault(); void calculate(); }}>
            <h2 className="text-base font-semibold">{step + 1}. {current.title}</h2>
            {current.hint && <p className="mb-4 mt-1 text-sm text-muted">{current.hint}</p>}

            {current.key !== "results" && (
              <StepForm stepKey={current.key} fields={fields} values={values} onChange={setValues} errors={errors} />
            )}
            {current.key === "results" && (
              <ResultsStep response={response} units={units} onReport={exportReport} />
            )}

            <div className="mt-6 flex flex-wrap items-center gap-2 border-t border-border pt-4">
              <button type="button" className="btn-ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>
                <ChevronLeft className="h-4 w-4" /> Back
              </button>
              {step < STEPS.length - 2 && (
                <button type="button" className="btn-ghost" onClick={() => setStep(step + 1)}>
                  Next <ChevronRight className="h-4 w-4" />
                </button>
              )}
              <button type="submit" className="btn-primary" disabled={busy} data-testid="calculate">
                {busy ? <Spinner /> : <Calculator className="h-4 w-4" />}
                {busy ? (ready ? "Calculating…" : "Waiting for Python…") : "Calculate vessel"}
              </button>
              <button type="button" className="btn-ghost" onClick={() => { setValues(defaults); setResponse(null); setStep(0); setParams({}, { replace: true }); }}>
                <RotateCcw className="h-4 w-4" /> Reset
              </button>
              <button type="button" className="btn-ghost" onClick={copyLink}>
                {copied ? <Check className="h-4 w-4 text-ok" /> : <Link2 className="h-4 w-4" />} {copied ? "Copied" : "Copy link"}
              </button>
            </div>
            {!ready && progress.stage !== "error" && (
              <p className="mt-3 text-xs text-muted">Python is loading in the background ({progress.percent}%). You can fill in the steps meanwhile.</p>
            )}
            {response && !response.ok && (
              <div className="mt-3 flex gap-2 rounded-xl border border-fail/30 bg-fail/5 p-3 text-sm text-fail" data-testid="run-error">
                <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{response.error.message}</span>
              </div>
            )}
          </form>
        </section>

        <aside className="card h-fit p-5 xl:sticky xl:top-20">
          <h2 className="mb-3 text-sm font-semibold">Summary</h2>
          {!result && <p className="text-sm text-muted">Work through the steps and press Calculate vessel. Every step has sensible defaults.</p>}
          {result && <Summary result={result} units={units} />}
        </aside>
      </div>

      {response?.ok && response.charts.length > 0 && current.key === "results" && (
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {response.charts.map((c) => (
            <div key={c.id} className="card p-3"><ChartView chart={c} /></div>
          ))}
        </section>
      )}

      <footer className="flex items-start gap-2 text-xs text-muted">
        <BookOpen className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span><span className="font-medium">Reference:</span> {tool.reference}</span>
      </footer>
    </div>
  );
}

function StepForm({ stepKey, fields, values, onChange, errors }: {
  stepKey: string; fields: FieldSpec[]; values: Record<string, unknown>; onChange: (v: Record<string, unknown>) => void; errors: FieldErrors;
}) {
  const spec = fields.find((f) => f.name === stepKey);
  if (!spec) return null;
  if (spec.kind === "array") {
    // the list editor (add/remove nozzles) is the field itself
    return <ToolForm fields={[spec]} values={values} onChange={onChange} errors={errors} />;
  }
  return (
    <ToolForm
      fields={spec.fields ?? []}
      values={(values[stepKey] as Record<string, unknown>) ?? {}}
      onChange={(v) => onChange({ ...values, [stepKey]: v })}
      errors={errors}
      path={`${stepKey}.`}
    />
  );
}

function StatusBanner({ status }: { status: string | undefined }) {
  const ok = status === "PASS";
  const Icon = ok ? CircleCheck : CircleX;
  return (
    <div className={cn("flex items-center gap-3 rounded-xl border p-3", ok ? "border-ok/40 bg-ok/10 text-ok" : "border-fail/40 bg-fail/10 text-fail")}
      data-testid="vessel-status" data-status={status}>
      <Icon className="h-6 w-6" />
      <div>
        <div className="text-lg font-bold">{ok ? "PASS" : "FAIL"}</div>
        <div className="text-xs opacity-80">{ok ? "All checked items meet the code equations." : "At least one item fails: see the checks below."}</div>
      </div>
    </div>
  );
}

function Summary({ result, units }: { result: ResultField[]; units: "SI" | "Imperial" }) {
  const checks = field<VesselCheck[]>(result, "checks") ?? [];
  return (
    <div className="space-y-3">
      <StatusBanner status={field<string>(result, "status")} />
      <dl className="grid grid-cols-2 gap-2">
        {KEY_RESULTS.map(([name, label]) => {
          const f = result.find((r) => r.name === name);
          if (!f || (typeof f.value === "number" && !Number.isFinite(f.value)) || f.value === null) return null;
          return (
            <div key={name} className="rounded-xl border border-border px-3 py-2">
              <dt className="text-xs text-muted">{label}</dt>
              <dd className="font-mono text-sm font-semibold">{withUnit(f.value, f.unit, units)}</dd>
            </div>
          );
        })}
      </dl>
      <ul className="space-y-1 text-sm">
        {checks.map((c) => (
          <li key={c.item} className="flex items-center gap-2">
            {c.status === "PASS" ? <CircleCheck className="h-4 w-4 shrink-0 text-ok" /> : <CircleX className="h-4 w-4 shrink-0 text-fail" />}
            <span className="truncate" title={c.item}>{c.item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ResultsStep({ response, units, onReport }: { response: RunResponse | null; units: "SI" | "Imperial"; onReport: () => void }) {
  if (!response?.ok) return <p className="text-sm text-muted">Press Calculate vessel to size the shell, heads and nozzles.</p>;
  const result = response.result.fields;
  const checks = field<VesselCheck[]>(result, "checks") ?? [];
  const parts = field<VesselPart[]>(result, "parts") ?? [];
  const notes = field<string[]>(result, "notes") ?? [];
  // status texts and the key numbers are already in the banner and summary; show the remaining numbers
  const scalars = result.filter((f) => f.summary && typeof f.value === "number" && Number.isFinite(f.value));
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <StatusBanner status={field<string>(result, "status")} />
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted">{response.elapsed_ms} ms</span>
          <button type="button" className="btn-ghost text-xs" onClick={onReport} data-testid="vessel-report">
            <FileDown className="h-3.5 w-3.5" /> Markdown report
          </button>
        </div>
      </div>

      <div className="overflow-auto rounded-xl border border-border">
        <table className="w-full text-sm" data-testid="vessel-checks">
          <thead className="bg-bg text-xs text-muted">
            <tr>
              <th className="px-3 py-2 text-left font-medium">Check</th>
              <th className="px-3 py-2 text-left font-medium">Clause</th>
              <th className="px-3 py-2 text-right font-medium">Required</th>
              <th className="px-3 py-2 text-right font-medium">Provided</th>
              <th className="px-3 py-2 text-center font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {checks.map((c) => (
              <tr key={c.item} className="border-t border-border">
                <td className="px-3 py-1.5">{c.item}</td>
                <td className="px-3 py-1.5 text-muted">{c.clause}</td>
                <td className="whitespace-nowrap px-3 py-1.5 text-right font-mono">{withUnit(c.required, c.unit, units)}</td>
                <td className="whitespace-nowrap px-3 py-1.5 text-right font-mono">{withUnit(c.provided, c.unit, units)}</td>
                <td className={cn("px-3 py-1.5 text-center font-semibold", c.status === "PASS" ? "text-ok" : "text-fail")}>{c.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ResultsView fields={scalars} toolId={VESSEL_TOOL_ID} />

      {notes.length > 0 && (
        <div>
          <div className="mb-1 text-sm font-semibold">Notes and limitations</div>
          <ul className="list-disc space-y-0.5 pl-5 text-sm text-muted">{notes.map((n) => <li key={n}>{n}</li>)}</ul>
        </div>
      )}

      {parts.map((p) => <PartDetails key={p.name} part={p} />)}
    </div>
  );
}

// rendered only when opened, so the page has one results panel until the user asks for more
function PartDetails({ part }: { part: VesselPart }) {
  const [open, setOpen] = useState(false);
  return (
    <details className="rounded-xl border border-border p-3" onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary className="cursor-pointer text-sm font-semibold">{part.name} details</summary>
      {open && <div className="mt-3"><ResultsView fields={part.fields.filter((f) => f.summary)} toolId={VESSEL_TOOL_ID} /></div>}
    </details>
  );
}
