"""Shared plotting style (AA Engineering Toolkit theme)."""
from contextlib import contextmanager
from pathlib import Path

STYLE_PATH = Path(__file__).resolve().parent / "aa.mplstyle"

COLORS = ["#4F46E5", "#06B6D4", "#F97316", "#22C55E", "#A855F7", "#EC4899", "#0EA5E9", "#EAB308"]
DISCIPLINE_COLORS = {"thermo": "#F97316", "structural": "#0EA5E9", "electrical": "#22C55E", "asme": "#A855F7"}


def use_style() -> None:
    """Apply the toolkit matplotlib style globally (call once in a notebook)."""
    import matplotlib.pyplot as plt
    plt.style.use(STYLE_PATH)


def _figure_class():
    from matplotlib.figure import Figure

    class ToolkitFigure(Figure):
        """A Figure that renders itself in Jupyter (any front end) without pyplot."""

        def _repr_png_(self):
            import io
            buf = io.BytesIO()
            self.savefig(buf, format="png", dpi=110)
            return buf.getvalue()

        def to_png(self, dpi: int = 110) -> bytes:
            return self._repr_png_() if dpi == 110 else self._png(dpi)

        def _png(self, dpi):
            import io
            buf = io.BytesIO()
            self.savefig(buf, format="png", dpi=dpi)
            return buf.getvalue()

        def to_svg(self) -> str:
            import io
            buf = io.StringIO()
            self.savefig(buf, format="svg")
            return buf.getvalue()

    return ToolkitFigure


def new_figure(nrows: int = 1, ncols: int = 1, **kwargs):
    """
    (fig, axes) like ``plt.subplots`` but without pyplot: the figure is not auto-shown, so a
    returned figure displays exactly once in Jupyter and can be serialised by the web app
    (``fig.to_png()``, ``fig.to_svg()``). Use ``fig.savefig(...)`` in scripts.
    """
    figsize = kwargs.pop("figsize", None)
    fig = _figure_class()(figsize=figsize, layout="constrained")
    return fig, fig.subplots(nrows, ncols, **kwargs)


@contextmanager
def styled():
    """Context manager applying the toolkit style for the figures created inside it."""
    import matplotlib.pyplot as plt
    with plt.style.context(STYLE_PATH):
        yield
