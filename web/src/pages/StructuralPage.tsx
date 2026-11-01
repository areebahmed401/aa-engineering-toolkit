// Dedicated structural page: section designer + beam builder with a live free-body diagram.
// All numbers come from the Python tools structural.section_properties and structural.beam_analysis.
import { BookOpen, Calculator, Check, CircleAlert, CircleCheck, FileDown, Link2, Plus, RotateCcw, Trash2, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Navigate, useParams, useSearchParams } from "react-router-dom";
import { ChartView } from "../components/ChartView";
import { FbdDiagram } from "../components/FbdDiagram";
import { NumberInput, type Conversion } from "../components/NumberInput";
import { SectionDrawing } from "../components/SectionDrawing";
import { cn, SECTION_META, Spinner } from "../components/ui";
import { useEngine } from "../lib/engine";
import { usePrefs } from "../lib/prefs";
import { download, markdownReport } from "../lib/report";
import { defaultValues, fieldsFromSchema } from "../lib/schema";
import {
  BEAM_TOOL, beamInputs, defaultState, determinacy, fromToolInputs, LOAD_UNITS, loadErrors, mergeState, SECTION_TOOL,
  sectionInputs, shapeMeta, stateDiff, SUPPORTS, type BeamValues, type FbdFormat, type Load, type LoadKind,
  type Reactions, type StructuralState, type SupportKind,
} from "../lib/structural";
import type { ResultField, RunResponse } from "../lib/types";
import { decodeInputs, encodeInputs } from "../lib/urlState";
import { displayUnit, formatNumber, toDisplay, toSI, type UnitSystem } from "../lib/units";

type Tab = "section" | "beam";
const TOOL_OF: Record<Tab, string> = { section: SECTION_TOOL, beam: BEAM_TOOL };
const TAB_OF: Record<string, Tab> = { [SECTION_TOOL]: "section", [BEAM_TOOL]: "beam" };

/** Tools that open this page instead of the generic form. */
export const STRUCTURAL_PAGE_TOOLS = new Set(Object.keys(TAB_OF));

// ---------------- unit helpers ----------------

function unitConv(siUnit: string, system: UnitSystem): Conversion {
  return { unit: displayUnit(siUnit, system), toSI: (v) => toSI(v, siUnit, system), fromSI: (v) => toDisplay(v, siUnit, system) };
}

/** Section dimensions read better in mm / in than in m / ft. */
function smallLength(system: UnitSystem): Conversion {
  const f = system === "SI" ? 1e-3 : 0.0254;
  return { unit: system === "SI" ? "mm" : "in", toSI: (v) => v * f, fromSI: (v) => v / f };
}

function stressConv(system: UnitSystem): Conversion {
  const f = system === "SI" ? 1e6 : 6.894757293168e6;
  return { unit: system === "SI" ? "MPa" : "ksi", toSI: (v) => v * f, fromSI: (v) => v / f };
}

const fmtWith = (c: Conversion) => (v: number) => `${formatNumber(c.fromSI(v))} ${c.unit}`;

/** Old `#/tool/structural.*` links open this page with their inputs carried over. */
export function StructuralRedirect({ toolId, encoded }: { toolId: string; encoded: string | null }) {
  const state = fromToolInputs(toolId, decodeInputs(encoded));
  const i = encodeInputs(state, {});
  return <Navigate to={`/structural?tab=${TAB_OF[toolId]}${i ? `&i=${i}` : ""}`} replace />;
}

export function StructuralRoute() {
  const { toolId = "" } = useParams();
  const [params] = useSearchParams();
  return <StructuralRedirect toolId={toolId} encoded={params.get("i")} />;
}

// ---------------- page ----------------

type Stored = { res: RunResponse; key: string };
/** Functional patches so several edits in one tick all apply. */
type Update = (patch: Partial<StructuralState> | ((s: StructuralState) => Partial<StructuralState>)) => void;

