// Pure logic for the structural page: state shape, determinacy, shape fields and the FBD layout.
// The calculations themselves stay in Python (structural.section_properties / structural.beam_analysis).
import type { JsonSchema, ToolSchema } from "./types";

export const SECTION_TOOL = "structural.section_properties";
export const BEAM_TOOL = "structural.beam_analysis";

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
/** Everything the page edits: the section and material are shared by both tabs. */
export type StructuralState = { section: SectionValues; material: string; beam: BeamValues };

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

/** Page defaults from the two tools' schema defaults. */
export function defaultState(sectionDefaults: Record<string, unknown>, beamDefaults: Record<string, unknown>): StructuralState {
  const { section, material, ...beam } = beamDefaults;
  return {
    section: { ...(section as SectionValues) },
    material: String(material ?? sectionDefaults.material ?? "Steel"),
    beam: beam as unknown as BeamValues,
  };
}

/** Merge a (possibly partial) decoded URL state onto the defaults. */
export function mergeState(defaults: StructuralState, partial: Record<string, unknown>): StructuralState {
  const p = partial as Partial<StructuralState>;
  return {
    section: { ...defaults.section, ...(p.section ?? {}) },
    material: typeof p.material === "string" ? p.material : defaults.material,
    beam: { ...defaults.beam, ...(p.beam ?? {}) },
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
  return out;
}

/** Inputs from an old `#/tool/<id>?i=` link turned into the page's state shape. */
export function fromToolInputs(toolId: string, values: Record<string, unknown>): Record<string, unknown> {
  if (toolId === SECTION_TOOL) {
    const { material, ...section } = values;
    return { ...(Object.keys(section).length ? { section } : {}), ...(material !== undefined ? { material } : {}) };
  }
  const { section, material, ...beam } = values;
  return {
    ...(section !== undefined ? { section } : {}),
    ...(material !== undefined ? { material } : {}),
    ...(Object.keys(beam).length ? { beam } : {}),
  };
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
