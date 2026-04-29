"""
Regenerate the base OG-card template at assets/images/og-template.png.

Run manually whenever you want to change the brand chrome (gradient,
wordmark, logo placement). The per-post title overlay is handled by
Hugo at build time via layouts/partials/og-image.html — this script
only touches the static template.

Requires: Pillow, the HitC logo at static/hitc-logo.png, and a Lato
font installed (uses assets/fonts/Lato-Black.ttf if present, falls
back to a system Lato install otherwise).

Usage:
    python3 scripts/gen_og_template.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "images" / "og-template.png"
LOGO = ROOT / "static" / "hitc-logo.png"

# Prefer the bundled font; fall back to system Lato if needed
FONT_CANDIDATES = [
    ROOT / "assets" / "fonts" / "Lato-Black.ttf",
    ROOT / "assets" / "fonts" / "Lato-Bold.ttf",
    Path("/usr/share/fonts/truetype/lato/Lato-Black.ttf"),
    Path("/usr/share/fonts/truetype/lato/Lato-Bold.ttf"),
]
FONT_PATH = next((p for p in FONT_CANDIDATES if p.exists()), None)
if FONT_PATH is None:
    raise SystemExit("Lato font not found — install fonts-lato or bundle one in assets/fonts/")

# Azure palette
NAVY = (0, 32, 80)         # #002050
DARK = (27, 27, 47)        # #1B1B2F (matches dark-mode --theme)
BLUE = (0, 120, 212)       # #0078D4
CYAN = (80, 230, 255)      # #50E6FF
MUTED = (153, 153, 187)    # #9999bb (matches dark-mode --secondary)


def radial_gradient(size, inner, outer, centre):
    """Soft radial gradient — `inner` colour at `centre`, `outer` at corners."""
    w, h = size
    cx, cy = centre
    img = Image.new("RGB", size, outer)
    px = img.load()
    max_r = ((max(cx, w - cx)) ** 2 + (max(cy, h - cy)) ** 2) ** 0.5
    for y in range(h):
        for x in range(w):
            r = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            t = min(r / max_r, 1.0)
            t = t * t  # ease-out for a softer falloff
            px[x, y] = (
                int(inner[0] * (1 - t) + outer[0] * t),
                int(inner[1] * (1 - t) + outer[1] * t),
                int(inner[2] * (1 - t) + outer[2] * t),
            )
    return img


def main():
    bg = radial_gradient((W, H), inner=NAVY, outer=DARK, centre=(W * 0.85, H * 0.15))
    draw = ImageDraw.Draw(bg)

    # Cyan accent bar across the top
    draw.rectangle([(0, 0), (W, 6)], fill=CYAN)

    # Subtle Azure-blue stripe down the left edge
    draw.rectangle([(0, 0), (4, H)], fill=BLUE)

    # Bottom-left: site wordmark + URL
    font_brand = ImageFont.truetype(str(FONT_PATH), 28)
    font_url = ImageFont.truetype(str(FONT_PATH), 20)
    draw.text((80, H - 72), "HEAD IN THE CLOUD", font=font_brand, fill=CYAN)
    draw.text((80, H - 38), "headinthecloud.uk", font=font_url, fill=MUTED)

    # Bottom-right: HitC logo
    if LOGO.exists():
        logo = Image.open(LOGO).convert("RGBA")
        target_h = 90
        target_w = int(logo.width * target_h / logo.height)
        logo = logo.resize((target_w, target_h), Image.LANCZOS)
        bg.paste(logo, (W - target_w - 80, H - target_h - 30), logo)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    bg.save(OUT, "PNG", optimize=True)
    print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
