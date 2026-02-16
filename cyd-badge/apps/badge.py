"""
Badge App - Indie game-style nameplate with rainbow animations.

Smooth floating rainbow name, 4:3 portrait photo,
retro pixel-art aesthetic.
"""
import gc
import time
from badge_os import (display, WIDTH, HEIGHT, rgb, BLACK, WHITE,
                      load_image, draw_image, draw_back_button,
                      check_back_button)
from fonts import bitmap_font
import badge_config

# ─── Retro Game Palette ─────────────────────────────────────────

BG_DARK = rgb(12, 10, 28)
BG_MID = rgb(25, 20, 50)
FRAME_HI = rgb(180, 140, 255)
FRAME_LO = rgb(60, 40, 120)
FRAME_CLR = rgb(120, 80, 200)
HELLO_CLR = rgb(100, 220, 255)
ACCENT = rgb(255, 100, 150)
TEXT_DIM = rgb(140, 120, 180)
STAR_CLR = rgb(255, 255, 180)

CX = WIDTH // 2

# ─── Rainbow helper ─────────────────────────────────────────────

def _hue_rgb(hue):
    h = hue % 360
    c = 1.0
    x = c * (1.0 - abs((h / 60.0) % 2 - 1.0))
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
    return rgb(int(r * 255), int(g * 255), int(b * 255))


# ─── State ──────────────────────────────────────────────────────

avatar_img = None
back_btn = None
_needs_full = True
_last_touch = 0
rear_view = False
_tick = 0

# Layout cache
_tx = 0
_tw = 0
_l1 = ""
_l2 = ""
_l1x = 0
_l2x = 0
_l1y = 0
_l2y = 0


def init():
    global avatar_img, _needs_full, rear_view, _tick
    gc.collect()
    rear_view = False
    _tick = 0
    try:
        avatar_img = load_image("resources/avatar.bin")
    except OSError:
        avatar_img = None
    _needs_full = True
    gc.collect()


def _pborder(x, y, w, h):
    display.hline(x, y, w, FRAME_HI)
    display.hline(x, y + 1, w, FRAME_HI)
    display.vline(x, y, h, FRAME_HI)
    display.vline(x + 1, y, h, FRAME_HI)
    display.hline(x, y + h - 1, w, FRAME_LO)
    display.hline(x, y + h - 2, w, FRAME_LO)
    display.vline(x + w - 1, y, h, FRAME_LO)
    display.vline(x + w - 2, y, h, FRAME_LO)


def _stars():
    for sx, sy in [(28, 8), (295, 20), (12, 195), (305, 190),
                   (50, 220), (275, 5), (185, 225)]:
        display.pixel(sx, sy, STAR_CLR)
        display.pixel(sx + 1, sy, STAR_CLR)
        display.pixel(sx, sy + 1, STAR_CLR)
        display.pixel(sx - 1, sy, STAR_CLR)
        display.pixel(sx, sy - 1, STAR_CLR)


