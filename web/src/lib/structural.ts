// Pure logic for the structural page: state shape, determinacy, shape fields and the FBD layout.
// The calculations themselves stay in Python (structural.section_properties / structural.beam_analysis).
import { DEFAULT_POLE_MODEL, normalizeModel, POLE_TOOL, toolInputs, type PoleModel } from "./polplan";
import type { JsonSchema, ToolSchema } from "./types";

export const SECTION_TOOL = "structural.section_properties";
export const BEAM_TOOL = "structural.beam_analysis";
export const TORSION_TOOL = "structural.torsion";
export { POLE_TOOL };
export const SHEAR_TOOL = "structural.shear_flow";

export type SupportKind = "fixed" | "pinned" | "roller" | "free";
export type LoadKind = "point" | "udl" | "moment";
export type Load = { kind: LoadKind; value: number; x: number; x_end: number | null };

export type SectionValues = Record<string, unknown> & { shape: string };
export type BeamValues = {
  length: number;
  left_support: SupportKind;
  right_support: SupportKind;
  loads: Load[];
  theory: "EB" | "TB";
  n_elem: number;
};
/** Torsion end condition: fixed holds twist and warping, fork holds twist only, free holds nothing. */
export type TorsionSupport = "fixed" | "fork" | "free";
export type TorsionMode = "free" | "restrained";
export type TorsionSource = "library" | "drawn";
/** Point torque T [N·m] about +x1 at x [m]. */
export type TorqueLoad = { x: number; T: number };
export type TorsionValues = {
  length: number; position: number; mode: TorsionMode; section_source: TorsionSource; eta3: number;
  left_support: TorsionSupport; right_support: TorsionSupport; loads: TorqueLoad[]; m_t: number;
  Q2: number; Q3: number; e2: number; e3: number;
};
/** Thin-walled shear-flow tab: nodes (m, x3 pointing down) and walls i→j, plus the loads (SI). */
export type ShearNode = { x2: number; x3: number };
export type ShearWall = { i: number; j: number; h: number; G: number };
export type ShearGeometry = { nodes: ShearNode[]; walls: ShearWall[] };
export type ShearValues = ShearGeometry & {
  Q2: number; Q3: number; Mt: number; load_at_shear_centre: boolean; a2: number; a3: number;
};
/** Everything the page edits: the section and material are shared by the first three tabs. */
export type StructuralState = { section: SectionValues; material: string; beam: BeamValues; torsion: TorsionValues; poles: PoleModel; shear: ShearValues };

const TORSION_DEFAULTS: TorsionValues = {
  length: 1, position: 1, mode: "restrained", section_source: "library", eta3: 1, left_support: "fixed", right_support: "free",
  loads: [{ x: 1, T: 200 }], m_t: 0, Q2: 0, Q3: 0, e2: 0, e3: 0,
};
export const TORSION_SUPPORTS: TorsionSupport[] = ["fixed", "fork", "free"];

function normalizeLoads(v: unknown): TorqueLoad[] | null {
  if (!Array.isArray(v)) return null;
  return v.filter((l): l is TorqueLoad => !!l && typeof (l as TorqueLoad).x === "number" && typeof (l as TorqueLoad).T === "number")
    .map((l) => ({ x: l.x, T: l.T }));
}

/** Torsion defaults from the tool schema; the default load is the schema's torque at x = L. */
function torsionFromSchema(schema: Record<string, unknown>): TorsionValues {
  const base = { ...TORSION_DEFAULTS } as Record<string, unknown>;
  for (const k of Object.keys(TORSION_DEFAULTS)) if (k !== "loads" && schema[k] !== undefined) base[k] = schema[k];
  const listed = normalizeLoads(schema.loads);
  base.loads = listed && listed.length ? listed : [{ x: base.length as number, T: typeof schema.torque === "number" ? schema.torque : 200 }];
  return base as unknown as TorsionValues;
}

/**
 * Torsion state from a (possibly partial) decoded link. Old links carried { length, torque, position } for a cantilever
 * under an end torque: they have no `loads`, so they become fixed–free, restrained, one torque at x = L.
 */
function mergeTorsion(defaults: TorsionValues, p: unknown): TorsionValues {
  if (!p || typeof p !== "object") return defaults;
  const t = p as Record<string, unknown>;
  const known: Record<string, unknown> = {};
  for (const k of Object.keys(defaults)) if (t[k] !== undefined) known[k] = t[k];
  if ("loads" in t) return { ...defaults, ...known, loads: normalizeLoads(t.loads) ?? defaults.loads } as TorsionValues;
  const length = typeof t.length === "number" ? t.length : defaults.length;
  const torque = typeof t.torque === "number" ? t.torque : 200;
  return { ...defaults, ...known, loads: [{ x: length, T: torque }], mode: "restrained", left_support: "fixed", right_support: "free" } as TorsionValues;
}

export const SUPPORTS: SupportKind[] = ["fixed", "pinned", "roller", "free"];
export const LOAD_UNITS: Record<LoadKind, string> = { point: "N", udl: "N/m", moment: "N·m" };

// ---------------- shapes ----------------

export type ShapeMeta = {
  shapes: string[]; // in the order of the Python Literal
  fields: Record<string, [name: string, label: string][]>;
  labels: Record<string, string>;
};

type ShapeSchema = JsonSchema & { shape_fields?: ShapeMeta["fields"]; shape_labels?: ShapeMeta["labels"] };

/** Shape → relevant dimensions (ordered), read from the "shape_fields" hint the Python schema carries. */
export function shapeMeta(tool: ToolSchema | undefined): ShapeMeta {
  const shape = tool?.inputs.properties?.shape as ShapeSchema | undefined;
  const fields = shape?.shape_fields ?? {};
  const shapes = (shape?.enum?.map(String) ?? Object.keys(fields)).filter((s) => s in fields);
  return { shapes, fields, labels: shape?.shape_labels ?? {} };
}

// ---------------- state <-> tool inputs ----------------

export function sectionInputs(s: StructuralState): Record<string, unknown> {
  return { ...s.section, material: s.material };
}

export function beamInputs(s: StructuralState): Record<string, unknown> {
  return { section: s.section, material: s.material, ...s.beam };
}

/**
 * Inputs of structural.torsion. Always sends `loads` (and torque 0, the tool's legacy fallback when the list is empty);
 * the drawn section is sent only when it is the source, the off-shear-centre force only in free mode.
 */
