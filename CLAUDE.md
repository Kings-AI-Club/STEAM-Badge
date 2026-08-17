# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

This repo holds **three independent badge firmwares**, each targeting different hardware and toolchains. Treat them as separate projects — they share no code at runtime, only the avatar image pipeline crosses boundaries.

| Directory       | Hardware                                  | Language / Stack                          | Status                |
| --------------- | ----------------------------------------- | ----------------------------------------- | --------------------- |
| `cyd-badge/`    | ESP32 CYD (ESP32-2432S028R), ILI9341+XPT2046 | MicroPython                            | **Active** — the badge being developed |
| `Badgerware/`   | Pimoroni Tufty 2350 (RP2350 + 8MB PSRAM)  | MicroPython (custom-built `.uf2`)         | Upstream copy of pimoroni/tufty2350 (`bw-1.27.0`) — alternative platform |
| `working-badge/`| ESP32 CYD (same board as `cyd-badge`)     | C++ / Arduino + LVGL v9.1 via PlatformIO  | Legacy C++ prototype; superseded by `cyd-badge` |

Root-level `cmd` is the canonical flash recipe for `cyd-badge` (esptool erase → write MicroPython → `mpremote cp` of all directories). `IMG_3720.HEIC` is the default avatar source consumed by the conversion tools.

## cyd-badge — primary project

### Flashing and deploying

First-time flash (erase + write MicroPython firmware, then sync code):

```bash
# Sequence from ./cmd — adjust port and firmware path as needed
esptool.py --chip esp32 --port /dev/cu.usbserial-1220 erase_flash
esptool.py --chip esp32 --port /dev/cu.usbserial-1220 --baud 460800 \
    write_flash -z 0x1000 '/path/to/ESP32 Generic v1.27.0.bin'
mpremote cp cyd-badge/boot.py :
mpremote cp cyd-badge/main.py :
mpremote cp cyd-badge/badge_os.py :
mpremote cp cyd-badge/badge_config.py :
mpremote cp -r cyd-badge/drivers :
mpremote cp -r cyd-badge/fonts :
mpremote cp -r cyd-badge/apps :
mpremote cp -r cyd-badge/resources :
mpremote reset
```

Iterative edit-and-redeploy of a single app:

```bash
mpremote cp cyd-badge/apps/<name>.py :apps/<name>.py && mpremote reset
```

Interactive REPL: hold `Ctrl+C` within the 3-second `boot.py` grace window, or use `mpremote repl`.

### Personalising the badge

`cyd-badge/setup_badge.sh "First Last" path/to/photo.{heic,jpg,png}` updates `badge_config.py`'s `NAME`, runs the image converter, and `mpremote`-pushes both files plus `resources/avatar.bin`. Image conversion requires the **`badge-tools` conda env** (Pillow + pillow-heif); the script invokes `conda run -n badge-tools python tools/convert_image.py …`. The converter crops to 3:4 portrait, resizes to 96×128, and writes raw BGR565 big-endian (matches ILI9341 panel MADCTL_BGR).

`tools/convert_avatar.py` is a separate one-off that re-extracts the 80×80 RGB565A8 image from the LVGL C array in `working-badge/lib/ui/` — only relevant if regenerating from the old C++ project.

### Architecture: `badge_os.py` + app modules

`badge_os.py` is the OS shell. Apps are plain MicroPython modules in `apps/` that expose:

- `init()` — optional, called once when the app launches.
- `update(touch_pos) -> Optional[str]` — called every frame with current touch coords or `None`. Return a module name (e.g. `"pong"`) to switch apps, or `None` to keep running. Calling `badge_os.request_menu()` from inside the app cleanly returns to the launcher.

`main.py` drives the run loop: it imports `apps.menu`, runs it, and when `menu.update` returns a module name it imports `apps.<name>`, runs it, then **deletes the module from `sys.modules`** before going back to the menu. This is load-bearing — RAM is tight, so apps must not assume module-level state persists across launches.

Frame loop lives in `badge_os.run_app(update_fn, init_fn, target_fps)`. `pong` runs at 25 fps; everything else at 10–15.

### Framebuffer vs direct-draw — important

On boot, `ILI9341.__init__` tries to allocate a full 153,600-byte framebuffer (`gc.mem_free()` must exceed `buf_size + 30000`). Result is exposed as `display._full_fb`. Apps must support **both modes**:

- **FB mode** (`_full_fb=True`): draw the whole scene every frame; the runner calls `display.show()` once per frame to flush.
- **Direct-draw mode**: writes go straight to SPI. Apps must erase previous positions themselves (see `pong._move_paddle`, sprite/trail handling) — there is no double-buffering.

Many apps check `if display._full_fb:` and take different paths. Don't break that branching.

