"""Thermo tools registered for the notebooks and the web app (inputs in SI units)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, model_validator

from engtoolkit.catalogs import pipes
from engtoolkit.core.registry import Input, register_tool
from engtoolkit.core.results import Result, rfield
from engtoolkit.materials import FluidState, fluid

from .cooling_tower import CoolingTowerResult, cooling_tower
from .cycles import RefrigerationCycleResult, refrigeration_cycle
from .insulation import InsulationResult, insulated_pipe_heat_loss, insulation_thickness
from .pipe_flow import FITTING_FIELDS, PipeDropResult, pipe_pressure_drop
from .steam_tables import saturated_table

DN_CHOICES = tuple(p.dn for p in pipes.sizes("40"))
DNLiteral = Literal[DN_CHOICES]  # type: ignore[valid-type]
Schedule = Literal["10", "40", "80"]
StateInput = Literal["T", "P", "H", "S", "Q", "D", "U"]
UNIT_OF = {"T": "K", "P": "Pa", "H": "J/kg", "S": "J/(kg·K)", "Q": "", "D": "kg/m^3", "U": "J/kg"}


# ---------------- fluid properties ----------------

class FluidPropertiesInputs(BaseModel):
    fluid: str = Input("Water", "", "Fluid", "CoolProp name, e.g. Water, R134a, Air, IF97::Water, INCOMP::MEG[0.3]",
                       json_schema_extra={"choices": "fluids"})
    input_1: StateInput = Input("T", "", "First input")
    value_1: float = Input(373.15, "", "First value (SI)")
    input_2: StateInput = Input("Q", "", "Second input")
    value_2: float = Input(1.0, "", "Second value (SI)")

    @model_validator(mode="after")
    def _different(self):
        if self.input_1 == self.input_2:
            raise ValueError("Choose two different inputs")
        return self


@register_tool("thermo.fluid_properties", "Fluid properties", FluidPropertiesInputs,
               description="State properties of any CoolProp fluid from any two inputs.",
               reference="CoolProp (Bell et al., 2014); validated against IAPWS-95 steam table values",
               tags=("properties", "steam", "refrigerant"))
def fluid_properties_tool(inp: FluidPropertiesInputs) -> FluidState:
    return fluid(inp.fluid).state(**{inp.input_1: inp.value_1, inp.input_2: inp.value_2})


# ---------------- steam tables ----------------

@dataclass
class TableResult(Result):
    columns: list = rfield("", "Columns", default_factory=list, summary=False)
    rows: list = rfield("", "Rows", default_factory=list, summary=False)
    n_rows: int = rfield("", "Rows", default=0)


class SaturatedTableInputs(BaseModel):
    by: Literal["temperature", "pressure"] = Input("temperature", "", "Tabulate by")
    start: float = Input(283.15, "", "Start (K or Pa)")
    stop: float = Input(473.15, "", "Stop (K or Pa)")
    points: int = Input(10, "", "Number of rows", ge=2, le=200)
    formulation: Literal["IAPWS95", "IF97"] = Input("IAPWS95", "", "Formulation")


@register_tool("thermo.saturated_steam_table", "Saturated steam table", SaturatedTableInputs,
               description="Saturated water/steam table by temperature or pressure (°C, kPa, kJ/kg).",
               reference="IAPWS-95 / IAPWS-IF97 via CoolProp; checked against Cengel & Boles Table A-4",
               tags=("steam", "table"))
def saturated_steam_table_tool(inp: SaturatedTableInputs) -> TableResult:
    import numpy as np
    values = np.linspace(inp.start, inp.stop, inp.points)
    df = saturated_table(T=values, formulation=inp.formulation) if inp.by == "temperature" else \
        saturated_table(P=values, formulation=inp.formulation)
    return TableResult(columns=list(df.columns), rows=df.round(6).values.tolist(), n_rows=len(df))


# ---------------- pipe pressure drop ----------------

class PipePressureDropInputs(BaseModel):
    fluid: str = Input("Water", "", "Fluid", json_schema_extra={"choices": "fluids"})
    T: float = Input(293.15, "K", "Temperature", gt=0)
    P: float = Input(3e5, "Pa", "Pressure (absolute)", gt=0)
    mass_flow: float = Input(5.0, "kg/s", "Mass flow", gt=0)
    dn: DNLiteral = Input(50, "", "Nominal size DN")
    schedule: Schedule = Input("40", "", "Schedule")
    length: float = Input(100.0, "m", "Pipe length", gt=0)
    elevation_change: float = Input(0.0, "m", "Elevation change (outlet - inlet)")
    material: str = Input("Carbon Steel", "", "Pipe material", json_schema_extra={"choices": "materials:metal"})
    n_elbow_90: int = Input(0, "", "90° standard elbows", ge=0)
    n_elbow_90_LR: int = Input(0, "", "90° long-radius elbows", ge=0)
    n_elbow_45: int = Input(0, "", "45° elbows", ge=0)
    n_tee_straight: int = Input(0, "", "Tees (straight run)", ge=0)
    n_tee_branch: int = Input(0, "", "Tees (branch flow)", ge=0)
    n_gate_valve: int = Input(0, "", "Gate valves (open)", ge=0)
    n_ball_valve: int = Input(0, "", "Ball valves (open)", ge=0)
    n_globe_valve: int = Input(0, "", "Globe valves (open)", ge=0)
    n_check_valve: int = Input(0, "", "Swing check valves", ge=0)


@register_tool("thermo.pipe_pressure_drop", "Pipe pressure drop", PipePressureDropInputs,
               description="Friction (Colebrook), fittings (Crane K = f_T·L/D) and elevation pressure drop.",
               reference="Crane TP-410; Colebrook (1939); checked against Haaland explicit friction factor",
               tags=("pipe", "pressure drop", "fluids"))
def pipe_pressure_drop_tool(inp: PipePressureDropInputs) -> PipeDropResult:
    size = pipes.pipe(inp.dn, inp.schedule)
    fittings = {name: getattr(inp, field) for name, field in FITTING_FIELDS.items()}
    return pipe_pressure_drop(inp.fluid, inp.T, inp.P, size.id, inp.length, mass_flow=inp.mass_flow,
                              material=inp.material, fittings=fittings, elevation_change=inp.elevation_change)


# ---------------- insulation ----------------

class _InsulationBase(BaseModel):
    dn: DNLiteral = Input(100, "", "Nominal size DN")
    schedule: Schedule = Input("40", "", "Schedule")
    T_fluid: float = Input(453.15, "K", "Fluid temperature")
    T_ambient: float = Input(298.15, "K", "Ambient temperature")
    insulation: str = Input("Mineral wool", "", "Insulation material", json_schema_extra={"choices": "materials:insulation"})
    pipe_material: str = Input("Carbon Steel", "", "Pipe material", json_schema_extra={"choices": "materials:metal"})
    outer_surface: Literal["natural", "wind"] = Input("natural", "", "Outer surface condition")
    wind_speed: float = Input(0.0, "m/s", "Wind speed (if windy)", ge=0)
    emissivity: float = Input(0.9, "", "Outer surface emissivity", ge=0, le=1)


class InsulationThicknessInputs(_InsulationBase):
    q_max: float = Input(50.0, "W/m", "Allowed heat loss per metre", gt=0)


@register_tool("thermo.insulation_thickness", "Insulation thickness", InsulationThicknessInputs,
               description="Minimum insulation thickness for a target heat loss per metre of pipe.",
               reference="EN ISO 12241; Incropera ch. 3 & 9 (Churchill-Chu natural convection + radiation)",
               tags=("insulation", "heat loss"))
def insulation_thickness_tool(inp: InsulationThicknessInputs) -> InsulationResult:
    size = pipes.pipe(inp.dn, inp.schedule)
    return insulation_thickness(size.id, size.od, inp.T_fluid, inp.T_ambient, inp.q_max, inp.insulation,
                                inp.pipe_material, inp.outer_surface, inp.emissivity, inp.wind_speed)


class InsulationHeatLossInputs(_InsulationBase):
    thickness: float = Input(0.05, "m", "Insulation thickness", ge=0)


@register_tool("thermo.insulation_heat_loss", "Insulated pipe heat loss", InsulationHeatLossInputs,
               description="Heat loss and surface temperature for a given insulation thickness.",
               reference="EN ISO 12241; Incropera ch. 3 & 9 (Churchill-Chu natural convection + radiation)",
               tags=("insulation", "heat loss"))
def insulation_heat_loss_tool(inp: InsulationHeatLossInputs) -> InsulationResult:
    size = pipes.pipe(inp.dn, inp.schedule)
    return insulated_pipe_heat_loss(size.id, size.od, inp.thickness, inp.T_fluid, inp.T_ambient, inp.insulation,
                                    inp.pipe_material, inp.outer_surface, inp.emissivity, inp.wind_speed)


# ---------------- refrigeration cycle ----------------

class RefrigerationCycleInputs(BaseModel):
    refrigerant: str = Input("R134a", "", "Refrigerant", json_schema_extra={"choices": "fluids"})
    T_evap: float = Input(273.15, "K", "Evaporating temperature")
    T_cond: float = Input(313.15, "K", "Condensing temperature")
    compressor_power: float = Input(10e3, "W", "Compressor power", gt=0)
    isentropic_efficiency: float = Input(0.75, "", "Isentropic efficiency", gt=0, le=1)
    superheat: float = Input(5.0, "K", "Evaporator superheat", ge=0)
    subcooling: float = Input(3.0, "K", "Condenser subcooling", ge=0)


@register_tool("thermo.refrigeration_cycle", "Refrigeration / heat pump cycle", RefrigerationCycleInputs,
               description="Single-stage vapour-compression cycle: COP, capacities and states.",
               reference="Cengel & Boles, Thermodynamics, ch. 11; energy balance check",
               tags=("heat pump", "refrigeration", "cycle"))
def refrigeration_cycle_tool(inp: RefrigerationCycleInputs) -> RefrigerationCycleResult:
    return refrigeration_cycle(inp.refrigerant, inp.T_evap, inp.T_cond, inp.compressor_power,
                               inp.isentropic_efficiency, inp.superheat, inp.subcooling)


# ---------------- cooling tower ----------------

class CoolingTowerInputs(BaseModel):
    heat_load: float = Input(80e3, "W", "Heat load", gt=0)
    T_hot_water: float = Input(304.15, "K", "Hot water inlet temperature")
    T_dry: float = Input(297.15, "K", "Ambient dry-bulb temperature")
    RH: float = Input(0.6, "", "Relative humidity (0-1)", ge=0, le=1)
    approach: float = Input(3.0, "K", "Approach to wet bulb", gt=0)
    cycles_of_concentration: float = Input(3.0, "", "Cycles of concentration", gt=1)
    altitude: float = Input(0.0, "m", "Site altitude", ge=0)


@register_tool("thermo.cooling_tower", "Cooling tower sizing", CoolingTowerInputs,
               description="Water flow, cold-water temperature and evaporation/drift/blowdown losses.",
               reference="ASHRAE psychrometrics (PsychroLib); Perry's Handbook evaporation rule; energy balance check",
               tags=("cooling tower", "psychrometrics"))
def cooling_tower_tool(inp: CoolingTowerInputs) -> CoolingTowerResult:
    return cooling_tower(inp.heat_load, inp.T_hot_water, inp.T_dry, inp.RH, inp.approach,
                         inp.cycles_of_concentration, inp.altitude)
