// Shear-flow tab of the structural page: draw a thin-walled section, see t(s) through it, the shear centre
// and the formulary-style steps. All numbers come from the Python tool structural.shear_flow.
import { useState, type ReactNode } from "react";
import { NumberInput, type Conversion } from "../components/NumberInput";
import { ShearFlowEditor } from "../components/ShearFlowEditor";
import { ShearFlowPlot, type PlotLoad } from "../components/ShearFlowPlot";
import { cn } from "../components/ui";
import {
  cleanNoise, maxAbs, parseShearResult, seriesValues, shearError, type FlowQuantity, type FlowSeries, type Point, type ShearResult,
  type ShearValues, type StructuralState,
} from "../lib/structural";
import type { RunResponse } from "../lib/types";
import { formatNumber, type UnitSystem } from "../lib/units";
import { Card, ErrorBox, smallLength, stressConv, unitConv } from "./structuralShared";

type Update = (patch: Partial<StructuralState> | ((s: StructuralState) => Partial<StructuralState>)) => void;

const lin = (unit: string, f: number): Conversion => ({ unit, toSI: (v) => v * f, fromSI: (v) => v / f });

/** Shear flow t in N/m, shown as N/mm (lbf/in). */
const flowConv = (system: UnitSystem): Conversion => (system === "SI" ? lin("N/mm", 1e3) : lin("lbf/in", 175.12683));
const forceConv = (system: UnitSystem): Conversion => (system === "SI" ? lin("N", 1) : lin("lbf", 4.448221615));
const momentConv = (system: UnitSystem): Conversion => (system === "SI" ? lin("N·m", 1) : lin("lbf·ft", 1.355817948));
const modulusConv = (system: UnitSystem): Conversion => (system === "SI" ? lin("GPa", 1e9) : lin("Msi", 6.894757293168e9));
const SNAP_SI = [0.001, 0.002, 0.005, 0.01, 0.02];
const SNAP_IMPERIAL = [0.00127, 0.00254, 0.00635, 0.0127, 0.0254]; // 0.05, 0.1, 0.25, 0.5, 1 in

const show = (c: Conversion, v: number, digits = 4) => (Number.isFinite(v) ? `${formatNumber(c.fromSI(v), digits)} ${c.unit}` : "—");

