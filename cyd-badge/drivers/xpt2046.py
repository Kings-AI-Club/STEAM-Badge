"""
XPT2046 resistive touchscreen driver for ESP32 CYD.

Uses a separate SPI bus (VSPI) from the display.

Pin configuration for ESP32 CYD:
  - CLK  = GPIO 25
  - MOSI = GPIO 32
  - MISO = GPIO 39
  - CS   = GPIO 33
  - IRQ  = GPIO 36
"""

import machine
import time


class XPT2046:
    """XPT2046 resistive touch controller driver."""

    # Command bytes for reading X and Y coordinates
    _CMD_X = 0xD0  # Channel select for X position
    _CMD_Y = 0x90  # Channel select for Y position

    def __init__(self, spi=None, cs=33, irq=36,
                 width=320, height=240, rotation=1,
                 x_min=200, x_max=3700, y_min=240, y_max=3800):

        if spi is None:
            self.spi = machine.SPI(
                2,  # VSPI
                baudrate=2_000_000,
                polarity=0,
                phase=0,
                sck=machine.Pin(25),
                mosi=machine.Pin(32),
                miso=machine.Pin(39),
            )
        else:
            self.spi = spi

        self.cs = machine.Pin(cs, machine.Pin.OUT, value=1)
        self.irq = machine.Pin(irq, machine.Pin.IN)

        self.width = width
        self.height = height
        self.rotation = rotation

        # Calibration values (raw ADC range)
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max

        # Touch state tracking
        self._last_touch = None
        self._touch_start = None
        self._was_touched = False

        # Debounce
        self._last_read_time = 0
        self._debounce_ms = 0

    def _read_raw(self, cmd):
        """Read a raw 12-bit value from the touch controller."""
        self.cs(0)
        self.spi.write(bytes([cmd]))
        data = self.spi.read(2)
        self.cs(1)
        # 12-bit value from the top bits
        return ((data[0] << 8) | data[1]) >> 3

    def _read_raw_averaged(self, cmd, samples=2):
        """Read multiple samples and return average (noise reduction)."""
        total = 0
        for _ in range(samples):
            total += self._read_raw(cmd)
        return total // samples

    def is_touched(self):
        """Check if the screen is currently being touched."""
        return self.irq.value() == 0

    def get_raw(self):
        """Get raw touch coordinates (before calibration)."""
        if not self.is_touched():
            return None

        raw_x = self._read_raw_averaged(self._CMD_X)
        raw_y = self._read_raw_averaged(self._CMD_Y)

        return (raw_x, raw_y)

    def get_touch(self):
        """
        Get calibrated touch coordinates mapped to screen space.
        Returns (x, y) tuple or None if not touched.
        """
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_read_time) < self._debounce_ms:
            return self._last_touch if self.is_touched() else None
        self._last_read_time = now

        if not self.is_touched():
            if self._was_touched:
                self._was_touched = False
            self._last_touch = None
            return None

        raw = self.get_raw()
        if raw is None:
            self._last_touch = None
            return None

        raw_x, raw_y = raw

        # Auto-calibration: expand range if readings exceed current bounds
        if raw_x < self.x_min:
            self.x_min = raw_x
        if raw_x > self.x_max:
            self.x_max = raw_x
        if raw_y < self.y_min:
            self.y_min = raw_y
        if raw_y > self.y_max:
            self.y_max = raw_y

        # Map raw values to NATIVE touch panel coordinates (portrait: 240x320)
        # Touch panel X axis = short side (240), Y axis = long side (320)
        native_x = self._map(raw_x, self.x_min, self.x_max, 0, 239)
        native_y = self._map(raw_y, self.y_min, self.y_max, 0, 319)

        # Apply rotation: transform from native panel coords to screen coords
        x, y = self._apply_rotation(native_x, native_y)

        # Clamp to screen bounds
        x = max(0, min(self.width - 1, x))
        y = max(0, min(self.height - 1, y))

        self._last_touch = (x, y)
        self._was_touched = True
        self._touch_start = self._touch_start or now

        return (x, y)

    def get_gesture(self):
        """
        Detect simple gestures. Returns a dict with gesture info.
        Call this when touch is released to get swipe direction.
        """
        if self._was_touched and not self.is_touched():
            self._was_touched = False
            return {"type": "tap", "pos": self._last_touch}
        return None

    def _apply_rotation(self, nx, ny):
        """Transform native panel coords (240x320) to rotated screen coords."""
        if self.rotation == 0:
            # Portrait, USB bottom (240x320)
            return nx, ny
        elif self.rotation == 1:
            # Landscape, USB right (320x240): 180 degrees from rotation 3
            return ny, nx
        elif self.rotation == 2:
            # Portrait, USB top (240x320): screen_x=239-nx, screen_y=319-ny
            return 239 - nx, 319 - ny
        elif self.rotation == 3:
            # Landscape, USB left (320x240): screen_x=319-ny, screen_y=239-nx
            return 319 - ny, 239 - nx
        return nx, ny

    def _map(self, value, in_min, in_max, out_min, out_max):
        """Map a value from one range to another."""
        if in_max == in_min:
            return out_min
        return (value - in_min) * (out_max - out_min) // (in_max - in_min) + out_min
