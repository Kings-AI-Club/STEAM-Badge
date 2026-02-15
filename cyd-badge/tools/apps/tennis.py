"""
Tennis - Pong game for ESP32 CYD.

Classic Pong game adapted for touchscreen: touch the right side
of the screen to move your paddle up/down. Play against a CPU
opponent. First to 6 wins!

Adapted from the Tufty 2350 Badgerware tennis app.
"""
import gc
import time
import math
import random
from badge_os import (display, WIDTH, HEIGHT, rgb, BLACK, WHITE,
                      DARK_BG, MID_GREY, draw_back_button,
                      check_back_button, request_menu)
from fonts import bitmap_font

# ─── Constants ──────────────────────────────────────────────────

CX = WIDTH // 2
CY = HEIGHT // 2
COURT_COLOR = rgb(20, 20, 20)
LINE_COLOR = rgb(60, 60, 60)
PADDLE_COLOR = WHITE
BALL_COLOR = WHITE
SCORE_COLOR = WHITE
WIN_SCORE = 6

# ─── Game State ─────────────────────────────────────────────────

class GameState:
    INTRO = 0
    PLAYING = 1
    GAME_OVER = 2


# ─── Game Objects ───────────────────────────────────────────────

# Ball
ball_x = CX
ball_y = CY
ball_dx = 1.5
ball_dy = 0.5
ball_speed = 2
ball_size = 6

# Paddles
PADDLE_W = 8
PADDLE_H = 45
player_y = CY - PADDLE_H // 2
player_x = WIDTH - PADDLE_W - 6
cpu_y = CY - PADDLE_H // 2
cpu_x = 6

# Scores
player_score = 0
cpu_score = 0

# State
state = GameState.INTRO
_back_btn = None
_touch_debounce = 0


def init():
    """Initialize the tennis game."""
    global ball_x, ball_y, ball_dx, ball_dy, ball_speed
    global player_y, cpu_y, player_score, cpu_score, state, _back_btn

    ball_x = CX
    ball_y = CY
    ball_dx = 1.5
    ball_dy = 0.5
    ball_speed = 2
    player_y = CY - PADDLE_H // 2
    cpu_y = CY - PADDLE_H // 2
    player_score = 0
    cpu_score = 0
    state = GameState.INTRO
    _back_btn = draw_back_button()
    gc.collect()


def _reset_ball(direction):
    """Reset ball to center with given direction."""
    global ball_x, ball_y, ball_dx, ball_dy, ball_speed
    ball_x = CX
    ball_y = CY
    ball_dx = 1.5 * direction
    ball_dy = random.uniform(-0.5, 0.5)
    ball_speed = 2


def _normalise(x, y):
    """Normalize a 2D vector."""
    dist = math.sqrt(x * x + y * y)
    if dist == 0:
        return 0, 0
    return x / dist, y / dist


def _update_ball():
    """Update ball position and handle collisions."""
    global ball_x, ball_y, ball_dx, ball_dy, ball_speed
    global player_score, cpu_score, state

    for _ in range(int(ball_speed)):
        ball_x += ball_dx
        ball_y += ball_dy

        # Bounce off top/bottom
        if ball_y <= 2 or ball_y + ball_size >= HEIGHT - 2:
            ball_dy = -ball_dy
            ball_y = max(2, min(HEIGHT - ball_size - 2, ball_y))

        # Check paddle collisions
        # Player paddle (right side)
        if (ball_x + ball_size >= player_x and
                ball_y + ball_size >= player_y and
                ball_y <= player_y + PADDLE_H and
                ball_dx > 0):
            bat_center = player_y + PADDLE_H / 2
            y_diff = (ball_y + ball_size / 2) - bat_center
            ball_dx = -abs(ball_dx)
            ball_dy += y_diff / 40
            ball_dy = max(-1.2, min(1.2, ball_dy))
            ball_dx, ball_dy = _normalise(ball_dx, ball_dy)
            ball_dx = -abs(ball_dx)  # ensure going left
            ball_speed = min(5, ball_speed + 0.15)

        # CPU paddle (left side)
        if (ball_x <= cpu_x + PADDLE_W and
                ball_y + ball_size >= cpu_y and
                ball_y <= cpu_y + PADDLE_H and
                ball_dx < 0):
            bat_center = cpu_y + PADDLE_H / 2
            y_diff = (ball_y + ball_size / 2) - bat_center
            ball_dx = abs(ball_dx)
            ball_dy += y_diff / 40
            ball_dy = max(-1.2, min(1.2, ball_dy))
            ball_dx, ball_dy = _normalise(ball_dx, ball_dy)
            ball_dx = abs(ball_dx)  # ensure going right
            ball_speed = min(5, ball_speed + 0.15)

    # Check if ball is out
    if ball_x < -10:
        player_score += 1
        if player_score >= WIN_SCORE:
            state = GameState.GAME_OVER
        else:
            _reset_ball(1)

    elif ball_x > WIDTH + 10:
        cpu_score += 1
        if cpu_score >= WIN_SCORE:
            state = GameState.GAME_OVER
        else:
            _reset_ball(-1)


