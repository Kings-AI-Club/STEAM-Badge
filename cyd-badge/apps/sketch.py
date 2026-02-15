"""
Sketchy Sketch - Touch-based drawing app.

An Etch-A-Sketch style drawing app adapted for touchscreen.
Touch and drag to draw. Draws frame once, adds lines on touch.
Optimized for direct-draw mode.
"""
import gc
import time
from badge_os import (display, WIDTH, HEIGHT, rgb, BLACK, WHITE,
                      LIGHT_GREY, MID_GREY, DARK_GREY, TouchButton,
                      draw_back_button, check_back_button, request_menu)
from fonts import bitmap_font

# ─── Constants ──────────────────────────────────────────────────

CANVAS_X = 20
CANVAS_Y = 30
CANVAS_W = WIDTH - 40
CANVAS_H = HEIGHT - 60

FRAME_RED = rgb(170, 45, 40)
GOLD_LIGHT = rgb(240, 210, 160)
CANVAS_BG = rgb(210, 210, 210)
DRAW_COLOR = rgb(60, 60, 60)

# ─── State ──────────────────────────────────────────────────────

_last_touch = None
_clear_btn = None
_back_btn = None
_needs_full_draw = True


def init():
    """Initialize the sketch app."""
    global _last_touch, _clear_btn, _back_btn, _needs_full_draw

    gc.collect()
    _last_touch = None
    _needs_full_draw = True
    _clear_btn = TouchButton(WIDTH - 60, HEIGHT - 22, 50, 18, "Clear",
                             rgb(120, 40, 35))
    _back_btn = TouchButton(2, 2, 40, 18, "Menu", DARK_GREY)
    gc.collect()


def _draw_frame():
    """Draw the red toy frame, title, and canvas."""
    # Red frame background
    display.fill(FRAME_RED)

    # Title
    bitmap_font.draw_text(display, "Sketchy Sketch", 80, 6, GOLD_LIGHT)

    # Canvas
    display.fill_rect(CANVAS_X, CANVAS_Y, CANVAS_W, CANVAS_H, CANVAS_BG)

    # Dials (simple circles)
    display.fill_rect(8, HEIGHT - 22, 24, 20, rgb(200, 200, 210))
    display.fill_rect(WIDTH - 32, HEIGHT - 22, 24, 20, rgb(200, 200, 210))

    # Buttons
    _clear_btn.draw()
    _back_btn.draw()

    if display._full_fb:
        display.show()


def _draw_line_direct(x0, y0, x1, y1):
    """Draw a thick line on screen using Bresenham's algorithm."""
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    while True:
        # Draw 2x2 block for thickness
        display.fill_rect(CANVAS_X + x0 - 1, CANVAS_Y + y0 - 1,
                          3, 3, DRAW_COLOR)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy


def update(touch_pos):
    """Update and render the sketch app."""
    global _last_touch, _back_btn, _clear_btn, _needs_full_draw

    # Full draw on first frame
    if _needs_full_draw:
        _needs_full_draw = False
        _draw_frame()
        return None

    # In FB mode, redraw frame and canvas every frame
    if display._full_fb:
        _draw_frame()

    # Handle touch
    if touch_pos:
        tx, ty = touch_pos

        # Check buttons
        if _back_btn.check_touch(touch_pos):
            request_menu()
            return None

        if _clear_btn.check_touch(touch_pos):
            # Clear canvas
            display.fill_rect(CANVAS_X, CANVAS_Y,
                              CANVAS_W, CANVAS_H, CANVAS_BG)
            if display._full_fb:
                display.show()
            _last_touch = None
            return None

        # Convert to canvas coords and clamp
        cx = tx - CANVAS_X
        cy = ty - CANVAS_Y
        cx = max(2, min(CANVAS_W - 3, cx))
        cy = max(2, min(CANVAS_H - 3, cy))

        # Draw on canvas
        if _last_touch:
            _draw_line_direct(_last_touch[0], _last_touch[1], cx, cy)
        else:
            display.fill_rect(CANVAS_X + cx - 1, CANVAS_Y + cy - 1,
                              3, 3, DRAW_COLOR)

        _last_touch = (cx, cy)

        if display._full_fb:
            display.show()
    else:
        _last_touch = None

    return None
