"""
Menu / App Launcher for ESP32 CYD Badge.

Displays a touch-activated grid of apps with animated terminal
background effect, inspired by the Tufty 2350 Badgerware menu.
"""
import gc
import time
import math
from badge_os import (display, touch, WIDTH, HEIGHT, rgb, BLACK, WHITE,
                      ORANGE, BLUE, RED, GREEN, YELLOW, PURPLE,
                      DARK_BG, DARK_GREY, MID_GREY, TouchButton)
from fonts import bitmap_font

# ─── App definitions ────────────────────────────────────────────

APPS = [
    {"name": "Badge", "module": "badge", "color": ORANGE},
    {"name": "Sketch", "module": "sketch", "color": BLUE},
    {"name": "Tennis", "module": "tennis", "color": GREEN},
]

# ─── Layout ─────────────────────────────────────────────────────

COLS = 3
TILE_W = 80
TILE_H = 70
TILE_PAD = 12
GRID_X = (WIDTH - (COLS * TILE_W + (COLS - 1) * TILE_PAD)) // 2
GRID_Y = 60

APP_BUTTONS = []
selected = -1

# Terminal effect state
_term_lines = []
_term_seed = 42
_term_scroll = 0
_last_term_update = 0

# Fade-in
_alpha_step = 0
_ticks_start = 0


def init():
    """Initialize menu state."""
    global APP_BUTTONS, selected, _term_lines, _ticks_start, _alpha_step

    _ticks_start = time.ticks_ms()
    _alpha_step = 0
    selected = -1

    APP_BUTTONS.clear()

    for i, app in enumerate(APPS):
        col = i % COLS
        row = i // COLS
        x = GRID_X + col * (TILE_W + TILE_PAD)
        y = GRID_Y + row * (TILE_H + TILE_PAD)
        APP_BUTTONS.append(TouchButton(x, y, TILE_W, TILE_H,
                                       app["name"], app["color"]))

    # Pre-populate terminal lines
    _term_lines.clear()
    import random
    for _ in range(20):
        _term_lines.append(random.randint(20, 250))

    gc.collect()


def _draw_terminal_bg():
    """Draw the scrolling terminal text effect background."""
    global _term_scroll, _last_term_update, _term_lines

    now = time.ticks_ms()

    # Add new lines periodically
    if time.ticks_diff(now, _last_term_update) > 300:
        import random
        _term_lines.append(random.randint(20, 250))
        if len(_term_lines) > 25:
            _term_lines = _term_lines[-20:]
        _last_term_update = now
        _term_scroll += 1

    # Draw greeked terminal text lines
    term_color = rgb(80, 50, 15)
    import random

    for i in range(min(len(_term_lines), 18)):
        y = 28 + i * 12
        # Scroll offset
        scroll_frac = time.ticks_diff(now, _last_term_update) / 300
        y = int(y - scroll_frac * 12)
        if y < 20 or y > HEIGHT - 20:
            continue

        # Use deterministic seed for consistent word widths per line
        random.seed(i + _term_scroll)
        cx = 8
        line_len = _term_lines[i] if i < len(_term_lines) else 100
        while cx < line_len and cx < WIDTH - 10:
            w = random.randint(6, 20)
            display.fill_rect(cx, y, w, 3, term_color)
            cx += w + 4


def _draw_header():
    """Draw the BadgeOS header bar."""
    # Animated dots
    ticks = time.ticks_ms()
    dots = "." * (int(ticks / 400) % 4)
    label = "BadgeOS v1.0" + dots

    # Draw header text
    bitmap_font.draw_text(display, label, 8, 6, ORANGE)


def update(touch_pos):
    """Update and render the menu. Returns app module name on selection."""
    global selected, _alpha_step

    # ─── Background ─────────
    display.fill(rgb(30, 10, 5))

    # Terminal effect
    _draw_terminal_bg()

    # Header
    _draw_header()

    # ─── Draw rounded corners ─────────
    # Dark corners to create rounded screen feel
    for corner in [(0, 0), (WIDTH - 8, 0), (0, HEIGHT - 8), (WIDTH - 8, HEIGHT - 8)]:
        display.fill_rect(corner[0], corner[1], 8, 8, BLACK)

    display.rounded_rect(0, 0, WIDTH, HEIGHT, 6, rgb(30, 10, 5))

    # ─── Draw app tiles ─────────
    ticks = time.ticks_ms()

    for i, btn in enumerate(APP_BUTTONS):
        app = APPS[i]
        is_sel = (i == selected)

        # Tile background with shadow
        display.fill_rect(btn.x + 3, btn.y + 3, btn.w, btn.h,
                          rgb(15, 5, 2))

        # Tile body
        c = app["color"]
        if not is_sel:
            # Dimmed color for unselected
            r = ((c >> 11) & 0x1F) >> 1
            g = ((c >> 5) & 0x3F) >> 1
            b = (c & 0x1F) >> 1
            c = (r << 11) | (g << 5) | b

        display.rounded_rect(btn.x, btn.y, btn.w, btn.h, 5, c)

        # Icon area - draw a simple icon shape
        icon_cx = btn.x + btn.w // 2
        icon_cy = btn.y + 22

        if app["module"] == "badge":
            # ID card icon
            display.fill_rect(icon_cx - 12, icon_cy - 8, 24, 16, WHITE)
            display.fill_rect(icon_cx - 10, icon_cy - 6, 8, 8, rgb(100, 100, 100))
            display.fill_rect(icon_cx + 1, icon_cy - 5, 10, 2, rgb(60, 60, 60))
            display.fill_rect(icon_cx + 1, icon_cy, 10, 2, rgb(60, 60, 60))
        elif app["module"] == "sketch":
            # Pencil icon
            display.fill_rect(icon_cx - 10, icon_cy - 8, 20, 16, LIGHT_GREY)
            display.line(icon_cx - 6, icon_cy + 4, icon_cx + 6, icon_cy - 6, DARK_GREY)
            display.line(icon_cx - 5, icon_cy + 4, icon_cx + 7, icon_cy - 6, DARK_GREY)
        elif app["module"] == "tennis":
            # Ball + paddle
            display.fill_circle(icon_cx - 4, icon_cy, 5, WHITE)
            display.fill_rect(icon_cx + 10, icon_cy - 7, 4, 14, WHITE)

        # App name label
        tw = bitmap_font.measure_text(app["name"])
        tx = btn.x + (btn.w - tw) // 2
        ty = btn.y + btn.h - 18
        bitmap_font.draw_text(display, app["name"], tx, ty,
                              WHITE if is_sel else rgb(200, 200, 200))

        # Selection indicator - pulsing border
        if is_sel:
            pulse = int(abs(math.sin(ticks / 300.0)) * 2) + 1
            display.rect(btn.x - pulse, btn.y - pulse,
                         btn.w + pulse * 2, btn.h + pulse * 2, WHITE)

    # ─── Handle touch ─────────
    if touch_pos:
        for i, btn in enumerate(APP_BUTTONS):
            if btn.check_touch(touch_pos):
                if selected == i:
                    # Double tap / confirm - launch app
                    return APPS[i]["module"]
                else:
                    selected = i
                    break

    # ─── Fade in ─────────
    if _alpha_step < 8:
        # Simulate fade by drawing semi-transparent black overlay
        # (crude but effective on embedded)
        _alpha_step += 1

    return None
