#!/bin/bash
#
# ╔══════════════════════════════════════════════════════╗
# ║          STEAM Badge — Setup / Flash Script          ║
# ╚══════════════════════════════════════════════════════╝
#
# Sets up a CYD badge from any starting state: blank board, board running
# the old C++/LVGL firmware, or a board already running BadgeOS.
#
# USAGE:
#   bash cyd-badge/setup_badge.sh "First Last"                  # name only
#   bash cyd-badge/setup_badge.sh "First Last" photo.heic       # name + photo
#   bash cyd-badge/setup_badge.sh --flash "First Last"          # force firmware reflash
#   bash cyd-badge/setup_badge.sh --code-only                   # push code, keep name
#
# The script auto-detects the serial port and auto-detects whether the board
# is running MicroPython. If it isn't, it flashes MicroPython first — this is
# the step the old script was missing, which made every `mpremote` call fail
# with "could not enter raw repl".
#
# OFFLINE: the MicroPython firmware ships in cyd-badge/firmware/, so a full
# flash works with no internet. Only image conversion needs a local Pillow env.
#
# SUPPORTED IMAGE FORMATS: HEIC, JPG, PNG, BMP, TIFF (cropped 3:4, 96x128).
# The photo is optional — the badge renders fine with no avatar.
#

set -e

# ─── Config ─────────────────────────────────────────────
MPY_VERSION="v1.27.0"
MPY_FILE="ESP32_GENERIC-20251209-${MPY_VERSION}.bin"
MPY_URL="https://micropython.org/resources/firmware/${MPY_FILE}"
MPY_SHA256="aa4be80ec695911ba0f13f7558e559ce540f90efbf40c23b853ca49162136b9f"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$SCRIPT_DIR/badge_config.py"
CONVERTER="$SCRIPT_DIR/tools/convert_image.py"
AVATAR_BIN="$SCRIPT_DIR/resources/avatar.bin"

# Firmware ships with the repo so setup works with no internet. The download
# below is only a fallback for when someone deletes/never checked out the blob.
FW_BUNDLED="$SCRIPT_DIR/firmware/$MPY_FILE"
FW_CACHE="$REPO_ROOT/.firmware/$MPY_FILE"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; NC='\033[0m'

info()  { echo -e "${CYAN}$*${NC}"; }
ok()    { echo -e "      ${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}! $*${NC}"; }
die()   { echo -e "${RED}✗ $*${NC}" >&2; exit 1; }

echo ""
info "╔══════════════════════════════════════════╗"
info "║         =  STEAM Badge Setup  =          ║"
info "╚══════════════════════════════════════════╝"
echo ""

# ─── Parse arguments ───────────────────────────────────
FORCE_FLASH=0
CODE_ONLY=0
ARGS=()
for a in "$@"; do
    case "$a" in
        --flash)     FORCE_FLASH=1 ;;
        --code-only) CODE_ONLY=1 ;;
        *)           ARGS+=("$a") ;;
    esac
done

NAME="${ARGS[0]:-}"
PHOTO="${ARGS[1]:-}"

if [ "$CODE_ONLY" -eq 0 ] && [ -z "$NAME" ]; then
    echo -e "${YELLOW}Enter your name (First Last):${NC}"
    read -r NAME
    echo -e "${YELLOW}Path to photo (HEIC/JPG/PNG), or press Enter for none:${NC}"
    read -r PHOTO
    PHOTO=$(echo "$PHOTO" | sed "s/^['\"]//;s/['\"]$//")
fi

# ─── Find the board ────────────────────────────────────
info "[1/5] Finding badge..."

PORT=""
for _ in 1 2 3 4 5 6 7 8 9 10; do
    PORT=$(ls /dev/cu.usbserial-* /dev/cu.wchusbserial* /dev/cu.SLAB_USBtoUART* 2>/dev/null | head -1 || true)
    [ -n "$PORT" ] && break
    echo "      waiting for board to appear on USB..."
    sleep 1
done

[ -n "$PORT" ] || die "No badge found. Plug it in via USB (a data cable, not charge-only) and retry."
ok "Found badge at: $PORT"

# mpremote sometimes races the CH340 re-enumerating; retry a few times.
mp() {
    local tries=0
    until mpremote connect "$PORT" "$@"; do
        tries=$((tries + 1))
        [ "$tries" -ge 4 ] && return 1
        sleep 2
    done
}

# ─── Flash MicroPython if needed ───────────────────────
info "[2/5] Checking firmware..."

NEEDS_FLASH=$FORCE_FLASH
if [ "$NEEDS_FLASH" -eq 0 ]; then
    if mpremote connect "$PORT" exec "print(1)" >/dev/null 2>&1; then
        ok "MicroPython already running"
    else
        warn "Board is not running MicroPython (likely the old C++ firmware)"
        NEEDS_FLASH=1
    fi
