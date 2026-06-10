"""
game_env.py
─────────────────────────────────────────────────────────────
A Gymnasium environment that wraps your game's logic so that
a Reinforcement Learning algorithm can train in it.

Key improvements over the original
────────────────────────────────────
• Observation expanded to 32 floats (wall proximity, bullet
  threat, pickup distance — see ai_helpers.py)
• Reward function completely redesigned:
    - Picking up a weapon gives a real bonus
    - Using a ranged weapon correctly is rewarded
    - Camping near walls is penalised
    - Passive running is penalised (no damage dealt timer)
    - Win/loss values are balanced so the AI prefers fighting
      to dying slowly
• P1 training bot has THREE difficulty modes that rotate
  each episode so the AI learns to handle different styles:
    - Rusher  : charges straight and swings
    - Kiter   : stays at medium range and shoots
    - Dodger  : strafes around P2 and attacks from angles
"""

import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import sys, math, random

import pygame
pygame.init()
pygame.display.set_mode((1, 1))

import numpy as np
import gymnasium as gym
from gymnasium import spaces

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game import (
    Player, Arena, resolve_player_collision, WIDTH, HEIGHT
)
from ai_helpers import get_observation, OBS_SIZE

MOVEMENT_DIRS = [
    ( 0,  0),   # 0  stand
    ( 0, -1),   # 1  up
    ( 0,  1),   # 2  down
    (-1,  0),   # 3  left
    ( 1,  0),   # 4  right
    (-1, -1),   # 5  up-left
    ( 1, -1),   # 6  up-right
    (-1,  1),   # 7  down-left
    ( 1,  1),   # 8  down-right
]

# How many frames without dealing damage before the AI is
# penalised for passivity
PASSIVITY_TIMEOUT = 180   # 3 seconds at 60 fps


