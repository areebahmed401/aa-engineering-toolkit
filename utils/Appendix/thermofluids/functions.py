import math
from ..constants import PIPE_THERMAL_CONDUCTIVITY
from ..formulas import colebrook_white

def convert_headtombar(h, density):
    return 9.81 * density * h / 100.0

def darcy_weisbach(f, distance, velocity, diameter):
    return f * distance * (velocity ** 2) / (2 * diameter * 9.81)

def get_equivalent_length(fittings, diameter):
    Le_D = {
        "90_elbow": 30, "45_elbow": 16, "globe_valve": 340,
        "gate_valve": 8, "ball_valve": 3, "check_valve": 100,
        "tee_run": 20, "tee_branch": 60
    }
    breakdown, Le_total = {}, 0.0
    for key, count in fittings.items():
        if key in Le_D:
            Le = Le_D[key] * count * diameter
            breakdown[key] = Le
            Le_total += Le
    for k in Le_D.keys():
        if k not in breakdown:
            breakdown[k] = 0.0
    return Le_total, breakdown

def insulated_pipe_heat_loss(d_in, d_out, t_ins, T_fluid_c, T_atm_c, k_ins,
                             pipe_material="Carbon Steel", h_out=10.0):
    """
    Heat loss per metre [W/m] of an insulated pipe from series resistances:
    pipe wall conduction + insulation conduction + outer surface convection.
    The inner wall is assumed at the fluid temperature.

    d_in, d_out : pipe inner / outer diameter [m]
    t_ins       : insulation thickness [m]
    k_ins       : insulation conductivity [W/m·K]
    h_out       : outer surface heat transfer coefficient [W/m²·K]
    """
    k_pipe = PIPE_THERMAL_CONDUCTIVITY.get(pipe_material, 45.0)  # Default to Carbon Steel if unknown
    r1, r2 = d_in / 2.0, d_out / 2.0
    r3 = r2 + t_ins
    R_pipe = math.log(r2 / r1) / (2 * math.pi * k_pipe)
    R_ins = math.log(r3 / r2) / (2 * math.pi * k_ins)
    R_conv = 1 / (h_out * 2 * math.pi * r3)
    return (T_fluid_c - T_atm_c) / (R_pipe + R_ins + R_conv)

def calc_insulation_thickness(d_in, d_out, T_fluid_c, T_atm_c, q_max, k_ins,
                              pipe_material="Carbon Steel", h_out=10.0, t_max=0.5):
    """
    Minimum insulation thickness [mm] that keeps the heat loss at or below q_max [W/m].
    Solved by bisection on insulated_pipe_heat_loss. Returns 0 if the bare pipe already
    meets q_max and inf if even t_max [m] is not enough.
    """
    if T_fluid_c - T_atm_c <= 0:
        return 0.0

    def loss(t):
        return insulated_pipe_heat_loss(d_in, d_out, t, T_fluid_c, T_atm_c, k_ins, pipe_material, h_out)

    if loss(0.0) <= q_max:
        return 0.0
    if loss(t_max) > q_max:
        return float('inf')

    lo, hi = 0.0, t_max
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if loss(mid) > q_max:
            lo = mid
        else:
            hi = mid
    return hi * 1000.0  # mm

import CoolProp.CoolProp as CP
import math

# ---------------- Helper Functions -----------------
def mixture_molar_mass(fluids, mass_fracs):
    """Calculate average molar mass of a mixture given fluids and mass fractions."""
    molar_masses = [CP.PropsSI("M", f) for f in fluids]
    total_mass = sum(mass_fracs)
    molar_contributions = [mass_fracs[i] / molar_masses[i] for i in range(len(fluids))]
    avg_molar_mass = total_mass / sum(molar_contributions)
    return avg_molar_mass


def required_pump_flow(V, Pi, Pf, t):
    """Calculate required pump flow for pump-down (classical)."""
    return (V / t) * math.log(Pi / Pf)


