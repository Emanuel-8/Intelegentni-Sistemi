import os
import math
import random
import numpy as np
import pygame
from stable_baselines3 import PPO
from ai_helpers import get_observation

# The 9 directions the AI can move in (matches game_env.py exactly)
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

# ─────────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────────
WIDTH, HEIGHT = 1920, 1080
FPS = 60
MAX_WEAPON_PICKUPS = 5
WEAPON_RESPAWN_INTERVAL = 300

# ─────────────────────────────────────────────
#  WEAPONS
# ─────────────────────────────────────────────
class Weapon:
    def __init__(self, name, color, glow, projectile, bullet_speed, damage, fire_rate, ammo):
        self.name = name
        self.color = color
        self.glow = glow
        self.projectile = projectile
        self.bullet_speed = bullet_speed
        self.damage = damage
        self.fire_rate = fire_rate
        self.ammo = ammo

    @staticmethod
    def default_weapon():
        return Weapon("Sword", (230, 210, 130), (255, 240, 80), False, 0, 30, 0, -1)

WEAPON_TYPES = [
    Weapon("Sword",         (230, 210, 130), (255, 240,  80), False,  0, 30,  0, -1),
    Weapon("Crossbow",      (120, 190, 250), (100, 180, 255), True,  18, 20, 18, 10),
    Weapon("Pulse Rifle",   (160, 230, 170), ( 80, 255, 140), True,  26, 15, 10, 16),
    Weapon("Flare Launcher",(240, 140,  90), (255, 120,  40), True,  13, 28, 28,  6),
    Weapon("Plasma Gun",    (200, 100, 240), (210,  60, 255), True,  20, 22, 14, 12),
]

class Bullet:
    def __init__(self, x, y, dx, dy, speed, damage, color, glow, owner):
        self.x, self.y = x, y
        self.dx, self.dy = dx, dy
        self.speed = speed
        self.damage = damage
        self.color = color
        self.glow = glow
        self.owner = owner
        self.radius = 8
        self.trail = []

    def update(self):
        self.trail.append((self.x, self.y))
        if len(self.trail) > 6:
            self.trail.pop(0)
        self.x += self.dx * self.speed
        self.y += self.dy * self.speed

    def draw(self, surface):
        for i, (tx, ty) in enumerate(self.trail):
            alpha = int(180 * (i / len(self.trail)))
            r = max(2, self.radius - (len(self.trail) - i))
            s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.glow, alpha), (r + 2, r + 2), r)
            surface.blit(s, (int(tx) - r - 2, int(ty) - r - 2))
        glow_s = pygame.Surface((self.radius * 6, self.radius * 6), pygame.SRCALPHA)
        pygame.draw.circle(glow_s, (*self.glow, 80), (self.radius * 3, self.radius * 3), self.radius * 3)
        surface.blit(glow_s, (int(self.x) - self.radius * 3, int(self.y) - self.radius * 3))
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surface, (255, 255, 255), (int(self.x), int(self.y)), self.radius, 2)

class WeaponPickup:
    def __init__(self, weapon, x, y):
        self.weapon = weapon
        self.x, self.y = x, y
        self.radius = 26
        self.bob = random.uniform(0, math.pi * 2)
        self.age = 0

    def draw(self, surface):
        self.age += 1
        bob_y = math.sin(self.age * 0.05 + self.bob) * 5
        cx, cy = int(self.x), int(self.y + bob_y)
        # outer glow
        for r in range(36, 26, -2):
            alpha = int(60 * (36 - r) / 10)
            s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.weapon.glow, alpha), (r, r), r)
            surface.blit(s, (cx - r, cy - r))
        pygame.draw.circle(surface, self.weapon.color, (cx, cy), self.radius)
        pygame.draw.circle(surface, self.weapon.glow, (cx, cy), self.radius, 3)
        font = pygame.font.SysFont("arialblack", 18)
        label = font.render(self.weapon.name[0], True, (255, 255, 255))
        surface.blit(label, label.get_rect(center=(cx, cy)))
        # name tag
        nfont = pygame.font.SysFont(None, 22)
        ntag = nfont.render(self.weapon.name, True, (240, 240, 240))
        nr = ntag.get_rect(center=(cx, cy - self.radius - 12))
        bg = pygame.Surface((nr.width + 10, nr.height + 4), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 120))
        surface.blit(bg, (nr.x - 5, nr.y - 2))
        surface.blit(ntag, nr)

    def check_pickup(self, player):
        return math.hypot(player.x - self.x, player.y - self.y) <= player.radius + self.radius

