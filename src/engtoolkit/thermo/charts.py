"""Chart specs for the thermo tools (SI units; front ends convert for display)."""
from __future__ import annotations

import numpy as np

from engtoolkit.catalogs import pipes
from engtoolkit.core.charts import Chart, Series
from engtoolkit.materials import AIR, fluid

from .insulation import insulated_pipe_heat_loss
from .pipe_flow import pipe_pressure_drop

PRIMARY, ACCENT, ORANGE, RED = "#E0A800", "#2A9D8F", "#C8632B", "#DC2626"


def saturation_dome(fluid_name: str, n: int = 50):
    """Saturated liquid and vapour states from near the triple point to near the critical point."""
    f = fluid(fluid_name)
    T = np.linspace(max(f.T_triple, f.T_min) + 0.5, f.T_critical - 0.5, n)
    liq, vap = [], []
    for t in T:
        try:
            a, b = f.saturation(T=float(t))
        except ValueError:
            continue
        liq.append(a)
        vap.append(b)
    return liq, vap


def _dome_charts(fluid_name: str, points, labels=(), close: bool = False, title_suffix: str = "") -> list[Chart]:
    liq, vap = saturation_dome(fluid_name)
    pts = list(points) + ([points[0]] if close and points else [])
    mode = "lines+markers" if len(pts) > 1 else "markers"
    ph = Chart("ph", f"p-h diagram{title_suffix}", "Enthalpy", "J/kg", "Pressure", "Pa", log_y=True, series=[
        Series("Saturated liquid", [s.h for s in liq], [s.P for s in liq], color=PRIMARY),
        Series("Saturated vapour", [s.h for s in vap], [s.P for s in vap], color=ACCENT),
        Series("State" if len(points) == 1 else "Cycle", [p.h for p in pts], [p.P for p in pts], mode=mode, color=ORANGE),
    ])
    ts = Chart("ts", f"T-s diagram{title_suffix}", "Entropy", "J/(kg·K)", "Temperature", "K", series=[
        Series("Saturated liquid", [s.s for s in liq], [s.T for s in liq], color=PRIMARY),
        Series("Saturated vapour", [s.s for s in vap], [s.T for s in vap], color=ACCENT),
        Series("State" if len(points) == 1 else "Cycle", [p.s for p in pts], [p.T for p in pts], mode=mode, color=ORANGE),
    ])
    return [ph, ts]


def fluid_properties_charts(inp, res) -> list[Chart]:
    if inp.fluid == AIR or fluid(inp.fluid).is_incompressible:
        return []
    try:
        return _dome_charts(inp.fluid, [res], title_suffix=f": {inp.fluid}")
    except ValueError:
        return []


def saturated_table_charts(inp, res) -> list[Chart]:
    T = [row[0] + 273.15 for row in res.rows]
    P = [row[1] * 1e3 for row in res.rows]
    return [Chart("psat", "Saturation pressure", "Temperature", "K", "Pressure", "Pa", log_y=True,
                  series=[Series("Saturation curve", T, P, mode="lines+markers", color=PRIMARY)])]


def pipe_pressure_drop_charts(inp, res) -> list[Chart]:
    from .pipe_flow import FITTING_FIELDS
    fittings = {name: getattr(inp, attr) for name, attr in FITTING_FIELDS.items()}
    dn, dp, v = [], [], []
    for size in pipes.sizes(inp.schedule):
        try:
            r = pipe_pressure_drop(inp.fluid, inp.T, inp.P, size.id, inp.length, mass_flow=inp.mass_flow,
                                   material=inp.material, fittings=fittings, elevation_change=inp.elevation_change)
        except ValueError:
            continue
        dn.append(size.dn)
        dp.append(r.dp_total)
        v.append(r.velocity)
    return [Chart("sweep", f"Pressure drop and velocity vs size (Sch {inp.schedule})", "Nominal size DN", "",
                  "Pressure drop", "Pa", y2_label="Velocity", y2_unit="m/s", log_y=True, series=[
                      Series("Pressure drop", dn, dp, mode="lines+markers", color=PRIMARY),
                      Series("Velocity", dn, v, mode="lines+markers", axis="y2", dash=True, color=ACCENT),
                      Series(f"Selected DN{inp.dn}", [inp.dn], [res.dp_total], mode="markers", color=ORANGE),
                  ])]


def insulation_charts(inp, res, q_target: float | None = None) -> list[Chart]:
    size = pipes.pipe(inp.dn, inp.schedule)
    t_max = max(0.15, 2.0 * res.thickness)
    thicknesses = np.linspace(0.0, t_max, 31)
    sweep = [insulated_pipe_heat_loss(size.id, size.od, float(t), inp.T_fluid, inp.T_ambient, inp.insulation,
                                      inp.pipe_material, inp.outer_surface, inp.emissivity, inp.wind_speed, _bare=False)
             for t in thicknesses]
    series = [
        Series("Heat loss", thicknesses, [r.heat_loss for r in sweep], color=PRIMARY),
        Series("Surface temperature", thicknesses, [r.T_surface for r in sweep], axis="y2", dash=True, color=ORANGE),
        Series("Selected", [res.thickness], [res.heat_loss], mode="markers", color=RED),
    ]
    if q_target is not None:
        series.append(Series("Target", [0, t_max], [q_target, q_target], dash=True, color=RED))
    return [Chart("insulation", "Heat loss vs insulation thickness", "Insulation thickness", "m",
                  "Heat loss", "W/m", y2_label="Surface temperature", y2_unit="K", log_y=True, series=series)]


def insulation_thickness_charts(inp, res) -> list[Chart]:
    return insulation_charts(inp, res, q_target=inp.q_max)


def refrigeration_cycle_charts(inp, res) -> list[Chart]:
    return _dome_charts(inp.refrigerant, res.states, close=True, title_suffix=f": {inp.refrigerant}")
