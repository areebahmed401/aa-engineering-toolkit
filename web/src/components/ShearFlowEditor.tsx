// Editor for the thin-walled section of the shear-flow tab: an SVG canvas (grid, snapping, select / add wall /
// delete / place load) and editable node and wall tables that change the same geometry.
import { Crosshair, Eraser, MousePointer2, PencilLine, Plus, Trash2, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  addNode, addWall, deleteNode, deleteWall, makeView, moveNode, nextFreeWall, nodeNear, SHEAR_G, SHEAR_H,
  SHEAR_PRESETS, shearPreset, snapPoint, wallNear, wallStrokePx, type Point, type ShearGeometry, type View,
} from "../lib/structural";
import { formatNumber } from "../lib/units";
import { cn } from "./ui";
import type { Conversion } from "./NumberInput";

export type EditorLoad = { show: boolean; a2: number; a3: number };

type Props = {
  value: ShearGeometry;
  onChange: (g: ShearGeometry) => void;
  load: EditorLoad;
  onPlaceLoad: (a2: number, a3: number) => void;
  /** Centroid of the last result, for the x2 / x3 axes. */
  centroid: Point | null;
  lengthConv: Conversion;
  modulusConv: Conversion;
  snapChoices: number[]; // m
  error: string | null;
};

type Mode = "select" | "wall" | "delete" | "load";

const MODES: { id: Mode; label: string; icon: typeof Plus; hint: string }[] = [
  { id: "select", label: "Select / move", icon: MousePointer2, hint: "Drag a node to move it; it snaps to the grid." },
  { id: "wall", label: "Add wall", icon: PencilLine, hint: "Click a node or grid point to start, click again to finish a wall and keep chaining. Esc ends the chain." },
  { id: "delete", label: "Delete", icon: Eraser, hint: "Click a node (its walls go with it) or a wall to remove it." },
  { id: "load", label: "Place load", icon: Crosshair, hint: "Click to set the point (a2, a3) the load line passes through." },
];

const W = 640;
const H = 420;
const NODE_HIT = 12; // px
const WALL_HIT = 8;