# ─────────────────────────────────────────────
#  PLAYER
# ─────────────────────────────────────────────
class Player:
    def __init__(self, x, y, color, glow_color):
        self.x, self.y = x, y
        self.color = color
        self.glow_color = glow_color
        self.walk_speed = 5
        self.sprint_speed = 9
        self.max_stamina = 100
        self.stamina = 100
        self.stamina_drain = 1.5
        self.stamina_regen = 0.8
        self.dash_speed = 20
        self.dash_duration = 10
        self.dash_cooldown = 90
        self.dash_stamina_cost = 22
        self.dash_timer = 0
        self.cooldown_timer = 0
        self.dash_dx = self.dash_dy = 0
        self.attack_damage = 30
        self.attack_range = 82
        self.attack_duration = 12
        self.attack_cooldown = 38
        self.attack_timer = 0
        self.attack_cooldown_timer = 0
        self.attack_hit_registered = False
        self.max_health = 100
        self.health = 100
        self.radius = 30
        self.facing_dx = 1
        self.facing_dy = 0
        self.hit_timer = 0
        self.hit_flash_time = 14
        self.weapon = Weapon.default_weapon()
        self.ammo = -1
        self.shoot_cooldown_timer = 0
        self.trail = []

    def move(self, dx, dy, sprint, arena):
        if self.dash_timer > 0:
            self.trail.append((self.x, self.y))
            if len(self.trail) > 8: self.trail.pop(0)
            self.x += self.dash_dx * self.dash_speed
            self.y += self.dash_dy * self.dash_speed
            self.dash_timer -= 1
            arena.keep_player_in_bounds(self)
            return
        self.trail = []
        length = math.hypot(dx, dy)
        if length:
            dx /= length; dy /= length
            self.facing_dx = dx; self.facing_dy = dy
        if sprint and self.stamina > 0:
            speed = self.sprint_speed
            self.stamina = max(0, self.stamina - self.stamina_drain)
        else:
            speed = self.walk_speed
            self.stamina = min(self.max_stamina, self.stamina + self.stamina_regen)
        self.x += dx * speed
        self.y += dy * speed
        arena.keep_player_in_bounds(self)

    def update(self):
        for attr in ('cooldown_timer', 'attack_timer', 'attack_cooldown_timer',
                     'shoot_cooldown_timer', 'hit_timer'):
            v = getattr(self, attr)
            if v > 0: setattr(self, attr, v - 1)

    def start_attack(self, dx, dy):
        if self.attack_cooldown_timer > 0 or self.attack_timer > 0: return
        if dx == 0 and dy == 0: dx, dy = self.facing_dx, self.facing_dy
        length = math.hypot(dx, dy)
        if length:
            dx /= length; dy /= length
            self.facing_dx = dx; self.facing_dy = dy
        self.attack_timer = self.attack_duration
        self.attack_cooldown_timer = self.attack_cooldown
        self.attack_hit_registered = False

    def is_attacking(self): return self.attack_timer > 0
    def attack_active(self): return self.attack_timer > 0 and self.attack_timer <= self.attack_duration - 4

    def take_hit(self, damage):
        self.health = max(0, self.health - damage)
        self.hit_timer = self.hit_flash_time

    def is_dead(self): return self.health <= 0

    def start_dash(self, dx, dy):
        if self.cooldown_timer > 0 or self.dash_timer > 0 or self.stamina < self.dash_stamina_cost: return
        if dx == 0 and dy == 0: return
        length = math.hypot(dx, dy)
        if length: dx /= length; dy /= length
        self.dash_dx, self.dash_dy = dx, dy
        self.dash_timer = self.dash_duration
        self.cooldown_timer = self.dash_cooldown
        self.stamina -= self.dash_stamina_cost

    def start_shoot(self):
        if not self.weapon.projectile or self.shoot_cooldown_timer > 0: return None
        if self.weapon.ammo >= 0 and self.ammo <= 0: return None
        self.shoot_cooldown_timer = self.weapon.fire_rate
        if self.weapon.ammo >= 0: self.ammo -= 1
        bx = self.x + self.facing_dx * (self.radius + 14)
        by = self.y + self.facing_dy * (self.radius + 14)
        return Bullet(bx, by, self.facing_dx, self.facing_dy,
                      self.weapon.bullet_speed, self.weapon.damage,
                      self.weapon.color, self.weapon.glow, self)

    def pick_weapon(self, weapon):
        self.weapon = weapon
        self.ammo = -1 if weapon.ammo < 0 else weapon.ammo

    def display_ammo(self):
        return "∞" if self.ammo < 0 else str(self.ammo)

    def collides_with(self, x, y, radius):
        return math.hypot(self.x - x, self.y - y) <= self.radius + radius

    def draw(self, surface):
        # dash trail
        for i, (tx, ty) in enumerate(self.trail):
            alpha = int(100 * i / max(len(self.trail), 1))
            s = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.glow_color, alpha), (self.radius, self.radius), self.radius)
            surface.blit(s, (int(tx) - self.radius, int(ty) - self.radius))

        # glow ring
        hit = self.hit_timer > 0
        gc = (255, 80, 80) if hit else self.glow_color
        for r in range(self.radius + 14, self.radius, -3):
            a = int(50 * (r - self.radius) / 14)
            s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*gc, a), (r, r), r)
            surface.blit(s, (int(self.x) - r, int(self.y) - r))

        # body
        body_color = (255, 120, 120) if hit else self.color
        pygame.draw.circle(surface, body_color, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surface, (255, 255, 255), (int(self.x), int(self.y)), self.radius, 3)

        # direction dot
        fx = self.x + self.facing_dx * (self.radius - 8)
        fy = self.y + self.facing_dy * (self.radius - 8)
        pygame.draw.circle(surface, (255, 255, 255), (int(fx), int(fy)), 5)

        # melee weapon arc
        if self.is_attacking():
            angle = math.atan2(self.facing_dy, self.facing_dx)
            progress = 1 - (self.attack_timer / self.attack_duration)
            swing = math.sin(progress * math.pi) * 1.1
            tip_angle = angle + swing
            sword_len = self.radius + 32
            sx = self.x + math.cos(tip_angle) * 10
            sy = self.y + math.sin(tip_angle) * 10
            ex = self.x + math.cos(tip_angle) * sword_len
            ey = self.y + math.sin(tip_angle) * sword_len
            pygame.draw.line(surface, self.weapon.glow, (sx, sy), (ex, ey), 9)
            pygame.draw.line(surface, (255, 255, 255), (sx, sy), (ex, ey), 4)

        # health bar
        bw, bh = 100, 12
        bx = self.x - bw // 2
        by = self.y - self.radius - 26
        pygame.draw.rect(surface, (20, 20, 20), (bx, by, bw, bh), border_radius=6)
        hp_frac = max(0, self.health / self.max_health)
        hp_color = (
            int(40 + 200 * (1 - hp_frac)),
            int(180 * hp_frac),
            40
        )
        pygame.draw.rect(surface, hp_color, (bx, by, bw * hp_frac, bh), border_radius=6)
        pygame.draw.rect(surface, (200, 200, 200), (bx, by, bw, bh), 2, border_radius=6)

        # stamina bar
        shy = by - 11
        pygame.draw.rect(surface, (20, 20, 20), (bx, shy, bw, 8), border_radius=4)
        pygame.draw.rect(surface, (60, 180, 230), (bx, shy, bw * (self.stamina / self.max_stamina), 8), border_radius=4)
        pygame.draw.rect(surface, (120, 200, 255), (bx, shy, bw, 8), 1, border_radius=4)

