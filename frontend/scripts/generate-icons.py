"""
Generate the PWA icons from the design tokens — no design tool, no binary blobs
committed by hand, and no dependency beyond the standard library.

escalasPT ships a single SVG for every icon slot, which Android will not use for
the home-screen icon and which has no maskable variant, so the installed app
gets a generic glyph. Here: 192 and 512 in PNG, plus a 512 maskable whose glyph
sits inside the 80% safe zone.

    python3 scripts/generate-icons.py
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "public" / "icons"

# Tokens from src/index.css
PRIMARY_500 = (0x10, 0xB9, 0x81)
PRIMARY_700 = (0x04, 0x78, 0x57)
SURFACE_0 = (0x05, 0x08, 0x10)
WHITE = (0xF1, 0xF5, 0xF9)

SS = 2  # supersampling factor


def _mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _rounded_rect(x, y, left, top, right, bottom, radius) -> bool:
    if x < left or x > right or y < top or y > bottom:
        return False
    cx = min(max(x, left + radius), right - radius)
    cy = min(max(y, top + radius), bottom - radius)
    return (x - cx) ** 2 + (y - cy) ** 2 <= radius**2


def _sample(x: float, y: float, size: int, glyph_scale: float) -> tuple[int, int, int]:
    """Colour at a point, in icon coordinates."""
    # Background: rounded square (or full bleed for maskable) with a 135° ramp.
    ramp = _mix(PRIMARY_500, PRIMARY_700, (x + y) / (2 * size))

    if glyph_scale < 1.0:
        colour = ramp  # maskable: the platform crops, so bleed to the edges
    else:
        if not _rounded_rect(x, y, 0, 0, size - 1, size - 1, size * 0.22):
            return SURFACE_0
        colour = ramp

    # Notebook glyph, centred, scaled into the safe zone for maskable icons.
    g = size * 0.46 * glyph_scale
    cx = cy = size / 2
    left, right = cx - g / 2, cx + g / 2
    top, bottom = cy - g * 0.62, cy + g * 0.62
    radius = g * 0.10

    if _rounded_rect(x, y, left, top, right, bottom, radius):
        spine = left + g * 0.20
        if x <= spine:
            return _mix(WHITE, PRIMARY_700, 0.25)  # the binding
        # Three ruled lines
        for i in range(3):
            line_y = top + g * (0.34 + i * 0.28)
            if abs(y - line_y) <= max(1.0, g * 0.035) and spine + g * 0.10 <= x <= right - g * 0.14:
                return _mix(PRIMARY_700, WHITE, 0.15)
        return WHITE

    return colour


def render(size: int, glyph_scale: float = 1.0) -> bytes:
    rows = []
    for py in range(size):
        row = bytearray()
        for px in range(size):
            r = g = b = 0
            for sy in range(SS):
                for sx in range(SS):
                    c = _sample(
                        px + (sx + 0.5) / SS, py + (sy + 0.5) / SS, size, glyph_scale
                    )
                    r += c[0]
                    g += c[1]
                    b += c[2]
            n = SS * SS
            row += bytes((r // n, g // n, b // n))
        rows.append(row)

    raw = b"".join(b"\x00" + bytes(row) for row in rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    targets = [
        ("icon-192.png", 192, 1.0),
        ("icon-512.png", 512, 1.0),
        ("icon-512-maskable.png", 512, 0.72),  # glyph inside the 80% safe zone
    ]
    for name, size, scale in targets:
        (OUT / name).write_bytes(render(size, scale))
        print(f"{name}  {size}×{size}")


if __name__ == "__main__":
    main()
