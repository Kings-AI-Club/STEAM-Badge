"""
Tetris - Classic block puzzle for ESP32 CYD.

Uses the long edge (portrait) so user rotates device 90 degrees.
Tap to rotate, drag left/right to move piece.
Renders in landscape coordinates but draws rotated.
"""
import gc
import time
import random
from badge_os import (display, WIDTH, HEIGHT, rgb, BLACK, WHITE,
                      draw_back_button, check_back_button)
from fonts import bitmap_font

# ─── The game runs in a virtual 240x320 portrait space ─────────
# But we draw to the 320x240 landscape display by swapping coords:
#   virtual (vx, vy) -> screen (WIDTH-1-vy, vx)
# This means the user holds the device sideways (USB port up/down).

VW = HEIGHT   # 240 virtual width
VH = WIDTH    # 320 virtual height

# ─── Colors ─────────────────────────────────────────────────────

BG = rgb(8, 8, 20)
GRID_CLR = rgb(20, 20, 40)
BORDER = rgb(60, 40, 180)
TEXT_CLR = rgb(200, 200, 255)
TEXT_DIM = rgb(80, 80, 140)
GAMEOVER_CLR = rgb(255, 80, 80)

PIECE_COLORS = [
    rgb(0, 240, 240),    # I - cyan
    rgb(0, 0, 240),      # J - blue
    rgb(240, 160, 0),    # L - orange
    rgb(240, 240, 0),    # O - yellow
    rgb(0, 240, 0),      # S - green
    rgb(160, 0, 240),    # T - purple
    rgb(240, 0, 0),      # Z - red
]

# ─── Piece definitions (4 rotations each) ──────────────────────

PIECES = [
    # I
    [[(0,1),(1,1),(2,1),(3,1)], [(2,0),(2,1),(2,2),(2,3)],
     [(0,2),(1,2),(2,2),(3,2)], [(1,0),(1,1),(1,2),(1,3)]],
    # J
    [[(0,0),(0,1),(1,1),(2,1)], [(1,0),(2,0),(1,1),(1,2)],
     [(0,1),(1,1),(2,1),(2,2)], [(1,0),(1,1),(0,2),(1,2)]],
    # L
    [[(2,0),(0,1),(1,1),(2,1)], [(1,0),(1,1),(1,2),(2,2)],
     [(0,1),(1,1),(2,1),(0,2)], [(0,0),(1,0),(1,1),(1,2)]],
    # O
    [[(1,0),(2,0),(1,1),(2,1)]] * 4,
    # S
    [[(1,0),(2,0),(0,1),(1,1)], [(1,0),(1,1),(2,1),(2,2)],
     [(1,1),(2,1),(0,2),(1,2)], [(0,0),(0,1),(1,1),(1,2)]],
    # T
    [[(1,0),(0,1),(1,1),(2,1)], [(1,0),(1,1),(2,1),(1,2)],
     [(0,1),(1,1),(2,1),(1,2)], [(1,0),(0,1),(1,1),(1,2)]],
    # Z
    [[(0,0),(1,0),(1,1),(2,1)], [(2,0),(1,1),(2,1),(1,2)],
     [(0,1),(1,1),(1,2),(2,2)], [(1,0),(0,1),(1,1),(0,2)]],
]

# ─── Game constants ─────────────────────────────────────────────

