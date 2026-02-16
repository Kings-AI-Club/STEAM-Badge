"""
ILI9341 display driver for ESP32 CYD (Cheap Yellow Display) 2.8" 320x240.

Uses SPI to communicate with the ILI9341 LCD controller.
Supports full framebuffer mode (if RAM available) or direct-draw mode.

Pin configuration for ESP32 CYD:
  - CLK  = GPIO 14
  - MOSI = GPIO 13
  - MISO = GPIO 12
  - CS   = GPIO 15
  - DC   = GPIO 2
  - BL   = GPIO 21
"""

import gc
import machine
import struct
import time
import framebuf

# ILI9341 command constants
_SWRESET = 0x01
_SLPOUT = 0x11
_COLMOD = 0x3A
_MADCTL = 0x36
_DISPON = 0x29
_CASET = 0x2A
_RASET = 0x2B
_RAMWR = 0x2C

# MADCTL bits
_MADCTL_MY = 0x80
_MADCTL_MX = 0x40
_MADCTL_MV = 0x20
_MADCTL_BGR = 0x08

# Rotation configurations: (MADCTL value, width, height)
# Tuned for ESP32 CYD panel wiring
_ROTATIONS = {
    0: (_MADCTL_BGR, 240, 320),
    1: (_MADCTL_MV | _MADCTL_MX | _MADCTL_BGR, 320, 240),
    2: (_MADCTL_MX | _MADCTL_MY | _MADCTL_BGR, 240, 320),
    3: (_MADCTL_MV | _MADCTL_MY | _MADCTL_BGR, 320, 240),
}


def color565(r, g, b):
    """Convert RGB888 to BGR565, byte-swapped for ILI9341 (BGR panel)."""
    # ILI9341 with MADCTL_BGR: bits 15-11=Blue, 10-5=Green, 4-0=Red
    c = ((b & 0xF8) << 8) | ((g & 0xFC) << 3) | (r >> 3)
    # Byte-swap so framebuf stores in ILI9341's big-endian order
    return ((c & 0xFF) << 8) | ((c >> 8) & 0xFF)


