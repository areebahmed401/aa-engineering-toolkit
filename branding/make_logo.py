"""
Render the PNG versions of the AA Engineering Toolkit logo (the SVGs in this folder
are the source design). Run:  python branding/make_logo.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
PRIMARY = (79, 70, 229)    # #4F46E5
ACCENT = (6, 182, 212)     # #06B6D4
INK = (15, 23, 42)         # #0F172A
MUTED = (100, 116, 139)    # #64748B
SCALE = 8                  # supersampling for smooth edges


def _font(names, size):
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def draw_icon(size):
    s = size * SCALE
    u = s / 64  # SVG viewBox units

    # Diagonal gradient background
    grad = Image.new("RGB", (s, s))
    px = grad.load()
    for y in range(s):
        for x in range(s):
            t = (x + y) / (2 * (s - 1))
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(PRIMARY, ACCENT))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=15 * u, fill=255)
    icon = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    icon.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(icon)
    pts = [(12, 48), (22, 16), (32, 48), (42, 16), (52, 48)]
    d.line([(x * u, y * u) for x, y in pts], fill="white", width=round(5 * u), joint="curve")
    for x, y in (pts[0], pts[-1]):  # round caps at the feet only
        r = 2.5 * u
        d.ellipse([x * u - r, y * u - r, x * u + r, y * u + r], fill="white")
    d.line([(17.3 * u, 36 * u), (46.7 * u, 36 * u)], fill="white", width=round(4.5 * u))
    for x in (17.3, 46.7):
        r = 2.25 * u
        d.ellipse([x * u - r, 36 * u - r, x * u + r, 36 * u + r], fill="white")
    r = 3.2 * u
    d.ellipse([32 * u - r, 48 * u - r, 32 * u + r, 48 * u + r], fill="white")
    return icon.resize((size, size), Image.LANCZOS)


def draw_wordmark(height):
    s = SCALE
    w, h = int(height * 360 / 64), height
    img = Image.new("RGBA", (w * s, h * s), (255, 255, 255, 0))
    icon = draw_icon(height).resize((h * s, h * s), Image.LANCZOS)
    img.paste(icon, (0, 0), icon)
    d = ImageDraw.Draw(img)
    u = h * s / 64
    bold = _font(["Inter-Bold.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], round(24 * u))
    semi = _font(["Inter-SemiBold.ttf", "seguisb.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], round(24 * u))
    small = _font(["Inter-Medium.ttf", "segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"], round(15 * u))
    d.text((80 * u, 31 * u), "AA", font=bold, fill=PRIMARY, anchor="ls")
    aa_w = d.textlength("AA ", font=bold)
    d.text((80 * u + aa_w, 31 * u), "Engineering", font=semi, fill=INK, anchor="ls")
    x = 80 * u
    for ch in "TOOLKIT":  # letter-spaced
        d.text((x, 54 * u), ch, font=small, fill=MUTED, anchor="ls")
        x += d.textlength(ch, font=small) + 3 * u
    return img.resize((w, h), Image.LANCZOS)


if __name__ == "__main__":
    draw_icon(256).save(HERE / "aa-logo.png")
    draw_icon(64).save(HERE / "favicon.png")
    draw_wordmark(96).save(HERE / "aa-wordmark.png")
    print("wrote aa-logo.png, favicon.png, aa-wordmark.png")
