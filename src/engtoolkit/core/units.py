"""
Units.

Inside the toolkit every number is SI (m, kg, s, K, Pa, W, J). Conversions happen only at the
boundary (user input / display) through ``to_si`` and ``from_si``, backed by pint.
"""
from __future__ import annotations

import math
from functools import lru_cache

import pint

ureg = pint.UnitRegistry()
Q_ = ureg.Quantity


@lru_cache(maxsize=256)
def _si_unit(unit: str) -> str:
    return str(Q_(1, unit).to_base_units().units)


def to_si(value: float, unit: str) -> float:
    """Convert ``value`` in ``unit`` (e.g. 'bar', 'degC', 'mm', 'kJ/kg') to SI."""
    if not unit:
        return value
    return Q_(value, unit).to_base_units().magnitude


def from_si(value: float, unit: str) -> float:
    """Convert an SI ``value`` to ``unit``."""
    if not unit:
        return value
    return Q_(value, _si_unit(unit)).to(unit).magnitude


def convert(value: float, from_unit: str, to_unit: str) -> float:
    return Q_(value, from_unit).to(to_unit).magnitude


# Common display unit sets used by the web app's SI / Imperial toggle
DISPLAY_UNITS = {
    "SI": {"K": "degC", "Pa": "kPa", "m": "m", "kg/s": "kg/s", "J/kg": "kJ/kg", "W": "kW",
           "m^3/s": "m^3/h", "W/m": "W/m", "Pa·s": "mPa·s"},
    "Imperial": {"K": "degF", "Pa": "psi", "m": "ft", "kg/s": "lb/s", "J/kg": "BTU/lb", "W": "BTU/h",
                 "m^3/s": "gal/min", "W/m": "BTU/(h·ft)", "Pa·s": "cP"},
}


# ---- small helpers kept from the original unit_convertors module ----

def c_to_k(celsius: float) -> float:
    return celsius + 273.15


def k_to_c(kelvin: float) -> float:
    return kelvin - 273.15


def bar_to_pa(bar: float) -> float:
    return bar * 1e5


def pa_to_bar(pa: float) -> float:
    return pa / 1e5


def rad_to_deg(rad: float) -> float:
    return math.degrees(rad)


def deg_to_rad(deg: float) -> float:
    return math.radians(deg)