fi

if [ "$NEEDS_FLASH" -eq 1 ]; then
    if [ -f "$FW_BUNDLED" ]; then
        FW="$FW_BUNDLED"
        ok "Firmware: bundled copy (no download needed)"
    elif [ -f "$FW_CACHE" ]; then
        FW="$FW_CACHE"
        ok "Firmware: cached copy"
    else
        warn "Bundled firmware missing at $FW_BUNDLED — falling back to download"
        info "      Downloading MicroPython $MPY_VERSION..."
        mkdir -p "$(dirname "$FW_CACHE")"
        curl -fsSL -o "$FW_CACHE" "$MPY_URL" || die "Firmware download failed and no
     bundled copy is present. With no internet, restore the file with:
       git checkout -- cyd-badge/firmware/$MPY_FILE"
        FW="$FW_CACHE"
        ok "Firmware: $FW"
    fi

    # Guard against a truncated/corrupt blob (e.g. git-lfs pointer, bad copy).
    if command -v shasum >/dev/null 2>&1; then
        ACTUAL_SHA=$(shasum -a 256 "$FW" | cut -d' ' -f1)
        [ "$ACTUAL_SHA" = "$MPY_SHA256" ] || \
            die "Firmware checksum mismatch for $FW
     expected $MPY_SHA256
     got      $ACTUAL_SHA"
    fi

    info "      Erasing flash (this wipes any existing firmware)..."
    esptool.py --chip esp32 --port "$PORT" erase_flash >/dev/null
    info "      Writing MicroPython..."
    esptool.py --chip esp32 --port "$PORT" --baud 460800 \
        write_flash -z 0x1000 "$FW" >/dev/null
    ok "MicroPython $MPY_VERSION flashed"
    sleep 3
fi

# ─── Update name ───────────────────────────────────────
if [ "$CODE_ONLY" -eq 1 ]; then
    info "[3/5] Keeping existing name"
else
    info "[3/5] Setting name..."
    ESCAPED_NAME=$(echo "$NAME" | sed 's/[&/\]/\\&/g')
    sed -i '' "s/^NAME = .*/NAME = \"$ESCAPED_NAME\"/" "$CONFIG_FILE"
    ok "Name set to: $NAME"
fi

# ─── Convert photo (optional) ──────────────────────────
info "[4/5] Photo..."
HAVE_AVATAR=0

if [ -n "$PHOTO" ]; then
    if [ ! -f "$PHOTO" ] && [ -f "$REPO_ROOT/$PHOTO" ]; then
        PHOTO="$REPO_ROOT/$PHOTO"
    fi
    [ -f "$PHOTO" ] || die "Photo not found: $PHOTO"

    if conda env list 2>/dev/null | grep -q '^badge-tools'; then
        conda run -n badge-tools python "$CONVERTER" "$PHOTO"
    elif python3 -c "import PIL" 2>/dev/null; then
        python3 "$CONVERTER" "$PHOTO"
    else
        die "Image conversion needs Pillow. Create the env with:
     conda create -n badge-tools python=3.11 pillow pillow-heif"
    fi
    HAVE_AVATAR=1
    ok "Photo converted (96x128)"
elif [ -f "$AVATAR_BIN" ]; then
    HAVE_AVATAR=1
    ok "Using existing avatar.bin"
else
    ok "No photo — badge will render without an avatar"
fi

# ─── Upload ────────────────────────────────────────────
info "[5/5] Uploading to badge..."

mp cp "$SCRIPT_DIR/boot.py" : >/dev/null
mp cp "$SCRIPT_DIR/main.py" : >/dev/null
mp cp "$SCRIPT_DIR/badge_os.py" : >/dev/null
mp cp "$SCRIPT_DIR/badge_config.py" : >/dev/null
ok "core files"

mp cp -r "$SCRIPT_DIR/drivers" : >/dev/null
mp cp -r "$SCRIPT_DIR/fonts" : >/dev/null
mp cp -r "$SCRIPT_DIR/apps" : >/dev/null
ok "drivers, fonts, apps"

# resources/ must exist even with no avatar — apps/badge.py handles a
# missing avatar.bin, but the directory itself needs to be there.
mp mkdir :resources >/dev/null 2>&1 || true
if [ "$HAVE_AVATAR" -eq 1 ]; then
    mp cp "$AVATAR_BIN" :resources/avatar.bin >/dev/null
    ok "avatar.bin"
fi

mp reset >/dev/null 2>&1 || true

echo ""
info "╔══════════════════════════════════════════╗"
info "║     ✅  Badge updated successfully!      ║"
info "╚══════════════════════════════════════════╝"
echo ""
[ "$CODE_ONLY" -eq 0 ] && echo -e "Your badge now shows: ${YELLOW}$NAME${NC}"
echo ""