# ─────────────────────────────────────────────
#  OBSTACLES
# ─────────────────────────────────────────────
class Obstacle:
    def __init__(self, shape, x, y, w, h=None, color=(90, 90, 90), edge=(140, 140, 160)):
        self.shape = shape
        self.x, self.y = x, y
        self.w = w
        self.h = h if h is not None else w
        self.color = color
        self.edge = edge

    @classmethod
    def rect(cls, x, y, w, h, color=(80, 80, 100), edge=(130, 130, 160)):
        return cls("rect", x, y, w, h, color, edge)

    @classmethod
    def circle(cls, x, y, r, color=(90, 90, 110), edge=(140, 140, 160)):
        return cls("circle", x, y, r, None, color, edge)

    def draw(self, surface):
        if self.shape == "rect":
            # shadow
            sr = pygame.Rect(self.x + 6, self.y + 6, self.w, self.h)
            ss = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            ss.fill((0, 0, 0, 60))
            surface.blit(ss, sr.topleft)
            pygame.draw.rect(surface, self.color, (self.x, self.y, self.w, self.h), border_radius=10)
            pygame.draw.rect(surface, self.edge, (self.x, self.y, self.w, self.h), 3, border_radius=10)
        else:
            cx, cy = int(self.x), int(self.y)
            # shadow
            pygame.draw.circle(surface, (0, 0, 0, 60), (cx + 5, cy + 5), self.w)
            pygame.draw.circle(surface, self.color, (cx, cy), self.w)
            pygame.draw.circle(surface, self.edge, (cx, cy), self.w, 3)

    def collides_with_circle(self, px, py, pr):
        if self.shape == "rect":
            nx = max(self.x, min(px, self.x + self.w))
            ny = max(self.y, min(py, self.y + self.h))
            return math.hypot(px - nx, py - ny) <= pr
        return math.hypot(px - self.x, py - self.y) <= self.w + pr

    def push_out(self, px, py, pr):
        if self.shape == "rect":
            left, right = self.x - pr, self.x + self.w + pr
            top, bottom = self.y - pr, self.y + self.h + pr
            if left <= px <= right and top <= py <= bottom:
                dx = min(abs(px - left), abs(px - right))
                dy = min(abs(py - top), abs(py - bottom))
                if dx < dy:
                    px = left if abs(px - left) < abs(px - right) else right
                else:
                    py = top if abs(py - top) < abs(py - bottom) else bottom
        else:
            dx, dy = px - self.x, py - self.y
            dist = math.hypot(dx, dy) or 1
            md = self.w + pr
            if dist < md:
                px = self.x + dx / dist * md
                py = self.y + dy / dist * md
        return px, py

