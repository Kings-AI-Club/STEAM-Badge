"""
Image converter: Extracts the LVGL C image array from the working-badge
project and converts it to a raw RGB565 .bin file for MicroPython.

Run this script on your desktop (not on the ESP32!):
    python3 tools/convert_avatar.py

It will create: resources/avatar.bin (80x80 RGB565, 12800 bytes)
"""

import os
import re
import struct

# Source file path (relative to repo root)
SRC = os.path.join(os.path.dirname(__file__), "..", "..",
                   "working-badge", "lib", "ui", "ui_img_1147937936.c")
DST_DIR = os.path.join(os.path.dirname(__file__), "..", "resources")
DST = os.path.join(DST_DIR, "avatar.bin")

# Image dimensions (from the LVGL descriptor)
WIDTH = 80
HEIGHT = 80
PIXELS = WIDTH * HEIGHT  # 6400


def extract_bytes_from_c(filepath):
    """Parse the C array and extract all hex bytes."""
    with open(filepath, "r") as f:
        content = f.read()

    # Find all hex byte values in the array
    hex_values = re.findall(r'0x([0-9a-fA-F]{2})', content)
    return bytes(int(h, 16) for h in hex_values)


def convert_rgb565a8_to_rgb565(raw_data, num_pixels):
    """
    LVGL RGB565A8 format: first num_pixels*2 bytes are RGB565,
    followed by num_pixels bytes of alpha.
    We extract just the RGB565 portion.
    """
    rgb565_size = num_pixels * 2
    if len(raw_data) < rgb565_size:
        print(f"Warning: data size {len(raw_data)} < expected {rgb565_size}")
        return raw_data[:len(raw_data)]

    rgb565_data = raw_data[:rgb565_size]
    alpha_data = raw_data[rgb565_size:rgb565_size + num_pixels]

    # For pixels with alpha=0, replace with black (transparent -> black)
    result = bytearray(rgb565_size)
    for i in range(num_pixels):
        alpha = alpha_data[i] if i < len(alpha_data) else 255
        if alpha > 128:
            # Keep the pixel
            result[i * 2] = rgb565_data[i * 2]
            result[i * 2 + 1] = rgb565_data[i * 2 + 1]
        else:
            # Transparent -> black
            result[i * 2] = 0
            result[i * 2 + 1] = 0

    return bytes(result)


def main():
    print(f"Reading LVGL image from: {SRC}")

    if not os.path.exists(SRC):
        print(f"Error: Source file not found: {SRC}")
        return

    raw = extract_bytes_from_c(SRC)
    print(f"Extracted {len(raw)} bytes from C array")
    print(f"Expected: {PIXELS * 3} bytes (RGB565A8 for {WIDTH}x{HEIGHT})")

    rgb565 = convert_rgb565a8_to_rgb565(raw, PIXELS)
    print(f"Converted to RGB565: {len(rgb565)} bytes")

    os.makedirs(DST_DIR, exist_ok=True)

    # Write header + pixel data
    # Header: 2 bytes width (LE) + 2 bytes height (LE) + pixel data
    with open(DST, "wb") as f:
        f.write(struct.pack("<HH", WIDTH, HEIGHT))
        f.write(rgb565)

    print(f"Saved to: {DST}")
    print(f"File size: {os.path.getsize(DST)} bytes")
    print(f"(4 byte header + {len(rgb565)} bytes pixel data)")


if __name__ == "__main__":
    main()
