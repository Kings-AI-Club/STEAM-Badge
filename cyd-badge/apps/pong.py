"""
Tennis - Pong game for ESP32 CYD.

Classic Pong with 90s hacker aesthetic. Flicker-free sprite updates:
paddles use differential erase (only erase uncovered strips).
"""
import gc
import time
import random
from badge_os import (display, WIDTH, HEIGHT, rgb, BLACK, WHITE,
                      MID_GREY, draw_back_button,
                      check_back_button, request_menu)
from fonts import bitmap_font

# ─── Hacker Theme Colors ───────────────────────────────────────

COURT_BG = rgb(2, 8, 4)
NET_COLOR = rgb(0, 40, 15)
BALL_COLOR = rgb(0, 255, 80)
PAD_COLOR = rgb(0, 200, 60)
SCORE_COLOR = rgb(0, 255, 80)
TEXT_DIM = rgb(0, 120, 40)

CX = WIDTH // 2
CY = HEIGHT // 2
WIN_SCORE = 6

# ─── Game Objects ──────────────────────────────────────────────

STATE_INTRO = 0
STATE_PLAYING = 1
STATE_OVER = 2

# Ball
ball_x = 0.0
ball_y = 0.0
ball_dx = 0.0
ball_dy = 0.0
ball_speed = 4.0
BALL_SZ = 6

# Paddles
PAD_W = 8
PAD_H = 40
player_y = 0.0
player_x = WIDTH - PAD_W - 6
cpu_y = 0.0
cpu_x = 6

# Scores
player_score = 0
cpu_score = 0

state = STATE_INTRO
_back_btn = None
_touch_debounce = 0
_needs_full_draw = True

# Previous positions for flicker-free updates
_prev_ball_x = -1
_prev_ball_y = -1
_prev_player_y = -1
_prev_cpu_y = -1


def _reset_ball(direction):
    """Reset ball to center."""
    global ball_x, ball_y, ball_dx, ball_dy, ball_speed
    ball_x = float(CX)
    ball_y = float(CY)
    ball_dx = 2.5 * direction
    ball_dy = (random.getrandbits(8) - 128) / 200.0
    ball_speed = 4.0