# ─────────────────────────────────────────────
#  MAPS
# ─────────────────────────────────────────────
class Map:
    def __init__(self, name, top_color, bottom_color, accent, player_starts, obstacles):
        self.name = name
        self.top_color = top_color
        self.bottom_color = bottom_color
        self.accent = accent
        self.player_starts = player_starts
        self.obstacles = obstacles
        self._bg = None

    def _build_bg(self):
        bg = pygame.Surface((WIDTH, HEIGHT))
        for y in range(HEIGHT):
            t = y / HEIGHT
            c = tuple(int(self.top_color[i] * (1 - t) + self.bottom_color[i] * t) for i in range(3))
            pygame.draw.line(bg, c, (0, y), (WIDTH, y))
        return bg

    def draw(self, surface):
        if self._bg is None:
            self._bg = self._build_bg()
        surface.blit(self._bg, (0, 0))
        for ob in self.obstacles:
            ob.draw(surface)

    def is_within_bounds(self, x, y, r):
        return r <= x <= WIDTH - r and r <= y <= HEIGHT - r

    def collides_with_obstacle(self, x, y, r):
        return any(ob.collides_with_circle(x, y, r) for ob in self.obstacles)

    def random_open_position(self):
        for _ in range(300):
            x = random.randint(120, WIDTH - 120)
            y = random.randint(120, HEIGHT - 120)
            if not self.collides_with_obstacle(x, y, 30):
                return x, y
        return WIDTH // 2, HEIGHT // 2

def create_maps():
    return [
        Map("Forest Canyon",
            (18, 58, 22), (38, 108, 55), (80, 200, 80),
            [(240, 540), (1680, 540)],
            [
                Obstacle.circle(520, 340, 52, (60, 90, 55), (100, 160, 80)),
                Obstacle.circle(1400, 300, 46, (55, 85, 50), (90, 150, 70)),
                Obstacle.circle(960, 700, 38, (65, 95, 58), (110, 170, 85)),
                Obstacle.rect(740, 410, 360, 44, (70, 75, 65), (110, 120, 90)),
                Obstacle.rect(1100, 610, 340, 44, (70, 75, 65), (110, 120, 90)),
                Obstacle.rect(200, 170, 200, 44, (80, 85, 70), (120, 130, 95)),
                Obstacle.rect(1620, 730, 190, 44, (80, 85, 70), (120, 130, 95)),
                Obstacle.rect(400, 820, 260, 40, (70, 75, 65), (110, 120, 90)),
                Obstacle.rect(1200, 180, 240, 40, (70, 75, 65), (110, 120, 90)),
            ]),
        Map("Sunset Quarry",
            (80, 32, 12), (190, 100, 22), (255, 150, 60),
            [(240, 240), (1680, 840)],
            [
                Obstacle.rect(580, 130, 760, 64, (110, 80, 55), (180, 130, 80)),
                Obstacle.rect(220, 430, 300, 88, (110, 80, 55), (180, 130, 80)),
                Obstacle.rect(1390, 510, 260, 88, (110, 80, 55), (180, 130, 80)),
                Obstacle.circle(960, 570, 52, (130, 110, 90), (200, 160, 110)),
                Obstacle.rect(840, 330, 260, 44, (100, 72, 48), (165, 120, 72)),
                Obstacle.rect(500, 750, 200, 50, (110, 80, 55), (180, 130, 80)),
                Obstacle.rect(1220, 760, 210, 50, (110, 80, 55), (180, 130, 80)),
                Obstacle.circle(340, 620, 36, (120, 95, 65), (190, 145, 90)),
                Obstacle.circle(1580, 400, 36, (120, 95, 65), (190, 145, 90)),
            ]),
        Map("Ruins Arena",
            (14, 18, 50), (65, 50, 110), (160, 120, 255),
            [(340, 540), (1580, 540)],
            [
                Obstacle.rect(460, 200, 68, 340, (75, 75, 120), (130, 120, 200)),
                Obstacle.rect(1392, 200, 68, 340, (75, 75, 120), (130, 120, 200)),
                Obstacle.circle(960, 250, 56, (85, 80, 135), (140, 130, 210)),
                Obstacle.circle(960, 830, 48, (85, 80, 135), (140, 130, 210)),
                Obstacle.rect(740, 690, 440, 54, (75, 75, 120), (130, 120, 200)),
                Obstacle.rect(840, 410, 220, 44, (95, 90, 150), (155, 145, 225)),
                Obstacle.rect(260, 700, 160, 44, (75, 75, 120), (130, 120, 200)),
                Obstacle.rect(1500, 700, 160, 44, (75, 75, 120), (130, 120, 200)),
                Obstacle.circle(540, 560, 34, (85, 80, 135), (140, 130, 210)),
                Obstacle.circle(1380, 560, 34, (85, 80, 135), (140, 130, 210)),
            ]),
        Map("Neon Void",
            (5, 5, 20), (10, 8, 40), (0, 255, 200),
            [(280, 540), (1640, 540)],
            [
                Obstacle.rect(600, 200, 160, 160, (20, 20, 60), (0, 220, 180)),
                Obstacle.rect(1160, 200, 160, 160, (20, 20, 60), (0, 220, 180)),
                Obstacle.rect(600, 720, 160, 160, (20, 20, 60), (220, 0, 180)),
                Obstacle.rect(1160, 720, 160, 160, (20, 20, 60), (220, 0, 180)),
                Obstacle.circle(960, 540, 60, (15, 15, 50), (0, 200, 255)),
                Obstacle.rect(820, 450, 280, 40, (20, 20, 60), (180, 0, 255)),
                Obstacle.circle(400, 350, 40, (20, 20, 60), (255, 60, 200)),
                Obstacle.circle(1520, 350, 40, (20, 20, 60), (255, 60, 200)),
                Obstacle.circle(400, 730, 40, (20, 20, 60), (60, 255, 200)),
                Obstacle.circle(1520, 730, 40, (20, 20, 60), (60, 255, 200)),
            ]),
    ]