export function torsionInputs(s: StructuralState): Record<string, unknown> {
  const { Q2, Q3, e2, e3, eta3, section_source, ...rest } = s.torsion;
  const drawn = section_source === "drawn";
  return {
    ...(drawn ? {} : { section: s.section }),
    material: s.material,
    ...rest, torque: 0, section_source,
    ...(drawn ? { nodes: s.shear.nodes, walls: s.shear.walls, eta3 } : {}),
    ...(rest.mode === "free" ? { Q2, Q3, e2, e3 } : {}),
  };
}

/** The pole-plan tab has its own model (no section or material). */
export function polesInputs(s: StructuralState): Record<string, unknown> {
  return { ...toolInputs(s.poles) };
}

/** The shear-flow tab has its own drawn thin-walled section. */
export function shearInputs(s: StructuralState): Record<string, unknown> {
  return { ...s.shear };
}

/** Page defaults from the tools' schema defaults. */
export function defaultState(
  sectionDefaults: Record<string, unknown>, beamDefaults: Record<string, unknown>, torsionDefaults: Record<string, unknown> = {},
  poles: PoleModel = DEFAULT_POLE_MODEL,
): StructuralState {
  const { section, material, ...beam } = beamDefaults;
  const { section: _s, material: _m, ...torsion } = torsionDefaults;
  return {
    section: { ...(section as SectionValues) },
    material: String(material ?? sectionDefaults.material ?? "Steel"),
    beam: beam as unknown as BeamValues,
    torsion: torsionFromSchema(torsion),
    poles,
    shear: defaultShear(),
  };
}

/** Merge a (possibly partial) decoded URL state onto the defaults. */
export function mergeState(defaults: StructuralState, partial: Record<string, unknown>): StructuralState {
  const p = partial as Partial<StructuralState>;
  return {
    section: { ...defaults.section, ...(p.section ?? {}) },
    material: typeof p.material === "string" ? p.material : defaults.material,
    beam: { ...defaults.beam, ...(p.beam ?? {}) },
    torsion: mergeTorsion(defaults.torsion, p.torsion),
    poles: normalizeModel(p.poles) ?? defaults.poles,
    shear: { ...defaults.shear, ...(p.shear ?? {}) },
  };
}

/** Only the parts that differ from the defaults (keeps shared URLs short). */
export function stateDiff(state: StructuralState, defaults: StructuralState): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  const diff = (a: Record<string, unknown>, b: Record<string, unknown>) => {
    const d: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(a)) if (JSON.stringify(v) !== JSON.stringify(b[k])) d[k] = v;
    return d;
  };
  const sec = diff(state.section, defaults.section);
  const beam = diff(state.beam as unknown as Record<string, unknown>, defaults.beam as unknown as Record<string, unknown>);
  if (Object.keys(sec).length) out.section = sec;
  if (state.material !== defaults.material) out.material = state.material;
  if (Object.keys(beam).length) out.beam = beam;
  const torsion = diff(state.torsion as unknown as Record<string, unknown>, defaults.torsion as unknown as Record<string, unknown>);
  // `loads` always travels with any torsion change: its absence marks an old { length, torque, position } link
  if (Object.keys(torsion).length) out.torsion = { ...torsion, loads: state.torsion.loads };
  if (JSON.stringify(state.poles) !== JSON.stringify(defaults.poles)) out.poles = state.poles;
  const shear = diff(state.shear as unknown as Record<string, unknown>, defaults.shear as unknown as Record<string, unknown>);
  if (Object.keys(shear).length) out.shear = shear;
  return out;
}

/** Inputs from an old `#/tool/<id>?i=` link turned into the page's state shape. */
export function fromToolInputs(toolId: string, values: Record<string, unknown>): Record<string, unknown> {
  if (toolId === SECTION_TOOL) {
    const { material, ...section } = values;
    return { ...(Object.keys(section).length ? { section } : {}), ...(material !== undefined ? { material } : {}) };
  }
  if (toolId === POLE_TOOL) return Object.keys(values).length ? { poles: values } : {};
  if (toolId === SHEAR_TOOL) return Object.keys(values).length ? { shear: values } : {};
  const { section, material, ...rest } = values;
  const key = toolId === TORSION_TOOL ? "torsion" : "beam";
  return {
    ...(section !== undefined ? { section } : {}),
    ...(material !== undefined ? { material } : {}),
    ...(Object.keys(rest).length ? { [key]: rest } : {}),
  };
}

/** Messages per point torque whose position lies outside the member. */
export function torqueLoadErrors(t: TorsionValues): Record<number, string> {
  const out: Record<number, string> = {};
  t.loads.forEach((l, i) => {
    if (!(l.x >= 0) || l.x > t.length) out[i] = "Position must be within the length";
  });
  return out;
}

/** Closed cells of a drawn section (walls − nodes + connected parts); 0 means an open section. */
export function drawnCellCount(g: ShearGeometry): number {
  return Math.max(0, g.walls.length - g.nodes.length + componentCount(g.nodes.length, g.walls));
}

/** Client-side checks before calling structural.torsion (Python repeats them): returns an error message or null. */
export function torsionError(t: TorsionValues, shear?: ShearGeometry): string | null {
  if (!(t.length > 0)) return "Length must be positive";
  if (!(t.position >= 0) || t.position > t.length) return "Position must be within the length";
  if (t.left_support === "free" && t.right_support === "free") return "At least one end must be supported (fixed or fork)";
  const bad = Object.keys(torqueLoadErrors(t))[0];
  if (bad !== undefined) return `Torque ${Number(bad) + 1}: position must be within the length`;
  if (t.section_source === "drawn" && shear) {
    const e = shearError(shear);
    if (e) return `Drawn section: ${e}`;
  }
  return null;
}

// ---------------- torsion result ----------------

export type TorsionResult = {
  twist: number; twist_deg: number; twist_saint_venant: number; max_shear_stress: number; alpha: number;
  saint_venant_share: number; mode: string; J_T: number; W_T: number; C_T: number; omega_max: number; mu: number;
  twist_rate_sv: number; theta_max: number; x_theta_max: number; M_sv_max: number; M_b_max: number; B_max: number;
  sigma_w_max: number; tau_sv_max: number; T_left: number; T_right: number; note: string; steps: ShearStep[];
};

