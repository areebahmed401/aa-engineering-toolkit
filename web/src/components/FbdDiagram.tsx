// Free-body diagram of the beam, drawn from the inputs (and the reactions once solved).
import { fbdLayout, momentArc, type BeamValues, type FbdArrow, type FbdFormat, type FbdMoment, type Reactions, type SupportKind } from "../lib/structural";

const pts = (p: [number, number][]) => p.map((q) => q.join(",")).join(" ");

function Arrow({ a, className }: { a: FbdArrow; className: string }) {
  const down = a.yHead > a.yTail;
  const h = 9;
  const tip = a.yHead;
  const back = down ? tip - h : tip + h;
  return (
    <g className={className}>
      <line x1={a.x} y1={a.yTail} x2={a.x} y2={back} stroke="currentColor" strokeWidth={2.2} />
      <polygon points={pts([[a.x, tip], [a.x - 5.5, back], [a.x + 5.5, back]])} fill="currentColor" />
      <text x={a.x + 8} y={Math.min(a.yTail, a.yHead) + (a.reaction ? Math.abs(a.yHead - a.yTail) : 10)} className="fill-current text-[14px] font-medium" dominantBaseline={a.reaction ? "auto" : "hanging"}>
        {a.label}
      </text>
    </g>
  );
}

function Moment({ m, y, className, labelX, anchor }: { m: FbdMoment; y: number; className: string; labelX?: number; anchor?: "start" | "end" }) {
  const r = m.reaction ? 20 : 18;
  const { d, head } = momentArc(m.x, y, r, m.ccw);
  return (
    <g className={className}>
      <path d={d} fill="none" stroke="currentColor" strokeWidth={2.2} />
      <polygon points={pts(head)} fill="currentColor" />
      <text x={labelX ?? m.x} y={m.reaction ? y - r - 8 : y + r + 16} textAnchor={anchor ?? "middle"} className="fill-current text-[14px] font-medium">
        {m.label} {m.ccw ? "↺" : "↻"}
      </text>
    </g>
  );
}

function Hatch({ x1, y1, x2, y2, vertical, flip }: { x1: number; y1: number; x2: number; y2: number; vertical?: boolean; flip?: boolean }) {
  const lines = [];
  if (vertical) {
    for (let y = y1; y <= y2; y += 8) lines.push(<line key={y} x1={x1} y1={y} x2={x1 + (flip ? 8 : -8)} y2={y + 8} />);
  } else {
    for (let x = x1; x <= x2; x += 8) lines.push(<line key={x} x1={x} y1={y1} x2={x - 8} y2={y1 + 8} />);
  }
  return (
    <g stroke="currentColor" strokeWidth={1}>
      <line x1={x1} y1={y1} x2={vertical ? x1 : x2} y2={vertical ? y2 : y1} strokeWidth={2} />
      {lines}
    </g>
  );
}

function Support({ kind, x, y, side }: { kind: SupportKind; x: number; y: number; side: "left" | "right" }) {
  const flip = side === "right";
  if (kind === "fixed") {
    const wx = flip ? x + 2 : x - 2;
    return (
      <g className="text-muted" data-testid={`support-${side}-fixed`}>
        <Hatch x1={wx} y1={y - 34} x2={wx} y2={y + 26} vertical flip={flip} />
      </g>
    );
  }
  if (kind === "free") return <g data-testid={`support-${side}-free`} />;
  const top = y + 4;
  const base = y + 24;
  return (
    <g className="text-muted" data-testid={`support-${side}-${kind}`}>
      <polygon points={pts([[x, top], [x - 12, base], [x + 12, base]])} fill="none" stroke="currentColor" strokeWidth={2} />
      {kind === "roller" ? (
        <>
          <circle cx={x - 6} cy={base + 4} r={3.5} fill="none" stroke="currentColor" strokeWidth={1.5} />
          <circle cx={x + 6} cy={base + 4} r={3.5} fill="none" stroke="currentColor" strokeWidth={1.5} />
          <Hatch x1={x - 18} y1={base + 8} x2={x + 18} y2={base + 8} />
        </>
      ) : (
        <Hatch x1={x - 18} y1={base} x2={x + 18} y2={base} />
      )}
    </g>
  );
}

export function FbdDiagram({ beam, fmt, reactions }: { beam: BeamValues; fmt: FbdFormat; reactions?: Reactions | null }) {
  const f = fbdLayout(beam, fmt, reactions);
  const y = f.beamY;
  return (
    <svg viewBox={`0 0 ${f.width} ${f.height}`} className="h-auto w-full min-w-[540px] select-none text-ink" role="img" aria-label="Free-body diagram" data-testid="fbd">
      {/* UDL blocks */}
      {f.udls.map((u, i) => (
        <g key={`u${i}`} className="text-structural" data-testid="fbd-udl">
          <rect x={u.x1} y={u.yTop} width={Math.max(u.x2 - u.x1, 1)} height={y - 4 - u.yTop} className="fill-current" opacity={0.1} />
          <line x1={u.x1} y1={u.yTop} x2={u.x2} y2={u.yTop} stroke="currentColor" strokeWidth={1.8} />
          {u.arrows.map((ax) => {
            const tip = u.down ? y - 4 : u.yTop;
            const back = u.down ? tip - 6 : tip + 6;
            return (
              <g key={ax}>
                <line x1={ax} y1={u.yTop} x2={ax} y2={y - 4} stroke="currentColor" strokeWidth={1.2} />
                <polygon points={pts([[ax, tip], [ax - 3.5, back], [ax + 3.5, back]])} fill="currentColor" />
              </g>
            );
          })}
          <text x={u.x1 + 4} y={u.yTop - 6} className="fill-current text-[14px] font-medium">{u.label}</text>
        </g>
      ))}

      {/* beam */}
      <rect x={f.x0} y={y - 4} width={f.x1 - f.x0} height={8} rx={2} className="fill-current text-ink" opacity={0.85} data-testid="fbd-beam" />

      {f.supports.map((s) => <Support key={s.side} kind={s.kind} x={s.x} y={y} side={s.side} />)}

      {f.points.map((a, i) => <g key={`p${i}`} data-testid="fbd-point"><Arrow a={a} className="text-primary-ink" /></g>)}
      {f.moments.map((m, i) => <g key={`m${i}`} data-testid="fbd-moment"><Moment m={m} y={y} className="text-thermo" /></g>)}

      {f.reactions.map((a, i) => <g key={`r${i}`} data-testid="fbd-reaction"><Arrow a={a} className="text-ok" /></g>)}
      {f.reactionMoments.map((m, i) => (
        <g key={`rm${i}`} data-testid="fbd-reaction-moment"><Moment m={{ ...m, x: m.x + (m.x === f.x0 ? -34 : 34) }} y={y - 56} className="text-ok"
          labelX={m.x === f.x0 ? 6 : f.width - 6} anchor={m.x === f.x0 ? "start" : "end"} /></g>
      ))}

      {/* position axis */}
      <g className="text-muted" fontSize={13}>
        <line x1={f.x0} y1={f.height - 22} x2={f.x1} y2={f.height - 22} stroke="currentColor" strokeWidth={1} />
        {f.ticks.map((t, i) => (
          <g key={i}>
            <line x1={t.x} y1={f.height - 26} x2={t.x} y2={f.height - 18} stroke="currentColor" />
            <text x={t.x} y={f.height - 6} textAnchor="middle" className="fill-current">{t.label}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}
