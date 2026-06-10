"""
game_env.py
─────────────────────────────────────────────────────────────
A Gymnasium environment that wraps your game's logic so that
a Reinforcement Learning algorithm can train in it.

Key ideas
─────────
• We run the game WITHOUT rendering (headless) so training
  is fast — thousands of matches per minute.
• The AI controls Player 2.
• Player 1 is run by a simple rule-based bot during training.
• After each frame the AI receives a REWARD signal:
    +points for hurting P1, −points for being hurt, big bonus
    for winning, big penalty for dying.
  The AI's only goal is to maximise its total reward over time.
"""

# ── Suppress pygame window during training ──────────────────────
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import sys, math, random

# Initialise pygame minimally (needed so the module can be imported)
import pygame
pygame.init()
pygame.display.set_mode((1, 1))

import numpy as np
import gymnasium as gym
from gymnasium import spaces

# Make sure Python can find game.py in the same folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game import (
    Player, Arena, resolve_player_collision, WIDTH, HEIGHT
)
from ai_helpers import get_observation

# ── The 9 movement directions the AI can choose from ────────────
MOVEMENT_DIRS = [
    ( 0,  0),   # 0  stand still
    ( 0, -1),   # 1  up
    ( 0,  1),   # 2  down
    (-1,  0),   # 3  left
    ( 1,  0),   # 4  right
    (-1, -1),   # 5  up-left
    ( 1, -1),   # 6  up-right
    (-1,  1),   # 7  down-left
    ( 1,  1),   # 8  down-right
]


class ArenaFightEnv(gym.Env):
    """
    One episode = one full match (until someone dies or time runs out).

    Observation space  : 22 floats in [-1, 1]  (see ai_helpers.py)
    Action space       : MultiDiscrete [9, 2, 2, 2, 2]
        [0] movement direction  (0-8)
        [1] sprint              (0 = off, 1 = on)
        [2] dash                (0 = off, 1 = trigger)
        [3] melee attack        (0 = off, 1 = trigger)
        [4] shoot               (0 = off, 1 = trigger)
    """

    metadata = {"render_modes": []}

    def __init__(self):
        super().__init__()

        self.action_space = spaces.MultiDiscrete([9, 2, 2, 2, 2])
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(22,), dtype=np.float32
        )

        # Will be created fresh in reset()
        self.p1 = self.p2 = self.arena = None
        self.bullets: list = []
        self._prev_p1_hp = 100.0
        self._prev_p2_hp = 100.0
        self._prev_dist_to_p1 = 0.0
        self.current_step = 0
        self.MAX_STEPS = 3600   # 60 seconds worth of frames

    # ────────────────────────────────────────────────────────────
    def reset(self, seed=None, options=None):
        """Start a brand-new match."""
        super().reset(seed=seed)

        # Create fresh players (colours must match the main game)
        self.p1 = Player(0, 0, (100, 180, 240), (80,  160, 255))
        self.p2 = Player(0, 0, (240, 140, 100), (255, 120,  60))

        # Random map each episode so the AI generalises
        self.arena = Arena(self.p1, self.p2, random.randint(0, 3))
        self.bullets = []
        self._prev_p1_hp = 100.0
        self._prev_p2_hp = 100.0
        self._prev_dist_to_p1 = math.hypot(self.p2.x - self.p1.x, self.p2.y - self.p1.y)
        self.current_step = 0

        obs = get_observation(self.p1, self.p2, self.arena, self.bullets)
        return obs, {}

    # ────────────────────────────────────────────────────────────
    def step(self, action):
        """
        Advance the game by ONE frame.

        action : array-like of length 5 (from the AI)
        returns: (observation, reward, terminated, truncated, info)
        """
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

        # ── Rule-based bot for P1 ──────────────────────────────
        self._run_p1_bot()

        # ── Game physics ───────────────────────────────────────
        self.p1.update()
        self.p2.update()
        self.arena.resolve_obstacle_collision(self.p1)
        self.arena.resolve_obstacle_collision(self.p2)
        resolve_player_collision(self.p1, self.p2)
        self._process_melee()
        self._process_pickups()
        self._process_bullets()
        self.arena.update()   # handles weapon-pickup spawning

        # ── Reward ────────────────────────────────────────────
        reward = self._compute_reward()
        self._prev_p1_hp = float(self.p1.health)
        self._prev_p2_hp = float(self.p2.health)

        self.current_step += 1
        terminated = self.p1.is_dead() or self.p2.is_dead()
        truncated  = self.current_step >= self.MAX_STEPS

        obs  = get_observation(self.p1, self.p2, self.arena, self.bullets)
        info = {
            "p1_health": self.p1.health,
            "p2_health": self.p2.health,
            "winner":    ("p2" if self.p1.is_dead()
                          else "p1" if self.p2.is_dead()
                          else None),
        }
        return obs, reward, terminated, truncated, info

    # ────────────────────────────────────────────────────────────
    #  Rule-based P1 bot
    # ────────────────────────────────────────────────────────────
    def _run_p1_bot(self):
        """
        Simple deterministic bot for P1.
        Moves toward P2, attacks when close, occasionally dashes.
        This gives the AI a consistent opponent to learn against.
        """
        p1, p2 = self.p1, self.p2
        dx   = p2.x - p1.x
        dy   = p2.y - p1.y
        dist = math.hypot(dx, dy) or 1.0
        ndx, ndy = dx / dist, dy / dist

        # Move toward opponent; sprint if far away
        p1.move(ndx, ndy, dist > 350, self.arena)

        # Melee if close enough
        if dist < p1.attack_range + p2.radius + 20:
            p1.start_attack(ndx, ndy)
        # Shoot if has a ranged weapon and medium range
        elif p1.weapon.projectile and dist < 550:
            b = p1.start_shoot()
            if b:
                self.bullets.append(b)

        # 1.5% chance per frame to dash toward P2
        if dist > 250 and random.random() < 0.015:
            p1.start_dash(ndx, ndy)

    # ────────────────────────────────────────────────────────────
    #  Game sub-systems (no rendering)
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
            if not self.arena.map.is_within_bounds(bullet.x, bullet.y, bullet.radius):
                hit = True
            elif self.arena.map.collides_with_obstacle(bullet.x, bullet.y, bullet.radius):
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
    #  Reward function  ← THE MOST IMPORTANT PART
    # ────────────────────────────────────────────────────────────
    def _compute_reward(self):
        reward = 0.0

        # Strongly reward dealing damage to P1
        p1_dmg = self._prev_p1_hp - self.p1.health
        if p1_dmg > 0:
            reward += p1_dmg * 1.6

        # Penalise taking damage, but make attack worth more than caution
        p2_dmg = self._prev_p2_hp - self.p2.health
        if p2_dmg > 0:
            reward -= p2_dmg * 0.6

        # Reward moving toward P1 and closing the distance
        dist_to_p1 = math.hypot(self.p2.x - self.p1.x, self.p2.y - self.p1.y)
        dist_delta = self._prev_dist_to_p1 - dist_to_p1
        if dist_delta > 0:
            reward += min(dist_delta * 0.15, 0.25)
        else:
            reward += max(dist_delta * 0.05, -0.1)
        self._prev_dist_to_p1 = dist_to_p1

        # Big bonus / penalty for match outcome
        if self.p1.is_dead():
            reward += 700.0
        if self.p2.is_dead():
            reward -= 250.0

        # Step penalty to discourage camping and force action
        reward -= 0.1

        return reward

    # ────────────────────────────────────────────────────────────
    def render(self):
        pass   # No rendering during training

    def close(self):
        pass
