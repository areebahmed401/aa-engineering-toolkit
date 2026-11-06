// Shear flow through a thin-walled section: the flow t(s) (or τ = t/h) is drawn as a band next to each wall
// mid-line, offset along the wall's left normal, with flow arrows, value labels, S / SC markers and the load line.
import {
  declutter, flowDirection, flowLabelCandidates, flowPoint, flowRegions, flowScale, leftNormal, makeView, maxAbs, polygonPath,
  seriesValues, wallStrokePx, type FlowQuantity, type FlowSeries, type Point, type ShearResult,
} from "../lib/structural";

export type PlotLoad = { q2: number; q3: number; atSC: boolean; a2: number; a3: number };

type Props = {
  result: ShearResult;
  series?: FlowSeries;
  quantity: FlowQuantity;
  /** Display text for a value in N/m (t) or Pa (τ), number only. */
  fmt: (v: number) => string;
  /** Common max |value| so several panels share one offset scale. */
  shared?: number;
  load?: PlotLoad;
  title?: string;
  compact?: boolean;
  /** Mark the cut (s = 0) of the walls in result.cut_walls. */
  cuts?: boolean;
  testId?: string;
};

// positive flow (along i→j) blue, negative orange: brand tokens, not hex
const POS = "fill-structural/30 stroke-structural";
const NEG = "fill-thermo/30 stroke-thermo";

const HALO = { paintOrder: "stroke", stroke: "rgb(var(--surface))", strokeWidth: 3, strokeLinejoin: "round" } as const;

function Arrow({ at, dir, size = 6 }: { at: Point; dir: Point; size?: number }) {
  const [nx, ny] = [-dir[1], dir[0]];
  const tip: Point = [at[0] + dir[0] * size, at[1] + dir[1] * size];
  const b1: Point = [at[0] - dir[0] * size * 0.6 + nx * size * 0.55, at[1] - dir[1] * size * 0.6 + ny * size * 0.55];
  const b2: Point = [at[0] - dir[0] * size * 0.6 - nx * size * 0.55, at[1] - dir[1] * size * 0.6 - ny * size * 0.55];
  return <polygon points={`${tip} ${b1} ${b2}`} fill="currentColor" />;
}

