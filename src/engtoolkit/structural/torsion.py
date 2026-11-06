"""
Torsion (SI units), RWTH OLS formulary §3 notation: x1 beam axis, T torque about the shear centre (positive
about +x1), ϑ twist, ϑ' = dϑ/dx1, G J_T Saint-Venant and E C_T warping stiffness.

- Free warping (Saint-Venant, §3.1): T = G J_T ϑ', τ_max = T/W_T.
- Restrained warping (§3.2): E C_T ϑ'''' − G J_T ϑ'' = m_t with T = M_SV + M_B, M_SV = G J_T ϑ',
  M_B = −E C_T ϑ''', dT/dx1 = −m_t; bimoment B = −E C_T ϑ'', warping stress σ_ω = B ω / C_T.

:func:`solve_torsion` solves either with general supports (fixed, fork, free) and loads (point torques and a
uniform m_t); :class:`Torsion` is the formulary closed form for a cantilever with an end torque.
"""
from __future__ import annotations

import math
from typing import Literal

import numpy as np

SupportName = Literal["fixed", "fork", "free"]


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


# ---------------- general solver (piecewise exact) ----------------

# Conditions per support: derivative orders of ϑ (in ξ = x/L) set to zero, "T" = end torque condition.
# Restrained warping uses the first tuple, free warping (Saint-Venant only) the second.
_SUPPORT_CONDITIONS = {
    "fixed": ((0, 1), (0,)),      # ϑ = 0, ϑ' = 0 (warping prevented)
    "fork": ((0, 2), (0,)),       # ϑ = 0, ϑ'' = 0 (free to warp)
    "free": ((2, "T"), ("T",)),   # ϑ'' = 0, torque = applied end torque
}


def _sinh_minus_z(z):
    """sinh z − z, accurate for small z."""
    out = np.sinh(z) - z
    small = np.abs(z) < 0.5
    z2 = z[small] ** 2
    out[small] = z[small] ** 3 / 6 * (1 + z2 / 20 * (1 + z2 / 42 * (1 + z2 / 72 * (1 + z2 / 110))))
    return out


def _cosh_minus_2(z):
    """cosh z − 1 − z²/2, accurate for small z."""
    out = 2 * np.sinh(z / 2) ** 2 - z**2 / 2
    small = np.abs(z) < 0.5
    z2 = z[small] ** 2
    out[small] = z2**2 / 24 * (1 + z2 / 30 * (1 + z2 / 56 * (1 + z2 / 90 * (1 + z2 / 132))))
    return out


class TorsionSolution:
    """
    Solution of :func:`solve_torsion`. Arrays along x (segment ends appear twice, left and right value, so
    jumps of T at point torques plot as steps): theta [rad], dtheta [rad/m], M_sv, M_b, T [N·m], B [N·m²].
    """

    def __init__(self, length, GJ, EC, alpha, knots, coef, basis, particular, n_samples):
        self.length, self.GJ, self.EC, self.alpha = length, GJ, EC, alpha
        self.warping = EC > 0
        self.knots = knots
        self._coef, self._basis, self._part = coef, basis, particular
        xs, D = [], []
        for s in range(len(knots) - 1):
            d = knots[s + 1] - knots[s]
            u = np.linspace(0.0, d, max(2, math.ceil(n_samples * d) + 1))
            xs.append((knots[s] + u) * length)
            D.append(self._derivs(s, u))
        self.x = np.concatenate(xs)
        self._set(np.concatenate(D, axis=1))

    def _derivs(self, s, u):
        """ϑ and its first three ξ-derivatives on segment s at local u: array (4, n)."""
        return np.einsum("kbn,b->kn", self._basis(s, u), self._coef[s]) + self._part(s, u)

    def _set(self, D):
        L = self.length
        self.theta = D[0]
        self.dtheta = D[1] / L
        self.d2theta = D[2] / L**2
        self.d3theta = D[3] / L**3
        self.M_sv = self.GJ * self.dtheta
        self.M_b = -self.EC * self.d3theta if self.warping else np.zeros_like(self.theta)
        self.T = self.M_sv + self.M_b
        self.B = -self.EC * self.d2theta if self.warping else np.zeros_like(self.theta)

    def at(self, x: float) -> dict:
        """Values at one position x [m] (right-hand value at a point torque)."""
        xi = min(max(x / self.length, 0.0), 1.0)
        s = min(int(np.searchsorted(self.knots, xi, side="right")) - 1, len(self.knots) - 2)
        D = self._derivs(s, np.array([xi - self.knots[s]]))
        out = TorsionSolution.__new__(TorsionSolution)
        out.length, out.GJ, out.EC, out.warping = self.length, self.GJ, self.EC, self.warping
        out._set(D)
        return {k: float(getattr(out, k)[0]) for k in ("theta", "dtheta", "M_sv", "M_b", "T", "B")}


