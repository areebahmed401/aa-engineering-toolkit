// Brand colours that cannot come from CSS variables (SVG logo, Plotly). Mirrors branding/theme.json.
export const BRAND_GOLD = "#F2B705";
export const LOGO_DARK = "#111214";
export const LOGO_LIGHT = "#FFFFFF";
export const WORDMARK_SUB = "#9A9DA4";

const CHART_BASE = ["#E0A800", "#3D7EA6", "#C8632B", "#3E9A5C", "#7A64A8", "#8A8D93", "#9A7400"];

/** Plotly colorway: gold first, then ink (theme dependent), then the discipline colours. */
export function chartColorway(theme: "light" | "dark"): string[] {
  const ink = theme === "dark" ? "#ECECEE" : "#2B2D31";
  return [CHART_BASE[0], ink, ...CHART_BASE.slice(1)];
}

export const CHART_SHAPE_LINE = "#E0A800";
export const CHART_SHAPE_FILL = "rgba(224,168,0,0.18)";
