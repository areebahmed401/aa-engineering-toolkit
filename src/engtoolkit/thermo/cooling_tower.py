"""
Evaporative cooling tower sizing (SI units, temperatures in K).

Evaporation ≈ 0.00085 × flow × range (°F-based rule restated per K as 0.00153);
drift ≈ 0.2 % of circulation; blowdown = evaporation / (cycles − 1).
Reference: Perry's Chemical Engineers' Handbook; SPX "Cooling Tower Fundamentals".
"""
from __future__ import annotations

from dataclasses import dataclass

from engtoolkit.core.results import Result, rfield

from .psychro import moist_air_state

CP_WATER = 4186.0  # J/(kg·K)


@dataclass
class CoolingTowerResult(Result):
    T_wet_bulb: float = rfield("K", "Wet-bulb temperature")
    T_cold_water: float = rfield("K", "Cold water temperature")
    range: float = rfield("ΔK", "Range")
    approach: float = rfield("ΔK", "Approach")
    water_flow: float = rfield("kg/s", "Circulating water flow")
    effectiveness: float = rfield("", "Effectiveness")
    evaporation: float = rfield("kg/s", "Evaporation loss")
    drift: float = rfield("kg/s", "Drift loss")
    blowdown: float = rfield("kg/s", "Blowdown")
    makeup: float = rfield("kg/s", "Make-up water")


def cooling_tower(heat_load: float, T_hot_water: float, T_dry: float, RH: float, approach: float,
                  cycles_of_concentration: float = 3.0, altitude: float = 0.0,
                  drift_fraction: float = 0.002, cp_water: float = CP_WATER) -> CoolingTowerResult:
    """
    heat_load [W]; T_hot_water and T_dry [K]; RH 0-1; approach [K] above wet bulb.
    """
    if cycles_of_concentration <= 1:
        raise ValueError("Cycles of concentration must be greater than 1")
    T_wb = moist_air_state(T_dry, RH, altitude).T_wet
    T_cold = T_wb + approach
    rng = T_hot_water - T_cold
    if rng <= 0:
        raise ValueError(
            f"Hot water ({T_hot_water - 273.15:.1f} °C) must be above wet bulb + approach ({T_cold - 273.15:.1f} °C)")
    m = heat_load / (cp_water * rng)
    evap = 0.00153 * m * rng  # 0.00085 per °F = 0.00153 per K
    drift = drift_fraction * m
    blow = evap / (cycles_of_concentration - 1)
    return CoolingTowerResult(T_wb, T_cold, rng, approach, m, rng / (rng + approach),
                              evap, drift, blow, evap + drift + blow)
