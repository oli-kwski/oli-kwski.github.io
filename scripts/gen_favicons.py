"""
Generate the full favicon set from static/hitc-favicon.png.

Outputs into static/ so Hugo serves them at the site root:
    favicon.ico                  (multi-size: 16, 32, 48)
    favicon-16x16.png
    favicon-32x32.png
    favicon-48x48.png
    apple-touch-icon.png         (180x180, iOS home screen)
    android-chrome-192x192.png   (Android home screen)
    android-chrome-512x512.png   (PWA splash)
    site.webmanifest             (PWA manifest)

Run manually whenever the source logo changes.

Usage:
    python3 scripts/gen_favicons.py
"""
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
# Source the high-res logo — gives a clean LANCZOS downscale to all sizes
# including 512x512 without upscaling artefacts.
SRC = ROOT / "static" / "hitc-logo.png"
OUT = ROOT / "static"

PNG_SIZES = [
    ("favicon-16x16.png", 16),
    ("favicon-32x32.png", 32),
    ("favicon-48x48.png", 48),
    ("apple-touch-icon.png", 180),
    ("android-chrome-192x192.png", 192),
    ("android-chrome-512x512.png", 512),
]

ICO_SIZES = [(16, 16), (32, 32), (48, 48)]


def main():
    if not SRC.exists():
        raise SystemExit(f"Source missing: {SRC}")

    src = Image.open(SRC).convert("RGBA")

    for name, size in PNG_SIZES:
        out = OUT / name
        # Use LANCZOS for downscale, BICUBIC for the one mild upscale (256 -> 512)
        resample = Image.LANCZOS if size <= src.width else Image.BICUBIC
        img = src.resize((size, size), resample)
        img.save(out, "PNG", optimize=True)
        print(f"  {out.relative_to(ROOT)}  ({size}x{size})")

    # Multi-size .ico for legacy clients
    ico_out = OUT / "favicon.ico"
    src.save(ico_out, format="ICO", sizes=ICO_SIZES)
    print(f"  {ico_out.relative_to(ROOT)}  (16/32/48)")

    # PWA manifest
    manifest = {
        "name": "Head in the Cloud",
        "short_name": "HitC",
        "icons": [
            {"src": "/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/android-chrome-512x512.png", "sizes": "512x512", "type": "image/png"},
        ],
        "theme_color": "#0078D4",
        "background_color": "#1B1B2F",
        "display": "standalone",
        "start_url": "/",
    }
    manifest_out = OUT / "site.webmanifest"
    manifest_out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"  {manifest_out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