/** Typed view of the structural.torsion result fields (null values, i.e. NaN from Python, become NaN). */
export function parseTorsionResult(fields: { name: string; value: unknown }[]): TorsionResult {
  const f = Object.fromEntries(fields.map((x) => [x.name, x.value]));
  const n = (k: string) => numOr(f[k]);
  const steps = (Array.isArray(f.steps) ? (f.steps as Record<string, unknown>[]) : []).map((s) => ({
    label: String(s.label ?? ""), value: numOr(s.value), unit: String(s.unit ?? ""),
  }));
  return {
    twist: n("twist"), twist_deg: n("twist_deg"), twist_saint_venant: n("twist_saint_venant"), max_shear_stress: n("max_shear_stress"),
    alpha: n("alpha"), saint_venant_share: n("saint_venant_share"), mode: String(f.mode ?? ""), J_T: n("J_T"), W_T: n("W_T"), C_T: n("C_T"),
    omega_max: n("omega_max"), mu: n("mu"), twist_rate_sv: n("twist_rate_sv"), theta_max: n("theta_max"), x_theta_max: n("x_theta_max"),
    M_sv_max: n("M_sv_max"), M_b_max: n("M_b_max"), B_max: n("B_max"), sigma_w_max: n("sigma_w_max"), tau_sv_max: n("tau_sv_max"),
    T_left: n("T_left"), T_right: n("T_right"), note: typeof f.note === "string" ? f.note : "", steps,
  };
}

/** Plain-words reading of α = L √(G J_T / (E C_T)); null when α is not finite (C_T = 0). */
export function alphaHint(alpha: number): string | null {
  if (!Number.isFinite(alpha)) return null;
  if (alpha < 1) return "α < 1: mostly warping torsion";
  if (alpha > 10) return "α > 10: almost pure Saint-Venant torsion";
  return "1 ≤ α ≤ 10: Saint-Venant and warping torsion both matter";
}

// ---------------- determinacy (mirrors structural.loads.static_determinacy) ----------------

const REACTIONS: Record<SupportKind, number> = { fixed: 2, pinned: 1, roller: 1, free: 0 };

export type Determinacy = {
  degree: number;
  status: "determinate" | "indeterminate" | "mechanism";
  title: string;
  detail: string;
  method: string;
};

function equilibriumHandles(l: SupportKind, r: SupportKind): boolean {
  const simple = (s: SupportKind) => s === "pinned" || s === "roller";
  return (simple(l) && simple(r)) || (l === "fixed" && r === "free") || (l === "free" && r === "fixed");
}

export function determinacy(left: SupportKind, right: SupportKind, theory: "EB" | "TB" = "EB"): Determinacy {
  const unknowns = REACTIONS[left] + REACTIONS[right];
  const degree = unknowns - 2;
  const counts = `${unknowns} reaction${unknowns === 1 ? "" : "s"}, 2 equations (ΣFy, ΣM)`;
  if (degree < 0) {
    return {
      degree, status: "mechanism", title: "Mechanism: the beam cannot carry load",
      detail: `${counts}. Add or stiffen a support.`, method: "None",
    };
  }
  if (degree === 0) {
    const eq = theory === "EB" && equilibriumHandles(left, right);
    return {
      degree, status: "determinate", title: "Statically determinate",
      detail: `${counts}: equilibrium alone gives the reactions.`,
      method: eq ? "Equilibrium + double integration" : `FEM (${theory === "TB" ? "Timoshenko" : "Euler-Bernoulli"})`,
    };
  }
  return {
    degree, status: "indeterminate", title: `Statically indeterminate to degree ${degree}`,
    detail: `${counts}: compatibility is needed, so the beam is solved by FEM.`,
    method: `FEM (${theory === "TB" ? "Timoshenko" : "Euler-Bernoulli"})`,
  };
}

/** Client-side checks on the loads (Python repeats them); returns messages per load index. */
export function loadErrors(beam: BeamValues): Record<number, string> {
  const out: Record<number, string> = {};
  beam.loads.forEach((l, i) => {
    if (!(l.x >= 0) || l.x > beam.length) out[i] = "Position must be within the span";
    else if (l.kind === "udl" && l.x_end !== null && (l.x_end > beam.length || l.x_end <= l.x)) out[i] = "UDL end must be after its start and within the span";
  });
  return out;
}

// ---------------- free-body diagram layout ----------------

export type Reactions = { Ay?: number | null; MA?: number | null; By?: number | null; MB?: number | null };

export type FbdArrow = { x: number; yTail: number; yHead: number; label: string; reaction?: boolean };
export type FbdUdl = { x1: number; x2: number; yTop: number; down: boolean; label: string; arrows: number[] };
export type FbdMoment = { x: number; ccw: boolean; label: string; reaction?: boolean };
export type FbdLayout = {
  width: number;
  height: number;
  beamY: number;
  x0: number;
  x1: number;
  supports: { side: "left" | "right"; kind: SupportKind; x: number }[];
  points: FbdArrow[];
  udls: FbdUdl[];
  moments: FbdMoment[];
  reactions: FbdArrow[];
  reactionMoments: FbdMoment[];
  ticks: { x: number; label: string }[];
};

export type FbdFormat = { force: (n: number) => string; udl: (n: number) => string; moment: (n: number) => string; length: (n: number) => string };

const FBD = { width: 720, height: 310, beamY: 170, x0: 64, x1: 656, maxArrow: 70, minArrow: 32, maxUdl: 40, minUdl: 20 };