export function StructuralPage() {
  const [params, setParams] = useSearchParams();
  const { schema, choices, progress, run } = useEngine();
  const { units } = usePrefs();
  const tab: Tab = params.get("tab") === "beam" ? "beam" : "section";
  const urlI = params.get("i");

  const sectionTool = schema?.tools.find((t) => t.id === SECTION_TOOL);
  const beamTool = schema?.tools.find((t) => t.id === BEAM_TOOL);
  const sectionFields = useMemo(() => (sectionTool ? fieldsFromSchema(sectionTool.inputs) : []), [sectionTool]);
  const beamFields = useMemo(() => (beamTool ? fieldsFromSchema(beamTool.inputs) : []), [beamTool]);
  const defaults = useMemo(
    () => (sectionTool && beamTool ? defaultState(defaultValues(sectionFields), defaultValues(beamFields)) : null),
    [sectionTool, beamTool, sectionFields, beamFields],
  );
  const meta = useMemo(() => shapeMeta(sectionTool), [sectionTool]);

  const [state, setState] = useState<StructuralState | null>(null);
  const [stored, setStored] = useState<Partial<Record<Tab, Stored>>>({});
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const written = useRef<string | null | undefined>(undefined); // last `i` this page put in the URL
  const runId = useRef(0);

  // initial state, and again when a different shared link is opened while on the page
  useEffect(() => {
    if (!defaults || urlI === written.current) return;
    written.current = urlI;
    setState(mergeState(defaults, decodeInputs(urlI)));
  }, [defaults, urlI]);

  const encoded = state && defaults ? encodeInputs(stateDiff(state, defaults), {}) : "";

  // keep the URL in step with the inputs
  useEffect(() => {
    if (!state || encoded === (written.current ?? "")) return;
    const from = urlI;
    const id = setTimeout(() => {
      // skip if a link was opened meanwhile; keep the current tab (it may have changed)
      const now = new URLSearchParams(location.hash.split("?")[1] ?? "");
      if (now.get("i") !== from) return;
      written.current = encoded || null;
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        if (encoded) next.set("i", encoded);
        else next.delete("i");
        return next;
      }, { replace: true });
    }, 250);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [encoded]);

  const inputsFor = useCallback((t: Tab, s: StructuralState) => (t === "section" ? sectionInputs(s) : beamInputs(s)), []);

  const blocked = useMemo(() => {
    if (!state) return true;
    if (tab === "beam") {
      return determinacy(state.beam.left_support, state.beam.right_support).status === "mechanism"
        || Object.keys(loadErrors(state.beam)).length > 0 || !(state.beam.length > 0);
    }
    return false;
  }, [state, tab]);

  const calculate = useCallback(async (t: Tab, s: StructuralState) => {
    const inputs = inputsFor(t, s);
    const id = ++runId.current;
    setBusy(true);
    const res = await run(TOOL_OF[t], inputs);
    if (id !== runId.current) return; // a newer edit superseded this run
    setBusy(false);
    setStored((prev) => ({ ...prev, [t]: { res, key: JSON.stringify(inputs) } }));
  }, [inputsFor, run]);

  // live results: recalculate shortly after each edit once Python is ready
  const ready = progress.stage === "ready";
  const key = state ? JSON.stringify(inputsFor(tab, state)) : "";
  useEffect(() => {
    if (!state || !ready || blocked || stored[tab]?.key === key) return;
    const id = setTimeout(() => void calculate(tab, state), 300);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tab, ready, blocked]);

  if (!schema || !sectionTool || !beamTool || !state || !defaults) {
    return <div className="flex items-center gap-2 text-muted"><Spinner /> Loading tools…</div>;
  }

  const tool = tab === "section" ? sectionTool : beamTool;
  const current = stored[tab];
  const response = current?.res ?? null;
  const stale = current ? current.key !== key : false;
  const Icon = SECTION_META.structural.icon;

  const update: Update = (patch) => setState((s) => (s ? { ...s, ...(typeof patch === "function" ? patch(s) : patch) } : s));
  const setTab = (t: Tab) => setParams(encoded ? { tab: t, i: encoded } : { tab: t }, { replace: false });

  const link = () => `${location.origin}${location.pathname}#/structural?tab=${tab}${encoded ? `&i=${encoded}` : ""}`;
  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(link());
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      window.prompt("Copy this link", link());
    }
  };
  const exportReport = () => {
    if (!response?.ok) return;
    const fields = tab === "section" ? sectionFields : beamFields;
    const md = markdownReport({ tool, fields, values: inputsFor(tab, state), results: response.result.fields, system: units, version: schema.version, link: link() });
    download(`${tool.id}.md`, md, "text/markdown");
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
          <Icon className={cn("h-4 w-4", SECTION_META.structural.text)} />
          <span>{schema.sections.structural} · Structural designer</span>
        </div>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold tracking-tight">{tool.name}</h1>
            <p className="max-w-3xl text-muted">{tool.description}</p>
          </div>
          <div className="flex rounded-xl border border-border bg-surface p-1 text-sm" role="tablist">
            {(["section", "beam"] as const).map((t) => (
              <button key={t} role="tab" aria-selected={tab === t} data-testid={`tab-${t}`}
                className={cn("rounded-lg px-4 py-1.5 transition", tab === t ? "bg-primary text-on-primary shadow-sm" : "text-muted hover:text-ink")}
                onClick={() => setTab(t)}>
                {t === "section" ? "1 · Section" : "2 · Beam"}
              </button>
            ))}
          </div>
        </div>
      </header>

      {tab === "section"
        ? <SectionTab state={state} update={update} meta={meta} profiles={choices?.profiles ?? []} metals={choices?.materials.metal ?? []} response={response} units={units} />
        : <BeamTab state={state} update={update} response={response} units={units} onEditSection={() => setTab("section")} />}

      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="btn-primary" disabled={busy || blocked} data-testid="calculate" onClick={() => void calculate(tab, state)}>
          {busy ? <Spinner /> : <Calculator className="h-4 w-4" />}
          {busy ? (ready ? "Calculating…" : "Waiting for Python…") : "Calculate"}
        </button>
        <button type="button" className="btn-ghost" onClick={() => { setState(defaults); setStored({}); }}>
          <RotateCcw className="h-4 w-4" /> Reset
        </button>
        <button type="button" className="btn-ghost" onClick={copyLink}>
          {copied ? <Check className="h-4 w-4 text-ok" /> : <Link2 className="h-4 w-4" />} {copied ? "Copied" : "Copy link"}
        </button>
        <button type="button" className="btn-ghost" onClick={exportReport} disabled={!response?.ok || blocked}>
          <FileDown className="h-4 w-4" /> Report
        </button>
        <span className="text-xs text-muted">
          {blocked ? "Fix the beam inputs above to see results."
            : !ready && progress.stage !== "error" ? `Python is loading (${progress.percent}%); results appear when it is ready.`
            : response?.ok ? `Updates live as you edit · ${response.elapsed_ms} ms${stale ? " · updating…" : ""}` : "Updates live as you edit"}
        </span>
      </div>

      <footer className="flex items-start gap-2 text-xs text-muted">
        <BookOpen className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span><span className="font-medium">Reference:</span> {tool.reference}</span>
      </footer>
    </div>
  );
}

