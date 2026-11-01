"""
Thevenin equivalent-circuit model (1RC or 2RC) with OCV(SOC), Arrhenius resistances and an optional
lumped thermal model, for constant current, constant power, CC-CV charge and drive-cycle profiles.

Sign convention: current I > 0 discharges the cell.

    V = OCV(SOC) - I·R0(T) - V1 - V2,      dVk/dt = I/Ck - Vk/(Rk·Ck),      dSOC/dt = -I / (3600·Q)

Each step uses the exact solution of the RC pairs for a current held constant over the step (zero-order
hold), so any time step is stable and a current step reproduces V(t) = OCV - I·R0 - I·R1·(1 - e^(-t/τ1)) - ...
exactly at the sample times.
References: Plett, *Battery Management Systems Vol. 1* (2015), ch. 2; Hu, Li & Peng (2012),
J. Power Sources 198, 359 (comparison of ECMs for Li-ion cells).
"""
from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass, field, replace
from typing import Callable, Literal

import numpy as np

from engtoolkit.catalogs.cells import Cell

R_GAS = 8.314462618

Mode = Literal["discharge_cc", "discharge_cp", "charge_cccv", "drive_cycle"]


def _interp(x: float, xs: tuple[float, ...], ys: tuple[float, ...]) -> float:
    """Scalar linear interpolation, clamped at the ends (faster than np.interp for one value per step)."""
    i = bisect_right(xs, x)
    if i <= 0:
        return ys[0]
    if i >= len(xs):
        return ys[-1]
    x0, x1 = xs[i - 1], xs[i]
    return ys[i - 1] + (ys[i] - ys[i - 1]) * (x - x0) / (x1 - x0)


@dataclass(frozen=True)
class ECMParams:
    """Electrical parameters of one cell (resistances at T_ref)."""
    capacity_Ah: float
    soc: tuple[float, ...]
    ocv: tuple[float, ...]
    R0: float
    R1: float
    tau1: float
    R2: float = 0.0
    tau2: float = 1.0
    Ea_R: float = 0.0
    T_ref: float = 298.15
    dUdT: tuple[float, ...] = ()
    V_min: float = 2.5
    V_max: float = 4.2

    @classmethod
    def from_cell(cls, cell: Cell, n_rc: int = 2) -> ECMParams:
        if n_rc not in (1, 2):
            raise ValueError("n_rc must be 1 or 2")
        R2 = cell.R2 if n_rc == 2 else 0.0
        R1 = cell.R1 if n_rc == 2 else cell.R1 + cell.R2  # 1RC lumps both pairs into one
        tau1 = cell.tau1 if n_rc == 2 else (cell.R1 * cell.tau1 + cell.R2 * cell.tau2) / (cell.R1 + cell.R2)
        return cls(cell.capacity_Ah, cell.soc, cell.ocv, cell.R0, R1, tau1, R2, cell.tau2, cell.Ea_R, cell.T_ref,
                   cell.dUdT, cell.V_min, cell.V_max)

    def resistance_factor(self, T: float) -> float:
        """Arrhenius multiplier on all resistances at temperature T [K]."""
        return math.exp(self.Ea_R / R_GAS * (1.0 / T - 1.0 / self.T_ref)) if self.Ea_R else 1.0

    def ocv_at(self, soc):
        return np.interp(soc, self.soc, self.ocv)

    def dUdT_at(self, soc):
        return np.interp(soc, self.soc, self.dUdT) if self.dUdT else 0.0 * np.asarray(soc)

    def scaled(self, capacity: float = 1.0, resistance: float = 1.0) -> ECMParams:
        """Aged cell: capacity and resistances multiplied by the given factors."""
        return replace(self, capacity_Ah=self.capacity_Ah * capacity, R0=self.R0 * resistance,
                       R1=self.R1 * resistance, R2=self.R2 * resistance)


@dataclass
class Simulation:
    """Time series of a simulation (SI units, SOC 0-1)."""
    t: np.ndarray
    current: np.ndarray
    voltage: np.ndarray
    soc: np.ndarray
    temperature: np.ndarray
    heat: np.ndarray            # heat generated in the cell [W]
    heat_removed: np.ndarray    # heat to the coolant / ambient [W]
    h: np.ndarray               # effective heat transfer coefficient over the cooled area [W/(m²·K)]
    stop_reason: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def power(self) -> np.ndarray:
        return self.current * self.voltage

    @property
    def capacity_Ah(self) -> float:
        """Charge delivered (discharge positive) [A·h], trapezoidal integration."""
        return float(np.trapezoid(self.current, self.t) / 3600) if len(self.t) > 1 else 0.0

    @property
    def energy_Wh(self) -> float:
        return float(np.trapezoid(self.power, self.t) / 3600) if len(self.t) > 1 else 0.0


# ---------------- current profiles ----------------

# Synthetic drive cycle: (duration [s], current as a fraction of the peak C-rate). Urban stop-and-go,
# then a highway section, with regenerative braking (negative current). Not a standardised cycle.
DRIVE_CYCLE = (
    (20, 0.0), (15, 0.6), (30, 0.25), (8, -0.35), (20, 0.0), (12, 0.8), (40, 0.3), (10, -0.45), (25, 0.0),
    (15, 0.7), (60, 0.35), (12, -0.4), (15, 0.0), (20, 1.0), (180, 0.45), (30, 0.6), (15, -0.5), (60, 0.4),
    (20, -0.3), (30, 0.0),
)


def drive_cycle_current(peak_current: float) -> Callable[[float], float]:
    edges = np.cumsum([d for d, _ in DRIVE_CYCLE])
    levels = np.array([f for _, f in DRIVE_CYCLE]) * peak_current
    period = float(edges[-1])

    def current(t: float) -> float:
        return float(levels[np.searchsorted(edges, t % period, side="right") % len(levels)])

    return current


