"""Thermo figures. Every function returns a matplotlib Figure (no plt.show())."""
from __future__ import annotations

import numpy as np

from engtoolkit.core.plotting import new_figure, styled
from engtoolkit.materials import WATER, fluid


def ph_ts_diagram(fluid_name: str = WATER, states=None, close: bool = False, n: int = 200):
    """
    Saturation dome on p-h and T-s axes, with optional state points (objects with T, P, h, s)
    connected in order (``close=True`` joins the last back to the first, e.g. for a cycle).
    """

    f = fluid(fluid_name)
    T = np.linspace(max(f.T_triple, f.T_min) + 0.5, f.T_critical - 0.5, n)
    liq = [f.state(T=t, Q=0) for t in T]
    vap = [f.state(T=t, Q=1) for t in T]

    with styled():
        fig, (ax_ph, ax_ts) = new_figure(1, 2, figsize=(12, 4.8))
        ax_ph.semilogy([s.h / 1e3 for s in liq], [s.P / 1e3 for s in liq], label="Saturated liquid")
        ax_ph.semilogy([s.h / 1e3 for s in vap], [s.P / 1e3 for s in vap], label="Saturated vapour")
        ax_ts.plot([s.s / 1e3 for s in liq], T - 273.15, label="Saturated liquid")
        ax_ts.plot([s.s / 1e3 for s in vap], T - 273.15, label="Saturated vapour")
        if states:
            pts = list(states) + ([states[0]] if close else [])
            ax_ph.plot([p.h / 1e3 for p in pts], [p.P / 1e3 for p in pts], "o-", color="#C8632B", label="Process")
            ax_ts.plot([p.s / 1e3 for p in pts], [p.T - 273.15 for p in pts], "o-", color="#C8632B", label="Process")
            for i, p in enumerate(states):
                tag = getattr(p, "label", "") or str(i + 1)
                ax_ph.annotate(tag, (p.h / 1e3, p.P / 1e3), textcoords="offset points", xytext=(5, 5))
                ax_ts.annotate(tag, (p.s / 1e3, p.T - 273.15), textcoords="offset points", xytext=(5, 5))
        ax_ph.set(xlabel="Enthalpy [kJ/kg]", ylabel="Pressure [kPa]", title=f"p-h diagram: {fluid_name}")
        ax_ts.set(xlabel="Entropy [kJ/(kg·K)]", ylabel="Temperature [°C]", title=f"T-s diagram: {fluid_name}")
        ax_ph.legend()
        ax_ts.legend()
    return fig


def pipe_size_sweep_plot(rows, title: str = ""):
    """Pressure drop, velocity and cost vs DN from ``pipe_size_sweep`` rows."""

    dn = [str(r.dn) for r in rows]
    with styled():
        fig, ax1 = new_figure(figsize=(11, 5))
        ax1.plot(dn, [r.dp_total / 1e3 for r in rows], "o-", color="#E0A800", label="Pressure drop")
        ax1.set(xlabel="Pipe size DN", ylabel="Pressure drop [kPa]")
        ax2 = ax1.twinx()
        ax2.plot(dn, [r.velocity for r in rows], "s--", color="#2B2D31", label="Velocity")
        ax2.set_ylabel("Velocity [m/s]")
        ax2.grid(False)
        ax3 = ax1.twinx()
        ax3.spines["right"].set_position(("outward", 60))
        ax3.spines["right"].set_visible(True)
        ax3.plot(dn, [r.cost for r in rows], "d-.", color="#C8632B", label="Cost")
        ax3.set_ylabel("Pipe cost [USD]")
        ax3.grid(False)
        lines = ax1.get_lines() + ax2.get_lines() + ax3.get_lines()
        ax1.legend(lines, [l.get_label() for l in lines], loc="upper center")
        ax1.set_title(title or "Pressure drop, velocity and cost vs pipe size")
    return fig


def insulation_plot(results, q_target: float | None = None):
    """Heat loss and surface temperature vs insulation thickness."""

    t = [r.thickness * 1000 for r in results]
    with styled():
        fig, ax1 = new_figure(figsize=(9, 4.5))
        ax1.plot(t, [r.heat_loss for r in results], color="#E0A800", label="Heat loss")
        if q_target is not None:
            ax1.axhline(q_target, color="#DC2626", ls="--", label="Target")
        ax1.set(xlabel="Insulation thickness [mm]", ylabel="Heat loss [W/m]")
        ax2 = ax1.twinx()
        ax2.plot(t, [r.T_surface - 273.15 for r in results], color="#C8632B", label="Surface temperature")
        ax2.set_ylabel("Surface temperature [°C]")
        ax2.grid(False)
        lines = ax1.get_lines() + ax2.get_lines()
        ax1.legend(lines, [l.get_label() for l in lines])
    return fig