function Toggle<T extends string>({ label, value, options, onChange, testId }: {
  label: string; value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; testId: string;
}) {
  return (
    <div className="flex rounded-lg border border-border p-0.5 text-xs" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={value === o.value} data-testid={`${testId}-${o.value}`}
          className={cn("rounded-md px-2.5 py-1 transition", value === o.value ? "bg-primary text-on-primary" : "text-muted hover:text-ink")}
          onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function ShearFlowTab({ state, update, response, units }: {
  state: StructuralState; update: Update; response: RunResponse | null; units: UnitSystem;
}) {
  const v = state.shear;
  const setShear = (p: Partial<ShearValues>) => update((s) => ({ shear: { ...s.shear, ...p } }));
  const [quantity, setQuantity] = useState<FlowQuantity>("t");
  const [view, setView] = useState<"result" | "steps">("result");

  const length = smallLength(units);
  const force = forceConv(units);
  const moment = momentConv(units);
  const flow = flowConv(units);
  const stress = stressConv(units);
  const err = shearError(v);
  const result = !err && response?.ok ? parseShearResult(response.result.fields) : null;
  const toolError = !err && response && !response.ok ? response.error.message : null;
  const plotConv = quantity === "t" ? flow : stress;
  const fmt = (x: number) => formatNumber(plotConv.fromSI(x), 3);
  const load: PlotLoad = { q2: v.Q2, q3: v.Q3, atSC: v.load_at_shear_centre, a2: v.a2, a3: v.a3 };
  const centroid: Point | null = result ? [result.x2S, result.x3S] : null;
  const closed = !!result && result.n_cells > 0;

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,6fr)_minmax(0,6fr)]">
      <div className="space-y-6">
        <Card title="Thin-walled section (mid-lines)">
          <ShearFlowEditor
            value={{ nodes: v.nodes, walls: v.walls }} onChange={(g) => setShear(g)}
            load={{ show: !v.load_at_shear_centre, a2: v.a2, a3: v.a3 }}
            onPlaceLoad={(a2, a3) => setShear({ a2, a3, load_at_shear_centre: false })}
            centroid={centroid} lengthConv={length} modulusConv={modulusConv(units)}
            snapChoices={units === "SI" ? SNAP_SI : SNAP_IMPERIAL} error={err} />
        </Card>

        <Card title="Loads">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <NumberInput label="Shear force Q₂ (+x₂, right)" value={v.Q2} conv={force} testId="shear-Q2" onChange={(x) => setShear({ Q2: x ?? 0 })} />
            <NumberInput label="Shear force Q₃ (+x₃, down)" value={v.Q3} conv={force} testId="shear-Q3" onChange={(x) => setShear({ Q3: x ?? 0 })} />
            <NumberInput label="Torque Mₜ (x₂ → x₃)" value={v.Mt} conv={moment} testId="shear-Mt" onChange={(x) => setShear({ Mt: x ?? 0 })} />
          </div>
          <label className="mt-3 flex items-center gap-2 text-sm">
            <input type="checkbox" className="accent-primary" checked={v.load_at_shear_centre} data-testid="shear-at-sc"
              onChange={(e) => setShear({ load_at_shear_centre: e.target.checked })} />
            Load acts at the shear centre
          </label>
          {!v.load_at_shear_centre && (
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <NumberInput label="Load line through a₂" value={v.a2} conv={length} testId="shear-a2" onChange={(x) => setShear({ a2: x ?? 0 })} />
              <NumberInput label="Load line through a₃" value={v.a3} conv={length} testId="shear-a3" onChange={(x) => setShear({ a3: x ?? 0 })} />
            </div>
          )}
          <p className="mt-3 text-xs text-muted">
            Q acts along the shear force direction; off the shear centre it adds a torque about the shear centre. Use “Place load” on the canvas to pick the point.
            Mₜ is positive about +x₁ (from x₂ towards x₃).
          </p>
        </Card>
      </div>

      <div className="space-y-6">
        <Card title="Shear flow through the section" aside={
          result && (
            <div className="flex flex-wrap items-center gap-2">
              {closed && (
                <Toggle label="View" value={view} testId="shear-view" onChange={setView}
                  options={[{ value: "result", label: "Result" }, { value: "steps", label: "Steps" }]} />
              )}
              <Toggle label="Quantity" value={quantity} testId="shear-quantity" onChange={setQuantity}
                options={[{ value: "t", label: "t (shear flow)" }, { value: "tau", label: "τ = t/h" }]} />
            </div>
          )
        }>
          {err && <p className="text-sm text-muted">Fix the section above to see the shear flow.</p>}
          {!err && !response && <p className="text-sm text-muted">The shear flow appears here once Python is ready.</p>}
          {toolError && <ErrorBox message={toolError} />}
          {result && (
            <div className="space-y-3" data-testid="results">
              {closed && view === "steps"
                ? <StepsPanels result={result} quantity={quantity} fmt={fmt} />
                : <ShearFlowPlot result={result} quantity={quantity} fmt={fmt} load={load} title="Shear flow through the section" />}
              <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-muted">
                <span className="inline-flex items-center gap-1">
                  <span className="inline-block h-2.5 w-2.5 rounded-sm border border-fail" style={{ background: "repeating-linear-gradient(90deg, rgb(var(--fail)) 0 1px, transparent 1px 3px)" }} />
                  Hatched: {quantity === "t" ? "|t|" : "|τ|"} drawn outside each wall
                </span>
                <span>· arrows: flow direction</span>
                <span>· NA: neutral axis</span>
                <span>values in {plotConv.unit}</span>
                <span className="inline-flex items-center gap-1"><span className="font-mono text-ink">⊕</span> S centroid</span>
                <span className="inline-flex items-center gap-1"><span className="text-thermo">◆</span> SC shear centre</span>
              </div>
              <p className="text-center text-xs text-muted">Hatch length is proportional to {quantity === "t" ? "|t|" : "|τ|"}. Walls are drawn at their real thickness, at least 6 px.</p>
            </div>
          )}
        </Card>

        {result && <KeyResults result={result} units={units} />}
        {result && <StepsTable result={result} units={units} />}
      </div>
    </div>
  );
}

// ---------------- closed sections: formulary steps t' + t0 (+ torque) = t ----------------

function StepsPanels({ result, quantity, fmt }: { result: ShearResult; quantity: FlowQuantity; fmt: (v: number) => string }) {
  const torque = maxAbs(seriesValues(result.walls, "t_torque", quantity)) > 1e-9 * maxAbs(seriesValues(result.walls, "t_total", quantity));
  const panels: { series: FlowSeries; title: string; cuts?: boolean }[] = [
    { series: "t_cut", title: quantity === "t" ? "t′ (cut open)" : "τ′ (cut open)", cuts: true },
    { series: "t0", title: quantity === "t" ? "t₀ (closing flow)" : "τ₀ (closing flow)" },
    ...(torque ? [{ series: "t_torque" as const, title: quantity === "t" ? "t (torque, Bredt)" : "τ (torque, Bredt)" }] : []),
    { series: "t_total", title: quantity === "t" ? "t" : "τ" },
  ];
  const shared = Math.max(...panels.map((p) => maxAbs(seriesValues(result.walls, p.series, quantity))));
  const items: ReactNode[] = [];
  panels.forEach((p, i) => {
    if (i > 0) items.push(<span key={`op${i}`} className="select-none self-center text-2xl text-muted" aria-hidden="true">{i === panels.length - 1 ? "=" : "+"}</span>);
    items.push(
      <figure key={p.series} className="min-w-[180px] flex-1" data-testid={`shear-step-${p.series}`}>
        <figcaption className="mb-1 text-center text-xs font-semibold text-muted">{p.title}</figcaption>
        <ShearFlowPlot result={result} series={p.series} quantity={quantity} fmt={fmt} shared={shared} compact cuts={p.cuts} title={p.title} testId={`shear-plot-${p.series}`} />
      </figure>,
    );
  });
  return <div className="flex flex-wrap items-stretch justify-center gap-2" data-testid="shear-steps-panels">{items}</div>;
}

