# STEAM Badge

A hackable conference badge that runs on the **ESP32 "Cheap Yellow Display"** (ESP32-2432S028R) — a ~$10 board with a 320×240 ILI9341 touchscreen. The badge runs **BadgeOS**, a tiny MicroPython app shell with a touch launcher, a personalized nameplate, and a handful of built-in apps.

Made by King's AI Seminar.

## What's on the badge

| App | Description |
| --- | --- |
| **Badge** | Animated nameplate with your name, photo, and a color-cycling gradient |
| **Pong** | Neon arcade Pong with spin, speed ramping, particles, and screen shake |
| **Tennis** | Classic two-paddle Pong, 90s hacker aesthetic |
| **Tetris** | Tap to rotate, drag to move — hold the board in portrait |
| **Sketch** | Etch-A-Sketch style touch drawing |
| **Terminal** | htop-style live monitor of the ESP32's RAM, CPU, and flash |

## Hardware

- **Board:** ESP32-2432S028R ("CYD") — widely available on AliExpress/Amazon
- **Display:** ILI9341 320×240 on HSPI (pins 14/13/12/15)
- **Touch:** XPT2046 resistive on VSPI (pins 25/32/39/33)
- A USB **data** cable (many bundled cables are charge-only)

## Quick start

Prerequisites: Python 3 with `esptool` and `mpremote` (`pip install esptool mpremote`). For photo conversion you also need Pillow + pillow-heif (`conda create -n badge-tools python=3.11 pillow pillow-heif`).

Plug the board in and run:

```bash
bash cyd-badge/setup_badge.sh "Your Name" path/to/photo.jpg
```

The script handles everything from any starting state: it finds the serial port, flashes MicroPython v1.27.0 if the board isn't running it (the firmware is bundled in `cyd-badge/firmware/`, so this works offline), sets your name, converts your photo (HEIC/JPG/PNG, cropped to 3:4 and resized to 96×128), and uploads all the code. The photo is optional — the badge works fine without one.

Other invocations:

```bash
bash cyd-badge/setup_badge.sh "Your Name"        # name only, no photo
bash cyd-badge/setup_badge.sh --flash "Your Name" # force a firmware reflash
bash cyd-badge/setup_badge.sh --code-only         # push code, keep existing name
```

## Hacking on it

### Repo layout

```
cyd-badge/
├── boot.py            # boot with a 3s Ctrl+C grace window for REPL access
├── main.py            # run loop: menu → app → back to menu
├── badge_os.py        # OS shell: display/touch init, frame loop, buttons, state
├── badge_config.py    # your name, socials, (optional) WiFi
├── apps/              # one module per app
├── drivers/           # ILI9341 + XPT2046 drivers (working — don't retune pins blindly)
├── fonts/             # 16px bitmap font renderer
├── firmware/          # bundled MicroPython .bin for offline flashing
└── tools/convert_image.py  # photo → raw BGR565 avatar.bin
```

### Writing an app

Apps are plain MicroPython modules in `cyd-badge/apps/` that expose:

```python
def init():                # optional, runs once at launch
    ...

def update(touch_pos):     # runs every frame; touch_pos is (x, y) or None
    ...
    return None            # keep running, or return "pong" to switch apps
```

Call `badge_os.request_menu()` to return to the launcher, then add your app to the list in `apps/menu.py`. Redeploy a single app with:

```bash
mpremote cp cyd-badge/apps/myapp.py :apps/myapp.py && mpremote reset
```

### Things to know

- **RAM is tight.** `main.py` deletes each app from `sys.modules` when it exits — don't rely on module state surviving across launches.
- **Two draw modes.** If there's enough free RAM at boot, the driver allocates a full framebuffer (`display._full_fb` is truthy): draw the whole scene each frame and the runner flushes it. Otherwise writes go straight to SPI and your app must erase its own previous pixels (see `apps/pong.py`). Support both.
- **Colors are byte-swapped BGR565.** Always go through `badge_os.rgb(r, g, b)` or the exported constants (`BLACK`, `WHITE`, `ORANGE`, …) — raw RGB565 ints come out wrong on this panel.
- **Text:** built-in `display.text()` is 8×8; use `fonts.bitmap_font.draw_text(...)` for the nicer 16px font.
- **Touch:** debounce taps yourself (`time.ticks_diff(now, last) > 400` is the house pattern). `badge_os.TouchButton` handles rectangular hit-testing, and `draw_back_button()` / `check_back_button()` give you the standard top-left "Menu" button.
- **Persistence:** `badge_os.State.save("myapp", {...})` / `State.load("myapp", defaults)` store JSON under `/state/` on the device — good for high scores and settings.
- **REPL access:** hold `Ctrl+C` during the 3-second boot window, or `mpremote repl`.

There's no test suite — verification is flashing the board and playing with it.

## License

Hack away. If you build something fun on it, we'd love to see it.