def _update_cpu():
    """Update CPU paddle AI."""
    global cpu_y

    # Weighted movement: track ball when close, drift to center when far
    x_dist = abs(ball_x - cpu_x)
    center_target = CY - PADDLE_H // 2
    ball_target = ball_y - PADDLE_H // 2 + random.randint(-5, 5)

    weight = min(1.0, x_dist / CX)
    target_y = weight * center_target + (1.0 - weight) * ball_target

    # Smooth movement with speed limit
    diff = target_y - cpu_y
    movement = max(-4, min(4, diff))
    cpu_y += movement

    # Clamp
    cpu_y = max(0, min(HEIGHT - PADDLE_H, cpu_y))


def _update_player_auto():
    """Auto-play the player paddle (for intro demo)."""
    global player_y

    target = ball_y - PADDLE_H // 2 + random.randint(-8, 8)
    diff = target - player_y
    movement = max(-3, min(3, diff))
    player_y += movement
    player_y = max(0, min(HEIGHT - PADDLE_H, player_y))


def _draw_court():
    """Draw the court markings."""
    # Background
    display.fill(COURT_COLOR)

    # Center line (dashed)
    for y in range(0, HEIGHT, 12):
        display.fill_rect(CX - 1, y, 3, 6, LINE_COLOR)

    # Top and bottom borders
    display.fill_rect(0, 0, WIDTH, 2, LINE_COLOR)
    display.fill_rect(0, HEIGHT - 2, WIDTH, 2, LINE_COLOR)


def _draw_scores():
    """Draw score display."""
    # Player score (right)
    p_str = str(player_score)
    bitmap_font.draw_text(display, p_str, CX + 30, 8, SCORE_COLOR, 2)

    # CPU score (left)
    c_str = str(cpu_score)
    bitmap_font.draw_text(display, c_str, CX - 40, 8, SCORE_COLOR, 2)


def _draw_ball():
    """Draw the ball."""
    display.fill_rect(int(ball_x), int(ball_y), ball_size, ball_size,
                      BALL_COLOR)


def _draw_paddles():
    """Draw both paddles."""
    display.fill_rect(int(player_x), int(player_y), PADDLE_W, PADDLE_H,
                      PADDLE_COLOR)
    display.fill_rect(int(cpu_x), int(cpu_y), PADDLE_W, PADDLE_H,
                      PADDLE_COLOR)


def update(touch_pos):
    """Update and render the tennis game."""
    global state, player_y, player_score, cpu_score, _back_btn
    global _touch_debounce

    ticks = time.ticks_ms()

    # Draw court
    _draw_court()
    _draw_scores()

    # Back button
    _back_btn = draw_back_button()

    if state == GameState.INTRO:
        # ─── INTRO: Auto-play demo ─────────
        _update_ball()
        _update_cpu()
        _update_player_auto()
        _draw_ball()
        _draw_paddles()

        # Title
        bitmap_font.draw_text(display, "TENNIS", CX - 42, CY - 30,
                              WHITE, 2)

        # Blinking prompt
        if (ticks // 500) % 2:
            display.text("Touch to start!", CX - 56, CY + 20, WHITE)

        # Touch to start
        if touch_pos:
            if check_back_button(touch_pos, _back_btn):
                return None
            if time.ticks_diff(ticks, _touch_debounce) > 500:
                state = GameState.PLAYING
                _reset_ball(-1)
                player_score = 0
                cpu_score = 0
                _touch_debounce = ticks

    elif state == GameState.PLAYING:
        # ─── PLAYING ─────────

        # Player control via touch
        if touch_pos:
            tx, ty = touch_pos
            if check_back_button(touch_pos, _back_btn):
                return None
            # Touch anywhere on right half to control paddle
            if tx > CX:
                # Map touch Y to paddle position
                player_y = ty - PADDLE_H // 2
                player_y = max(0, min(HEIGHT - PADDLE_H, player_y))
        else:
            # Touch zones at top/bottom for paddle control
            pass

        _update_ball()
        _update_cpu()
        _draw_ball()
        _draw_paddles()

        # Touch hint
        display.text("Touch right side", WIDTH - 130, HEIGHT - 14,
                     rgb(60, 60, 60))

    elif state == GameState.GAME_OVER:
        # ─── GAME OVER ─────────
        _draw_ball()
        _draw_paddles()

        bitmap_font.draw_text(display, "GAME OVER", CX - 60, CY - 40,
                              WHITE, 2)

        if player_score >= WIN_SCORE:
            bitmap_font.draw_text(display, "YOU WIN!", CX - 48, CY + 10,
                                  rgb(0, 255, 100))
        else:
            bitmap_font.draw_text(display, "CPU WINS", CX - 48, CY + 10,
                                  rgb(255, 80, 80))

        if (ticks // 500) % 2:
            display.text("Touch for menu", CX - 52, CY + 50, WHITE)

        if touch_pos:
            if time.ticks_diff(ticks, _touch_debounce) > 500:
                if check_back_button(touch_pos, _back_btn):
                    return None
                # Reset to intro
                state = GameState.INTRO
                player_score = 0
                cpu_score = 0
                _reset_ball(1)
                _touch_debounce = ticks

    return None
