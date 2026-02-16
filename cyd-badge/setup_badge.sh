#!/bin/bash
#
# ╔══════════════════════════════════════════════════════╗
# ║          STEAM Badge — Quick Setup Script            ║
# ╚══════════════════════════════════════════════════════╝
#
# This script lets you change the NAME and PHOTO on your badge.
#
# USAGE:
#   cd /Users/arona/Documents/GitHub/STEAM-Badge
#   bash cyd-badge/setup_badge.sh "First Last" /path/to/photo.heic
#
# EXAMPLES:
#   bash cyd-badge/setup_badge.sh "Michael Ienna" IMG_3720.HEIC
#   bash cyd-badge/setup_badge.sh "Rev Edward" ~/Desktop/selfie.jpg
#   bash cyd-badge/setup_badge.sh "Jane Doe" ~/Photos/photo.png
#
# SUPPORTED IMAGE FORMATS: HEIC, JPG, PNG, BMP, TIFF
# The photo will be auto-cropped to 3:4 portrait and resized to 96x128.
#
# FILES MODIFIED:
#   cyd-badge/badge_config.py  — your name (on your computer)
#   resources/avatar.bin       — your photo (on the badge device)
#   badge_config.py            — your name (on the badge device)
#

set -e

# ─── Paths ──────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$SCRIPT_DIR/badge_config.py"
CONVERTER="$SCRIPT_DIR/tools/convert_image.py"
AVATAR_BIN="$SCRIPT_DIR/resources/avatar.bin"

# ─── Colors for pretty output ──────────────────────────
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     🎮  STEAM Badge Setup  🎮           ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# ─── Parse arguments or ask interactively ──────────────
if [ -n "$1" ]; then
    NAME="$1"
else
    echo -e "${YELLOW}Enter your name (First Last):${NC}"
    read -r NAME
fi

if [ -n "$2" ]; then
    PHOTO="$2"
else
    echo -e "${YELLOW}Enter path to your photo (HEIC/JPG/PNG):${NC}"
    echo -e "${YELLOW}(press Enter to skip and keep current photo)${NC}"
    read -r PHOTO
    # Strip surrounding quotes (users often paste paths with quotes)
    PHOTO=$(echo "$PHOTO" | sed "s/^['\"]//;s/['\"]$//")
fi

echo ""
echo -e "${GREEN}Name:${NC}  $NAME"
echo -e "${GREEN}Photo:${NC} ${PHOTO:-<keeping current>}"
echo ""

# ─── Step 1: Update name in badge_config.py ────────────
echo -e "${CYAN}[1/3] Updating name in badge_config.py...${NC}"

# Escape special characters for sed
ESCAPED_NAME=$(echo "$NAME" | sed 's/[&/\]/\\&/g')
sed -i '' "s/^NAME = .*/NAME = \"$ESCAPED_NAME\"/" "$CONFIG_FILE"

echo -e "      ${GREEN}✓${NC} Name set to: $NAME"
echo -e "      File: $CONFIG_FILE"

# ─── Step 2: Convert photo (if provided) ──────────────
if [ -n "$PHOTO" ]; then
    if [ ! -f "$PHOTO" ]; then
        # Try relative to repo root
        if [ -f "$REPO_ROOT/$PHOTO" ]; then
            PHOTO="$REPO_ROOT/$PHOTO"
        else
            echo -e "${RED}✗ Photo not found: $PHOTO${NC}"
            exit 1
        fi
    fi

    echo -e "${CYAN}[2/3] Converting photo to badge format...${NC}"
    echo -e "      Input:  $PHOTO"
    echo -e "      Output: $AVATAR_BIN"

    conda run -n badge-tools python "$CONVERTER" "$PHOTO"

    echo -e "      ${GREEN}✓${NC} Photo converted (96x128 RGB565)"
else
    echo -e "${CYAN}[2/3] Skipping photo (no image provided)${NC}"
fi

# ─── Step 3: Upload to device ─────────────────────────
echo ""
echo -e "${CYAN}[3/3] Uploading to badge...${NC}"
echo -e "      (Make sure the badge is plugged in via USB)"
echo ""

# Upload config
mpremote cp "$CONFIG_FILE" :badge_config.py
echo -e "      ${GREEN}✓${NC} badge_config.py uploaded"

# Upload photo if it was converted
if [ -n "$PHOTO" ]; then
    mpremote cp "$AVATAR_BIN" :resources/avatar.bin
    echo -e "      ${GREEN}✓${NC} avatar.bin uploaded"
fi

# Reset device
mpremote reset
echo -e "      ${GREEN}✓${NC} Badge reset"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     ✅  Badge updated successfully!      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "Your badge now shows: ${YELLOW}$NAME${NC}"
echo ""
