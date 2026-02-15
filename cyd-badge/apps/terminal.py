"""
Terminal - htop-like system monitor for ESP32 CYD.

Shows real-time RAM, CPU, and disk usage with
90s hacker terminal aesthetic.
"""
import gc
import os
import time
import machine
from badge_os import (display, WIDTH, HEIGHT, rgb, BLACK, WHITE,
                      MID_GREY, DARK_GREY, draw_back_button,
                      check_back_button, request_menu)
from fonts import bitmap_font

# ─── Hacker Theme Colors ───────────────────────────────────────

TERM_BG = rgb(2, 8, 4)
TERM_GREEN = rgb(0, 255, 80)
TERM_DIM = rgb(0, 120, 40)
TERM_DARK = rgb(0, 40, 15)
BAR_BG = rgb(0, 20, 8)
BAR_LOW = rgb(0, 200, 60)
BAR_MED = rgb(200, 200, 0)
BAR_HIGH = rgb(255, 50, 30)
BORDER = rgb(0, 100, 30)
CYAN = rgb(0, 200, 220)

# ─── State ──────────────────────────────────────────────────────

_back_btn = None
_needs_full_draw = True
_last_update = 0
_frame = 0


def init():
    """Initialize terminal app."""
    global _back_btn, _needs_full_draw, _last_update, _frame
    _needs_full_draw = True
    _last_update = 0
    _frame = 0
    gc.collect()


def _bar_color(pct):
    """Return color based on usage percentage."""
    if pct < 50:
        return BAR_LOW
    elif pct < 80:
        return BAR_MED
    return BAR_HIGH


def _draw_bar(x, y, w, h, pct, color):
    """Draw a usage bar with border."""
    display.fill_rect(x, y, w, h, BAR_BG)
    filled = max(1, int(w * pct / 100))
    display.fill_rect(x, y, filled, h, color)
    display.rect(x, y, w, h, TERM_DARK)


def _draw_stats():
    """Draw all system stats."""
    global _back_btn

    display.fill(TERM_BG)

    # Top border
    display.hline(0, 0, WIDTH, BORDER)

    # Header
    _back_btn = draw_back_button()
    bitmap_font.draw_text(display, "> SYSTEM MONITOR", 50, 5, TERM_GREEN)

    # Separator
    display.hline(0, 22, WIDTH, TERM_DARK)

    # ─── CPU Info ───────────────────────────────────────
    y = 28
    freq_mhz = machine.freq() // 1_000_000
    display.text("CPU", 8, y, CYAN)
    display.text("{}MHz".format(freq_mhz), 40, y, TERM_GREEN)
    # Fake CPU bar (ESP32 doesn't expose real CPU usage)
    # Show frequency as percentage of max (240MHz)
    cpu_pct = min(100, freq_mhz * 100 // 240)
    _draw_bar(120, y - 1, 185, 10, cpu_pct, _bar_color(cpu_pct))
    display.text("{}%".format(cpu_pct), WIDTH - 35, y, TERM_DIM)

    # ─── RAM Usage ──────────────────────────────────────
    y = 46
    gc.collect()
    mem_free = gc.mem_free()
    mem_alloc = gc.mem_alloc()
    mem_total = mem_free + mem_alloc
    mem_pct = mem_alloc * 100 // mem_total if mem_total > 0 else 0
    display.text("RAM", 8, y, CYAN)
    display.text("{}/{}K".format(mem_alloc // 1024, mem_total // 1024),
                 40, y, TERM_GREEN)
    _draw_bar(120, y - 1, 185, 10, mem_pct, _bar_color(mem_pct))
    display.text("{}%".format(mem_pct), WIDTH - 35, y, TERM_DIM)

    # ─── Disk Usage ─────────────────────────────────────
    y = 64
    try:
        stat = os.statvfs('/')
        blk_size = stat[0]
        blk_total = stat[2]
        blk_free = stat[3]
        disk_total = blk_size * blk_total
        disk_used = blk_size * (blk_total - blk_free)
        disk_pct = disk_used * 100 // disk_total if disk_total > 0 else 0
        display.text("DSK", 8, y, CYAN)
        display.text("{}/{}K".format(disk_used // 1024,
                                     disk_total // 1024),
                     40, y, TERM_GREEN)
        _draw_bar(120, y - 1, 185, 10, disk_pct, _bar_color(disk_pct))
        display.text("{}%".format(disk_pct), WIDTH - 35, y, TERM_DIM)
    except OSError:
        display.text("DSK  N/A", 8, y, TERM_DIM)

    # ─── Separator ──────────────────────────────────────
    display.hline(0, 80, WIDTH, TERM_DARK)

    # ─── System Details ─────────────────────────────────
    y = 86
    display.text("SYSTEM INFO", 8, y, CYAN)
    y += 14
    display.text("Chip:  ESP32-D0WD-V3", 8, y, TERM_GREEN)
    y += 12
    display.text("Freq:  {}MHz".format(freq_mhz), 8, y, TERM_GREEN)
    y += 12
    display.text("Flash: {}KB free".format(
        (blk_size * blk_free) // 1024 if 'blk_free' in dir() else 0),
        8, y, TERM_GREEN)
    y += 12
    display.text("Heap:  {}KB free".format(mem_free // 1024),
                 8, y, TERM_GREEN)

    # ─── Separator ──────────────────────────────────────
    display.hline(0, 150, WIDTH, TERM_DARK)

    # ─── Process List (fake htop style) ─────────────────
    y = 156
    display.text("  PID  CMD          MEM   STATE", 8, y, CYAN)
    y += 12

    procs = [
        ("  1", "badge_os", "{}K".format(mem_alloc // 2048), "RUN"),
        ("  2", "display_drv", "5K", "RUN"),
        ("  3", "touch_drv", "2K", "RUN"),
        ("  4", "gc_worker", "1K", "IDLE"),
        ("  5", "wifi_mgr", "0K", "STOP"),
    ]

    for pid, cmd, mem, st in procs:
        st_color = TERM_GREEN if st == "RUN" else TERM_DIM
        display.text(pid, 8, y, TERM_DIM)
        display.text(cmd, 48, y, TERM_GREEN)
        display.text(mem, 168, y, TERM_DIM)
        display.text(st, 210, y, st_color)
        y += 11

    # ─── Footer ─────────────────────────────────────────
    display.hline(0, HEIGHT - 16, WIDTH, TERM_DARK)
    uptime_s = time.ticks_ms() // 1000
    m = uptime_s // 60
    s = uptime_s % 60
    display.text("Uptime: {}m {}s".format(m, s), 8, HEIGHT - 12, TERM_DIM)
    display.text("[LIVE]", WIDTH - 52, HEIGHT - 12, TERM_GREEN)

    # Bottom border
    display.hline(0, HEIGHT - 1, WIDTH, BORDER)

    if display._full_fb:
        display.show()


def update(touch_pos):
    """Update terminal display."""
    global _needs_full_draw, _last_update, _back_btn, _frame

    _frame += 1
    ticks = time.ticks_ms()

    if _needs_full_draw:
        _needs_full_draw = False
        _draw_stats()
        _last_update = ticks
        return None

    # Check back button
    if touch_pos:
        if check_back_button(touch_pos, _back_btn):
            return None

    # Refresh stats every 2 seconds
    if time.ticks_diff(ticks, _last_update) > 2000:
        _draw_stats()
        _last_update = ticks

    return None
