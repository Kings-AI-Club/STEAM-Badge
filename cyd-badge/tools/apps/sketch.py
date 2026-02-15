"""
Sketchy Sketch - Touch-based drawing app.

An Etch-A-Sketch style drawing app adapted for touchscreen.
Touch and drag to draw. Features the classic red frame and
decorative dial graphics.

Adapted from the Tufty 2350 Badgerware sketchy_sketch app.
"""
import gc
import time
import math
from badge_os import (display, WIDTH, HEIGHT, rgb, BLACK, WHITE,
                      LIGHT_GREY, MID_GREY, TouchButton,
                      draw_back_button, check_back_button, request_menu)
from fonts import bitmap_font

# ─── Constants ──────────────────────────────────────────────────

# Canvas area (inside the red frame)
CANVAS_X = 20
CANVAS_Y = 30
CANVAS_W = WIDTH - 40
CANVAS_H = HEIGHT - 60

# Colors
FRAME_RED = rgb(170, 45, 40)
GOLD_LIGHT = rgb(240, 210, 160)
GOLD_DARK = rgb(190, 140, 80)
CANVAS_BG = rgb(210, 210, 210)
DRAW_COLOR = rgb(80, 80, 80)
CURSOR_COLOR = rgb(50, 50, 50)
DIAL_FACE = rgb(220, 220, 230)
DIAL_EDGE = rgb(150, 160, 170)
DIAL_TICK = rgb(190, 190, 220)

# ─── State ──────────────────────────────────────────────────────

# Canvas pixel buffer (1 bit per pixel to save memory, using bytearray)
_canvas_buf = None
_last_touch = None
_clear_btn = None
_back_btn = None


def init():
    """Initialize the sketch app."""
    global _canvas_buf, _last_touch, _clear_btn, _back_btn

    gc.collect()

    # Simple canvas buffer: store drawn pixels as a bytearray bitmap
    # Each byte holds 8 pixels (1 bit per pixel)
    bytes_per_row = (CANVAS_W + 7) // 8
    _canvas_buf = bytearray(bytes_per_row * CANVAS_H)

    _last_touch = None

    # Clear button
    _clear_btn = TouchButton(WIDTH - 60, HEIGHT - 22, 50, 18, "Clear",
                             rgb(120, 40, 35))

    _back_btn = draw_back_button()
    gc.collect()


def _get_pixel(x, y):
    """Get pixel state from canvas buffer."""
    if 0 <= x < CANVAS_W and 0 <= y < CANVAS_H:
        bytes_per_row = (CANVAS_W + 7) // 8
        byte_idx = y * bytes_per_row + x // 8
        bit_idx = 7 - (x % 8)
        return (_canvas_buf[byte_idx] >> bit_idx) & 1
    return 0


def _set_pixel(x, y):
    """Set pixel in canvas buffer."""
    if 0 <= x < CANVAS_W and 0 <= y < CANVAS_H:
        bytes_per_row = (CANVAS_W + 7) // 8
        byte_idx = y * bytes_per_row + x // 8
        bit_idx = 7 - (x % 8)
        _canvas_buf[byte_idx] |= (1 << bit_idx)


def _draw_line_on_canvas(x0, y0, x1, y1):
    """Draw a line on the canvas buffer using Bresenham's algorithm."""
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    while True:
        # Draw a 2x2 block for thicker lines
        for ox in range(-1, 2):
            for oy in range(-1, 2):
                _set_pixel(x0 + ox, y0 + oy)

        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy


def _draw_frame():
    """Draw the red toy frame and title."""
    # Red frame background
    display.fill(FRAME_RED)

    # Title - embossed gold text
    title = "Sketchy Sketch"
    tw = bitmap_font.measure_text(title)
    tx = (WIDTH - tw) // 2
    bitmap_font.draw_text(display, title, tx - 1, 5, GOLD_LIGHT)
    bitmap_font.draw_text(display, title, tx, 6, GOLD_DARK)

    # Canvas area background
    display.rounded_rect(CANVAS_X - 3, CANVAS_Y - 3,
                         CANVAS_W + 6, CANVAS_H + 6, 4, rgb(140, 30, 25))
    display.rounded_rect(CANVAS_X, CANVAS_Y, CANVAS_W, CANVAS_H, 3,
                         CANVAS_BG)

    # Screen edge shadows
    display.fill_rect(CANVAS_X + 2, CANVAS_Y, CANVAS_W - 4, 2,
                      rgb(180, 180, 180))
    display.fill_rect(CANVAS_X, CANVAS_Y + 2, 2, CANVAS_H - 4,
                      rgb(180, 180, 180))

    # Highlights
    display.vline(CANVAS_X - 4, CANVAS_Y + 5, CANVAS_H - 10,
                  rgb(200, 80, 75))
    display.vline(CANVAS_X + CANVAS_W + 3, CANVAS_Y + 5, CANVAS_H - 10,
                  rgb(200, 80, 75))


