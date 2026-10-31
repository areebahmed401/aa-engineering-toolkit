"""Shared foundations: units, results, tool registry, environment flags, plotting style."""
from .env import IN_BROWSER, has_package
from .registry import (
    SECTIONS, Input, ToolSpec, export_schema, get_tool, list_tools, load_tools, register_tool, run,
)
from .results import Result, rfield

_UNIT_NAMES = {"Q_", "convert", "from_si", "to_si", "ureg"}


def __getattr__(name):
    # pint is imported only when unit conversion is used (it is a slow import in the browser)
    if name in _UNIT_NAMES:
        from . import units
        return getattr(units, name)
    raise AttributeError(f"module 'engtoolkit.core' has no attribute {name!r}")
