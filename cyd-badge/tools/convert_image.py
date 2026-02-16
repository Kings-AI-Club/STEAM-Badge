"""
Convert any image (HEIC, PNG, JPG, etc.) to an 80x80 RGB565 .bin for the badge.

Uses Pillow + pillow-heif. Run with the badge-tools conda env:
    conda run -n badge-tools python3 tools/convert_image.py [path_to_image]

If no path given, defaults to IMG_3720.HEIC in the repo root.
Output: resources/avatar.bin
"""

import os
import sys
import struct

from pillow_heif import register_heif_opener
register_heif_opener()

from PIL import Image, ImageOps

# Output dimensions (3:4 portrait ≈ 1/3 of 320px screen width)
OUT_W = 96
OUT_H = 128

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..", "..")
DEFAULT_IMG = os.path.join(REPO_ROOT, "IMG_3720.HEIC")
DST_DIR = os.path.join(SCRIPT_DIR, "..", "resources")
DST = os.path.join(DST_DIR, "avatar.bin")


def crop_portrait_3_4(img):
    """Crop to 3:4 portrait ratio (centered)."""
    w, h = img.size
    target_ratio = 3 / 4  # width / height
    current_ratio = w / h
    if current_ratio > target_ratio:
        # Too wide — crop sides
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    else:
        # Too tall — crop top/bottom
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        return img.crop((0, top, w, top + new_h))


def rgb_to_565_be(r, g, b):
    """Convert RGB888 to BGR565 big-endian (for ILI9341 BGR panel)."""
    # ILI9341 with MADCTL_BGR: bits 15-11=Blue, 10-5=Green, 4-0=Red
    color = ((b & 0xF8) << 8) | ((g & 0xFC) << 3) | (r >> 3)
    return struct.pack(">H", color)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IMG

    if not os.path.exists(src):
        print(f"Error: Image not found: {src}")
        print(f"Usage: conda run -n badge-tools python {sys.argv[0]} <path_to_image>")
        sys.exit(1)

    print(f"Input:  {src}")
    print(f"Output: {DST}")

    # Open image (HEIC, PNG, JPG, etc.)
    img = Image.open(src)
    print(f"  Original: {img.size[0]}x{img.size[1]} {img.mode}")

    # Apply EXIF rotation (phones often store rotated images)
    img = ImageOps.exif_transpose(img)
    print(f"  After EXIF fix: {img.size[0]}x{img.size[1]}")

    # Convert to RGB
    img = img.convert("RGB")

    # Ensure portrait orientation (taller than wide)
    w, h = img.size
    if w > h:
        img = img.rotate(90, expand=True)
        print(f"  Rotated to portrait: {img.size[0]}x{img.size[1]}")

    # Crop to 3:4 portrait ratio
    img = crop_portrait_3_4(img)
    print(f"  Cropped:  {img.size[0]}x{img.size[1]}")

    # Resize to 80x80 with high-quality resampling
    img = img.resize((OUT_W, OUT_H), Image.LANCZOS)
    print(f"  Resized:  {img.size[0]}x{img.size[1]}")

    # Convert to RGB565
    pixels = list(img.getdata())
    rgb565_data = bytearray()
    for r, g, b in pixels:
        rgb565_data.extend(rgb_to_565_be(r, g, b))

    # Write binary: 2-byte LE width + 2-byte LE height + pixel data
    os.makedirs(DST_DIR, exist_ok=True)
    with open(DST, "wb") as f:
        f.write(struct.pack("<HH", OUT_W, OUT_H))
        f.write(rgb565_data)

    file_size = os.path.getsize(DST)
    print(f"\nSaved: {DST}")
    print(f"  Header: 4 bytes (width={OUT_W}, height={OUT_H})")
    print(f"  Pixels: {len(rgb565_data)} bytes")
    print(f"  Total:  {file_size} bytes")
    print(f"\nDeploy with:")
    print(f"  mpremote cp cyd-badge/resources/avatar.bin :resources/avatar.bin")


if __name__ == "__main__":
    main()
