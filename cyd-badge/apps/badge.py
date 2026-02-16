"""
Badge App - Indie game-style nameplate with color gradient animation.

Fast yellow-blue gradient cycling on name text,
4:3 portrait photo, retro pixel-art aesthetic.
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
SCALE = 3

# Pre-compute 32-step round-trip gradient: yellow -> blue -> yellow
_GRAD = []
for _i in range(16):
    _t = _i / 15.0
    _r = int(255 * (1.0 - _t) + 80 * _t)
    _g = int(230 * (1.0 - _t) + 120 * _t)
    _b = int(50 * (1.0 - _t) + 255 * _t)
    _GRAD.append(rgb(_r, _g, _b))
for _i in range(14, 0, -1):
    _GRAD.append(_GRAD[_i])
# Total: 30 entries, smooth round-trip
_GLEN = len(_GRAD)

# ─── State ──────────────────────────────────────────────────────

avatar_img = None
back_btn = None
_needs_full = True
_last_touch = 0
rear_view = False
_tick = 0

# Per-character data: [(char, x, y)]
_chars = []


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


def _bg_stars():
    for sx, sy in [(28, 8), (295, 20), (12, 195), (305, 190),
                   (50, 220), (275, 5), (185, 225)]:
        display.pixel(sx, sy, STAR_CLR)
        display.pixel(sx + 1, sy, STAR_CLR)
        display.pixel(sx, sy + 1, STAR_CLR)
        display.pixel(sx - 1, sy, STAR_CLR)
        display.pixel(sx, sy - 1, STAR_CLR)


def _draw_static():
    """Draw all static elements once."""
    global back_btn, _l1, _l2, _l1x, _l2x, _l1y, _l2y

    display.fill(BG_DARK)
    back_btn = draw_back_button()
    _bg_stars()

    px, py = 8, 26
    pw, ph = WIDTH - 16, HEIGHT - 50

    display.fill_rect(px, py, pw, ph, BG_MID)
    _pborder(px, py, pw, ph)

    for dx, dy in [(px + 4, py + 4), (px + pw - 7, py + 4)]:
        display.pixel(dx, dy, ACCENT)
        display.pixel(dx + 1, dy - 1, ACCENT)
        display.pixel(dx + 2, dy, ACCENT)
        display.pixel(dx + 1, dy + 1, ACCENT)

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

    tx = fx + fw + 8
    tw = px + pw - tx - 4

    img_top = fy + fp
    bitmap_font.draw_text(display, "Hello! I am", tx, img_top, HELLO_CLR, 1)
    display.hline(tx, img_top + 18, tw, FRAME_CLR)

    name = badge_config.NAME
    parts = name.split()
    l1 = parts[0] if parts else name
    l2 = " ".join(parts[1:]) if len(parts) >= 2 else ""

    char_h = 16 * SCALE
    name_top = img_top + 24
    name_bot = py + ph - 6
    block_h = char_h + (char_h + 4 if l2 else 0)
    base_y = name_top + (name_bot - name_top - block_h) // 2

    # Build per-character position list
    _chars = []
    cx = tx
    for ch in l1:
        cw = bitmap_font.measure_text(ch, SCALE)
        _chars.append((ch, cx, base_y))
        cx += cw
    if l2:
        cx = tx
        y2 = base_y + char_h + 4
        for ch in l2:
            cw = bitmap_font.measure_text(ch, SCALE)
            _chars.append((ch, cx, y2))
            cx += cw

    # Initial draw
    for idx, (ch, cx, cy) in enumerate(_chars):
        bitmap_font.draw_char(display, ch, cx, cy, _GRAD[idx % _GLEN], SCALE)

    credit = "Made by King's AI Seminar"
    credit_y = py + ph + (HEIGHT - py - ph - 8) // 2
    display.text(credit, CX - len(credit) * 4, credit_y, TEXT_DIM)

    if display._full_fb:
        display.show()


def _animate():
    """Flowing ribbon: gradient slides across letters."""
    offset = _tick * 15  # speed of flow
    for idx, (ch, cx, cy) in enumerate(_chars):
        color = _GRAD[(offset + idx * 3) % _GLEN]
        bitmap_font.draw_char(display, ch, cx, cy, color, SCALE)

    if display._full_fb:
        display.show()


def _draw_back():
    global back_btn

    display.fill(BG_DARK)
    back_btn = draw_back_button()
    _bg_stars()

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
    credit_y = py + ph + (HEIGHT - py - ph - 8) // 2
    display.text(credit, CX - len(credit) * 4, credit_y, TEXT_DIM)

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
