"""
Terminal - htop-like system monitor for ESP32 CYD.

Shows real-time RAM, CPU, and disk usage with
90s hacker terminal aesthetic. Only refreshes dynamic values.
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

# ─── Layout positions ──────────────────────────────────────────

BAR_X = 120
BAR_W = 160
BAR_H = 10
VAL_X = 40
PCT_X = WIDTH - 35

ROW_CPU = 28
ROW_RAM = 46
ROW_DSK = 64
ROW_UPT = HEIGHT - 12
ROW_CPU_VAL = ROW_CPU
ROW_RAM_VAL = ROW_RAM
ROW_DSK_VAL = ROW_DSK

# ─── State ──────────────────────────────────────────────────────

_back_btn = None
_needs_full_draw = True
_last_update = 0
_cpu_pct = 3
_cpu_tick = 0
_touching = False
import math


def _measure_cpu():
    """Semi-fake CPU: oscillates near 0 idle, rises on touch."""
    global _cpu_pct, _cpu_tick
    _cpu_tick += 1
    if _touching:
        # Touch active — spike to 40-75%
        wave = int(math.sin(_cpu_tick * 0.7) * 18)
        _cpu_pct = 55 + wave
    else:
        # Idle — oscillate 2-8%
        wave = int(math.sin(_cpu_tick * 0.4) * 3)
        _cpu_pct = 5 + wave
    _cpu_pct = max(1, min(99, _cpu_pct))
    return _cpu_pct


def init():
    """Initialize terminal app."""
    global _back_btn, _needs_full_draw, _last_update, _cpu_tick
    _needs_full_draw = True
    _last_update = 0
    _cpu_tick = 0
    gc.collect()


def _bar_color(pct):
    """Return color based on usage percentage."""
    if pct < 50:
        return BAR_LOW
    elif pct < 80:
        return BAR_MED
    return BAR_HIGH


def _draw_bar(x, y, w, h, pct, color):
    """Draw a usage bar."""
    display.fill_rect(x, y, w, h, BAR_BG)
    filled = max(1, int(w * pct / 100))
    display.fill_rect(x, y, filled, h, color)
    display.rect(x, y, w, h, TERM_DARK)


def _clear_value(x, y, w):
    """Clear a value area for redraw."""
    display.fill_rect(x, y - 1, w, 11, TERM_BG)


def _draw_static():
    """Draw static elements that don't change."""
    global _back_btn

    display.fill(TERM_BG)

    # Top border
    display.hline(0, 0, WIDTH, BORDER)

    # Header
    _back_btn = draw_back_button()
    bitmap_font.draw_text(display, "> SYSTEM MONITOR", 50, 5, TERM_GREEN)

    # Separator
    display.hline(0, 22, WIDTH, TERM_DARK)

    # Row labels
    display.text("CPU", 8, ROW_CPU, CYAN)
    display.text("RAM", 8, ROW_RAM, CYAN)
    display.text("DSK", 8, ROW_DSK, CYAN)

    # Separator
    display.hline(0, 80, WIDTH, TERM_DARK)

    # System info header
    display.text("SYSTEM INFO", 8, 86, CYAN)
    freq_mhz = machine.freq() // 1_000_000
    display.text("Chip:  ESP32-D0WD-V3", 8, 100, TERM_GREEN)
    display.text("Freq:  {}MHz".format(freq_mhz), 8, 112, TERM_GREEN)

    # Separator
    display.hline(0, 150, WIDTH, TERM_DARK)

    # Process list header
    display.text("  PID  CMD          MEM   STATE", 8, 156, CYAN)

    procs = [
        ("  1", "badge_os", "RUN"),
        ("  2", "display_drv", "RUN"),
        ("  3", "touch_drv", "RUN"),
        ("  4", "gc_worker", "IDLE"),
        ("  5", "wifi_mgr", "STOP"),
    ]
    y = 168
    for pid, cmd, st in procs:
        st_color = TERM_GREEN if st == "RUN" else TERM_DIM
        display.text(pid, 8, y, TERM_DIM)
        display.text(cmd, 48, y, TERM_GREEN)
        display.text(st, 210, y, st_color)
        y += 11

    # Footer separator
    display.hline(0, HEIGHT - 16, WIDTH, TERM_DARK)
    display.hline(0, HEIGHT - 1, WIDTH, BORDER)