def _draw_canvas():
    """Render the canvas buffer to the display."""
    bytes_per_row = (CANVAS_W + 7) // 8
    for y in range(CANVAS_H):
        for x in range(CANVAS_W):
            byte_idx = y * bytes_per_row + x // 8
            bit_idx = 7 - (x % 8)
            if (_canvas_buf[byte_idx] >> bit_idx) & 1:
                display.pixel(CANVAS_X + x, CANVAS_Y + y, DRAW_COLOR)


def _draw_dial(x, y, angle):
    """Draw a decorative Etch-A-Sketch dial knob."""
    radius = 12

    # Shadow
    display.fill_circle(x + 2, y, radius + 1, rgb(100, 20, 15))

    # Dial edge (shaft)
    display.fill_circle(x + 1, y, radius, DIAL_EDGE)

    # Dial face
    display.fill_circle(x, y, radius, DIAL_FACE)

    # Tick marks
    ticks = 12
    for i in range(ticks):
        deg = angle + i * (360 // ticks)
        r = deg * math.pi / 180.0
        ox = int(math.sin(r) * radius)
        oy = int(math.cos(r) * radius)
        ix = int(math.sin(r) * (radius - 3))
        iy = int(math.cos(r) * (radius - 3))
        display.line(x + ix, y + iy, x + ox, y + oy, DIAL_TICK)


def _draw_cursor(cx, cy):
    """Draw a crosshair cursor on the canvas."""
    ticks = time.ticks_ms()
    intensity = int(abs(math.sin(ticks / 150.0)) * 80) + 40
    cursor_c = rgb(intensity, intensity, intensity)

    sx = CANVAS_X + cx
    sy = CANVAS_Y + cy

    # Crosshair
    display.hline(sx + 2, sy, 3, cursor_c)
    display.hline(sx - 4, sy, 3, cursor_c)
    display.vline(sx, sy + 2, 3, cursor_c)
    display.vline(sx, sy - 4, 3, cursor_c)


def update(touch_pos):
    """Update and render the sketch app."""
    global _last_touch, _back_btn, _clear_btn

    # Draw the frame and canvas
    _draw_frame()
    _draw_canvas()

    # Dials at bottom corners
    _draw_dial(18, HEIGHT - 12, int(time.ticks_ms() / 50) % 360)
    _draw_dial(WIDTH - 18, HEIGHT - 12, -int(time.ticks_ms() / 50) % 360)

    # Clear button
    _clear_btn.draw()

    # Back button
    _back_btn = draw_back_button()

    # Handle touch
    if touch_pos:
        tx, ty = touch_pos

        # Check back button
        if check_back_button(touch_pos, _back_btn):
            return None

        # Check clear button
        if _clear_btn.check_touch(touch_pos):
            for i in range(len(_canvas_buf)):
                _canvas_buf[i] = 0
            _last_touch = None
            return None

        # Convert screen coords to canvas coords
        cx = tx - CANVAS_X
        cy = ty - CANVAS_Y

        # Clamp to canvas bounds
        cx = max(1, min(CANVAS_W - 2, cx))
        cy = max(1, min(CANVAS_H - 2, cy))

        # Draw on canvas
        if _last_touch:
            _draw_line_on_canvas(_last_touch[0], _last_touch[1], cx, cy)
        else:
            _set_pixel(cx, cy)

        _last_touch = (cx, cy)

        # Show cursor
        _draw_cursor(cx, cy)
    else:
        _last_touch = None

        # Show a default cursor in center if no touch history
        _draw_cursor(CANVAS_W // 2, CANVAS_H // 2)

    return None