MAP_NAMES = ["Forest Canyon", "Sunset Quarry", "Ruins Arena", "Neon Void"]
MAP_DESCRIPTIONS = [
    "Lush canyon with stone pillars and tree clusters.",
    "Blazing quarry with high walls and rock formations.",
    "Ancient ruins with columns and mystical arches.",
    "Cyberpunk void with glowing geometric obstacles.",
]

# ─────────────────────────────────────────────
#  ARENA ENVIRONMENT
# ─────────────────────────────────────────────
class Arena:
    def __init__(self, player1, player2, map_index=0):
        self.player1 = player1
        self.player2 = player2
        self.all_maps = create_maps()
        self.map_index = map_index
        self.map = self.all_maps[map_index]
        self.weapon_pickups = []
        self.spawn_timer = WEAPON_RESPAWN_INTERVAL // 2
        self._place_players()

    def _place_players(self):
        self.player1.x, self.player1.y = self.map.player_starts[0]
        self.player2.x, self.player2.y = self.map.player_starts[1]

    def switch_map(self, index):
        self.map_index = index
        self.map = self.all_maps[index]
        self.weapon_pickups.clear()
        self.spawn_timer = WEAPON_RESPAWN_INTERVAL // 2
        self._place_players()

    def update(self):
        self.spawn_timer -= 1
        if self.spawn_timer <= 0 and len(self.weapon_pickups) < MAX_WEAPON_PICKUPS:
            self._spawn_pickup()
            self.spawn_timer = WEAPON_RESPAWN_INTERVAL

    def _spawn_pickup(self):
        weapon = random.choice(WEAPON_TYPES[1:])
        x, y = self.map.random_open_position()
        self.weapon_pickups.append(WeaponPickup(weapon, x, y))

    def keep_player_in_bounds(self, player):
        player.x = max(player.radius, min(player.x, WIDTH - player.radius))
        player.y = max(player.radius, min(player.y, HEIGHT - player.radius))

    def resolve_obstacle_collision(self, player):
        for ob in self.map.obstacles:
            if ob.collides_with_circle(player.x, player.y, player.radius):
                player.x, player.y = ob.push_out(player.x, player.y, player.radius)

    def draw(self, surface):
        self.map.draw(surface)
        for pickup in self.weapon_pickups:
            pickup.draw(surface)

def resolve_player_collision(p1, p2):
    dx, dy = p2.x - p1.x, p2.y - p1.y
    dist = math.hypot(dx, dy) or 0.01
    md = p1.radius + p2.radius
    if dist < md:
        overlap = (md - dist) * 0.52
        px, py = dx / dist * overlap, dy / dist * overlap
        p1.x -= px; p1.y -= py
        p2.x += px; p2.y += py

# ─────────────────────────────────────────────
#  HUD & UI HELPERS
# ─────────────────────────────────────────────
def draw_text_shadow(surface, text, font, color, pos, shadow=(3, 3)):
    s = font.render(text, True, (0, 0, 0))
    surface.blit(s, (pos[0] + shadow[0], pos[1] + shadow[1]))
    surface.blit(font.render(text, True, color), pos)

def draw_panel(surface, rect, bg=(20, 20, 40), alpha=200, radius=16, border=(100, 100, 160)):
    s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(s, (*bg, alpha), (0, 0, rect.width, rect.height), border_radius=radius)
    pygame.draw.rect(s, (*border, 200), (0, 0, rect.width, rect.height), 2, border_radius=radius)
    surface.blit(s, rect.topleft)

class Button:
    def __init__(self, text, x, y, w, h, base=(30, 30, 55), accent=(140, 120, 255)):
        self.text = text
        self.rect = pygame.Rect(x, y, w, h)
        self.base = base
        self.accent = accent

    def draw(self, surface, font, override_accent=None):
        ac = override_accent or self.accent
        hovered = self.rect.collidepoint(pygame.mouse.get_pos())
        col = tuple(min(255, c + 35) for c in self.base) if hovered else self.base

        if hovered:
            glow = self.rect.inflate(14, 14)
            gs = pygame.Surface((glow.width, glow.height), pygame.SRCALPHA)
            pygame.draw.rect(gs, (*ac, 90), (0, 0, glow.width, glow.height), border_radius=20)
            surface.blit(gs, glow.topleft)

        pygame.draw.rect(surface, col, self.rect, border_radius=16)
        pygame.draw.rect(surface, ac, self.rect, 3, border_radius=16)
        label = font.render(self.text, True, (245, 245, 255))
        surface.blit(label, label.get_rect(center=self.rect.center))

    def clicked(self, event):
        return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos)

