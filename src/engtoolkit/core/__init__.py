"""Shared foundations: units, results, tool registry, environment flags, plotting style."""
from .env import IN_BROWSER, has_package
from .registry import (
    SECTIONS, Input, ToolSpec, export_schema, get_tool, list_tools, load_tools, register_tool, run,
)
from .results import Result, rfield
from .units import Q_, convert, from_si, to_si, ureg