/** Positions (SVG units) of everything drawn on the FBD. Loads are scaled within their own kind. */
export function fbdLayout(beam: BeamValues, fmt: FbdFormat, reactions?: Reactions | null): FbdLayout {
  const { width, height, beamY, x0, x1 } = FBD;
  const L = beam.length > 0 ? beam.length : 1;
  const sx = (x: number) => x0 + (Math.min(Math.max(x, 0), L) / L) * (x1 - x0);
  const scale = (v: number, max: number, lo: number, hi: number) => (max > 0 ? lo + (hi - lo) * (Math.abs(v) / max) : lo);

  const points = beam.loads.filter((l) => l.kind === "point" && Number.isFinite(l.value) && l.value !== 0);
  const udls = beam.loads.filter((l) => l.kind === "udl" && Number.isFinite(l.value) && l.value !== 0);
  const moments = beam.loads.filter((l) => l.kind === "moment" && Number.isFinite(l.value) && l.value !== 0);
  const pMax = Math.max(0, ...points.map((l) => Math.abs(l.value)));
  const wMax = Math.max(0, ...udls.map((l) => Math.abs(l.value)));

  const udlBlocks: FbdUdl[] = udls.map((l) => {
    const a = sx(l.x);
    const b = sx(l.x_end ?? L);
    const h = scale(l.value, wMax, FBD.minUdl, FBD.maxUdl);
    const n = Math.max(2, Math.round((b - a) / 28) + 1);
    const arrows = Array.from({ length: n }, (_, i) => a + ((b - a) * i) / (n - 1));
    return { x1: a, x2: b, yTop: beamY - 4 - h, down: l.value > 0, label: fmt.udl(Math.abs(l.value)), arrows };
  });

  const pointArrows: FbdArrow[] = points.map((l) => {
    const x = sx(l.x);
    const len = scale(l.value, pMax, FBD.minArrow, FBD.maxArrow);
    // a point load inside a UDL block sits on top of the block so both stay readable
    const base = Math.min(beamY - 4, ...udlBlocks.filter((u) => x >= u.x1 - 1 && x <= u.x2 + 1).map((u) => u.yTop - 2));
    const down = l.value > 0; // down-positive: tail above pointing down; upward load: tail above pointing up
    return { x, yTail: down ? base - len : base, yHead: down ? base : base - len, label: fmt.force(Math.abs(l.value)) };
  });

  const momentArcs: FbdMoment[] = moments.map((l) => ({ x: sx(l.x), ccw: l.value > 0, label: fmt.moment(Math.abs(l.value)) }));

  const supports = [
    { side: "left" as const, kind: beam.left_support, x: x0 },
    { side: "right" as const, kind: beam.right_support, x: x1 },
  ];

  const reactionArrows: FbdArrow[] = [];
  const reactionMoments: FbdMoment[] = [];
  if (reactions) {
    const forces = [
      { v: reactions.Ay, x: x0 },
      { v: reactions.By, x: x1 },
    ].filter((r): r is { v: number; x: number } => typeof r.v === "number" && Number.isFinite(r.v) && Math.abs(r.v) > 1e-9);
    const rMax = Math.max(0, ...forces.map((r) => Math.abs(r.v)));
    for (const r of forces) {
      const len = scale(r.v, rMax, FBD.minArrow, FBD.maxArrow - 10);
      const base = beamY + 42; // below the support symbols
      // reactions are positive upward
      reactionArrows.push(r.v > 0
        ? { x: r.x, yTail: base + len, yHead: base, label: fmt.force(Math.abs(r.v)), reaction: true }
        : { x: r.x, yTail: base, yHead: base + len, label: fmt.force(Math.abs(r.v)), reaction: true });
    }
    for (const [v, x] of [[reactions.MA, x0], [reactions.MB, x1]] as const) {
      if (typeof v === "number" && Number.isFinite(v) && Math.abs(v) > 1e-9) {
        reactionMoments.push({ x, ccw: v > 0, label: fmt.moment(Math.abs(v)), reaction: true });
      }
    }
  }

  const xs = new Set<number>([0, L]);
  for (const l of beam.loads) {
    if (Number.isFinite(l.x)) xs.add(Math.min(Math.max(l.x, 0), L));
    if (l.kind === "udl" && l.x_end !== null && Number.isFinite(l.x_end)) xs.add(Math.min(Math.max(l.x_end, 0), L));
  }
  const ticks = [...xs].sort((a, b) => a - b).map((x) => ({ x: sx(x), label: fmt.length(x) }));

  return {
    width, height, beamY, x0, x1, supports, points: pointArrows, udls: udlBlocks, moments: momentArcs,
    reactions: reactionArrows, reactionMoments, ticks,
  };
}

/** SVG path of a ~270° arc around (cx, cy) with its end point and tangent, for moment symbols. */
export function momentArc(cx: number, cy: number, r: number, ccw: boolean): { d: string; head: [number, number][] } {
  // screen y points down, so a counter-clockwise moment runs with decreasing screen angle
  const start = (ccw ? 225 : -45) * (Math.PI / 180);
  const sweep = (ccw ? -270 : 270) * (Math.PI / 180);
  const end = start + sweep;
  const p = (a: number): [number, number] => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  const [sx0, sy0] = p(start);
  const [ex, ey] = p(end);
  const d = `M ${sx0.toFixed(2)} ${sy0.toFixed(2)} A ${r} ${r} 0 1 ${ccw ? 0 : 1} ${ex.toFixed(2)} ${ey.toFixed(2)}`;
  // arrowhead along the tangent at the end point
  const dir = ccw ? -1 : 1;
  const tx = -Math.sin(end) * dir;
  const ty = Math.cos(end) * dir;
  const nx = -ty;
  const ny = tx;
  const s = 7;
  const head: [number, number][] = [
    [ex + tx * s, ey + ty * s],
    [ex - tx * 2 + nx * s * 0.6, ey - ty * 2 + ny * s * 0.6],
    [ex - tx * 2 - nx * s * 0.6, ey - ty * 2 - ny * s * 0.6],
  ];
  return { d, head };
}

// ---------------- section drawing ----------------

export type Point = [number, number];

/** Fit polygons (metres, y up) into a w×h box with a margin; returns a mapper to SVG coordinates (y down). */
export function fitSection(polys: Point[][], w: number, h: number, margin: number) {
  const all = polys.flat();
  const minX = Math.min(...all.map((p) => p[0]));
  const maxX = Math.max(...all.map((p) => p[0]));
  const minY = Math.min(...all.map((p) => p[1]));
  const maxY = Math.max(...all.map((p) => p[1]));
  const s = Math.min((w - 2 * margin) / (maxX - minX || 1), (h - 2 * margin) / (maxY - minY || 1));
  const ox = (w - s * (maxX - minX)) / 2;
  const oy = (h - s * (maxY - minY)) / 2;
  const map = (p: Point): Point => [ox + (p[0] - minX) * s, h - oy - (p[1] - minY) * s];
  return { map, bounds: { minX, maxX, minY, maxY }, scale: s };
}

export function polygonPath(points: Point[]): string {
  return points.map((p, i) => `${i ? "L" : "M"} ${p[0].toFixed(2)} ${p[1].toFixed(2)}`).join(" ") + " Z";
}

// ---------------- bending stress at a station ----------------

/** Fibre stresses at x, linearly interpolated between the solver's stations (clamped at the ends). */
export function stressAt(x: number, xs: number[], top: number[], bottom: number[]): { top: number; bottom: number } {
  const n = Math.min(xs.length, top.length, bottom.length);
  if (n === 0) return { top: NaN, bottom: NaN };
  if (n === 1 || x <= xs[0]) return { top: top[0], bottom: bottom[0] };
  if (x >= xs[n - 1]) return { top: top[n - 1], bottom: bottom[n - 1] };
  let i = 1;
  while (i < n - 1 && xs[i] < x) i++;
  const span = xs[i] - xs[i - 1];
  const f = span > 0 ? (x - xs[i - 1]) / span : 0;
  return { top: top[i - 1] + f * (top[i] - top[i - 1]), bottom: bottom[i - 1] + f * (bottom[i] - bottom[i - 1]) };
}

