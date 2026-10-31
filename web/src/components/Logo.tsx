// AA monogram (same design as branding/aa-logo.svg)
export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} role="img" aria-label="AA Engineering Toolkit">
      <defs>
        <linearGradient id="aa-bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#4F46E5" />
          <stop offset="1" stopColor="#06B6D4" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="15" fill="url(#aa-bg)" />
      <path d="M12 48 L22 16 L32 48 L42 16 L52 48" fill="none" stroke="#fff" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M17.3 36 H46.7" fill="none" stroke="#fff" strokeWidth="4.5" strokeLinecap="round" />
      <circle cx="32" cy="48" r="3.2" fill="#fff" />
    </svg>
  );
}

export function Wordmark() {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark size={30} />
      <span className="leading-tight">
        <span className="block text-sm font-bold">
          <span className="text-primary">AA</span> Engineering
        </span>
        <span className="block text-[10px] font-medium tracking-[0.25em] text-muted">TOOLKIT</span>
      </span>
    </span>
  );
}
