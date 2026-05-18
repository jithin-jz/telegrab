"""Generate app.ico for the Windows installer using Pillow only."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ICO = ROOT / "installer" / "app.ico"


def _draw_icon(size: int) -> Image.Image:
    """Draw the Telegrab icon: Telegram-style paper plane on a blue circle."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Blue circle background (Telegram blue)
    draw.ellipse([0, 0, size - 1, size - 1], fill=(42, 171, 238, 255))

    # Paper plane shape scaled to icon size
    s = size / 512.0
    plane_points = [
        (116 * s, 253 * s),
        (265 * s, 189 * s),
        (360 * s, 154 * s),
        (390 * s, 148 * s),
        (395 * s, 151 * s),
        (394 * s, 161 * s),
        (365 * s, 345 * s),
        (348 * s, 364 * s),
        (330 * s, 371 * s),
        (290 * s, 352 * s),
        (267 * s, 337 * s),
        (233 * s, 314 * s),
        (303 * s, 245 * s),
        (304 * s, 240 * s),
        (302 * s, 237 * s),
        (298 * s, 238 * s),
        (210 * s, 300 * s),
        (182 * s, 319 * s),
        (155 * s, 310 * s),
        (142 * s, 305 * s),
        (116 * s, 296 * s),
        (108 * s, 280 * s),
        (116 * s, 253 * s),
    ]
    draw.polygon(plane_points, fill=(255, 255, 255, 255))

    return img


def main():
    sizes = [16, 32, 48, 64, 128, 256]
    imgs = [_draw_icon(s) for s in sizes]
    imgs[-1].save(
        str(ICO),
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=imgs[:-1],
    )
    print(f"Created {ICO} ({ICO.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