class ArenaFightEnv(gym.Env):
    """
    Observation space : 32 floats in [-1, 1]
    Action space      : MultiDiscrete [9, 2, 2, 2, 2]
      [0] movement direction  0-8
      [1] sprint              0/1
      [2] dash                0/1
      [3] melee attack        0/1
      [4] shoot               0/1
    """

    metadata = {"render_modes": []}

    def __init__(self):
        super().__init__()

        self.action_space      = spaces.MultiDiscrete([9, 2, 2, 2, 2])
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(OBS_SIZE,), dtype=np.float32
        )

        self.p1 = self.p2 = self.arena = None
        self.bullets: list = []
        self._prev_p1_hp     = 100.0
        self._prev_p2_hp     = 100.0
        self._prev_dist      = 0.0
        self._prev_p2_weapon = False   # had ranged weapon last frame
        self._frames_since_damage = 0  # passivity counter
        self._p1_bot_mode    = 0       # 0=rusher 1=kiter 2=dodger
        self._p1_strafe_sign = 1       # used by dodger bot
        self.current_step    = 0
        self.MAX_STEPS       = 3600

    # ────────────────────────────────────────────────────────────
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

        self.p1 = Player(0, 0, (100, 180, 240), (80,  160, 255))
        self.p2 = Player(0, 0, (240, 140, 100), (255, 120,  60))

        self.arena   = Arena(self.p1, self.p2, random.randint(0, 3))
        self.bullets = []

        self._prev_p1_hp  = float(self.p1.health)
        self._prev_p2_hp  = float(self.p2.health)
        self._prev_dist   = math.hypot(self.p2.x - self.p1.x,
                                       self.p2.y - self.p1.y)
        self._prev_p2_weapon      = self.p2.weapon.projectile
        self._frames_since_damage = 0
        self._p1_bot_mode         = random.randint(0, 2)
        self._p1_strafe_sign      = random.choice([-1, 1])
        self.current_step         = 0

        obs = get_observation(self.p1, self.p2, self.arena, self.bullets)
        return obs, {}

    # ────────────────────────────────────────────────────────────
    def step(self, action):
        move_idx, sprint, dash, melee, shoot = action
        dx2, dy2 = MOVEMENT_DIRS[int(move_idx)]

        # ── AI (P2) actions ────────────────────────────────────
        if dash:
            self.p2.start_dash(dx2, dy2)
        if melee:
            self.p2.start_attack(dx2, dy2)
        if shoot:
            b = self.p2.start_shoot()
            if b:
                self.bullets.append(b)
        self.p2.move(dx2, dy2, bool(sprint), self.arena)

        # ── Rule-based P1 bot ──────────────────────────────────
        self._run_p1_bot()

        # ── Physics ────────────────────────────────────────────
        self.p1.update()
        self.p2.update()
        self.arena.resolve_obstacle_collision(self.p1)
        self.arena.resolve_obstacle_collision(self.p2)
        resolve_player_collision(self.p1, self.p2)
        self._process_melee()
        self._process_pickups()
        self._process_bullets()
        self.arena.update()

        # ── Reward ─────────────────────────────────────────────
        reward = self._compute_reward()
        self._prev_p1_hp     = float(self.p1.health)
        self._prev_p2_hp     = float(self.p2.health)
        self._prev_p2_weapon = self.p2.weapon.projectile

        self.current_step += 1
        terminated = self.p1.is_dead() or self.p2.is_dead()
        truncated  = self.current_step >= self.MAX_STEPS

        obs  = get_observation(self.p1, self.p2, self.arena, self.bullets)
        info = {
            "p1_health": self.p1.health,
            "p2_health": self.p2.health,
            "winner": ("p2" if self.p1.is_dead()
                       else "p1" if self.p2.is_dead()
                       else None),
        }
        return obs, reward, terminated, truncated, info

    # ────────────────────────────────────────────────────────────
    #  P1 training bot  — three styles so the AI generalises
    # ────────────────────────────────────────────────────────────
    def _run_p1_bot(self):
        p1, p2 = self.p1, self.p2
        dx   = p2.x - p1.x
        dy   = p2.y - p1.y
        dist = math.hypot(dx, dy) or 1.0
        ndx, ndy = dx / dist, dy / dist

        mode = self._p1_bot_mode

        if mode == 0:
            # ── Rusher: sprint straight in and swing ──────────
            p1.move(ndx, ndy, True, self.arena)
            if dist < p1.attack_range + p2.radius + 25:
                p1.start_attack(ndx, ndy)
            if dist > 200 and random.random() < 0.02:
                p1.start_dash(ndx, ndy)

        elif mode == 1:
            # ── Kiter: preferred range 300-500, shoot constantly
            preferred_dist = 380
            if dist < preferred_dist - 60:
                # too close — back away
                p1.move(-ndx, -ndy, False, self.arena)
            elif dist > preferred_dist + 60:
                # too far — close in
                p1.move(ndx, ndy, dist > 550, self.arena)
            else:
                # strafe sideways
                perp_x = -ndy * self._p1_strafe_sign
                perp_y =  ndx * self._p1_strafe_sign
                p1.move(perp_x, perp_y, False, self.arena)
                # flip strafe direction occasionally
                if random.random() < 0.008:
                    self._p1_strafe_sign *= -1
            if p1.weapon.projectile and dist < 600:
                b = p1.start_shoot()
                if b:
                    self.bullets.append(b)
            elif dist < p1.attack_range + p2.radius + 20:
                p1.start_attack(ndx, ndy)

        else:
            # ── Dodger: circles around P2, mix of melee+ranged ─
            angle_offset = math.pi * 0.45 * self._p1_strafe_sign
            circle_dx = math.cos(math.atan2(dy, dx) + angle_offset)
            circle_dy = math.sin(math.atan2(dy, dx) + angle_offset)
            # blend circling with approach
            approach  = max(0.0, (dist - 220) / 400)
            move_dx   = circle_dx * (1 - approach) + ndx * approach
            move_dy   = circle_dy * (1 - approach) + ndy * approach
            p1.move(move_dx, move_dy, False, self.arena)
            if random.random() < 0.006:
                self._p1_strafe_sign *= -1
            if dist < p1.attack_range + p2.radius + 30:
                p1.start_attack(ndx, ndy)
            elif p1.weapon.projectile and dist < 500:
                b = p1.start_shoot()
                if b:
                    self.bullets.append(b)
            if dist > 300 and random.random() < 0.012:
                p1.start_dash(ndx, ndy)

    # ────────────────────────────────────────────────────────────
    #  Game sub-systems
    # ────────────────────────────────────────────────────────────
    def _process_melee(self):
        for attacker, defender in [(self.p1, self.p2), (self.p2, self.p1)]:
            if attacker.attack_active() and not attacker.attack_hit_registered:
                ax = attacker.x + attacker.facing_dx * attacker.attack_range
                ay = attacker.y + attacker.facing_dy * attacker.attack_range
                if defender.collides_with(ax, ay, 20):
                    defender.take_hit(attacker.attack_damage)
                    attacker.attack_hit_registered = True

    def _process_pickups(self):
        for pickup in self.arena.weapon_pickups[:]:
            if pickup.check_pickup(self.p1):
                self.p1.pick_weapon(pickup.weapon)
                self.arena.weapon_pickups.remove(pickup)
            elif pickup.check_pickup(self.p2):
                self.p2.pick_weapon(pickup.weapon)
                self.arena.weapon_pickups.remove(pickup)

    def _process_bullets(self):
        for bullet in self.bullets[:]:
            bullet.update()
            hit = False
            if not self.arena.map.is_within_bounds(bullet.x, bullet.y,
                                                    bullet.radius):
                hit = True
            elif self.arena.map.collides_with_obstacle(bullet.x, bullet.y,
                                                        bullet.radius):
                hit = True
            elif (bullet.owner is not self.p1
                  and self.p1.collides_with(bullet.x, bullet.y, bullet.radius)):
                self.p1.take_hit(bullet.damage)
                hit = True
            elif (bullet.owner is not self.p2
                  and self.p2.collides_with(bullet.x, bullet.y, bullet.radius)):
                self.p2.take_hit(bullet.damage)
                hit = True
            if hit:
                self.bullets.remove(bullet)

    # ────────────────────────────────────────────────────────────
    #  Reward function — the most important part
    # ────────────────────────────────────────────────────────────
    def _compute_reward(self):
        reward = 0.0

        # ── 1. Damage dealt / received ─────────────────────────
        p1_dmg = self._prev_p1_hp - self.p1.health
        p2_dmg = self._prev_p2_hp - self.p2.health

        if p1_dmg > 0:
            reward += p1_dmg * 2.0          # strongly reward hurting P1
            self._frames_since_damage = 0
        else:
            self._frames_since_damage += 1

        if p2_dmg > 0:
            reward -= p2_dmg * 0.8          # moderate penalty for taking hits

        # ── 2. Weapon pickup bonus ─────────────────────────────
        # Reward transitioning from no ranged weapon → ranged weapon
        if self.p2.weapon.projectile and not self._prev_p2_weapon:
            reward += 40.0

        # Small continuous bonus for having a ranged weapon
        if self.p2.weapon.projectile:
            reward += 0.05

        # ── 3. Engagement — close distance to P1 ──────────────
        dist = math.hypot(self.p2.x - self.p1.x, self.p2.y - self.p1.y)
        dist_delta = self._prev_dist - dist
        if dist_delta > 0:
            # moving toward P1
            reward += min(dist_delta * 0.08, 0.3)
        else:
            # moving away — small penalty only if also not shooting
            if not self.p2.weapon.projectile:
                reward += max(dist_delta * 0.04, -0.12)
        self._prev_dist = dist

        # Bonus for being in melee range and attacking
        if dist < 150 and self.p2.is_attacking():
            reward += 0.4

        # ── 4. Wall-hugging penalty ────────────────────────────
        margin = 80
        near_wall = (self.p2.x < margin or self.p2.x > WIDTH  - margin or
                     self.p2.y < margin or self.p2.y > HEIGHT - margin)
        if near_wall:
            reward -= 0.15

        # ── 5. Passivity penalty ───────────────────────────────
        if self._frames_since_damage > PASSIVITY_TIMEOUT:
            reward -= 0.3    # escalating penalty for not fighting

        # ── 6. Match outcome ───────────────────────────────────
        if self.p1.is_dead():
            reward += 500.0
        if self.p2.is_dead():
            reward -= 400.0

        # ── 7. Tiny step penalty (force urgency) ───────────────
        reward -= 0.05

        return reward

    # ────────────────────────────────────────────────────────────
    def render(self): pass
    def close(self):  pass