// ---------------- thin-walled shear flow: geometry, presets, validation ----------------

export const SHEAR_H = 0.002; // m, default wall thickness
export const SHEAR_G = 81e9; // Pa, default shear modulus

const mm = (v: number) => v / 1000;
const r9 = (v: number) => Number(v.toFixed(9));

/** Build a section from mid-line nodes (mm, x3 down) and wall links i→j. */
function geom(pts: [number, number][], links: [number, number][], h = SHEAR_H): ShearGeometry {
  return {
    nodes: pts.map(([x2, x3]) => ({ x2: r9(mm(x2)), x3: r9(mm(x3)) })),
    walls: links.map(([i, j]) => ({ i, j, h, G: SHEAR_G })),
  };
}

/** Ring of `segments` straight walls on a circle of radius r (mm); `gap` degrees of slit at the top (0 = closed). */
function ring(r: number, segments: number, gap: number): ShearGeometry {
  const closed = gap <= 0;
  const count = closed ? segments : segments + 1;
  const step = (360 - gap) / segments;
  const pts: [number, number][] = [];
  for (let k = 0; k < count; k++) {
    const a = ((-90 + gap / 2 + k * step) * Math.PI) / 180;
    pts.push([r + r * Math.cos(a), r + r * Math.sin(a)]);
  }
  const links: [number, number][] = Array.from({ length: segments }, (_, k) => [k, (k + 1) % count]);
  return geom(pts, links);
}

export const SHEAR_PRESETS: { id: string; label: string }[] = [
  { id: "channel", label: "Channel" },
  { id: "i_section", label: "I-section" },
  { id: "z_section", label: "Z-section" },
  { id: "equal_angle", label: "Equal angle" },
  { id: "closed_box", label: "Closed box" },
  { id: "slit_tube", label: "Slit circular tube" },
  { id: "closed_tube", label: "Closed circular tube" },
  { id: "two_cell_box", label: "Two-cell box" },
];

/** Preset mid-line sections (50 to 200 mm, h = 2 mm). Axes: x2 right, x3 down. */
export function shearPreset(id: string): ShearGeometry {
  switch (id) {
    case "i_section":
      return geom([[0, 0], [50, 0], [100, 0], [0, 200], [50, 200], [100, 200]], [[0, 1], [1, 2], [1, 4], [3, 4], [4, 5]]);
    case "z_section":
      return geom([[0, 0], [50, 0], [50, 100], [100, 100]], [[0, 1], [1, 2], [2, 3]]);
    case "equal_angle":
      return geom([[0, 0], [0, 80], [80, 80]], [[0, 1], [1, 2]]);
    case "closed_box":
      return geom([[0, 0], [100, 0], [100, 60], [0, 60]], [[0, 1], [1, 2], [2, 3], [3, 0]]);
    case "slit_tube":
      return ring(50, 24, 15);
    case "closed_tube":
      return ring(50, 24, 0);
    case "two_cell_box":
      return geom([[0, 0], [60, 0], [120, 0], [120, 60], [60, 60], [0, 60]], [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 0], [1, 4]]);
    default: // channel (matches the Python default)
      return geom([[50, 0], [0, 0], [0, 100], [50, 100]], [[0, 1], [1, 2], [2, 3]]);
  }
}

export function defaultShear(): ShearValues {
  return { ...shearPreset("channel"), Q2: 0, Q3: 1000, Mt: 0, load_at_shear_centre: true, a2: 0, a3: 0 };
}

/** Number of connected components of the wall graph (union-find). */
export function componentCount(nodeCount: number, walls: { i: number; j: number }[]): number {
  const parent = Array.from({ length: nodeCount }, (_, k) => k);
  const root = (a: number): number => {
    while (parent[a] !== a) {
      parent[a] = parent[parent[a]];
      a = parent[a];
    }
    return a;
  };
  for (const w of walls) {
    if (w.i >= 0 && w.i < nodeCount && w.j >= 0 && w.j < nodeCount) parent[root(w.i)] = root(w.j);
  }
  return new Set(Array.from({ length: nodeCount }, (_, k) => root(k))).size;
}

/** Client-side checks before calling structural.shear_flow (Python repeats them); message or null. */
export function shearError(g: ShearGeometry): string | null {
  const n = g.nodes.length;
  if (n < 2) return "Need at least 2 nodes.";
  if (g.walls.length < 1) return "Add at least one wall.";
  for (let k = 0; k < n; k++) {
    if (!Number.isFinite(g.nodes[k].x2) || !Number.isFinite(g.nodes[k].x3)) return `Node ${k}: coordinates must be numbers.`;
  }
  const seen = new Map<string, number>();
  for (let k = 0; k < g.walls.length; k++) {
    const { i, j, h, G } = g.walls[k];
    if (!Number.isInteger(i) || !Number.isInteger(j) || i < 0 || j < 0 || i >= n || j >= n) return `Wall ${k}: node index out of range (0 to ${n - 1}).`;
    if (i === j) return `Wall ${k}: runs from node ${i} to itself.`;
    const a = g.nodes[i];
    const b = g.nodes[j];
    if (Math.hypot(a.x2 - b.x2, a.x3 - b.x3) < 1e-9) return `Wall ${k}: nodes ${i} and ${j} coincide.`;
    const key = `${Math.min(i, j)}-${Math.max(i, j)}`;
    if (seen.has(key)) return `Wall ${k} duplicates wall ${seen.get(key)} (nodes ${i} and ${j}).`;
    seen.set(key, k);
    if (!(h > 0)) return `Wall ${k}: thickness h must be > 0.`;
    if (!(G > 0)) return `Wall ${k}: shear modulus G must be > 0.`;
  }
  if (componentCount(n, g.walls) > 1) return "Section is not connected: every node must be joined to the others by walls.";
  return null;
}

// ---------------- editing helpers (pure) ----------------

/** Round to the nearest multiple of `step` (float noise removed). */
export function snapTo(v: number, step: number): number {
  return step > 0 ? r9(Math.round(v / step) * step) : v;
}

export function snapPoint(p: Point, step: number): Point {
  return [snapTo(p[0], step), snapTo(p[1], step)];
}

/** Index of the node nearest to p within `tol` (same unit as p), or -1. */
export function nodeNear(nodes: ShearNode[], p: Point, tol: number): number {
  let best = -1;
  let bestD = tol;
  nodes.forEach((n, k) => {
    const d = Math.hypot(n.x2 - p[0], n.x3 - p[1]);
    if (d <= bestD) {
      best = k;
      bestD = d;
    }
  });
  return best;
}

