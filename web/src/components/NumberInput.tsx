import { useEffect, useId, useState } from "react";
import { cn } from "./ui";

export type Conversion = { unit: string; toSI: (v: number) => number; fromSI: (v: number) => number };

type Props = {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
  conv: Conversion;
  nullable?: boolean;
  placeholder?: string;
  min?: number; // SI, exclusive lower bound when `positive`
  positive?: boolean;
  error?: string;
  testId?: string;
  className?: string;
};

/** Labelled number box that edits an SI value in display units (kept as typed while focused). */
export function NumberInput({ label, value, onChange, conv, nullable, placeholder, min, positive, error, testId, className }: Props) {
  const id = useId();
  const show = (v: number | null) => (v === null || v === undefined || Number.isNaN(v) ? "" : String(Number.parseFloat(conv.fromSI(v).toPrecision(8))));
  const [text, setText] = useState(show(value));
  const [focused, setFocused] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (!focused) setText(show(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, conv.unit, focused]);

  const message = localError ?? error;
  return (
    <div className={className}>
      <label htmlFor={id} className="label">
        {label} {conv.unit && <span className="text-muted/80">[{conv.unit}]</span>}
      </label>
      <input
        id={id}
        inputMode="decimal"
        data-testid={testId}
        className={cn("input", message && "border-fail focus:border-fail focus:ring-fail/20")}
        value={text}
        placeholder={placeholder ?? (nullable ? "optional" : "")}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onChange={(e) => {
          const t = e.target.value;
          setText(t);
          if (t.trim() === "" && nullable) {
            setLocalError(null);
            onChange(null);
            return;
          }
          const n = Number(t.replace(",", "."));
          if (t.trim() === "" || Number.isNaN(n)) {
            setLocalError("Enter a number");
            return;
          }
          const si = conv.toSI(n);
          if (positive && !(si > 0)) setLocalError("Must be > 0");
          else if (min !== undefined && si < min) setLocalError(`Must be ≥ ${conv.fromSI(min)}`);
          else setLocalError(null);
          onChange(si);
        }}
      />
      {message && <p className="mt-1 text-xs text-fail">{message}</p>}
    </div>
  );
}
