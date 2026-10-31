"""
Steam tables generated from CoolProp (IAPWS-95 by default, IAPWS-IF97 with ``formulation="IF97"``).

Tables come back as pandas DataFrames in engineering units (°C, kPa, kJ/kg, m³/kg) unless
``units="SI"``. For single states use ``steam_state(T=..., P=...)`` (SI inputs).
"""
from __future__ import annotations

from typing import Iterable

import numpy as np

from engtoolkit.materials import FluidState, fluid


def _water(formulation: str):
    return fluid("IF97::Water" if formulation.upper() == "IF97" else "Water")


def steam_state(formulation: str = "IAPWS95", **inputs) -> FluidState:
    """Water/steam state from any two of T, P, H, S, Q, D, U (SI)."""
    return _water(formulation).state(**inputs)


def _saturated_row(w, given: dict) -> dict:
    liq, vap = w.saturation(**given)
    return {
        "T": liq.T, "P": liq.P,
        "v_f": 1 / liq.rho, "v_g": 1 / vap.rho,
        "u_f": liq.u, "u_g": vap.u,
        "h_f": liq.h, "h_fg": vap.h - liq.h, "h_g": vap.h,
        "s_f": liq.s, "s_fg": vap.s - liq.s, "s_g": vap.s,
    }


_ENG = {"T": ("degC", lambda x: x - 273.15), "P": ("kPa", lambda x: x / 1e3)}
_ENG_ENERGY = lambda x: x / 1e3  # J/kg -> kJ/kg, J/kg.K -> kJ/kg.K


def _to_frame(rows: list[dict], units: str):
    import pandas as pd
    df = pd.DataFrame(rows)
    if units.upper() == "SI":
        return df
    for col in df.columns:
        if col == "T":
            df[col] = df[col] - 273.15
        elif col == "P":
            df[col] = df[col] / 1e3
        elif col[0] in "uhs":
            df[col] = _ENG_ENERGY(df[col])
    return df.rename(columns={"T": "T [°C]", "P": "P [kPa]", "v_f": "v_f [m³/kg]", "v_g": "v_g [m³/kg]",
                              "u_f": "u_f [kJ/kg]", "u_g": "u_g [kJ/kg]", "h_f": "h_f [kJ/kg]",
                              "h_fg": "h_fg [kJ/kg]", "h_g": "h_g [kJ/kg]", "s_f": "s_f [kJ/kg·K]",
                              "s_fg": "s_fg [kJ/kg·K]", "s_g": "s_g [kJ/kg·K]", "v": "v [m³/kg]",
                              "u": "u [kJ/kg]", "h": "h [kJ/kg]", "s": "s [kJ/kg·K]"})


def saturated_table(T: Iterable[float] | None = None, P: Iterable[float] | None = None,
                    units: str = "engineering", formulation: str = "IAPWS95"):
    """Saturated water/steam table by temperature [K] or pressure [Pa]."""
    if (T is None) == (P is None):
        raise ValueError("Give either T or P values")
    w = _water(formulation)
    rows = [_saturated_row(w, {"T": float(t)}) for t in T] if T is not None else \
           [_saturated_row(w, {"P": float(p)}) for p in P]
    return _to_frame(rows, units)


def superheated_table(P: float, T: Iterable[float], units: str = "engineering", formulation: str = "IAPWS95"):
    """Superheated (or compressed) water table at pressure P [Pa] for temperatures T [K]."""
    w = _water(formulation)
    rows = []
    for t in T:
        s = w.state(T=float(t), P=P)
        rows.append({"T": s.T, "P": s.P, "v": 1 / s.rho, "u": s.u, "h": s.h, "s": s.s, "phase": s.phase})
    return _to_frame(rows, units)


def default_temperature_range(n: int = 20) -> np.ndarray:
    """Evenly spaced saturation temperatures from 0.01 °C to 370 °C [K]."""
    return np.linspace(273.16, 643.15, n)