/** Distance from point p to segment a-b. */
export function distToSegment(p: Point, a: Point, b: Point): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const l2 = dx * dx + dy * dy;
  const f = l2 > 0 ? Math.min(1, Math.max(0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2)) : 0;
  return Math.hypot(p[0] - (a[0] + f * dx), p[1] - (a[1] + f * dy));
}

/** Index of the wall nearest to p within `tol`, or -1. */
export function wallNear(g: ShearGeometry, p: Point, tol: number): number {
  let best = -1;
  let bestD = tol;
  g.walls.forEach((w, k) => {
    const a = g.nodes[w.i];
    const b = g.nodes[w.j];
    if (!a || !b) return;
    const d = distToSegment(p, [a.x2, a.x3], [b.x2, b.x3]);
    if (d <= bestD) {
      best = k;
      bestD = d;
    }
  });
  return best;
}

export function addNode(g: ShearGeometry, p: Point): { geometry: ShearGeometry; index: number } {
  return { geometry: { ...g, nodes: [...g.nodes, { x2: p[0], x3: p[1] }] }, index: g.nodes.length };
}

export const hasWall = (g: ShearGeometry, a: number, b: number) => g.walls.some((w) => (w.i === a && w.j === b) || (w.i === b && w.j === a));

/** Wall a→b; unchanged when it would run to itself or duplicate an existing wall. */
export function addWall(g: ShearGeometry, a: number, b: number, h: number, G = SHEAR_G): ShearGeometry {
  if (a === b || hasWall(g, a, b)) return g;
  return { ...g, walls: [...g.walls, { i: a, j: b, h, G }] };
}

/** Free node pair for the "add wall" row button: prefers the last two nodes. */
export function nextFreeWall(g: ShearGeometry): [number, number] | null {
  const n = g.nodes.length;
  if (n >= 2 && !hasWall(g, n - 2, n - 1)) return [n - 2, n - 1];
  for (let a = 0; a < n; a++) for (let b = a + 1; b < n; b++) if (!hasWall(g, a, b)) return [a, b];
  return null;
}

export function moveNode(g: ShearGeometry, k: number, p: Point): ShearGeometry {
  if (!g.nodes[k] || (g.nodes[k].x2 === p[0] && g.nodes[k].x3 === p[1])) return g;
  return { ...g, nodes: g.nodes.map((n, m) => (m === k ? { x2: p[0], x3: p[1] } : n)) };
}

/** Remove a node with its walls; later node indices shift down by one. */
export function deleteNode(g: ShearGeometry, k: number): ShearGeometry {
  const shift = (m: number) => (m > k ? m - 1 : m);
  return {
    ...g,
    nodes: g.nodes.filter((_, m) => m !== k),
    walls: g.walls.filter((w) => w.i !== k && w.j !== k).map((w) => ({ ...w, i: shift(w.i), j: shift(w.j) })),
  };
}

export function deleteWall(g: ShearGeometry, k: number): ShearGeometry {
  return { ...g, walls: g.walls.filter((_, m) => m !== k) };
}

// ---------------- shear-flow plot geometry ----------------

/** Fit of world points (metres, x3 down) into a w×h box: no flip, so SVG y is x3. */
export type View = { s: number; toPx: (p: Point) => Point; toWorld: (p: Point) => Point };

export function makeView(points: Point[], w: number, h: number, margin: number, minExtent = 0.02): View {
  const xs = points.map((p) => p[0]).filter(Number.isFinite);
  const ys = points.map((p) => p[1]).filter(Number.isFinite);
  const minX = xs.length ? Math.min(...xs) : 0;
  const maxX = xs.length ? Math.max(...xs) : 0;
  const minY = ys.length ? Math.min(...ys) : 0;
  const maxY = ys.length ? Math.max(...ys) : 0;
  const ex = Math.max(maxX - minX, minExtent);
  const ey = Math.max(maxY - minY, minExtent);
  const s = Math.min((w - 2 * margin) / ex, (h - 2 * margin) / ey);
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  return {
    s,
    toPx: ([x, y]) => [w / 2 + (x - cx) * s, h / 2 + (y - cy) * s],
    toWorld: ([u, v]) => [(u - w / 2) / s + cx, (v - h / 2) / s + cy],
  };
}

/** Line width (px) for a wall of thickness h: proportional to h, clamped so thin walls stay visible. */
export function wallStrokePx(h: number, scale: number): number {
  return Math.min(8, Math.max(1.5, h * scale * 0.5));
}

/** Unit normal to the left of a→b as seen on screen (x2 right, x3 down). */
export function leftNormal(a: Point, b: Point): Point {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const l = Math.hypot(dx, dy) || 1;
  return [dy / l, -dx / l];
}

/** Drawn wall thickness (px): the real thickness at plot scale, but never thinner than `min` so 2 mm walls stay visible. */
export function wallThicknessPx(h: number, scale: number, min = 6): number {
  return Math.max(min, h * scale);
}

/**
 * Unit normal of wall a→b that points away from the centroid S (sign of n·(mid − S)), so the |t| diagram is drawn outside.
 * A wall through S has no outside: use the normal with positive x2 (right), or +x3 (down) for a horizontal wall.
 */
export function outerNormal(a: Point, b: Point, S: Point, extent: number): Point {
  const n = leftNormal(a, b);
  const flip: Point = [0 - n[0], 0 - n[1]]; // `0 -` keeps -0 out
  const d = n[0] * ((a[0] + b[0]) / 2 - S[0]) + n[1] * ((a[1] + b[1]) / 2 - S[1]);
  if (Math.abs(d) >= 1e-6 * extent) return d > 0 ? n : flip;
  if (Math.abs(n[0]) > 1e-9) return n[0] > 0 ? n : flip;
  return n[1] > 0 ? n : flip;
}

/** Offset (m per unit of t) so that the largest |t| reaches `frac` of the section's larger extent. */
export function flowScale(tMax: number, extent: number, frac = 0.15): number {
  return tMax > 0 && extent > 0 ? (frac * extent) / tMax : 0;
}

export type FlowRegion = { positive: boolean; points: Point[] };

/**
 * Polygons between a wall's mid-line and the |t| curve (mid-line offset along `normal` by k·|t|, so always on the
 * side `normal` points to), split where t changes sign (a butterfly: two lobes on the same side).
 */
