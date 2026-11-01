// Bending-stress view of a cross-section: the outline shaded by stress (red tension, blue compression,
// clear at the neutral axis) beside the linear stress block σ(y) from the bottom to the top fibre.
import { useId } from "react";
import { fitSection, polygonPath, type Point } from "../lib/structural";
import type { ChartSpec } from "../lib/types";

type Props = {
  chart: ChartSpec;
  cTop: number; // m, centroid to top fibre
  cBottom: number; // m, centroid to bottom fibre
  sigmaTop: number; // Pa, tension +
  sigmaBottom: number; // Pa
  stress: (pa: number) => string; // formatted with unit, from the magnitude
};

const W = 640;
const H = 340;
const SEC_W = 280; // width of the section area
const BASE = 450; // x of the stress baseline
const K = 80; // px for the largest stress

// brand tokens: --fail is the tension red, --structural is the steel-blue compression colour
const TENSION = "rgb(var(--fail))";
const COMPRESSION = "rgb(var(--structural))";
const colour = (pa: number) => (pa >= 0 ? TENSION : COMPRESSION);

export function StressSection({ chart, cTop, cBottom, sigmaTop, sigmaBottom, stress }: Props) {
  const gid = useId().replace(/:/g, "");
  const outer = chart.shapes.filter((s) => !s.hole).map((s) => s.points as Point[]);
  const holes = chart.shapes.filter((s) => s.hole).map((s) => s.points as Point[]);
  if (!outer.length || !Number.isFinite(cTop) || !Number.isFinite(cBottom) || !Number.isFinite(sigmaTop) || !Number.isFinite(sigmaBottom)) return null;

  const { map, bounds } = fitSection([...outer, ...holes], SEC_W, H, 44);
  const d = [...outer, ...holes].map((poly) => polygonPath(poly.map(map))).join(" ");
  const yTop = map([bounds.minX, bounds.maxY])[1];
  const yBot = map([bounds.minX, bounds.minY])[1];
  const yNa = map([bounds.minX, bounds.minY + cBottom])[1]; // neutral axis = centroid height
  const [xl] = map([bounds.minX, bounds.minY]);
  const [xr] = map([bounds.maxX, bounds.minY]);

  const peak = Math.max(Math.abs(sigmaTop), Math.abs(sigmaBottom));
  const k = peak > 0 ? K / peak : 0;
  const off = Math.min(1, Math.max(0, (yNa - yTop) / (yBot - yTop || 1)));
  const alpha = (pa: number) => (peak > 0 ? 0.12 + 0.78 * (Math.abs(pa) / peak) : 0);
  const xt = BASE + sigmaTop * k;
  const xb = BASE + sigmaBottom * k;
  // no T/C tag where the fibre is unstressed (e.g. at a free end)
  const tag = (pa: number) => (Math.abs(pa) <= 1e-9 * Math.max(peak, 1) ? "" : pa > 0 ? "T" : "C");
  const label = (pa: number, x: number, y: number) => {
    const right = pa >= 0;
    return (
      <text x={x + (right ? 8 : -8)} y={y} textAnchor={right ? "start" : "end"} dominantBaseline="middle" fontSize={12} className="fill-current font-mono">
        <tspan fontWeight={700} fill={colour(pa)}>{tag(pa)}</tspan> {stress(Math.abs(pa))}
      </text>
    );
  };

  return (
    <div className="space-y-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="mx-auto h-auto w-full max-w-2xl text-ink" role="img" aria-label="Bending stress across the section" data-testid="stress-section">
        <defs>
          <linearGradient id={`g${gid}`} gradientUnits="userSpaceOnUse" x1={0} y1={yTop} x2={0} y2={yBot}>
            <stop offset={0} stopColor={colour(sigmaTop)} stopOpacity={alpha(sigmaTop)} />
            <stop offset={off} stopColor={colour(sigmaTop)} stopOpacity={0} />
            <stop offset={off} stopColor={colour(sigmaBottom)} stopOpacity={0} />
            <stop offset={1} stopColor={colour(sigmaBottom)} stopOpacity={alpha(sigmaBottom)} />
          </linearGradient>
        </defs>

        <path d={d} fillRule="evenodd" fill={`url(#g${gid})`} stroke="currentColor" strokeOpacity={0.7} strokeWidth={1.6} />

        {/* stress block */}
        <g>
          <polygon points={`${BASE},${yTop} ${xt},${yTop} ${BASE},${yNa}`} fill={colour(sigmaTop)} fillOpacity={0.35} stroke={colour(sigmaTop)} strokeWidth={1.4} data-testid="stress-top-block" />
          <polygon points={`${BASE},${yNa} ${xb},${yBot} ${BASE},${yBot}`} fill={colour(sigmaBottom)} fillOpacity={0.35} stroke={colour(sigmaBottom)} strokeWidth={1.4} data-testid="stress-bottom-block" />
          <line x1={BASE} y1={yTop - 6} x2={BASE} y2={yBot + 6} stroke="currentColor" strokeWidth={1.2} />
          <g data-testid="stress-top-label">{label(sigmaTop, xt, yTop)}</g>
          <g data-testid="stress-bottom-label">{label(sigmaBottom, xb, yBot)}</g>
          <text x={BASE} y={yTop - 14} textAnchor="middle" fontSize={11} className="fill-current text-muted">σ(y)</text>
        </g>

        {/* neutral axis */}
        <line x1={Math.max(2, xl - 24)} y1={yNa} x2={BASE + K + 4} y2={yNa} stroke="currentColor" strokeWidth={1.2} strokeDasharray="6 4" data-testid="neutral-axis" />
        <text x={Math.max(2, xl - 24)} y={yNa - 6} fontSize={11} className="fill-current text-muted">N.A.</text>
        <text x={(xl + xr) / 2} y={yTop - 12} textAnchor="middle" fontSize={11} className="fill-current text-muted">top fibre</text>
        <text x={(xl + xr) / 2} y={yBot + 20} textAnchor="middle" fontSize={11} className="fill-current text-muted">bottom fibre</text>
      </svg>
      <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-muted">
        <span className="inline-flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: TENSION }} /> Tension</span>
        <span className="inline-flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: COMPRESSION }} /> Compression</span>
      </div>
    </div>
  );
}
