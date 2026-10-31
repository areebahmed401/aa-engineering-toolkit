"""Moist air properties (ASHRAE Fundamentals via PsychroLib). SI units, temperatures in K."""
from __future__ import annotations

from dataclasses import dataclass

from engtoolkit.core.results import Result, rfield

from ._vendor import psychrolib  # vendored: PsychroLib ships no wheel, which the browser build needs

psychrolib.SetUnitSystem(psychrolib.SI)


def atmospheric_pressure(altitude: float) -> float:
    """Standard atmospheric pressure [Pa] at an altitude [m] (ASHRAE Fundamentals eq. 3)."""
    return psychrolib.GetStandardAtmPressure(altitude)


@dataclass
class MoistAirState(Result):
    T_dry: float = rfield("K", "Dry-bulb temperature")
    T_wet: float = rfield("K", "Wet-bulb temperature")
    T_dew: float = rfield("K", "Dew-point temperature")
    RH: float = rfield("", "Relative humidity (0-1)")
    humidity_ratio: float = rfield("kg/kg", "Humidity ratio")
    enthalpy: float = rfield("J/kg", "Moist air enthalpy (per kg dry air)")
    specific_volume: float = rfield("m^3/kg", "Specific volume (per kg dry air)")
    P_atm: float = rfield("Pa", "Atmospheric pressure")
    P_vapour: float = rfield("Pa", "Vapour partial pressure")


def moist_air_state(T_dry: float, RH: float, altitude: float = 0.0, P_atm: float | None = None) -> MoistAirState:
    """State from dry-bulb temperature [K] and relative humidity [0-1]."""
    if not 0 <= RH <= 1:
        raise ValueError("RH must be between 0 and 1")
    P = P_atm if P_atm is not None else atmospheric_pressure(altitude)
    t = T_dry - 273.15
    W = psychrolib.GetHumRatioFromRelHum(t, RH, P)
    return MoistAirState(
        T_dry=T_dry,
        T_wet=psychrolib.GetTWetBulbFromRelHum(t, RH, P) + 273.15,
        T_dew=psychrolib.GetTDewPointFromRelHum(t, RH) + 273.15 if RH > 0 else float("nan"),
        RH=RH, humidity_ratio=W,
        enthalpy=psychrolib.GetMoistAirEnthalpy(t, W),
        specific_volume=psychrolib.GetMoistAirVolume(t, W, P),
        P_atm=P, P_vapour=psychrolib.GetVapPresFromRelHum(t, RH),
    )