export function flowRegions(x2: number[], x3: number[], t: number[], k: number, normal: Point): FlowRegion[] {
  const n = Math.min(x2.length, x3.length, t.length);
  if (n < 2 || !k) return [];
  const [nx, ny] = normal;
  const eps = 1e-9 * Math.max(0, ...t.slice(0, n).map(Math.abs));
  const sign = (v: number) => (v > eps ? 1 : v < -eps ? -1 : 0);
  const base = (i: number): Point => [x2[i], x3[i]];
  const off = (i: number): Point => [x2[i] + nx * k * Math.abs(t[i]), x3[i] + ny * k * Math.abs(t[i])];
  type Run = { positive: boolean; curve: Point[]; line: Point[] };
  const out: FlowRegion[] = [];
  const st: { cur: Run | null } = { cur: null };
  const close = () => {
    if (st.cur && st.cur.curve.length >= 2) out.push({ positive: st.cur.positive, points: [...st.cur.curve, ...st.cur.line.reverse()] });
    st.cur = null;
  };
  for (let i = 0; i < n; i++) {
    const sg = sign(t[i]);
    const sp = i > 0 ? sign(t[i - 1]) : 0;
    if (sg * sp < 0 && st.cur) {
      const f = t[i - 1] / (t[i - 1] - t[i]);
      const c: Point = [x2[i - 1] + f * (x2[i] - x2[i - 1]), x3[i - 1] + f * (x3[i] - x3[i - 1])];
      st.cur.curve.push(c);
      st.cur.line.push(c);
      close();
      st.cur = { positive: sg > 0, curve: [c], line: [c] };
    }
    if (sg === 0) {
      if (st.cur) {
        st.cur.curve.push(base(i));
        st.cur.line.push(base(i));
        close();
      }
      continue;
    }
    if (!st.cur) {
      st.cur = { positive: sg > 0, curve: [], line: [] };
      if (sp === 0 && i > 0) {
        st.cur.curve.push(base(i - 1));
        st.cur.line.push(base(i - 1));
      }
    }
    st.cur.curve.push(off(i));
    st.cur.line.push(base(i));
  }
  close();
  return out;
}

/** Point on the |t| curve at sample i (offset along `normal`). */
export function flowPoint(x2: number[], x3: number[], t: number[], k: number, i: number, normal: Point): Point {
  return [x2[i] + normal[0] * k * Math.abs(t[i]), x3[i] + normal[1] * k * Math.abs(t[i])];
}

/** Point and linearly interpolated t at fraction f (0..1) of the wall's arc length. */
export function alongWall(x2: number[], x3: number[], t: number[], f: number): { p: Point; t: number } {
  const n = Math.min(x2.length, x3.length, t.length);
  const cum = [0];
  for (let i = 1; i < n; i++) cum.push(cum[i - 1] + Math.hypot(x2[i] - x2[i - 1], x3[i] - x3[i - 1]));
  const target = Math.min(1, Math.max(0, f)) * cum[n - 1];
  let i = 1;
  while (i < n - 1 && cum[i] < target) i++;
  const seg = cum[i] - cum[i - 1];
  const u = seg > 0 ? (target - cum[i - 1]) / seg : 0;
  return { p: [x2[i - 1] + u * (x2[i] - x2[i - 1]), x3[i - 1] + u * (x3[i] - x3[i - 1])], t: t[i - 1] + u * (t[i] - t[i - 1]) };
}

/**
 * Hatch lines of the |t| diagram: from the mid-line to the curve, perpendicular to the wall, evenly spaced along the wall
 * (about `spacing` apart, at least `minIntervals` + 1 lines). Zero-length lines (|t| ≈ 0) are skipped.
 */
export function hatchLines(x2: number[], x3: number[], t: number[], k: number, normal: Point, spacing: number, minIntervals = 5): [Point, Point][] {
  const n = Math.min(x2.length, x3.length, t.length);
  if (n < 2 || !k) return [];
  const len = Math.hypot(x2[n - 1] - x2[0], x3[n - 1] - x3[0]);
  if (!(len > 0)) return [];
  const count = Math.max(minIntervals, Math.round(len / Math.max(spacing, 1e-12)));
  const out: [Point, Point][] = [];
  for (let m = 0; m <= count; m++) {
    const { p, t: tv } = alongWall(x2, x3, t, m / count);
    const d = k * Math.abs(tv);
    if (d < 1e-3 * len) continue;
    out.push([p, [p[0] + normal[0] * d, p[1] + normal[1] * d]]);
  }
  return out;
}

export type FlowArrow = { at: Point; dir: Point };

/** Direction arrows on the mid-line at the given fractions of the wall; none where |t| < minFrac·vMax. */
export function wallArrows(x2: number[], x3: number[], t: number[], vMax: number, fracs = [0.25, 0.5, 0.75], minFrac = 0.02): FlowArrow[] {
  const n = Math.min(x2.length, x3.length, t.length);
  if (n < 2 || !(vMax > 0)) return [];
  const a: Point = [x2[0], x3[0]];
  const b: Point = [x2[n - 1], x3[n - 1]];
  const out: FlowArrow[] = [];
  for (const f of fracs) {
    const { p, t: tv } = alongWall(x2, x3, t, f);
    if (Math.abs(tv) >= minFrac * vMax) out.push({ at: p, dir: flowDirection(a, b, tv) });
  }
  return out;
}

/**
 * Direction (unit, x2 right / x3 down, pointing right or else down) of the neutral axis through S for shear forces Q2, Q3.
 * The accompanying bending is M2 = Q3, M3 = −Q2 (per unit length), and σ ∝ (M2 J33 + M3 J23) x3 − (M3 J22 + M2 J23) x2 = 0.
 * Null without a shear force.
 */
export function neutralAxis(J22: number, J33: number, J23: number, Q2: number, Q3: number): Point | null {
  const a = Q3 * J33 - Q2 * J23;
  const b = Q3 * J23 - Q2 * J22;
  const l = Math.hypot(a, b);
  if (!(l > 0) || !Number.isFinite(l)) return null;
  const flip = a < -1e-9 * l || (Math.abs(a) <= 1e-9 * l && b < 0) ? -1 : 1;
  return [(flip * a) / l || 0, (flip * b) / l || 0];
}