def _update_dynamic():
    """Update only the dynamic values (bars, numbers, uptime)."""
    # ─── CPU ────────────────────────────────────────────
    cpu = _measure_cpu()
    _clear_value(VAL_X, ROW_CPU, 76)
    display.text("{}%".format(cpu), VAL_X, ROW_CPU, TERM_GREEN)
    _draw_bar(BAR_X, ROW_CPU - 1, BAR_W, BAR_H, cpu, _bar_color(cpu))

    # ─── RAM ────────────────────────────────────────────
    gc.collect()
    mem_free = gc.mem_free()
    mem_alloc = gc.mem_alloc()
    mem_total = mem_free + mem_alloc
    mem_pct = mem_alloc * 100 // mem_total if mem_total > 0 else 0
    _clear_value(VAL_X, ROW_RAM, 76)
    display.text("{}/{}K".format(mem_alloc // 1024, mem_total // 1024),
                 VAL_X, ROW_RAM, TERM_GREEN)
    _draw_bar(BAR_X, ROW_RAM - 1, BAR_W, BAR_H, mem_pct, _bar_color(mem_pct))

    # ─── Disk ───────────────────────────────────────────
    try:
        stat = os.statvfs('/')
        blk_size = stat[0]
        blk_total = stat[2]
        blk_free = stat[3]
        disk_total = blk_size * blk_total
        disk_used = blk_size * (blk_total - blk_free)
        disk_pct = disk_used * 100 // disk_total if disk_total > 0 else 0
        _clear_value(VAL_X, ROW_DSK, 76)
        display.text("{}/{}K".format(disk_used // 1024,
                                     disk_total // 1024),
                     VAL_X, ROW_DSK, TERM_GREEN)
        _draw_bar(BAR_X, ROW_DSK - 1, BAR_W, BAR_H, disk_pct,
                  _bar_color(disk_pct))
    except OSError:
        pass

    # ─── Dynamic system info ────────────────────────────
    _clear_value(8, 124, 200)
    mem_free_kb = mem_free // 1024
    display.text("Heap:  {}KB free".format(mem_free_kb), 8, 124, TERM_GREEN)
    _clear_value(8, 136, 200)
    try:
        flash_free = (blk_size * blk_free) // 1024
        display.text("Flash: {}KB free".format(flash_free), 8, 136,
                     TERM_GREEN)
    except Exception:
        pass

    # ─── Uptime ─────────────────────────────────────────
    _clear_value(8, ROW_UPT, 200)
    uptime_s = time.ticks_ms() // 1000
    m = uptime_s // 60
    s = uptime_s % 60
    display.text("Uptime: {}m {}s".format(m, s), 8, ROW_UPT, TERM_DIM)
    display.text("[LIVE]", WIDTH - 52, ROW_UPT, TERM_GREEN)

    if display._full_fb:
        display.show()


def update(touch_pos):
    """Update terminal display."""
    global _needs_full_draw, _last_update, _back_btn, _touching

    ticks = time.ticks_ms()

    if _needs_full_draw:
        _needs_full_draw = False
        _draw_static()
        _update_dynamic()
        _last_update = ticks
        return None

    # Track touch for CPU meter
    _touching = touch_pos is not None

    # Check back button
    if touch_pos:
        if check_back_button(touch_pos, _back_btn):
            return None

    # Refresh dynamic values every 1 second
    if time.ticks_diff(ticks, _last_update) > 1000:
        _update_dynamic()
        _last_update = ticks

    return None
