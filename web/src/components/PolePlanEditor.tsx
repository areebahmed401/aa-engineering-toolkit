// SVG editor for planar systems (bars, joints, supports) with the pole plan drawn over it.
// The drawing lives in the page's state (PoleModel); the numbers shown come from the Python tool structural.pole_plan.
import { Eraser, Hand, Maximize, MousePointer2, Redo2, Trash2, Undo2, ZoomIn, ZoomOut } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode, type SVGProps } from "react";
import {
  addMember, clipLine, clusterOffsets, contradictionPoint, directionArrow, displacedSegments, displacementFactor, emptyHistory, EMPTY_MODEL,
  fitView, GRID_STEPS, hasAngle, hitTest, memberAxis, modelBounds, moveNode, nodeAt, nodeById, panBy, pickNode, placeInfinityPoles, POLE_PRESETS,
  record, redo, removeMember, removeNode, removeSupport, rotateSupport, round6, bestLabelSpot, setSupport, setSupportAngle, snap, supportSide, toModel, toScreen,
  toggleJoint, toolInputs, undo, zoomAt, type Hit, type History, type JointKind, type PoleModel, type PoleResult, type PoleSupportKind, type Pt, type View,
} from "../lib/polplan";
import { cn } from "./ui";

type Tool = "select" | "pan" | "bar" | "hinge" | "sleeve" | "shear" | "fixed" | "pin" | "roller" | "clamp" | "delete";

const TOOLS: { id: Tool; label: string; key: string; hint: string }[] = [
  { id: "select", label: "Select", key: "V", hint: "Select and move nodes" },
  { id: "pan", label: "Pan", key: "G", hint: "Drag to pan (or middle mouse button)" },
  { id: "bar", label: "Bar", key: "B", hint: "Click a node or grid point, then the next one; Esc stops the chain" },
  { id: "hinge", label: "Hinge", key: "H", hint: "Click a node or bar to toggle a hinge" },
  { id: "sleeve", label: "Sleeve", key: "S", hint: "Click a node between two collinear bars: slides along the axis" },
  { id: "shear", label: "Shear release", key: "Q", hint: "Click a node between two collinear bars: slides across the axis" },
  { id: "fixed", label: "Fixed", key: "F", hint: "Fixed support (3 reactions)" },
  { id: "pin", label: "Pin", key: "P", hint: "Pin support (2 reactions)" },
  { id: "roller", label: "Roller", key: "R", hint: "Roller (1 reaction, free direction by angle)" },
  { id: "clamp", label: "Clamp", key: "C", hint: "Sliding clamp (2 reactions, free direction by angle)" },
  { id: "delete", label: "Delete", key: "Del", hint: "Click a node, bar or support to delete it" },
];
const KEY_TOOL: Record<string, Tool> = Object.fromEntries(TOOLS.filter((t) => t.key.length === 1).map((t) => [t.key.toLowerCase(), t.id]));
const SUPPORT_TOOLS = new Set<Tool>(["fixed", "pin", "roller", "clamp"]);
const JOINT_OF: Partial<Record<Tool, JointKind>> = { hinge: "hinge", sleeve: "sleeve", shear: "shear" };

const TOL_PX = 10; // click tolerance
const SYMBOL_PX = 26; // support symbol length (hit area)

// ---------------- tool icons (same drawing language as the canvas) ----------------

function ToolIcon({ tool }: { tool: Tool }) {
  const p = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" } as const;
  const hatch = (y: number) => <path d={`M4 ${y + 4} l3 -4 M9 ${y + 4} l3 -4 M14 ${y + 4} l3 -4 M19 ${y + 4} l3 -4`} {...p} strokeWidth={1.2} />;
  switch (tool) {
    case "select": return <MousePointer2 className="h-4 w-4" />;
    case "pan": return <Hand className="h-4 w-4" />;
    case "delete": return <Trash2 className="h-4 w-4" />;
    default: break;
  }
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden>
      {tool === "bar" && <><path d="M4 18 L20 6" {...p} strokeWidth={3} /></>}
      {tool === "hinge" && <><path d="M2 12h6.5M15.5 12H22" {...p} strokeWidth={3} /><circle cx="12" cy="12" r="3.5" {...p} /></>}
      {tool === "sleeve" && <><path d="M2 12h20" {...p} strokeWidth={3} /><path d="M7 7.5h10M7 16.5h10" {...p} /></>}
      {tool === "shear" && <><path d="M2 12h20" {...p} strokeWidth={3} /><path d="M10.5 6v12M13.5 6v12" {...p} /></>}
      {tool === "pin" && <><path d="M12 5l-5 8h10z" {...p} /><path d="M4 13h16" {...p} />{hatch(13)}</>}
      {tool === "roller" && <><path d="M12 4l-5 7h10z" {...p} /><path d="M4 15h16" {...p} />{hatch(15)}</>}
      {tool === "fixed" && <><path d="M12 12h10" {...p} strokeWidth={3} /><path d="M9 4v16" {...p} /><path d="M9 8l-4 3M9 12l-4 3M9 16l-4 3" {...p} strokeWidth={1.2} /></>}
      {tool === "clamp" && <><path d="M3 5h18" {...p} /><circle cx="8" cy="9" r="3" {...p} /><circle cx="16" cy="9" r="3" {...p} /><path d="M3 13h18" {...p} />{hatch(13)}</>}
    </svg>
  );
}

// ---------------- canvas symbols ----------------

