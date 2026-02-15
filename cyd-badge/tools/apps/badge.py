"""
Badge App - Conference Name Badge Display.

Shows your name, role, and avatar on an ID card with animated
ripple background. Touch to flip the card to show social handles.
Touch left/right edges to cycle background hue.

Adapted from the Tufty 2350 Badgerware badge app.
"""
import gc
import time
import math
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

# Card state
hue = 180
rear_view = False
flip_start = 0
flipping = False

# Touch debounce
_last_touch_time = 0


def init():
    """Initialize badge app."""
    global avatar_img, back_btn

    gc.collect()

    # Load avatar image
    try:
        avatar_img = load_image("resources/avatar.bin")
    except OSError:
        avatar_img = None

    back_btn = draw_back_button()
    gc.collect()


def _hue_to_rgb565(hue_val):
    """Convert a hue (0-360) to RGB565 color."""
    h = hue_val % 360
    s = 0.4  # low saturation for soft background
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


def _draw_ripple_bg(bg_color):
    """Draw animated ripple dot pattern background."""
    ticks = time.ticks_ms()

    # Fill with background
    display.fill(bg_color)

    # Draw ripple grid
    grid_size = 20
    for gy in range(0, HEIGHT, grid_size):
        for gx in range(0, WIDTH, grid_size):
            # Distance from center
            dx = gx + grid_size // 2 - CX
            dy = gy + grid_size // 2 - CY
            dist = math.sqrt(dx * dx + dy * dy)

            # Pulsing wave
            pulse = (math.sin(-ticks / 500.0 + dist / 40.0) + 1) / 2
            brightness = int(20 + pulse * 30)

            dot_color = rgb(brightness, brightness, brightness)
            display.fill_rect(gx + 7, gy + 7, 6, 6, dot_color)


def _draw_card_front(card_x, card_y, card_w, card_h):
    """Draw the front of the ID card (photo + name + role)."""
    # Card body with shadow
    display.fill_rect(card_x + 4, card_y + 4, card_w, card_h,
                      rgb(30, 30, 30))
    display.rounded_rect(card_x, card_y, card_w, card_h, 6, WHITE)

    # Draw avatar
    if avatar_img:
        img_w, img_h, _ = avatar_img
        ax = card_x + (card_w - img_w) // 2
        ay = card_y + 8
        draw_image(ax, ay, avatar_img)
        name_y = ay + img_h + 4
    else:
        # Placeholder avatar circle
        display.fill_circle(card_x + card_w // 2, card_y + 40, 25,
                            rgb(100, 130, 180))
        display.fill_circle(card_x + card_w // 2, card_y + 32, 10,
                            rgb(200, 180, 160))
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
    display.text(role, rx, name_y + 20, rgb(80, 80, 80))


def _draw_card_back(card_x, card_y, card_w, card_h):
    """Draw the back of the ID card (social handles)."""
    # Card body with shadow
    display.fill_rect(card_x + 4, card_y + 4, card_w, card_h,
                      rgb(30, 30, 30))
    display.rounded_rect(card_x, card_y, card_w, card_h, 6, WHITE)

    # Title
    bitmap_font.draw_text(display, "Socials", card_x + 10, card_y + 10,
                          BLACK)
    display.hline(card_x + 8, card_y + 28, card_w - 16, MID_GREY)

    # Social handles
    sy = card_y + 35
    for platform, handle in badge_config.SOCIALS.items():
        if sy + 20 > card_y + card_h - 5:
            break

        # Platform icon placeholder (colored dot)
        colors = {
            "GitHub": rgb(50, 50, 50),
            "Discord": rgb(88, 101, 242),
            "Twitter": rgb(29, 161, 242),
            "Bluesky": rgb(0, 133, 255),
            "Instagram": rgb(225, 48, 108),
        }
        dot_color = colors.get(platform, MID_GREY)
        display.fill_circle(card_x + 20, sy + 6, 6, dot_color)

        # Platform name and handle
        display.text(platform, card_x + 32, sy, rgb(80, 80, 80))
        display.text(handle, card_x + 32, sy + 10, BLACK)
        sy += 28


def update(touch_pos):
    """Update and render the badge display."""
    global hue, rear_view, flipping, flip_start, back_btn, _last_touch_time

    ticks = time.ticks_ms()

    # Background
    bg = _hue_to_rgb565(hue)
    _draw_ripple_bg(bg)

    # Back button
    back_btn = draw_back_button()

    # Card dimensions
    card_w = 180
    card_h = 190
    card_x = CX - card_w // 2
    card_y = 25

    # Handle flip animation
    if flipping:
        elapsed = time.ticks_diff(ticks, flip_start)
        speed = 300  # ms for full flip
        progress = elapsed / speed

        if progress >= 1.0:
            flipping = False
        else:
            # Scale width during flip
            scale = abs(math.cos(progress * math.pi))
            card_w_anim = max(4, int(card_w * scale))
            card_x = CX - card_w_anim // 2

            # Switch view at midpoint
            if progress > 0.5 and not rear_view:
                rear_view = True
            elif progress > 0.5:
                pass  # already switched

            if rear_view:
                _draw_card_back(card_x, card_y, card_w_anim, card_h)
            else:
                _draw_card_front(card_x, card_y, card_w_anim, card_h)

            # Touch handling during animation
            if touch_pos:
                check_back_button(touch_pos, back_btn)
            return None

    # Draw card (not flipping)
    if rear_view:
        _draw_card_back(card_x, card_y, card_w, card_h)
    else:
        _draw_card_front(card_x, card_y, card_w, card_h)

    # Hint text
    display.text("Tap card to flip", CX - 64, HEIGHT - 16, WHITE)

    # Handle touch
    if touch_pos:
        tx, ty = touch_pos

        # Debounce check
        if time.ticks_diff(ticks, _last_touch_time) < 300:
            return None
        _last_touch_time = ticks

        # Back button
        if check_back_button(touch_pos, back_btn):
            return None

        # Touch card to flip
        if (card_x <= tx <= card_x + card_w and
                card_y <= ty <= card_y + card_h):
            flipping = True
            flip_start = ticks
            rear_view = not rear_view
            return None

        # Touch left edge to change hue
        if tx < 40:
            hue = (hue - 15) % 360

        # Touch right edge to change hue
        if tx > WIDTH - 40:
            hue = (hue + 15) % 360

    return None