// ---------------- shared bits ----------------

function Card({ title, children, className, aside }: { title: string; children: ReactNode; className?: string; aside?: ReactNode }) {
  return (
    <section className={cn("card p-5", className)}>
      <div className="mb-4 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div className="flex gap-2 rounded-xl border border-fail/30 bg-fail/5 p-3 text-sm text-fail" data-testid="run-error">
      <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

function Select({ label, value, options, onChange, testId }: { label: string; value: string; options: { value: string; label: string }[]; onChange: (v: string) => void; testId?: string }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      <select className="input" value={value} onChange={(e) => onChange(e.target.value)} data-testid={testId}>
        {!options.some((o) => o.value === value) && <option value={value}>{value}</option>}
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

function fieldMap(fields: ResultField[]): Record<string, ResultField> {
  return Object.fromEntries(fields.map((f) => [f.name, f]));
}

// ---------------- section tab ----------------

const SHAPE_ICONS: Record<string, string> = {
  rectangle: "M7 4h10v16H7z",
  square_tube: "M5 5h14v14H5z M8 8v8h8V8z",
  rectangular_tube: "M7 3h10v18H7z M9.5 5.5v13h5v-13z",
  circle: "M12 4a8 8 0 1 0 0.01 0z",
  hollow_circle: "M12 4a8 8 0 1 0 0.01 0z M12 8a4 4 0 1 1 -0.01 0z",
  i_beam: "M5 3h14v3h-5.5v12H19v3H5v-3h5.5V6H5z",
  c_beam: "M6 3h12v3H9.5v12H18v3H6z",
  t_beam: "M4 4h16v3.5h-6.25V20h-3.5V7.5H4z",
  z_beam: "M5 3h8.5v15H19v3h-8.5V6H5z",
  l_beam: "M6 3h3.5v14.5H19V21H6z",
  profile: "M5 3h14v2.5h-5.75v13H19V21H5v-2.5h5.75v-13H5z",
};

function SectionTab({ state, update, meta, profiles, metals, response, units }: {
  state: StructuralState; update: Update; meta: ReturnType<typeof shapeMeta>;
  profiles: string[]; metals: string[]; response: RunResponse | null; units: UnitSystem;
}) {
  const shape = state.section.shape;
  const fields = meta.fields[shape] ?? [];
  const small = smallLength(units);
  const setDim = (name: string, v: unknown) => update((s) => ({ section: { ...s.section, [name]: v } }));
  const errors: Record<string, string> = {};
  if (response && !response.ok) for (const f of response.error.fields ?? []) errors[f.loc[f.loc.length - 1]] = f.msg;
  const chart = response?.ok ? response.charts.find((c) => c.id === "section") : undefined;

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <Card title="Shape and dimensions">
        <div className="grid grid-cols-4 gap-2 sm:grid-cols-6 xl:grid-cols-4" role="radiogroup" aria-label="Section shape">
          {meta.shapes.map((s) => (
            <button key={s} type="button" role="radio" aria-checked={shape === s} data-testid={`shape-${s}`} title={meta.labels[s]}
              className={cn("flex flex-col items-center gap-1 rounded-xl border p-2 text-[11px] leading-tight transition",
                shape === s ? "border-primary bg-primary/10 text-primary-ink" : "border-border text-muted hover:border-primary/50 hover:text-ink")}
              onClick={() => update((st) => ({ section: { ...st.section, shape: s } }))}>
              <svg viewBox="0 0 24 24" className="h-7 w-7"><path d={SHAPE_ICONS[s] ?? ""} fill="currentColor" fillRule="evenodd" opacity={0.85} /></svg>
              <span className="text-center">{meta.labels[s] ?? s}</span>
            </button>
          ))}
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="dimension-fields">
          {fields.map(([name, label]) =>
            name === "profile" ? (
              <Select key={name} label={label} value={String(state.section.profile ?? "")} testId="field-profile"
                options={profiles.map((p) => ({ value: p, label: p }))} onChange={(v) => setDim("profile", v)} />
            ) : (
              <NumberInput key={name} label={label} value={state.section[name] as number} conv={small} positive testId={`field-${name}`}
                error={errors[name]} onChange={(v) => setDim(name, v)} />
            ),
          )}
          <Select label="Material" value={state.material} testId="field-material"
            options={metals.map((m) => ({ value: m, label: m }))} onChange={(v) => update({ material: v })} />
        </div>
        <p className="mt-4 text-xs text-muted">Only the dimensions this shape uses are shown. Bending about the horizontal axis is the strong axis (Iyy).</p>
      </Card>

      <Card title={response?.ok ? `Section · ${String(fieldMap(response.result.fields).designation?.value ?? "")}` : "Section"}>
        {!response && <p className="text-sm text-muted">The section appears here once Python is ready.</p>}
        {response && !response.ok && <ErrorBox message={response.error.message} />}
        {response?.ok && (
          <div className="grid grid-cols-1 items-start gap-5 2xl:grid-cols-2" data-testid="results">
            {chart && <SectionDrawing chart={chart} length={fmtWith(small)}
              dims={fields.filter(([n]) => n !== "profile").map(([n, l]) => ({ label: l.split(" ").pop()!, value: fmtWith(small)(state.section[n] as number) }))} />}
            <PropertyTable fields={response.result.fields} units={units} />
          </div>
        )}
      </Card>
    </div>
  );
}

const HIDDEN = new Set(["shape", "designation"]);

function PropertyTable({ fields, units }: { fields: ResultField[]; units: UnitSystem }) {
  const small = smallLength(units);
  return (
    <table className="w-full text-sm" data-testid="property-table">
      <tbody>
        {fields.filter((f) => f.summary && typeof f.value === "number" && !HIDDEN.has(f.name)).map((f) => {
          const conv = f.unit === "m" ? small : unitConv(f.unit, units);
          return (
            <tr key={f.name} className="border-b border-border last:border-0" data-testid={`result-${f.name}`}>
              <td className="py-1.5 pr-3 text-muted">{f.label}</td>
              <td className="py-1.5 text-right font-mono font-semibold">{formatNumber(conv.fromSI(f.value as number))}</td>
              <td className="py-1.5 pl-2 text-xs text-muted">{f.unit ? conv.unit : ""}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ---------------- beam tab ----------------

const SUPPORT_LABEL: Record<SupportKind, string> = { fixed: "Fixed", pinned: "Pinned", roller: "Roller", free: "Free" };
const LOAD_LABEL: Record<LoadKind, string> = { point: "Point load P", udl: "UDL w", moment: "Moment M" };
const LOAD_HINT: Record<LoadKind, string> = { point: "down +", udl: "down +", moment: "CCW +" };

function BeamTab({ state, update, response, units, onEditSection }: {
  state: StructuralState; update: Update; response: RunResponse | null; units: UnitSystem; onEditSection: () => void;
}) {
  const beam = state.beam;
  const setBeam = (p: Partial<BeamValues> | ((b: BeamValues) => Partial<BeamValues>)) =>
    update((s) => ({ beam: { ...s.beam, ...(typeof p === "function" ? p(s.beam) : p) } }));
  const setLoad = (i: number, p: Partial<Load>) => setBeam((b) => ({ loads: b.loads.map((l, j) => (j === i ? { ...l, ...p } : l)) }));
  const addLoad = (kind: LoadKind) => {
    const x = kind === "udl" ? 0 : kind === "moment" ? beam.length * 0.75 : beam.length / 2;
    setBeam((b) => ({ loads: [...b.loads, { kind, value: kind === "moment" ? 5e3 : 10e3, x, x_end: null }] }));
  };
  const det = determinacy(beam.left_support, beam.right_support, beam.theory);
  const lerr = loadErrors(beam);
  const span = unitConv("m", units);
  const fmt: FbdFormat = {
    force: fmtWith(unitConv("N", units)), udl: fmtWith(unitConv("N/m", units)),
    moment: fmtWith(unitConv("N·m", units)), length: (v) => `${formatNumber(span.fromSI(v), 3)} ${span.unit}`,
  };
  const r = response?.ok ? fieldMap(response.result.fields) : null;
  const reactions: Reactions | null = r && det.status !== "mechanism"
    ? { Ay: r.Ay?.value as number | null, MA: r.MA?.value as number | null, By: r.By?.value as number | null, MB: r.MB?.value as number | null }
    : null;
  const sectionName = state.section.shape === "profile" ? String(state.section.profile) : state.section.shape.replace(/_/g, " ");

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <Card title="Beam" aside={
          <button type="button" className="text-xs text-primary-ink hover:underline" onClick={onEditSection}>
            Section: <span className="font-medium capitalize">{sectionName}</span> · {state.material} (edit)
          </button>}>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <NumberInput label="Span L" value={beam.length} conv={span} positive testId="field-length" onChange={(v) => setBeam({ length: v ?? 0 })} />
            <div>
              <span className="label">Beam theory</span>
              <div className="flex rounded-lg border border-border p-0.5 text-xs" role="group" aria-label="Beam theory">
                {(["EB", "TB"] as const).map((t) => (
                  <button key={t} type="button" aria-pressed={beam.theory === t} data-testid={`theory-${t}`}
                    className={cn("flex-1 rounded-md px-2 py-1.5 transition", beam.theory === t ? "bg-primary text-on-primary" : "text-muted hover:text-ink")}
                    onClick={() => setBeam({ theory: t })}>
                    {t === "EB" ? "Euler-Bernoulli" : "Timoshenko"}
                  </button>
                ))}
              </div>
            </div>
            {(["left_support", "right_support"] as const).map((side) => (
              <div key={side}>
                <span className="label">{side === "left_support" ? "Left support (x = 0)" : "Right support (x = L)"}</span>
                <div className="grid grid-cols-4 gap-1 rounded-lg border border-border p-0.5 text-xs" role="radiogroup" aria-label={side}>
                  {SUPPORTS.map((s) => (
                    <button key={s} type="button" role="radio" aria-checked={beam[side] === s} data-testid={`${side}-${s}`}
                      className={cn("rounded-md px-1 py-1.5 transition", beam[side] === s ? "bg-primary text-on-primary" : "text-muted hover:text-ink")}
                      onClick={() => setBeam({ [side]: s })}>
                      {SUPPORT_LABEL[s]}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-5">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-semibold text-muted">Loads</span>
              <div className="flex gap-1">
                {(["point", "udl", "moment"] as const).map((k) => (
                  <button key={k} type="button" className="btn-ghost px-2 py-1 text-xs" data-testid={`add-${k}`} onClick={() => addLoad(k)}>
                    <Plus className="h-3.5 w-3.5" /> {k === "udl" ? "UDL" : k === "point" ? "Point" : "Moment"}
                  </button>
                ))}
              </div>
            </div>
            {beam.loads.length === 0 && <p className="rounded-lg bg-bg p-3 text-xs text-muted">No loads: add a point load, UDL or moment.</p>}
            <div className="space-y-2">
              {beam.loads.map((l, i) => (
                <div key={i} className="rounded-lg bg-bg p-3" data-testid={`load-${i}`}>
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <select className="input w-auto py-1 text-xs" value={l.kind} aria-label={`Load ${i + 1} type`} data-testid={`load-${i}-kind`}
                      onChange={(e) => setLoad(i, { kind: e.target.value as LoadKind })}>
                      {(["point", "udl", "moment"] as const).map((k) => <option key={k} value={k}>{LOAD_LABEL[k]}</option>)}
                    </select>
                    <button type="button" className="rounded p-1 text-muted hover:text-fail" aria-label={`Remove load ${i + 1}`} onClick={() => setBeam((b) => ({ loads: b.loads.filter((_, j) => j !== i) }))}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <div className={cn("grid gap-2", l.kind === "udl" ? "grid-cols-3" : "grid-cols-2")}>
                    <NumberInput label={`Value (${LOAD_HINT[l.kind]})`} value={l.value} conv={unitConv(LOAD_UNITS[l.kind], units)} testId={`load-${i}-value`} onChange={(v) => setLoad(i, { value: v ?? 0 })} />
                    <NumberInput label={l.kind === "udl" ? "From x" : "At x"} value={l.x} conv={span} min={0} testId={`load-${i}-x`} onChange={(v) => setLoad(i, { x: v ?? 0 })} />
                    {l.kind === "udl" && (
                      <NumberInput label="To x" value={l.x_end} conv={span} nullable placeholder="end (L)" testId={`load-${i}-x_end`} onChange={(v) => setLoad(i, { x_end: v })} />
                    )}
                  </div>
                  {lerr[i] && <p className="mt-1 text-xs text-fail">{lerr[i]}</p>}
                </div>
              ))}
            </div>
          </div>
        </Card>

        <Card title="Free-body diagram">
          <DeterminacyBanner det={det} />
          <div className="mt-3 overflow-x-auto rounded-xl border border-border bg-bg/60 p-2">
            <FbdDiagram beam={beam} fmt={fmt} reactions={reactions} />
          </div>
          <p className="mt-2 text-xs text-muted">
            <span className="text-primary-ink">■</span> applied loads · <span className="text-structural">■</span> UDL ·{" "}
            <span className="text-thermo">■</span> moments · <span className="text-ok">■</span> reactions (after calculation)
          </p>
        </Card>
      </div>

      <BeamResults response={det.status === "mechanism" ? null : response} units={units} />
    </div>
  );
}

function DeterminacyBanner({ det }: { det: ReturnType<typeof determinacy> }) {
  const style = det.status === "mechanism" ? "border-fail/40 bg-fail/10 text-fail"
    : det.status === "indeterminate" ? "border-warn/40 bg-warn/10 text-ink" : "border-ok/40 bg-ok/10 text-ink";
  const IconC = det.status === "mechanism" ? TriangleAlert : det.status === "indeterminate" ? CircleAlert : CircleCheck;
  return (
    <div className={cn("flex gap-3 rounded-xl border p-3", style)} data-testid="determinacy" data-status={det.status} data-degree={det.degree}>
      <IconC className={cn("mt-0.5 h-5 w-5 shrink-0", det.status === "mechanism" ? "text-fail" : det.status === "indeterminate" ? "text-warn" : "text-ok")} />
      <div className="text-sm">
        <div className="font-semibold">{det.title}</div>
        <div className="text-muted">{det.detail}</div>
        {det.status !== "mechanism" && <div className="mt-1 text-xs">Method: <span className="font-medium">{det.method}</span></div>}
      </div>
    </div>
  );
}

function Stat({ label, value, sub, testId }: { label: string; value: string; sub?: string; testId?: string }) {
  return (
    <div className="rounded-xl border border-border px-3 py-2" data-testid={testId}>
      <div className="truncate text-xs text-muted" title={label}>{label}</div>
      <div className="font-mono text-base font-semibold">{value}</div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </div>
  );
}

function BeamResults({ response, units }: { response: RunResponse | null; units: UnitSystem }) {
  if (!response) return null;
  if (!response.ok) return <ErrorBox message={response.error.message} />;
  const r = fieldMap(response.result.fields);
  const num = (n: string) => (typeof r[n]?.value === "number" ? (r[n].value as number) : null);
  const show = (n: string, c: Conversion) => {
    const v = num(n);
    return v === null ? "—" : `${formatNumber(c.fromSI(v))} ${c.unit}`;
  };
  const span = unitConv("m", units);
  const at = (n: string) => (num(n) === null ? undefined : `at x = ${formatNumber(span.fromSI(num(n)!), 3)} ${span.unit}`);
  const force = unitConv("N", units);
  const moment = unitConv("N·m", units);
  const util = num("utilisation");
  const utilColor = util === null ? "bg-muted" : util < 0.8 ? "bg-ok" : util < 1 ? "bg-warn" : "bg-fail";
  const reactions = [
    { n: "Ay", label: "R_A (left vertical)", c: force }, { n: "MA", label: "M_A (left moment)", c: moment },
    { n: "By", label: "R_B (right vertical)", c: force }, { n: "MB", label: "M_B (right moment)", c: moment },
  ].filter((x) => num(x.n) !== null);

  return (
    <div className="space-y-6" data-testid="results">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card title="Reactions (up +, CCW +)">
          <div className="grid grid-cols-2 gap-2">
            {reactions.map((x) => (
              <Stat key={x.n} label={x.label} value={show(x.n, x.c)} testId={`result-${x.n}`} />
            ))}
          </div>
          <p className="mt-3 text-xs text-muted">{String(r.method?.value ?? "")}</p>
        </Card>
        <Card title="Peak values">
          <div className="grid grid-cols-2 gap-2">
            <Stat label="Max |deflection|" value={show("max_deflection", smallLength(units))} sub={at("x_max_deflection")} testId="result-max_deflection" />
            <Stat label="Max |moment|" value={show("max_moment", moment)} sub={at("x_max_moment")} testId="result-max_moment" />
            <Stat label="Max |shear|" value={show("max_shear", force)} sub={at("x_max_shear")} testId="result-max_shear" />
            <Stat label="Section" value={String(r.section?.value ?? "—")} />
          </div>
        </Card>
        <Card title="Bending stress">
          <div className="grid grid-cols-2 gap-2">
            <Stat label="Max bending stress σ" value={show("max_bending_stress", stressConv(units))} sub={at("x_max_moment")} testId="result-max_bending_stress" />
            <Stat label="Yield strength fy" value={show("yield_strength", stressConv(units))} />
          </div>
          <div className="mt-3" data-testid="result-utilisation">
            <div className="mb-1 flex justify-between text-xs">
              <span className="text-muted">Utilisation σ / fy</span>
              <span className={cn("font-mono font-semibold", util !== null && util >= 1 && "text-fail")}>{util === null ? "—" : `${formatNumber(util * 100, 3)} %`}</span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full bg-bg">
              <div className={cn("h-full rounded-full transition-all", utilColor)} style={{ width: `${Math.min(100, (util ?? 0) * 100)}%` }} />
            </div>
            {util !== null && util >= 1 && <p className="mt-1 text-xs text-fail">Bending stress exceeds yield: choose a larger section.</p>}
          </div>
        </Card>
      </div>

      {response.charts.length > 0 && (
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {response.charts.map((c) => (
            <div key={c.id} className="card p-3"><ChartView chart={c} /></div>
          ))}
        </section>
      )}
    </div>
  );
}

