// Dedicated page for electrical.battery_simulator: grouped inputs, cooling picker and the full chart set
// (voltage, temperature, SOC/current, heat, capacity fade) with PyBaMM reference curves.
import { BatteryCharging, BookOpen, Calculator, Check, Droplets, Fan, Flame, Link2, RotateCcw, Snowflake, Thermometer, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ChartView } from "../components/ChartView";
import { ResultsView } from "../components/ResultsView";
import { ToolForm, type FieldErrors } from "../components/ToolForm";
import { cn, SECTION_META, Spinner } from "../components/ui";
import { useEngine } from "../lib/engine";
import { defaultValues, fieldsFromSchema, type FieldSpec } from "../lib/schema";
import type { RunResponse } from "../lib/types";
import { decodeInputs, encodeInputs } from "../lib/urlState";

export const BATTERY_TOOL = "electrical.battery_simulator";

const MODES: { value: string; label: string }[] = [
  { value: "discharge_cc", label: "Constant current" },
  { value: "discharge_cp", label: "Constant power" },
  { value: "drive_cycle", label: "Drive cycle" },
  { value: "charge_cccv", label: "CC-CV charge" },
];

const COOLING: { value: string; label: string; icon: typeof Fan }[] = [
  { value: "natural_air", label: "Still air", icon: Thermometer },
  { value: "forced_air", label: "Forced air", icon: Fan },
  { value: "liquid_cold_plate", label: "Cold plate", icon: Droplets },
  { value: "adiabatic", label: "Adiabatic", icon: Flame },
  { value: "fixed_h", label: "Fixed h", icon: Snowflake },
];

const RATE_PRESETS = ["0.5, 1, 2", "1", "0.2, 0.5, 1", "1, 2, 3"];

// which inputs each cooling option uses (besides the cooling choice itself)
const COOLING_FIELDS: Record<string, string[]> = {
  natural_air: ["T_ambient"],
  forced_air: ["T_ambient", "T_coolant", "air_velocity"],
  liquid_cold_plate: ["T_ambient", "T_coolant", "coolant", "coolant_velocity", "cooled_fraction"],
  adiabatic: ["T_ambient"],
  fixed_h: ["T_ambient", "T_coolant", "h_fixed"],
};
const NOTES: Record<string, string> = {
  voltage: "Dashed: PyBaMM DFN (Chen2020 parameters) for the LG M50; the equivalent circuit was fitted to DFN pulses at 60 % SOC.",
  capacity_fade:
    "Solid: semi-empirical correlation fitted to lab cycling (all aging mechanisms; Schmalstieg 2014 for NMC, Wang 2011 for LFP) " +
    "at the simulated mean cell temperature. Dashed: PyBaMM with only SEI growth and lithium plating (OKane2022 parameters), " +
    "so it shows how these mechanisms depend on C-rate and temperature rather than the total fade.",
};
const CELL_FIELDS =["cell", "c_rates", "n_rc", "soc_initial"];
const PACK_FIELDS = ["n_series", "n_parallel", "aging_cycles", "c_rate_charge", "compare_pybamm"];

