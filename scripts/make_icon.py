from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_ICO = ROOT / "packaging" / "nova.ico"
OUT_PNG = ROOT / "static" / "icons" / "nova.png"


def main() -> None:
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((8, 8, 248, 248), fill=(124, 92, 255, 255))
    draw.ellipse((48, 40, 120, 110), fill=(255, 255, 255, 80))
    try:
        font = ImageFont.truetype("arial.ttf", 120)
    except OSError:
        font = ImageFont.load_default()
    draw.text((128, 118), "N", fill="white", font=font, anchor="mm")
    OUT_ICO.parent.mkdir(parents=True, exist_ok=True)
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT_PNG)
    img.save(OUT_ICO, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(OUT_ICO)


if __name__ == "__main__":
    main()
