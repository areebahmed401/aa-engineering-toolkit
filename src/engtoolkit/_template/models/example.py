"""Example model: a calculation returning a Result with units."""
from dataclasses import dataclass

from engtoolkit.core.results import Result, rfield


@dataclass
class ExampleResult(Result):
    area: float = rfield("m^2", "Area")


def example_calculation(width: float, height: float) -> ExampleResult:
    """Rectangle area [m²] from width and height [m]."""
    return ExampleResult(area=width * height)
