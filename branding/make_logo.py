"""
Render the PNG versions of the AA Engineering Toolkit logo (the SVGs in this folder
are the source design: a truss "AA" mark, transparent background). Run:  python branding/make_logo.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
GOLD = (242, 183, 5)       # #F2B705
GOLD_DEEP = (201, 148, 0)  # #C99400
INK = (17, 18, 20)         # #111214
WHITE = (255, 255, 255)
MUTED = (94, 97, 104)      # #5E6168
MUTED_DARK = (154, 157, 164)  # #9A9DA4
SCALE = 8                  # supersampling for smooth edges

# Truss geometry in SVG viewBox units (64 x 64)
BOTTOM = ((6, 54), (58, 54))
CHORDS = [((6, 54), (19, 12)), ((19, 12), (32, 54)), ((32, 54), (45, 12)),
          ((45, 12), (58, 54)), ((19, 12), (45, 12))]
BARS = [((10.95, 38), (27.05, 38)), ((36.95, 38), (53.05, 38))]
WEBS = [((10.95, 38), (19, 54)), ((27.05, 38), (19, 54)),
        ((36.95, 38), (45, 54)), ((53.05, 38), (45, 54))]
PINS = [(6, 54), (32, 54), (58, 54), (19, 12), (45, 12), (10.95, 38),
        (27.05, 38), (36.95, 38), (53.05, 38), (19, 54), (45, 54)]


def _font(names, size):
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _line(d, u, p1, p2, fill, width):
    """Line with round caps (circles at both ends)."""
    d.line([(p1[0] * u, p1[1] * u), (p2[0] * u, p2[1] * u)], fill=fill, width=round(width * u))
    r = width * u / 2
    for x, y in (p1, p2):
        d.ellipse([x * u - r, y * u - r, x * u + r, y * u + r], fill=fill)


def draw_icon(size, ink=INK, pin_fill=WHITE):
    s = size * SCALE
    u = s / 64  # SVG viewBox units
    icon = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(icon)

    _line(d, u, *BOTTOM, ink, 3.4)
    for p1, p2 in CHORDS:
        _line(d, u, p1, p2, GOLD, 3.6)
    for p1, p2 in BARS:
        _line(d, u, p1, p2, ink, 2.8)
    for p1, p2 in WEBS:
        _line(d, u, p1, p2, GOLD, 2)
    for x, y in PINS:  # ink ring (stroke 1.6 centred on r=2.6) with filled centre
        r = (2.6 + 0.8) * u
        d.ellipse([x * u - r, y * u - r, x * u + r, y * u + r], fill=ink)
        r = (2.6 - 0.8) * u
        d.ellipse([x * u - r, y * u - r, x * u + r, y * u + r], fill=pin_fill)
    return icon.resize((size, size), Image.LANCZOS)


def draw_wordmark(height, dark=False):
    s = SCALE
    w, h = int(height * 360 / 64), height
    img = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
    if dark:
        icon = draw_icon(height, ink=WHITE, pin_fill=INK)
        aa, eng, tag = GOLD, WHITE, MUTED_DARK
    else:
        icon = draw_icon(height)
        aa, eng, tag = GOLD_DEEP, INK, MUTED
    icon = icon.resize((h * s, h * s), Image.LANCZOS)
    img.paste(icon, (0, 0), icon)
    d = ImageDraw.Draw(img)
    u = h * s / 64
    bold = _font(["Inter-Bold.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], round(24 * u))
    semi = _font(["Inter-SemiBold.ttf", "seguisb.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], round(24 * u))
    small = _font(["Inter-Medium.ttf", "segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"], round(15 * u))
    d.text((80 * u, 31 * u), "AA", font=bold, fill=aa, anchor="ls")
    aa_w = d.textlength("AA ", font=bold)
    d.text((80 * u + aa_w, 31 * u), "Engineering", font=semi, fill=eng, anchor="ls")
    x = 80 * u
    for ch in "TOOLKIT":  # letter-spaced
        d.text((x, 54 * u), ch, font=small, fill=tag, anchor="ls")
        x += d.textlength(ch, font=small) + 3 * u
    return img.resize((w, h), Image.LANCZOS)


if __name__ == "__main__":
    draw_icon(256).save(HERE / "aa-logo.png")
    draw_icon(256, ink=WHITE, pin_fill=INK).save(HERE / "aa-logo-dark.png")
    draw_icon(64).save(HERE / "favicon.png")
    draw_wordmark(96).save(HERE / "aa-wordmark.png")
    draw_wordmark(96, dark=True).save(HERE / "aa-wordmark-dark.png")
    print("wrote aa-logo.png, aa-logo-dark.png, favicon.png, aa-wordmark.png, aa-wordmark-dark.png")