# ---------------- simulation ----------------

def simulate(params: ECMParams, mode: Mode = "discharge_cc", *, c_rate: float = 1.0, power: float = 0.0,
             soc0: float | None = None, T0: float = 298.15, thermal=None, dt: float | None = None,
             t_max: float | None = None, cv_cutoff_C: float = 0.05, soc_min: float = 0.0,
             current_fn: Callable[[float], float] | None = None) -> Simulation:
    """
    Run the equivalent-circuit model until a cut-off.

    mode: ``discharge_cc`` (c_rate), ``discharge_cp`` (power [W], positive = discharge), ``charge_cccv``
    (CC at c_rate to V_max, then CV until the current falls below ``cv_cutoff_C``), ``drive_cycle``
    (synthetic cycle with peak current c_rate·Q, repeated until V_min or ``soc_min``; regenerative current
    is limited so the voltage stays at or below V_max).
    ``current_fn(t)`` overrides the profile with any current [A] (stops at V_min / V_max / t_max).
    thermal: a :class:`~engtoolkit.electrical.battery.thermal.ThermalModel` (None = isothermal at T0).
    """
    Q = params.capacity_Ah
    I_nom = c_rate * Q
    if soc0 is None:
        soc0 = {"charge_cccv": 0.0, "drive_cycle": 0.95}.get(mode, 1.0)
    if mode in ("discharge_cc", "drive_cycle", "charge_cccv") and current_fn is None and c_rate <= 0:
        raise ValueError("C-rate must be positive")
    if mode == "discharge_cp" and current_fn is None and power <= 0:
        raise ValueError("Power must be positive for a constant-power discharge")
    if t_max is None:
        rate = c_rate if mode != "discharge_cp" else power / (params.ocv_at(0.5) * Q)
        t_max = 3600.0 * 1.6 / max(rate, 1e-3) + (4 * 3600 if mode == "charge_cccv" else 0)
        if mode == "drive_cycle":
            t_max *= 6
    if dt is None:
        dt = 2.0 if mode == "drive_cycle" else float(min(max(t_max / 2500, 0.5), 10.0))
    if mode == "drive_cycle" and current_fn is None:
        current_fn = drive_cycle_current(I_nom)

    n_max = int(t_max / dt) + 2
    t = np.empty(n_max)
    I_arr, V_arr, soc_arr, T_arr = (np.empty(n_max) for _ in range(4))
    q_gen, q_out, h_arr = (np.empty(n_max) for _ in range(3))

    v1 = v2 = 0.0
    soc, T = soc0, T0
    phase_cv = False
    stop = "time limit"
    n = 0
    time = 0.0
    while n < n_max:
        f = params.resistance_factor(T)
        R0, R1, R2 = params.R0 * f, params.R1 * f, params.R2 * f
        e1 = math.exp(-dt / params.tau1)
        e2 = math.exp(-dt / params.tau2) if R2 > 0 else 0.0
        E = _interp(soc, params.soc, params.ocv)
        # terminal voltage with the step current applied: V = a - R0·I
        a = E - v1 - v2

        if current_fn is not None:
            I = current_fn(time)
            if I < 0 and a - R0 * I > params.V_max:  # the BMS limits regenerative charging at V_max
                I = min((a - params.V_max) / R0, 0.0)
        elif mode == "discharge_cc":
            I = I_nom
        elif mode == "discharge_cp":
            disc = a * a - 4 * R0 * power
            if disc < 0:
                stop = "power limit (voltage collapse)"
                break
            I = (a - math.sqrt(disc)) / (2 * R0)
        else:  # charge_cccv
            I = -I_nom
            if phase_cv or a - R0 * I > params.V_max:
                phase_cv = True
                I = (a - params.V_max) / R0  # holds V = V_max
                if -I < cv_cutoff_C * Q:
                    stop = "charge complete (CV current cut-off)"
                    break

        V = a - R0 * I
        t[n], I_arr[n], V_arr[n], soc_arr[n], T_arr[n] = time, I, V, soc, T
        rev = -I * T * _interp(soc, params.soc, params.dUdT) if params.dUdT else 0.0
        q_irr = I * I * R0 + (v1 * v1 / R1 if R1 else 0.0) + (v2 * v2 / R2 if R2 else 0.0)
        q_gen[n] = q_irr + rev
        if thermal is not None:
            sinks = thermal.sinks(T)
            q_out[n] = sum(g * (T - Ts) for g, Ts in sinks)
            h_arr[n] = sum(g for g, _ in sinks) / thermal.area
        else:
            q_out[n], h_arr[n] = q_gen[n], math.nan
        n += 1

        if V < params.V_min and I > 0:
            stop = "lower cut-off voltage"
            break
        if V > params.V_max + 1e-6 and I < 0 and mode != "charge_cccv":
            stop = "upper cut-off voltage"
            break
        if soc <= soc_min and I > 0 and mode == "drive_cycle":
            stop = "minimum SOC"
            break
        if soc <= 0.0 and I > 0:
            stop = "SOC reached 0"
            break

        # advance one step
        v1 = v1 * e1 + R1 * (1 - e1) * I
        v2 = v2 * e2 + R2 * (1 - e2) * I
        soc = soc - I * dt / (3600.0 * Q)
        if thermal is not None:
            T = thermal.step(T, q_gen[n - 1], dt, sinks)
        time += dt
        if time > t_max:
            break

    sl = slice(0, n)
    return Simulation(t[sl].copy(), I_arr[sl].copy(), V_arr[sl].copy(), soc_arr[sl].copy(), T_arr[sl].copy(),
                      q_gen[sl].copy(), q_out[sl].copy(), h_arr[sl].copy(), stop, {"dt": dt})
