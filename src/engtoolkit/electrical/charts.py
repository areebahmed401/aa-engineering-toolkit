"""Chart specs for the electrical tools (SI units; the web app converts for display)."""
from __future__ import annotations

from engtoolkit.core.charts import Chart, Series

# one colour per C-rate / case, reused for the matching PyBaMM (dashed) curve
PALETTE = ("#4F46E5", "#059669", "#D97706", "#DC2626", "#0891B2", "#7C3AED")


def color(i: int) -> str:
    return PALETTE[i % len(PALETTE)]


def discharge_charts(runs: list[dict], references: list[dict | None], aging: list[dict] | None = None,
                     aging_refs: list[dict | None] | None = None, x_capacity: bool = True,
                     reference_temperature: bool = True) -> list[Chart]:
    """
    ``runs``: dicts with label, sim (ecm.Simulation). ``references``: PyBaMM discharge dicts (or None) per run.
    ``aging``: dicts with label, curve (aging.AgingCurve); ``aging_refs``: PyBaMM aging dicts per curve.
    ``reference_temperature``: also overlay the PyBaMM temperatures (only meaningful for similar cooling).
    """
    volt = Chart("voltage", "Terminal voltage", "Charge delivered" if x_capacity else "Time",
                 "Ah" if x_capacity else "s", "Voltage", "V")
    temp = Chart("temperature", "Cell temperature", "Time", "s", "Temperature", "K")
    soc = Chart("soc", "State of charge and current", "Time", "s", "SOC", "", y2_label="Current", y2_unit="A")
    heat = Chart("heat", "Heat generated and removed per cell", "Time", "s", "Heat rate", "W/cell")
    for i, (run, ref) in enumerate(zip(runs, references)):
        s, c, label = run["sim"], color(i), run["label"]
        x = _cumulative_Ah(s) if x_capacity else s.t
        volt.series.append(Series(label, x, s.voltage, color=c))
        temp.series.append(Series(label, s.t, s.temperature, color=c))
        soc.series.append(Series(f"SOC {label}", s.t, s.soc, color=c))
        soc.series.append(Series(f"I {label}", s.t, s.current, axis="y2", dash=True, color=c))
        heat.series.append(Series(f"generated {label}", s.t, s.heat, color=c))
        heat.series.append(Series(f"removed {label}", s.t, s.heat_removed, dash=True, color=c))
        if ref is not None:
            name = f"PyBaMM DFN {label}"
            volt.series.append(Series(name, ref["capacity_Ah"] if x_capacity else ref["time"], ref["voltage"],
                                      dash=True, color=c))
            if reference_temperature:
                temp.series.append(Series(f"{name} (h = {ref['h']:g} W/(m²·K))", ref["time"], ref["temperature"],
                                          dash=True, color=c))
    charts = [volt, temp, soc, heat]
    if aging:
        charts.append(aging_chart(aging, aging_refs))
    return charts


def aging_chart(aging: list[dict], refs: list[dict | None] | None = None) -> Chart:
    chart = Chart("capacity_fade", "Capacity retention over cycles", "Full-equivalent cycles", "",
                  "Relative capacity", "")
    refs = refs or [None] * len(aging)
    for i, (a, ref) in enumerate(zip(aging, refs)):
        curve = a["curve"]
        chart.series.append(Series(a["label"], curve.cycles, curve.capacity, color=color(i)))
        if ref is not None:
            chart.series.append(Series(f"PyBaMM SEI + plating {a['label']}", ref["cycles"], ref["capacity"],
                                       dash=True, color=color(i)))
    return chart


def resistance_chart(aging: list[dict]) -> Chart:
    chart = Chart("resistance_growth", "Resistance growth over cycles", "Full-equivalent cycles", "",
                  "Relative resistance", "")
    for i, a in enumerate(aging):
        chart.series.append(Series(a["label"], a["curve"].cycles, a["curve"].resistance, color=color(i)))
    return chart


def _cumulative_Ah(sim):
    import numpy as np
    if len(sim.t) < 2:
        return np.zeros_like(sim.t)
    dq = 0.5 * (sim.current[1:] + sim.current[:-1]) * np.diff(sim.t) / 3600
    return np.abs(np.concatenate([[0.0], np.cumsum(dq)]))
