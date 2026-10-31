// Shapes of the JSON produced by engtoolkit.webapi / scripts/build_web_assets.py

export type JsonSchema = {
  type?: string | string[];
  title?: string;
  description?: string;
  default?: unknown;
  enum?: (string | number)[];
  const?: string | number;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  items?: JsonSchema;
  anyOf?: JsonSchema[];
  allOf?: JsonSchema[];
  $ref?: string;
  $defs?: Record<string, JsonSchema>;
  unit?: string;
  label?: string | null;
  choices?: string;
};

export type ToolSchema = {
  id: string;
  name: string;
  section: string;
  description: string;
  reference: string;
  tags: string[];
  custom_page: boolean;
  has_charts: boolean;
  inputs: JsonSchema;
};

export type Schema = {
  version: string;
  sections: Record<string, string>;
  tools: ToolSchema[];
};

export type Choices = {
  fluids_fast: string[];
  fluids: string[];
  incompressibles: string[];
  materials: Record<string, string[]>;
  material_info: Record<string, { family: string; source: string }>;
  profiles: string[];
};

export type Manifest = { version: string; wheel: string; pyodide: string; packages: string[] };

export type ResultField = { name: string; label: string; unit: string; summary: boolean; value: unknown };

export type ChartSeries = {
  name: string;
  x: (number | null)[];
  y: (number | null)[];
  mode: "lines" | "markers" | "lines+markers";
  axis: "y" | "y2";
  fill: boolean;
  dash: boolean;
  color: string | null;
};

export type ChartShape = { points: [number, number][]; hole: boolean };

export type ChartSpec = {
  id: string;
  title: string;
  x_label: string;
  x_unit: string;
  y_label: string;
  y_unit: string;
  y2_label: string;
  y2_unit: string;
  log_x: boolean;
  log_y: boolean;
  equal_aspect: boolean;
  series: ChartSeries[];
  shapes: ChartShape[];
};

export type RunError = {
  kind: "validation" | "calculation" | "unknown_tool" | "engine";
  message: string;
  fields?: { loc: string[]; msg: string }[];
};

export type RunResponse =
  | {
      ok: true;
      tool: string;
      inputs: Record<string, unknown>;
      result: { type: string; fields: ResultField[] };
      charts: ChartSpec[];
      chart_error: string | null;
      elapsed_ms: number;
    }
  | { ok: false; error: RunError };

export type EngineStage = "idle" | "loading-python" | "loading-packages" | "installing" | "warming" | "ready" | "error";

export type EngineProgress = { stage: EngineStage; message: string; percent: number };