# ─────────────────────────────────────────────
#  PARTICLES
# ─────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, color):
        self.x, self.y = x, y
        self.color = color
        angle = random.uniform(0, math.pi * 2)
        speed = random.uniform(2, 7)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = random.randint(15, 35)
        self.max_life = self.life
        self.r = random.randint(3, 7)

    def update(self):
        self.x += self.vx; self.y += self.vy
        self.vy += 0.2
        self.vx *= 0.95; self.vy *= 0.95
        self.life -= 1

    def draw(self, surface):
        a = int(255 * self.life / self.max_life)
        s = pygame.Surface((self.r * 2, self.r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, a), (self.r, self.r), self.r)
        surface.blit(s, (int(self.x) - self.r, int(self.y) - self.r))

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    # ── Load trained AI model ────────────────────────────────────
    if not os.path.exists("p2_ai.zip"):
        print("=" * 58)
        print("  ERROR: p2_ai.zip not found!")
        print("  Please run  python train_ai.py  first.")
        print("=" * 58)
        return
    print("Loading AI model for Player 2…")
    model = PPO.load("p2_ai")
    print("AI ready! Starting game…\n")

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Arena Fighters")
    clock = pygame.time.Clock()

    TITLE_FONT  = pygame.font.SysFont("arialblack", 96)
    HEADER_FONT = pygame.font.SysFont("arialblack", 48)
    MENU_FONT   = pygame.font.SysFont(None, 46)
    BODY_FONT   = pygame.font.SysFont(None, 34)
    SMALL_FONT  = pygame.font.SysFont(None, 26)

    MENU, GAME, GAME_OVER = 0, 1, 2
    state = MENU
    selected_map = 0
    winner_text = ""
    winner_color = (255, 220, 80)

    # ── menu background ──
    menu_bg = pygame.Surface((WIDTH, HEIGHT))
    for y in range(HEIGHT):
        t = y / HEIGHT
        c = (int(8 + t * 22), int(8 + t * 20), int(30 + t * 60))
        pygame.draw.line(menu_bg, c, (0, y), (WIDTH, y))
    # subtle grid
    for gx in range(0, WIDTH, 80):
        pygame.draw.line(menu_bg, (30, 30, 60), (gx, 0), (gx, HEIGHT))
    for gy in range(0, HEIGHT, 80):
        pygame.draw.line(menu_bg, (30, 30, 60), (0, gy), (WIDTH, gy))

    # ── buttons ──
    BTN_W, BTN_H = 380, 80
    cx = WIDTH // 2
    start_btn = Button("⚔  Start Battle", cx - BTN_W // 2, HEIGHT // 2 + 60, BTN_W, BTN_H,
                       (35, 30, 70), (180, 140, 255))
    exit_btn  = Button("✕  Exit",         cx - BTN_W // 2, HEIGHT // 2 + 160, BTN_W, BTN_H,
                       (60, 20, 20), (220, 80, 80))
    rematch_btn = Button("⟳  Rematch",    cx - BTN_W // 2, HEIGHT // 2 + 20,  BTN_W, BTN_H,
                         (35, 30, 70), (180, 140, 255))
    menu_btn    = Button("⌂  Main Menu",  cx - BTN_W // 2, HEIGHT // 2 + 120, BTN_W, BTN_H,
                         (20, 40, 60), (80, 180, 255))

    MAP_BW, MAP_BH = 340, 66
    map_btns = [
        Button(MAP_NAMES[i],
               cx - 730 + i * 360, HEIGHT // 2 - 80,
               MAP_BW, MAP_BH,
               (30, 40, 30) if i == 0 else (50, 28, 10) if i == 1 else (20, 18, 50) if i == 2 else (5, 5, 20),
               (80, 220, 80)  if i == 0 else (255, 140, 40) if i == 1 else (160, 120, 255) if i == 2 else (0, 220, 200))
        for i in range(4)
    ]

    def make_players():
        p1 = Player(0, 0, (100, 180, 240), (80, 160, 255))
        p2 = Player(0, 0, (240, 140, 100), (255, 120, 60))
        return p1, p2

    p1, p2 = make_players()
    arena = Arena(p1, p2, selected_map)
    bullets = []
    particles = []

    def reset_game():
        nonlocal p1, p2, arena, bullets, particles, winner_text
        p1, p2 = make_players()
        arena = Arena(p1, p2, selected_map)
        bullets = []
        particles = []
        winner_text = ""

    def spawn_particles(x, y, color, n=12):
        for _ in range(n):
            particles.append(Particle(x, y, color))

    tick = 0
    running = True

    while running:
        tick += 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if state == MENU:
                if start_btn.clicked(event):
                    arena.switch_map(selected_map)
                    reset_game()
                    state = GAME
                if exit_btn.clicked(event):
                    running = False
                for i, mb in enumerate(map_btns):
                    if mb.clicked(event):
                        selected_map = i

            elif state == GAME_OVER:
                if rematch_btn.clicked(event):
                    reset_game()
                    state = GAME
                if menu_btn.clicked(event):
                    state = MENU
                if exit_btn.clicked(event):
                    running = False

        keys = pygame.key.get_pressed()

        # ──────────── MENU ────────────
        if state == MENU:
            screen.blit(menu_bg, (0, 0))

            # animated star particles
            if tick % 4 == 0:
                sx = random.randint(0, WIDTH)
                sy = random.randint(0, HEIGHT)
                particles.append(Particle(sx, sy, (180, 160, 255)))
            for pt in particles[:]:
                pt.update()
                pt.draw(screen)
                if pt.life <= 0:
                    particles.remove(pt)

            # title glow
            title_surf = TITLE_FONT.render("ARENA FIGHTERS", True, (220, 210, 255))
            ts_glow = pygame.Surface(title_surf.get_size(), pygame.SRCALPHA)
            for _ in range(3):
                pygame.draw.rect(ts_glow, (140, 100, 255, 30),
                                 ts_glow.get_rect().inflate(20, 10), border_radius=8)
            tx = cx - title_surf.get_width() // 2
            screen.blit(ts_glow, (tx - 10, 68))
            draw_text_shadow(screen, "ARENA FIGHTERS", TITLE_FONT, (220, 210, 255), (tx, 70))

            sub = BODY_FONT.render("Choose your arena and fight!", True, (180, 180, 220))
            screen.blit(sub, sub.get_rect(center=(cx, 190)))

            # map buttons
            for i, mb in enumerate(map_btns):
                is_active = (i == selected_map)
                ac = mb.accent if is_active else (70, 70, 100)
                if is_active:
                    glow_r = mb.rect.inflate(16, 16)
                    gs = pygame.Surface((glow_r.width, glow_r.height), pygame.SRCALPHA)
                    pygame.draw.rect(gs, (*mb.accent, 60), (0, 0, glow_r.width, glow_r.height), border_radius=20)
                    screen.blit(gs, glow_r.topleft)
                mb.draw(screen, MENU_FONT, ac)
                desc = SMALL_FONT.render(MAP_DESCRIPTIONS[i], True, (180, 180, 200))
                screen.blit(desc, desc.get_rect(center=(mb.rect.centerx, mb.rect.bottom + 22)))

            # control guide panel
            panel_r = pygame.Rect(cx - 560, HEIGHT - 190, 1120, 130)
            draw_panel(screen, panel_r, (10, 10, 30), 200, 12, (80, 80, 120))
            clines = [
                ("P1", "WASD Move  |  LSHIFT Sprint  |  Q Dash  |  F Melee  |  E Shoot", (140, 200, 255)),
                ("P2", "AI  –  Trained with Reinforcement Learning  (no keyboard)", (255, 180, 120)),
            ]
            for li, (tag, txt, col) in enumerate(clines):
                t_surf = SMALL_FONT.render(f"[{tag}]  {txt}", True, col)
                screen.blit(t_surf, t_surf.get_rect(center=(cx, HEIGHT - 160 + li * 38)))

            start_btn.draw(screen, MENU_FONT)
            exit_btn.draw(screen, MENU_FONT)

            if keys[pygame.K_RETURN]:
                arena.switch_map(selected_map)
                reset_game()
                state = GAME
            if keys[pygame.K_ESCAPE]:
                running = False

        # ──────────── GAME ────────────
        elif state == GAME:
            arena.update()

            # P1 input
            dx1 = (keys[pygame.K_d] - keys[pygame.K_a])
            dy1 = (keys[pygame.K_s] - keys[pygame.K_w])
            sprint1 = keys[pygame.K_LSHIFT]
            if keys[pygame.K_q]: p1.start_dash(dx1, dy1)
            if keys[pygame.K_f]: p1.start_attack(dx1, dy1)
            if keys[pygame.K_e]:
                b = p1.start_shoot()
                if b: bullets.append(b)
            p1.move(dx1, dy1, sprint1, arena)

            # P2 input — controlled by the trained AI
            obs = get_observation(p1, p2, arena, bullets)
            ai_action, _ = model.predict(obs, deterministic=True)
            move_idx, sprint2, dash2, melee2, shoot2 = ai_action
            dx2, dy2 = MOVEMENT_DIRS[int(move_idx)]
            if dash2:  p2.start_dash(dx2, dy2)
            if melee2: p2.start_attack(dx2, dy2)
            if shoot2:
                b = p2.start_shoot()
                if b: bullets.append(b)
            p2.move(dx2, dy2, bool(sprint2), arena)

            p1.update(); p2.update()
            arena.resolve_obstacle_collision(p1)
            arena.resolve_obstacle_collision(p2)
            resolve_player_collision(p1, p2)

            # melee hit detection
            for attacker, defender in [(p1, p2), (p2, p1)]:
                if attacker.attack_active() and not attacker.attack_hit_registered:
                    ax = attacker.x + attacker.facing_dx * attacker.attack_range
                    ay = attacker.y + attacker.facing_dy * attacker.attack_range
                    if defender.collides_with(ax, ay, 20):
                        defender.take_hit(attacker.attack_damage)
                        attacker.attack_hit_registered = True
                        spawn_particles(defender.x, defender.y, (255, 80, 80))

            # weapon pickups
            for pickup in arena.weapon_pickups[:]:
                if pickup.check_pickup(p1):
                    spawn_particles(pickup.x, pickup.y, pickup.weapon.color, 10)
                    p1.pick_weapon(pickup.weapon)
                    arena.weapon_pickups.remove(pickup)
                elif pickup.check_pickup(p2):
                    spawn_particles(pickup.x, pickup.y, pickup.weapon.color, 10)
                    p2.pick_weapon(pickup.weapon)
                    arena.weapon_pickups.remove(pickup)

            # bullets
            for bullet in bullets[:]:
                bullet.update()
                hit = False
                if not arena.map.is_within_bounds(bullet.x, bullet.y, bullet.radius):
                    hit = True
                elif arena.map.collides_with_obstacle(bullet.x, bullet.y, bullet.radius):
                    spawn_particles(bullet.x, bullet.y, bullet.color, 6)
                    hit = True
                elif bullet.owner is not p1 and p1.collides_with(bullet.x, bullet.y, bullet.radius):
                    p1.take_hit(bullet.damage)
                    spawn_particles(p1.x, p1.y, (255, 80, 80), 10)
                    hit = True
                elif bullet.owner is not p2 and p2.collides_with(bullet.x, bullet.y, bullet.radius):
                    p2.take_hit(bullet.damage)
                    spawn_particles(p2.x, p2.y, (255, 80, 80), 10)
                    hit = True
                if hit:
                    bullets.remove(bullet)

            # particles
            for pt in particles[:]:
                pt.update()
                if pt.life <= 0: particles.remove(pt)

            # ── draw ──
            arena.draw(screen)
            for pt in particles:
                pt.draw(screen)
            for b in bullets:
                b.draw(screen)
            p1.draw(screen)
            p2.draw(screen)

            # ── HUD ──
            hud_panel = pygame.Rect(20, 20, 420, 200)
            draw_panel(screen, hud_panel, (8, 8, 24), 210, 14, (80, 80, 130))

            draw_text_shadow(screen, f"Map: {arena.map.name}", BODY_FONT, (200, 200, 255), (36, 34))
            draw_text_shadow(screen, f"P1 ▶ {p1.weapon.name}   Ammo: {p1.display_ammo()}",
                             BODY_FONT, (120, 200, 255), (36, 74))
            draw_text_shadow(screen, f"P2 ▶ {p2.weapon.name}   Ammo: {p2.display_ammo()}",
                             BODY_FONT, (255, 170, 100), (36, 114))
            draw_text_shadow(screen, "Walk over glowing orbs to pick up weapons.",
                             SMALL_FONT, (170, 170, 200), (36, 158))
            draw_text_shadow(screen, "P1: E Shoot / F Melee   P2: . Shoot / RCTRL Melee",
                             SMALL_FONT, (170, 170, 200), (36, 182))

            if p1.is_dead() or p2.is_dead():
                if p1.is_dead():
                    winner_text = "PLAYER 2 WINS!"
                    winner_color = (255, 170, 80)
                    spawn_particles(p2.x, p2.y, (255, 220, 60), 30)
                else:
                    winner_text = "PLAYER 1 WINS!"
                    winner_color = (100, 210, 255)
                    spawn_particles(p1.x, p1.y, (100, 200, 255), 30)
                state = GAME_OVER

        # ──────────── GAME OVER ────────────
        elif state == GAME_OVER:
            arena.draw(screen)
            for pt in particles[:]:
                pt.update()
                pt.draw(screen)
                if pt.life <= 0: particles.remove(pt)

            # celebration bursts
            if tick % 18 == 0:
                for _ in range(16):
                    particles.append(Particle(
                        random.randint(WIDTH // 4, 3 * WIDTH // 4),
                        random.randint(HEIGHT // 4, 3 * HEIGHT // 4),
                        random.choice([(255, 220, 60), (100, 220, 255), (255, 100, 180), (80, 255, 120)])
                    ))

            # dim overlay
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 170))
            screen.blit(overlay, (0, 0))

            # winner panel
            panel = pygame.Rect(cx - 380, HEIGHT // 2 - 160, 760, 340)
            draw_panel(screen, panel, (10, 10, 30), 230, 20, (120, 100, 200))

            tw = TITLE_FONT.render(winner_text, True, winner_color)
            screen.blit(tw, tw.get_rect(center=(cx, HEIGHT // 2 - 80)))

            sub2 = HEADER_FONT.render("GG!", True, (200, 200, 255))
            screen.blit(sub2, sub2.get_rect(center=(cx, HEIGHT // 2 - 10)))

            rematch_btn.draw(screen, MENU_FONT)
            menu_btn.draw(screen, MENU_FONT)
            exit_btn.draw(screen, MENU_FONT)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()
