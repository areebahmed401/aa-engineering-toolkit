// Cross-section drawn from the Python outline() polygons (the "section" chart), with
// centroid / shear-centre markers and overall dimension lines.
import { fitSection, polygonPath, type Point } from "../lib/structural";
import type { ChartSpec } from "../lib/types";

type Props = { chart: ChartSpec; length: (m: number) => string; dims?: { label: string; value: string }[] };

const W = 420;
const H = 340;

export function SectionDrawing({ chart, length, dims = [] }: Props) {
  const outer = chart.shapes.filter((s) => !s.hole).map((s) => s.points as Point[]);
  const holes = chart.shapes.filter((s) => s.hole).map((s) => s.points as Point[]);
  if (!outer.length) return null;
  const point = (name: string): Point | null => {
    const s = chart.series.find((x) => x.name === name);
    return s && s.x[0] !== null && s.y[0] !== null ? [s.x[0] as number, s.y[0] as number] : null;
  };
  const markers = [point("Centroid"), point("Shear centre")];
  // markers can lie outside the section (channel shear centre), so they count when fitting
  const { map } = fitSection([...outer, ...holes, markers.filter((p): p is Point => p !== null)], W, H, 58);
  const bounds = fitSection([...outer, ...holes], W, H, 58).bounds;
  const d = [...outer, ...holes].map((poly) => polygonPath(poly.map(map))).join(" ");
  const [cog, cos] = markers.map((p) => (p ? map(p) : null));
  const [l, b] = map([bounds.minX, bounds.minY]);
  const [r, t] = map([bounds.maxX, bounds.maxY]);
  const same = cog && cos && Math.hypot(cog[0] - cos[0], cog[1] - cos[1]) < 2;

  return (
    <div className="space-y-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="mx-auto h-auto w-full max-w-md text-ink" role="img" aria-label="Cross-section" data-testid="section-drawing">
        <path d={d} fillRule="evenodd" className="fill-primary/20 stroke-primary" strokeWidth={1.8} />

        {/* width (below) and height (right) dimension lines */}
        <g className="text-muted" stroke="currentColor" strokeWidth={1} fontSize={12}>
          <line x1={l} y1={b + 8} x2={l} y2={b + 30} />
          <line x1={r} y1={b + 8} x2={r} y2={b + 30} />
          <line x1={l} y1={b + 24} x2={r} y2={b + 24} />
          <polygon points={`${l},${b + 24} ${l + 7},${b + 20} ${l + 7},${b + 28}`} fill="currentColor" />
          <polygon points={`${r},${b + 24} ${r - 7},${b + 20} ${r - 7},${b + 28}`} fill="currentColor" />
          <text x={(l + r) / 2} y={b + 42} textAnchor="middle" className="fill-current" stroke="none" data-testid="dim-width">
            {length(bounds.maxX - bounds.minX)}
          </text>
          <line x1={r + 8} y1={t} x2={r + 30} y2={t} />
          <line x1={r + 8} y1={b} x2={r + 30} y2={b} />
          <line x1={r + 24} y1={t} x2={r + 24} y2={b} />
          <polygon points={`${r + 24},${t} ${r + 20},${t + 7} ${r + 28},${t + 7}`} fill="currentColor" />
          <polygon points={`${r + 24},${b} ${r + 20},${b - 7} ${r + 28},${b - 7}`} fill="currentColor" />
          <text x={r + 38} y={(t + b) / 2} textAnchor="middle" className="fill-current" stroke="none" transform={`rotate(90 ${r + 38} ${(t + b) / 2})`} data-testid="dim-height">
            {length(bounds.maxY - bounds.minY)}
          </text>
        </g>

        {cog && (
          <g className="text-ink" data-testid="marker-centroid">
            <circle cx={cog[0]} cy={cog[1]} r={6} fill="none" stroke="currentColor" strokeWidth={1.6} />
            <line x1={cog[0] - 10} y1={cog[1]} x2={cog[0] + 10} y2={cog[1]} stroke="currentColor" strokeWidth={1.2} />
            <line x1={cog[0]} y1={cog[1] - 10} x2={cog[0]} y2={cog[1] + 10} stroke="currentColor" strokeWidth={1.2} />
          </g>
        )}
        {cos && (
          <g className="text-thermo" data-testid="marker-shear-centre">
            <polygon points={`${cos[0]},${cos[1] - 6} ${cos[0] + 6},${cos[1]} ${cos[0]},${cos[1] + 6} ${cos[0] - 6},${cos[1]}`}
              fill={same ? "none" : "currentColor"} stroke="currentColor" strokeWidth={1.4} />
          </g>
        )}
      </svg>
      <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-muted">
        <span className="inline-flex items-center gap-1"><span className="font-mono text-ink">⊕</span> Centroid</span>
        <span className="inline-flex items-center gap-1"><span className="text-thermo">◆</span> Shear centre{same ? " (at centroid)" : ""}</span>
        {dims.map((x) => <span key={x.label}>{x.label} = <span className="font-mono text-ink">{x.value}</span></span>)}
      </div>
    </div>
  );
}
