"""Electrical (battery) tools registered for the notebooks and the web app (inputs in SI units)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
from pydantic import BaseModel, field_validator

from engtoolkit.catalogs.cells import get_cell, list_cells
from engtoolkit.core.charts import Chart, Series
from engtoolkit.core.registry import Input, register_tool
from engtoolkit.core.results import Result, rfield

from . import charts as _charts
from .battery import reference
from .battery.aging import MODELS as AGING_MODELS, cycle_aging
from .battery.ecm import ECMParams, simulate
from .battery.thermal import COOLING_LABELS, WATER_GLYCOL, Cooling, ThermalModel

CellName = Literal[tuple(list_cells())]  # type: ignore[valid-type]
DEFAULT_CELL = "LG M50 21700 (NMC811)"
CoolingKind = Literal["natural_air", "forced_air", "liquid_cold_plate", "adiabatic", "fixed_h"]
Coolant = Literal["INCOMP::MEG[0.3]", "INCOMP::MPG[0.3]", "IF97::Water"]  # fast in the browser
Mode = Literal["discharge_cc", "discharge_cp", "drive_cycle", "charge_cccv"]
MODE_LABELS = {"discharge_cc": "CC discharge", "discharge_cp": "CP discharge", "drive_cycle": "drive cycle",
               "charge_cccv": "CC-CV charge"}

ECM_REFERENCE = ("Plett, Battery Management Systems Vol. 1 (2015) ch. 2; analytical RC step response, "
                 "Coulomb counting and energy balance; Bernardi et al. (1985) heat generation")
AGING_REFERENCE = ("Wang et al. (2011) J. Power Sources 196, 3942 (LFP); Schmalstieg et al. (2014) "
                   "J. Power Sources 257, 325 (NMC)")


def parse_rates(text: str, limit: int = 5) -> list[float]:
    try:
        rates = [float(v) for v in text.replace(";", ",").split(",") if v.strip()]
    except ValueError:
        raise ValueError("Enter numbers separated by commas, e.g. 0.5, 1, 2") from None
    if not rates or len(rates) > limit:
        raise ValueError(f"Enter 1 to {limit} values")
    if any(not 0 < r <= 20 for r in rates):
        raise ValueError("Each value must be between 0 and 20")
    return rates


def _fmt_rate(c: float) -> str:
    return f"{c:g}C"


# ---------------- shared inputs ----------------

class _CoolingInputs(BaseModel):
    cooling: CoolingKind = Input("natural_air", "", "Cooling",
                                 "Natural air, forced air, liquid cold plate (water-glycol), adiabatic, or a fixed h")
    T_ambient: float = Input(298.15, "K", "Ambient air temperature", gt=200, lt=400)
    T_coolant: float = Input(298.15, "K", "Coolant / cooling-air temperature", gt=250, lt=400)
    air_velocity: float = Input(3.0, "m/s", "Air velocity (forced air)", gt=0, le=50)
    coolant: Coolant = Input(WATER_GLYCOL, "", "Liquid coolant (cold plate)")
    coolant_velocity: float = Input(0.5, "m/s", "Coolant velocity in the channel", gt=0, le=10)
    cooled_fraction: float = Input(0.25, "", "Share of cell surface on the cold plate", gt=0, le=1)
    h_fixed: float = Input(10.0, "W/(m²·K)", "Heat transfer coefficient (fixed h)", gt=0)

    def cooling_spec(self, kind: str | None = None) -> Cooling:
        return Cooling(kind or self.cooling, T_ambient=self.T_ambient, T_coolant=self.T_coolant,
                       air_velocity=self.air_velocity, coolant=self.coolant, coolant_velocity=self.coolant_velocity,
                       cooled_fraction=self.cooled_fraction, h_fixed=self.h_fixed)

    @property
    def T_start(self) -> float:
        return self.T_coolant if self.cooling in ("forced_air", "liquid_cold_plate", "fixed_h") else self.T_ambient


def _run(cell, params, mode: str, rate: float, cooling: Cooling, T0: float, soc0: float | None = None):
    power = rate * cell.energy_Wh  # constant power: rate is an E-rate (power / nominal energy)
    return simulate(params, mode, c_rate=rate, power=power, soc0=soc0, T0=T0,
                    thermal=ThermalModel.for_cell(cell, cooling))


def _cycle_temperature(dis, chg) -> float:
    """Time-averaged cell temperature over one discharge + CC-CV charge."""
    return float((np.trapezoid(dis.temperature, dis.t) + np.trapezoid(chg.temperature, chg.t)) / (dis.t[-1] + chg.t[-1]))


def _mean_ocv(cell, dod: float) -> float:
    return float(np.mean(cell.ocv_at(np.linspace(1.0 - dod, 1.0, 50))))


def _aging_curves(cell, params, rates, rate_charge, cooling, T0, n_cycles, dod=1.0, use_thermal=True,
                  discharges: dict | None = None):
    """Aging curve per discharge rate; cell temperature from simulated discharge + charge (reused if given)."""
    cycles = np.linspace(0, n_cycles, 101)
    chg = _run(cell, params, "charge_cccv", rate_charge, cooling, T0) if use_thermal else None
    out = []
    for r in rates:
        if use_thermal:
            dis = (discharges or {}).get(r) or _run(cell, params, "discharge_cc", r, cooling, T0)
            T = _cycle_temperature(dis, chg)
        else:
            T = T0
        curve = cycle_aging(cell.aging_model, cycles, c_rate=r, T=T, dod=dod, V_mean=_mean_ocv(cell, dod),
                            c_rate_charge=rate_charge)
        out.append({"label": _fmt_rate(r), "curve": curve, "T_cycle": T, "rate": r})
    return out


# ---------------- battery simulator (main tool, dedicated web page) ----------------

class BatterySimulatorInputs(_CoolingInputs):
    cell: CellName = Input(DEFAULT_CELL, "", "Cell")
    mode: Mode = Input("discharge_cc", "", "Profile",
                       "Constant current, constant power (rate = power / nominal energy), synthetic drive cycle "
                       "(rate = peak C-rate) or CC-CV charge")
    c_rates: str = Input("0.5, 1, 2", "", "C-rates to compare", "Comma-separated, up to 5 (E-rates for constant power)")
    n_rc: Literal[1, 2] = Input(2, "", "RC pairs in the equivalent circuit")
    soc_initial: float = Input(1.0, "", "Initial SOC (discharge profiles)", ge=0.05, le=1)
    n_series: int = Input(1, "", "Cells in series (pack)", ge=1, le=1000)
    n_parallel: int = Input(1, "", "Cells in parallel (pack)", ge=1, le=100)
    compare_pybamm: bool = Input(True, "", "Overlay PyBaMM DFN reference (LG M50, CC discharge)")
    aging_cycles: int = Input(1000, "", "Cycles for the degradation chart (0 = off)", ge=0, le=10000)
    c_rate_charge: float = Input(0.5, "", "Charge C-rate in the aging cycles", gt=0, le=5)

    @field_validator("c_rates")
    @classmethod
    def _rates(cls, v: str) -> str:
        parse_rates(v)
        return v


@dataclass
class BatterySimResult(Result):
    cell: str = rfield("", "Cell", default="")
    stop_reason: str = rfield("", "Stopped by (first rate)", default="")
    capacity: float = rfield("Ah", "Charge delivered (first rate)", default=math.nan)
    energy: float = rfield("Wh", "Energy delivered (first rate)", default=math.nan)
    duration: float = rfield("s", "Duration (first rate)", default=math.nan)
    T_max: float = rfield("K", "Max cell temperature (all rates)", default=math.nan)
    dT_max: float = rfield("ΔK", "Max temperature rise (all rates)", default=math.nan)
    heat_total: float = rfield("J", "Heat generated per cell (first rate)", default=math.nan)
    h_mean: float = rfield("W/(m²·K)", "Mean heat transfer coefficient", default=math.nan)
    cycles_to_80: float = rfield("", "Cycles to 80 % capacity (first rate)", default=math.nan)
    pack_voltage: float = rfield("V", "Pack nominal voltage", default=math.nan)
    pack_capacity: float = rfield("Ah", "Pack capacity", default=math.nan)
    pack_energy: float = rfield("Wh", "Pack nominal energy", default=math.nan)
    pack_mass: float = rfield("kg", "Pack cell mass", default=math.nan)
    columns: list = rfield("", "Columns", default_factory=list, summary=False)
    rows: list = rfield("", "Rows", default_factory=list, summary=False)


def _with_charts(result: Result, charts: list) -> Result:
    """Keep the chart specs built during the calculation on the result (not a dataclass field, so not serialised)."""
    result.chart_specs = charts
    return result


def _stored_charts(inp, result) -> list:
    return getattr(result, "chart_specs", [])


@register_tool("electrical.battery_simulator", "Battery cell simulator", BatterySimulatorInputs,
               description="Equivalent-circuit (1RC/2RC) cell model coupled to a lumped thermal model with "
                           "air or liquid cooling: voltage, SOC, temperature and heat for several C-rates, "
                           "capacity fade over cycles, and PyBaMM reference curves.",
               reference=ECM_REFERENCE + "; PyBaMM DFN (Chen et al. 2020) for the reference curves",
               tags=("battery", "ECM", "thermal", "aging", "PyBaMM"), custom_page=True,
               charts=_stored_charts)
def battery_simulator_tool(inp: BatterySimulatorInputs) -> BatterySimResult:
    cell = get_cell(inp.cell)
    params = ECMParams.from_cell(cell, inp.n_rc)
    cooling = inp.cooling_spec()
    rates = parse_rates(inp.c_rates)
    T0 = inp.T_start
    soc0 = None if inp.mode == "charge_cccv" else inp.soc_initial
    runs, refs = [], []
    use_ref = inp.compare_pybamm and inp.mode == "discharge_cc" and cell.name == reference.cell()
    for r in rates:
        sim = _run(cell, params, inp.mode, r, cooling, T0, soc0)
        runs.append({"label": _fmt_rate(r), "sim": sim})
        refs.append(reference.discharge(r, inp.T_ambient) if use_ref else None)

    aging, aging_refs = None, None
    if inp.aging_cycles > 0:
        reuse = {r: run["sim"] for r, run in zip(rates, runs)} if inp.mode == "discharge_cc" and soc0 == 1.0 else None
        aging = _aging_curves(cell, params, rates, inp.c_rate_charge, cooling, T0, inp.aging_cycles, discharges=reuse)
        aging_refs = [reference.aging(r, inp.T_ambient) if use_ref and abs(inp.c_rate_charge - 0.5) < 1e-9
                      else None for r in rates]

    rows = []
    for i, run in enumerate(runs):
        s = run["sim"]
        rows.append([rates[i], round(abs(s.capacity_Ah), 4), round(abs(s.energy_Wh), 3), round(s.t[-1] / 60, 2),
                     round(float(s.temperature.max()) - 273.15, 2), round(float(s.temperature.max() - T0), 2),
                     round(float(np.mean(s.heat)), 4),
                     round(aging[i]["curve"].cycles_to(0.8), 0) if aging else None, s.stop_reason])
    first = runs[0]["sim"]
    n_cells = inp.n_series * inp.n_parallel
    result = BatterySimResult(
        cell=cell.name, stop_reason=first.stop_reason, capacity=abs(first.capacity_Ah), energy=abs(first.energy_Wh),
        duration=float(first.t[-1]), T_max=max(float(r["sim"].temperature.max()) for r in runs),
        dT_max=max(float(r["sim"].temperature.max()) - T0 for r in runs),
        heat_total=float(np.trapezoid(first.heat, first.t)), h_mean=float(np.nanmean(first.h)),
        cycles_to_80=aging[0]["curve"].cycles_to(0.8) if aging else math.nan,
        pack_voltage=inp.n_series * cell.V_nominal, pack_capacity=inp.n_parallel * cell.capacity_Ah,
        pack_energy=n_cells * cell.energy_Wh, pack_mass=n_cells * cell.mass,
        columns=["Rate [1/h]", "Charge [Ah]", "Energy [Wh]", "Duration [min]", "T max [°C]", "ΔT [K]",
                 "Mean heat [W/cell]", "Cycles to 80 %", "Stopped by"],
        rows=rows,
    )
    similar_cooling = inp.cooling == "natural_air" or (inp.cooling == "fixed_h" and abs(inp.h_fixed - 10.0) < 5)
    return _with_charts(result, _charts.discharge_charts(runs, refs, aging, aging_refs,
                                                         x_capacity=inp.mode != "drive_cycle",
                                                         reference_temperature=similar_cooling))


# ---------------- cooling comparison ----------------

class CoolingComparisonInputs(_CoolingInputs):
    cell: CellName = Input(DEFAULT_CELL, "", "Cell")
    c_rate: float = Input(1.5, "", "Discharge C-rate", gt=0, le=20)


@dataclass
class CoolingComparisonResult(Result):
    best: str = rfield("", "Lowest peak temperature", default="")
    T_max_natural: float = rfield("K", "Max temperature, natural air", default=math.nan)
    T_max_forced: float = rfield("K", "Max temperature, forced air", default=math.nan)
    T_max_liquid: float = rfield("K", "Max temperature, cold plate", default=math.nan)
    T_max_adiabatic: float = rfield("K", "Max temperature, adiabatic", default=math.nan)
    h_forced: float = rfield("W/(m²·K)", "h forced air (Churchill-Bernstein / flat plate)", default=math.nan)
    h_channel: float = rfield("W/(m²·K)", "h coolant channel (Gnielinski / laminar)", default=math.nan)
    Re_channel: float = rfield("", "Coolant channel Reynolds number", default=math.nan)
    columns: list = rfield("", "Columns", default_factory=list, summary=False)
    rows: list = rfield("", "Rows", default_factory=list, summary=False)


COMPARED = ("natural_air", "forced_air", "liquid_cold_plate", "adiabatic")


@register_tool("electrical.cooling_comparison", "Battery cooling comparison", CoolingComparisonInputs,
               description="Same discharge with natural air, forced air, a water-glycol cold plate and no cooling: "
                           "peak temperature, heat transfer coefficients and heat removed.",
               reference="Incropera (Churchill-Chu, Churchill-Bernstein, flat plate, Gnielinski); "
                         "steady-state and energy balance of the lumped model",
               tags=("battery", "thermal", "cooling"), charts=_stored_charts)
def cooling_comparison_tool(inp: CoolingComparisonInputs) -> CoolingComparisonResult:
    cell = get_cell(inp.cell)
    params = ECMParams.from_cell(cell)
    runs, rows, res = [], [], {}
    for kind in COMPARED:
        cooling = inp.cooling_spec(kind)
        T0 = inp.T_coolant if kind in ("forced_air", "liquid_cold_plate") else inp.T_ambient
        thermal = ThermalModel.for_cell(cell, cooling)
        sim = simulate(params, "discharge_cc", c_rate=inp.c_rate, T0=T0, thermal=thermal)
        runs.append({"label": COOLING_LABELS[kind], "sim": sim})
        res[kind] = (float(sim.temperature.max()), thermal.info)
        rows.append([COOLING_LABELS[kind], round(float(np.nanmean(sim.h)), 2),
                     round(float(sim.temperature.max()) - 273.15, 2), round(float(sim.temperature.max() - T0), 2),
                     round(float(np.trapezoid(sim.heat, sim.t)) / 1e3, 3),
                     round(float(np.trapezoid(sim.heat_removed, sim.t)) / 1e3, 3), round(abs(sim.energy_Wh), 3)])
    charts = _charts.discharge_charts(runs, [None] * len(runs))
    best = min(COMPARED, key=lambda k: res[k][0])
    result = CoolingComparisonResult(
        best=COOLING_LABELS[best], T_max_natural=res["natural_air"][0], T_max_forced=res["forced_air"][0],
        T_max_liquid=res["liquid_cold_plate"][0], T_max_adiabatic=res["adiabatic"][0],
        h_forced=res["forced_air"][1].get("h_forced", math.nan),
        h_channel=res["liquid_cold_plate"][1].get("h_channel", math.nan),
        Re_channel=res["liquid_cold_plate"][1].get("Re_channel", math.nan),
        columns=["Cooling", "Mean h [W/(m²·K)]", "T max [°C]", "ΔT [K]", "Heat generated [kJ]", "Heat removed [kJ]",
                 "Energy [Wh]"],
        rows=rows,
    )
    return _with_charts(result, [charts[1], charts[3], charts[0]])


# ---------------- cycle life ----------------

class CycleLifeInputs(_CoolingInputs):
    cell: CellName = Input(DEFAULT_CELL, "", "Cell")
    c_rates: str = Input("0.5, 1, 2", "", "Discharge C-rates to compare", "Comma-separated, up to 5")
    c_rate_charge: float = Input(0.5, "", "Charge C-rate", gt=0, le=5)
    dod: float = Input(1.0, "", "Depth of discharge (0-1)", gt=0, le=1)
    n_cycles: int = Input(2000, "", "Cycles", ge=10, le=20000)
    use_thermal: bool = Input(True, "", "Cell temperature from the thermal model (else ambient)")

    @field_validator("c_rates")
    @classmethod
    def _rates(cls, v: str) -> str:
        parse_rates(v)
        return v


@dataclass
class CycleLifeResult(Result):
    model: str = rfield("", "Aging correlation", default="")
    cycles_to_80: float = rfield("", "Cycles to 80 % capacity (first rate)", default=math.nan)
    capacity_end: float = rfield("", "Relative capacity at the last cycle (first rate)", default=math.nan)
    resistance_end: float = rfield("", "Relative resistance at the last cycle (first rate)", default=math.nan)
    T_cycle: float = rfield("K", "Mean cell temperature while cycling (first rate)", default=math.nan)
    columns: list = rfield("", "Columns", default_factory=list, summary=False)
    rows: list = rfield("", "Rows", default_factory=list, summary=False)


@register_tool("electrical.cycle_life", "Battery cycle life", CycleLifeInputs,
               description="Capacity fade and resistance growth over cycles at several C-rates, with the cell "
                           "temperature from the electro-thermal model (semi-empirical correlations).",
               reference=AGING_REFERENCE, tags=("battery", "aging", "degradation"),
               charts=_stored_charts)
def cycle_life_tool(inp: CycleLifeInputs) -> CycleLifeResult:
    cell = get_cell(inp.cell)
    params = ECMParams.from_cell(cell)
    rates = parse_rates(inp.c_rates)
    aging = _aging_curves(cell, params, rates, inp.c_rate_charge, inp.cooling_spec(), inp.T_start, inp.n_cycles,
                          inp.dod, inp.use_thermal)
    rows = [[a["rate"], round(a["T_cycle"] - 273.15, 2), round(a["curve"].cycles_to(0.8), 0),
             round(float(a["curve"].capacity[-1]), 4),
             None if math.isnan(a["curve"].resistance[-1]) else round(float(a["curve"].resistance[-1]), 4)]
            for a in aging]
    charts = [_charts.aging_chart(aging)]
    if not np.all(np.isnan(aging[0]["curve"].resistance)):
        charts.append(_charts.resistance_chart(aging))
    a0 = aging[0]
    result = CycleLifeResult(
        model=AGING_MODELS[cell.aging_model], cycles_to_80=a0["curve"].cycles_to(0.8),
        capacity_end=float(a0["curve"].capacity[-1]), resistance_end=float(a0["curve"].resistance[-1]),
        T_cycle=a0["T_cycle"],
        columns=["C-rate", "Mean T [°C]", "Cycles to 80 %", f"C/C0 at {inp.n_cycles}", f"R/R0 at {inp.n_cycles}"],
        rows=rows,
    )
    return _with_charts(result, charts)


# ---------------- PyBaMM reference viewer ----------------

class PybammReferenceInputs(BaseModel):
    T_ambient: float = Input(298.15, "K", "Ambient temperature (nearest in the grid: 10, 25, 40 °C)", gt=200, lt=400)
    compare_ecm: bool = Input(True, "", "Overlay the equivalent-circuit model (same h)")
    n_rc: Literal[1, 2] = Input(2, "", "RC pairs in the equivalent circuit")


@dataclass
class PybammReferenceResult(Result):
    cell: str = rfield("", "Cell", default="")
    model: str = rfield("", "PyBaMM discharge model", default="")
    aging_model: str = rfield("", "PyBaMM degradation model", default="")
    T_grid: float = rfield("K", "Grid temperature used", default=math.nan)
    h: float = rfield("W/(m²·K)", "Heat transfer coefficient", default=math.nan)
    max_capacity_error: float = rfield("", "Max ECM vs DFN capacity difference (fraction)", default=math.nan)
    columns: list = rfield("", "Columns", default_factory=list, summary=False)
    rows: list = rfield("", "Rows", default_factory=list, summary=False)


@register_tool("electrical.pybamm_reference", "PyBaMM reference curves", PybammReferenceInputs,
               description="Precomputed PyBaMM results for the LG M50 cell (DFN discharge with lumped thermal; "
                           "SEI growth and lithium plating over cycles) next to the equivalent-circuit model.",
               reference="PyBaMM (Sulzer et al. 2021); Chen et al. (2020) and O'Kane et al. (2022) parameter sets",
               tags=("battery", "PyBaMM", "DFN", "degradation"), charts=_stored_charts)
def pybamm_reference_tool(inp: PybammReferenceInputs) -> PybammReferenceResult:
    data = reference.load()
    meta = data["meta"]
    T = reference.nearest_temperature(inp.T_ambient)
    cell = get_cell(meta["cell"])
    params = ECMParams.from_cell(cell, inp.n_rc)
    cooling = Cooling("fixed_h", T_ambient=T, T_coolant=T, h_fixed=meta["h"])
    runs, refs, rows, errors = [], [], [], []
    for r in reference.c_rates():
        ref = reference.discharge(r, T)
        sim = simulate(params, "discharge_cc", c_rate=r, T0=T, thermal=ThermalModel.for_cell(cell, cooling))
        q_ref = ref["capacity_Ah"][-1]
        errors.append(abs(abs(sim.capacity_Ah) - q_ref) / q_ref)
        if inp.compare_ecm:
            runs.append({"label": _fmt_rate(r), "sim": sim})
            refs.append(ref)
        aging = reference.aging(r, T)
        rows.append([r, round(q_ref, 4), round(abs(sim.capacity_Ah), 4), round(ref["temperature"][-1] - 273.15, 2),
                     round(float(sim.temperature[-1]) - 273.15, 2), aging["cycles"][-1] if aging else None,
                     round(aging["capacity"][-1], 5) if aging else None])
    if inp.compare_ecm:
        charts = _charts.discharge_charts(runs, refs)[:2]
        for c in charts:  # ECM drawn solid, PyBaMM dashed: name the solid ones
            for s in c.series:
                if not s.name.startswith("PyBaMM"):
                    s.name = f"ECM {s.name}"
    else:
        charts = []
    aging_runs = [a for a in (reference.aging(r, T) for r in reference.c_rates()) if a]
    fade = Chart("pybamm_fade", "PyBaMM capacity fade (SEI + lithium plating)", "Cycle", "",
                         "Relative capacity", "")
    lli = Chart("pybamm_lli", "Loss of lithium inventory", "Cycle", "", "LLI", "%")
    for i, a in enumerate(aging_runs):
        fade.series.append(Series(_fmt_rate(a["c_rate"]), a["cycles"], a["capacity"], color=_charts.color(i)))
        lli.series.append(Series(_fmt_rate(a["c_rate"]), a["cycles"], a["lli"], color=_charts.color(i)))
    charts += [fade, lli]
    result = PybammReferenceResult(
        cell=cell.name, model=meta["discharge_model"], aging_model=meta["aging_model"], T_grid=T, h=meta["h"],
        max_capacity_error=max(errors),
        columns=["C-rate", "DFN charge [Ah]", "ECM charge [Ah]", "DFN T end [°C]", "ECM T end [°C]", "Cycles",
                 "DFN C/C0 at end"],
        rows=rows,
    )
    return _with_charts(result, charts)
