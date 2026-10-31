# converters.py
import math

class Angle:
    """Angle conversions."""
    @staticmethod
    def rad_to_deg(value_rad: float) -> float:
        return math.degrees(value_rad)

    @staticmethod
    def deg_to_rad(value_deg: float) -> float:
        return math.radians(value_deg)

def rads_to_degrees(value_rad: float) -> float:
    return Angle.rad_to_deg(value_rad)

class Length:
    """Length conversions."""
    @staticmethod
    def mm_to_m(value_mm: float) -> float:
        return value_mm / 1000.0

    @staticmethod
    def m_to_mm(value_m: float) -> float:
        return value_m * 1000.0

class Flow:
    """Flow rate conversions."""
    @staticmethod
    def l_per_s_to_m3_per_s(value_lps: float) -> float:
        return value_lps / 1000.0

    @staticmethod
    def m3_per_s_to_l_per_s(value_m3s: float) -> float:
        return value_m3s * 1000.0

class Pressure:
    """Pressure conversions."""
    @staticmethod
    def pa_to_kpa(value_pa: float) -> float:
        return value_pa / 1000.0

    @staticmethod
    def kpa_to_pa(value_kpa: float) -> float:
        return value_kpa * 1000.0

    @staticmethod
    def bar_to_pa(value_bar: float) -> float:
        return value_bar * 1e5

    @staticmethod
    def pa_to_bar(value_pa: float) -> float:
        return value_pa / 1e5

class Velocity:
    """Velocity conversions."""
    @staticmethod
    def m_s_to_km_h(value_ms: float) -> float:
        return value_ms * 3.6

    @staticmethod
    def km_h_to_m_s(value_kmh: float) -> float:
        return value_kmh / 3.6
    
class Temperature:
    """Temperature conversions between common units."""

    @staticmethod
    def c_to_k(celsius: float) -> float:
        """Celsius to Kelvin."""
        return celsius + 273.15

    @staticmethod
    def k_to_c(kelvin: float) -> float:
        """Kelvin to Celsius."""
        return kelvin - 273.15

    @staticmethod
    def c_to_f(celsius: float) -> float:
        """Celsius to Fahrenheit."""
        return (celsius * 9/5) + 32

    @staticmethod
    def f_to_c(fahrenheit: float) -> float:
        """Fahrenheit to Celsius."""
        return (fahrenheit - 32) * 5/9

    @staticmethod
    def k_to_f(kelvin: float) -> float:
        """Kelvin to Fahrenheit."""
        return (kelvin - 273.15) * 9/5 + 32

    @staticmethod
    def f_to_k(fahrenheit: float) -> float:
        """Fahrenheit to Kelvin."""
        return (fahrenheit - 32) * 5/9 + 273.15

    @staticmethod
    def c_to_r(celsius: float) -> float:
        """Celsius to Rankine."""
        return (celsius + 273.15) * 9/5

    @staticmethod
    def r_to_c(rankine: float) -> float:
        """Rankine to Celsius."""
        return (rankine - 491.67) * 5/9

    @staticmethod
    def k_to_r(kelvin: float) -> float:
        """Kelvin to Rankine."""
        return kelvin * 9/5

    @staticmethod
    def r_to_k(rankine: float) -> float:
        """Rankine to Kelvin."""
        return rankine * 5/9
