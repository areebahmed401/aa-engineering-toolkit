"""Structural figures. Every function returns a matplotlib Figure (no plt.show())."""
from __future__ import annotations

import numpy as np

from engtoolkit.core.plotting import new_figure, styled

from .loads import DistributedLoad, Fixed, MomentLoad, Pinned, PointLoad, Roller


def beam_results_plot(x, v, theta, x_internal, V, M):
    """Deflection [mm], slope, shear [N] and bending moment [N·m] diagrams."""

    with styled():
        fig, axs = new_figure(4, 1, figsize=(11, 10), sharex=True)
        axs[0].plot(x, np.asarray(v) * 1000, color="#E0A800")
        axs[0].set(ylabel="Deflection [mm]", title="Deflection")
        axs[1].plot(x, theta, color="#2B2D31")
        axs[1].set(ylabel="Slope θ [rad]", title="Slope")
        axs[2].plot(x_internal, V, color="#3D7EA6")
        axs[2].fill_between(x_internal, V, alpha=0.15, color="#3D7EA6")
        axs[2].set(ylabel="Shear [N]", title="Shear force")
        axs[3].plot(x_internal, M, color="#C8632B")
        axs[3].fill_between(x_internal, M, alpha=0.15, color="#C8632B")
        axs[3].set(ylabel="Moment [N·m]", xlabel="x [m]", title="Bending moment (sagging +)")
        for ax in axs:
            ax.axhline(0, color="#94A3B8", lw=0.8)
    return fig


def plot_fbd(beam, scale_force=None, scale_moment=None, scale_udl=None):
    """Free body diagram: loads (point, distributed, moment) and supports."""
    from matplotlib import patches

    L = beam.length
    with styled():
        fig, ax = new_figure(figsize=(12, 3))

    point = [l for l in beam.loads if isinstance(l, PointLoad)]
    udls = [l for l in beam.loads if isinstance(l, DistributedLoad)]
    moments = [l for l in beam.loads if isinstance(l, MomentLoad)]
    force_scale = scale_force or 0.3 * L / max([abs(l.P) for l in point] + [1.0])
    moment_scale = scale_moment or 0.08 * L / max([abs(l.M) for l in moments] + [1.0])
    udl_scale = scale_udl or 0.15 * L / max([abs(l.w) for l in udls] + [1.0])

    ax.plot([0, L], [0, 0], linewidth=5, color="#0F172A", solid_capstyle="round")

    for load in point:
        h = load.P * force_scale
        ax.annotate("", xy=(load.x, 0), xytext=(load.x, h),
                    arrowprops=dict(arrowstyle="-|>", color="#E0A800", lw=2))
        ax.text(load.x, h * 1.08, f"{load.P / 1e3:.2f} kN", ha="center", va="bottom", color="#E0A800", fontsize=9)
    for load in udls:
        x2 = load.x2 if load.x2 is not None else L
        h = load.w * udl_scale
        ax.fill_between([load.x1, x2], 0, h, color="#22C55E", alpha=0.15)
        for x in np.linspace(load.x1, x2, max(int((x2 - load.x1) / L * 20), 2)):
            ax.annotate("", xy=(x, 0), xytext=(x, h), arrowprops=dict(arrowstyle="-|>", color="#22C55E", lw=1))
        ax.text((load.x1 + x2) / 2, h * 1.08, f"{load.w / 1e3:.2f} kN/m", ha="center", va="bottom",
                color="#16A34A", fontsize=9)
    for load in moments:
        r = max(abs(load.M) * moment_scale, 0.03 * L)
        t = np.linspace(0.2 * np.pi, 1.8 * np.pi, 50) if load.M > 0 else np.linspace(1.8 * np.pi, 0.2 * np.pi, 50)
        ax.plot(load.x + r * np.cos(t), r * np.sin(t), color="#DC2626", lw=1.8)
        ax.annotate("", xy=(load.x + r * np.cos(t[-1]), r * np.sin(t[-1])),
                    xytext=(load.x + r * np.cos(t[-3]), r * np.sin(t[-3])),
                    arrowprops=dict(arrowstyle="-|>", color="#DC2626"))
        ax.text(load.x, r * 1.3, f"{load.M / 1e3:.2f} kN·m", ha="center", va="bottom", color="#DC2626", fontsize=9)

    s = 0.04 * L
    for end, xpos, side in [(beam.left_end, 0, -1), (beam.right_end, L, 1)]:
        if isinstance(end, Fixed):
            ax.add_patch(patches.Rectangle((xpos if side > 0 else xpos - s, -2 * s), s, 4 * s, color="#64748B"))
        elif isinstance(end, Pinned):
            ax.add_patch(patches.Polygon([(xpos, 0), (xpos - s, -1.6 * s), (xpos + s, -1.6 * s)], color="#64748B"))
        elif isinstance(end, Roller):
            ax.add_patch(patches.Polygon([(xpos, 0), (xpos - s, -1.3 * s), (xpos + s, -1.3 * s)], color="#64748B"))
            ax.add_patch(patches.Circle((xpos, -1.7 * s), 0.35 * s, color="#64748B"))

    ax.set_aspect("equal")
    ax.set_xlim(-0.08 * L, 1.08 * L)
    ax.set_ylim(-0.15 * L, 0.45 * L)
    ax.axis("off")
    return fig


def section_plot(section, title: str | None = None):
    """Cross-section drawing with centroid (●) and shear centre (✕)."""
    from matplotlib import patches

    shape = section.outline()
    with styled():
        fig, ax = new_figure(figsize=(4.5, 4.5))
        ax.add_patch(patches.Polygon(shape["outer"], closed=True, facecolor="#FCEBB0", edgecolor="#9A7400", lw=1.5))
        for hole in shape["holes"]:
            ax.add_patch(patches.Polygon(hole, closed=True, facecolor="white", edgecolor="#9A7400", lw=1.5))
        ax.plot(section.CoG_z, section.CoG_y, "o", color="#0F172A", label="Centroid")
        ax.plot(section.CoS_z, section.CoS_y, "x", color="#C8632B", ms=9, mew=2, label="Shear centre")
        pad = 0.15 * max(section.width, section.height)
        z_min = min(0.0, section.CoS_z) - pad
        ax.set_xlim(z_min, section.width + pad)
        ax.set_ylim(-pad, section.height + pad)
        ax.set_aspect("equal")
        ax.grid(False)
        ax.legend(loc="upper right", fontsize=8)
        ax.set_title(title or type(section).__name__)
        ax.set(xlabel="z [m]", ylabel="y [m]")
    return fig