def solve_torsion(length: float, GJ: float, EC: float = 0.0, left: SupportName = "fixed",
                  right: SupportName = "free", point_torques=(), m_t: float = 0.0,
                  n_samples: int = 101) -> TorsionSolution:
    """
    Twist of a straight member under torsion, exact piecewise solution.

    ``EC > 0``: restrained warping E C_T ϑ'''' − G J_T ϑ'' = m_t. On each segment between point torques
    ϑ = c1 + c2 u + c3 f3(u) + c4 f4(u) + particular (u = ξ − ξ_start), with f3, f4 = e^(−αu), e^(−α(d−u))
    for long segments (α d > 1, no overflow for large α) and (cosh αu − 1)/α², (sinh αu − αu)/α³ for short
    ones (well conditioned as α → 0). One linear system holds the support conditions and, at each point
    torque, continuity of ϑ, ϑ', ϑ'' and the jump T(x+) − T(x−) = −T_k.
    ``EC = 0``: free warping, G J_T ϑ'' = −m_t, same supports (fixed and fork both just hold ϑ = 0).

    ``left``/``right``: "fixed" (ϑ = ϑ' = 0), "fork" (ϑ = ϑ'' = 0) or "free" (ϑ'' = 0, end torque);
    at least one end must hold ϑ. ``point_torques``: [(x, T), ...] with 0 ≤ x ≤ L, T positive about +x1;
    a torque at a fixed or fork end goes straight into the support. ``m_t``: uniform torque per length [N·m/m].
    """
    for side in (left, right):
        if side not in _SUPPORT_CONDITIONS:
            raise ValueError(f"Unknown support {side!r} (fixed, fork or free)")
    if left == "free" and right == "free":
        raise ValueError("At least one end must restrain the twist (fixed or fork): free-free is a mechanism")
    if not (length > 0 and GJ > 0 and EC >= 0):
        raise ValueError("Need length > 0, G J_T > 0 and E C_T ≥ 0")
    L = length
    warping = EC > 0
    alpha = math.sqrt(GJ * L**2 / EC) if warping else math.inf
    unit = EC / L**3 if warping else GJ / L          # torque = unit * τ, τ in ξ-units
    q = m_t * L / unit

    tol = 1e-9
    end_T = [0.0, 0.0]
    interior: dict[float, float] = {}
    for x, Tk in point_torques:
        if not (-tol * L <= x <= L * (1 + tol)):
            raise ValueError(f"Point torque at x = {x} m is outside the member (0 … {L} m)")
        xi = x / L
        if xi < tol:
            end_T[0] += Tk
        elif xi > 1 - tol:
            end_T[1] += Tk
        else:
            interior[xi] = interior.get(xi, 0.0) + Tk
    knots = np.array([0.0] + sorted(interior) + [1.0])
    seg_d = np.diff(knots)
    nseg = len(seg_d)
    nb = 4 if warping else 2
    a = alpha

    def basis(s, u):
        n = len(u)
        Z, O = np.zeros(n), np.ones(n)
        if not warping:
            return np.array([[O, u], [Z, O], [Z, Z], [Z, Z]])
        z = a * u
        if a * seg_d[s] <= 1.0:
            sh, ch, cm1 = np.sinh(z), np.cosh(z), 2 * np.sinh(z / 2) ** 2
            f3 = [cm1 / a**2, sh / a, ch, a * sh]
            f4 = [_sinh_minus_z(z) / a**3, cm1 / a**2, sh / a, ch]
        else:
            e3, e4 = np.exp(-z), np.exp(-a * (seg_d[s] - u))
            f3 = [e3, -a * e3, a**2 * e3, -a**3 * e3]
            f4 = [e4, a * e4, a**2 * e4, a**3 * e4]
        return np.array([[O, u, f3[0], f4[0]], [Z, O, f3[1], f4[1]], [Z, Z, f3[2], f4[2]], [Z, Z, f3[3], f4[3]]])

    def particular(s, u):
        if not warping:
            return -q * np.array([u**2 / 2, u, np.ones_like(u), np.zeros_like(u)])
        z = a * u
        if a * seg_d[s] <= 1.0:  # (cosh z − 1 − z²/2)/α⁴ → u⁴/24 as α → 0
            return q * np.array([_cosh_minus_2(z) / a**4, _sinh_minus_z(z) / a**3,
                                 2 * np.sinh(z / 2) ** 2 / a**2, np.sinh(z) / a])
        return -q / a**2 * np.array([u**2 / 2, u, np.ones_like(u), np.zeros_like(u)])

    w_T = np.array([0.0, a**2, 0.0, -1.0]) if warping else np.array([0.0, 1.0, 0.0, 0.0])

    def cond(s, u, c):
        Bm = basis(s, np.array([u]))[:, :, 0]
        Pm = particular(s, np.array([u]))[:, 0]
        return (w_T @ Bm, float(w_T @ Pm)) if c == "T" else (Bm[c], float(Pm[c]))

    rows, rhs = [], []

    def add(terms, value):
        r = np.zeros(nseg * nb)
        for s, sign, (cf, pp) in terms:
            r[s * nb:(s + 1) * nb] += sign * cf
            value -= sign * pp
        rows.append(r)
        rhs.append(value)

    k = 0 if warping else 1
    for c in _SUPPORT_CONDITIONS[left][k]:
        add([(0, 1.0, cond(0, 0.0, c))], -end_T[0] / unit if c == "T" else 0.0)
    for c in _SUPPORT_CONDITIONS[right][k]:
        add([(nseg - 1, 1.0, cond(nseg - 1, seg_d[-1], c))], end_T[1] / unit if c == "T" else 0.0)
    for s, xi in enumerate(knots[1:-1]):
        for c in ((0, 1, 2) if warping else (0,)):
            add([(s + 1, 1.0, cond(s + 1, 0.0, c)), (s, -1.0, cond(s, seg_d[s], c))], 0.0)
        add([(s + 1, 1.0, cond(s + 1, 0.0, "T")), (s, -1.0, cond(s, seg_d[s], "T"))], -interior[xi] / unit)

    A, b = np.array(rows), np.array(rhs)
    cs = np.abs(A).max(axis=0)
    cs[cs == 0] = 1.0
    A = A / cs
    rs = np.abs(A).max(axis=1)[:, None]
    coef = np.linalg.solve(A / rs, b / rs[:, 0]) / cs
    return TorsionSolution(L, GJ, EC if warping else 0.0, alpha if warping else math.nan, knots,
                           coef.reshape(nseg, nb), basis, particular, n_samples)