class ILI9341:
    """ILI9341 display driver with framebuffer support."""

    def __init__(self, spi=None, cs=15, dc=2, bl=21, rotation=3,
                 width=320, height=240):
        # Use provided SPI or create default
        if spi is None:
            self.spi = machine.SPI(
                1,
                baudrate=40_000_000,
                polarity=0,
                phase=0,
                sck=machine.Pin(14),
                mosi=machine.Pin(13),
                miso=machine.Pin(12),
            )
        else:
            self.spi = spi

        self.cs = machine.Pin(cs, machine.Pin.OUT, value=1)
        self.dc = machine.Pin(dc, machine.Pin.OUT, value=0)
        self.bl = machine.Pin(bl, machine.Pin.OUT, value=1)

        self.width = width
        self.height = height
        self._rotation = rotation
        self._full_fb = False
        self.buffer = None
        self.fb = None

        # Try to allocate framebuffer — gc.collect() first for max free block
        gc.collect()
        free = gc.mem_free()
        buf_size = width * height * 2  # 153,600 bytes for 320x240

        if free > buf_size + 30000:  # Need 30KB headroom for app code
            try:
                self.buffer = bytearray(buf_size)
                self.fb = framebuf.FrameBuffer(self.buffer, width, height,
                                               framebuf.RGB565)
                self._full_fb = True
                print("Display: full framebuffer ({} bytes)".format(buf_size))
            except MemoryError:
                self._full_fb = False
                self.buffer = None
                self.fb = None

        if not self._full_fb:
            print("Display: direct draw mode (no framebuffer)")
            # Pre-allocate an 8-line chunk buffer for optimized fills
            self._chunk_lines = 8
            self._chunk_size = width * self._chunk_lines * 2
            self._chunk_buf = bytearray(self._chunk_size)

        self._init_display()
        gc.collect()

    def _write_cmd(self, cmd, data=None):
        """Write a command byte, optionally followed by data bytes."""
        self.cs(0)
        self.dc(0)
        self.spi.write(bytes([cmd]))
        if data is not None:
            self.dc(1)
            self.spi.write(data)
        self.cs(1)

    def _init_display(self):
        """Initialize the ILI9341 display."""
        self._write_cmd(_SWRESET)
        time.sleep_ms(150)
        self._write_cmd(_SLPOUT)
        time.sleep_ms(150)
        self._write_cmd(_COLMOD, bytes([0x55]))
        madctl, self.width, self.height = _ROTATIONS.get(
            self._rotation, _ROTATIONS[3]
        )
        self._write_cmd(_MADCTL, bytes([madctl]))
        self._write_cmd(_DISPON)
        time.sleep_ms(100)
        self.bl(1)

    def _set_window(self, x0, y0, x1, y1):
        """Set the drawing window."""
        self._write_cmd(_CASET, struct.pack(">HH", x0, x1))
        self._write_cmd(_RASET, struct.pack(">HH", y0, y1))

    # ─── Framebuffer mode ───────────────────────────────────────

    def show(self):
        """Flush the full framebuffer to the display."""
        if not self._full_fb:
            return

        self._set_window(0, 0, self.width - 1, self.height - 1)
        self.cs(0)
        self.dc(0)
        self.spi.write(bytes([_RAMWR]))
        self.dc(1)

        # Pre-swapped colors mean buffer is already in ILI9341 format
        mv = memoryview(self.buffer)
        chunk = 4096
        for i in range(0, len(self.buffer), chunk):
            self.spi.write(mv[i:i + chunk])

        self.cs(1)

    # ─── Drawing primitives ─────────────────────────────────────

    def fill(self, c):
        """Fill entire screen with color."""
        if self._full_fb:
            self.fb.fill(c)
        else:
            self._fill_direct(c)

    def _fill_direct(self, c):
        """Fill screen directly — optimized with chunked writes."""
        self._set_window(0, 0, self.width - 1, self.height - 1)
        # Pre-swapped color: lo byte first gives correct SPI byte order
        lo = c & 0xFF
        hi = (c >> 8) & 0xFF
        # Fill the chunk buffer with the color pattern
        mv = memoryview(self._chunk_buf)
        for i in range(0, self._chunk_size, 2):
            mv[i] = lo
            mv[i + 1] = hi

        self.cs(0)
        self.dc(0)
        self.spi.write(bytes([_RAMWR]))
        self.dc(1)
        # Send 8 lines at a time (5120 bytes each)
        full_chunks = self.height // self._chunk_lines
        for _ in range(full_chunks):
            self.spi.write(self._chunk_buf)
        remaining = self.height % self._chunk_lines
        if remaining:
            self.spi.write(memoryview(self._chunk_buf)[:self.width * remaining * 2])
        self.cs(1)

    def pixel(self, x, y, c):
        """Set a single pixel."""
        if self._full_fb:
            self.fb.pixel(x, y, c)
        else:
            if 0 <= x < self.width and 0 <= y < self.height:
                self._set_window(x, y, x, y)
                lo = c & 0xFF
                hi = (c >> 8) & 0xFF
                self.cs(0)
                self.dc(0)
                self.spi.write(bytes([_RAMWR]))
                self.dc(1)
                self.spi.write(bytes([lo, hi]))
                self.cs(1)

    def fill_rect(self, x, y, w, h, c):
        """Fill a rectangle."""
        if self._full_fb:
            self.fb.fill_rect(x, y, w, h, c)
        else:
            self._fill_rect_direct(x, y, w, h, c)

    def _fill_rect_direct(self, x, y, w, h, c):
        """Fill rectangle directly on display."""
        x = max(0, x)
        y = max(0, y)
        x2 = min(self.width - 1, x + w - 1)
        y2 = min(self.height - 1, y + h - 1)
        if x2 < x or y2 < y:
            return
        w = x2 - x + 1
        h = y2 - y + 1
        self._set_window(x, y, x2, y2)
        lo = c & 0xFF
        hi = (c >> 8) & 0xFF

        self.cs(0)
        self.dc(0)
        self.spi.write(bytes([_RAMWR]))
        self.dc(1)

        # For small rects, build and send directly
        total_bytes = w * h * 2
        if total_bytes <= self._chunk_size:
            buf = bytes([lo, hi] * (w * h))
            self.spi.write(buf)
        else:
            # Larger rects: send row by row
            row = bytes([lo, hi] * w)
            for _ in range(h):
                self.spi.write(row)
        self.cs(1)

    def rect(self, x, y, w, h, c):
        """Draw a rectangle outline."""
        if self._full_fb:
            self.fb.rect(x, y, w, h, c)
        else:
            self.hline(x, y, w, c)
            self.hline(x, y + h - 1, w, c)
            self.vline(x, y, h, c)
            self.vline(x + w - 1, y, h, c)

    def hline(self, x, y, w, c):
        """Draw a horizontal line."""
        if self._full_fb:
            self.fb.hline(x, y, w, c)
        else:
            self.fill_rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        """Draw a vertical line."""
        if self._full_fb:
            self.fb.vline(x, y, h, c)
        else:
            self.fill_rect(x, y, 1, h, c)

    def line(self, x0, y0, x1, y1, c):
        """Draw a line using Bresenham's algorithm."""
        if self._full_fb:
            self.fb.line(x0, y0, x1, y1, c)
        else:
            dx = abs(x1 - x0)
            dy = abs(y1 - y0)
            sx = 1 if x0 < x1 else -1
            sy = 1 if y0 < y1 else -1
            err = dx - dy
            while True:
                self.pixel(x0, y0, c)
                if x0 == x1 and y0 == y1:
                    break
                e2 = 2 * err
                if e2 > -dy:
                    err -= dy
                    x0 += sx
                if e2 < dx:
                    err += dx
                    y0 += sy

    def text(self, string, x, y, c, bg=None):
        """Draw text using MicroPython's built-in 8x8 font."""
        if self._full_fb:
            if bg is not None:
                text_width = len(string) * 8
                self.fb.fill_rect(x, y, text_width, 8, bg)
            self.fb.text(string, x, y, c)
        else:
            text_width = len(string) * 8
            tmp_buf = bytearray(text_width * 8 * 2)
            tmp_fb = framebuf.FrameBuffer(tmp_buf, text_width, 8,
                                          framebuf.RGB565)
            if bg is not None:
                tmp_fb.fill(bg)
            else:
                tmp_fb.fill(0)
            tmp_fb.text(string, 0, 0, c)
            self.blit_buffer(tmp_buf, x, y, text_width, 8)

    def blit_buffer(self, buf, x, y, w, h):
        """Blit a raw RGB565 buffer to the display."""
        x = max(0, x)
        y = max(0, y)
        x2 = min(self.width - 1, x + w - 1)
        y2 = min(self.height - 1, y + h - 1)
        if x2 < x or y2 < y:
            return

        self._set_window(x, y, x2, y2)
        self.cs(0)
        self.dc(0)
        self.spi.write(bytes([_RAMWR]))
        self.dc(1)
        self.spi.write(buf)
        self.cs(1)

    def circle(self, cx, cy, r, c):
        """Draw a circle outline using midpoint algorithm."""
        x = r
        y = 0
        err = 1 - r
        while x >= y:
            self.pixel(cx + x, cy + y, c)
            self.pixel(cx - x, cy + y, c)
            self.pixel(cx + x, cy - y, c)
            self.pixel(cx - x, cy - y, c)
            self.pixel(cx + y, cy + x, c)
            self.pixel(cx - y, cy + x, c)
            self.pixel(cx + y, cy - x, c)
            self.pixel(cx - y, cy - x, c)
            y += 1
            if err < 0:
                err += 2 * y + 1
            else:
                x -= 1
                err += 2 * (y - x) + 1

    def fill_circle(self, cx, cy, r, c):
        """Draw a filled circle."""
        for y in range(-r, r + 1):
            half_w = int((r * r - y * y) ** 0.5)
            self.hline(cx - half_w, cy + y, half_w * 2 + 1, c)

    def rounded_rect(self, x, y, w, h, r, c):
        """Draw a filled rounded rectangle."""
        self.fill_rect(x + r, y, w - 2 * r, h, c)
        self.fill_rect(x, y + r, r, h - 2 * r, c)
        self.fill_rect(x + w - r, y + r, r, h - 2 * r, c)
        self._fill_corner(x + r, y + r, r, c)
        self._fill_corner(x + w - r - 1, y + r, r, c)
        self._fill_corner(x + r, y + h - r - 1, r, c)
        self._fill_corner(x + w - r - 1, y + h - r - 1, r, c)

    def _fill_corner(self, cx, cy, r, c):
        """Fill a quarter circle for rounded rectangles."""
        for y in range(-r, r + 1):
            half_w = int((r * r - y * y) ** 0.5)
            self.hline(cx - half_w, cy + y, half_w * 2 + 1, c)

    def backlight(self, on=True):
        """Control backlight."""
        self.bl(1 if on else 0)

    def text_width(self, string, scale=1):
        """Calculate text width in pixels."""
        return len(string) * 8 * scale
