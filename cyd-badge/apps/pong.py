"""
Pong - Classic arcade game for ESP32 CYD.

Neon arcade aesthetic with speed ramping, spin mechanics,
particle trails, and screen shake effects.
"""
import gc
import time
import random
from badge_os import (display, WIDTH, HEIGHT, rgb, BLACK, WHITE,
                      MID_GREY, draw_back_button,
                      check_back_button, request_menu)
from fonts import bitmap_font

# ─── Neon Arcade Colors ────────────────────────────────────────

COURT_BG = rgb(5, 5, 20)
NET_COLOR = rgb(30, 30, 80)
BORDER_CLR = rgb(60, 40, 180)
BALL_COLOR = rgb(255, 100, 50)
BALL_TRAIL = rgb(80, 30, 15)
PAD_PLAYER = rgb(50, 200, 255)
PAD_CPU = rgb(255, 80, 180)
SCORE_COLOR = rgb(255, 255, 100)
TEXT_HI = rgb(255, 220, 80)
TEXT_DIM = rgb(80, 80, 140)
FLASH_COLOR = rgb(255, 255, 255)
SPARK_COLORS = [rgb(255, 200, 50), rgb(255, 100, 50), rgb(50, 200, 255)]

CX = WIDTH // 2
CY = HEIGHT // 2
WIN_SCORE = 7

# ─── Game Objects ──────────────────────────────────────────────

STATE_INTRO = 0
STATE_PLAYING = 1
STATE_OVER = 2
STATE_COUNTDOWN = 3

# Ball
ball_x = 0.0
ball_y = 0.0
ball_dx = 0.0
ball_dy = 0.0
ball_speed = 3.5
BALL_SZ = 6

# Trail
_trail = []  # list of (x, y) last 4 positions
MAX_TRAIL = 4

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
_rally_count = 0

state = STATE_INTRO
_back_btn = None
_touch_debounce = 0
_needs_full_draw = True
_countdown_tick = 0

# Previous positions for flicker-free updates
_prev_ball_x = -1
_prev_ball_y = -1
_prev_player_y = -1
_prev_cpu_y = -1

# Sparks (paddle hit particles)
_sparks = []  # list of [x, y, dx, dy, life]

# Screen shake
_shake_frames = 0


def _reset_ball(direction):
    """Reset ball to center with random angle."""
    global ball_x, ball_y, ball_dx, ball_dy, ball_speed, _trail, _rally_count
    ball_x = float(CX)
    ball_y = float(CY)
    angle_var = (random.getrandbits(8) - 128) / 80.0
    ball_dx = 2.0 * direction
    ball_dy = angle_var + (0.8 if angle_var >= 0 else -0.8)
    ball_speed = 3.5
    _trail = []
    _rally_count = 0


