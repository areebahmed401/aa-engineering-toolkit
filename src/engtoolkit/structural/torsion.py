"""Torsion: Saint-Venant (uniform) and warping torsion of a cantilever (SI units)."""
from __future__ import annotations

import math


def saint_venant_twist(T: float, length: float, G: float, J: float) -> float:
    """Twist angle [rad] over ``length`` for uniform (warping-free) torsion: θ = T L / (G J)."""
    return T * length / (G * J)


def max_torsional_shear(T: float, W_torsion: float) -> float:
    """Maximum Saint-Venant shear stress [Pa]: τ = T / W_t."""
    return T / W_torsion


class Torsion:
    """
    Warping torsion of a cantilever with an end torque (fixed end: θ = θ' = 0, free end: θ'' = 0).

    Solution of  E C_T θ'''' − G J θ'' = 0  with ξ = x/L, α² = G J L² / (E C_T), μ = T L³ / (E C_T):
        θ = A1 + A2 cosh(αξ) + A3 sinh(αξ) + μ ξ / α²
    """

    def __init__(self, beam, TorsionalMoment, position):
        if TorsionalMoment == 0:
            raise ValueError("TorsionalMoment cannot be zero")
        if position < 0 or position > beam.length:
            raise ValueError(f"Position must be between 0 and {beam.length}")
        if beam.shape.C_torsion <= 0:
            raise ValueError("Section has no warping constant; use saint_venant_twist for closed/solid sections")

        self.G = beam.material.G  # Shear modulus
        self.J_t = beam.shape.J_torsion  # Torsional moment of area
        self.L = beam.length  # Length of the member
        self.C_t = beam.shape.C_torsion  # Warping constant
        self.E = beam.material.E  # Young's modulus
        self.T = TorsionalMoment  # Applied torsional moment
        self.x = position  # Position of interest

    @property
    def xi(self):
        """Dimensionless position along beam (0 to 1)."""
        return self.x / self.L

    @property
    def alpha(self):
        """Dimensionless warping parameter."""
        return math.sqrt(self.G * self.J_t * self.L**2 / (self.C_t * self.E))

    @property
    def mu(self):
        """Dimensionless torsional moment parameter."""
        return self.T * self.L**3 / (self.C_t * self.E)

    @property
    def A1(self):
        return -self.mu * math.tanh(self.alpha) / self.alpha**3

    @property
    def A2(self):
        return -self.A1

    @property
    def A3(self):
        return -self.mu / self.alpha**3

    def theta(self, xi: float | None = None):
        """Twist angle [rad] at ξ (default: the position given)."""
        xi = self.xi if xi is None else xi
        a = self.alpha
        return self.A1 + self.A2 * math.cosh(a * xi) + self.A3 * math.sinh(a * xi) + self.mu * xi / a**2

    def saint_venant_share(self, xi: float | None = None) -> float:
        """Fraction of the torque carried by Saint-Venant shear at ξ (the rest is warping)."""
        xi = self.xi if xi is None else xi
        a = self.alpha
        return math.tanh(a) * math.sinh(a * xi) - math.cosh(a * xi) + 1

    def __repr__(self):
        return f"Torsion(T={self.T}, x={self.x}, L={self.L}, θ={self.theta():.6f} rad)"
