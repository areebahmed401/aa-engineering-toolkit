import { Info, Plus, Trash2 } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { useEngine } from "../lib/engine";
import { needsFluidLibrary } from "../lib/fluids";
import { usePrefs } from "../lib/prefs";
import { checkBounds, defaultOf, type FieldSpec } from "../lib/schema";
import { displayUnit, inputString, toSI, type UnitSystem } from "../lib/units";
import { cn } from "./ui";

type Values = Record<string, unknown>;
export type FieldErrors = Record<string, string>; // "section.width" -> message

type FormProps = {
  fields: FieldSpec[];
  values: Values;
  onChange: (values: Values) => void;
  errors?: FieldErrors;
  path?: string;
};

export function ToolForm({ fields, values, onChange, errors = {}, path = "" }: FormProps) {
  return (
    <div className="grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-2">
      {fields.map((f) => (
        <Field
          key={f.name}
          field={f}
          value={values[f.name]}
          error={errors[path + f.name]}
          errors={errors}
          path={`${path}${f.name}.`}
          onChange={(v) => onChange({ ...values, [f.name]: v })}
        />
      ))}
    </div>
  );
}

type FieldProps = {
  field: FieldSpec;
  value: unknown;
  error?: string;
  errors: FieldErrors;
  path: string;
  onChange: (v: unknown) => void;
};

function Field({ field, value, error, errors, path, onChange }: FieldProps) {
  const id = useId();
  const { units } = usePrefs();

  if (field.kind === "object" && field.fields) {
    return (
      <fieldset className="col-span-full rounded-xl border border-border p-3">
        <legend className="px-1 text-xs font-semibold text-muted">{field.label}</legend>
        <ToolForm fields={field.fields} values={(value as Values) ?? {}} onChange={onChange} errors={errors} path={path} />
      </fieldset>
    );
  }

  if (field.kind === "array" && field.item) {
    const items = Array.isArray(value) ? (value as Values[]) : [];
    return (
      <fieldset className="col-span-full rounded-xl border border-border p-3">
        <legend className="px-1 text-xs font-semibold text-muted">{field.label}</legend>
        <div className="space-y-3">
          {items.map((item, i) => (
            <div key={i} className="relative rounded-lg bg-bg p-3">
              <button
                type="button"
                className="absolute right-2 top-2 rounded p-1 text-muted hover:text-fail"
                onClick={() => onChange(items.filter((_, j) => j !== i))}
                aria-label={`Remove ${field.label} ${i + 1}`}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
              <ToolForm
                fields={field.item!.fields ?? []}
                values={item}
                onChange={(v) => onChange(items.map((it, j) => (j === i ? v : it)))}
                errors={errors}
                path={`${path}${i}.`}
              />
            </div>
          ))}
          <button type="button" className="btn-ghost text-xs" onClick={() => onChange([...items, defaultOf(field.item!) as Values])}>
            <Plus className="h-3.5 w-3.5" /> Add {field.label.toLowerCase().replace(/s$/, "")}
          </button>
        </div>
      </fieldset>
    );
  }

  const unit = field.unit ? displayUnit(field.unit, units) : "";
  return (
    <div>
      <label htmlFor={id} className="label flex items-center gap-1">
        <span>{field.label}</span>
        {unit && <span className="text-muted/80">[{unit}]</span>}
        {field.description && field.description !== field.label && (
          <span title={field.description} className="cursor-help text-muted/70">
            <Info className="h-3 w-3" />
          </span>
        )}
      </label>
      <Control id={id} field={field} value={value} onChange={onChange} units={units} invalid={Boolean(error)} />
      {error && <p className="mt-1 text-xs text-fail">{error}</p>}
      {(field.name === "fluid" || field.name === "refrigerant") && needsFluidLibrary(value) && (
        <p className="mt-1 text-xs text-warn">First use loads CoolProp's full fluid library (about a minute in the browser).</p>
      )}
    </div>
  );
}

type ControlProps = {
  id: string;
  field: FieldSpec;
  value: unknown;
  onChange: (v: unknown) => void;
  units: UnitSystem;
  invalid: boolean;
};

function Control({ id, field, value, onChange, units, invalid }: ControlProps) {
  const { choices } = useEngine();
  const cls = cn("input", invalid && "border-fail focus:border-fail focus:ring-fail/20");

  if (field.kind === "enum") {
    return (
      <select id={id} className={cls} value={String(value ?? "")}
        onChange={(e) => {
          const opt = field.options!.find((o) => String(o) === e.target.value);
          onChange(opt ?? e.target.value);
        }}>
        {field.options!.map((o) => (
          <option key={String(o)} value={String(o)}>{String(o)}</option>
        ))}
      </select>
    );
  }

  if (field.kind === "boolean") {
    return <input id={id} type="checkbox" className="h-4 w-4 accent-primary" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />;
  }

  if (field.kind === "number" || field.kind === "integer") {
    return <NumberControl id={id} field={field} value={value as number | null} onChange={onChange} units={units} className={cls} />;
  }

  // strings: dropdowns from build-time choices, or free text with suggestions for fluids
  const hint = field.choices ?? "";
  if (hint.startsWith("materials:") && choices) {
    const options = choices.materials[hint.split(":")[1]] ?? [];
    return (
      <select id={id} className={cls} value={String(value ?? "")} onChange={(e) => onChange(e.target.value)}>
        {!options.includes(String(value)) && <option value={String(value)}>{String(value)}</option>}
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }
  if (hint === "profiles" && choices) {
    return (
      <select id={id} className={cls} value={String(value ?? "")} onChange={(e) => onChange(e.target.value)}>
        {choices.profiles.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }
  const listId = hint === "fluids" ? `${id}-list` : undefined;
  return (
    <>
      <input id={id} className={cls} value={String(value ?? "")} list={listId} onChange={(e) => onChange(e.target.value)} spellCheck={false} />
      {listId && choices && (
        <datalist id={listId}>
          {choices.fluids.map((f) => <option key={f} value={f}>{choices.fluids_fast.includes(f) ? "fast" : ""}</option>)}
        </datalist>
      )}
    </>
  );
}

function NumberControl({ id, field, value, onChange, units, className }: {
  id: string; field: FieldSpec; value: number | null; onChange: (v: unknown) => void; units: UnitSystem; className: string;
}) {
  const show = (v: number | null) => (v === null || v === undefined || Number.isNaN(v) ? "" : inputString(v, field.unit, units));
  const [text, setText] = useState(show(value));
  const [focused, setFocused] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  // follow external changes (unit switch, reset, URL) unless the user is typing
  useEffect(() => {
    if (!focused) setText(show(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, units, focused]);

  return (
    <>
      <input
        id={id}
        inputMode="decimal"
        className={cn(className, localError && "border-fail")}
        value={text}
        placeholder={field.nullable ? "optional" : ""}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onChange={(e) => {
          const t = e.target.value;
          setText(t);
          if (t.trim() === "" && field.nullable) {
            setLocalError(null);
            onChange(null);
            return;
          }
          const n = Number(t.replace(",", "."));
          if (t.trim() === "" || Number.isNaN(n)) {
            setLocalError("Enter a number");
            return;
          }
          const si = field.unit ? toSI(n, field.unit, units) : n;
          const v = field.kind === "integer" ? Math.round(si) : si;
          setLocalError(checkBounds(field, v));
          onChange(v);
        }}
      />
      {localError && <p className="mt-1 text-xs text-fail">{localError}</p>}
    </>
  );
}