### Colour and font conventions

- `rgb(r, g, b)` is an alias for `color565` which produces a **byte-swapped BGR565** value tuned for the CYD panel — don't pass raw RGB565 ints to draw calls.
- Constants like `BLACK`, `WHITE`, `ORANGE`, etc. are exported from `badge_os` — use them rather than re-deriving.
- Built-in MicroPython `display.text()` is 8×8. Use `fonts.bitmap_font.draw_text(display, s, x, y, color, scale=1)` for 16px text with the custom font; `measure_text(s, scale)` for layout.

### Touch handling

- Hand-rolled debounce: `if time.ticks_diff(now, _last_touch) > 400:` is the prevailing pattern (varies 400–800 ms by app).
- `TouchButton(x, y, w, h, label, color)` from `badge_os` for rectangular hit-testing; `draw_back_button()` + `check_back_button(touch_pos, btn)` for the standard "Menu" affordance in the top-left.
- `XPT2046` is on a separate SPI bus (VSPI, pins 25/32/39/33) from the display SPI (HSPI, pins 14/13/12/15) — both buses are mandatory and must not be re-merged.

### Persistent state

`badge_os.State.save(app_name, dict)` / `State.load(app_name, defaults)` writes JSON to `/state/<app>.json` on the device filesystem. Use for high-scores, settings, etc.

### `cyd-badge/tools/` quirk

`tools/` mirrors the top-level `cyd-badge/` layout (it contains its own `apps/`, `drivers/`, `fonts/`, `main.py`, etc.). It appears to be a working/staging copy used by the desktop converter scripts and possibly a backup. Edits should land in `cyd-badge/` proper, not in `cyd-badge/tools/`, unless you're modifying the conversion utilities themselves.

## Badgerware — Tufty 2350 MicroPython firmware

This is a Pimoroni upstream snapshot (target board `pimoroni_tufty2350`, RP2350). It builds a custom MicroPython `.uf2` rather than running on stock firmware.

Local lint (CI runs the same):

```bash
source Badgerware/ci/python.sh
qa_prepare_all       # pip install ruff
qa_firmware_check    # lint firmware/
qa_modules_check     # lint modules/
qa_examples_check    # lint examples/
qa_firmware_fix      # auto-fix variant
```

Ruff config is `Badgerware/ci/ruff.toml`; it whitelists Pimoroni's MicroPython built-ins (`io`, `pen`, `picovector`, etc.) and ignores `E501`/`E402`/`COM812`/`ICN001`.

Full firmware build (GitHub Actions does this; locally needs `arm-none-eabi-gcc` 14.2 + ccache + `pip install littlefs-python==0.12.0`):

```bash
export CI_PROJECT_ROOT=$(pwd)/Badgerware
export CI_BUILD_ROOT=$(pwd)/build
source Badgerware/ci/micropython.sh
ci_install_build_deps
ci_prepare_all        # clones pimoroni-pico + forked micropython (bw-1.27.0) + tools
ci_cmake_configure    # configures CMake against ports/rp2 with board=tufty
ci_cmake_build        # produces tufty.uf2 and tufty-with-filesystem.uf2
```

Apps live in `firmware/apps/<app_name>/` (each is its own dir). The runtime contract (`firmware/main.py` → `badgeware.run(menu.update)` → launches selected app dir) is similar in spirit to `cyd-badge` but uses a different API surface (`badgeware` module, `io.held`, `BUTTON_HOME` IRQ, `machine.reset()` to return to launcher).

## working-badge — legacy C++/LVGL

PlatformIO project, single env:

```bash
cd working-badge
pio run                 # build
pio run -t upload       # build + flash
pio device monitor      # serial @ 115200
```

`platformio.ini` pins `board=esp32dev`, framework `arduino`, monitor speed 115200. UI was generated by Squareline Studio (LVGL 9.1); the avatar image at `lib/ui/ui_img_1147937936.c` is the source of truth that `cyd-badge/tools/convert_avatar.py` consumes.

This project is no longer the active badge — prefer changes to `cyd-badge/`. Touch calibration values are hard-coded at the top of `src/main.cpp` (`touchScreenMinimumX = 200`, etc.) and may need re-tuning per panel.

## Cross-project notes

- The badge identity is "Made by King's AI Seminar". `cyd-badge/badge_config.py` is the per-device config; do not commit a real `WIFI_PASS`. `Badgerware/firmware/secrets.py` and `Badgerware/modules/common/secrets.py` are the equivalents for the Tufty.
- This repo has no test suite — verification is done by flashing and running on hardware.
- The HSPI/VSPI split on the CYD board is a footgun: every CYD driver online does it differently. The drivers in `cyd-badge/drivers/` are working — don't refactor pin assignments without re-testing.
