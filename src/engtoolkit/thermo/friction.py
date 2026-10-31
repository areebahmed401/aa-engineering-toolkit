"""Friction factors and pipe friction losses (Darcy convention, SI units)."""
from __future__ import annotations

import math

G = 9.80665  # m/s²


def reynolds(rho: float, velocity: float, D: float, mu: float) -> float:
    return rho * velocity * D / mu


def colebrook_white(Re: float, roughness: float, D: float, tol: float = 1e-10, max_iter: int = 200) -> float:
    """
    Darcy friction factor [-] from the Colebrook-White equation (Colebrook, 1939).
    Laminar flow (Re <= 2300) returns 64/Re.
    """
    if Re <= 0:
        raise ValueError("Reynolds number must be positive")
    if Re <= 2300:
        return 64.0 / Re
    eps_D = roughness / D
    f = haaland(Re, roughness, D)  # explicit starting value
    for _ in range(max_iter):
        f_new = (-2.0 * math.log10(eps_D / 3.7 + 2.51 / (Re * math.sqrt(f)))) ** -2
        if abs(f_new - f) < tol * f:
            return f_new
        f = f_new
    raise RuntimeError("Colebrook-White did not converge")


def haaland(Re: float, roughness: float, D: float) -> float:
    """Explicit Haaland (1983) approximation of Colebrook, within ~2 %."""
    return (-1.8 * math.log10((roughness / D / 3.7) ** 1.11 + 6.9 / Re)) ** -2


def swamee_jain(Re: float, roughness: float, D: float) -> float:
    """Explicit Swamee-Jain (1976) approximation, valid 5e3 < Re < 1e8."""
    return 0.25 / math.log10(roughness / (3.7 * D) + 5.74 / Re**0.9) ** 2


def fully_turbulent_friction_factor(roughness: float, D: float) -> float:
    """
    Fully turbulent Darcy friction factor f_T [-] (rough-pipe limit of Colebrook).
    Used with Crane TP-410 L/D values: K = f_T * (L/D).
    """
    return 0.25 / math.log10(roughness / (3.7 * D)) ** 2


def darcy_weisbach_dp(f: float, length: float, D: float, rho: float, velocity: float) -> float:
    """Frictional pressure drop [Pa]."""
    return f * length / D * 0.5 * rho * velocity**2


def head_loss(f: float, length: float, D: float, velocity: float) -> float:
    """Frictional head loss [m of fluid]."""
    return f * length / D * velocity**2 / (2 * G)