def _draw_static():
    """Draw all static elements once."""
    global back_btn, _tx, _tw
    global _l1, _l2, _l1x, _l2x, _l1y, _l2y

    display.fill(BG_DARK)
    back_btn = draw_back_button()
    _stars()

    # Main panel — pushed down to clear Menu button
    px, py = 8, 26
    pw, ph = WIDTH - 16, HEIGHT - 50  # 304 x 190

    display.fill_rect(px, py, pw, ph, BG_MID)
    _pborder(px, py, pw, ph)

    # Corner diamonds
    for dx, dy in [(px + 4, py + 4), (px + pw - 7, py + 4)]:
        display.pixel(dx, dy, ACCENT)
        display.pixel(dx + 1, dy - 1, ACCENT)
        display.pixel(dx + 2, dy, ACCENT)
        display.pixel(dx + 1, dy + 1, ACCENT)

    # Photo frame
    if avatar_img:
        iw, ih, _ = avatar_img
    else:
        iw, ih = 96, 128

    fp = 4
    fx = px + 8
    fy = py + (ph - ih - fp * 2) // 2
    fw = iw + fp * 2
    fh = ih + fp * 2

    display.fill_rect(fx, fy, fw, fh, BG_DARK)
    _pborder(fx, fy, fw, fh)

    if avatar_img:
        draw_image(fx + fp, fy + fp, avatar_img)

    # Text area
    tx = fx + fw + 8
    tw = px + pw - tx - 4
    _tx = tx
    _tw = tw

    # "Hello! I am" — scale 1, light blue, not caps
    hello = "Hello! I am"
    hw = bitmap_font.measure_text(hello, 1)
    hx = tx + max(0, (tw - hw) // 2)
    bitmap_font.draw_text(display, hello, hx, py + 10, HELLO_CLR, 1)

    # Separator
    display.hline(tx, py + 28, tw, FRAME_CLR)

    # Split name
    name = badge_config.NAME
    parts = name.split()
    if len(parts) >= 2:
        _l1 = parts[0]
        _l2 = " ".join(parts[1:])
    else:
        _l1 = name
        _l2 = ""

    # Name at scale 2 (32px tall), centered vertically in remaining space
    # Available: from py+32 to py+ph = 158px of space
    avail_top = py + 34
    avail_bot = py + ph - 4
    avail_h = avail_bot - avail_top
    name_h = 32 + (36 if _l2 else 0)
    name_top = avail_top + (avail_h - name_h) // 2

    l1w = bitmap_font.measure_text(_l1, 2)
    _l1x = tx + max(0, (tw - l1w) // 2)
    _l1y = name_top

    if _l2:
        l2w = bitmap_font.measure_text(_l2, 2)
        _l2x = tx + max(0, (tw - l2w) // 2)
        _l2y = name_top + 36

    # Draw name initially (will be overwritten each frame with new color)
    bitmap_font.draw_text(display, _l1, _l1x, _l1y, ACCENT, 2)
    if _l2:
        bitmap_font.draw_text(display, _l2, _l2x, _l2y, ACCENT, 2)

    # "Made by King's AI Seminar" between panel bottom and screen edge
    credit = "Made by King's AI Seminar"
    cw = len(credit) * 8
    credit_y = py + ph + (HEIGHT - py - ph - 8) // 2
    display.text(credit, CX - cw // 2, credit_y, TEXT_DIM)

    if display._full_fb:
        display.show()


def _animate():
    """Smooth rainbow color cycle — just overwrite text at same position."""
    # Rainbow hue cycles — no erase, just redraw text with new color
    hue = (_tick * 5) % 360
    color1 = _hue_rgb(hue)
    bitmap_font.draw_text(display, _l1, _l1x, _l1y, color1, 2)

    if _l2:
        color2 = _hue_rgb((hue + 80) % 360)
        bitmap_font.draw_text(display, _l2, _l2x, _l2y, color2, 2)

    if display._full_fb:
        display.show()


def _draw_back():
    global back_btn

    display.fill(BG_DARK)
    back_btn = draw_back_button()
    _stars()

    px, py = 8, 26
    pw, ph = WIDTH - 16, HEIGHT - 50

    display.fill_rect(px, py, pw, ph, BG_MID)
    _pborder(px, py, pw, ph)

    bitmap_font.draw_text(display, "SOCIALS", CX - 50, py + 10, ACCENT, 2)
    display.hline(px + 10, py + 42, pw - 20, FRAME_CLR)

    sy = py + 50
    for platform, handle in badge_config.SOCIALS.items():
        if sy + 30 > py + ph - 8:
            break
        bitmap_font.draw_text(display, platform, px + 20, sy, HELLO_CLR, 1)
        display.text(handle, px + 20, sy + 18, WHITE)
        sy += 36

    display.hline(px + 10, py + ph - 18, pw - 20, FRAME_CLR)

    credit = "Made by King's AI Seminar"
    cw = len(credit) * 8
    credit_y = py + ph + (HEIGHT - py - ph - 8) // 2
    display.text(credit, CX - cw // 2, credit_y, TEXT_DIM)

    if display._full_fb:
        display.show()


def update(touch_pos):
    global _needs_full, rear_view, _last_touch, _tick

    ticks = time.ticks_ms()

    if _needs_full:
        _needs_full = False
        if rear_view:
            _draw_back()
        else:
            _draw_static()
        return None

    if not rear_view:
        _tick += 1
        _animate()

    if touch_pos:
        if time.ticks_diff(ticks, _last_touch) < 400:
            return None
        _last_touch = ticks

        if check_back_button(touch_pos, back_btn):
            return None

        rear_view = not rear_view
        _needs_full = True

    return None
