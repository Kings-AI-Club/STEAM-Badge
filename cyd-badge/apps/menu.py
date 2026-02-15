"""
Menu / App Launcher for ESP32 CYD Badge.

90s hacker terminal aesthetic. Single tap to launch apps.
"""
import gc
import time
from badge_os import (display, touch, WIDTH, HEIGHT, rgb, BLACK, WHITE,
                      ORANGE, BLUE, GREEN, DARK_GREY, MID_GREY,
                      LIGHT_GREY, TouchButton)
from fonts import bitmap_font

# ─── App definitions ────────────────────────────────────────────

APPS = [
    {"name": "Badge", "module": "badge", "color": rgb(0, 255, 100)},
    {"name": "Sketch", "module": "sketch", "color": rgb(0, 200, 255)},
    {"name": "Pong", "module": "pong", "color": rgb(255, 50, 50)},
    {"name": "Term", "module": "terminal", "color": rgb(200, 200, 0)},
]

# ─── 90s Hacker Colors ─────────────────────────────────────────

TERM_GREEN = rgb(0, 255, 80)
TERM_DIM = rgb(0, 120, 40)
TERM_DARK = rgb(0, 40, 15)
TERM_BG = rgb(2, 8, 4)
SCANLINE = rgb(0, 15, 5)
BORDER_GREEN = rgb(0, 180, 60)

# ─── Layout ─────────────────────────────────────────────────────

COLS = 4
TILE_W = 64
TILE_H = 70
TILE_PAD = 10
GRID_X = (WIDTH - (COLS * TILE_W + (COLS - 1) * TILE_PAD)) // 2
GRID_Y = 70

APP_BUTTONS = []
_needs_full_draw = True
_touch_debounce = 0


def _draw_scanlines():
    """Draw subtle CRT scanlines over the background."""
    for y in range(0, HEIGHT, 4):
        display.hline(0, y, WIDTH, SCANLINE)


def _draw_tile(i):
    """Draw a single app tile with terminal hacker style."""
    btn = APP_BUTTONS[i]
    app = APPS[i]

    # Terminal-style border
    display.fill_rect(btn.x, btn.y, btn.w, btn.h, TERM_DARK)
    display.rect(btn.x, btn.y, btn.w, btn.h, TERM_DIM)

    # Icon area
    icon_cx = btn.x + btn.w // 2
    icon_cy = btn.y + 20

    if app["module"] == "badge":
        # ID card icon
        display.rect(icon_cx - 12, icon_cy - 8, 24, 16, TERM_GREEN)
        display.fill_rect(icon_cx - 8, icon_cy - 4, 6, 6, TERM_DIM)
        display.hline(icon_cx + 1, icon_cy - 3, 8, TERM_GREEN)
        display.hline(icon_cx + 1, icon_cy + 1, 8, TERM_GREEN)
    elif app["module"] == "sketch":
        # Pencil icon
        display.rect(icon_cx - 10, icon_cy - 8, 20, 16, rgb(0, 200, 255))
        display.line(icon_cx - 5, icon_cy + 4, icon_cx + 5, icon_cy - 6,
                     rgb(0, 200, 255))
    elif app["module"] == "pong":
        # Pong icon
        display.fill_rect(icon_cx - 3, icon_cy - 3, 6, 6, rgb(255, 50, 50))
        display.fill_rect(icon_cx - 14, icon_cy - 6, 3, 12, rgb(255, 50, 50))
        display.fill_rect(icon_cx + 11, icon_cy - 6, 3, 12, rgb(255, 50, 50))
    elif app["module"] == "terminal":
        # Terminal icon
        display.rect(icon_cx - 12, icon_cy - 8, 24, 16, rgb(200, 200, 0))
        display.text(">_", icon_cx - 8, icon_cy - 4, rgb(200, 200, 0))

    # Label
    tw = bitmap_font.measure_text(app["name"])
    tx = btn.x + (btn.w - tw) // 2
    ty = btn.y + btn.h - 18
    bitmap_font.draw_text(display, app["name"], tx, ty, app["color"])


def _draw_full_screen():
    """Draw the complete menu screen."""
    # Dark background
    display.fill(TERM_BG)

    # Scanlines
    _draw_scanlines()

    # Top border line
    display.hline(0, 0, WIDTH, BORDER_GREEN)
    display.hline(0, 1, WIDTH, TERM_DARK)

    # Header — terminal prompt style
    bitmap_font.draw_text(display, "> BadgeOS v1.0", 6, 6, TERM_GREEN)
    display.text("Made by King's AI Seminar!", 6, 24, TERM_DIM)

    # Blinking cursor effect (static underscore)
    tw = bitmap_font.measure_text("> BadgeOS v1.0")
    display.fill_rect(6 + tw + 2, 6, 8, 14, TERM_GREEN)

    # Separator
    for x in range(0, WIDTH, 4):
        display.fill_rect(x, 44, 2, 1, TERM_DIM)

    # Status bar text
    display.text("SYS:OK  MEM:FREE  TOUCH:ON", 6, 50, TERM_DARK)

    # Draw all tiles
    for i in range(len(APPS)):
        _draw_tile(i)

    # Bottom border
    display.hline(0, HEIGHT - 2, WIDTH, BORDER_GREEN)
    display.hline(0, HEIGHT - 1, WIDTH, TERM_DARK)

    # Footer
    display.text("[SELECT APP]", WIDTH // 2 - 48, HEIGHT - 16, TERM_DIM)

    if display._full_fb:
        display.show()


def init():
    """Initialize menu state."""
    global APP_BUTTONS, _needs_full_draw

    _needs_full_draw = True
    APP_BUTTONS.clear()

    for i, app in enumerate(APPS):
        col = i % COLS
        row = i // COLS
        x = GRID_X + col * (TILE_W + TILE_PAD)
        y = GRID_Y + row * (TILE_H + TILE_PAD)
        APP_BUTTONS.append(TouchButton(x, y, TILE_W, TILE_H,
                                       app["name"], app["color"]))

    gc.collect()


def update(touch_pos):
    """Update and render the menu."""
    global _needs_full_draw, _touch_debounce

    ticks = time.ticks_ms()

    # Full redraw on first frame
    if _needs_full_draw:
        _needs_full_draw = False
        _draw_full_screen()
        return None

    # In framebuffer mode, redraw every frame
    if display._full_fb:
        _draw_full_screen()

    # Handle touch — single tap to launch
    if touch_pos and time.ticks_diff(ticks, _touch_debounce) > 400:
        for i, btn in enumerate(APP_BUTTONS):
            if btn.check_touch(touch_pos):
                _touch_debounce = ticks
                return APPS[i]["module"]

    return None
