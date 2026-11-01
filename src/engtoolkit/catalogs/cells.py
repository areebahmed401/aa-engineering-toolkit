"""
Battery cells: capacity, voltages, geometry, open-circuit voltage, equivalent-circuit and thermal
parameters, and which aging correlation applies. Data in ``data/cells.yaml`` (each cell has a source).

    from engtoolkit.catalogs import get_cell, list_cells
    cell = get_cell("LG M50 21700 (NMC811)")
    cell.ocv_at(0.5), cell.energy_Wh, cell.surface_area

Units: SI except capacity in A·h (and energy in W·h), the convention for batteries.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml

DATA = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class Cell:
    name: str
    chemistry: str
    format: str                 # "cylindrical", "pouch" or "prismatic"
    capacity_Ah: float          # nominal capacity [A·h]
    V_nominal: float            # [V]
    V_max: float                # charge cut-off [V]
    V_min: float                # discharge cut-off [V]
    mass: float                 # [kg]
    cp: float                   # specific heat [J/(kg·K)]
    dimensions: tuple[float, ...]  # cylindrical: (diameter, height); pouch/prismatic: (length, width, thickness) [m]
    soc: tuple[float, ...]      # SOC grid for the tables below (0-1)
    ocv: tuple[float, ...]      # open-circuit voltage [V]
    dUdT: tuple[float, ...]     # entropic coefficient [V/K]
    R0: float                   # series resistance at T_ref [ohm]
    R1: float                   # first RC pair [ohm]
    tau1: float                 # first RC time constant [s]
    R2: float                   # second RC pair [ohm]
    tau2: float                 # second RC time constant [s]
    Ea_R: float                 # Arrhenius activation energy of the resistances [J/mol]
    T_ref: float                # temperature the resistances refer to [K]
    max_discharge_C: float      # continuous discharge rating [1/h]
    max_charge_C: float
    aging_model: str            # key of a correlation in engtoolkit.electrical.battery.aging
    source: str

    # ----- derived -----
    @property
    def C1(self) -> float:
        return self.tau1 / self.R1

    @property
    def C2(self) -> float:
        return self.tau2 / self.R2 if self.R2 > 0 else math.inf

    @property
    def energy_Wh(self) -> float:
        return self.capacity_Ah * self.V_nominal

    @property
    def specific_energy(self) -> float:
        """[W·h/kg]"""
        return self.energy_Wh / self.mass

    @property
    def surface_area(self) -> float:
        """External surface area [m²]."""
        if self.format == "cylindrical":
            d, h = self.dimensions
            return math.pi * d * h + 2 * math.pi * d**2 / 4
        a, b, c = self.dimensions
        return 2 * (a * b + a * c + b * c)

    @property
    def volume(self) -> float:
        """[m³]"""
        if self.format == "cylindrical":
            d, h = self.dimensions
            return math.pi * d**2 / 4 * h
        a, b, c = self.dimensions
        return a * b * c

    @property
    def characteristic_length(self) -> float:
        """Diameter (cylinders) or height of the largest face (pouch/prismatic) for convection [m]."""
        return self.dimensions[0] if self.format == "cylindrical" else self.dimensions[1]

    def ocv_at(self, soc):
        return np.interp(soc, self.soc, self.ocv)

    def dUdT_at(self, soc):
        return np.interp(soc, self.soc, self.dUdT)

    def soc_at_ocv(self, voltage):
        return np.interp(voltage, self.ocv, self.soc)


@lru_cache(maxsize=1)
def _cells() -> dict[str, Cell]:
    with open(DATA / "cells.yaml", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    out = {}
    for c in raw["cells"]:
        table = np.array(c.pop("ocv_table"), dtype=float)  # rows: SOC, OCV, dU/dT [mV/K]
        dims = tuple(float(v) / 1000 for v in c.pop("dimensions_mm"))
        ecm = c.pop("ecm")
        cell = Cell(
            name=c["name"], chemistry=c["chemistry"], format=c["format"], capacity_Ah=float(c["capacity_Ah"]),
            V_nominal=float(c["V_nominal"]), V_max=float(c["V_max"]), V_min=float(c["V_min"]),
            mass=float(c["mass_g"]) / 1000, cp=float(c["cp"]), dimensions=dims,
            soc=tuple(table[:, 0]), ocv=tuple(table[:, 1]), dUdT=tuple(table[:, 2] / 1000),
            R0=float(ecm["R0_mohm"]) / 1000, R1=float(ecm["R1_mohm"]) / 1000, tau1=float(ecm["tau1_s"]),
            R2=float(ecm["R2_mohm"]) / 1000, tau2=float(ecm["tau2_s"]), Ea_R=float(ecm["Ea_kJ_mol"]) * 1000,
            T_ref=float(ecm["T_ref"]), max_discharge_C=float(c["max_discharge_C"]),
            max_charge_C=float(c["max_charge_C"]), aging_model=c["aging_model"], source=c["source"],
        )
        out[cell.name] = cell
    return out


def list_cells() -> list[str]:
    return list(_cells())


def get_cell(name: str) -> Cell:
    try:
        return _cells()[name]
    except KeyError:
        raise KeyError(f"Unknown cell {name!r}. Available: {list_cells()}") from None
