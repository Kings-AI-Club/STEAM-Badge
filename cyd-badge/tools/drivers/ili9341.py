"""
ILI9341 display driver for ESP32 CYD (Cheap Yellow Display) 2.8" 320x240.

Uses SPI to communicate with the ILI9341 LCD controller.
Provides framebuffer-based drawing with flush-to-screen support.

Pin configuration for ESP32 CYD:
  - CLK  = GPIO 14
  - MOSI = GPIO 13
  - MISO = GPIO 12
  - CS   = GPIO 15
  - DC   = GPIO 2
  - BL   = GPIO 21
"""

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
_ROTATIONS = {
    0: (_MADCTL_MX | _MADCTL_BGR, 240, 320),
    1: (_MADCTL_MV | _MADCTL_BGR, 320, 240),
    2: (_MADCTL_MY | _MADCTL_BGR, 240, 320),
    3: (_MADCTL_MX | _MADCTL_MY | _MADCTL_MV | _MADCTL_BGR, 320, 240),
}


def color565(r, g, b):
    """Convert RGB888 to RGB565 (big-endian for ILI9341)."""
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return c


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

        # Create a full framebuffer (RGB565 = 2 bytes per pixel)
        # 320*240*2 = 153,600 bytes — tight on ESP32 but possible
        # We'll use a line buffer approach instead for memory efficiency
        self._buf_size = width * height * 2
        try:
            self.buffer = bytearray(self._buf_size)
            self.fb = framebuf.FrameBuffer(self.buffer, width, height,
                                           framebuf.RGB565)
            self._full_fb = True
        except MemoryError:
            # Fall back to no full framebuffer — draw directly
            self._full_fb = False
            self.buffer = None
            self.fb = None

        # Line buffer for flushing (640 bytes for 320px line)
        self._line_buf = bytearray(width * 2)

        self._init_display()

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
        # Software reset
        self._write_cmd(_SWRESET)
        time.sleep_ms(150)

        # Sleep out
        self._write_cmd(_SLPOUT)
        time.sleep_ms(150)

        # Pixel format: 16-bit color (RGB565)
        self._write_cmd(_COLMOD, bytes([0x55]))

        # Memory access control (rotation)
        madctl, self.width, self.height = _ROTATIONS.get(
            self._rotation, _ROTATIONS[3]
        )
        self._write_cmd(_MADCTL, bytes([madctl]))

        # Display on
        self._write_cmd(_DISPON)
        time.sleep_ms(100)

        # Backlight on
        self.bl(1)

    def _set_window(self, x0, y0, x1, y1):
        """Set the drawing window."""
        self._write_cmd(_CASET, struct.pack(">HH", x0, x1))
        self._write_cmd(_RASET, struct.pack(">HH", y0, y1))

    def _swap_bytes_buf(self, buf, length):
        """Swap bytes in-place for RGB565 big-endian transmission."""
        mv = memoryview(buf)
        for i in range(0, length, 2):
            mv[i], mv[i + 1] = mv[i + 1], mv[i]

    def show(self):
        """Flush the full framebuffer to the display."""
        if not self._full_fb:
            return

        self._set_window(0, 0, self.width - 1, self.height - 1)
        self.cs(0)
        self.dc(0)
        self.spi.write(bytes([_RAMWR]))
        self.dc(1)

        # Send in chunks (line by line) to avoid memory issues
        line_size = self.width * 2
        for y in range(self.height):
            start = y * line_size
            # Copy line and swap bytes for big-endian
            self._line_buf[:line_size] = self.buffer[start:start + line_size]
            self._swap_bytes_buf(self._line_buf, line_size)
            self.spi.write(self._line_buf)

        self.cs(1)

    def fill(self, c):
        """Fill entire screen with color."""
        if self._full_fb:
            self.fb.fill(c)
        else:
            self._fill_direct(c)

    def _fill_direct(self, c):
        """Fill screen directly without framebuffer."""
        self._set_window(0, 0, self.width - 1, self.height - 1)
        # Swap bytes for SPI
        hi = (c >> 8) & 0xFF
        lo = c & 0xFF
        line = bytes([hi, lo] * self.width)

        self.cs(0)
        self.dc(0)
        self.spi.write(bytes([_RAMWR]))
        self.dc(1)
        for _ in range(self.height):
            self.spi.write(line)
        self.cs(1)

    def pixel(self, x, y, c):
        """Set a single pixel."""
        if self._full_fb:
            self.fb.pixel(x, y, c)
        else:
            self._pixel_direct(x, y, c)

    def _pixel_direct(self, x, y, c):
        """Set pixel directly on display."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self._set_window(x, y, x, y)
            hi = (c >> 8) & 0xFF
            lo = c & 0xFF
            self.cs(0)
            self.dc(0)
            self.spi.write(bytes([_RAMWR]))
            self.dc(1)
            self.spi.write(bytes([hi, lo]))
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
        hi = (c >> 8) & 0xFF
        lo = c & 0xFF
        line = bytes([hi, lo] * w)
        self.cs(0)
        self.dc(0)
        self.spi.write(bytes([_RAMWR]))
        self.dc(1)
        for _ in range(h):
            self.spi.write(line)
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
                # Draw background rectangle first
                text_width = len(string) * 8
                self.fb.fill_rect(x, y, text_width, 8, bg)
            self.fb.text(string, x, y, c)
        else:
            # For direct mode, use a small temp framebuffer
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

    def text_large(self, string, x, y, c, scale=2, bg=None):
        """Draw scaled text (integer scaling of built-in 8x8 font)."""
        # Render at 1x into a temp buffer, then scale up
        text_w = len(string) * 8
        text_h = 8
        tmp_buf = bytearray(text_w * text_h * 2)
        tmp_fb = framebuf.FrameBuffer(tmp_buf, text_w, text_h,
                                      framebuf.RGB565)
        tmp_fb.fill(0x0000)  # transparent black
        tmp_fb.text(string, 0, 0, c)

        # Scale and draw pixel by pixel
        for py in range(text_h):
            for px in range(text_w):
                pc = tmp_fb.pixel(px, py)
                if pc != 0x0000:
                    if self._full_fb:
                        self.fb.fill_rect(x + px * scale, y + py * scale,
                                          scale, scale, c)
                    else:
                        self.fill_rect(x + px * scale, y + py * scale,
                                       scale, scale, c)
                elif bg is not None:
                    if self._full_fb:
                        self.fb.fill_rect(x + px * scale, y + py * scale,
                                          scale, scale, bg)
                    else:
                        self.fill_rect(x + px * scale, y + py * scale,
                                       scale, scale, bg)

    def blit_buffer(self, buf, x, y, w, h):
        """Blit a raw RGB565 buffer to the display (direct mode)."""
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
        # Main body
        self.fill_rect(x + r, y, w - 2 * r, h, c)
        self.fill_rect(x, y + r, r, h - 2 * r, c)
        self.fill_rect(x + w - r, y + r, r, h - 2 * r, c)
        # Corners
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