def init():
    global player_y, cpu_y, player_score, cpu_score, state
    global _back_btn, _needs_full_draw, _sparks, _shake_frames
    global _prev_ball_x, _prev_ball_y, _prev_player_y, _prev_cpu_y

    _reset_ball(-1)
    player_y = float(CY - PAD_H // 2)
    cpu_y = float(CY - PAD_H // 2)
    player_score = 0
    cpu_score = 0
    state = STATE_INTRO
    _needs_full_draw = True
    _sparks = []
    _shake_frames = 0
    _prev_ball_x = -1
    _prev_ball_y = -1
    _prev_player_y = -1
    _prev_cpu_y = -1
    gc.collect()


def _draw_court():
    """Draw the full court background."""
    global _back_btn

    display.fill(COURT_BG)

    # Center net (dashed, neon)
    for y in range(4, HEIGHT - 4, 12):
        display.fill_rect(CX - 1, y, 2, 6, NET_COLOR)

    # Top and bottom borders (thick neon)
    display.fill_rect(0, 0, WIDTH, 2, BORDER_CLR)
    display.fill_rect(0, HEIGHT - 2, WIDTH, 2, BORDER_CLR)

    _back_btn = draw_back_button()


def _draw_scores():
    """Draw score display."""
    # Player score (right)
    bitmap_font.draw_text(display, str(player_score), CX + 30, 8,
                          PAD_PLAYER, 2)
    # CPU score (left)
    bitmap_font.draw_text(display, str(cpu_score), CX - 40, 8,
                          PAD_CPU, 2)


def _move_paddle(x, old_y, new_y, color):
    """Move a paddle with minimal redraw."""
    oi = int(old_y)
    ni = int(new_y)
    ix = int(x)
    if oi == ni:
        return
    display.fill_rect(ix, ni, PAD_W, PAD_H, color)
    if ni > oi:
        h = min(ni - oi, PAD_H)
        display.fill_rect(ix, oi, PAD_W, h, COURT_BG)
    else:
        h = min(oi - ni, PAD_H)
        display.fill_rect(ix, ni + PAD_H, PAD_W, h, COURT_BG)


def _draw_paddle(x, y, color):
    """Draw a paddle at position."""
    display.fill_rect(int(x), int(y), PAD_W, PAD_H, color)


def _spawn_sparks(x, y):
    """Spawn hit sparks at paddle collision point."""
    global _sparks
    for _ in range(4):
        dx = (random.getrandbits(8) - 128) / 40.0
        dy = (random.getrandbits(8) - 128) / 40.0
        _sparks.append([int(x), int(y), dx, dy, 6])


def _update_sparks():
    """Update and draw spark particles."""
    global _sparks
    alive = []
    for s in _sparks:
        # Erase old
        display.pixel(int(s[0]), int(s[1]), COURT_BG)
        s[0] += s[2]
        s[1] += s[3]
        s[4] -= 1
        if s[4] > 0 and 0 < s[0] < WIDTH and 0 < s[1] < HEIGHT:
            c = SPARK_COLORS[s[4] % 3]
            display.pixel(int(s[0]), int(s[1]), c)
            alive.append(s)
    _sparks = alive


def _update_ball():
    """Update ball position and handle collisions."""
    global ball_x, ball_y, ball_dx, ball_dy, ball_speed
    global player_score, cpu_score, state, _rally_count, _shake_frames

    for _ in range(int(ball_speed)):
        ball_x += ball_dx
        ball_y += ball_dy

        # Bounce top/bottom
        if ball_y <= 3 or ball_y + BALL_SZ >= HEIGHT - 3:
            ball_dy = -ball_dy
            ball_y = max(3.0, min(float(HEIGHT - BALL_SZ - 3), ball_y))

        # Player paddle (right)
        if (ball_x + BALL_SZ >= player_x and
                ball_y + BALL_SZ >= player_y and
                ball_y <= player_y + PAD_H and
                ball_dx > 0):
            ball_dx = -abs(ball_dx)
            # Spin: hit position on paddle affects angle
            hit_pos = (ball_y + BALL_SZ / 2 - player_y) / PAD_H
            ball_dy += (hit_pos - 0.5) * 2.0
            ball_dy = max(-3.0, min(3.0, ball_dy))
            ball_speed = min(7.0, ball_speed + 0.25)
            _rally_count += 1
            _spawn_sparks(player_x, ball_y + BALL_SZ // 2)
            _shake_frames = 3

        # CPU paddle (left)
        if (ball_x <= cpu_x + PAD_W and
                ball_y + BALL_SZ >= cpu_y and
                ball_y <= cpu_y + PAD_H and
                ball_dx < 0):
            ball_dx = abs(ball_dx)
            hit_pos = (ball_y + BALL_SZ / 2 - cpu_y) / PAD_H
            ball_dy += (hit_pos - 0.5) * 1.5
            ball_dy = max(-3.0, min(3.0, ball_dy))
            ball_speed = min(7.0, ball_speed + 0.25)
            _rally_count += 1
            _spawn_sparks(cpu_x + PAD_W, ball_y + BALL_SZ // 2)
            _shake_frames = 3

    # Out of bounds
    if ball_x < -10:
        player_score += 1
        _shake_frames = 6
        if player_score >= WIN_SCORE:
            state = STATE_OVER
        else:
            _reset_ball(1)
        return True

    if ball_x > WIDTH + 10:
        cpu_score += 1
        _shake_frames = 6
        if cpu_score >= WIN_SCORE:
            state = STATE_OVER
        else:
            _reset_ball(-1)
        return True

    return False


def _update_cpu():
    """CPU AI — gets smarter as rally grows."""
    global cpu_y
    # CPU speed scales with rally count
    spd = min(3.5, 2.0 + _rally_count * 0.1)
    target = ball_y - PAD_H // 2
    # Add slight prediction error
    if _rally_count < 3:
        target += (random.getrandbits(4) - 8)
    diff = target - cpu_y
    cpu_y += max(-spd, min(spd, diff))
    cpu_y = max(3.0, min(float(HEIGHT - PAD_H - 3), cpu_y))


def update(touch_pos):
    global state, player_y, _back_btn, _touch_debounce
    global _needs_full_draw, _countdown_tick, _shake_frames
    global _prev_ball_x, _prev_ball_y, _prev_player_y, _prev_cpu_y
    global player_score, cpu_score, _trail

    ticks = time.ticks_ms()

    # Full redraw
    if _needs_full_draw:
        _needs_full_draw = False
        _draw_court()
        _draw_scores()

        if state == STATE_INTRO:
            # Title screen
            bitmap_font.draw_text(display, "PONG", CX - 46, CY - 30,
                                  BALL_COLOR, 3)
            # Center hints
            hw = bitmap_font.measure_text("Touch to play!", 1)
            bitmap_font.draw_text(display, "Touch to play!", CX - hw // 2,
                                  CY + 25, TEXT_HI, 1)
            h2 = len("Touch right side") * 8
            display.text("Touch right side", CX - h2 // 2, CY + 45, TEXT_DIM)
            h3 = len("to move paddle") * 8
            display.text("to move paddle", CX - h3 // 2, CY + 58, TEXT_DIM)

        elif state == STATE_PLAYING:
            display.fill_rect(int(ball_x), int(ball_y), BALL_SZ, BALL_SZ,
                              BALL_COLOR)
            _draw_paddle(player_x, player_y, PAD_PLAYER)
            _draw_paddle(cpu_x, cpu_y, PAD_CPU)
            _prev_ball_x = int(ball_x)
            _prev_ball_y = int(ball_y)
            _prev_player_y = int(player_y)
            _prev_cpu_y = int(cpu_y)
        elif state == STATE_OVER:
            gow = bitmap_font.measure_text("GAME OVER", 2)
            bitmap_font.draw_text(display, "GAME OVER", CX - gow // 2,
                                  CY - 30, BALL_COLOR, 2)
            if player_score >= WIN_SCORE:
                ww = bitmap_font.measure_text("YOU WIN!", 2)
                bitmap_font.draw_text(display, "YOU WIN!", CX - ww // 2,
                                      CY + 10, PAD_PLAYER, 2)
            else:
                cw = bitmap_font.measure_text("CPU WINS", 2)
                bitmap_font.draw_text(display, "CPU WINS", CX - cw // 2,
                                      CY + 10, PAD_CPU, 2)
            rw = len("Touch to restart") * 8
            display.text("Touch to restart", CX - rw // 2, CY + 45, TEXT_DIM)

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
                player_y = max(3.0, min(float(HEIGHT - PAD_H - 3), player_y))

        # Update game
        score_changed = _update_ball()
        _update_cpu()
        _update_sparks()

        if score_changed:
            _needs_full_draw = True
            return None

        # Trail management
        _trail.append((int(ball_x), int(ball_y)))
        if len(_trail) > MAX_TRAIL:
            old = _trail.pop(0)
            display.fill_rect(old[0], old[1], BALL_SZ, BALL_SZ, COURT_BG)

        new_bx = int(ball_x)
        new_by = int(ball_y)
        new_py = int(player_y)
        new_cy = int(cpu_y)

        if not display._full_fb:
            # Erase old ball
            if _prev_ball_x >= 0:
                display.fill_rect(_prev_ball_x, _prev_ball_y,
                                  BALL_SZ, BALL_SZ, COURT_BG)

            # Draw trail
            for i, (tx, ty) in enumerate(_trail[:-1]):
                display.fill_rect(tx, ty, BALL_SZ, BALL_SZ, BALL_TRAIL)

            # Draw new ball
            display.fill_rect(new_bx, new_by, BALL_SZ, BALL_SZ, BALL_COLOR)

            # Move paddles
            if _prev_player_y >= 0:
                _move_paddle(player_x, _prev_player_y, new_py, PAD_PLAYER)
            else:
                _draw_paddle(player_x, player_y, PAD_PLAYER)

            if _prev_cpu_y >= 0:
                _move_paddle(cpu_x, _prev_cpu_y, new_cy, PAD_CPU)
            else:
                _draw_paddle(cpu_x, cpu_y, PAD_CPU)

            # Screen shake removed

            # Rally counter (top center)
            if _rally_count > 3:
                display.text(str(_rally_count), CX - 4, 5, TEXT_DIM)

        else:
            display.fill_rect(new_bx, new_by, BALL_SZ, BALL_SZ, BALL_COLOR)
            _draw_paddle(player_x, player_y, PAD_PLAYER)
            _draw_paddle(cpu_x, cpu_y, PAD_CPU)
            display.show()

        # Save positions
        _prev_ball_x = new_bx
        _prev_ball_y = new_by
        _prev_player_y = new_py
        _prev_cpu_y = new_cy

    elif state == STATE_OVER:
        if touch_pos and time.ticks_diff(ticks, _touch_debounce) > 800:
            _touch_debounce = ticks
            init()

    return None
