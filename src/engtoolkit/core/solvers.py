"""
Small numerical helpers in pure Python, so common tools don't need SciPy (a ~3 s import in the browser).
"""
from __future__ import annotations

from typing import Callable


def brentq(f: Callable[[float], float], a: float, b: float, xtol: float = 1e-12, rtol: float = 4e-16,
           maxiter: int = 200) -> float:
    """
    Root of f in [a, b] by Brent's method (bisection + secant + inverse quadratic interpolation).
    f(a) and f(b) must have opposite signs. Same contract as scipy.optimize.brentq.
    """
    fa, fb = f(a), f(b)
    if fa == 0:
        return a
    if fb == 0:
        return b
    if fa * fb > 0:
        raise ValueError("f(a) and f(b) must have opposite signs")
    c, fc = a, fa
    d = e = b - a
    for _ in range(maxiter):
        if fb * fc > 0:
            c, fc = a, fa
            d = e = b - a
        if abs(fc) < abs(fb):
            a, b, c = b, c, b
            fa, fb, fc = fb, fc, fb
        tol = 2 * rtol * abs(b) + 0.5 * xtol
        m = 0.5 * (c - b)
        if abs(m) <= tol or fb == 0:
            return b
        if abs(e) >= tol and abs(fa) > abs(fb):
            s = fb / fa
            if a == c:  # secant
                p, q = 2 * m * s, 1 - s
            else:  # inverse quadratic interpolation
                q, r = fa / fc, fb / fc
                p = s * (2 * m * q * (q - r) - (b - a) * (r - 1))
                q = (q - 1) * (r - 1) * (s - 1)
            if p > 0:
                q = -q
            p = abs(p)
            if 2 * p < min(3 * m * q - abs(tol * q), abs(e * q)):
                e, d = d, p / q
            else:
                d = e = m
        else:
            d = e = m
        a, fa = b, fb
        b += d if abs(d) > tol else (tol if m > 0 else -tol)
        fb = f(b)
    raise RuntimeError("brentq did not converge")