export function ShearFlowPlot({ result, series = "t_total", quantity, fmt, shared, load, title, compact = false, cuts = false, testId = "shear-plot" }: Props) {
  const W = compact ? 220 : 640;
  const H = compact ? 190 : 420;
  const margin = compact ? 26 : 60;
  const walls = result.walls;
  const values = seriesValues(walls, series, quantity);
  const vMax = shared ?? maxAbs(values);

  const nodePts: Point[] = walls.flatMap((w) => [[w.x2[0], w.x3[0]] as Point, [w.x2[w.x2.length - 1], w.x3[w.x3.length - 1]] as Point]);
  const xs = nodePts.map((p) => p[0]);
  const ys = nodePts.map((p) => p[1]);
  const extent = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
  const k = flowScale(vMax, extent);

  const S: Point = [result.x2S, result.x3S];
  const SC: Point = [result.x2_SC, result.x3_SC];
  const loadPt: Point | null = load && !compact ? (load.atSC ? SC : [load.a2, load.a3]) : null;
  const qLen = load ? Math.hypot(load.q2, load.q3) : 0;
  const curves = walls.flatMap((w, wi) => w.x2.map((_, i) => flowPoint(w.x2, w.x3, values[wi], k, i)));
  const fitPts = [...nodePts, ...curves, ...(compact ? [] : [S, SC]), ...(loadPt ? [loadPt] : [])];
  const view = makeView(fitPts, W, H, margin);
  const px = (p: Point) => view.toPx(p);

  // flow bands
  const bands = walls.flatMap((w, wi) =>
    flowRegions(w.x2, w.x3, values[wi], k).map((r, ri) => (
      <path key={`${wi}-${ri}`} d={polygonPath(r.points.map(px))} className={r.positive ? POS : NEG} strokeWidth={1} data-sign={r.positive ? "+" : "-"} />
    )),
  );

  // direction arrows at the wall midpoints (actual flow direction = sign of t × wall direction)
  const arrows = walls.map((w, wi) => {
    const n = w.x2.length;
    const m = Math.floor((n - 1) / 2);
    const t = values[wi][m];
    if (!(Math.abs(t) >= 0.05 * vMax) || !(vMax > 0)) return null;
    const a: Point = [w.x2[0], w.x3[0]];
    const b: Point = [w.x2[n - 1], w.x3[n - 1]];
    const at = px(flowPoint(w.x2, w.x3, values[wi], k / 2, m));
    return <Arrow key={wi} at={at} dir={flowDirection(a, b, t)} size={compact ? 4.5 : 6.5} />;
  });

  // value labels at the ends and at the extreme of each wall, de-cluttered
  const cands = flowLabelCandidates(values, vMax).map((c) => {
    const w = walls[c.wall];
    const n = w.x2.length;
    const nrm = leftNormal([w.x2[0], w.x3[0]], [w.x2[n - 1], w.x3[n - 1]]);
    const [x, y] = px(flowPoint(w.x2, w.x3, values[c.wall], k, c.index));
    const out = c.value >= 0 ? 1 : -1;
    return { ...c, x: x + nrm[0] * out * 11, y: y + nrm[1] * out * 11 };
  });
  const labels = declutter(cands, compact ? 36 : 34);

  const dots = new Map<string, Point>();
  for (const p of nodePts) dots.set(`${p[0].toFixed(6)},${p[1].toFixed(6)}`, px(p));

  const cutMarks = cuts
    ? result.cut_walls.map((cw) => {
        const w = walls[cw];
        if (!w) return null;
        const a = px([w.x2[0], w.x3[0]]);
        const b = px([w.x2[w.x2.length - 1], w.x3[w.x3.length - 1]]);
        const l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
        const e: Point = [(b[0] - a[0]) / l, (b[1] - a[1]) / l];
        const n: Point = [-e[1], e[0]];
        const u: Point = [e[0] * 0.5 + n[0] * 0.866, e[1] * 0.5 + n[1] * 0.866];
        return (
          <g key={cw} stroke="currentColor" strokeWidth={1.6} data-testid="shear-cut">
            {[8, 13].map((o) => {
              const c: Point = [a[0] + e[0] * o, a[1] + e[1] * o];
              return <line key={o} x1={c[0] - u[0] * 7} y1={c[1] - u[1] * 7} x2={c[0] + u[0] * 7} y2={c[1] + u[1] * 7} />;
            })}
          </g>
        );
      })
    : null;

  // load line: through the shear centre or through (a2, a3)
  let loadMark = null;
  if (loadPt && load && qLen > 0) {
    const L = px(loadPt);
    const d: Point = [load.q2 / qLen, load.q3 / qLen];
    const tail: Point = [L[0] - d[0] * 54, L[1] - d[1] * 54];
    loadMark = (
      <g className="text-primary-ink" data-testid="shear-load">
        <line x1={L[0] - d[0] * 260} y1={L[1] - d[1] * 260} x2={L[0] + d[0] * 260} y2={L[1] + d[1] * 260} stroke="currentColor" strokeWidth={1} strokeDasharray="5 4" opacity={0.7} />
        <line x1={tail[0]} y1={tail[1]} x2={L[0] - d[0] * 4} y2={L[1] - d[1] * 4} stroke="currentColor" strokeWidth={2.2} />
        <Arrow at={[L[0] - d[0] * 5, L[1] - d[1] * 5]} dir={d} size={9} />
        <text x={tail[0] - d[0] * 6 - d[1] * 9} y={tail[1] - d[1] * 6 + d[0] * 9} fontSize={12} fontWeight={700} className="fill-current" textAnchor="middle" dominantBaseline="middle">Q</text>
        {!load.atSC && <circle cx={L[0]} cy={L[1]} r={3} fill="currentColor" />}
      </g>
    );
  }

  const s = compact ? null : px(S);
  const c = compact ? null : px(SC);
  const same = s && c && Math.hypot(s[0] - c[0], s[1] - c[1]) < 3;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mx-auto h-auto w-full text-ink" style={{ maxWidth: W }} role="img"
      aria-label={title ?? "Shear flow through the section"} data-testid={testId}>
      {bands}
      {walls.map((w, wi) => {
        const a = px([w.x2[0], w.x3[0]]);
        const b = px([w.x2[w.x2.length - 1], w.x3[w.x3.length - 1]]);
        return <line key={wi} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="currentColor" strokeOpacity={0.85} strokeWidth={wallStrokePx(w.h, view.s)} strokeLinecap="round" />;
      })}
      {[...dots.values()].map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r={2.2} fill="rgb(var(--surface))" stroke="currentColor" strokeWidth={1} />)}
      {cutMarks}
      {arrows}
      {labels.map((l) => (
        <text key={`${l.wall}-${l.index}`} x={l.x} y={l.y} fontSize={compact ? 10 : 11} textAnchor="middle" dominantBaseline="middle"
          className="fill-current font-mono" style={HALO}>
          {fmt(l.value)}
        </text>
      ))}
      {loadMark}
      {s && (
        <g className="text-ink" data-testid="shear-centroid">
          <circle cx={s[0]} cy={s[1]} r={6} fill="none" stroke="currentColor" strokeWidth={1.6} />
          <line x1={s[0] - 10} y1={s[1]} x2={s[0] + 10} y2={s[1]} stroke="currentColor" strokeWidth={1.2} />
          <line x1={s[0]} y1={s[1] - 10} x2={s[0]} y2={s[1] + 10} stroke="currentColor" strokeWidth={1.2} />
          <text x={s[0] - 9} y={s[1] + 18} fontSize={12} fontWeight={700} textAnchor="end" className="fill-current" style={HALO}>S</text>
        </g>
      )}
      {c && (
        <g className="text-thermo" data-testid="shear-sc">
          <polygon points={`${c[0]},${c[1] - 7} ${c[0] + 7},${c[1]} ${c[0]},${c[1] + 7} ${c[0] - 7},${c[1]}`}
            fill={same ? "none" : "currentColor"} stroke="currentColor" strokeWidth={1.5} />
          <text x={c[0] + 10} y={c[1] - 9} fontSize={12} fontWeight={700} className="fill-current" style={HALO}>SC</text>
        </g>
      )}
    </svg>
  );
}
