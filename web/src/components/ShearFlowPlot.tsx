// Shear flow through a thin-walled section, textbook style: |t(s)| (or |τ| = |t/h|) is hatched on the outer side of each
// wall, walls are drawn as outlines at their real thickness with flow-direction arrows inside, plus the neutral axis,
// value labels, S / SC markers and the load line.
import {
  awayFrom, clipLine, declutter, flowLabelCandidates, flowPoint, flowRegions, flowScale, hatchLines, makeView, maxAbs, neutralAxis,
  outerNormal, polygonPath, seriesValues, wallArrows, wallThicknessPx, type FlowQuantity, type FlowSeries, type Point, type ShearResult,
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

// one theme colour for the |t| diagram (the red "fail" token), no sign colours
const DIAGRAM = "fill-fail stroke-fail";

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
  // |t| always on the outer side (away from S), so one normal per wall
  const normals = walls.map((w) => {
    const n = w.x2.length;
    return outerNormal([w.x2[0], w.x3[0]], [w.x2[n - 1], w.x3[n - 1]], S, extent);
  });

  const curves = walls.flatMap((w, wi) => w.x2.map((_, i) => flowPoint(w.x2, w.x3, values[wi], k, i, normals[wi])));
  const fitPts = [...nodePts, ...curves, ...(compact ? [] : [S, SC]), ...(loadPt ? [loadPt] : [])];
  const view = makeView(fitPts, W, H, margin);
  const px = (p: Point) => view.toPx(p);

  // hatched |t| diagrams: thin outline (mid-line, curve, back) plus hatch lines perpendicular to the wall
  const diagrams = walls.map((w, wi) => {
    const len = Math.hypot(w.x2[w.x2.length - 1] - w.x2[0], w.x3[w.x3.length - 1] - w.x3[0]);
    const hatch = hatchLines(w.x2, w.x3, values[wi], k, normals[wi], Math.max(0.04 * len, 0.02 * extent));
    const regions = flowRegions(w.x2, w.x3, values[wi], k, normals[wi]);
    if (!hatch.length && !regions.length) return null;
    return (
      <g key={wi} data-testid={`shear-hatch-${wi}`} className={DIAGRAM}>
        {regions.map((r, ri) => (
          <path key={ri} d={polygonPath(r.points.map(px))} fillOpacity={0.06} strokeWidth={1} data-sign={r.positive ? "+" : "-"} />
        ))}
        <path d={hatch.map(([a, b]) => `M${px(a)}L${px(b)}`).join("")} fill="none" strokeWidth={0.9} strokeOpacity={0.75} />
      </g>
    );
  });

  // walls: outline at real thickness (min on screen). An outline-coloured copy grown by 1 px sits under the surface-coloured
  // copy, so touching walls merge into one outline. Free ends keep their cap; joined ends are extended by half the thickness.
  const degree = new Map<number, number>();
  for (const w of walls) for (const nd of [w.i, w.j]) degree.set(nd, (degree.get(nd) ?? 0) + 1);
  const wallPolys = walls.map((w) => {
    const n = w.x2.length;
    const a = px([w.x2[0], w.x3[0]]);
    const b = px([w.x2[n - 1], w.x3[n - 1]]);
    const l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    const e: Point = [(b[0] - a[0]) / l, (b[1] - a[1]) / l];
    const half = wallThicknessPx(w.h, view.s, compact ? 5 : 6) / 2;
    const ea = (degree.get(w.i) ?? 1) > 1 ? half : 0;
    const eb = (degree.get(w.j) ?? 1) > 1 ? half : 0;
    const p0: Point = [a[0] - e[0] * ea, a[1] - e[1] * ea];
    const p1: Point = [b[0] + e[0] * eb, b[1] + e[1] * eb];
    const nrm: Point = [-e[1] * half, e[0] * half];
    const points = `${p0[0] + nrm[0]},${p0[1] + nrm[1]} ${p1[0] + nrm[0]},${p1[1] + nrm[1]} ${p1[0] - nrm[0]},${p1[1] - nrm[1]} ${p0[0] - nrm[0]},${p0[1] - nrm[1]}`;
    return { points, half };
  });

  // direction arrows on the walls (actual flow direction = sign of t × wall direction)
  const arrows = walls.flatMap((w, wi) =>
    wallArrows(w.x2, w.x3, values[wi], vMax).map((ar, ai) => (
      <g key={`${wi}-${ai}`} data-testid="shear-arrow" data-wall={wi}>
        <Arrow at={px(ar.at)} dir={ar.dir} size={Math.min(6.5, wallPolys[wi].half * 1.4)} />
      </g>
    )),
  );

  // value labels at the ends and at the extreme of each wall, on the outer side of the curve, de-cluttered
  const cands = flowLabelCandidates(values, vMax).map((c) => {
    const w = walls[c.wall];
    const nrm = normals[c.wall];
    const [x, y] = px(flowPoint(w.x2, w.x3, values[c.wall], k, c.index, nrm));
    return { ...c, x: x + nrm[0] * 11, y: y + nrm[1] * 11 };
  });
  const sPx = compact ? null : px(S);
  const scPx = compact ? null : px(SC);
  const labels = declutter(awayFrom(cands, [sPx, scPx].filter((p): p is Point => !!p), 16), compact ? 36 : 34);

  // neutral axis through S (not in the compact step panels, and not without a shear force)
  const naDir = !compact && load ? neutralAxis(result.J22, result.J33, result.J23, load.q2, load.q3) : null;
  let naMark = null;
  if (naDir) {
    const [p0, p1] = clipLine(S, naDir, [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)], 0.08 * extent);
    const a = px(p0);
    const b = px(p1);
    naMark = (
      <g className="text-ink" data-testid="shear-na">
        <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="currentColor" strokeWidth={1.2} strokeDasharray="7 4 1.5 4" />
        <text x={b[0] + naDir[0] * 11} y={b[1] + naDir[1] * 11} fontSize={12} fontWeight={700} textAnchor="middle" dominantBaseline="middle"
          className="fill-current" style={HALO}>NA</text>
      </g>
    );
  }

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

  const s = sPx;
  const c = scPx;
  const same = s && c && Math.hypot(s[0] - c[0], s[1] - c[1]) < 3;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mx-auto h-auto w-full text-ink" style={{ maxWidth: W }} role="img"
      aria-label={title ?? "Shear flow through the section"} data-testid={testId}>
      {diagrams}
      {wallPolys.map((wp, wi) => <polygon key={`o${wi}`} points={wp.points} fill="currentColor" stroke="currentColor" strokeWidth={2} strokeLinejoin="miter" />)}
      {wallPolys.map((wp, wi) => <polygon key={`f${wi}`} points={wp.points} fill="rgb(var(--surface))" data-testid={`shear-wall-${wi}`} />)}
      {naMark}
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
