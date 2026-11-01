import { useEffect, useRef } from "react";
import { CHART_SHAPE_FILL, CHART_SHAPE_LINE, chartColorway } from "../lib/brandColors";
import { usePrefs } from "../lib/prefs";
import type { ChartSpec } from "../lib/types";
import { displayUnit, toDisplay, type UnitSystem } from "../lib/units";

let plotlyModule: Promise<typeof import("plotly.js-basic-dist-min")> | null = null;
const loadPlotly = () => (plotlyModule ??= import("plotly.js-basic-dist-min"));

function conv(values: (number | null)[], unit: string, system: UnitSystem) {
  return values.map((v) => (v === null ? null : unit ? toDisplay(v, unit, system) : v));
}

function axisTitle(label: string, unit: string, system: UnitSystem) {
  const u = unit ? displayUnit(unit, system) : "";
  return u ? `${label} [${u}]` : label;
}

export function ChartView({ chart }: { chart: ChartSpec }) {
  const ref = useRef<HTMLDivElement>(null);
  const { units, theme } = usePrefs();

  useEffect(() => {
    let cancelled = false;
    void draw();
    return () => {
      cancelled = true;
    };

    async function draw() {
    // Plotly is loaded on first use so the initial page stays light
    const Plotly = (await loadPlotly()).default;
    if (cancelled || !ref.current) return;
    const css = getComputedStyle(document.documentElement);
    const rgb = (name: string) => `rgb(${css.getPropertyValue(name).trim().split(" ").join(",")})`;
    const ink = rgb("--ink");
    const grid = rgb("--border");
    const surface = rgb("--surface");

    const traces: Record<string, unknown>[] = chart.shapes.map((s) => ({
      x: conv(s.points.map((p) => p[0]), chart.x_unit, units),
      y: conv(s.points.map((p) => p[1]), chart.y_unit, units),
      type: "scatter", mode: "lines", fill: "toself", hoverinfo: "skip", showlegend: false,
      line: { color: CHART_SHAPE_LINE, width: 1.5 },
      fillcolor: s.hole ? surface : CHART_SHAPE_FILL,
    }));
    for (const s of chart.series) {
      const yUnit = s.axis === "y2" ? chart.y2_unit : chart.y_unit;
      traces.push({
        name: s.name,
        x: conv(s.x, chart.x_unit, units),
        y: conv(s.y, yUnit, units),
        type: "scatter",
        mode: s.mode,
        yaxis: s.axis === "y2" ? "y2" : "y",
        fill: s.fill ? "tozeroy" : undefined,
        line: { color: s.color ?? undefined, width: 2.2, dash: s.dash ? "dash" : "solid" },
        marker: { size: s.mode === "markers" ? 10 : 6, color: s.color ?? undefined },
      });
    }
    const axis = { gridcolor: grid, zerolinecolor: grid, linecolor: grid, color: ink };
    const layout: Record<string, unknown> = {
      title: { text: chart.title, font: { size: 14, color: ink }, x: 0.01, y: 0.97, yanchor: "top" },
      colorway: chartColorway(theme),
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: "Inter, Segoe UI, sans-serif", color: ink, size: 12 },
      margin: { l: 64, r: chart.y2_label ? 70 : 20, t: 72, b: 52 },
      legend: { orientation: "h", x: 0, y: 1.02, yanchor: "bottom", font: { size: 11 } },
      xaxis: { ...axis, title: axisTitle(chart.x_label, chart.x_unit, units), type: chart.log_x ? "log" : "linear" },
      yaxis: {
        ...axis, title: axisTitle(chart.y_label, chart.y_unit, units), type: chart.log_y ? "log" : "linear",
        ...(chart.equal_aspect ? { scaleanchor: "x", scaleratio: 1 } : {}),
      },
      hovermode: "closest",
    };
    if (chart.y2_label) {
      layout.yaxis2 = { ...axis, title: axisTitle(chart.y2_label, chart.y2_unit, units), overlaying: "y", side: "right", showgrid: false };
    }
    await Plotly.react(ref.current, traces, layout, { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] });
    }
  }, [chart, units, theme]);

  useEffect(() => {
    const el = ref.current;
    return () => {
      if (el) void loadPlotly().then((m) => m.default.purge(el));
    };
  }, []);

  return <div ref={ref} className={chart.equal_aspect ? "h-[26rem] w-full" : "h-96 w-full"} data-testid={`chart-${chart.id}`} />;
}
