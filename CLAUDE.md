# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A hackable conference badge for the ESP32 CYD (ESP32-2432S028R, ILI9341 display + XPT2046 touch), written in MicroPython. All code lives in `cyd-badge/`. See `README.md` for user-facing setup; this file covers what matters when changing code.

## Flashing and deploying

`cyd-badge/setup_badge.sh` is the canonical setup path — it auto-detects the port, flashes the bundled MicroPython v1.27.0 from `cyd-badge/firmware/` if needed, personalizes `badge_config.py`, converts the photo, and pushes everything with `mpremote`.

Iterative edit-and-redeploy of a single app:

```bash
mpremote cp cyd-badge/apps/<name>.py :apps/<name>.py && mpremote reset
```

Interactive REPL: hold `Ctrl+C` within the 3-second `boot.py` grace window, or use `mpremote repl`.

Image conversion (`tools/convert_image.py`) needs Pillow + pillow-heif; the script prefers the **`badge-tools` conda env** (`conda run -n badge-tools …`) and falls back to system `python3` if Pillow is importable. The converter crops to 3:4 portrait, resizes to 96×128, and writes raw BGR565 big-endian (matches ILI9341 panel MADCTL_BGR). `resources/avatar.bin` is gitignored — it's the owner's personal photo, generated locally.

## Architecture: `badge_os.py` + app modules

`badge_os.py` is the OS shell. Apps are plain MicroPython modules in `apps/` that expose:

- `init()` — optional, called once when the app launches.
- `update(touch_pos) -> Optional[str]` — called every frame with current touch coords or `None`. Return a module name (e.g. `"pong"`) to switch apps, or `None` to keep running. Calling `badge_os.request_menu()` from inside the app cleanly returns to the launcher.

`main.py` drives the run loop: it imports `apps.menu`, runs it, and when `menu.update` returns a module name it imports `apps.<name>`, runs it, then **deletes the module from `sys.modules`** before going back to the menu. This is load-bearing — RAM is tight, so apps must not assume module-level state persists across launches.

Frame loop lives in `badge_os.run_app(update_fn, init_fn, target_fps)`. `pong` runs at 25 fps; everything else at 10–15.

## Framebuffer vs direct-draw — important

On boot, `ILI9341.__init__` tries to allocate a full 153,600-byte framebuffer (`gc.mem_free()` must exceed `buf_size + 30000`). Result is exposed as `display._full_fb`. Apps must support **both modes**:

- **FB mode** (`_full_fb=True`): draw the whole scene every frame; the runner calls `display.show()` once per frame to flush.
- **Direct-draw mode**: writes go straight to SPI. Apps must erase previous positions themselves (see `pong._move_paddle`, sprite/trail handling) — there is no double-buffering.

Many apps check `if display._full_fb:` and take different paths. Don't break that branching.

## Colour and font conventions

- `rgb(r, g, b)` is an alias for `color565` which produces a **byte-swapped BGR565** value tuned for the CYD panel — don't pass raw RGB565 ints to draw calls.
- Constants like `BLACK`, `WHITE`, `ORANGE`, etc. are exported from `badge_os` — use them rather than re-deriving.
- Built-in MicroPython `display.text()` is 8×8. Use `fonts.bitmap_font.draw_text(display, s, x, y, color, scale=1)` for 16px text with the custom font; `measure_text(s, scale)` for layout.

## Touch handling

- Hand-rolled debounce: `if time.ticks_diff(now, _last_touch) > 400:` is the prevailing pattern (varies 400–800 ms by app).
- `TouchButton(x, y, w, h, label, color)` from `badge_os` for rectangular hit-testing; `draw_back_button()` + `check_back_button(touch_pos, btn)` for the standard "Menu" affordance in the top-left.
- `XPT2046` is on a separate SPI bus (VSPI, pins 25/32/39/33) from the display SPI (HSPI, pins 14/13/12/15) — both buses are mandatory and must not be re-merged. The HSPI/VSPI split on the CYD board is a footgun: every CYD driver online does it differently. The drivers in `cyd-badge/drivers/` are working — don't refactor pin assignments without re-testing.

## Persistent state

`badge_os.State.save(app_name, dict)` / `State.load(app_name, defaults)` writes JSON to `/state/<app>.json` on the device filesystem. Use for high-scores, settings, etc.

## Notes

- The badge identity is "Made by King's AI Seminar". `cyd-badge/badge_config.py` is the per-device config; do not commit a real `WIFI_PASS` or personal details.
- This repo has no test suite — verification is done by flashing and running on hardware.
