// Torsion tab of the structural page: free (Saint-Venant) or restrained warping of a member with fixed / fork / free
// ends under point and uniform torques, for the tab-1 section or the section drawn in tab 5. All numbers come from the
// Python tool structural.torsion; the results follow the order of the course formulary.
import { Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { ChartView } from "../components/ChartView";
import { NumberInput, type Conversion } from "../components/NumberInput";
import { SectionDrawing } from "../components/SectionDrawing";
import { TorsionBeamDiagram } from "../components/TorsionBeamDiagram";
import {
  alphaHint, cleanNoise, drawnCellCount, parseTorsionResult, torqueLoadErrors, torsionError, TORSION_SUPPORTS, type ShearGeometry,
  type StructuralState, type TorsionResult, type TorsionSupport, type TorsionValues,
} from "../lib/structural";
import type { RunResponse } from "../lib/types";
import { formatNumber, type UnitSystem } from "../lib/units";
import {
  bimomentConv, Card, ErrorBox, forceNConv, lengthPowConv, smallLength, stressConv, Toggle, torqueConv, torquePerLengthConv, unitConv,
} from "./structuralShared";

type Update = (patch: Partial<StructuralState> | ((s: StructuralState) => Partial<StructuralState>)) => void;

const PLAIN: Conversion = { unit: "", toSI: (v) => v, fromSI: (v) => v };
const show = (c: Conversion, v: number, digits = 4) => (Number.isFinite(v) ? `${formatNumber(c.fromSI(v), digits)} ${c.unit}`.trim() : "—");

const SUPPORT_LABEL: Record<TorsionSupport, string> = { fixed: "Fixed", fork: "Fork", free: "Free" };
const SUPPORT_HINT: Record<TorsionSupport, string> = {
  fixed: "Fixed: twist and warping are held (clamped end).",
  fork: "Fork: twist is held, warping stays free (the end may warp).",
  free: "Free: nothing is held.",
};
const MODE_HINT = {
  free: "Free warping (Saint-Venant): the cross-sections may warp freely, so the whole torque is carried by shear stresses alone.",
  restrained: "Restrained warping: a clamped or loaded section is held against warping, so part of the torque is carried by a warping torque, which adds normal stresses σ_ω and a bimoment.",
};

/** Unit of a result step (SI as written by Python) → display conversion. */
function stepConv(unit: string, units: UnitSystem): Conversion {
  switch (unit) {
    case "m^2": return lengthPowConv(2, units);
    case "m^3": return lengthPowConv(3, units);
    case "m^4": return lengthPowConv(4, units);
    case "m^6": return lengthPowConv(6, units);
    case "m": return smallLength(units);
    case "N·m": return torqueConv(units);
    case "N·m^2": return bimomentConv(units);
    case "Pa": return stressConv(units);
    default: return { ...PLAIN, unit };
  }
}

export function TorsionTab({ state, update, response, units, onEditSection, onEditShear }: {
  state: StructuralState; update: Update; response: RunResponse | null; units: UnitSystem;
  onEditSection: () => void; onEditShear: () => void;
}) {
  const t = state.torsion;
  const setT = (p: Partial<TorsionValues>) => update((s) => ({ torsion: { ...s.torsion, ...p } }));
  const span = unitConv("m", units);
  const torque = torqueConv(units);
  const perLength = torquePerLengthConv(units);
  const force = forceNConv(units);
  const small = smallLength(units);
  const err = torsionError(t, state.shear);
  const loadErr = torqueLoadErrors(t);
  const drawn = t.section_source === "drawn";
  const cells = drawnCellCount(state.shear);
  const sectionName = state.section.shape === "profile" ? String(state.section.profile) : state.section.shape.replace(/_/g, " ");
  const extraT = t.Q2 * t.e3 - t.Q3 * t.e2;
  const [offOpen, setOffOpen] = useState(t.Q2 !== 0 || t.Q3 !== 0 || t.e2 !== 0 || t.e3 !== 0);

  const shown = err ? null : response;
  const res = useMemo(() => (shown?.ok ? parseTorsionResult(shown.result.fields) : null), [shown]);
  const charts = shown?.ok ? shown.charts : [];
  const sectionChart = charts.find((c) => c.id === "section");
  const lineCharts = charts.filter((c) => c.id !== "section");

  const setLoad = (i: number, p: Partial<TorsionValues["loads"][number]>) =>
    update((s) => ({ torsion: { ...s.torsion, loads: s.torsion.loads.map((l, k) => (k === i ? { ...l, ...p } : l)) } }));

  return (
    <div className="space-y-6">
      <Card title="Warping">
        <Toggle label="Warping" value={t.mode} testId="torsion-mode" onChange={(mode) => setT({ mode })}
          options={[{ value: "free", label: "Free warping (Saint-Venant)" }, { value: "restrained", label: "Restrained warping" }]} />
        <p className="mt-3 text-xs text-muted" data-testid="torsion-mode-hint">{MODE_HINT[t.mode]}</p>
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <div className="space-y-6">
          <Card title="Section">
            <Toggle label="Section source" value={t.section_source} testId="torsion-source" onChange={(section_source) => setT({ section_source })}
              options={[{ value: "library", label: "Section from tab 1" }, { value: "drawn", label: "Drawn section (tab 5)" }]} />
            {!drawn && (
              <p className="mt-3 text-sm" data-testid="torsion-section-library">
                <span className="font-medium capitalize">{sectionName}</span> · {state.material}{" "}
                <button type="button" className="text-xs text-primary-ink hover:underline" onClick={onEditSection}>(edit in tab 1)</button>
              </p>
            )}
            {drawn && (
              <div className="mt-3 space-y-3" data-testid="torsion-section-drawn">
                <DrawnPreview geometry={state.shear} />
                <p className="text-sm">
                  {state.shear.walls.length} walls, {state.shear.nodes.length} nodes · {state.material}{" "}
                  <button type="button" className="text-xs text-primary-ink hover:underline" onClick={onEditShear} data-testid="torsion-edit-shear">(edit in tab 5)</button>
                </p>
                {cells === 0 ? (
                  <NumberInput label="η3 correction (J_T = η3/3 Σ h³ l)" value={t.eta3} conv={PLAIN} positive testId="field-eta3" onChange={(v) => setT({ eta3: v ?? 1 })} />
                ) : (
                  <p className="text-xs text-muted" data-testid="torsion-closed-note">
                    Closed section ({cells} cell{cells === 1 ? "" : "s"}): J_T from Bredt; the warping constant C_T is taken as 0, so warping restraint has no effect.
                  </p>
                )}
              </div>
            )}
          </Card>

          <Card title="Beam">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <NumberInput label="Length L" value={t.length} conv={span} positive testId="field-torsion-length" onChange={(v) => setT({ length: v ?? 0 })} />
              <NumberInput label="Position of interest x" value={t.position} conv={span} min={0} testId="field-position" onChange={(v) => setT({ position: v ?? 0 })} />
              {(["left", "right"] as const).map((side) => {
                const key = side === "left" ? "left_support" : "right_support";
                return (
                  <label key={side} className="block" title={TORSION_SUPPORTS.map((k) => SUPPORT_HINT[k]).join("\n")}>
                    <span className="label">{side === "left" ? "Left end (x = 0)" : "Right end (x = L)"}</span>
                    <select className="input" value={t[key]} data-testid={`torsion-${side}-support`} onChange={(e) => setT({ [key]: e.target.value as TorsionSupport })}>
                      {TORSION_SUPPORTS.map((k) => <option key={k} value={k} title={SUPPORT_HINT[k]}>{SUPPORT_LABEL[k]}</option>)}
                    </select>
                  </label>
                );
              })}
            </div>
            <p className="mt-3 text-xs text-muted">
              {TORSION_SUPPORTS.map((k) => SUPPORT_HINT[k]).join(" ")}
            </p>
            {err && <p className="mt-2 text-xs text-fail" data-testid="torsion-error">{err}</p>}
          </Card>

          <Card title="Torques" aside={
            <button type="button" className="btn-ghost px-2 py-1 text-xs" data-testid="torsion-load-add"
              onClick={() => update((s) => ({ torsion: { ...s.torsion, loads: [...s.torsion.loads, { x: s.torsion.length, T: 100 }] } }))}>
              <Plus className="h-3.5 w-3.5" /> Add torque
            </button>}>
            <div className="space-y-2" data-testid="torsion-loads">
              {t.loads.length === 0 && <p className="text-xs text-muted">No point torques.</p>}
              {t.loads.map((l, i) => (
                <div key={i} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] items-start gap-2" data-testid="torsion-load-row">
                  <NumberInput label={`Torque ${i + 1} at x`} value={l.x} conv={span} min={0} error={loadErr[i]} testId={`torsion-load-${i}-x`} onChange={(v) => setLoad(i, { x: v ?? 0 })} />
                  <NumberInput label="Torque T" value={l.T} conv={torque} testId={`torsion-load-${i}-T`} onChange={(v) => setLoad(i, { T: v ?? 0 })} />
                  <button type="button" className="btn-ghost mt-6 p-2" aria-label={`Delete torque ${i + 1}`} data-testid={`torsion-load-${i}-delete`}
                    onClick={() => update((s) => ({ torsion: { ...s.torsion, loads: s.torsion.loads.filter((_, k) => k !== i) } }))}>
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
              <NumberInput label="Uniform torque m_t (whole span)" value={t.m_t} conv={perLength} testId="field-torsion-mt" onChange={(v) => setT({ m_t: v ?? 0 })} />
            </div>
            <p className="mt-3 text-xs text-muted">Positive torque acts about +x₁ (arrow pointing right).</p>
          </Card>

          {t.mode === "free" && (
            <details className="card p-5" open={offOpen} data-testid="torsion-offcentre" onToggle={(e) => setOffOpen(e.currentTarget.open)}>
              <summary className="cursor-pointer text-sm font-semibold">Shear force off the shear centre</summary>
              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                <NumberInput label="Shear force Q₂ (+x₂)" value={t.Q2} conv={force} testId="field-torsion-Q2" onChange={(v) => setT({ Q2: v ?? 0 })} />
                <NumberInput label="Shear force Q₃ (+x₃, down)" value={t.Q3} conv={force} testId="field-torsion-Q3" onChange={(v) => setT({ Q3: v ?? 0 })} />
                <NumberInput label="Offset e₂ (shear centre − load line)" value={t.e2} conv={small} testId="field-torsion-e2" onChange={(v) => setT({ e2: v ?? 0 })} />
                <NumberInput label="Offset e₃ (shear centre − load line)" value={t.e3} conv={small} testId="field-torsion-e3" onChange={(v) => setT({ e3: v ?? 0 })} />
              </div>
              <p className="mt-3 text-xs text-muted">
                The force Q acts at x = L. Off the shear centre it adds the torque T = M_t + Q₂ e₃ − Q₃ e₂ there:{" "}
                <span className="font-mono text-ink" data-testid="torsion-extra-torque">{show(torque, extraT)}</span> in addition to the torques above.
              </p>
            </details>
          )}
        </div>

        <div className="space-y-6">
          <Card title="Member and loads">
            <div className="overflow-x-auto">
              <TorsionBeamDiagram length={t.length} left={t.left_support} right={t.right_support} loads={t.loads} mt={t.m_t} position={t.position}
                fmt={{ length: (m) => show(span, m, 3), torque: (v) => `T = ${show(torque, v)}`, perLength: (v) => show(perLength, v) }} />
            </div>
          </Card>

          {shown && !shown.ok && <ErrorBox message={shown.error.message} />}
          {res && (
            <div className="space-y-6" data-testid="results">
              <KeyResults r={res} units={units} />
              <StepsTable r={res} units={units} />
            </div>
          )}
          {!shown && !err && <p className="text-sm text-muted">The results appear here once Python is ready.</p>}
        </div>
      </div>

      {shown?.ok && (lineCharts.length > 0 || sectionChart) && (
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-2" data-testid="torsion-charts">
          {lineCharts.map((c) => <div key={c.id} className="card p-3"><ChartView chart={c} /></div>)}
          {sectionChart && (
            <div className="card p-3">
              {drawn ? <ChartView chart={sectionChart} /> : <SectionDrawing chart={sectionChart} length={(m) => show(small, m)} />}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

// ---------------- results ----------------

function KeyResults({ r, units }: { r: TorsionResult; units: UnitSystem }) {
  const span = unitConv("m", units);
  const torque = torqueConv(units);
  const stress = stressConv(units);
  const warping = r.mode === "restrained" && r.C_T > 0;
  const hint = r.mode === "restrained" ? (alphaHint(r.alpha) ?? "C_T = 0: warping restraint has no effect") : null;
  const rad = (v: number) => (Number.isFinite(v) ? `${formatNumber(cleanNoise(v, Math.abs(r.theta_max)))} rad` : "—");
  const rows: { id: string; label: string; value: string; hint?: string | null }[] = [
    { id: "twist", label: "Twist ϑ at x", value: rad(r.twist) },
    { id: "twist_deg", label: "Twist ϑ at x (degrees)", value: Number.isFinite(r.twist_deg) ? `${formatNumber(cleanNoise(r.twist_deg, Math.abs(r.theta_max) * 180 / Math.PI))} °` : "—" },
    { id: "theta_max", label: "Largest twist ϑ_max", value: `${rad(r.theta_max)} at x = ${show(span, r.x_theta_max)}` },
    { id: "J_T", label: "Torsion constant J_T", value: show(lengthPowConv(4, units), r.J_T) },
    { id: "W_T", label: "Torsional section modulus W_T", value: show(lengthPowConv(3, units), r.W_T) },
    ...(warping || r.C_T > 0 ? [{ id: "C_T", label: "Warping constant C_T", value: show(lengthPowConv(6, units), r.C_T) }] : []),
    ...(Number.isFinite(r.alpha) ? [{ id: "alpha", label: "Warping parameter α = L √(G J_T/(E C_T))", value: formatNumber(r.alpha), hint }] : []),
    { id: "tau_sv_max", label: "Max Saint-Venant shear stress τ_SV", value: show(stress, r.tau_sv_max) },
    ...(warping ? [
      { id: "sigma_w_max", label: "Max warping normal stress σ_ω", value: show(stress, r.sigma_w_max) },
      { id: "B_max", label: "Max bimoment |B|", value: show(bimomentConv(units), r.B_max) },
    ] : []),
    { id: "T_left", label: "End torque T at x = 0+", value: show(torque, r.T_left) },
    { id: "T_right", label: "End torque T at x = L−", value: show(torque, r.T_right) },
  ];
  return (
    <Card title="Key results">
      <table className="w-full text-sm" data-testid="torsion-results">
        <tbody>
          {rows.map((x) => (
            <tr key={x.id} className="border-b border-border last:border-0" data-testid={`result-${x.id}`}>
              <td className="py-1.5 pr-3 text-muted">{x.label}</td>
              <td className="py-1.5 text-right font-mono font-semibold">
                {x.value}
                {x.hint && <div className="font-sans text-xs font-normal text-muted" data-testid="result-alpha-hint">{x.hint}</div>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {r.note && <p className="mt-3 rounded-lg bg-bg p-3 text-xs text-muted" data-testid="torsion-note">{r.note}</p>}
    </Card>
  );
}

function StepsTable({ r, units }: { r: TorsionResult; units: UnitSystem }) {
  const scale: Record<string, number> = {};
  for (const s of r.steps) if (Number.isFinite(s.value)) scale[s.unit] = Math.max(scale[s.unit] ?? 0, Math.abs(s.value));
  return (
    <Card title="Formulary steps">
      <div className="max-h-96 overflow-auto">
        <table className="w-full text-sm" data-testid="torsion-steps">
          <tbody>
            {r.steps.map((s, i) => {
              const c = stepConv(s.unit, units);
              return (
                <tr key={i} className="border-b border-border last:border-0" data-testid="torsion-step-row">
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
        Order as in the formulary: section constants J_T, W_T, C_T and ω_max, the parameters α and μ, the Saint-Venant rate of twist, the end torques, then twist, torque split, bimoment and stresses.
        A dash means the quantity does not exist for this section or mode.
      </p>
    </Card>
  );
}

// ---------------- drawn section preview ----------------

/** Read-only mid-line sketch of the section drawn in tab 5 (x₃ points down, as on screen). */
function DrawnPreview({ geometry }: { geometry: ShearGeometry }) {
  const { nodes, walls } = geometry;
  const W = 220;
  const H = 130;
  const pad = 14;
  if (!nodes.length) return null;
  const xs = nodes.map((n) => n.x2);
  const ys = nodes.map((n) => n.x3);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const k = Math.min((W - 2 * pad) / Math.max(x1 - x0, 1e-9), (H - 2 * pad) / Math.max(y1 - y0, 1e-9));
  const ox = (W - k * (x1 - x0)) / 2;
  const oy = (H - k * (y1 - y0)) / 2;
  const at = (n: { x2: number; x3: number }): [number, number] => [ox + k * (n.x2 - x0), oy + k * (n.x3 - y0)];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full max-w-[240px] text-primary-ink" role="img" aria-label="Drawn section mid-lines" data-testid="torsion-drawn-preview">
      {walls.map((w, i) => {
        const a = nodes[w.i];
        const b = nodes[w.j];
        if (!a || !b) return null;
        const [ax, ay] = at(a);
        const [bx, by] = at(b);
        return <line key={i} x1={ax} y1={ay} x2={bx} y2={by} stroke="currentColor" strokeWidth={3} strokeLinecap="round" />;
      })}
      {nodes.map((n, i) => {
        const [cx, cy] = at(n);
        return <circle key={i} cx={cx} cy={cy} r={2.5} className="fill-current text-muted" />;
      })}
    </svg>
  );
}
