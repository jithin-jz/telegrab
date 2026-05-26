"""Generate app.ico for Telegrab — sky blue rounded square with white lowercase t."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ICO = ROOT / "assets" / "icons" / "app.ico"

SKY_BLUE = (244, 63, 94, 255)  # #f43f5e rose


def _render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r = int(size * 0.1875)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=SKY_BLUE)

    font_size = int(size * 0.45)
    try:
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), "tb", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1]
    draw.text((x, y), "tb", fill=(255, 255, 255, 255), font=font)

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