def mixture_properties(fluids, mass_fracs, T_C, P_mbar):
    """Return density and viscosity of a gas mixture using mass fractions."""
    total_mass = sum(mass_fracs)
    if total_mass == 0:
        raise ValueError("Mass fractions cannot all be zero")
    mass_fracs = [mf / total_mass for mf in mass_fracs]

    molar_masses = [CP.PropsSI("M", f) for f in fluids]
    moles = [mass_fracs[i] / molar_masses[i] for i in range(len(fluids))]
    total_moles = sum(moles)
    mole_fracs = [n / total_moles for n in moles]

    P_Pa = P_mbar * 100.0
    T_K = T_C + 273.15

    density = sum(
        mole_fracs[i] * CP.PropsSI("D", "T", T_K, "P", P_Pa, fluids[i])
        for i in range(len(fluids))
    )
    viscosity = sum(
        mole_fracs[i] * CP.PropsSI("VISCOSITY", "T", T_K, "P", P_Pa, fluids[i])
        for i in range(len(fluids))
    )

    return density, viscosity


def validate_water_state(T_C, P_mbar):
    """Check if water is superheated at given T and P."""
    T_K = T_C + 273.15
    P_Pa = P_mbar * 100.0
    Tsat = CP.PropsSI("T", "P", P_Pa, "Q", 0, "Water")
    if T_K <= Tsat:
        return False, Tsat - 273.15
    return True, Tsat - 273.15


# ---------------- High-Level Sizing Functions -----------------
def pumpdown_sizing(fluids, mass_fracs, V, Pi_mbar, Pf_mbar, T_C, t):
    """Perform pump-down sizing calculations."""
    if Pf_mbar >= Pi_mbar:
        raise ValueError("Final pressure must be less than initial pressure")

    if "Water" in fluids:
        valid, Tsat_C = validate_water_state(T_C, Pi_mbar)
        if not valid:
            raise ValueError(
                f"Water must be superheated. At {Pi_mbar} mbar, Tsat ≈ {Tsat_C:.2f} °C. "
                f"Your T = {T_C:.2f} °C"
            )

    Pi_Pa = Pi_mbar * 100.0
    Pf_Pa = Pf_mbar * 100.0
    T_K = T_C + 273.15

    # Pump flow
    Q_m3s_classical = required_pump_flow(V, Pi_Pa, Pf_Pa, t)

    # Convert to Nm³/hr
    P_norm = 101325.0
    T_norm = 273.15
    Q_Nm3hr_classical = Q_m3s_classical * 3600.0 * (Pi_Pa / P_norm) * (T_norm / T_K)

    # Mixture props
    density, viscosity = mixture_properties(fluids, mass_fracs, T_C, Pi_mbar)
    M_mix = mixture_molar_mass(fluids, mass_fracs)

    return {
        "Q_m3hr": Q_m3s_classical * 3600.0,
        "Q_Nm3hr": Q_Nm3hr_classical,
        "M_mix": M_mix,
        "density": density,
        "viscosity": viscosity,
        "T_C": T_C,
    }


