import { BRAND_GOLD, LOGO_DARK, LOGO_LIGHT, WORDMARK_SUB } from "../lib/brandColors";

// AA truss mark (Concept B, same geometry as branding/aa-logo.svg, no background tile).
// ink: colour of the bottom chord and cross bars; pins use the opposite colour.
// Pass ink="currentColor" to follow the surrounding text colour.
export function LogoMark({ size = 32, ink = LOGO_LIGHT }: { size?: number; ink?: string }) {
  const pinFill = ink === LOGO_LIGHT ? LOGO_DARK : ink === "currentColor" ? "rgb(var(--surface))" : LOGO_LIGHT;
  const pinStroke = ink === LOGO_LIGHT ? LOGO_LIGHT : ink;
  const gold = { stroke: BRAND_GOLD, strokeLinecap: "round" as const };
  const dark = { stroke: ink, strokeLinecap: "round" as const };
  const pins: [number, number][] = [
    [6, 54], [32, 54], [58, 54], [19, 12], [45, 12], [10.95, 38], [27.05, 38], [36.95, 38], [53.05, 38], [19, 54], [45, 54],
  ];
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} role="img" aria-label="AA Engineering Toolkit" color={ink === "currentColor" ? undefined : ink}>
      <line x1="6" y1="54" x2="58" y2="54" {...dark} strokeWidth="3.4" />
      <line x1="6" y1="54" x2="19" y2="12" {...gold} strokeWidth="3.6" />
      <line x1="19" y1="12" x2="32" y2="54" {...gold} strokeWidth="3.6" />
      <line x1="32" y1="54" x2="45" y2="12" {...gold} strokeWidth="3.6" />
      <line x1="45" y1="12" x2="58" y2="54" {...gold} strokeWidth="3.6" />
      <line x1="19" y1="12" x2="45" y2="12" {...gold} strokeWidth="3.6" />
      <line x1="10.95" y1="38" x2="27.05" y2="38" {...dark} strokeWidth="2.8" />
      <line x1="36.95" y1="38" x2="53.05" y2="38" {...dark} strokeWidth="2.8" />
      <line x1="10.95" y1="38" x2="19" y2="54" {...gold} strokeWidth="2" />
      <line x1="27.05" y1="38" x2="19" y2="54" {...gold} strokeWidth="2" />
      <line x1="36.95" y1="38" x2="45" y2="54" {...gold} strokeWidth="2" />
      <line x1="53.05" y1="38" x2="45" y2="54" {...gold} strokeWidth="2" />
      {pins.map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="2.6" fill={pinFill} stroke={pinStroke} strokeWidth="1.6" />
      ))}
    </svg>
  );
}

// Wordmark sits on the black header.
export function Wordmark() {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark size={30} />
      <span className="leading-tight">
        <span className="block text-sm font-bold text-white">
          <span style={{ color: BRAND_GOLD }}>AA</span> Engineering
        </span>
        <span className="block text-[10px] font-medium tracking-[0.25em]" style={{ color: WORDMARK_SUB }}>TOOLKIT</span>
      </span>
    </span>
  );
}