// ---------------- key results and steps table ----------------

function KeyResults({ result: r, units }: { result: ShearResult; units: UnitSystem }) {
  const small = smallLength(units);
  const area = unitConv("m^2", units);
  const inertia = unitConv("m^4", units);
  const flow = flowConv(units);
  const stress = stressConv(units);
  const moment = momentConv(units);
  const rows: { id: string; label: string; value: string }[] = [
    { id: "A", label: "Area A = Σ h l", value: show(area, r.A) },
    { id: "centroid", label: "Centroid S (x₂, x₃)", value: `${show(small, r.x2S)}, ${show(small, r.x3S)}` },
    { id: "J22", label: "J₂₂ = ∫x₃² h ds", value: show(inertia, r.J22) },
    { id: "J33", label: "J₃₃ = ∫x₂² h ds", value: show(inertia, r.J33) },
    { id: "J23", label: "J₂₃ = ∫x₂x₃ h ds", value: show(inertia, r.J23) },
    { id: "phi", label: "Principal angle φ", value: Number.isFinite(r.phi_deg) ? `${formatNumber(cleanNoise(r.phi_deg, 1))} °` : "—" },
    { id: "sc", label: "Shear centre SC (x₂, x₃)", value: `${show(small, r.x2_SC)}, ${show(small, r.x3_SC)}` },
    { id: "e", label: "Offset e₂, e₃ from S", value: `${show(small, cleanNoise(r.e2, Math.abs(r.x2_SC) + Math.abs(r.x2S)))}, ${show(small, cleanNoise(r.e3, Math.abs(r.x3_SC) + Math.abs(r.x3S)))}` },
    { id: "JT", label: r.n_cells > 0 ? "Torsion constant J_T (Bredt)" : "Torsion constant J_T (Σ l h³/3)", value: show(inertia, r.J_T) },
    { id: "torque", label: "Torque about SC", value: show(moment, cleanNoise(r.torque_SC, 1)) },
    { id: "t_max", label: `Max |t| (wall ${r.t_max_wall}, s = ${show(small, r.t_max_s, 3)})`, value: show(flow, r.t_max) },
    { id: "tau_max", label: "Max |τ| = |t/h|", value: show(stress, r.tau_max) },
    ...(Number.isFinite(r.tau_torsion_open) && r.tau_torsion_open > 0
      ? [{ id: "tau_torsion_open", label: "Torsion τ_max, open (Saint-Venant)", value: show(stress, r.tau_torsion_open) }] : []),
    { id: "cells", label: "Closed cells", value: String(r.n_cells) },
  ];
  return (
    <Card title="Key results">
      <table className="w-full text-sm" data-testid="shear-results">
        <tbody>
          {rows.map((x) => (
            <tr key={x.id} className="border-b border-border last:border-0" data-testid={`result-${x.id}`}>
              <td className="py-1.5 pr-3 text-muted">{x.label}</td>
              <td className="py-1.5 text-right font-mono font-semibold">{x.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {r.note && <p className="mt-3 rounded-lg bg-bg p-3 text-xs text-muted" data-testid="shear-note">{r.note}</p>}
    </Card>
  );
}

function StepsTable({ result: r, units }: { result: ShearResult; units: UnitSystem }) {
  const conv = (unit: string): Conversion => (unit === "m" ? smallLength(units) : unit === "N/m" ? flowConv(units) : unitConv(unit, units));
  const scale: Record<string, number> = {};
  for (const s of r.steps) if (Number.isFinite(s.value)) scale[s.unit] = Math.max(scale[s.unit] ?? 0, Math.abs(s.value));
  return (
    <Card title="Formulary steps">
      <div className="max-h-96 overflow-auto">
        <table className="w-full text-sm" data-testid="shear-steps">
          <tbody>
            {r.steps.map((s, i) => {
              const c = conv(s.unit);
              return (
                <tr key={i} className="border-b border-border last:border-0" data-testid="shear-step-row">
                  <td className="py-1.5 pr-3 text-muted">{s.label}</td>
                  <td className="py-1.5 text-right font-mono font-semibold">{formatNumber(c.fromSI(cleanNoise(s.value, scale[s.unit] ?? 1)))}</td>
                  <td className="py-1.5 pl-2 text-xs text-muted">{c.unit}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-muted">
        Order as in the formulary: static moments S₂ at the nodes, then J₂₂, J₃₃, J₂₃, the cut-open shear centre e₁ and, for closed cells, the enclosed areas and closing flows t₀.
        S₂ in {unitConv("m^3", units).unit}.
      </p>
    </Card>
  );
}
