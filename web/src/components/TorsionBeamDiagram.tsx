// Torsion member sketch drawn from the inputs: beam axis, end conditions (fixed wall, fork, free), point torques as
// double-headed arrows along the axis (formulary style), a uniform torque m_t as a row of small double arrows,
// and the position of interest.
import type { TorqueLoad, TorsionSupport } from "../lib/structural";

export type TorsionDiagramFormat = { length: (m: number) => string; torque: (nm: number) => string; perLength: (nm: number) => string };

type Props = {
  length: number;
  left: TorsionSupport;
  right: TorsionSupport;
  loads: TorqueLoad[];
  mt: number;
  position: number;
  fmt: TorsionDiagramFormat;
};

const W = 640;
const H = 230;
const X0 = 70;
const X1 = 570;
const BEAM_Y = 145;

const pts = (p: [number, number][]) => p.map((q) => q.join(",")).join(" ");

/** Double-headed arrow along +x (dir 1) or −x (dir −1), centred on cx. */
function DoubleArrow({ cx, y, dir, size = 40, head = 6 }: { cx: number; y: number; dir: 1 | -1; size?: number; head?: number }) {
  const tail = cx - (dir * size) / 2;
  const tip = cx + (dir * size) / 2;
  const h1 = tip - dir * head * 1.4; // second head sits behind the first
  const back = (t: number): [number, number][] => [[t, y], [t - dir * head * 1.4, y - head * 0.7], [t - dir * head * 1.4, y + head * 0.7]];
  return (
    <g>
      <line x1={tail} y1={y} x2={h1} y2={y} stroke="currentColor" strokeWidth={2.2} />
      <polygon points={pts(back(tip))} fill="currentColor" />
      <polygon points={pts(back(h1))} fill="currentColor" />
    </g>
  );
}

function Hatch({ x, y, outward }: { x: number; y: number; outward: 1 | -1 }) {
  const lines = [];
  for (let yy = y - 30; yy <= y + 26; yy += 8) lines.push(<line key={yy} x1={x} y1={yy} x2={x + outward * 8} y2={yy + 8} />);
  return (
    <g stroke="currentColor" strokeWidth={1}>
      <line x1={x} y1={y - 34} x2={x} y2={y + 34} strokeWidth={2} />
      {lines}
    </g>
  );
}

function End({ kind, x, side }: { kind: TorsionSupport; x: number; side: "left" | "right" }) {
  const out: 1 | -1 = side === "left" ? -1 : 1;
  if (kind === "free") return <g data-testid={`torsion-support-${side}-free`} />;
  if (kind === "fixed") {
    return (
      <g className="text-muted" data-testid={`torsion-support-${side}-fixed`}>
        <Hatch x={x + out * 2} y={BEAM_Y} outward={out} />
      </g>
    );
  }
  // fork: two prongs clasp the end (twist held, the end may warp), attached to a hatched wall
  const wall = x + out * 14;
  return (
    <g className="text-muted" data-testid={`torsion-support-${side}-fork`}>
      <Hatch x={wall} y={BEAM_Y} outward={out} />
      <line x1={wall} y1={BEAM_Y - 18} x2={x - out * 14} y2={BEAM_Y - 18} stroke="currentColor" strokeWidth={2} />
      <line x1={wall} y1={BEAM_Y + 18} x2={x - out * 14} y2={BEAM_Y + 18} stroke="currentColor" strokeWidth={2} />
    </g>
  );
}

export function TorsionBeamDiagram({ length, left, right, loads, mt, position, fmt }: Props) {
  const L = length > 0 ? length : 1;
  const px = (x: number) => X0 + (Math.min(Math.max(x, 0), L) / L) * (X1 - X0);

  // stack labels of nearby torques on separate levels
  const order = loads.map((l, i) => ({ l, i, x: px(l.x) })).sort((a, b) => a.x - b.x);
  const level: Record<number, number> = {};
  for (const o of order) {
    let k = 0;
    while (order.some((p) => p.i !== o.i && level[p.i] === k && Math.abs(p.x - o.x) < 110)) k += 1;
    level[o.i] = k;
  }

  const nMt = Math.max(2, Math.floor((X1 - X0) / 48));
  const mtX = Array.from({ length: nMt }, (_, k) => X0 + ((k + 0.5) * (X1 - X0)) / nMt);
  const posX = px(position);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full min-w-[520px] select-none text-ink" role="img" aria-label="Torsion member with supports and torques" data-testid="torsion-beam">
      {mt !== 0 && (
        <g className="text-structural" data-testid="torsion-mt">
          {mtX.map((x) => <DoubleArrow key={x} cx={x} y={BEAM_Y - 18} dir={mt > 0 ? 1 : -1} size={26} head={4.5} />)}
          <text x={X0} y={BEAM_Y - 32} className="fill-current text-[14px] font-medium">m_t = {fmt.perLength(mt)}</text>
        </g>
      )}

      <rect x={X0} y={BEAM_Y - 4} width={X1 - X0} height={8} rx={2} className="fill-current text-ink" opacity={0.85} data-testid="torsion-beam-axis" />
      <End kind={left} x={X0} side="left" />
      <End kind={right} x={X1} side="right" />

      {loads.map((l, i) => {
        if (!Number.isFinite(l.T) || l.T === 0) return null;
        const x = px(l.x);
        const y = BEAM_Y - 58 - 24 * (level[i] ?? 0);
        return (
          <g key={i} className="text-primary-ink" data-testid="torsion-load">
            <line x1={x} y1={y + 6} x2={x} y2={BEAM_Y - 4} stroke="currentColor" strokeWidth={1} strokeDasharray="3 3" />
            <DoubleArrow cx={x} y={y} dir={l.T > 0 ? 1 : -1} />
            <text x={x} y={y - 9} textAnchor="middle" className="fill-current text-[14px] font-medium">{fmt.torque(l.T)}</text>
          </g>
        );
      })}

      <g className="text-ink" data-testid="torsion-position">
        <line x1={posX} y1={BEAM_Y + 8} x2={posX} y2={H - 22} stroke="currentColor" strokeWidth={1.2} strokeDasharray="4 3" />
        <polygon points={pts([[posX, BEAM_Y + 8], [posX - 5, BEAM_Y + 18], [posX + 5, BEAM_Y + 18]])} fill="currentColor" />
        <text x={posX + (posX > X1 - 50 ? -6 : posX < X0 + 50 ? 6 : 0)} y={BEAM_Y + 36} textAnchor={posX > X1 - 50 ? "end" : posX < X0 + 50 ? "start" : "middle"} className="fill-current text-[13px] font-medium">x = {fmt.length(position)}</text>
      </g>

      <g className="text-muted" fontSize={13}>
        <line x1={X0} y1={H - 22} x2={X1} y2={H - 22} stroke="currentColor" strokeWidth={1} />
        {[0, L].map((x) => (
          <g key={x}>
            <line x1={px(x)} y1={H - 26} x2={px(x)} y2={H - 18} stroke="currentColor" />
            <text x={px(x)} y={H - 6} textAnchor="middle" className="fill-current">{fmt.length(x)}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}