function Segmented({ options, value, onChange, testId }: {
  options: { value: string; label: string; icon?: typeof Fan }[]; value: unknown; onChange: (v: string) => void; testId: string;
}) {
  return (
    <div className="flex flex-wrap gap-1.5" role="radiogroup" data-testid={testId}>
      {options.map((o) => {
        const Icon = o.icon;
        const active = value === o.value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition",
              active ? "border-primary bg-primary/10 text-primary-ink" : "border-border text-muted hover:bg-bg",
            )}
          >
            {Icon && <Icon className="h-3.5 w-3.5" />}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</h3>
      {children}
    </div>
  );
}

export function BatteryPage() {
  const [params, setParams] = useSearchParams();
  const { schema, progress, run } = useEngine();
  const tool = schema?.tools.find((t) => t.id === BATTERY_TOOL);

  const fields = useMemo(() => (tool ? fieldsFromSchema(tool.inputs) : []), [tool]);
  const defaults = useMemo(() => defaultValues(fields), [fields]);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [response, setResponse] = useState<RunResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const autoRan = useRef(false);

  useEffect(() => {
    setValues({ ...defaults, ...decodeInputs(params.get("i")) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaults]);

  const calculate = async (inputs = values) => {
    if (!tool) return;
    setBusy(true);
    const encoded = encodeInputs(inputs, defaults);
    setParams(encoded ? { i: encoded } : {}, { replace: true });
    setResponse(await run(tool.id, inputs));
    setBusy(false);
  };

  // shared links calculate automatically once Python is ready
  useEffect(() => {
    if (tool && params.get("i") && progress.stage === "ready" && !autoRan.current && Object.keys(values).length) {
      autoRan.current = true;
      void calculate(values);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tool, progress.stage, values]);

  if (!schema) return <div className="flex items-center gap-2 text-muted"><Spinner /> Loading tools…</div>;
  if (!tool) {
    return (
      <div className="card p-6">
        <p className="mb-2 font-semibold">Tool not found</p>
        <Link className="text-primary-ink underline" to="/">Back to all tools</Link>
      </div>
    );
  }

  const pick = (names: string[]): FieldSpec[] => names.map((n) => fields.find((f) => f.name === n)).filter((f): f is FieldSpec => Boolean(f));
  const cooling = String(values.cooling ?? "natural_air");
  const mode = String(values.mode ?? "discharge_cc");
  const set = (name: string, v: unknown) => setValues({ ...values, [name]: v });
  const errors: FieldErrors = {};
  if (response && !response.ok && response.error.fields) {
    for (const f of response.error.fields) errors[f.loc.join(".")] = f.msg;
  }
  const ready = progress.stage === "ready";
  const meta = SECTION_META[tool.section];

  const copyLink = async () => {
    const encoded = encodeInputs(values, defaults);
    const url = `${location.origin}${location.pathname}#/tool/${tool.id}${encoded ? `?i=${encoded}` : ""}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      window.prompt("Copy this link", url);
    }
  };

  const charts = response?.ok ? response.charts : [];
  const wide = new Set(["capacity_fade"]);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
          <BatteryCharging className={cn("h-4 w-4", meta?.text)} />
          <span>{schema.sections[tool.section]}</span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight">{tool.name}</h1>
        <p className="max-w-3xl text-muted">{tool.description}</p>
      </header>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <section className="card p-5">
          <form
            className="space-y-6"
            onSubmit={(e) => {
              e.preventDefault();
              void calculate();
            }}
          >
            <Group title="Cell and load">
              <Segmented options={MODES} value={mode} onChange={(v) => set("mode", v)} testId="battery-mode" />
              <ToolForm fields={pick(CELL_FIELDS)} values={values} onChange={setValues} errors={errors} />
              <div className="flex flex-wrap items-center gap-1.5 text-xs">
                <span className="text-muted">{mode === "discharge_cp" ? "E-rates:" : "C-rates:"}</span>
                {RATE_PRESETS.map((p) => (
                  <button key={p} type="button" onClick={() => set("c_rates", p)}
                    className={cn("rounded-full border px-2 py-0.5", values.c_rates === p ? "border-primary text-primary-ink" : "border-border text-muted hover:bg-bg")}>
                    {p}
                  </button>
                ))}
              </div>
            </Group>

            <Group title="Cooling">
              <Segmented options={COOLING} value={cooling} onChange={(v) => set("cooling", v)} testId="battery-cooling" />
              <ToolForm fields={pick(COOLING_FIELDS[cooling] ?? [])} values={values} onChange={setValues} errors={errors} />
            </Group>

            <Group title="Pack and aging">
              <ToolForm fields={pick(PACK_FIELDS)} values={values} onChange={setValues} errors={errors} />
            </Group>

            <div className="flex flex-wrap items-center gap-2">
              <button type="submit" className="btn-primary" disabled={busy} data-testid="calculate">
                {busy ? <Spinner /> : <Calculator className="h-4 w-4" />}
                {busy ? (ready ? "Simulating…" : "Waiting for Python…") : "Simulate"}
              </button>
              <button type="button" className="btn-ghost" onClick={() => { setValues(defaults); setResponse(null); setParams({}, { replace: true }); }}>
                <RotateCcw className="h-4 w-4" /> Reset
              </button>
              <button type="button" className="btn-ghost" onClick={copyLink}>
                {copied ? <Check className="h-4 w-4 text-ok" /> : <Link2 className="h-4 w-4" />} {copied ? "Copied" : "Copy link"}
              </button>
            </div>
            {!ready && progress.stage !== "error" && (
              <p className="text-xs text-muted">Python is loading in the background ({progress.percent}%). You can set the inputs meanwhile.</p>
            )}
          </form>
        </section>

        <section className="card p-5">
          <div className="mb-4 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">Results</h2>
            {response?.ok && <span className="text-xs text-muted">{response.elapsed_ms} ms</span>}
          </div>
          {!response && (
            <p className="text-sm text-muted">
              Pick a cell, the C-rates and a cooling option, then press Simulate. Dashed lines are PyBaMM
              reference results (LG M50, constant-current discharge).
            </p>
          )}
          {response && !response.ok && (
            <div className="flex gap-2 rounded-xl border border-fail/30 bg-fail/5 p-3 text-sm text-fail" data-testid="run-error">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{response.error.message}</span>
            </div>
          )}
          {response?.ok && <ResultsView fields={response.result.fields} toolId={tool.id} />}
        </section>
      </div>

      {charts.length > 0 && (
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {charts.map((c) => (
            <div key={c.id} className={cn("card p-3", wide.has(c.id) && "lg:col-span-2")}>
              <ChartView chart={c} />
              {NOTES[c.id] && <p className="px-2 pb-1 text-xs text-muted">{NOTES[c.id]}</p>}
            </div>
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
