"""Generates the PWA's placeholder icons: a simple vinyl-record glyph on a
rounded dark-violet square, in the sizes the manifest needs. Not run
automatically -- a one-off (`uv run python scripts/gen_icons.py`) used to
produce `web/public/icons/*` and `web/public/favicon.svg`, checked in as
ordinary static assets. Swap these for real artwork whenever you like.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

BG = (11, 11, 15, 255)
ACCENT = (124, 92, 255, 255)
LIGHT = (242, 242, 245, 255)

OUT_DIR = Path(__file__).resolve().parent.parent / "web" / "public"


def _rounded_square(size: int, radius_ratio: float = 0.22) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = int(size * radius_ratio)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BG)
    return img


def _vinyl_glyph(img: Image.Image, inset_ratio: float = 0.16) -> None:
    size = img.width
    draw = ImageDraw.Draw(img)
    inset = int(size * inset_ratio)
    draw.ellipse([inset, inset, size - inset, size - inset], fill=ACCENT)
    hole_r = size * 0.06
    cx = cy = size / 2
    draw.ellipse([cx - hole_r, cy - hole_r, cx + hole_r, cy + hole_r], fill=BG)
    ring_r = size * 0.20
    draw.ellipse(
        [cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
        outline=LIGHT,
        width=max(2, int(size * 0.012)),
    )


def make_icon(size: int, maskable: bool = False) -> Image.Image:
    img = _rounded_square(size, radius_ratio=0.0 if maskable else 0.22)
    # Maskable icons need generous "safe zone" padding since platforms crop
    # them to arbitrary shapes; a smaller inner glyph avoids clipping.
    _vinyl_glyph(img, inset_ratio=0.28 if maskable else 0.16)
    return img


def main() -> None:
    icons_dir = OUT_DIR / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    make_icon(192).save(icons_dir / "icon-192.png")
    make_icon(512).save(icons_dir / "icon-512.png")
    make_icon(512, maskable=True).save(icons_dir / "icon-512-maskable.png")

    favicon_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="rgb{BG[:3]}"/>
  <circle cx="32" cy="32" r="22" fill="rgb{ACCENT[:3]}"/>
  <circle cx="32" cy="32" r="12.8" fill="none" stroke="rgb{LIGHT[:3]}" stroke-width="1.6"/>
  <circle cx="32" cy="32" r="3.8" fill="rgb{BG[:3]}"/>
</svg>
"""
    (OUT_DIR / "favicon.svg").write_text(favicon_svg)
    print(f"Wrote icons to {icons_dir} and favicon to {OUT_DIR / 'favicon.svg'}")


if __name__ == "__main__":
    main()
