"""
Badge App - Conference Name Badge Display.

Shows your name, role, and avatar on an ID card.
Touch the card to flip and show social handles.
Touch left/right edges to cycle background color.

Optimized for both framebuffer and direct-draw modes.
"""
import gc
import time
from badge_os import (display, WIDTH, HEIGHT, rgb, BLACK, WHITE,
                      DARK_BG, MID_GREY, LIGHT_GREY,
                      load_image, draw_image, TouchButton, draw_back_button,
                      check_back_button, request_menu)
from fonts import bitmap_font
import badge_config

# ─── State ──────────────────────────────────────────────────────

CX = WIDTH // 2
CY = HEIGHT // 2

avatar_img = None
back_btn = None
hue = 180
rear_view = False
_needs_redraw = True
_last_touch_time = 0


def _hue_to_rgb565(hue_val):
    """Convert a hue (0-360) to a soft RGB565 color."""
    h = hue_val % 360
    s = 0.4
    v = 0.95
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return rgb(int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))


def init():
    """Initialize badge app."""
    global avatar_img, back_btn, _needs_redraw

    gc.collect()

    try:
        avatar_img = load_image("resources/avatar.bin")
    except OSError:
        avatar_img = None

    _needs_redraw = True
    gc.collect()


def _draw_card_front(card_x, card_y, card_w, card_h):
    """Draw the front of the ID card."""
    # Shadow + body
    display.fill_rect(card_x + 4, card_y + 4, card_w, card_h, rgb(30, 30, 30))
    display.fill_rect(card_x, card_y, card_w, card_h, WHITE)

    # Avatar
    if avatar_img:
        img_w, img_h, _ = avatar_img
        ax = card_x + (card_w - img_w) // 2
        ay = card_y + 8
        draw_image(ax, ay, avatar_img)
        name_y = ay + img_h + 4
    else:
        display.fill_rect(card_x + card_w // 2 - 25, card_y + 15, 50, 50,
                          rgb(100, 130, 180))
        name_y = card_y + 72

    # Name
    name = badge_config.NAME
    tw = bitmap_font.measure_text(name)
    nx = card_x + (card_w - tw) // 2
    bitmap_font.draw_text(display, name, nx, name_y, BLACK)

    # Role
    role = badge_config.ROLE
    rw = display.text_width(role)
    rx = card_x + (card_w - rw) // 2
    display.text(role, rx, name_y + 20, MID_GREY)


def _draw_card_back(card_x, card_y, card_w, card_h):
    """Draw the back of the ID card (social handles)."""
    display.fill_rect(card_x + 4, card_y + 4, card_w, card_h, rgb(30, 30, 30))
    display.fill_rect(card_x, card_y, card_w, card_h, WHITE)

    bitmap_font.draw_text(display, "Socials", card_x + 10, card_y + 10, BLACK)
    display.fill_rect(card_x + 8, card_y + 28, card_w - 16, 1, MID_GREY)

    sy = card_y + 35
    for platform, handle in badge_config.SOCIALS.items():
        if sy + 20 > card_y + card_h - 5:
            break
        display.text(platform, card_x + 15, sy, MID_GREY)
        display.text(handle, card_x + 15, sy + 10, BLACK)
        sy += 28


def _draw_full():
    """Draw the complete badge screen."""
    global back_btn

    bg = _hue_to_rgb565(hue)
    display.fill(bg)

    back_btn = draw_back_button()

    card_w = 180
    card_h = 190
    card_x = CX - card_w // 2
    card_y = 25

    if rear_view:
        _draw_card_back(card_x, card_y, card_w, card_h)
    else:
        _draw_card_front(card_x, card_y, card_w, card_h)

    display.text("Tap card to flip", CX - 64, HEIGHT - 16, WHITE)

    if display._full_fb:
        display.show()


def update(touch_pos):
    """Update and render the badge display."""
    global hue, rear_view, back_btn, _last_touch_time, _needs_redraw

    ticks = time.ticks_ms()

    # Full redraw on first frame or after state change
    if _needs_redraw:
        _needs_redraw = False
        _draw_full()
        return None

    # In FB mode, redraw every frame
    if display._full_fb:
        _draw_full()

    # Handle touch
    if touch_pos:
        if time.ticks_diff(ticks, _last_touch_time) < 400:
            return None
        _last_touch_time = ticks

        tx, ty = touch_pos

        if check_back_button(touch_pos, back_btn):
            return None

        card_x = CX - 90
        card_y = 25
        card_w = 180
        card_h = 190

        if card_x <= tx <= card_x + card_w and card_y <= ty <= card_y + card_h:
            rear_view = not rear_view
            _needs_redraw = True
            return None

        if tx < 40:
            hue = (hue - 15) % 360
            _needs_redraw = True
        elif tx > WIDTH - 40:
            hue = (hue + 15) % 360
            _needs_redraw = True

    return None
