"""
Insulated pipe heat loss and insulation sizing (per metre of pipe, SI units, temperatures in K).

Series resistances: pipe wall conduction + insulation conduction + outer surface
(convection + radiation). The inner wall is taken at the fluid temperature (conservative).
Insulation conductivity may be a number or a material name; materials are evaluated at the
mean insulation temperature, so ``Mineral wool`` gets its higher k at high temperatures.
Method follows EN ISO 12241 / Incropera ch. 3.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from engtoolkit.core.results import Result, rfield
from engtoolkit.materials import Material, get_material

from .heat_transfer import (
    R_conduction_cylinder, forced_convection_cylinder, h_radiation, natural_convection_horizontal_cylinder,
)


@dataclass
class InsulationResult(Result):
    thickness: float = rfield("m", "Insulation thickness")
    heat_loss: float = rfield("W/m", "Heat loss per metre")
    T_surface: float = rfield("K", "Outer surface temperature")
    h_outer: float = rfield("W/(m²·K)", "Outer heat transfer coefficient")
    k_insulation: float = rfield("W/(m·K)", "Insulation conductivity used")
    R_pipe: float = rfield("m·K/W", "Pipe wall resistance")
    R_insulation: float = rfield("m·K/W", "Insulation resistance")
    R_outer: float = rfield("m·K/W", "Outer surface resistance")
    bare_heat_loss: float = rfield("W/m", "Bare pipe heat loss")


def _k_of(k_ins, T_mean: float) -> float:
    if isinstance(k_ins, (int, float)):
        return float(k_ins)
    return get_material(k_ins).prop("k", T_mean)


def insulated_pipe_heat_loss(
    d_in: float, d_out: float, thickness: float, T_fluid: float, T_ambient: float,
    k_insulation: float | str | Material, pipe_material: str | Material = "Carbon Steel",
    h_outer: float | str = "natural", emissivity: float = 0.9, wind_speed: float = 0.0,
    _bare: bool = True,
) -> InsulationResult:
    """
    Heat loss per metre [W/m] of an insulated pipe.

    h_outer: a fixed coefficient [W/(m²·K)], or "natural" (still air natural convection +
    radiation, iterated on the surface temperature), or "wind" (forced convection at
    ``wind_speed`` + radiation).
    """
    k_pipe = get_material(pipe_material).prop("k", T_fluid)
    r1, r2 = d_in / 2, d_out / 2
    r3 = r2 + thickness
    R_pipe = R_conduction_cylinder(r1, r2, k_pipe)

    T_s = T_ambient + 0.1 * (T_fluid - T_ambient)  # initial guess
    k_ins = h = q = math.nan
    for _ in range(200):
        T_mean_ins = 0.5 * (T_fluid + T_s)
        k_ins = _k_of(k_insulation, T_mean_ins) if thickness > 0 else 1.0
        R_ins = R_conduction_cylinder(r2, r3, k_ins) if thickness > 0 else 0.0
        if isinstance(h_outer, (int, float)):
            h = float(h_outer)
        elif h_outer == "natural":
            h = natural_convection_horizontal_cylinder(T_s, T_ambient, 2 * r3) + h_radiation(emissivity, T_s, T_ambient)
        elif h_outer == "wind":
            h = forced_convection_cylinder(wind_speed, T_s, T_ambient, 2 * r3) + h_radiation(emissivity, T_s, T_ambient)
        else:
            raise ValueError("h_outer must be a number, 'natural' or 'wind'")
        R_out = 1.0 / (max(h, 1e-6) * 2 * math.pi * r3)
        q = (T_fluid - T_ambient) / (R_pipe + R_ins + R_out)
        T_s_new = T_ambient + q * R_out
        if abs(T_s_new - T_s) < 1e-6:
            T_s = T_s_new
            break
        T_s = 0.5 * (T_s + T_s_new)

    bare = math.nan
    if _bare:
        bare = insulated_pipe_heat_loss(d_in, d_out, 0.0, T_fluid, T_ambient, k_insulation, pipe_material,
                                        h_outer, emissivity, wind_speed, _bare=False).heat_loss
    return InsulationResult(thickness=thickness, heat_loss=q, T_surface=T_s, h_outer=h,
                            k_insulation=k_ins if thickness > 0 else math.nan,
                            R_pipe=R_pipe, R_insulation=R_ins, R_outer=R_out,
                            bare_heat_loss=bare if _bare else q)


def insulation_thickness(
    d_in: float, d_out: float, T_fluid: float, T_ambient: float, q_max: float,
    k_insulation: float | str | Material, pipe_material: str | Material = "Carbon Steel",
    h_outer: float | str = "natural", emissivity: float = 0.9, wind_speed: float = 0.0,
    t_max: float = 0.5,
) -> InsulationResult:
    """
    Minimum insulation thickness [m] keeping the heat loss at or below q_max [W/m] (bisection).
    Raises ValueError if even t_max is not enough.
    """
    def run(t):
        return insulated_pipe_heat_loss(d_in, d_out, t, T_fluid, T_ambient, k_insulation, pipe_material,
                                        h_outer, emissivity, wind_speed, _bare=False)

    bare = run(0.0)
    if T_fluid <= T_ambient or bare.heat_loss <= q_max:
        res = insulated_pipe_heat_loss(d_in, d_out, 0.0, T_fluid, T_ambient, k_insulation, pipe_material,
                                       h_outer, emissivity, wind_speed)
        return res
    if run(t_max).heat_loss > q_max:
        raise ValueError(f"Heat loss target {q_max} W/m not reachable with {t_max * 1000:.0f} mm of insulation")
    lo, hi = 0.0, t_max
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if run(mid).heat_loss > q_max:
            lo = mid
        else:
            hi = mid
    return insulated_pipe_heat_loss(d_in, d_out, hi, T_fluid, T_ambient, k_insulation, pipe_material,
                                    h_outer, emissivity, wind_speed)


def heat_loss_vs_thickness(d_in: float, d_out: float, T_fluid: float, T_ambient: float,
                           k_insulation, thicknesses, **kwargs) -> list[InsulationResult]:
    """Heat loss for a range of thicknesses (for diminishing-returns plots)."""
    return [insulated_pipe_heat_loss(d_in, d_out, t, T_fluid, T_ambient, k_insulation, _bare=False, **kwargs)
            for t in thicknesses]
