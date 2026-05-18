"""Generate app.ico for Telegrab — purple gradient rounded square with T + upload arrow."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ICO = ROOT / "assets" / "icons" / "app.ico"


def _render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size
    r = int(s * 0.1875)  # corner radius

    # Purple gradient approximation (top-left #6366f1, bottom-right #8b5cf6)
    draw.rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=(99, 102, 241, 255))

    # "T" shape
    lw = max(2, int(s * 0.09))  # line width
    # Horizontal bar of T
    x1 = int(s * 0.3)
    x2 = int(s * 0.7)
    y_bar = int(s * 0.38)
    draw.line([(x1, y_bar), (x2, y_bar)], fill=(255, 255, 255, 255), width=lw)
    # Vertical bar of T
    cx = s // 2
    y_bot = int(s * 0.72)
    draw.line([(cx, y_bar), (cx, y_bot)], fill=(255, 255, 255, 255), width=lw)

    # Upload arrow (chevron above center)
    arr_w = int(s * 0.11)
    arr_top = int(s * 0.48)
    arr_bot = int(s * 0.58)
    draw.line([(cx - arr_w, arr_bot), (cx, arr_top), (cx + arr_w, arr_bot)],
              fill=(255, 255, 255, 180), width=max(1, lw - 1))

    return img


def main():
    sizes = [16, 32, 48, 64, 128, 256]
    imgs = [_render(s) for s in sizes]
    imgs[-1].save(
        str(ICO),
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=imgs[:-1],
    )
    print(f"Created {ICO} ({ICO.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
