"""
Convection and radiation correlations (SI units, temperatures in K).

References: Incropera, DeWitt, Bergman & Lavine, *Fundamentals of Heat and Mass Transfer*;
Gnielinski (1976); Churchill & Bernstein (1977); Churchill & Chu (1975).
"""
from __future__ import annotations

import math

from engtoolkit.materials import AIR, fluid

SIGMA = 5.670374419e-8  # Stefan-Boltzmann [W/(m²·K⁴)]
G = 9.80665


def prandtl(mu: float, cp: float, k: float) -> float:
    return mu * cp / k


def h_from_nusselt(Nu: float, k: float, L: float) -> float:
    return Nu * k / L


# ---------------- internal forced convection ----------------

def dittus_boelter(Re: float, Pr: float, heating: bool = True) -> float:
    """Nu for fully developed turbulent pipe flow (Re > 1e4, 0.6 < Pr < 160)."""
    return 0.023 * Re**0.8 * Pr ** (0.4 if heating else 0.3)


def gnielinski(Re: float, Pr: float, f: float | None = None) -> float:
    """Nu for turbulent/transitional pipe flow (3000 < Re < 5e6, 0.5 < Pr < 2000), smooth-pipe f by default."""
    if f is None:
        f = (0.790 * math.log(Re) - 1.64) ** -2  # Petukhov
    return (f / 8) * (Re - 1000) * Pr / (1 + 12.7 * math.sqrt(f / 8) * (Pr ** (2 / 3) - 1))


def nusselt_internal(Re: float, Pr: float, boundary: str = "constant_T", f: float | None = None) -> float:
    """
    Fully developed pipe-flow Nusselt number.
    Laminar (Re < 2300): 3.66 (constant wall T) or 4.36 (constant heat flux).
    Turbulent (Re > 3000): Gnielinski. Linear blend in between.
    """
    lam = 3.66 if boundary == "constant_T" else 4.36
    if Re < 2300:
        return lam
    if Re >= 3000:
        return gnielinski(Re, Pr, f)
    w = (Re - 2300) / 700
    return (1 - w) * lam + w * gnielinski(3000, Pr, f)


# ---------------- external convection ----------------

def churchill_bernstein(Re: float, Pr: float) -> float:
    """Average Nu for a cylinder in cross-flow (Re·Pr > 0.2)."""
    return 0.3 + (0.62 * Re**0.5 * Pr ** (1 / 3)) / (1 + (0.4 / Pr) ** (2 / 3)) ** 0.25 * (
        1 + (Re / 282000) ** (5 / 8)) ** (4 / 5)


def rayleigh(T_surface: float, T_fluid: float, L: float, fluid_name: str = AIR, P: float = 101325.0) -> tuple[float, float, float]:
    """Rayleigh number, film Prandtl number and film conductivity for natural convection."""
    T_film = 0.5 * (T_surface + T_fluid)
    s = fluid(fluid_name).state(T=T_film, P=P)
    beta = 1.0 / T_film  # ideal gas
    nu = s.mu / s.rho
    alpha = s.k / (s.rho * s.cp)
    Ra = G * beta * abs(T_surface - T_fluid) * L**3 / (nu * alpha)
    return Ra, s.Pr, s.k


def natural_convection_horizontal_cylinder(T_surface: float, T_ambient: float, D: float,
                                           fluid_name: str = AIR) -> float:
    """h [W/(m²·K)] for a long horizontal cylinder in still air (Churchill & Chu, Ra < 1e12)."""
    if abs(T_surface - T_ambient) < 1e-9:
        return 0.0
    Ra, Pr, k = rayleigh(T_surface, T_ambient, D, fluid_name)
    Nu = (0.60 + 0.387 * Ra ** (1 / 6) / (1 + (0.559 / Pr) ** (9 / 16)) ** (8 / 27)) ** 2
    return Nu * k / D


def natural_convection_vertical_plate(T_surface: float, T_ambient: float, L: float,
                                      fluid_name: str = AIR) -> float:
    """h [W/(m²·K)] for a vertical plate of height L (Churchill & Chu, all Ra)."""
    if abs(T_surface - T_ambient) < 1e-9:
        return 0.0
    Ra, Pr, k = rayleigh(T_surface, T_ambient, L, fluid_name)
    Nu = (0.825 + 0.387 * Ra ** (1 / 6) / (1 + (0.492 / Pr) ** (9 / 16)) ** (8 / 27)) ** 2
    return Nu * k / L


def forced_convection_cylinder(velocity: float, T_surface: float, T_ambient: float, D: float,
                               fluid_name: str = AIR, P: float = 101325.0) -> float:
    """h [W/(m²·K)] for a cylinder in cross-flow (e.g. wind on a pipe)."""
    s = fluid(fluid_name).state(T=0.5 * (T_surface + T_ambient), P=P)
    Re = s.rho * velocity * D / s.mu
    return churchill_bernstein(Re, s.Pr) * s.k / D


def forced_convection_flat_plate(velocity: float, T_surface: float, T_ambient: float, L: float,
                                 fluid_name: str = AIR, P: float = 101325.0) -> float:
    """
    Average h [W/(m²·K)] for parallel flow over a flat plate of length L: laminar 0.664·Re^0.5·Pr^(1/3)
    below Re = 5e5, mixed laminar/turbulent (0.037·Re^0.8 - 871)·Pr^(1/3) above (Incropera eq. 7.30, 7.38).
    """
    s = fluid(fluid_name).state(T=0.5 * (T_surface + T_ambient), P=P)
    Re = s.rho * velocity * L / s.mu
    Nu = 0.664 * Re**0.5 * s.Pr ** (1 / 3) if Re < 5e5 else (0.037 * Re**0.8 - 871) * s.Pr ** (1 / 3)
    return Nu * s.k / L


def h_radiation(emissivity: float, T_surface: float, T_surroundings: float) -> float:
    """Linearised radiation coefficient [W/(m²·K)] to large surroundings."""
    return emissivity * SIGMA * (T_surface + T_surroundings) * (T_surface**2 + T_surroundings**2)


# ---------------- resistances and exchangers ----------------

def R_conduction_cylinder(r_inner: float, r_outer: float, k: float, length: float = 1.0) -> float:
    """Conduction resistance of a cylindrical shell [K/W] (per metre by default)."""
    return math.log(r_outer / r_inner) / (2 * math.pi * k * length)


def R_convection_cylinder(h: float, r: float, length: float = 1.0) -> float:
    return 1.0 / (h * 2 * math.pi * r * length)


def lmtd(T_hot_in: float, T_hot_out: float, T_cold_in: float, T_cold_out: float) -> float:
    """Counter-flow log-mean temperature difference [K]."""
    dT1 = T_hot_in - T_cold_out
    dT2 = T_hot_out - T_cold_in
    if dT1 <= 0 or dT2 <= 0:
        raise ValueError("Temperature cross: LMTD undefined")
    if abs(dT1 - dT2) < 1e-12:
        return dT1
    return (dT1 - dT2) / math.log(dT1 / dT2)