const INK = "stroke-ink";
const sw = { strokeLinecap: "round", strokeLinejoin: "round" } as const;
const halo = { stroke: "rgb(var(--surface))", strokeWidth: 3, paintOrder: "stroke", strokeLinejoin: "round" } as const;

function Hatch({ y, from, to }: { y: number; from: number; to: number }) {
  const xs: number[] = [];
  for (let x = from; x <= to + 0.1; x += 6) xs.push(x);
  return <path d={xs.map((x) => `M${x} ${y} l-5 6`).join(" ")} className="stroke-muted" strokeWidth={1.2} {...sw} />;
}

/** Support symbol in a local frame: the node at the origin, +y towards the ground (rotated by the caller). */
function SupportSymbol({ kind }: { kind: PoleSupportKind }) {
  const w = 1.8;
  switch (kind) {
    case "pin":
      return <g><path d="M0 0 L-9 15 L9 15 Z" className={cn(INK, "fill-surface")} strokeWidth={w} {...sw} /><path d="M-15 15 H15" className={INK} strokeWidth={w} {...sw} /><Hatch y={15} from={-13} to={15} /></g>;
    case "roller":
      return <g><path d="M0 0 L-8 12 L8 12 Z" className={cn(INK, "fill-surface")} strokeWidth={w} {...sw} /><path d="M-15 17 H15" className={INK} strokeWidth={w} {...sw} /><Hatch y={17} from={-13} to={15} /></g>;
    case "fixed":
      return <g><path d="M-15 1.5 H15" className={INK} strokeWidth={2.4} {...sw} /><Hatch y={1.5} from={-13} to={15} /></g>;
    case "clamp":
      return (
        <g>
          <path d="M-16 0 H16" className={INK} strokeWidth={w} {...sw} />
          <circle cx={-8} cy={7} r={7} className={cn(INK, "fill-surface")} strokeWidth={w} />
          <circle cx={8} cy={7} r={7} className={cn(INK, "fill-surface")} strokeWidth={w} />
          <path d="M-18 14 H18" className={INK} strokeWidth={w} {...sw} />
          <Hatch y={14} from={-16} to={18} />
        </g>
      );
  }
}

function Bolt() {
  return <path d="M3 -12 L-6 2 L-1 2 L-4 12 L7 -3 L1 -3 L5 -12 Z" className="fill-fail stroke-surface" strokeWidth={1} strokeLinejoin="round" />;
}

function Halo({ children, className, ...rest }: { children: ReactNode; className?: string } & SVGProps<SVGTextElement>) {
  return <text className={cn("select-none", className)} style={halo} fontSize={11} {...rest}>{children}</text>;
}

// ---------------- the editor ----------------

type Props = {
  model: PoleModel;
  onModel: (m: PoleModel) => void;
  result: PoleResult | null;
  stale: boolean;
};

const sameModel = (a: PoleModel, b: PoleModel) => JSON.stringify(toolInputs(a)) === JSON.stringify(toolInputs(b));

