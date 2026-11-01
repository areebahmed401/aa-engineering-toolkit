"""
Semi-empirical aging correlations (capacity fade and resistance growth).

``wang2011_lfp`` - Wang et al. (2011), "Cycle-life model for graphite-LiFePO4 cells",
J. Power Sources 196, 3942-3948 (A123 2.2 Ah 26650 cells, C/2-10C, -30 to 60 °C, 10-90 % DOD):

    Q_loss [%] = B(C) · exp(-(31700 - 370.3·C) / (R·T)) · Ah^0.55

with B = 31630, 21681, 12934, 15512 at C/2, 2C, 6C, 10C and Ah = cycles × DOD × full capacity.
At C/2 the paper also gives the single-rate fit Q_loss = 30330 · exp(-31500/(R·T)) · Ah^0.552.

``schmalstieg2014_nmc`` - Schmalstieg et al. (2014), "A holistic aging model for Li(NiMnCo)O2 based 18650
lithium-ion batteries", J. Power Sources 257, 325-334 (Sanyo UR18650E 2.05 Ah):

    C/C0 = 1 - α_cap·t^0.75 - β_cap·√Q,          R/R0 = 1 + α_res·t^0.75 + β_res·Q
    α_cap = (7.543·V - 23.75)·1e6 · exp(-6976/T)      α_res = (5.270·V - 16.32)·1e5 · exp(-5986/T)
    β_cap = 7.348e-3·(V̄ - 3.667)² + 7.600e-4 + 4.081e-3·ΔDOD
    β_res = 2.153e-4·(V̄ - 3.725)² - 1.521e-5 + 2.798e-4·ΔDOD

t in days, Q = charge throughput [A·h], V/V̄ the (mean) cell voltage, ΔDOD as a fraction.

Charge throughput is scaled to each paper's reference cell by the capacity ratio (equal full-equivalent
cycles age cells of the same chemistry equally). Wang's model has no calendar term; Schmalstieg's cycle
term was fitted at 35 °C and 1C, so for NMC the C-rate acts through the cell temperature (thermal model)
and the cycle duration (calendar time).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

R_GAS = 8.314462618

WANG_C_RATES = (0.5, 2.0, 6.0, 10.0)
WANG_B = (31630.0, 21681.0, 12934.0, 15512.0)
WANG_REF_AH = 2.2
SCHMALSTIEG_REF_AH = 2.05

MODELS = {
    "wang2011_lfp": "Wang et al. (2011) LFP cycle-life model",
    "schmalstieg2014_nmc": "Schmalstieg et al. (2014) NMC calendar + cycle model",
}


# ---------------- Wang et al. 2011 (LFP) ----------------

def wang2011_B(c_rate: float) -> float:
    """Pre-exponential factor B for a C-rate (linear between the paper's rates, constant outside)."""
    return float(np.interp(c_rate, WANG_C_RATES, WANG_B))


def wang2011_capacity_loss(ah_throughput, c_rate: float, T: float):
    """Capacity loss [%] after the given Ah throughput (reference 2.2 Ah cell) at C-rate and temperature T [K]."""
    Ah = np.asarray(ah_throughput, dtype=float)
    return wang2011_B(c_rate) * math.exp(-(31700.0 - 370.3 * c_rate) / (R_GAS * T)) * Ah**0.55


def wang2011_capacity_loss_c2(ah_throughput, T: float):
    """The paper's single-rate C/2 fit: 30330 · exp(-31500/RT) · Ah^0.552 [%]."""
    return 30330.0 * math.exp(-31500.0 / (R_GAS * T)) * np.asarray(ah_throughput, dtype=float) ** 0.552


# ---------------- Schmalstieg et al. 2014 (NMC) ----------------

def schmalstieg2014_alpha_cap(V: float, T: float) -> float:
    return (7.543 * V - 23.75) * 1e6 * math.exp(-6976.0 / T)


def schmalstieg2014_alpha_res(V: float, T: float) -> float:
    return (5.270 * V - 16.32) * 1e5 * math.exp(-5986.0 / T)


def schmalstieg2014_beta_cap(V_mean: float, dod: float) -> float:
    return 7.348e-3 * (V_mean - 3.667) ** 2 + 7.600e-4 + 4.081e-3 * dod


def schmalstieg2014_beta_res(V_mean: float, dod: float) -> float:
    return 2.153e-4 * (V_mean - 3.725) ** 2 - 1.521e-5 + 2.798e-4 * dod


def schmalstieg2014_calendar(days, V: float, T: float) -> tuple[np.ndarray, np.ndarray]:
    """Relative capacity and relative resistance after storage at voltage V and temperature T [K]."""
    t = np.asarray(days, dtype=float) ** 0.75
    return 1 - schmalstieg2014_alpha_cap(V, T) * t, 1 + schmalstieg2014_alpha_res(V, T) * t


def schmalstieg2014(days, ah_throughput, V_mean: float, dod: float, T: float) -> tuple[np.ndarray, np.ndarray]:
    """Relative capacity and resistance with calendar and cycle terms superposed (reference 2.05 Ah cell)."""
    t = np.asarray(days, dtype=float) ** 0.75
    Q = np.asarray(ah_throughput, dtype=float)
    a_c, a_r = schmalstieg2014_alpha_cap(V_mean, T), schmalstieg2014_alpha_res(V_mean, T)
    b_c, b_r = schmalstieg2014_beta_cap(V_mean, dod), schmalstieg2014_beta_res(V_mean, dod)
    return 1 - max(a_c, 0.0) * t - max(b_c, 0.0) * np.sqrt(Q), 1 + max(a_r, 0.0) * t + max(b_r, 0.0) * Q


# ---------------- cycling a catalog cell ----------------

@dataclass
class AgingCurve:
    cycles: np.ndarray
    days: np.ndarray
    capacity: np.ndarray        # relative capacity C/C0
    resistance: np.ndarray      # relative resistance R/R0 (NaN if the model has none)
    model: str

    def cycles_to(self, retention: float = 0.8) -> float:
        """Cycles until the relative capacity first falls to ``retention`` (NaN if not reached)."""
        below = np.nonzero(self.capacity <= retention)[0]
        if len(below) == 0:
            return math.nan
        i = below[0]
        if i == 0:
            return float(self.cycles[0])
        c0, c1 = self.capacity[i - 1], self.capacity[i]
        return float(self.cycles[i - 1] + (c0 - retention) / (c0 - c1) * (self.cycles[i] - self.cycles[i - 1]))


def cycle_aging(model: str, cycles, *, c_rate: float = 1.0, T: float = 298.15,
                dod: float = 1.0, V_mean: float = 3.7, c_rate_charge: float = 0.5,
                rest_hours: float = 0.0) -> AgingCurve:
    """
    Relative capacity and resistance after repeated full-depth cycles (discharge at ``c_rate``, charge at
    ``c_rate_charge``, cell at mean temperature T [K]), counted in full-equivalent cycles so the result
    applies to any cell of the model's chemistry.
    """
    n = np.asarray(cycles, dtype=float)
    hours_per_cycle = dod / c_rate + dod / c_rate_charge + rest_hours
    days = n * hours_per_cycle / 24.0
    if model == "wang2011_lfp":
        ah = n * dod * WANG_REF_AH  # Wang counts discharge throughput: cycles × DOD × capacity
        cap = 1 - wang2011_capacity_loss(ah, c_rate, T) / 100
        res = np.full_like(n, math.nan)
    elif model == "schmalstieg2014_nmc":
        ah = 2 * n * dod * SCHMALSTIEG_REF_AH  # charge + discharge throughput
        cap, res = schmalstieg2014(days, ah, V_mean, dod, T)
    else:
        raise KeyError(f"Unknown aging model {model!r}. Available: {list(MODELS)}")
    return AgingCurve(n, days, np.clip(cap, 0.0, 1.0), res, model)