def init():
    """Initialize the tennis game."""
    global player_y, cpu_y, player_score, cpu_score, state
    global _back_btn, _needs_full_draw
    global _prev_ball_x, _prev_ball_y, _prev_player_y, _prev_cpu_y

    _reset_ball(-1)
    player_y = float(CY - PAD_H // 2)
    cpu_y = float(CY - PAD_H // 2)
    player_score = 0
    cpu_score = 0
    state = STATE_INTRO
    _needs_full_draw = True
    _prev_ball_x = -1
    _prev_ball_y = -1
    _prev_player_y = -1
    _prev_cpu_y = -1
    gc.collect()


def _draw_court():
    """Draw the full court background."""
    global _back_btn

    display.fill(COURT_BG)

    # Center net (dashed)
    for y in range(4, HEIGHT - 4, 10):
        display.fill_rect(CX - 1, y, 2, 5, NET_COLOR)

    # Top and bottom borders
    display.hline(0, 0, WIDTH, rgb(0, 100, 30))
    display.hline(0, HEIGHT - 1, WIDTH, rgb(0, 100, 30))

    _back_btn = draw_back_button()


def _draw_scores():
    """Draw score display."""
    bitmap_font.draw_text(display, str(player_score), CX + 30, 8,
                          SCORE_COLOR, 2)
    bitmap_font.draw_text(display, str(cpu_score), CX - 40, 8,
                          SCORE_COLOR, 2)


def _move_paddle(x, old_y, new_y):
    """Move a paddle with minimal redraw (no flicker)."""
    oi = int(old_y)
    ni = int(new_y)
    ix = int(x)
    if oi == ni:
        return  # Didn't move — don't redraw
    # Draw paddle at new position first
    display.fill_rect(ix, ni, PAD_W, PAD_H, PAD_COLOR)
    # Erase only the strip no longer covered
    if ni > oi:
        # Moved down — erase top strip
        h = min(ni - oi, PAD_H)
        display.fill_rect(ix, oi, PAD_W, h, COURT_BG)
    else:
        # Moved up — erase bottom strip
        h = min(oi - ni, PAD_H)
        display.fill_rect(ix, ni + PAD_H, PAD_W, h, COURT_BG)


def _draw_paddle(x, y):
    """Draw a paddle at position."""
    display.fill_rect(int(x), int(y), PAD_W, PAD_H, PAD_COLOR)


def _update_ball():
    """Update ball position and handle collisions."""
    global ball_x, ball_y, ball_dx, ball_dy, ball_speed
    global player_score, cpu_score, state

    for _ in range(int(ball_speed)):
        ball_x += ball_dx
        ball_y += ball_dy

        # Bounce top/bottom
        if ball_y <= 2 or ball_y + BALL_SZ >= HEIGHT - 2:
            ball_dy = -ball_dy
            ball_y = max(2.0, min(float(HEIGHT - BALL_SZ - 2), ball_y))

        # Player paddle (right)
        if (ball_x + BALL_SZ >= player_x and
                ball_y + BALL_SZ >= player_y and
                ball_y <= player_y + PAD_H and
                ball_dx > 0):
            ball_dx = -abs(ball_dx)
            ball_speed = min(6.0, ball_speed + 0.2)

        # CPU paddle (left)
        if (ball_x <= cpu_x + PAD_W and
                ball_y + BALL_SZ >= cpu_y and
                ball_y <= cpu_y + PAD_H and
                ball_dx < 0):
            ball_dx = abs(ball_dx)
            ball_speed = min(6.0, ball_speed + 0.2)

    # Out of bounds
    if ball_x < -10:
        player_score += 1
        if player_score >= WIN_SCORE:
            state = STATE_OVER
        else:
            _reset_ball(1)
        return True

    if ball_x > WIDTH + 10:
        cpu_score += 1
        if cpu_score >= WIN_SCORE:
            state = STATE_OVER
        else:
            _reset_ball(-1)
        return True

    return False


def _update_cpu():
    """CPU AI tracks ball."""
    global cpu_y
    target = ball_y - PAD_H // 2
    diff = target - cpu_y
    cpu_y += max(-2.5, min(2.5, diff))
    cpu_y = max(2.0, min(float(HEIGHT - PAD_H - 2), cpu_y))


def update(touch_pos):
    """Update and render the tennis game."""
    global state, player_y, _back_btn, _touch_debounce
    global _needs_full_draw
    global _prev_ball_x, _prev_ball_y, _prev_player_y, _prev_cpu_y

    ticks = time.ticks_ms()

    # Full redraw
    if _needs_full_draw:
        _needs_full_draw = False
        _draw_court()
        _draw_scores()

        if state == STATE_INTRO:
            bitmap_font.draw_text(display, "TENNIS", CX - 42, CY - 20,
                                  BALL_COLOR, 2)
            display.text("Touch to start!", CX - 56, CY + 20, TEXT_DIM)

        elif state == STATE_PLAYING:
            # Draw sprites and record their positions
            display.fill_rect(int(ball_x), int(ball_y), BALL_SZ, BALL_SZ,
                              BALL_COLOR)
            _draw_paddle(player_x, player_y)
            _draw_paddle(cpu_x, cpu_y)
            _prev_ball_x = int(ball_x)
            _prev_ball_y = int(ball_y)
            _prev_player_y = int(player_y)
            _prev_cpu_y = int(cpu_y)

        if display._full_fb:
            display.show()
        return None

    # FB mode: full redraws
    if display._full_fb:
        _draw_court()
        _draw_scores()

    if state == STATE_INTRO:
        if touch_pos and time.ticks_diff(ticks, _touch_debounce) > 500:
            if check_back_button(touch_pos, _back_btn):
                return None
            state = STATE_PLAYING
            _reset_ball(-1)
            player_score = 0
            cpu_score = 0
            _touch_debounce = ticks
            _needs_full_draw = True
        return None

    elif state == STATE_PLAYING:
        # Player control
        if touch_pos:
            if check_back_button(touch_pos, _back_btn):
                return None
            tx, ty = touch_pos
            if tx > CX:
                player_y = float(ty - PAD_H // 2)
                player_y = max(2.0, min(float(HEIGHT - PAD_H - 2), player_y))

        # Update game
        score_changed = _update_ball()
        _update_cpu()

        if score_changed:
            _needs_full_draw = True
            return None

        new_bx = int(ball_x)
        new_by = int(ball_y)
        new_py = int(player_y)
        new_cy = int(cpu_y)

        if not display._full_fb:
            # Erase old ball
            if _prev_ball_x >= 0:
                display.fill_rect(_prev_ball_x, _prev_ball_y,
                                  BALL_SZ, BALL_SZ, COURT_BG)

            # Draw new ball
            display.fill_rect(new_bx, new_by, BALL_SZ, BALL_SZ, BALL_COLOR)

            # Move paddles with differential erase (no flicker)
            if _prev_player_y >= 0:
                _move_paddle(player_x, _prev_player_y, new_py)
            else:
                _draw_paddle(player_x, player_y)

            if _prev_cpu_y >= 0:
                _move_paddle(cpu_x, _prev_cpu_y, new_cy)
            else:
                _draw_paddle(cpu_x, cpu_y)
        else:
            display.fill_rect(new_bx, new_by, BALL_SZ, BALL_SZ, BALL_COLOR)
            _draw_paddle(player_x, player_y)
            _draw_paddle(cpu_x, cpu_y)
            display.show()

        # Save positions
        _prev_ball_x = new_bx
        _prev_ball_y = new_by
        _prev_player_y = new_py
        _prev_cpu_y = new_cy

    elif state == STATE_OVER:
        _draw_court()
        _draw_scores()

        bitmap_font.draw_text(display, "GAME OVER", CX - 60, CY - 30,
                              BALL_COLOR, 2)
        if player_score >= WIN_SCORE:
            bitmap_font.draw_text(display, "YOU WIN!", CX - 48, CY + 10,
                                  rgb(0, 255, 100))
        else:
            bitmap_font.draw_text(display, "CPU WINS", CX - 48, CY + 10,
                                  rgb(255, 80, 80))
        display.text("Touch to restart", CX - 56, CY + 40, TEXT_DIM)

        if display._full_fb:
            display.show()

        if touch_pos and time.ticks_diff(ticks, _touch_debounce) > 500:
            state = STATE_INTRO
            _touch_debounce = ticks
            _needs_full_draw = True

    return None