export function PolePlanEditor({ model, onModel, result, stale }: Props) {
  const [tool, setTool] = useState<Tool>("select");
  const [sel, setSel] = useState<Hit>(null);
  const [barStart, setBarStart] = useState<{ id: string; created: boolean } | null>(null);
  const [hover, setHover] = useState<Pt | null>(null);
  const [step, setStep] = useState<number>(1);
  const [view, setView] = useState<View>({ cx: 5, cy: 1, scale: 40 });
  const [size, setSize] = useState<{ w: number; h: number }>({ w: 0, h: 0 });
  const [hist, setHist] = useState<History<PoleModel>>(emptyHistory());
  const [showPoles, setShowPoles] = useState(true);
  const [showGo, setShowGo] = useState(true);
  const [showDisp, setShowDisp] = useState(false);
  const [dispPct, setDispPct] = useState(8);
  const wrap = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  const modelRef = useRef(model);
  modelRef.current = model;
  const fitted = useRef(false);
  const refit = useRef(true); // frame the poles too once the first result of a loaded example arrives (until the user moves the view)
  const gesture = useRef<{ kind: "pan" | "node"; id?: string; last: Pt; moved: boolean } | null>(null);
  const spaceDown = useRef(false);
  const { w, h } = size;

  // canvas size
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: Math.round(el.clientWidth), h: Math.round(el.clientHeight) }));
    ro.observe(el);
    setSize({ w: Math.round(el.clientWidth), h: Math.round(el.clientHeight) });
    return () => ro.disconnect();
  }, []);

  /** Pole points that are close enough to the drawing to be worth framing. */
  const framed = useCallback((m: PoleModel): PoleModel => {
    const b = modelBounds(m);
    if (!b || !result || !showPoles) return m;
    const span = Math.max(b.maxX - b.minX, b.maxY - b.minY, 1) * 0.6;
    const extra = result.poles
      .filter((p) => p.x !== null && p.y !== null && p.x > b.minX - span && p.x < b.maxX + span && p.y > b.minY - span && p.y < b.maxY + span)
      .map((p, i) => ({ id: `p${i}`, x: p.x as number, y: p.y as number, joint: "rigid" as JointKind }));
    return { ...m, nodes: [...m.nodes, ...extra] };
  }, [result, showPoles]);

  const fit = useCallback((m: PoleModel = modelRef.current) => {
    if (w > 0 && h > 0) setView(fitView(framed(m), w, h));
  }, [w, h, framed]);

  // first fit once the canvas has a size
  useEffect(() => {
    if (!fitted.current && w > 0 && h > 0) { fitted.current = true; setView(fitView(modelRef.current, w, h)); }
  }, [w, h]);

  useEffect(() => {
    if (refit.current && result && !stale && w > 0 && h > 0) { refit.current = false; setView(fitView(framed(modelRef.current), w, h)); }
  }, [result, stale, w, h, framed]);

  // ----- edits -----

  const commit = useCallback((next: PoleModel) => {
    const cur = modelRef.current;
    if (next === cur) return;
    setHist((hh) => record(hh, cur));
    refit.current = false;
    modelRef.current = next;
    onModel(next);
  }, [onModel]);

  const doUndo = useCallback(() => {
    const u = undo(hist, modelRef.current);
    if (!u) return;
    setHist(u.history); modelRef.current = u.value; onModel(u.value); setSel(null); setBarStart(null);
  }, [hist, onModel]);

  const doRedo = useCallback(() => {
    const r = redo(hist, modelRef.current);
    if (!r) return;
    setHist(r.history); modelRef.current = r.value; onModel(r.value); setSel(null); setBarStart(null);
  }, [hist, onModel]);

  const barStartRef = useRef(barStart);
  barStartRef.current = barStart;

  /** Stop drawing a chain; a start node created by the first click that never got a bar is removed again. */
  const cancelChain = useCallback(() => {
    const bs = barStartRef.current;
    if (bs?.created) {
      const m = modelRef.current;
      if (!m.members.some((x) => x.a === bs.id || x.b === bs.id) && nodeById(m, bs.id)) commit(removeNode(m, bs.id));
    }
    barStartRef.current = null;
    setBarStart(null);
  }, [commit]);

  const deleteSelection = useCallback(() => {
    const m = modelRef.current;
    if (!sel) return;
    if (sel.kind === "node") commit(removeNode(m, sel.id));
    else if (sel.kind === "member") commit(removeMember(m, sel.id));
    else commit(removeSupport(m, sel.node));
    setSel(null);
  }, [sel, commit]);

  const chooseTool = (t: Tool) => { if (t !== "bar") cancelChain(); setTool(t); };

  const loadPreset = (id: string) => {
    const p = POLE_PRESETS.find((x) => x.id === id);
    if (!p) return;
    cancelChain(); setSel(null); setTool("select");
    commit(p.model);
    refit.current = true;
    if (w > 0 && h > 0) setView(fitView(p.model, w, h));
  };

  // ----- keyboard -----

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) return;
      if ((e.ctrlKey || e.metaKey) && !e.altKey) {
        const k = e.key.toLowerCase();
        if (k === "z" && !e.shiftKey) { e.preventDefault(); doUndo(); } else if (k === "y" || (k === "z" && e.shiftKey)) { e.preventDefault(); doRedo(); }
        return;
      }
      if (e.altKey) return;
      if (e.key === " ") { spaceDown.current = true; if (t === document.body) e.preventDefault(); return; }
      if (e.key === "Escape") { if (barStartRef.current) cancelChain(); else setSel(null); return; }
      if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); deleteSelection(); return; }
      const next = KEY_TOOL[e.key.toLowerCase()];
      if (next) chooseTool(next);
    };
    const onUp = (e: KeyboardEvent) => { if (e.key === " ") spaceDown.current = false; };
    window.addEventListener("keydown", onKey);
    window.addEventListener("keyup", onUp);
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("keyup", onUp); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doUndo, doRedo, deleteSelection, cancelChain]);

  // wheel zoom (needs a non-passive listener)
  useEffect(() => {
    const el = svg.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      refit.current = false;
      const r = el.getBoundingClientRect();
      setView((v) => zoomAt(v, r.width, r.height, [e.clientX - r.left, e.clientY - r.top], Math.exp(-e.deltaY * 0.0015)));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [w, h]);

  // ----- pointer -----

  const local = (e: { clientX: number; clientY: number }): Pt => {
    const r = svg.current!.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  };
  const tolM = TOL_PX / view.scale;

  const onPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    if (e.button === 2) return;
    const sp = local(e);
    (e.target as Element).setPointerCapture?.(e.pointerId);
    if (e.button === 1 || tool === "pan" || spaceDown.current) { gesture.current = { kind: "pan", last: sp, moved: false }; e.preventDefault(); return; }
    const raw = toModel(view, w, h, sp);
    const m = modelRef.current;
    const opts = { tol: tolM, step };
    const hit = hitTest(m, raw, tolM, SYMBOL_PX / view.scale);

    if (tool === "select") {
      if (hit?.kind === "node") { setSel(hit); gesture.current = { kind: "node", id: hit.id, last: sp, moved: false }; } else if (hit) setSel(hit);
      else { setSel(null); gesture.current = { kind: "pan", last: sp, moved: false }; }
      return;
    }
    if (tool === "delete") {
      if (hit?.kind === "node") commit(removeNode(m, hit.id));
      else if (hit?.kind === "support") commit(removeSupport(m, hit.node));
      else if (hit?.kind === "member") commit(removeMember(m, hit.id));
      setSel(null);
      return;
    }
    if (tool === "bar") {
      const created = !nodeAt(m, raw, tolM);
      const { model: m1, id } = pickNode(m, raw, opts);
      if (!barStart) { commit(m1); setBarStart({ id, created: created && m1 !== m }); return; }
      if (id === barStart.id) return;
      commit(addMember(m1, barStart.id, id));
      setBarStart({ id, created: false });
      return;
    }
    const joint = JOINT_OF[tool];
    if (joint) {
      if (!hit || hit.kind === "support") return; // joints go on nodes and bars only
      const { model: m1, id } = pickNode(m, raw, opts);
      commit(toggleJoint(m1, id, joint));
      setSel({ kind: "node", id });
      return;
    }
    if (SUPPORT_TOOLS.has(tool)) {
      const { model: m1, id } = pickNode(m, raw, opts);
      commit(setSupport(m1, id, tool as PoleSupportKind, 0));
      setSel({ kind: "support", node: id });
    }
  };

  const onPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const sp = local(e);
    const raw = toModel(view, w, h, sp);
    const g = gesture.current;
    if (g?.kind === "pan") {
      g.moved = true;
      refit.current = false;
      setView((v) => panBy(v, sp[0] - g.last[0], sp[1] - g.last[1]));
      g.last = sp;
      return;
    }
    if (g?.kind === "node" && g.id) {
      const target: Pt = [snap(raw[0], step), snap(raw[1], step)];
      const m = modelRef.current;
      const n = nodeById(m, g.id);
      if (n && (n.x !== target[0] || n.y !== target[1])) {
        if (!g.moved) { g.moved = true; setHist((hh) => record(hh, m)); }
        const next = moveNode(m, g.id, target[0], target[1]);
        modelRef.current = next;
        onModel(next);
      }
      return;
    }
    const near = nodeAt(modelRef.current, raw, tolM);
    setHover(near ? [near.x, near.y] : [snap(raw[0], step), snap(raw[1], step)]);
  };

  const endGesture = () => { gesture.current = null; };

  // ----- derived drawing data -----

  const S = useCallback((p: Pt): Pt => toScreen(view, w, h, p), [view, w, h]);
  const rect = useMemo(() => {
    const a = toModel(view, w, h, [0, h]);
    const b = toModel(view, w, h, [w, 0]);
    return { minX: a[0], minY: a[1], maxX: b[0], maxY: b[1] };
  }, [view, w, h]);

  const selSupport = sel?.kind === "support" ? model.supports.find((s) => s.node === sel.node) : undefined;
  const presetValue = POLE_PRESETS.find((p) => sameModel(p.model, model))?.id ?? "custom";
  const empty = model.nodes.length === 0;

  // grid lines and tick labels
  const grid = useMemo(() => {
    if (w <= 0) return { v: [] as number[], hz: [] as number[], tickStep: step };
    let g = step;
    while (g * view.scale < 8) g *= 2;
    const lines = (lo: number, hi: number) => {
      const out: number[] = [];
      for (let k = Math.ceil(lo / g); k * g <= hi && out.length < 400; k++) out.push(round6(k * g));
      return out;
    };
    let tickStep = g;
    while (tickStep * view.scale < 56) tickStep *= 2;
    return { v: lines(rect.minX, rect.maxX), hz: lines(rect.minY, rect.maxY), tickStep };
  }, [w, step, view.scale, rect]);

  const centre = useMemo<Pt>(() => {
    const b = modelBounds(model);
    return S(b ? [(b.minX + b.maxX) / 2, (b.minY + b.maxY) / 2] : [view.cx, view.cy]);
  }, [model, S, view.cx, view.cy]);

  const overlay = showPoles && result ? result : null;
  const finitePoles = overlay ? overlay.poles.filter((p) => p.x !== null && p.y !== null && !p.at_infinity) : [];
  const poleScreen = finitePoles.map((p) => S([p.x as number, p.y as number]));
  const poleOff = clusterOffsets(poleScreen);
  const infinite = overlay ? placeInfinityPoles(overlay.poles.filter((p) => p.at_infinity && p.direction).map((p) => ({ name: p.name, direction: p.direction as Pt })), centre, w, h) : null;
  const bolts = overlay ? overlay.contradictions.map((c) => ({ c, at: contradictionPoint(c, overlay) })).filter((x): x is { c: typeof x.c; at: Pt } => x.at !== null) : [];
  const boltScreen = bolts.map((b) => S(b.at));
  const boltOff = clusterOffsets(boltScreen.map((p) => [p[0] + 10, p[1] - 14] as Pt), 16, 22);
  const dispFactor = result ? displacementFactor(model, result, dispPct / 100) : 0;
  const dispSegments = showDisp && result && result.movable && dispFactor > 0 ? displacedSegments(model, result, dispFactor) : [];

  // label layout: spots with the most room around them
  const taken: Pt[] = [
    ...poleScreen.map((q, i) => [q[0] + poleOff[i][0], q[1] + poleOff[i][1]] as Pt),
    ...(overlay ? overlay.bodies.flatMap((b) => { const q = S(b.label); return [[q[0] - 9, q[1] - 15], [q[0] + 9, q[1] - 15]] as Pt[]; }) : []),
    ...model.nodes.map((n) => S([n.x, n.y])),
    ...boltScreen,
  ];
  // keep labels clear of the zoom buttons and the legend box
  for (let y = 8; y <= 112; y += 18) for (const x of [w - 40, w - 22]) taken.push([x, y]);
  if (infinite && infinite.legend.length) for (let y = 8; y <= 56; y += 16) for (let x = 8; x <= 150; x += 24) taken.push([x, y]);
  const place = (cands: Pt[], halfW: number): Pt => {
    const at = bestLabelSpot(cands, halfW, 7, taken, { w, h });
    taken.push(at, [at[0] - halfW, at[1]], [at[0] + halfW, at[1]]);
    return at;
  };
  const goLines: { key: string; label: string; a: Pt; b: Pt; at: Pt }[] = [];
  if (overlay && showGo) {
    overlay.loci.forEach((l, i) => {
      const seg = clipLine(l.point, l.direction, rect);
      if (!seg) return;
      const a = S(seg[0]); const b = S(seg[1]);
      const cands: Pt[] = [];
      for (let t = 0.06; t <= 0.941; t += 0.04) cands.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t - 9]);
      goLines.push({ key: `${l.label}${i}`, label: l.label, a, b, at: place(cands, l.label.length * 3.3 + 2) });
    });
  }
  const infMarks = (infinite?.marks ?? []).map((m) => {
    const len = Math.hypot(...m.dir);
    const u: Pt = [m.dir[0] / len, m.dir[1] / len];
    const n: Pt = [-u[1], u[0]];
    const cands: Pt[] = [[m.pos[0] - n[0] * 18, m.pos[1] - n[1] * 18], [m.pos[0] + n[0] * 18, m.pos[1] + n[1] * 18],
      [m.pos[0] - u[0] * 52, m.pos[1] - u[1] * 52], [m.pos[0] + u[0] * 52, m.pos[1] + u[1] * 52]];
    return { ...m, u, label: place(cands, `∞ ${m.name}`.length * 3.4 + 2) };
  });

  const cursor = tool === "pan" ? "cursor-grab" : tool === "select" ? "cursor-default" : "cursor-crosshair";

  return (
    <div className="space-y-3" data-testid="pole-editor">
      <div className="flex flex-wrap items-end gap-3">
        <label className="block min-w-[14rem] flex-1">
          <span className="label">Example</span>
          <select className="input py-1.5" value={presetValue} data-testid="pole-preset" onChange={(e) => loadPreset(e.target.value)}>
            {presetValue === "custom" && <option value="custom">Custom drawing</option>}
            {POLE_PRESETS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="label">Grid</span>
          <select className="input py-1.5" value={step} data-testid="pole-grid" onChange={(e) => setStep(Number(e.target.value))}>
            {GRID_STEPS.map((g) => <option key={g} value={g}>{g} m</option>)}
          </select>
        </label>
        <div className="flex gap-1.5">
          <button type="button" className="btn-ghost px-2.5 py-1.5" title="Undo (Ctrl+Z)" aria-label="Undo" data-testid="pole-undo" disabled={!hist.past.length} onClick={doUndo}><Undo2 className="h-4 w-4" /></button>
          <button type="button" className="btn-ghost px-2.5 py-1.5" title="Redo (Ctrl+Y)" aria-label="Redo" data-testid="pole-redo" disabled={!hist.future.length} onClick={doRedo}><Redo2 className="h-4 w-4" /></button>
          <button type="button" className="btn-ghost px-2.5 py-1.5" title="Clear the drawing" data-testid="pole-clear" disabled={empty}
            onClick={() => { cancelChain(); setSel(null); commit(EMPTY_MODEL); }}><Eraser className="h-4 w-4" /> Clear</button>
        </div>
      </div>

      <div className="flex flex-col gap-3 md:flex-row">
        {/* toolbar */}
        <div className="flex flex-wrap gap-1.5 md:w-[8.75rem] md:flex-none md:flex-col md:flex-nowrap md:gap-1" role="toolbar" aria-label="Drawing tools">
          {TOOLS.map((t) => (
            <button key={t.id} type="button" title={`${t.label} (${t.key}): ${t.hint}`} aria-label={t.label} aria-pressed={tool === t.id} data-testid={`tool-${t.id}`}
              className={cn("inline-flex items-center gap-1.5 rounded-lg border px-2 py-1.5 text-xs transition md:w-full",
                tool === t.id ? "border-primary bg-primary/10 text-primary-ink" : "border-border bg-surface text-muted hover:border-primary/50 hover:text-ink")}
              onClick={() => chooseTool(t.id)}>
              <ToolIcon tool={t.id} />
              <span>{t.label}</span>
              <kbd className="ml-auto hidden rounded border border-border px-1 font-mono text-[10px] leading-4 text-muted sm:inline">{t.key}</kbd>
            </button>
          ))}
        </div>
        <div className="min-w-0 flex-1 space-y-3">
        {selSupport && (
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-bg/60 px-3 py-2 text-xs" data-testid="support-controls">
            <span className="font-medium capitalize">{selSupport.kind} at {selSupport.node}</span>
            {hasAngle(selSupport.kind) ? (
              <>
                <span className="text-muted">free direction</span>
                {[0, 90].map((a) => (
                  <button key={a} type="button" className={cn("rounded-md border px-2 py-0.5", selSupport.angle === a ? "border-primary bg-primary/10 text-primary-ink" : "border-border hover:border-primary/50")}
                    data-testid={`support-angle-${a}`} onClick={() => commit(setSupportAngle(modelRef.current, selSupport.node, a))}>{a}°</button>
                ))}
                <input type="number" className="input w-20 py-0.5" aria-label="Free direction angle in degrees" value={selSupport.angle} step={5} data-testid="support-angle"
                  onChange={(e) => commit(setSupportAngle(modelRef.current, selSupport.node, Number(e.target.value)))} />
                <span className="text-muted">°</span>
                <button type="button" className="rounded-md border border-border px-2 py-0.5 hover:border-primary/50" data-testid="support-rotate"
                  onClick={() => commit(rotateSupport(modelRef.current, selSupport.node, 90))}>Rotate 90°</button>
              </>
            ) : <span className="text-muted">no direction to set</span>}
            <button type="button" className="ml-auto inline-flex items-center gap-1 text-fail hover:underline" onClick={deleteSelection}><Trash2 className="h-3.5 w-3.5" /> Remove</button>
          </div>
        )}

        {/* canvas */}
        <div ref={wrap} className="relative h-[min(68vh,540px)] min-h-[300px] w-full overflow-hidden rounded-xl border border-border bg-surface" data-testid="pole-canvas-wrap">
          {w > 0 && h > 0 && (
            <svg ref={svg} width={w} height={h} className={cn("block select-none text-ink", cursor)} data-testid="pole-canvas" data-view={`${view.cx},${view.cy},${view.scale}`}
              style={{ touchAction: tool === "pan" ? "none" : "pan-y" }}
              onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={endGesture} onPointerCancel={endGesture} onPointerLeave={() => setHover(null)}
              onContextMenu={(e) => e.preventDefault()}>
              {/* grid */}
              <g aria-hidden>
                {grid.v.map((x) => <line key={`v${x}`} x1={S([x, 0])[0]} x2={S([x, 0])[0]} y1={0} y2={h} className={x === 0 ? "stroke-muted/50" : "stroke-border"} strokeWidth={x === 0 ? 1.2 : 0.7} />)}
                {grid.hz.map((y) => <line key={`h${y}`} y1={S([0, y])[1]} y2={S([0, y])[1]} x1={0} x2={w} className={y === 0 ? "stroke-muted/50" : "stroke-border"} strokeWidth={y === 0 ? 1.2 : 0.7} />)}
                {grid.v.filter((x) => Math.abs(x / grid.tickStep - Math.round(x / grid.tickStep)) < 1e-6).map((x) => (
                  <text key={`tx${x}`} x={S([x, 0])[0] + 3} y={h - 5} fontSize={10} className="fill-muted">{x}</text>
                ))}
                {grid.hz.filter((y) => Math.abs(y / grid.tickStep - Math.round(y / grid.tickStep)) < 1e-6).map((y) => (
                  <text key={`ty${y}`} x={4} y={S([0, y])[1] - 3} fontSize={10} className="fill-muted">{y}</text>
                ))}
              </g>

              {/* displacement figure */}
              {dispSegments.length > 0 && (
                <g data-testid="displacement-figure" className={stale ? "opacity-40" : undefined}>
                  {dispSegments.map((s) => {
                    const a = S(s.a); const b = S(s.b);
                    return <line key={s.id} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} className="stroke-thermo" strokeWidth={3} strokeDasharray="8 5" strokeLinecap="round" />;
                  })}
                </g>
              )}

              {/* G.O. lines */}
              {goLines.map((l) => (
                <g key={l.key} data-testid="go-line" className={stale ? "opacity-40" : undefined}>
                  <line x1={l.a[0]} y1={l.a[1]} x2={l.b[0]} y2={l.b[1]} className="stroke-structural" strokeWidth={1.4} strokeDasharray="7 5" />
                  <Halo x={l.at[0]} y={l.at[1] + 4} textAnchor="middle" className="fill-structural">{l.label}</Halo>
                </g>
              ))}

              {/* members */}
              <g>
                {model.members.map((mem) => {
                  const a = nodeById(model, mem.a); const b = nodeById(model, mem.b);
                  if (!a || !b) return null;
                  const p = S([a.x, a.y]); const q = S([b.x, b.y]);
                  const picked = sel?.kind === "member" && sel.id === mem.id;
                  return (
                    <g key={mem.id}>
                      {picked && <line x1={p[0]} y1={p[1]} x2={q[0]} y2={q[1]} className="stroke-primary/40" strokeWidth={11} strokeLinecap="round" />}
                      <line x1={p[0]} y1={p[1]} x2={q[0]} y2={q[1]} className="stroke-ink" strokeWidth={4} strokeLinecap="round" data-testid={`member-${mem.id}`} />
                    </g>
                  );
                })}
              </g>

              {/* supports */}
              <g>
                {model.supports.map((s) => {
                  const n = nodeById(model, s.node);
                  if (!n) return null;
                  const p = S([n.x, n.y]);
                  const side = supportSide(model, s);
                  const rot = (Math.atan2(-side[0], -side[1]) * 180) / Math.PI; // local +y -> screen (side.x, -side.y)
                  const picked = sel?.kind === "support" && sel.node === s.node;
                  return (
                    <g key={s.node} transform={`translate(${p[0]} ${p[1]}) rotate(${rot})`} data-testid={`support-${s.node}-${s.kind}`}>
                      {picked && <rect x={-20} y={-4} width={40} height={30} rx={4} className="fill-primary/15 stroke-primary" strokeDasharray="3 3" />}
                      <SupportSymbol kind={s.kind} />
                    </g>
                  );
                })}
              </g>

              {/* joints and nodes */}
              <g>
                {model.nodes.map((n) => {
                  const p = S([n.x, n.y]);
                  const axis = memberAxis(model, n.id);
                  const ang = (Math.atan2(-axis[1], axis[0]) * 180) / Math.PI;
                  const picked = sel?.kind === "node" && sel.id === n.id;
                  return (
                    <g key={n.id} data-testid={`node-${n.id}`} data-joint={n.joint}>
                      {picked && <circle cx={p[0]} cy={p[1]} r={11} className="fill-primary/15 stroke-primary" strokeDasharray="3 3" />}
                      {n.joint === "rigid" && <circle cx={p[0]} cy={p[1]} r={3} className="fill-ink" />}
                      {n.joint === "hinge" && <circle cx={p[0]} cy={p[1]} r={5.5} className="fill-surface stroke-ink" strokeWidth={1.8} />}
                      {n.joint === "sleeve" && (
                        <g transform={`translate(${p[0]} ${p[1]}) rotate(${ang})`}>
                          <rect x={-11} y={-6} width={22} height={12} className="fill-surface/70" stroke="none" />
                          <path d="M-11 -6 H11 M-11 6 H11" className="stroke-ink" strokeWidth={2} strokeLinecap="round" />
                        </g>
                      )}
                      {n.joint === "shear" && (
                        <g transform={`translate(${p[0]} ${p[1]}) rotate(${ang})`}>
                          <rect x={-4} y={-8} width={8} height={16} className="fill-surface/70" stroke="none" />
                          <path d="M-3 -8 V8 M3 -8 V8" className="stroke-ink" strokeWidth={2} strokeLinecap="round" />
                        </g>
                      )}
                    </g>
                  );
                })}
              </g>

              {/* body numbers */}
              {overlay && (
                <g>
                  {overlay.bodies.map((b) => {
                    const p = S(b.label);
                    const x = p[0]; const y = p[1] - 15;
                    return (
                      <g key={b.id} data-testid={`body-${b.id}`} data-immovable={b.immovable} className={stale ? "opacity-40" : undefined}>
                        <title>{b.immovable ? `Body ${b.id}: immovable${b.reason ? ` (${b.reason})` : ""}` : `Body ${b.id}`}</title>
                        <rect x={x - 10} y={y - 9} width={20} height={18} rx={3} className={b.immovable ? "fill-bg stroke-muted" : "fill-surface stroke-ink"} strokeWidth={1.3} />
                        <text x={x} y={y + 4} textAnchor="middle" fontSize={11} fontWeight={600} className={cn("select-none", b.immovable ? "fill-muted" : "fill-ink")}>{b.id}</text>
                        {b.immovable && <path d={`M${x - 10} ${y + 9} L${x + 10} ${y - 9}`} className="stroke-muted" strokeWidth={1.3} />}
                      </g>
                    );
                  })}
                </g>
              )}

              {/* poles */}
              {overlay && (
                <g className={stale ? "opacity-40" : undefined}>
                  {finitePoles.map((p, i) => {
                    const o = poleOff[i];
                    const sp = poleScreen[i];
                    const x = sp[0] + o[0]; const y = sp[1] + o[1];
                    const dashed = p.source === "displacement";
                    const tip = dashed ? `${p.name}: from displacement analysis` : `${p.name}`;
                    return (
                      <g key={p.name} data-testid={`pole-${p.name}`} data-source={p.source}>
                        <title>{tip}</title>
                        {(o[0] !== 0 || o[1] !== 0) && <><line x1={sp[0]} y1={sp[1]} x2={x} y2={y} className="stroke-primary-ink" strokeWidth={1} /><circle cx={sp[0]} cy={sp[1]} r={2} className="fill-primary-ink" /></>}
                        {p.j === 0 ? (
                          <>
                            <circle cx={x} cy={y} r={9.5} className="fill-surface stroke-primary-ink" strokeWidth={1.8} strokeDasharray={dashed ? "3 2.5" : undefined} />
                            <text x={x} y={y + 4} textAnchor="middle" fontSize={11} fontWeight={700} className="select-none fill-ink">{p.i}</text>
                          </>
                        ) : (
                          <>
                            <circle cx={x} cy={y} r={3.5} className="fill-primary-ink" />
                            {dashed && <circle cx={x} cy={y} r={7} className="fill-none stroke-primary-ink" strokeWidth={1.4} strokeDasharray="3 2.5" />}
                            <Halo x={x + 8} y={y - 7} className="fill-ink" fontWeight={600}>{p.name}</Halo>
                          </>
                        )}
                      </g>
                    );
                  })}
                </g>
              )}

              {/* poles at infinity */}
              {infinite && (
                <g className={stale ? "opacity-40" : undefined}>
                  {infMarks.map((m) => {
                    const dx = m.u[0] * 22; const dy = m.u[1] * 22;
                    const head = (sgn: 1 | -1): string => {
                      const ex = m.pos[0] + sgn * dx; const ey = m.pos[1] + sgn * dy;
                      const ux = sgn * m.u[0]; const uy = sgn * m.u[1];
                      return `M${ex} ${ey} L${ex - ux * 8 - uy * 4} ${ey - uy * 8 + ux * 4} L${ex - ux * 8 + uy * 4} ${ey - uy * 8 - ux * 4} Z`;
                    };
                    return (
                      <g key={m.name} data-testid={`pole-inf-${m.name}`}>
                        <title>{`${m.name} at infinity`}</title>
                        <path d={`M${m.pos[0] - dx} ${m.pos[1] - dy} L${m.pos[0] + dx} ${m.pos[1] + dy}`} className="stroke-primary-ink" strokeWidth={1.8} />
                        <path d={head(1)} className="fill-primary-ink" />
                        <path d={head(-1)} className="fill-primary-ink" />
                        <Halo x={m.label[0]} y={m.label[1] + 4} textAnchor="middle" className="fill-ink" fontWeight={600}>∞ {m.name}</Halo>
                      </g>
                    );
                  })}
                </g>
              )}

              {/* contradictions */}
              {bolts.map((b, i) => {
                const p = boltScreen[i]; const o = boltOff[i];
                const x = p[0] + 10 + (o[0] ? o[0] : 0); const y = p[1] - 14 + (o[1] ? o[1] : 0);
                return (
                  <g key={`${b.c.pole}${i}`} transform={`translate(${x} ${y})`} data-testid="contradiction-mark" className={stale ? "opacity-40" : undefined}>
                    <title>{`Contradiction in pole ${b.c.pole}: ${b.c.text}`}</title>
                    <Bolt />
                  </g>
                );
              })}

              {/* bar preview and snap cursor */}
              {tool === "bar" && barStart && hover && nodeById(model, barStart.id) && (() => {
                const a = nodeById(model, barStart.id)!; const p = S([a.x, a.y]); const q = S(hover);
                return <line x1={p[0]} y1={p[1]} x2={q[0]} y2={q[1]} className="stroke-primary" strokeWidth={3} strokeDasharray="6 4" strokeLinecap="round" pointerEvents="none" />;
              })()}
              {hover && tool !== "select" && tool !== "pan" && tool !== "delete" && (
                <circle cx={S(hover)[0]} cy={S(hover)[1]} r={5} className="fill-none stroke-primary" strokeWidth={1.8} pointerEvents="none" />
              )}
              {barStart && nodeById(model, barStart.id) && <circle cx={S([nodeById(model, barStart.id)!.x, nodeById(model, barStart.id)!.y])[0]} cy={S([nodeById(model, barStart.id)!.x, nodeById(model, barStart.id)!.y])[1]} r={8} className="fill-primary/20 stroke-primary" pointerEvents="none" />}
            </svg>
          )}

          {/* canvas controls */}
          <div className="absolute right-2 top-2 flex flex-col gap-1">
            <button type="button" className="rounded-lg border border-border bg-surface/90 p-1.5 text-muted hover:text-ink" title="Zoom in" aria-label="Zoom in" data-testid="zoom-in"
              onClick={() => setView((v) => zoomAt(v, w, h, [w / 2, h / 2], 1.25))}><ZoomIn className="h-4 w-4" /></button>
            <button type="button" className="rounded-lg border border-border bg-surface/90 p-1.5 text-muted hover:text-ink" title="Zoom out" aria-label="Zoom out" data-testid="zoom-out"
              onClick={() => setView((v) => zoomAt(v, w, h, [w / 2, h / 2], 0.8))}><ZoomOut className="h-4 w-4" /></button>
            <button type="button" className="rounded-lg border border-border bg-surface/90 p-1.5 text-muted hover:text-ink" title="Fit to view" aria-label="Fit to view" data-testid="zoom-fit"
              onClick={() => fit()}><Maximize className="h-4 w-4" /></button>
          </div>
          {infinite && infinite.legend.length > 0 && (
            <div className="absolute left-2 top-2 max-w-[60%] rounded-lg border border-border bg-surface/90 px-2.5 py-1.5 text-xs" data-testid="inf-legend">
              <div className="font-semibold">Poles at infinity</div>
              <div className="text-muted">{infinite.legend.map((l) => `${l.name} ${directionArrow(l.dir)}`).join("   ")}</div>
            </div>
          )}
          <div className="pointer-events-none absolute bottom-6 right-2 rounded-md bg-surface/80 px-2 py-0.5 font-mono text-[11px] text-muted" data-testid="pole-readout">
            {hover ? `x ${round6(hover[0])} m · y ${round6(hover[1])} m` : "x · y in m"}
          </div>
          {empty && <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-muted">Pick the Bar tool (B) and click two points to draw a first bar, or load an example.</div>}
          {barStart && <div className="pointer-events-none absolute bottom-2 left-2 rounded-md bg-surface/80 px-2 py-0.5 text-[11px] text-muted">Click the next point · Esc stops the chain</div>}
        </div>

        {/* overlay toggles */}
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
          {([["poles", "Pole plan", showPoles, setShowPoles], ["go", "G.O. lines", showGo, setShowGo], ["disp", "Displacement figure", showDisp, setShowDisp]] as const).map(([id, label, on, set]) => (
            <label key={id} className="inline-flex cursor-pointer items-center gap-2">
              <input type="checkbox" className="h-4 w-4 accent-primary" checked={on} data-testid={`toggle-${id}`} onChange={(e) => set(e.target.checked)} /> {label}
            </label>
          ))}
          {showDisp && (
            <label className="inline-flex items-center gap-2 text-xs text-muted">
              Scale
              <input type="range" min={1} max={30} step={1} value={dispPct} className="w-32 accent-primary" data-testid="disp-scale" aria-label="Displacement scale"
                onChange={(e) => setDispPct(Number(e.target.value))} />
              <span className="w-24 font-mono text-ink">max shift {dispPct} %</span>
            </label>
          )}
          {showDisp && result && !result.movable && <span className="text-xs text-muted">The system is immovable: there is no displacement figure.</span>}
        </div>
        </div>
      </div>
    </div>
  );
}
