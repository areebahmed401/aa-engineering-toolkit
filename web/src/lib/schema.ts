// Turn a pydantic JSON schema into form field specs the UI can render.
import type { JsonSchema } from "./types";

export type FieldKind = "number" | "integer" | "string" | "boolean" | "enum" | "object" | "array";

export type FieldSpec = {
  name: string;
  label: string;
  description: string;
  unit: string;
  kind: FieldKind;
  nullable: boolean;
  default: unknown;
  min?: number;
  max?: number;
  exclusiveMin?: number;
  exclusiveMax?: number;
  options?: (string | number)[];
  choices?: string;
  fields?: FieldSpec[]; // object
  item?: FieldSpec; // array of objects
};

function deref(s: JsonSchema, defs: Record<string, JsonSchema>): JsonSchema {
  let out = s;
  if (out.$ref) out = { ...defs[out.$ref.split("/").pop()!], ...omit(out, "$ref") };
  if (out.allOf?.length === 1) out = { ...deref(out.allOf[0], defs), ...omit(out, "allOf") };
  return out;
}

function omit<T extends object>(o: T, key: string): Partial<T> {
  const copy = { ...o } as Record<string, unknown>;
  delete copy[key];
  return copy as Partial<T>;
}

function humanize(name: string): string {
  return name.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function fieldFromSchema(name: string, raw: JsonSchema, defs: Record<string, JsonSchema>): FieldSpec {
  let s = deref(raw, defs);
  let nullable = false;
  if (s.anyOf) {
    const nonNull = s.anyOf.filter((a) => a.type !== "null");
    nullable = nonNull.length < s.anyOf.length;
    s = { ...deref(nonNull[0] ?? {}, defs), ...omit(s, "anyOf") };
  }
  // nested models carry their class name as title (e.g. "SectionInputs"); use the field name instead
  const isRef = Boolean(raw.$ref || raw.allOf || raw.anyOf?.some((a) => a.$ref));
  const base: FieldSpec = {
    name,
    label: raw.label || s.label || (isRef ? humanize(name) : s.title) || humanize(name),
    description: s.description ?? "",
    unit: s.unit ?? "",
    kind: "string",
    nullable,
    default: s.default,
    min: s.minimum,
    max: s.maximum,
    exclusiveMin: s.exclusiveMinimum,
    exclusiveMax: s.exclusiveMaximum,
    choices: s.choices,
  };
  if (s.enum) return { ...base, kind: "enum", options: s.enum };
  if (s.properties) {
    return { ...base, kind: "object", fields: Object.entries(s.properties).map(([k, v]) => fieldFromSchema(k, v, defs)) };
  }
  if (s.type === "array" && s.items) return { ...base, kind: "array", item: fieldFromSchema("item", s.items, defs) };
  if (s.type === "number") return { ...base, kind: "number" };
  if (s.type === "integer") return { ...base, kind: "integer" };
  if (s.type === "boolean") return { ...base, kind: "boolean" };
  return base;
}

export function fieldsFromSchema(schema: JsonSchema): FieldSpec[] {
  const defs = schema.$defs ?? {};
  return Object.entries(schema.properties ?? {}).map(([k, v]) => fieldFromSchema(k, v, defs));
}

/** Default values for a list of fields (objects and arrays filled recursively). */
export function defaultValues(fields: FieldSpec[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const f of fields) out[f.name] = defaultOf(f);
  return out;
}

export function defaultOf(f: FieldSpec): unknown {
  if (f.kind === "object") return { ...defaultValues(f.fields ?? []), ...((f.default as object) ?? {}) };
  if (f.kind === "array") {
    if (Array.isArray(f.default)) return f.default;
    return f.item ? [defaultOf(f.item)] : [];
  }
  return f.default ?? (f.nullable ? null : f.kind === "boolean" ? false : "");
}

/** Client-side bounds check on an SI value; returns an error message or null. */
export function checkBounds(f: FieldSpec, value: number): string | null {
  if (f.min !== undefined && value < f.min) return `Must be ≥ ${f.min}`;
  if (f.max !== undefined && value > f.max) return `Must be ≤ ${f.max}`;
  if (f.exclusiveMin !== undefined && value <= f.exclusiveMin) return `Must be > ${f.exclusiveMin}`;
  if (f.exclusiveMax !== undefined && value >= f.exclusiveMax) return `Must be < ${f.exclusiveMax}`;
  return null;
}