COLS = 10
ROWS = 20
CELL = min(VW // (COLS + 8), VH // (ROWS + 2))  # cell size in pixels
BOARD_X = (VW - COLS * CELL) // 2
BOARD_Y = (VH - ROWS * CELL) // 2

# ─── State ──────────────────────────────────────────────────────

STATE_TITLE = 0
STATE_PLAY = 1
STATE_OVER = 2

_state = STATE_TITLE
_board = []  # ROWS x COLS, 0 = empty, >0 = color index+1
_cur_piece = 0
_cur_rot = 0
_cur_x = 0
_cur_y = 0
_score = 0
_lines = 0
_level = 1
_drop_interval = 500  # ms
_last_drop = 0
_back_btn = None
_needs_full = True
_touch_start = None
_touch_debounce = 0
_game_tick = 0


def _vdraw_rect(vx, vy, vw, vh, color):
    """Draw a rect in virtual portrait coords -> landscape screen."""
    # virtual (vx, vy) -> screen (WIDTH-1-vy-vh+1, vx)
    sx = WIDTH - vy - vh
    sy = vx
    display.fill_rect(sx, sy, vh, vw, color)


def _vdraw_pixel(vx, vy, color):
    sx = WIDTH - 1 - vy
    sy = vx
    display.pixel(sx, sy, color)


def _vdraw_text(text, vx, vy, color):
    """Draw text readable when device is rotated sideways.
    Each character is placed stepping along virtual-X (screen-Y),
    so the string runs vertically on screen = horizontally when rotated."""
    for ch in text:
        sx = WIDTH - 1 - vy
        sy = vx
        display.text(ch, sx, sy, color)
        vx += 8


def _vdraw_cell(col, row, color):
    """Draw a single cell on the board."""
    vx = BOARD_X + col * CELL
    vy = BOARD_Y + row * CELL
    _vdraw_rect(vx + 1, vy + 1, CELL - 2, CELL - 2, color)


def _new_board():
    return [[0] * COLS for _ in range(ROWS)]


def _get_cells(piece, rot, px, py):
    """Get absolute cell positions for a piece."""
    return [(px + dx, py + dy) for dx, dy in PIECES[piece][rot % 4]]


def _fits(piece, rot, px, py):
    """Check if piece fits at position."""
    for cx, cy in _get_cells(piece, rot, px, py):
        if cx < 0 or cx >= COLS or cy >= ROWS:
            return False
        if cy >= 0 and _board[cy][cx]:
            return False
    return True


def _lock_piece():
    """Lock current piece into board and check lines."""
    global _score, _lines, _level, _drop_interval, _state

    color_idx = _cur_piece + 1
    for cx, cy in _get_cells(_cur_piece, _cur_rot, _cur_x, _cur_y):
        if 0 <= cy < ROWS and 0 <= cx < COLS:
            _board[cy][cx] = color_idx

    # Check for completed lines
    cleared = 0
    row = ROWS - 1
    while row >= 0:
        if all(_board[row]):
            del _board[row]
            _board.insert(0, [0] * COLS)
            cleared += 1
        else:
            row -= 1

    if cleared:
        _lines += cleared
        _score += [0, 100, 300, 500, 800][min(cleared, 4)] * _level
        _level = 1 + _lines // 10
        _drop_interval = max(100, 500 - (_level - 1) * 40)

    # Spawn new piece
    if not _spawn_piece():
        _state = STATE_OVER


def _spawn_piece():
    """Spawn a new random piece at top."""
    global _cur_piece, _cur_rot, _cur_x, _cur_y
    _cur_piece = random.getrandbits(3) % 7
    _cur_rot = 0
    _cur_x = COLS // 2 - 2
    _cur_y = -1
    return _fits(_cur_piece, _cur_rot, _cur_x, _cur_y)


def init():
    global _state, _board, _score, _lines, _level
    global _drop_interval, _last_drop, _needs_full, _back_btn
    global _touch_start, _touch_debounce, _game_tick

    _state = STATE_TITLE
    _board = _new_board()
    _score = 0
    _lines = 0
    _level = 1
    _drop_interval = 500
    _last_drop = 0
    _needs_full = True
    _touch_start = None
    _touch_debounce = 0
    _game_tick = 0
    gc.collect()


def _draw_board():
    """Draw the full board and border."""
    # Board background
    _vdraw_rect(BOARD_X, BOARD_Y, COLS * CELL, ROWS * CELL, BG)

    # Border
    bx, by = BOARD_X - 2, BOARD_Y - 2
    bw, bh = COLS * CELL + 4, ROWS * CELL + 4
    # Top
    _vdraw_rect(bx, by, bw, 2, BORDER)
    # Bottom
    _vdraw_rect(bx, by + bh - 2, bw, 2, BORDER)
    # Left
    _vdraw_rect(bx, by, 2, bh, BORDER)
    # Right
    _vdraw_rect(bx + bw - 2, by, 2, bh, BORDER)

    # Grid lines
    for r in range(ROWS):
        for c in range(COLS):
            if _board[r][c]:
                _vdraw_cell(c, r, PIECE_COLORS[_board[r][c] - 1])

    # Score area (right side in virtual portrait = top in landscape)
    info_x = BOARD_X + COLS * CELL + 10
    _vdraw_text("SCORE", info_x, BOARD_Y, TEXT_DIM)
    _vdraw_text(str(_score), info_x, BOARD_Y + 12, TEXT_CLR)
    _vdraw_text("LINES", info_x, BOARD_Y + 30, TEXT_DIM)
    _vdraw_text(str(_lines), info_x, BOARD_Y + 42, TEXT_CLR)
    _vdraw_text("LVL", info_x, BOARD_Y + 60, TEXT_DIM)
    _vdraw_text(str(_level), info_x, BOARD_Y + 72, TEXT_CLR)


def _draw_piece(piece, rot, px, py, color):
    """Draw a piece on the board."""
    for cx, cy in _get_cells(piece, rot, px, py):
        if 0 <= cy < ROWS and 0 <= cx < COLS:
            _vdraw_cell(cx, cy, color)


def _erase_piece(piece, rot, px, py):
    """Erase a piece from the board."""
    for cx, cy in _get_cells(piece, rot, px, py):
        if 0 <= cy < ROWS and 0 <= cx < COLS:
            _vdraw_cell(cx, cy, BG)


def update(touch_pos):
    global _state, _needs_full, _last_drop, _touch_debounce
    global _cur_x, _cur_y, _cur_rot, _touch_start, _game_tick, _back_btn
    global _board, _score, _lines, _level, _drop_interval

    ticks = time.ticks_ms()

    if _needs_full:
        _needs_full = False
        display.fill(BG)
        _back_btn = draw_back_button()

        if _state == STATE_TITLE:
            # Title screen — draw in landscape directly
            tw = bitmap_font.measure_text("TETRIS", 3)
            bitmap_font.draw_text(display, "TETRIS", (WIDTH - tw) // 2, 60,
                                  BORDER, 3)
            tw2 = bitmap_font.measure_text("Tap to Start", 1)
            bitmap_font.draw_text(display, "Tap to Start",
                                  (WIDTH - tw2) // 2, 120, TEXT_CLR, 1)
            t3 = len("Turn device sideways!") * 8
            display.text("Turn device sideways!", (WIDTH - t3) // 2, 150,
                         TEXT_DIM)
            t4 = len("Tap=Rotate  Drag=Move") * 8
            display.text("Tap=Rotate  Drag=Move", (WIDTH - t4) // 2, 170,
                         TEXT_DIM)

        elif _state == STATE_PLAY:
            _draw_board()
            _draw_piece(_cur_piece, _cur_rot, _cur_x, _cur_y,
                        PIECE_COLORS[_cur_piece])

        elif _state == STATE_OVER:
            _draw_board()
            bitmap_font.draw_text(display, "GAME", 110, 80, GAMEOVER_CLR, 3)
            bitmap_font.draw_text(display, "OVER", 110, 130, GAMEOVER_CLR, 3)
            display.text("Score: " + str(_score), 115, 180, TEXT_CLR)
            display.text("Tap to restart", 105, 200, TEXT_DIM)

        if display._full_fb:
            display.show()
        return None

    if display._full_fb:
        display.fill(BG)
        _back_btn = draw_back_button()

    if _state == STATE_TITLE:
        if touch_pos and time.ticks_diff(ticks, _touch_debounce) > 500:
            if check_back_button(touch_pos, _back_btn):
                return None
            _state = STATE_PLAY
            _board = _new_board()
            _score = 0
            _lines = 0
            _level = 1
            _drop_interval = 500
            _spawn_piece()
            _last_drop = ticks
            _touch_debounce = ticks
            _needs_full = True
        return None

    elif _state == STATE_PLAY:
        # Touch: map screen touch to virtual portrait coords
        # Screen touch (sx, sy) -> virtual (sy, WIDTH-1-sx)
        if touch_pos:
            if check_back_button(touch_pos, _back_btn):
                return None

            sx, sy = touch_pos
            # Map to virtual coords
            vx = sy
            vy = WIDTH - 1 - sx

            if _touch_start is None:
                _touch_start = (vx, vy, ticks)
            else:
                start_vx, start_vy, start_t = _touch_start
                dx = vx - start_vx  # horizontal movement in virtual space
                dy = vy - start_vy  # vertical movement (down = positive)

                # Hard drop: drag down
                if dy > CELL * 2:
                    _erase_piece(_cur_piece, _cur_rot, _cur_x, _cur_y)
                    while _fits(_cur_piece, _cur_rot, _cur_x, _cur_y + 1):
                        _cur_y += 1
                    _draw_piece(_cur_piece, _cur_rot, _cur_x, _cur_y,
                                PIECE_COLORS[_cur_piece])
                    _lock_piece()
                    if _state == STATE_OVER:
                        _needs_full = True
                    else:
                        _needs_full = True
                    _touch_start = None
                    _touch_debounce = ticks
                    return None

                # Horizontal movement — follow finger position
                if abs(dx) >= CELL and time.ticks_diff(ticks, _touch_debounce) > 80:
                    direction = 1 if dx > 0 else -1
                    if _fits(_cur_piece, _cur_rot, _cur_x + direction, _cur_y):
                        _erase_piece(_cur_piece, _cur_rot, _cur_x, _cur_y)
                        _cur_x += direction
                        _draw_piece(_cur_piece, _cur_rot, _cur_x, _cur_y,
                                    PIECE_COLORS[_cur_piece])
                    _touch_start = (vx, vy, ticks)
                    _touch_debounce = ticks
        else:
            # Touch released — tap = rotate
            if _touch_start is not None:
                start_vx, start_vy, start_t = _touch_start
                dt = time.ticks_diff(ticks, start_t)
                dx = abs(start_vx - start_vx)  # no movement needed for tap
                if dt < 300:
                    new_rot = (_cur_rot + 1) % 4
                    if _fits(_cur_piece, new_rot, _cur_x, _cur_y):
                        _erase_piece(_cur_piece, _cur_rot, _cur_x, _cur_y)
                        _cur_rot = new_rot
                        _draw_piece(_cur_piece, _cur_rot, _cur_x, _cur_y,
                                    PIECE_COLORS[_cur_piece])
                _touch_start = None

        # Auto-drop
        if time.ticks_diff(ticks, _last_drop) >= _drop_interval:
            _last_drop = ticks
            if _fits(_cur_piece, _cur_rot, _cur_x, _cur_y + 1):
                _erase_piece(_cur_piece, _cur_rot, _cur_x, _cur_y)
                _cur_y += 1
                _draw_piece(_cur_piece, _cur_rot, _cur_x, _cur_y,
                            PIECE_COLORS[_cur_piece])
            else:
                _lock_piece()
                if _state == STATE_OVER:
                    _needs_full = True
                else:
                    _needs_full = True  # Redraw board after line clear

        if display._full_fb:
            display.show()

    elif _state == STATE_OVER:
        if touch_pos and time.ticks_diff(ticks, _touch_debounce) > 800:
            _touch_debounce = ticks
            init()
            _state = STATE_TITLE
            _needs_full = True

    return None
