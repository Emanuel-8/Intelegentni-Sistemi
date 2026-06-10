"""
ai_helpers.py
─────────────────────────────────────────────────────────────
Converts the live game state into the 22-value observation
vector that the AI model expects.

This file is imported by BOTH:
  • game_env.py  (used during training)
  • game_with_ai.py  (used when you actually play against the AI)

Keeping it in one place means the AI always sees the game
state in exactly the same format it was trained on.
"""

import math
import numpy as np

# Must match game.py
WIDTH  = 1920
HEIGHT = 1080
DIAG   = math.hypot(WIDTH, HEIGHT)   # max possible distance ≈ 2202


def get_observation(p1, p2, arena, bullets=None):
    """
    Build a 22-float observation vector for the AI (Player 2).

    All values are normalised to the range [-1, 1] so the neural
    network can process them efficiently.

    Parameters
    ----------
    p1      : Player  – the human opponent
    p2      : Player  – the AI being controlled
    arena   : Arena   – current arena (for weapon pickups)
    bullets : list    – active Bullet objects (optional)

    Returns
    -------
    np.ndarray of shape (22,), dtype float32, values in [-1, 1]
    """
    if bullets is None:
        bullets = []

    # ── Direction / distance from P2 → P1 ──────────────────────
    dx_to_p1   = p1.x - p2.x
    dy_to_p1   = p1.y - p2.y
    dist_to_p1 = math.hypot(dx_to_p1, dy_to_p1)

    # ── Nearest weapon pickup ───────────────────────────────────
    if arena.weapon_pickups:
        nearest  = min(arena.weapon_pickups,
                       key=lambda w: math.hypot(w.x - p2.x, w.y - p2.y))
        pu_dx    = (nearest.x - p2.x) / WIDTH
        pu_dy    = (nearest.y - p2.y) / HEIGHT
        pu_dist  = math.hypot(nearest.x - p2.x, nearest.y - p2.y) / DIAG
    else:
        pu_dx, pu_dy, pu_dist = 0.0, 0.0, 1.0

    # ── Assemble the vector ─────────────────────────────────────
    # Each comment shows what the value represents and its raw range
    obs = np.array([
        # ── Positions ──
        p2.x / WIDTH  * 2 - 1,          #  0  P2 x            [0,W]  → [-1,1]
        p2.y / HEIGHT * 2 - 1,          #  1  P2 y            [0,H]  → [-1,1]
        p1.x / WIDTH  * 2 - 1,          #  2  P1 x
        p1.y / HEIGHT * 2 - 1,          #  3  P1 y

        # ── Health & stamina ──
        p2.health  / 100.0 * 2 - 1,     #  4  P2 health       [0,100]→[-1,1]
        p1.health  / 100.0 * 2 - 1,     #  5  P1 health
        p2.stamina / 100.0 * 2 - 1,     #  6  P2 stamina

        # ── Relative position to opponent ──
        dx_to_p1 / WIDTH,               #  7  Δx toward P1    [-1,1]
        dy_to_p1 / HEIGHT,              #  8  Δy toward P1    [-1,1]
        min(dist_to_p1 / DIAG, 1.0) * 2 - 1,  # 9  distance  [-1,1]

        # ── P2 facing direction ──
        float(p2.facing_dx),            # 10  facing x        [-1,1]
        float(p2.facing_dy),            # 11  facing y        [-1,1]

        # ── P2 weapon state ──
        1.0 if p2.weapon.projectile else -1.0,          # 12  has ranged weapon
        (p2.ammo / 16.0) if p2.ammo >= 0 else 1.0,     # 13  ammo (0-1)

        # ── Cooldown timers ──
        p2.cooldown_timer        / 90.0 * 2 - 1,  # 14  dash cooldown
        p2.attack_cooldown_timer / 38.0 * 2 - 1,  # 15  melee cooldown
        p2.shoot_cooldown_timer  / 28.0 * 2 - 1,  # 16  shoot cooldown

        # ── State flags ──
        1.0 if p2.dash_timer   > 0 else -1.0,     # 17  P2 is dashing
        1.0 if p1.attack_timer > 0 else -1.0,     # 18  P1 is attacking
        1.0 if p1.dash_timer   > 0 else -1.0,     # 19  P1 is dashing

        # ── Nearest weapon pickup ──
        float(pu_dx),                              # 20  pickup Δx
        float(pu_dy),                              # 21  pickup Δy
    ], dtype=np.float32)

    # Safety clamp — should already be in range but just in case
    return np.clip(obs, -1.0, 1.0)