def continuous_operation_sizing(P_mbar, T_C, mdot_steam_kg_hr, mdot_co2_kg_hr):
    """Perform continuous operation pump sizing calculations."""
    T_K = T_C + 273.15
    P_Pa = P_mbar * 100.0

    valid, Tsat_C = validate_water_state(T_C, P_mbar)
    if not valid:
        raise ValueError(
            f"Steam must be superheated. At {P_mbar} mbar, Tsat ≈ {Tsat_C:.2f} °C. "
            f"Your T = {T_C:.2f} °C"
        )

    mdot_steam = mdot_steam_kg_hr / 3600.0
    mdot_co2 = mdot_co2_kg_hr / 3600.0

    M_steam = CP.PropsSI("M", "Water")
    M_co2 = CP.PropsSI("M", "CO2")

    n_steam = mdot_steam / M_steam
    n_co2 = mdot_co2 / M_co2
    n_total = n_steam + n_co2

    y_steam = n_steam / n_total
    y_co2 = n_co2 / n_total

    R = 8.314
    Vdot_m3s = n_total * R * T_K / P_Pa
    Vdot_m3hr = Vdot_m3s * 3600.0

    # Convert to Nm³/hr
    P_norm = 101325.0
    T_norm = 273.15
    Vdot_Nm3hr = Vdot_m3s * 3600.0 * (P_Pa / P_norm) * (T_norm / T_K)

    fluids = ["Water", "CO2"]
    mass_fracs = [mdot_steam, mdot_co2]
    density, viscosity = mixture_properties(fluids, mass_fracs, T_C, P_mbar)

    return {
        "Vdot_m3hr": Vdot_m3hr,
        "Vdot_Nm3hr": Vdot_Nm3hr,
        "y_steam": y_steam,
        "y_co2": y_co2,
        "density": density,
        "viscosity": viscosity,
    }


import math
import psychrolib

psychrolib.SetUnitSystem(psychrolib.SI)

def atmospheric_pressure(altitude_m):
    return 101.3 * (1 - 2.25577e-5 * altitude_m) ** 5.25588  # kPa

def psychrometric_properties(t_dry, RH, altitude):
    P_atm = atmospheric_pressure(altitude)
    P_sat = 0.611 * 10 ** (7.5 * t_dry / (t_dry + 237.3))
    P_v = RH / 100 * P_sat
    P_d = P_atm - P_v
    SH = 0.622 * P_v / (P_atm - P_v)
    t_wet = psychrolib.GetTWetBulbFromRelHum(t_dry, RH / 100, P_atm * 1000)
    return {
        "P_atm": P_atm,
        "P_sat": P_sat,
        "P_v": P_v,
        "P_d": P_d,
        "SH": SH,
        "t_wet": t_wet,
    }

def cooling_tower_performance(Q_kW, Cp_water, t_in, t_wet, approach):
    t_out = t_wet + approach
    delta_T = t_in - t_out
    if delta_T <= 0:
        raise ValueError(
            f"Hot water inlet ({t_in} °C) must be above wet bulb + approach ({t_out:.1f} °C)"
        )
    m_dot = Q_kW / (Cp_water * delta_T)  # kg/s
    effectiveness = delta_T / (delta_T + approach)
    return m_dot, effectiveness, delta_T, t_out

def cooling_tower_losses(m_dot, delta_T, CoC):
    if CoC <= 1:
        raise ValueError("Cycles of concentration must be greater than 1")
    m_dot_hr = m_dot * 3600
    evap_loss = 0.00085 * m_dot_hr * delta_T
    drift_loss = 0.002 * m_dot_hr
    blowdown_loss = evap_loss / (CoC - 1)
    return evap_loss, drift_loss, blowdown_loss

import CoolProp.CoolProp as CP
from .Ref_Cycle import get_refrigeration_cycle

def get_environmental_ratings(refrigerant):
    if refrigerant.lower() == "water":
        return "Water has no environmental impact"
    else:
        try:
            gwp_100 = CP.PropsSI('GWP100', refrigerant)
            gwp_20 = CP.PropsSI('GWP20', refrigerant)
            odp = CP.PropsSI('ODP', refrigerant)
            environmental_ratings = f"GWP100: {gwp_100}, GWP20: {gwp_20}, ODP: {odp}"
        except ValueError:
            environmental_ratings = "No environmental ratings available"
    return environmental_ratings


def get_health_ratings(refrigerant):
    Health_Hazard = CP.PropsSI('HH', refrigerant)
    flammability = CP.PropsSI('FH', refrigerant)
    Physical_hazard = CP.PropsSI('PH', refrigerant)
    health_ratings = f"Health Hazard: {Health_Hazard}, Flammability: {flammability}, Physical Hazard: {Physical_hazard}"
    return health_ratings