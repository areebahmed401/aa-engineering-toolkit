"""
Template for a new discipline. Copy this folder to ``engtoolkit/<discipline>/`` and:

1. Put pure calculations in ``models/`` (functions/classes returning ``Result`` dataclasses, SI units).
2. Put figures in ``plots.py`` (return matplotlib Figures, never call ``plt.show()``).
3. Register app-facing tools in ``tools.py`` with ``@register_tool("<discipline>.<name>", ...)``.
4. Put data files in ``data/`` with a ``# source:`` line (CSV) or ``source:`` key (YAML).
5. Add the discipline to ``SECTIONS`` in ``engtoolkit/core/registry.py`` and an import-linter
   contract in ``pyproject.toml``.
6. Add tests in ``tests/<discipline>/`` and a ``test_tool_<name>`` validation test per tool.

Expose the public API here, e.g. ``from .models.example import example_calculation``.
"""