/** Number box for table cells: edits an SI value in display units, keeps the text while focused. */
function Cell({ value, conv, onChange, label, testId, integer }: {
  value: number; conv: Conversion; onChange: (v: number) => void; label: string; testId?: string; integer?: boolean;
}) {
  const show = (v: number) => (Number.isFinite(v) ? String(Number.parseFloat(conv.fromSI(v).toPrecision(8))) : "");
  const [text, setText] = useState(show(value));
  const [focused, setFocused] = useState(false);
  const [bad, setBad] = useState(false);
  useEffect(() => {
    if (!focused) {
      setText(show(value));
      setBad(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, conv.unit, focused]);
  return (
    <input aria-label={label} data-testid={testId} inputMode={integer ? "numeric" : "decimal"}
      className={cn("input w-full min-w-[4.5rem] px-2 py-1 font-mono text-xs", bad && "border-fail")}
      value={text} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
      onChange={(e) => {
        const t = e.target.value;
        setText(t);
        const n = Number(t.replace(",", "."));
        if (t.trim() === "" || Number.isNaN(n) || (integer && !Number.isInteger(n))) {
          setBad(true);
          return;
        }
        setBad(false);
        onChange(conv.toSI(n));
      }} />
  );
}

const IDENTITY: Conversion = { unit: "", toSI: (v) => v, fromSI: (v) => v };

export function ShearFlowEditor({ value, onChange, load, onPlaceLoad, centroid, lengthConv, modulusConv, snapChoices, error }: Props) {
  const [mode, setMode] = useState<Mode>("select");
  const [chain, setChain] = useState<number | null>(null);
  const [hover, setHover] = useState<Point | null>(null);
  const [drag, setDrag] = useState<number | null>(null);
  const [snapState, setSnapState] = useState(snapChoices[2] ?? snapChoices[0]);
  const [lastH, setLastH] = useState(value.walls.length ? value.walls[value.walls.length - 1].h : SHEAR_H);
  const svgRef = useRef<SVGSVGElement>(null);
  const frozen = useRef<View | null>(null);
  const snap = snapChoices.includes(snapState) ? snapState : (snapChoices[2] ?? snapChoices[0]);
  const lenFmt = (m: number) => `${formatNumber(lengthConv.fromSI(m), 4)} ${lengthConv.unit}`;

  // view: all geometry plus room around it to click into
  const pts: Point[] = [...value.nodes.map((n): Point => [n.x2, n.x3])];
  if (load.show) pts.push([load.a2, load.a3]);
  if (centroid) pts.push(centroid);
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  const ext = Math.max(0.1, xs.length ? Math.max(...xs) - Math.min(...xs) : 0, ys.length ? Math.max(...ys) - Math.min(...ys) : 0);
  const pad = 0.18 * ext;
  const fitPts: Point[] = xs.length
    ? [[Math.min(...xs) - pad, Math.min(...ys) - pad], [Math.max(...xs) + pad, Math.max(...ys) + pad]]
    : [[-0.05, -0.05], [0.15, 0.15]];
  const live = makeView(fitPts, W, H, 24, 0.1);
  const view = drag !== null && frozen.current ? frozen.current : live;
  const px = (p: Point) => view.toPx(p);

  useEffect(() => {
    if (chain === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setChain(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [chain]);

  const pickMode = (m: Mode) => {
    setMode(m);
    setChain(null);
  };

  const canvasPoint = (e: { clientX: number; clientY: number }): Point => {
    const r = svgRef.current!.getBoundingClientRect();
    return [((e.clientX - r.left) * W) / r.width, ((e.clientY - r.top) * H) / r.height];
  };

  const onDown = (e: React.PointerEvent<SVGSVGElement>) => {
    const p = canvasPoint(e);
    const world = view.toWorld(p);
    const nodeTol = NODE_HIT / view.s;
    const snapped = snapPoint(world, snap);
    if (mode === "select") {
      const k = nodeNear(value.nodes, world, nodeTol);
      if (k >= 0) {
        frozen.current = view;
        svgRef.current?.setPointerCapture(e.pointerId);
        setDrag(k);
      }
    } else if (mode === "wall") {
      let g = value;
      let idx = nodeNear(g.nodes, world, nodeTol);
      if (idx < 0) {
        idx = nodeNear(g.nodes, snapped, 1e-6);
        if (idx < 0) {
          const r = addNode(g, snapped);
          g = r.geometry;
          idx = r.index;
        }
      }
      if (chain !== null && chain !== idx) g = addWall(g, chain, idx, lastH);
      if (g !== value) onChange(g);
      setChain(idx);
    } else if (mode === "delete") {
      const k = nodeNear(value.nodes, world, nodeTol);
      if (k >= 0) onChange(deleteNode(value, k));
      else {
        const w = wallNear(value, world, WALL_HIT / view.s);
        if (w >= 0) onChange(deleteWall(value, w));
      }
    } else {
      onPlaceLoad(snapped[0], snapped[1]);
    }
  };

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const snapped = snapPoint(view.toWorld(canvasPoint(e)), snap);
    setHover(snapped);
    if (drag !== null) onChange(moveNode(value, drag, snapped));
  };

  const onUp = () => {
    setDrag(null);
    frozen.current = null;
  };

  // grid lines at multiples of the snap step, coarsened until they are at least 9 px apart
  const [wx0, wy0] = view.toWorld([0, 0]);
  const [wx1, wy1] = view.toWorld([W, H]);
  const mult = [1, 2, 5, 10, 20, 50, 100, 200, 500].find((m) => m * snap * view.s >= 9) ?? 1000;
  const g = snap * mult;
  const lines = { minor: "", major: "" };
  for (let kx = Math.ceil(wx0 / g); kx <= Math.floor(wx1 / g); kx++) {
    const x = px([kx * g, 0])[0];
    lines[kx % 5 === 0 ? "major" : "minor"] += `M${x.toFixed(1)} 0V${H}`;
  }
  for (let ky = Math.ceil(wy0 / g); ky <= Math.floor(wy1 / g); ky++) {
    const y = px([0, ky * g])[1];
    lines[ky % 5 === 0 ? "major" : "minor"] += `M0 ${y.toFixed(1)}H${W}`;
  }

  const hint = MODES.find((m) => m.id === mode)!.hint;
  const setNode = (k: number, p: Partial<{ x2: number; x3: number }>) =>
    onChange({ ...value, nodes: value.nodes.map((n, m) => (m === k ? { ...n, ...p } : n)) });
  const setWall = (k: number, p: Partial<{ i: number; j: number; h: number; G: number }>) =>
    onChange({ ...value, walls: value.walls.map((w, m) => (m === k ? { ...w, ...p } : w)) });
  const free = nextFreeWall(value);
  const origin = centroid ? px(centroid) : null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex flex-wrap gap-1" role="group" aria-label="Drawing mode">
          {MODES.map(({ id, label, icon: Icon }) => (
            <button key={id} type="button" aria-pressed={mode === id} data-testid={`shear-mode-${id}`}
              className={cn("inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition",
                mode === id ? "border-primary bg-primary text-on-primary" : "border-border text-muted hover:text-ink")}
              onClick={() => pickMode(id)}>
              <Icon className="h-3.5 w-3.5" /> {label}
            </button>
          ))}
        </div>
        <label className="block">
          <span className="label">Preset</span>
          <select className="input py-1 text-xs" value="" data-testid="shear-preset" aria-label="Preset section"
            onChange={(e) => {
              if (!e.target.value) return;
              setChain(null);
              setLastH(SHEAR_H);
              onChange(shearPreset(e.target.value));
            }}>
            <option value="">Load a preset…</option>
            {SHEAR_PRESETS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="label">Snap</span>
          <select className="input py-1 text-xs" value={snap} data-testid="shear-snap" aria-label="Grid snap step" onChange={(e) => setSnapState(Number(e.target.value))}>
            {snapChoices.map((s) => <option key={s} value={s}>{lenFmt(s)}</option>)}
          </select>
        </label>
      </div>
      <p className="text-xs text-muted" data-testid="shear-hint">{hint}</p>

      <div className="overflow-hidden rounded-xl border border-border bg-bg/60">
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full select-none text-ink" role="img"
          aria-label="Section editor canvas" data-testid="shear-canvas" style={{ touchAction: "none", cursor: mode === "select" ? (drag !== null ? "grabbing" : "default") : "crosshair" }}
          onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp} onPointerLeave={() => setHover(null)}>
          <path d={lines.minor} className="stroke-border" strokeWidth={0.6} fill="none" opacity={0.7} />
          <path d={lines.major} className="stroke-border" strokeWidth={1} fill="none" />

          {value.walls.map((w, k) => {
            const a = value.nodes[w.i];
            const b = value.nodes[w.j];
            if (!a || !b) return null;
            const pa = px([a.x2, a.x3]);
            const pb = px([b.x2, b.x3]);
            const mx = (pa[0] + pb[0]) / 2;
            const my = (pa[1] + pb[1]) / 2;
            const l = Math.hypot(pb[0] - pa[0], pb[1] - pa[1]) || 1;
            const d: Point = [(pb[0] - pa[0]) / l, (pb[1] - pa[1]) / l];
            return (
              <g key={k} data-testid={`shear-wall-${k}`}>
                <line x1={pa[0]} y1={pa[1]} x2={pb[0]} y2={pb[1]} stroke="currentColor" strokeOpacity={0.8} strokeWidth={wallStrokePx(w.h, view.s)} strokeLinecap="round" />
                <polygon className="text-muted" fill="currentColor"
                  points={`${mx + d[0] * 5},${my + d[1] * 5} ${mx - d[0] * 3 - d[1] * 4},${my - d[1] * 3 + d[0] * 4} ${mx - d[0] * 3 + d[1] * 4},${my - d[1] * 3 - d[0] * 4}`} />
                <text x={mx + d[1] * 12} y={my - d[0] * 12} fontSize={10} textAnchor="middle" dominantBaseline="middle" className="fill-current text-muted"
                  style={{ paintOrder: "stroke", stroke: "rgb(var(--surface))", strokeWidth: 3 }}>w{k}</text>
              </g>
            );
          })}

          {chain !== null && hover && value.nodes[chain] && mode === "wall" && (() => {
            const a = px([value.nodes[chain].x2, value.nodes[chain].x3]);
            const b = px(hover);
            return <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} className="stroke-primary" strokeWidth={2} strokeDasharray="5 4" />;
          })()}
          {hover && (mode === "wall" || mode === "load") && (
            <circle cx={px(hover)[0]} cy={px(hover)[1]} r={3.5} className="fill-primary/60" />
          )}

          {origin && (
            <g className="text-muted" stroke="currentColor" strokeWidth={1.4} data-testid="shear-axes">
              <line x1={origin[0]} y1={origin[1]} x2={origin[0] + 46} y2={origin[1]} />
              <polygon points={`${origin[0] + 52},${origin[1]} ${origin[0] + 43},${origin[1] - 3.5} ${origin[0] + 43},${origin[1] + 3.5}`} fill="currentColor" stroke="none" />
              <line x1={origin[0]} y1={origin[1]} x2={origin[0]} y2={origin[1] + 46} />
              <polygon points={`${origin[0]},${origin[1] + 52} ${origin[0] - 3.5},${origin[1] + 43} ${origin[0] + 3.5},${origin[1] + 43}`} fill="currentColor" stroke="none" />
              <text x={origin[0] + 56} y={origin[1] + 4} fontSize={11} stroke="none" className="fill-current">x₂</text>
              <text x={origin[0] + 6} y={origin[1] + 62} fontSize={11} stroke="none" className="fill-current">x₃ (down)</text>
            </g>
          )}

          {load.show && (
            <g className="text-primary-ink" data-testid="shear-load-point">
              <line x1={px([load.a2, load.a3])[0] - 7} y1={px([load.a2, load.a3])[1]} x2={px([load.a2, load.a3])[0] + 7} y2={px([load.a2, load.a3])[1]} stroke="currentColor" strokeWidth={2} />
              <line x1={px([load.a2, load.a3])[0]} y1={px([load.a2, load.a3])[1] - 7} x2={px([load.a2, load.a3])[0]} y2={px([load.a2, load.a3])[1] + 7} stroke="currentColor" strokeWidth={2} />
              <text x={px([load.a2, load.a3])[0] + 9} y={px([load.a2, load.a3])[1] - 8} fontSize={11} fontWeight={700} className="fill-current">Q</text>
            </g>
          )}

          {value.nodes.map((n, k) => {
            const p = px([n.x2, n.x3]);
            return (
              <g key={k} data-testid={`shear-node-${k}`}>
                <circle cx={p[0]} cy={p[1]} r={5.5} stroke="currentColor" strokeWidth={1.4}
                  className={chain === k ? "fill-primary" : drag === k ? "fill-primary/70" : "fill-surface"} />
                <text x={p[0] + 8} y={p[1] - 8} fontSize={11} fontWeight={600} className="fill-current"
                  style={{ paintOrder: "stroke", stroke: "rgb(var(--surface))", strokeWidth: 3 }}>{k}</text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <span>Walls run i → j (small arrow); positive shear flow t follows that direction. Axes: x₂ right, x₃ down.</span>
        <span className="font-mono" data-testid="shear-cursor">{hover ? `x₂ ${lenFmt(hover[0])} · x₃ ${lenFmt(hover[1])}` : " "}</span>
      </div>

      {error && (
        <div className="flex gap-2 rounded-xl border border-fail/30 bg-fail/5 p-3 text-sm text-fail" data-testid="shear-error">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs font-semibold text-muted">{value.nodes.length} node{value.nodes.length === 1 ? "" : "s"}</span>
            <button type="button" className="btn-ghost px-2 py-1 text-xs" data-testid="shear-add-node" aria-label="Add node"
              onClick={() => {
                const last = value.nodes[value.nodes.length - 1];
                onChange({ ...value, nodes: [...value.nodes, { x2: last ? last.x2 + 0.05 : 0, x3: last ? last.x3 : 0 }] });
              }}>
              <Plus className="h-3.5 w-3.5" /> Node
            </button>
          </div>
          <div className="max-h-72 overflow-auto rounded-lg border border-border">
            <table className="w-full text-xs" data-testid="shear-nodes-table">
              <thead className="sticky top-0 bg-surface text-left text-muted">
                <tr><th className="px-2 py-1 font-medium">#</th><th className="px-1 py-1 font-medium">x₂ [{lengthConv.unit}]</th><th className="px-1 py-1 font-medium">x₃ [{lengthConv.unit}]</th><th /></tr>
              </thead>
              <tbody>
                {value.nodes.map((n, k) => (
                  <tr key={k} className="border-t border-border">
                    <td className="px-2 py-1 font-mono text-muted">{k}</td>
                    <td className="px-1 py-1"><Cell value={n.x2} conv={lengthConv} label={`Node ${k} x2`} testId={`shear-node-${k}-x2`} onChange={(v) => setNode(k, { x2: v })} /></td>
                    <td className="px-1 py-1"><Cell value={n.x3} conv={lengthConv} label={`Node ${k} x3`} testId={`shear-node-${k}-x3`} onChange={(v) => setNode(k, { x3: v })} /></td>
                    <td className="px-1 py-1 text-right">
                      <button type="button" className="rounded p-1 text-muted hover:text-fail" aria-label={`Delete node ${k}`} onClick={() => { setChain(null); onChange(deleteNode(value, k)); }}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs font-semibold text-muted">{value.walls.length} wall{value.walls.length === 1 ? "" : "s"}</span>
            <button type="button" className="btn-ghost px-2 py-1 text-xs" data-testid="shear-add-wall" aria-label="Add wall" disabled={!free}
              onClick={() => free && onChange(addWall(value, free[0], free[1], lastH))}>
              <Plus className="h-3.5 w-3.5" /> Wall
            </button>
          </div>
          <div className="max-h-72 overflow-auto rounded-lg border border-border">
            <table className="w-full text-xs" data-testid="shear-walls-table">
              <thead className="sticky top-0 bg-surface text-left text-muted">
                <tr>
                  <th className="px-2 py-1 font-medium">#</th><th className="px-1 py-1 font-medium">i</th><th className="px-1 py-1 font-medium">j</th>
                  <th className="px-1 py-1 font-medium">h [{lengthConv.unit}]</th><th className="px-1 py-1 font-medium">G [{modulusConv.unit}]</th><th />
                </tr>
              </thead>
              <tbody>
                {value.walls.map((w, k) => (
                  <tr key={k} className="border-t border-border">
                    <td className="px-2 py-1 font-mono text-muted">{k}</td>
                    <td className="px-1 py-1"><Cell value={w.i} conv={IDENTITY} integer label={`Wall ${k} start node i`} testId={`shear-wall-${k}-i`} onChange={(v) => setWall(k, { i: v })} /></td>
                    <td className="px-1 py-1"><Cell value={w.j} conv={IDENTITY} integer label={`Wall ${k} end node j`} testId={`shear-wall-${k}-j`} onChange={(v) => setWall(k, { j: v })} /></td>
                    <td className="px-1 py-1"><Cell value={w.h} conv={lengthConv} label={`Wall ${k} thickness h`} testId={`shear-wall-${k}-h`} onChange={(v) => { setLastH(v); setWall(k, { h: v }); }} /></td>
                    <td className="px-1 py-1"><Cell value={w.G} conv={modulusConv} label={`Wall ${k} shear modulus G`} testId={`shear-wall-${k}-G`} onChange={(v) => setWall(k, { G: v })} /></td>
                    <td className="px-1 py-1 text-right">
                      <button type="button" className="rounded p-1 text-muted hover:text-fail" aria-label={`Delete wall ${k}`} onClick={() => onChange(deleteWall(value, k))}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-1 text-[11px] text-muted">New walls use the last thickness h and G = {formatNumber(SHEAR_G / 1e9)} GPa.</p>
        </div>
      </div>
    </div>
  );
}
