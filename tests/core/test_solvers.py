"""Pure-Python numerical helpers."""
import math

import pytest

from engtoolkit.core.solvers import brentq


@pytest.mark.parametrize("f,a,b,root", [
    (lambda x: x**2 - 2, 0, 2, math.sqrt(2)),
    (lambda x: math.cos(x) - x, 0, 1, 0.7390851332151607),
    (lambda x: math.exp(x) - 5, -3, 4, math.log(5)),
    (lambda x: (x - 1e-3) ** 3, -1, 1, 1e-3),  # flat triple root
])
def test_brentq_finds_roots(f, a, b, root):
    assert brentq(f, a, b, xtol=1e-12) == pytest.approx(root, abs=1e-9)


def test_brentq_requires_bracket():
    with pytest.raises(ValueError):
        brentq(lambda x: x**2 + 1, -1, 1)
