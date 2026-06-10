"""
ai_helpers.py
─────────────────────────────────────────────────────────────
Converts the live game state into the observation vector that
the AI model expects.

Expanded from 22 → 32 floats to give the AI:
  • Wall-proximity signals so it stops walking into corners
  • Nearest incoming bullet threat so it can dodge
  • Explicit pickup distance (not just direction)
  • Cleaner normalisation on every value

This file is imported by BOTH:
  • game_env.py  (used during training)
  • game_with_ai.py  (used when you actually play against the AI)

IMPORTANT: if you change this file you must retrain from scratch —
the observation size/format must be identical at train and play time.
"""

import math
import numpy as np

# Must match game.py
WIDTH  = 1920
HEIGHT = 1080
DIAG   = math.hypot(WIDTH, HEIGHT)   # ≈ 2202

# How close to a wall before the signal activates (pixels)
WALL_SENSE_DIST = 200.0

OBS_SIZE = 32   # total floats in the observation vector


def get_observation(p1, p2, arena, bullets=None):
    """
    Build a 32-float observation vector for the AI (Player 2).

    All values are normalised to [-1, 1].

    Parameters
    ----------
    p1      : Player
    p2      : Player  (the AI)
    arena   : Arena
    bullets : list of Bullet

    Returns
    -------
    np.ndarray shape (32,) dtype float32, clipped to [-1, 1]
    """
    if bullets is None:
        bullets = []

    # ── Opponent relative info ──────────────────────────────────
    dx_to_p1   = p1.x - p2.x
    dy_to_p1   = p1.y - p2.y
    dist_to_p1 = math.hypot(dx_to_p1, dy_to_p1) or 1.0
    norm_dx    = dx_to_p1 / dist_to_p1   # unit vector
    norm_dy    = dy_to_p1 / dist_to_p1

    # ── Wall proximity (0 = touching wall, 1 = far away) ────────
    wall_left   = min(p2.x,            WALL_SENSE_DIST) / WALL_SENSE_DIST
    wall_right  = min(WIDTH  - p2.x,   WALL_SENSE_DIST) / WALL_SENSE_DIST
    wall_top    = min(p2.y,            WALL_SENSE_DIST) / WALL_SENSE_DIST
    wall_bottom = min(HEIGHT - p2.y,   WALL_SENSE_DIST) / WALL_SENSE_DIST
    # map to [-1, 1]: -1 = right against wall, +1 = far from it
    wall_left   = wall_left   * 2 - 1
    wall_right  = wall_right  * 2 - 1
    wall_top    = wall_top    * 2 - 1
    wall_bottom = wall_bottom * 2 - 1

    # ── Nearest weapon pickup ───────────────────────────────────
    if arena.weapon_pickups:
        nearest = min(arena.weapon_pickups,
                      key=lambda w: math.hypot(w.x - p2.x, w.y - p2.y))
        pu_dx   = (nearest.x - p2.x) / WIDTH        # already in ~[-1,1]
        pu_dy   = (nearest.y - p2.y) / HEIGHT
        pu_dist = math.hypot(nearest.x - p2.x,
                             nearest.y - p2.y) / DIAG * 2 - 1  # [-1,1]
        has_pickup = 1.0
    else:
        pu_dx, pu_dy, pu_dist = 0.0, 0.0, 1.0
        has_pickup = -1.0

    # ── Nearest incoming bullet threat ──────────────────────────
    # Only bullets fired by P1 (i.e. heading toward P2) matter.
    enemy_bullets = [b for b in bullets if b.owner is not p2]
    if enemy_bullets:
        # pick the bullet whose current position is closest to P2
        nb = min(enemy_bullets,
                 key=lambda b: math.hypot(b.x - p2.x, b.y - p2.y))
        nb_dist = math.hypot(nb.x - p2.x, nb.y - p2.y)
        bul_dx  = (nb.x - p2.x) / WIDTH
        bul_dy  = (nb.y - p2.y) / HEIGHT
        bul_threat = 1.0 - min(nb_dist / DIAG, 1.0)   # 1 = very close
        bul_threat = bul_threat * 2 - 1                # → [-1, 1]
    else:
        bul_dx, bul_dy, bul_threat = 0.0, 0.0, -1.0

    # ── Assemble ────────────────────────────────────────────────
    obs = np.array([
        # ── Own position (2) ──
        p2.x / WIDTH  * 2 - 1,               #  0  P2 x
        p2.y / HEIGHT * 2 - 1,               #  1  P2 y

        # ── Opponent position (2) ──
        p1.x / WIDTH  * 2 - 1,               #  2  P1 x
        p1.y / HEIGHT * 2 - 1,               #  3  P1 y

        # ── Health & stamina (3) ──
        p2.health  / 100.0 * 2 - 1,          #  4  P2 HP
        p1.health  / 100.0 * 2 - 1,          #  5  P1 HP
        p2.stamina / 100.0 * 2 - 1,          #  6  P2 stamina

        # ── Direction & distance to opponent (3) ──
        float(norm_dx),                       #  7  unit Δx to P1
        float(norm_dy),                       #  8  unit Δy to P1
        min(dist_to_p1 / DIAG, 1.0) * 2 - 1, #  9  distance

        # ── Own facing direction (2) ──
        float(p2.facing_dx),                  # 10
        float(p2.facing_dy),                  # 11

        # ── Weapon state (2) ──
        1.0 if p2.weapon.projectile else -1.0,         # 12  has ranged weapon
        (p2.ammo / 16.0) if p2.ammo >= 0 else 1.0,    # 13  ammo ratio

        # ── Cooldown timers (3) ──
        p2.cooldown_timer        / 90.0 * 2 - 1,  # 14  dash cd
        p2.attack_cooldown_timer / 38.0 * 2 - 1,  # 15  melee cd
        p2.shoot_cooldown_timer  / 28.0 * 2 - 1,  # 16  shoot cd

        # ── State flags (3) ──
        1.0 if p2.dash_timer   > 0 else -1.0,     # 17  P2 dashing
        1.0 if p1.attack_timer > 0 else -1.0,     # 18  P1 attacking
        1.0 if p1.dash_timer   > 0 else -1.0,     # 19  P1 dashing

        # ── Wall proximity (4)  NEW ──
        float(wall_left),                          # 20  distance from left wall
        float(wall_right),                         # 21  distance from right wall
        float(wall_top),                           # 22  distance from top wall
        float(wall_bottom),                        # 23  distance from bottom wall

        # ── Nearest weapon pickup (4)  IMPROVED ──
        float(has_pickup),                         # 24  any pickup exists
        float(pu_dx),                              # 25  pickup Δx
        float(pu_dy),                              # 26  pickup Δy
        float(pu_dist),                            # 27  pickup distance

        # ── Nearest enemy bullet (4)  NEW ──
        float(bul_dx),                             # 28  bullet Δx
        float(bul_dy),                             # 29  bullet Δy
        float(bul_threat),                         # 30  bullet proximity threat
        1.0 if p1.weapon.projectile else -1.0,     # 31  P1 has ranged weapon
    ], dtype=np.float32)

    return np.clip(obs, -1.0, 1.0)