/** End points of the line through `c` along `dir`, clipped to the box [minX, minY, maxX, maxY] grown by `pad`. */
export function clipLine(c: Point, dir: Point, box: [number, number, number, number], pad: number): [Point, Point] {
  const lo = [box[0] - pad, box[1] - pad];
  const hi = [box[2] + pad, box[3] + pad];
  let tMin = -Infinity;
  let tMax = Infinity;
  for (let ax = 0; ax < 2; ax++) {
    if (Math.abs(dir[ax]) < 1e-12) continue;
    const t1 = (lo[ax] - c[ax]) / dir[ax];
    const t2 = (hi[ax] - c[ax]) / dir[ax];
    tMin = Math.max(tMin, Math.min(t1, t2));
    tMax = Math.min(tMax, Math.max(t1, t2));
  }
  if (!Number.isFinite(tMin) || !Number.isFinite(tMax) || tMin > tMax) return [c, c];
  return [[c[0] + dir[0] * tMin, c[1] + dir[1] * tMin], [c[0] + dir[0] * tMax, c[1] + dir[1] * tMax]];
}

/** Flow direction (unit, screen frame) = wall direction i→j times the sign of t. */
export function flowDirection(a: Point, b: Point, t: number): Point {
  const l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
  const sg = t < 0 ? -1 : 1;
  return [(sg * (b[0] - a[0])) / l || 0, (sg * (b[1] - a[1])) / l || 0]; // `|| 0` turns -0 into 0
}

export type FlowLabel = { wall: number; index: number; value: number; priority: number };

/** Label candidates: the extreme of each wall (priority 0) and its ends (1); values under minFrac·max are skipped. */
export function flowLabelCandidates(values: number[][], vMax: number, minFrac = 0.05): FlowLabel[] {
  const out: FlowLabel[] = [];
  values.forEach((v, wall) => {
    if (!v.length) return;
    const last = v.length - 1;
    let ex = 0;
    v.forEach((x, i) => {
      if (Math.abs(x) > Math.abs(v[ex])) ex = i;
    });
    const add = (index: number, priority: number) => {
      if (Math.abs(v[index]) >= minFrac * vMax && Math.abs(v[index]) > 0) out.push({ wall, index, value: v[index], priority });
    };
    if (ex > 0 && ex < last) add(ex, 0);
    add(0, 1);
    add(last, 1);
  });
  return out.sort((a, b) => a.priority - b.priority || Math.abs(b.value) - Math.abs(a.value));
}

/** Greedy de-clutter: keep items (already in priority order) at least `minDist` apart. */
export function declutter<T extends { x: number; y: number }>(items: T[], minDist: number): T[] {
  const kept: T[] = [];
  for (const it of items) if (kept.every((k) => Math.hypot(k.x - it.x, k.y - it.y) >= minDist)) kept.push(it);
  return kept;
}

/** Items at least `minDist` away from every point in `pts`. */
export function awayFrom<T extends { x: number; y: number }>(items: T[], pts: Point[], minDist: number): T[] {
  return items.filter((it) => pts.every((p) => Math.hypot(p[0] - it.x, p[1] - it.y) >= minDist));
}

/** Float noise (about 1e-20, -0) shown as 0. */
export function cleanNoise(v: number, scale: number): number {
  return Math.abs(v) < 1e-12 * scale ? 0 : v;
}

// ---------------- shear-flow result ----------------

export type ShearWallData = {
  wall: number; i: number; j: number; h: number; G: number; length: number;
  s: number[]; x2: number[]; x3: number[];
  t_cut: number[]; t0: number[]; t_torque: number[]; t_total: number[]; tau: number[];
};
export type ShearStep = { label: string; value: number; unit: string };
export type ShearResult = {
  A: number; x2S: number; x3S: number; J22: number; J33: number; J23: number; phi_deg: number;
  x2_SC: number; x3_SC: number; e2: number; e3: number; n_cells: number; torque_SC: number; J_T: number;
  t_max: number; t_max_wall: number; t_max_s: number; tau_max: number; tau_torsion_open: number; note: string;
  cut_walls: number[]; steps: ShearStep[]; walls: ShearWallData[];
};

export type FlowSeries = "t_cut" | "t0" | "t_torque" | "t_total";
export type FlowQuantity = "t" | "tau";

const numOr = (v: unknown): number => (typeof v === "number" ? v : NaN);
const numArr = (v: unknown): number[] => (Array.isArray(v) ? v.map(numOr) : []);

/** Typed view of the structural.shear_flow result fields; null when the walls are missing. */
export function parseShearResult(fields: { name: string; value: unknown }[]): ShearResult | null {
  const f = Object.fromEntries(fields.map((x) => [x.name, x.value]));
  if (!Array.isArray(f.walls) || !f.walls.length) return null;
  const walls = (f.walls as Record<string, unknown>[]).map((w) => ({
    wall: numOr(w.wall), i: numOr(w.i), j: numOr(w.j), h: numOr(w.h), G: numOr(w.G), length: numOr(w.length),
    s: numArr(w.s), x2: numArr(w.x2), x3: numArr(w.x3), t_cut: numArr(w.t_cut), t0: numArr(w.t0),
    t_torque: numArr(w.t_torque), t_total: numArr(w.t_total), tau: numArr(w.tau),
  }));
  const steps = (Array.isArray(f.steps) ? (f.steps as Record<string, unknown>[]) : []).map((s) => ({
    label: String(s.label ?? ""), value: numOr(s.value), unit: String(s.unit ?? ""),
  }));
  const n = (k: string) => numOr(f[k]);
  return {
    A: n("A"), x2S: n("x2S"), x3S: n("x3S"), J22: n("J22"), J33: n("J33"), J23: n("J23"), phi_deg: n("phi_deg"),
    x2_SC: n("x2_SC"), x3_SC: n("x3_SC"), e2: n("e2"), e3: n("e3"), n_cells: n("n_cells"), torque_SC: n("torque_SC"),
    J_T: n("J_T"), t_max: n("t_max"), t_max_wall: n("t_max_wall"), t_max_s: n("t_max_s"), tau_max: n("tau_max"),
    tau_torsion_open: n("tau_torsion_open"), note: typeof f.note === "string" ? f.note : "",
    cut_walls: numArr(f.cut_walls), steps, walls,
  };
}

/** Per-wall sample values of one flow series, as t (N/m) or τ = t/h (Pa); noise cleaned against the series maximum. */
export function seriesValues(walls: ShearWallData[], series: FlowSeries, quantity: FlowQuantity): number[][] {
  const raw = walls.map((w) => w[series].map((t) => (quantity === "tau" ? t / w.h : t)));
  const scale = Math.max(0, ...raw.flat().map((v) => (Number.isFinite(v) ? Math.abs(v) : 0)));
  return raw.map((a) => a.map((v) => cleanNoise(v, scale)));
}

export const maxAbs = (values: number[][]): number => Math.max(0, ...values.flat().filter(Number.isFinite).map(Math.abs));
