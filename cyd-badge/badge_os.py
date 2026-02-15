"""
Badge OS - Core framework for ESP32 CYD Conference Badge.

Provides hardware initialization, display/touch singletons,
color utilities, image loading, touch button abstraction,
state management, and the main app run loop.

Supports both framebuffer mode (fast, if RAM available) and
direct-draw mode (works on ESP32 without PSRAM).
"""

import gc
import json
import os
import time
import struct

gc.collect()

from drivers.ili9341 import ILI9341, color565
from drivers.xpt2046 import XPT2046

# ─── Hardware Singletons ────────────────────────────────────────

display = None
touch = None

# ─── Constants ──────────────────────────────────────────────────

WIDTH = 320
HEIGHT = 240

# Common colors (RGB565, pre-swapped by color565)
BLACK = color565(0, 0, 0)
WHITE = color565(255, 255, 255)
RED = color565(230, 60, 46)
GREEN = color565(9, 183, 117)
BLUE = color565(28, 181, 202)
YELLOW = color565(246, 167, 4)
ORANGE = color565(246, 135, 4)
PURPLE = color565(188, 96, 208)
DARK_BG = color565(20, 40, 60)
DARK_GREY = color565(40, 40, 40)
MID_GREY = color565(100, 100, 100)
LIGHT_GREY = color565(200, 200, 200)


def rgb(r, g, b):
    """Shorthand for color565."""
    return color565(r, g, b)


# ─── Hardware Init ──────────────────────────────────────────────

def init_hardware():
    """Initialize display and touch hardware."""
    global display, touch

    gc.collect()

    # Initialize ILI9341 display
    display = ILI9341(rotation=3)
    gc.collect()

    # Initialize XPT2046 touch
    touch = XPT2046(rotation=3)

    # Clear screen
    display.fill(BLACK)
    if display._full_fb:
        display.show()

    gc.collect()
    return display, touch


# ─── Image Loading ──────────────────────────────────────────────

def load_image(filepath):
    """
    Load a raw RGB565 image from a .bin file.
    Format: 2 bytes width (LE) + 2 bytes height (LE) + pixel data
    Returns: (width, height, pixel_data_bytes)
    """
    with open(filepath, "rb") as f:
        header = f.read(4)
        w, h = struct.unpack("<HH", header)
        data = f.read(w * h * 2)
    return w, h, data


def draw_image(x, y, img_data):
    """Draw a loaded image on screen."""
    w, h, data = img_data
    if display._full_fb:
        idx = 0
        for py in range(h):
            for px in range(w):
                if idx + 1 < len(data):
                    c = data[idx] | (data[idx + 1] << 8)
                    if c != 0:
                        display.pixel(x + px, y + py, c)
                idx += 2
    else:
        # Direct mode: blit the buffer directly
        display.blit_buffer(data, x, y, w, h)


# ─── Touch Button Abstraction ──────────────────────────────────

class TouchButton:
    """A rectangular touch zone on screen."""

    def __init__(self, x, y, w, h, label="", color=None):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.label = label
        self.color = color or MID_GREY

    def contains(self, tx, ty):
        """Check if touch coordinates are within this button."""
        return (self.x <= tx <= self.x + self.w and
                self.y <= ty <= self.y + self.h)

    def draw(self, active=False):
        """Draw the button on screen."""
        c = WHITE if active else self.color
        display.fill_rect(self.x, self.y, self.w, self.h, c)
        if self.label:
            tw = display.text_width(self.label)
            tx = self.x + (self.w - tw) // 2
            ty = self.y + (self.h - 8) // 2
            display.text(self.label, tx, ty, BLACK if active else WHITE)

    def check_touch(self, touch_pos):
        """Check if a touch position hits this button."""
        if touch_pos is None:
            return False
        return self.contains(touch_pos[0], touch_pos[1])


# ─── State Management ──────────────────────────────────────────

class State:
    """Persistent JSON state storage on the filesystem."""

    @staticmethod
    def _ensure_dir():
        try:
            os.stat("/state")
        except OSError:
            os.mkdir("/state")

    @staticmethod
    def save(app_name, data):
        State._ensure_dir()
        try:
            with open("/state/{}.json".format(app_name), "w") as f:
                f.write(json.dumps(data))
        except OSError:
            pass

    @staticmethod
    def load(app_name, defaults=None):
        if defaults is None:
            defaults = {}
        try:
            with open("/state/{}.json".format(app_name), "r") as f:
                data = json.loads(f.read())
                if isinstance(data, dict):
                    defaults.update(data)
        except (OSError, ValueError):
            pass
        return defaults


# ─── App Runner ─────────────────────────────────────────────────

_back_to_menu = False


def request_menu():
    """Request to go back to menu from within an app."""
    global _back_to_menu
    _back_to_menu = True


def run_app(update_fn, init_fn=None, target_fps=20):
    """
    Main app run loop.
    - update_fn(touch_pos): called every frame with current touch pos
      Should return a string (app path to launch) or None to continue.
    - init_fn: optional initialization function called once.
    - target_fps: target frame rate (lower = less CPU usage)
    """
    global _back_to_menu
    _back_to_menu = False

    frame_ms = 1000 // target_fps

    if init_fn:
        init_fn()
        gc.collect()

    try:
        while not _back_to_menu:
            start = time.ticks_ms()

            # Poll touch
            touch_pos = touch.get_touch() if touch else None

            # Update app
            result = update_fn(touch_pos)

            # Flush framebuffer to screen (no-op in direct mode)
            if display._full_fb:
                display.show()

            if result is not None:
                gc.collect()
                return result

            # Frame timing
            elapsed = time.ticks_diff(time.ticks_ms(), start)
            if elapsed < frame_ms:
                time.sleep_ms(frame_ms - elapsed)

            gc.collect()

    except KeyboardInterrupt:
        raise  # Let it propagate to main.py for REPL access
    except Exception as e:
        import sys
        sys.print_exception(e)
        display.fill(RED)
        display.text("ERROR:", 10, 10, WHITE)
        display.text(str(e)[:35], 10, 25, WHITE)
        if display._full_fb:
            display.show()
        time.sleep(3)

    gc.collect()
    return None


# ─── Utility Drawing ───────────────────────────────────────────

def center_text(text, y, color=WHITE, scale=1):
    """Draw text centered horizontally on screen."""
    from fonts.bitmap_font import measure_text, draw_text
    tw = measure_text(text, scale)
    x = (WIDTH - tw) // 2
    draw_text(display, text, x, y, color, scale)


def draw_back_button():
    """Draw a small back/menu button in the top-left corner."""
    btn = TouchButton(2, 2, 40, 18, "Menu", DARK_GREY)
    btn.draw()
    return btn


def check_back_button(touch_pos, btn):
    """Check if back button was pressed."""
    if btn and btn.check_touch(touch_pos):
        request_menu()
        return True
    return False
