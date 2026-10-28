import argparse
import itertools
import json
import math
import os
import platform
import random
from collections import namedtuple

import numpy as np

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

import map_art
from ai_player import AIController, DIFFICULTIES, load_policy, policy_status
from net import (BTN_DASH, BTN_MELEE, BTN_SHOOT, DEFAULT_PORT, PROTOCOL_VERSION,
                 HostConnector, JoinConnector, LanBeacon, LanScanner)
from sfx import SoundBank

# ─────────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────────
WIDTH, HEIGHT = 1920, 1080
FPS = 60
MAX_WEAPON_PICKUPS = 5
WEAPON_RESPAWN_INTERVAL = 300

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".arena_fighters.json")

# ─────────────────────────────────────────────
#  CACHED DRAWING HELPERS
#  (sprites are built once instead of every frame)
# ─────────────────────────────────────────────
_sprite_cache = {}
_font_cache = {}


def get_font(size, bold=True):
    key = (size, bold)
    f = _font_cache.get(key)
    if f is None:
        f = pygame.font.SysFont("arialblack,arial,dejavusans", size) if bold \
            else pygame.font.SysFont("segoeui,arial,dejavusans", size)
        _font_cache[key] = f
    return f


def cached(key, builder):
    spr = _sprite_cache.get(key)
    if spr is None:
        spr = _sprite_cache[key] = builder()
    return spr


def alpha_circle(color, r, alpha):
    """Translucent filled circle; alpha is bucketed so the cache stays small."""
    r = max(1, int(r))
    alpha = max(0, min(255, int(alpha) // 16 * 16))

    def build():
        s = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*color[:3], alpha), (r + 1, r + 1), r)
        return s
    return cached(("ac", tuple(color[:3]), r, alpha), build)


def blit_center(surface, spr, x, y, flags=0):
    surface.blit(spr, (int(x) - spr.get_width() // 2, int(y) - spr.get_height() // 2), special_flags=flags)


def add_glow(surface, color, x, y, radius, intensity=1.0):
    """Additive light blob – makes bullets, pickups and hits 'shine'."""
    spr = map_art.glow_sprite(color, int(radius), round(intensity, 1))
    blit_center(surface, spr, x, y, pygame.BLEND_ADD)


def sphere_sprite(color, r, hit=False):
    """A lit, anti-aliased ball used for the fighters' bodies."""
    def build():
        size = r * 2 + 4
        yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
        c = (size - 1) / 2
        nx, ny = (xx - c) / r, (yy - c) / r
        d2 = nx * nx + ny * ny
        nz = np.sqrt(np.clip(1 - d2, 0, 1))
        lx, ly, lz = -0.45, -0.6, 0.66
        diff = np.clip(nx * lx + ny * ly + nz * lz, 0, 1)
        spec = diff ** 28
        base = np.array((255, 110, 110) if hit else color, dtype=np.float32)
        rgb = base[None, None, :] * (0.38 + 0.72 * diff)[..., None] + 255 * 0.6 * spec[..., None]
        rim = np.clip((np.sqrt(d2) - 0.82) / 0.18, 0, 1)[..., None]
        rgb = rgb * (1 - rim * 0.35)
        alpha = np.clip((1 - np.sqrt(d2)) * r + 0.5, 0, 1) * 255
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        px = pygame.surfarray.pixels3d(s)
        px[:, :, :] = np.clip(rgb, 0, 255).astype(np.uint8).transpose(1, 0, 2)
        del px
        pa = pygame.surfarray.pixels_alpha(s)
        pa[:, :] = alpha.astype(np.uint8).T
        del pa
        return s
    return cached(("sphere", tuple(color), r, hit), build)


def ground_shadow(w, h, alpha=110):
    def build():
        sh, _pad = map_art.soft_shadow((w, h), alpha, 4)
        return sh
    return cached(("gshadow", w, h, alpha), build)

# ─────────────────────────────────────────────
#  PIXEL-ART WEAPON SPRITES  (drawn procedurally)
# ─────────────────────────────────────────────
def make_sword_sprite(color, glow):
    s = pygame.Surface((48, 14), pygame.SRCALPHA)
    # blade
    for x in range(6, 44):
        pygame.draw.line(s, (220, 220, 255), (x, 6), (x, 8))
    pygame.draw.line(s, (255, 255, 255), (6, 7), (44, 7))
    # tip
    pygame.draw.line(s, (200, 200, 240), (44, 7), (47, 7))
    # crossguard
    pygame.draw.rect(s, color, (4, 2, 4, 10))
    pygame.draw.rect(s, glow, (4, 2, 4, 10), 1)
    # handle
    pygame.draw.rect(s, (100, 70, 40), (0, 5, 5, 5))
    return s

def make_crossbow_sprite(color, glow):
    s = pygame.Surface((48, 22), pygame.SRCALPHA)
    # stock
    pygame.draw.rect(s, (100, 70, 40), (0, 8, 30, 6))
    pygame.draw.rect(s, (140, 100, 60), (0, 8, 30, 6), 1)
    # bow arms
    pygame.draw.line(s, color, (18, 2), (18, 20), 2)
    # string
    pygame.draw.line(s, (200, 200, 200), (18, 2), (30, 11), 1)
    pygame.draw.line(s, (200, 200, 200), (18, 20), (30, 11), 1)
    # front rail
    pygame.draw.rect(s, (80, 60, 30), (28, 9, 20, 4))
    # tip glow
    pygame.draw.circle(s, glow, (47, 11), 3)
    return s

def make_pulse_rifle_sprite(color, glow):
    s = pygame.Surface((52, 16), pygame.SRCALPHA)
    # body
    pygame.draw.rect(s, (50, 60, 50), (4, 4, 36, 8), border_radius=2)
    pygame.draw.rect(s, color, (4, 4, 36, 8), 1, border_radius=2)
    # barrel
    pygame.draw.rect(s, (40, 50, 40), (38, 6, 14, 4))
    pygame.draw.rect(s, glow, (38, 6, 14, 4), 1)
    # stock
    pygame.draw.rect(s, (60, 70, 60), (0, 5, 6, 6))
    # mag
    pygame.draw.rect(s, color, (12, 11, 8, 5))
    # scope
    pygame.draw.rect(s, (30, 40, 30), (20, 2, 10, 3))
    pygame.draw.circle(s, glow, (49, 8), 2)
    return s

def make_flare_launcher_sprite(color, glow):
    s = pygame.Surface((48, 20), pygame.SRCALPHA)
    # barrel (wide)
    pygame.draw.rect(s, (60, 40, 30), (6, 4, 36, 12), border_radius=3)
    pygame.draw.rect(s, color, (6, 4, 36, 12), 2, border_radius=3)
    # muzzle bell
    pygame.draw.rect(s, (80, 55, 40), (40, 2, 8, 16), border_radius=4)
    pygame.draw.rect(s, glow, (40, 2, 8, 16), 1, border_radius=4)
    # grip
    pygame.draw.rect(s, (80, 50, 30), (0, 6, 8, 8))
    # flare glow
    pygame.draw.circle(s, glow, (44, 10), 4)
    pygame.draw.circle(s, (255, 200, 80), (44, 10), 2)
    return s

def make_plasma_gun_sprite(color, glow):
    s = pygame.Surface((50, 18), pygame.SRCALPHA)
    # main body
    pygame.draw.rect(s, (40, 20, 50), (4, 4, 30, 10), border_radius=3)
    pygame.draw.rect(s, color, (4, 4, 30, 10), 1, border_radius=3)
    # barrel
    pygame.draw.rect(s, (50, 25, 65), (32, 6, 18, 6))
    pygame.draw.rect(s, glow, (32, 6, 18, 6), 1)
    # grip
    pygame.draw.rect(s, (30, 15, 40), (0, 5, 6, 8))
    # energy cells (lit dots)
    for i in range(3):
        pygame.draw.circle(s, glow, (8 + i * 8, 15), 2)
    # muzzle glow
    pygame.draw.circle(s, glow, (48, 9), 4)
    pygame.draw.circle(s, (220, 100, 255), (48, 9), 2)
    return s

WEAPON_SPRITES_FN = {
    "Sword":          make_sword_sprite,
    "Crossbow":       make_crossbow_sprite,
    "Pulse Rifle":    make_pulse_rifle_sprite,
    "Flare Launcher": make_flare_launcher_sprite,
    "Plasma Gun":     make_plasma_gun_sprite,
}

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
        self._sprite = None

    def get_sprite(self):
        if self._sprite is None:
            fn = WEAPON_SPRITES_FN.get(self.name)
            if fn:
                self._sprite = fn(self.color, self.glow)
        return self._sprite

    @staticmethod
    def default_weapon():
        return Weapon("Sword", (230, 210, 130), (255, 240, 80), False, 0, 30, 0, -1)

WEAPON_TYPES = [
    Weapon("Sword",          (230, 210, 130), (255, 240,  80), False,  0, 30,  0, -1),
    Weapon("Crossbow",       (120, 190, 250), (100, 180, 255), True,  18, 20, 18, 10),
    Weapon("Pulse Rifle",    (160, 230, 170), ( 80, 255, 140), True,  26, 15, 10, 16),
    Weapon("Flare Launcher", (240, 140,  90), (255, 120,  40), True,  13, 28, 28,  6),
    Weapon("Plasma Gun",     (200, 100, 240), (210,  60, 255), True,  20, 22, 14, 12),
]

WEAPON_NAMES = [w.name for w in WEAPON_TYPES]


def weapon_index(weapon):
    return WEAPON_NAMES.index(weapon.name) if weapon.name in WEAPON_NAMES else 0


def weapon_from_index(idx):
    return Weapon.default_weapon() if idx <= 0 else WEAPON_TYPES[idx]


class Bullet:
    def __init__(self, x, y, dx, dy, speed, damage, color, glow, owner, widx=0):
        self.x, self.y = x, y
        self.dx, self.dy = dx, dy
        self.speed = speed
        self.damage = damage
        self.color = color
        self.glow = glow
        self.owner = owner
        self.widx = widx
        self.radius = 8
        self.trail = []

    def update(self):
        self.trail.append((self.x, self.y))
        if len(self.trail) > 6: self.trail.pop(0)
        self.x += self.dx * self.speed
        self.y += self.dy * self.speed

    def draw(self, surface):
        n = len(self.trail)
        for i, (tx, ty) in enumerate(self.trail):
            r = max(2, self.radius - (n - i))
            blit_center(surface, alpha_circle(self.glow, r, 180 * (i + 1) / n), tx, ty)
        add_glow(surface, self.glow, self.x, self.y, self.radius * 4, 0.9)
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surface, (255, 255, 255), (int(self.x), int(self.y)), self.radius - 3)


_pickup_ids = itertools.count(1)


class WeaponPickup:
    def __init__(self, weapon, x, y):
        self.weapon = weapon
        self.x, self.y = x, y
        self.radius = 28
        self.bob = random.uniform(0, math.pi * 2)
        self.age = 0
        self.id = next(_pickup_ids)

    def draw(self, surface):
        self.age += 1
        bob_y = math.sin(self.age * 0.05 + self.bob) * 6
        cx, cy = int(self.x), int(self.y + bob_y)
        w = self.weapon
        # shadow on the ground, shrinking as the item bobs up
        sh = ground_shadow(44, 14, 90)
        blit_center(surface, sh, self.x, self.y + self.radius + 4)
        # pulsing light
        pulse = 0.7 + 0.3 * math.sin(self.age * 0.08 + self.bob)
        add_glow(surface, w.glow, cx, cy, 58, round(pulse * 0.8, 1))
        # rotating ring
        ang = self.age * 0.04
        for k in range(3):
            a0 = ang + k * math.tau / 3
            pygame.draw.arc(surface, w.glow, (cx - 36, cy - 36, 72, 72), a0, a0 + 1.2, 3)
        # base disc
        pygame.draw.circle(surface, (16, 16, 34), (cx, cy), self.radius)
        pygame.draw.circle(surface, w.color, (cx, cy), self.radius, 3)
        spr = cached(("pickup_spr", w.name),
                     lambda: pygame.transform.smoothscale(w.get_sprite(), (44, int(44 * w.get_sprite().get_height() / w.get_sprite().get_width()))))
        blit_center(surface, spr, cx, cy)
        tag = cached(("pickup_tag", w.name), lambda: self._make_tag(w))
        blit_center(surface, tag, cx, cy - self.radius - 18)

    @staticmethod
    def _make_tag(w):
        txt = get_font(15).render(w.name, True, (245, 245, 245))
        bg = pygame.Surface((txt.get_width() + 14, txt.get_height() + 6), pygame.SRCALPHA)
        pygame.draw.rect(bg, (0, 0, 0, 170), bg.get_rect(), border_radius=6)
        pygame.draw.rect(bg, (*w.glow, 170), bg.get_rect(), 1, border_radius=6)
        bg.blit(txt, (7, 3))
        return bg

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
        self.label = ""

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
                      self.weapon.color, self.weapon.glow, self,
                      weapon_index(self.weapon))

    def pick_weapon(self, weapon):
        self.weapon = weapon
        self.ammo = -1 if weapon.ammo < 0 else weapon.ammo

    def display_ammo(self):
        return "∞" if self.ammo < 0 else str(self.ammo)

    def collides_with(self, x, y, radius):
        return math.hypot(self.x - x, self.y - y) <= self.radius + radius

    def draw(self, surface):
        x, y, r = int(self.x), int(self.y), self.radius
        hit = self.hit_timer > 0
        gc = (255, 80, 80) if hit else self.glow_color

        # dash after-images
        n = len(self.trail)
        for i, (tx, ty) in enumerate(self.trail):
            blit_center(surface, alpha_circle(self.glow_color, r, 120 * (i + 1) / max(n, 1)), tx, ty)

        # ground shadow + team ring
        blit_center(surface, ground_shadow(r * 2 + 10, r, 120), x + 5, y + r - 4)
        ring = cached(("ring", self.glow_color), lambda: self._make_ring(self.glow_color))
        blit_center(surface, ring, x, y + r - 6)

        # aura + body
        add_glow(surface, gc, x, y, r + 22, 0.55 if not hit else 0.9)
        blit_center(surface, sphere_sprite(self.color, r, hit), x, y)
        pygame.draw.circle(surface, (255, 255, 255), (x, y), r, 2)

        # weapon sprite attached to player, rotated toward facing
        # hide during sword swing (drawn separately in the swing block below)
        if not (self.is_attacking() and not self.weapon.projectile):
            spr = self.weapon.get_sprite()
            if spr:
                angle_deg = -math.degrees(math.atan2(self.facing_dy, self.facing_dx))
                rot = pygame.transform.rotate(spr, angle_deg)
                ox = self.x + self.facing_dx * (self.radius + 2)
                oy = self.y + self.facing_dy * (self.radius + 2)
                surface.blit(rot, rot.get_rect(center=(int(ox), int(oy))))

        # direction "eye"
        fx = self.x + self.facing_dx * (self.radius - 9)
        fy = self.y + self.facing_dy * (self.radius - 9)
        pygame.draw.circle(surface, (20, 20, 30), (int(fx), int(fy)), 7)
        pygame.draw.circle(surface, (255, 255, 255), (int(fx), int(fy)), 5)

        # melee weapon swing
        if self.is_attacking():
            angle = math.atan2(self.facing_dy, self.facing_dx)
            progress = 1 - (self.attack_timer / self.attack_duration)
            # swing arc: starts at -70 deg, sweeps +140 deg through the hit
            swing_offset = -1.22 + progress * 2.44
            tip_angle = angle + swing_offset
            col = self.weapon.glow if not self.weapon.projectile else (255, 255, 255)

            # crescent slash trail
            for ti in range(7):
                blur_progress = max(0.0, progress - ti * 0.06)
                blur_angle = angle - 1.22 + blur_progress * 2.44
                bx = self.x + math.cos(blur_angle) * (self.radius + 30)
                by = self.y + math.sin(blur_angle) * (self.radius + 30)
                blit_center(surface, alpha_circle(col, 13 - ti, 150 - ti * 20), bx, by)
            add_glow(surface, col, self.x + math.cos(tip_angle) * (self.radius + 34),
                     self.y + math.sin(tip_angle) * (self.radius + 34), 34, 0.6)

            if not self.weapon.projectile:
                spr = self.weapon.get_sprite()
                if spr:
                    big_spr = cached(("bigsword", self.weapon.name),
                                     lambda: pygame.transform.smoothscale(spr, (78, int(78 * spr.get_height() / spr.get_width()))))
                    rot_spr = pygame.transform.rotate(big_spr, -math.degrees(tip_angle))
                    mid_x = int(self.x + math.cos(tip_angle) * (self.radius + 24))
                    mid_y = int(self.y + math.sin(tip_angle) * (self.radius + 24))
                    surface.blit(rot_spr, rot_spr.get_rect(center=(mid_x, mid_y)))

        # health bar (directly above player)
        bw, bh = 64, 9
        bx = self.x - bw // 2
        by = self.y - self.radius - 18
        pygame.draw.rect(surface, (20, 20, 20), (bx - 1, by - 1, bw + 2, bh + 2), border_radius=5)
        hp_frac = max(0, self.health / self.max_health)
        hp_color = (int(40 + 200 * (1 - hp_frac)), int(180 * hp_frac + 40), 50)
        if bw * hp_frac > 0:
            pygame.draw.rect(surface, hp_color, (bx, by, bw * hp_frac, bh), border_radius=5)
            pygame.draw.rect(surface, shade_color(hp_color, 60), (bx + 2, by + 1, max(0, bw * hp_frac - 4), 2), border_radius=2)
        pygame.draw.rect(surface, (200, 200, 200), (bx, by, bw, bh), 1, border_radius=5)
        if self.label:
            tag = cached(("ptag", self.label, self.glow_color),
                         lambda: get_font(14).render(self.label, True, self.glow_color))
            outline = cached(("ptag_o", self.label), lambda: get_font(14).render(self.label, True, (0, 0, 0)))
            surface.blit(outline, (int(self.x) - tag.get_width() // 2 + 1, int(by) - 20 + 1))
            surface.blit(tag, (int(self.x) - tag.get_width() // 2, int(by) - 20))

    @staticmethod
    def _make_ring(color):
        s = pygame.Surface((84, 30), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (*color, 70), (0, 0, 84, 30), 0)
        pygame.draw.ellipse(s, (*color, 200), (0, 0, 84, 30), 2)
        return s


def shade_color(color, amount):
    return tuple(max(0, min(255, c + amount)) for c in color[:3])

# ─────────────────────────────────────────────
#  OBSTACLES
# ─────────────────────────────────────────────
class Obstacle:
    def __init__(self, shape, x, y, w, h=None, color=(90, 90, 90), edge=(140, 140, 160)):
        self.shape = shape; self.x, self.y = x, y; self.w = w
        self.h = h if h is not None else w; self.color = color; self.edge = edge

    @classmethod
    def rect(cls, x, y, w, h, color=(80, 80, 100), edge=(130, 130, 160)):
        return cls("rect", x, y, w, h, color, edge)

    @classmethod
    def circle(cls, x, y, r, color=(90, 90, 110), edge=(140, 140, 160)):
        return cls("circle", x, y, r, None, color, edge)

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
                px = self.x + dx / dist * md; py = self.y + dy / dist * md
        return px, py

# ─────────────────────────────────────────────
#  MAP DECORATIONS  (positions; artwork lives in map_art.py)
# ─────────────────────────────────────────────
# Build decoration layouts per map (pre-computed positions)
def _forest_decor():
    """Trees and rocks for Forest Canyon."""
    items = []
    tree_positions = [
        (120,120,1.3),(180,200,1.0),(90,350,1.1),(150,500,0.9),(110,700,1.2),(200,820,1.0),
        (1750,130,1.1),(1820,270,1.3),(1780,450,0.9),(1750,650,1.2),(1830,800,1.0),
        (350,130,1.0),(500,200,0.85),(650,120,1.1),(700,900,1.0),(900,950,1.2),
        (1100,950,0.9),(1300,920,1.1),(1500,870,0.85),(1700,900,1.0),
        (400,750,0.8),(800,130,0.9),(1100,130,1.0),(1400,150,0.85),
    ]
    rock_positions = [
        (320,440,0.9),(620,580,1.0),(800,300,0.8),(1050,480,0.9),
        (1250,700,1.0),(1450,350,0.8),(1600,600,0.9),(870,820,0.8),
    ]
    bush_positions = [
        (250,260,0.9),(420,380,0.8),(560,720,0.95),(760,220,0.75),(980,360,0.85),
        (1180,260,0.8),(1360,560,0.9),(1540,820,0.85),(660,930,0.8),(920,160,0.75),
    ]
    stump_positions = [
        (280,620,0.9),(720,640,0.8),(980,760,0.85),(1320,420,0.75),(1710,360,0.8),
    ]
    for x,y,s in tree_positions:
        items.append(('tree', x, y, s))
    for x,y,s in rock_positions:
        items.append(('rock_forest', x, y, s))
    for x,y,s in bush_positions:
        items.append(('bush_forest', x, y, s))
    for x,y,s in stump_positions:
        items.append(('stump', x, y, s))
    return items

def _quarry_decor():
    items = []
    dead_trees = [(130,150,1.1),(200,320,0.9),(150,600,1.0),(120,800,0.85),
                  (1770,180,1.0),(1820,400,1.1),(1760,700,0.9),(1830,900,0.85),
                  (550,900,0.8),(700,50,0.9),(1200,60,1.0),(1400,940,0.8)]
    rocks = [(280,300,1.2),(450,600,1.0),(680,820,0.9),(850,150,1.1),
             (1050,900,1.0),(1300,300,0.9),(1500,650,1.1),(1650,820,0.8),
             (760,480,1.3),(1150,480,1.2),(960,200,1.0),(960,880,0.9),
             (350,130,0.8),(1600,200,0.9)]
    for x,y,s in dead_trees:
        items.append(('dead_tree', x, y, s))
    for x,y,s in rocks:
        items.append(('rock_quarry', x, y, s))
    for x,y,s in [(250,240,0.8),(980,680,0.9),(1420,180,0.75),(1540,860,0.8)]:
        items.append(('stump', x, y, s))
    for x,y,s in [(420,160,0.8),(520,880,0.75),(1040,330,0.7),(1280,880,0.8)]:
        items.append(('bush_quarry', x, y, s))
    return items

def _ruins_decor():
    items = []
    columns = [(300,200,1.1),(350,300,0.9),(300,400,1.0),(250,550,0.85),
               (1600,220,1.0),(1650,340,1.1),(1620,460,0.9),(1660,570,0.85),
               (700,150,0.8),(850,200,0.9),(1000,170,0.8),(1150,200,0.9),(1300,160,0.8),
               (680,900,0.85),(960,920,1.0),(1240,900,0.85)]
    rocks = [(400,700,0.9),(500,450,0.8),(1400,650,0.9),(1500,430,0.8),
             (750,600,0.85),(1170,580,0.85)]
    debris = [(520,260,0.8),(620,760,0.75),(960,360,0.9),(1080,780,0.8),(1400,260,0.75)]
    for x,y,s in columns:
        items.append(('column', x, y, s))
    for x,y,s in rocks:
        items.append(('rock_ruins', x, y, s))
    for x,y,s in debris:
        items.append(('ruin_debris', x, y, s))
    return items

def _neon_decor():
    crystal_colors = [(0,220,200),(220,0,180),(0,200,255),(255,60,200),(60,255,200),(180,0,255)]
    positions = [(200,180),(400,150),(250,550),(180,800),(1720,200),(1600,150),
                 (1750,600),(1800,850),(700,150),(1200,150),(700,950),(1200,950),
                 (450,450),(1470,450),(450,680),(1470,680),(960,150),(960,950)]
    items = []
    for i,(x,y) in enumerate(positions):
        col = crystal_colors[i % len(crystal_colors)]
        items.append(('crystal', x, y, col))
    for x, y in [(320,320), (1560,320), (320,760), (1560,760), (960,320), (960,760)]:
        items.append(('crate_neon', x, y, 0.9))
    return items

MAP_DECOR = [_forest_decor(), _quarry_decor(), _ruins_decor(), _neon_decor()]


class Map:
    def __init__(self, name, top_color, bottom_color, accent, player_starts, obstacles, decor=None, style="forest"):
        self.name = name; self.top_color = top_color; self.bottom_color = bottom_color
        self.accent = accent; self.player_starts = player_starts; self.obstacles = obstacles
        self.decor = decor or []
        self.style = style
        self._layer = None
        self._animator = None
        self._thumb = None

    # artwork is built lazily: the headless training environment never draws
    def static_layer(self):
        if self._layer is None:
            self._layer = map_art.cached_static_layer(self, self.style)
        return self._layer

    def thumbnail(self, size):
        if self._thumb is None or self._thumb.get_size() != size:
            self._thumb = pygame.transform.smoothscale(self.static_layer(), size)
        return self._thumb

    def animator(self):
        if self._animator is None:
            self._animator = map_art.MapAnimator(self, self.style)
        return self._animator

    def draw(self, surface, tick=0):
        surface.blit(self.static_layer(), (0, 0))
        anim = self.animator()
        anim.update()
        anim.draw_under(surface, tick)

    def draw_overlay(self, surface, tick=0):
        self.animator().draw_over(surface, tick)

    def is_within_bounds(self, x, y, r):
        return r <= x <= WIDTH - r and r <= y <= HEIGHT - r

    def collides_with_obstacle(self, x, y, r):
        return any(ob.collides_with_circle(x, y, r) for ob in self.obstacles)

    def random_open_position(self):
        for _ in range(300):
            x = random.randint(120, WIDTH - 120); y = random.randint(120, HEIGHT - 120)
            if not self.collides_with_obstacle(x, y, 30): return x, y
        return WIDTH // 2, HEIGHT // 2

def create_maps():
    d = MAP_DECOR
    return [
        Map("Forest Canyon", (18, 58, 22), (38, 108, 55), (80, 200, 80),
            [(240, 540), (1680, 540)],
            [Obstacle.circle(520,340,52,(60,90,55),(100,160,80)),
             Obstacle.circle(1400,300,46,(55,85,50),(90,150,70)),
             Obstacle.circle(960,700,38,(65,95,58),(110,170,85)),
             Obstacle.rect(740,410,360,44,(70,75,65),(110,120,90)),
             Obstacle.rect(1100,610,340,44,(70,75,65),(110,120,90)),
             Obstacle.rect(200,170,200,44,(80,85,70),(120,130,95)),
             Obstacle.rect(1620,730,190,44,(80,85,70),(120,130,95)),
             Obstacle.rect(400,820,260,40,(70,75,65),(110,120,90)),
             Obstacle.rect(1200,180,240,40,(70,75,65),(110,120,90))], d[0], "forest"),
        Map("Sunset Quarry", (80,32,12),(190,100,22),(255,150,60),
            [(240,240),(1680,840)],
            [Obstacle.rect(580,130,760,64,(110,80,55),(180,130,80)),
             Obstacle.rect(220,430,300,88,(110,80,55),(180,130,80)),
             Obstacle.rect(1390,510,260,88,(110,80,55),(180,130,80)),
             Obstacle.circle(960,570,52,(130,110,90),(200,160,110)),
             Obstacle.rect(840,330,260,44,(100,72,48),(165,120,72)),
             Obstacle.rect(500,750,200,50,(110,80,55),(180,130,80)),
             Obstacle.rect(1220,760,210,50,(110,80,55),(180,130,80)),
             Obstacle.circle(340,620,36,(120,95,65),(190,145,90)),
             Obstacle.circle(1580,400,36,(120,95,65),(190,145,90))], d[1], "quarry"),
        Map("Ruins Arena", (14,18,50),(65,50,110),(160,120,255),
            [(340,540),(1580,540)],
            [Obstacle.rect(460,200,68,340,(75,75,120),(130,120,200)),
             Obstacle.rect(1392,200,68,340,(75,75,120),(130,120,200)),
             Obstacle.circle(960,250,56,(85,80,135),(140,130,210)),
             Obstacle.circle(960,830,48,(85,80,135),(140,130,210)),
             Obstacle.rect(740,690,440,54,(75,75,120),(130,120,200)),
             Obstacle.rect(840,410,220,44,(95,90,150),(155,145,225)),
             Obstacle.rect(260,700,160,44,(75,75,120),(130,120,200)),
             Obstacle.rect(1500,700,160,44,(75,75,120),(130,120,200)),
             Obstacle.circle(540,560,34,(85,80,135),(140,130,210)),
             Obstacle.circle(1380,560,34,(85,80,135),(140,130,210))], d[2], "ruins"),
        Map("Neon Void", (5,5,20),(10,8,40),(0,255,200),
            [(280,540),(1640,540)],
            [Obstacle.rect(600,200,160,160,(20,20,60),(0,220,180)),
             Obstacle.rect(1160,200,160,160,(20,20,60),(0,220,180)),
             Obstacle.rect(600,720,160,160,(20,20,60),(220,0,180)),
             Obstacle.rect(1160,720,160,160,(20,20,60),(220,0,180)),
             Obstacle.circle(960,540,60,(15,15,50),(0,200,255)),
             Obstacle.rect(820,450,280,40,(20,20,60),(180,0,255)),
             Obstacle.circle(400,350,40,(20,20,60),(255,60,200)),
             Obstacle.circle(1520,350,40,(20,20,60),(255,60,200)),
             Obstacle.circle(400,730,40,(20,20,60),(60,255,200)),
             Obstacle.circle(1520,730,40,(20,20,60),(60,255,200))], d[3], "neon"),
    ]

MAP_NAMES = ["Forest Canyon", "Sunset Quarry", "Ruins Arena", "Neon Void"]
MAP_DESCRIPTIONS = [
    "Lush canyon with stone pillars and tree clusters.",
    "Blazing quarry with high walls and rock formations.",
    "Ancient ruins with columns and mystical arches.",
    "Cyberpunk void with glowing geometric obstacles.",
]

_shared_maps = None


def shared_maps():
    """Maps are static data + lazily built art, so every Arena can share them."""
    global _shared_maps
    if _shared_maps is None:
        _shared_maps = create_maps()
    return _shared_maps

# ─────────────────────────────────────────────
#  ARENA
# ─────────────────────────────────────────────
class Arena:
    def __init__(self, player1, player2, map_index=0):
        self.player1 = player1; self.player2 = player2
        self.all_maps = shared_maps(); self.map_index = map_index
        self.map = self.all_maps[map_index]; self.weapon_pickups = []
        self.spawn_timer = WEAPON_RESPAWN_INTERVAL // 2
        self._place_players()

    def _place_players(self):
        self.player1.x, self.player1.y = self.map.player_starts[0]
        self.player2.x, self.player2.y = self.map.player_starts[1]

    def switch_map(self, index):
        self.map_index = index; self.map = self.all_maps[index]
        self.weapon_pickups.clear(); self.spawn_timer = WEAPON_RESPAWN_INTERVAL // 2
        self._place_players()

    def update(self):
        self.spawn_timer -= 1
        if self.spawn_timer <= 0 and len(self.weapon_pickups) < MAX_WEAPON_PICKUPS:
            self._spawn_pickup(); self.spawn_timer = WEAPON_RESPAWN_INTERVAL

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

    def draw(self, surface, tick=0):
        self.map.draw(surface, tick)
        for pickup in self.weapon_pickups: pickup.draw(surface)

def resolve_player_collision(p1, p2):
    dx, dy = p2.x - p1.x, p2.y - p1.y
    dist = math.hypot(dx, dy) or 0.01
    md = p1.radius + p2.radius
    if dist < md:
        overlap = (md - dist) * 0.52
        px, py = dx / dist * overlap, dy / dist * overlap
        p1.x -= px; p1.y -= py; p2.x += px; p2.y += py



# ─────────────────────────────────────────────
#  HUD & UI HELPERS
# ─────────────────────────────────────────────
def draw_text_shadow(surface, text, font, color, pos, shadow=(2, 2)):
    s = font.render(text, True, (0, 0, 0))
    surface.blit(s, (pos[0] + shadow[0], pos[1] + shadow[1]))
    surface.blit(font.render(text, True, color), pos)


def draw_text_center(surface, text, font, color, center, shadow=2):
    img = font.render(text, True, color)
    r = img.get_rect(center=center)
    if shadow:
        surface.blit(font.render(text, True, (0, 0, 0)), (r.x + shadow, r.y + shadow))
    surface.blit(img, r)
    return r


def draw_panel(surface, rect, bg=(20, 20, 40), alpha=200, radius=16, border=(100, 100, 160)):
    def build():
        s = pygame.Surface((rect.width + 18, rect.height + 18), pygame.SRCALPHA)
        pygame.draw.rect(s, (0, 0, 0, 70), (12, 14, rect.width, rect.height), border_radius=radius + 2)
        pygame.draw.rect(s, (*bg, alpha), (4, 4, rect.width, rect.height), border_radius=radius)
        hi = pygame.Surface((rect.width, rect.height // 2), pygame.SRCALPHA)
        pygame.draw.rect(hi, (255, 255, 255, 14), hi.get_rect(), border_top_left_radius=radius, border_top_right_radius=radius)
        s.blit(hi, (4, 4))
        pygame.draw.rect(s, (*border, 190), (4, 4, rect.width, rect.height), 2, border_radius=radius)
        return s
    surface.blit(cached(("panel", rect.size, bg, alpha, radius, border), build), (rect.x - 4, rect.y - 4))


def draw_hud_bar(surface, x, y, w, h, frac, fill_color, bg=(20,20,20), border=(160,160,160), radius=5):
    pygame.draw.rect(surface, bg, (x, y, w, h), border_radius=radius)
    if frac > 0:
        fw = max(radius * 2, int(w * frac))
        pygame.draw.rect(surface, fill_color, (x, y, fw, h), border_radius=radius)
        pygame.draw.rect(surface, shade_color(fill_color, 55), (x + 3, y + 2, max(0, fw - 6), max(1, h // 4)), border_radius=radius)
    pygame.draw.rect(surface, border, (x, y, w, h), 1, border_radius=radius)


class Button:
    def __init__(self, text, x, y, w, h, base=(30,30,55), accent=(140,120,255)):
        self.text = text; self.rect = pygame.Rect(x, y, w, h)
        self.base = base; self.accent = accent

    def hovered(self):
        return self.rect.collidepoint(mouse_pos())

    def draw(self, surface, font, override_accent=None, selected=False):
        ac = override_accent or self.accent
        hovered = self.hovered()
        col = tuple(min(255, c + 28) for c in self.base) if (hovered or selected) else self.base
        shadow = self.rect.inflate(12, 12)
        gs = pygame.Surface((shadow.width, shadow.height), pygame.SRCALPHA)
        pygame.draw.rect(gs, (0, 0, 0, 70), (4, 6, shadow.width - 8, shadow.height - 8), border_radius=22)
        surface.blit(gs, shadow.topleft)
        if hovered or selected:
            glow = self.rect.inflate(14, 14)
            gs = pygame.Surface((glow.width, glow.height), pygame.SRCALPHA)
            pygame.draw.rect(gs, (*ac, 110 if selected else 70), (0, 0, glow.width, glow.height), border_radius=22)
            surface.blit(gs, glow.topleft)
        pygame.draw.rect(surface, col, self.rect, border_radius=22)
        hi = pygame.Rect(self.rect.x + 6, self.rect.y + 4, self.rect.width - 12, self.rect.height // 2 - 4)
        hs = pygame.Surface(hi.size, pygame.SRCALPHA)
        pygame.draw.rect(hs, (255, 255, 255, 18), hs.get_rect(), border_radius=16)
        surface.blit(hs, hi.topleft)
        pygame.draw.rect(surface, ac, self.rect, 3 if selected else 2, border_radius=22)
        label = font.render(self.text, True, (245, 245, 255))
        surface.blit(label, label.get_rect(center=self.rect.center))

    def clicked(self, event):
        return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos)


class TextField:
    def __init__(self, label, x, y, w, h, text="", placeholder="", max_len=60):
        self.label = label; self.rect = pygame.Rect(x, y, w, h)
        self.text = text; self.placeholder = placeholder
        self.max_len = max_len; self.focused = False

    def handle(self, event):
        """Returns True when Enter is pressed inside the field."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.focused = self.rect.collidepoint(event.pos)
        elif self.focused and event.type == pygame.TEXTINPUT:
            self.text = (self.text + event.text)[:self.max_len]
        elif self.focused and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return True
            elif event.key == pygame.K_v and event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META):
                try:
                    pasted = pygame.scrap.get_text() if hasattr(pygame.scrap, "get_text") else ""
                    self.text = (self.text + (pasted or "").strip())[:self.max_len]
                except Exception:
                    pass
        return False

    def draw(self, surface, tick):
        draw_text_shadow(surface, self.label, get_font(18), (180, 180, 220), (self.rect.x + 4, self.rect.y - 28))
        pygame.draw.rect(surface, (12, 12, 28), self.rect, border_radius=12)
        pygame.draw.rect(surface, (150, 130, 255) if self.focused else (80, 80, 120), self.rect, 2, border_radius=12)
        font = get_font(26, bold=False)
        if self.text:
            img = font.render(self.text, True, (240, 240, 255))
        else:
            img = font.render(self.placeholder, True, (110, 110, 140))
        surface.blit(img, (self.rect.x + 16, self.rect.centery - img.get_height() // 2))
        if self.focused and (tick // 30) % 2 == 0:
            cx = self.rect.x + 18 + (img.get_width() if self.text else 0)
            pygame.draw.line(surface, (220, 220, 255), (cx, self.rect.y + 12), (cx, self.rect.bottom - 12), 2)


def banner_text(text, size, color, glow=None):
    """Big outlined + glowing title text (cached)."""
    def build():
        font = get_font(size)
        main = font.render(text, True, color)
        w, h = main.get_width() + 40, main.get_height() + 40
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        dark = font.render(text, True, (10, 10, 20))
        for dx, dy in ((-4, 0), (4, 0), (0, -4), (0, 4), (-3, -3), (3, 3), (-3, 3), (3, -3), (5, 6)):
            s.blit(dark, (20 + dx, 20 + dy))
        if glow:
            g = pygame.Surface((w, h), pygame.SRCALPHA)
            g.blit(font.render(text, True, glow), (20, 20))
            g = map_art.blur_surface(g, 6)
            for _ in range(2):
                s.blit(g, (0, 0))
        s.blit(main, (20, 20))
        return s
    return cached(("banner", text, size, color, glow), build)


# ─────────────────────────────────────────────
#  PARTICLES & EFFECTS
# ─────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, color, speed=(2, 7), life=(15, 35), size=(3, 7), gravity=0.2):
        self.x, self.y = x, y; self.color = color
        angle = random.uniform(0, math.pi * 2); spd = random.uniform(*speed)
        self.vx = math.cos(angle) * spd; self.vy = math.sin(angle) * spd
        self.life = random.randint(*life); self.max_life = self.life
        self.r = random.randint(*size)
        self.gravity = gravity

    def update(self):
        self.x += self.vx; self.y += self.vy
        self.vy += self.gravity; self.vx *= 0.95; self.vy *= 0.95; self.life -= 1

    def draw(self, surface):
        f = self.life / self.max_life
        blit_center(surface, alpha_circle(self.color, max(1, self.r * (0.4 + 0.6 * f)), 255 * f), self.x, self.y)


class FloatingText:
    def __init__(self, text, x, y, color, size=26, life=55):
        self.text, self.x, self.y, self.color, self.size = text, x, y, color, size
        self.life = self.max_life = life
        self.vx = random.uniform(-0.6, 0.6)

    def update(self):
        self.y -= 1.3 * (self.life / self.max_life) + 0.2
        self.x += self.vx
        self.life -= 1

    def draw(self, surface):
        img = banner_text(self.text, self.size, self.color)
        a = int(255 * min(1.0, self.life / (self.max_life * 0.4)))
        img.set_alpha(a)
        blit_center(surface, img, self.x, self.y)
        img.set_alpha(255)


class Shockwave:
    def __init__(self, x, y, color, max_r=90, life=18, width=6):
        self.x, self.y, self.color = x, y, color
        self.max_r, self.life, self.max_life, self.width = max_r, life, life, width

    def update(self):
        self.life -= 1

    def draw(self, surface):
        t = 1 - self.life / self.max_life
        r = int(10 + (self.max_r - 10) * (1 - (1 - t) ** 2))
        w = max(1, int(self.width * (1 - t)))
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), r, w)


# ─────────────────────────────────────────────
#  INPUT
# ─────────────────────────────────────────────
PlayerInput = namedtuple("PlayerInput", "dx dy sprint dash melee shoot")
NO_INPUT = PlayerInput(0, 0, False, False, False, False)

SCHEME_P1 = dict(left=[pygame.K_a], right=[pygame.K_d], up=[pygame.K_w], down=[pygame.K_s],
                 sprint=[pygame.K_LSHIFT], dash=[pygame.K_q], melee=[pygame.K_f], shoot=[pygame.K_e])
SCHEME_P2 = dict(left=[pygame.K_LEFT], right=[pygame.K_RIGHT], up=[pygame.K_UP], down=[pygame.K_DOWN],
                 sprint=[pygame.K_RSHIFT], dash=[pygame.K_SLASH, pygame.K_QUESTION],
                 melee=[pygame.K_RCTRL], shoot=[pygame.K_PERIOD])
# one human on the keyboard (vs AI / online): both layouts work, plus Space and the mouse
SCHEME_SOLO = {k: SCHEME_P1[k] + SCHEME_P2[k] for k in SCHEME_P1}
SCHEME_SOLO["dash"] = SCHEME_SOLO["dash"] + [pygame.K_SPACE]
SCHEME_SOLO["melee"] = SCHEME_SOLO["melee"] + [pygame.K_j]
SCHEME_SOLO["shoot"] = SCHEME_SOLO["shoot"] + [pygame.K_k]


def read_input(keys, scheme, mouse=False):
    on = lambda name: any(keys[k] for k in scheme[name])
    melee, shoot = on("melee"), on("shoot")
    if mouse:
        left, _middle, right = pygame.mouse.get_pressed()
        melee, shoot = melee or left, shoot or right
    return PlayerInput(on("right") - on("left"), on("down") - on("up"), on("sprint"), on("dash"), melee, shoot)


def input_from_tuple(t):
    return PlayerInput(*t)


# ─────────────────────────────────────────────
#  MATCH  (rounds + the simulation step shared by every mode)
# ─────────────────────────────────────────────
ROUNDS_TO_WIN = 2
MAX_ROUNDS = 5
ROUND_FRAMES = 90 * FPS
COUNTDOWN_FRAMES = 150
KO_FRAMES = 170
HITSTOP_FRAMES = 4


def make_players():
    p1 = Player(0, 0, (100, 180, 240), (80, 160, 255))
    p2 = Player(0, 0, (240, 140, 100), (255, 120, 60))
    return p1, p2


class Match:
    """
    Owns one best-of-3 match.  step() runs exactly the same per-frame game
    logic as the original game loop, and records what happened in
    self.events so the renderer (local or on a network client) can play
    particles and sounds.
    """

    def __init__(self, map_index, labels=("P1", "P2")):
        self.labels = labels
        self.p1, self.p2 = make_players()
        self.arena = Arena(self.p1, self.p2, map_index)
        self.score = [0, 0]
        self.round = 1
        self.match_winner = 0
        self.events = []
        self.stats = [dict(dmg=0, hits=0, shots=0, pickups=0) for _ in range(2)]
        self._start_round()

    def _start_round(self):
        self.p1, self.p2 = make_players()
        self.p1.label, self.p2.label = self.labels
        self.arena.player1, self.arena.player2 = self.p1, self.p2
        self.arena.switch_map(self.arena.map_index)
        self.bullets = []
        self.round_timer = ROUND_FRAMES
        self.phase = "countdown"
        self.phase_timer = COUNTDOWN_FRAMES
        self.round_winner = 0
        self.ko_reason = ""
        self.freeze = 0
        self.fight_frames = 0

    def players(self):
        return self.p1, self.p2

    # ── per-frame update ───────────────────────────────────────
    def step(self, in1, in2):
        self.events = []
        if self.phase == "countdown":
            if self.phase_timer % 50 == 0:
                self.events.append(["count", self.phase_timer // 50])
            self.phase_timer -= 1
            if self.phase_timer <= 0:
                self.phase = "fight"
                self.events.append(["fight"])
        elif self.phase == "fight":
            self.fight_frames += 1
            if self.freeze > 0:
                self.freeze -= 1
                return
            self._simulate(in1, in2)
            self.round_timer -= 1
            self._check_round_end()
        elif self.phase == "ko":
            self.phase_timer -= 1
            for pl in (self.p1, self.p2):
                pl.update()
            if self.phase_timer <= 0:
                if self.match_winner:
                    self.phase = "over"
                    self.events.append(["over", self.match_winner])
                else:
                    self.round += 1
                    self._start_round()

    def _simulate(self, in1, in2):
        arena, p1, p2 = self.arena, self.p1, self.p2
        ev = self.events
        arena.update()
        for idx, (pl, inp) in enumerate(((p1, in1), (p2, in2)), start=1):
            if inp.dash:
                was = pl.dash_timer
                pl.start_dash(inp.dx, inp.dy)
                if pl.dash_timer > 0 and was == 0:
                    ev.append(["dash", idx])
            if inp.melee:
                was = pl.attack_timer
                pl.start_attack(inp.dx, inp.dy)
                if pl.attack_timer > 0 and was == 0:
                    ev.append(["swing", idx])
            if inp.shoot:
                b = pl.start_shoot()
                if b:
                    self.bullets.append(b)
                    self.stats[idx - 1]["shots"] += 1
                    ev.append(["shoot", round(b.x), round(b.y), b.widx])
            pl.move(inp.dx, inp.dy, bool(inp.sprint), arena)

        p1.update(); p2.update()
        arena.resolve_obstacle_collision(p1)
        arena.resolve_obstacle_collision(p2)
        resolve_player_collision(p1, p2)

        for a_idx, (attacker, defender) in enumerate(((p1, p2), (p2, p1)), start=1):
            if attacker.attack_active() and not attacker.attack_hit_registered:
                ax = attacker.x + attacker.facing_dx * attacker.attack_range
                ay = attacker.y + attacker.facing_dy * attacker.attack_range
                if defender.collides_with(ax, ay, 20):
                    defender.take_hit(attacker.attack_damage)
                    attacker.attack_hit_registered = True
                    self._record_hit(a_idx, attacker.attack_damage)
                    ev.append(["hit", round(defender.x), round(defender.y), attacker.attack_damage, 3 - a_idx, 1])
                    self.freeze = HITSTOP_FRAMES

        for pickup in arena.weapon_pickups[:]:
            for idx, pl in ((1, p1), (2, p2)):
                if pickup.check_pickup(pl):
                    pl.pick_weapon(pickup.weapon)
                    arena.weapon_pickups.remove(pickup)
                    self.stats[idx - 1]["pickups"] += 1
                    ev.append(["pickup", round(pickup.x), round(pickup.y), weapon_index(pickup.weapon), idx])
                    break

        for bullet in self.bullets[:]:
            bullet.update(); hit = False
            if not arena.map.is_within_bounds(bullet.x, bullet.y, bullet.radius):
                hit = True
            elif arena.map.collides_with_obstacle(bullet.x, bullet.y, bullet.radius):
                ev.append(["impact", round(bullet.x), round(bullet.y), bullet.widx]); hit = True
            else:
                for idx, pl in ((1, p1), (2, p2)):
                    if bullet.owner is not pl and pl.collides_with(bullet.x, bullet.y, bullet.radius):
                        pl.take_hit(bullet.damage)
                        self._record_hit(3 - idx, bullet.damage)
                        ev.append(["hit", round(pl.x), round(pl.y), bullet.damage, idx, 0])
                        hit = True
                        break
            if hit: self.bullets.remove(bullet)

    def _record_hit(self, attacker_idx, dmg):
        st = self.stats[attacker_idx - 1]
        st["dmg"] += dmg
        st["hits"] += 1

    def _check_round_end(self):
        d1, d2 = self.p1.is_dead(), self.p2.is_dead()
        if not (d1 or d2 or self.round_timer <= 0):
            return
        if d1 and d2:
            w = 3
        elif d1 or d2:
            w = 2 if d1 else 1
        else:
            h1, h2 = self.p1.health, self.p2.health
            w = 1 if h1 > h2 else 2 if h2 > h1 else 3
        self.ko_reason = "ko" if (d1 or d2) else "time"
        self.round_winner = w
        if w in (1, 2):
            self.score[w - 1] += 1
        if max(self.score) >= ROUNDS_TO_WIN:
            self.match_winner = 1 if self.score[0] > self.score[1] else 2
        elif self.round >= MAX_ROUNDS:
            self.match_winner = 1 if self.score[0] > self.score[1] else 2 if self.score[1] > self.score[0] else 3
        loser = self.p2 if w == 1 else self.p1
        self.events.append(["ko", w, self.ko_reason, round(loser.x), round(loser.y)])
        self.phase = "ko"
        self.phase_timer = KO_FRAMES
        self.bullets = []

    # ── network snapshot (host → client) ───────────────────────
    def snapshot(self):
        def pack(p):
            return [round(p.x, 1), round(p.y, 1), round(p.facing_dx, 3), round(p.facing_dy, 3),
                    p.health, round(p.stamina, 1), p.hit_timer, p.attack_timer, p.dash_timer,
                    weapon_index(p.weapon), p.ammo, p.cooldown_timer]
        return {
            "t": "s", "ph": self.phase, "pt": self.phase_timer, "rt": self.round_timer,
            "ff": self.fight_frames, "sc": self.score, "r": self.round, "rw": self.round_winner,
            "mw": self.match_winner, "kr": self.ko_reason, "m": self.arena.map_index,
            "p": [pack(self.p1), pack(self.p2)],
            "b": [[round(b.x, 1), round(b.y, 1), round(b.dx, 3), round(b.dy, 3), b.speed, b.widx,
                   1 if b.owner is self.p1 else 2] for b in self.bullets],
            "w": [[w.id, w.x, w.y, weapon_index(w.weapon), round(w.bob, 2)] for w in self.arena.weapon_pickups],
            "st": self.stats if self.phase == "over" else None,
            "ev": self.events,
        }

    def apply_snapshot(self, snap):
        if snap["m"] != self.arena.map_index:
            self.arena.switch_map(snap["m"])
        if snap["r"] != self.round or (snap["ph"] == "countdown" and self.phase not in ("countdown",)):
            self._start_round()
        self.phase, self.phase_timer = snap["ph"], snap["pt"]
        self.round_timer, self.fight_frames = snap["rt"], snap["ff"]
        self.score, self.round = snap["sc"], snap["r"]
        self.round_winner, self.match_winner, self.ko_reason = snap["rw"], snap["mw"], snap["kr"]
        if snap.get("st"):
            self.stats = snap["st"]
        for p, d in zip((self.p1, self.p2), snap["p"]):
            ox, oy = p.x, p.y
            (p.x, p.y, p.facing_dx, p.facing_dy, p.health, p.stamina,
             p.hit_timer, p.attack_timer, p.dash_timer, widx, p.ammo, p.cooldown_timer) = d
            if p.dash_timer > 0:
                p.trail.append((ox, oy))
                p.trail = p.trail[-8:]
            else:
                p.trail = []
            if weapon_index(p.weapon) != widx:
                p.weapon = weapon_from_index(widx)
        self.bullets = []
        for x, y, dx, dy, speed, widx, owner in snap["b"]:
            w = weapon_from_index(widx)
            b = Bullet(x, y, dx, dy, speed, w.damage, w.color, w.glow, self.p1 if owner == 1 else self.p2, widx)
            b.trail = [(x - dx * speed * k, y - dy * speed * k) for k in range(6, 0, -1)]
            self.bullets.append(b)
        old = {w.id: w for w in self.arena.weapon_pickups}
        pickups = []
        for pid, x, y, widx, bob in snap["w"]:
            pk = old.get(pid)
            if pk is None:
                pk = WeaponPickup(weapon_from_index(widx), x, y)
                pk.id, pk.bob = pid, bob
            pickups.append(pk)
        self.arena.weapon_pickups = pickups


# ─────────────────────────────────────────────
#  DRAW IN-GAME HUD
# ─────────────────────────────────────────────
def _player_panel(screen, rect, p, title, title_color, bg, border, right_aligned):
    PAD = 18
    PW = rect.width
    draw_panel(screen, rect, bg, 215, 14, border)
    dot_x = rect.right - 22 if right_aligned else rect.x + 22
    pygame.draw.circle(screen, p.color, (dot_x, rect.y + 24), 10)
    pygame.draw.circle(screen, p.glow_color, (dot_x, rect.y + 24), 10, 2)
    label = get_font(22).render(title, True, title_color)
    lx = rect.right - 38 - label.get_width() if right_aligned else rect.x + 38
    screen.blit(get_font(22).render(title, True, (0, 0, 0)), (lx + 2, rect.y + 12))
    screen.blit(label, (lx, rect.y + 10))
    tiny = get_font(16, bold=False)
    small = get_font(21, bold=False)
    draw_text_shadow(screen, "HP", tiny, (170, 230, 170), (rect.x + PAD, rect.y + 50))
    hp = max(0, p.health / p.max_health)
    hp_col = (int(40 + 200 * (1 - hp)), int(180 * hp + 40), 50)
    draw_hud_bar(screen, rect.x + 48, rect.y + 52, PW - 66, 16, hp, hp_col, border=(90, 140, 90))
    hp_txt = tiny.render(f"{int(p.health)}/{p.max_health}", True, (230, 245, 230))
    screen.blit(hp_txt, (rect.x + 48 + (PW - 66) - hp_txt.get_width() - 8, rect.y + 52))
    draw_text_shadow(screen, "SP", tiny, (120, 190, 240), (rect.x + PAD, rect.y + 76))
    draw_hud_bar(screen, rect.x + 48, rect.y + 79, PW - 66, 9, p.stamina / p.max_stamina,
                 (70, 180, 235), border=(60, 120, 170))
    # dash readiness
    dash_frac = 1 - p.cooldown_timer / p.dash_cooldown
    draw_text_shadow(screen, "DASH", tiny, (200, 200, 230), (rect.x + PAD, rect.y + 96))
    draw_hud_bar(screen, rect.x + 70, rect.y + 99, 90, 7, dash_frac,
                 (255, 230, 120) if dash_frac >= 1 else (150, 140, 110), border=(110, 110, 130), radius=3)
    spr = p.weapon.get_sprite()
    wy = rect.y + 116
    if spr:
        spr_s = cached(("hudspr", p.weapon.name), lambda: pygame.transform.smoothscale(spr, (40, int(40 * spr.get_height() / spr.get_width()))))
        screen.blit(spr_s, (rect.x + PAD, wy + 8))
    draw_text_shadow(screen, p.weapon.name, small, p.weapon.color, (rect.x + 66, wy + 2))
    if p.weapon.projectile:
        ammo_col = (255, 200, 80) if p.ammo >= 0 and p.ammo <= 3 else (210, 210, 210)
        draw_text_shadow(screen, f"Ammo: {p.display_ammo()}", small, ammo_col, (rect.x + 66, wy + 22))


def draw_game_hud(screen, match, titles, hint, tick):
    PAD, PW, PH = 18, 320, 168
    p1, p2 = match.p1, match.p2
    _player_panel(screen, pygame.Rect(PAD, PAD, PW, PH), p1, titles[0], (130, 205, 255),
                  (8, 16, 30), (80, 140, 200), False)
    _player_panel(screen, pygame.Rect(WIDTH - PAD - PW, PAD, PW, PH), p2, titles[1], (255, 180, 110),
                  (30, 14, 8), (200, 130, 80), True)

    # ── scoreboard / timer — top-center ──
    cw, ch = 280, 96
    cr = pygame.Rect(WIDTH // 2 - cw // 2, PAD, cw, ch)
    draw_panel(screen, cr, (10, 10, 24), 215, 16, (110, 100, 180))
    draw_text_center(screen, f"ROUND {match.round}", get_font(16), (190, 180, 240), (cr.centerx, cr.y + 18))
    secs = max(0, math.ceil(match.round_timer / FPS))
    tcol = (255, 90, 90) if secs <= 10 and match.phase == "fight" and tick % 30 < 18 else (245, 245, 255)
    draw_text_center(screen, f"{secs}", get_font(40), tcol, (cr.centerx, cr.y + 56))
    for side, (p, sc) in enumerate(((p1, match.score[0]), (p2, match.score[1]))):
        for i in range(ROUNDS_TO_WIN):
            x = cr.x + 36 + i * 30 if side == 0 else cr.right - 36 - i * 30
            filled = i < sc
            if filled:
                add_glow(screen, p.glow_color, x, cr.y + 56, 22, 0.8)
            pygame.draw.circle(screen, p.glow_color if filled else (40, 40, 60), (x, cr.y + 56), 9)
            pygame.draw.circle(screen, (230, 230, 255), (x, cr.y + 56), 9, 2)
    draw_text_center(screen, match.arena.map.name, get_font(18, bold=False), (210, 210, 245), (cr.centerx, cr.bottom + 18))

    # ── controls reminder — bottom-center ──
    hint_img = get_font(18, bold=False).render(hint, True, (170, 170, 210))
    bw = hint_img.get_width() + 48
    bottom_r = pygame.Rect(WIDTH // 2 - bw // 2, HEIGHT - 50, bw, 36)
    draw_panel(screen, bottom_r, (6, 6, 18), 170, 10, (50, 50, 90))
    screen.blit(hint_img, hint_img.get_rect(center=bottom_r.center))


def draw_banners(screen, match, titles):
    cx, cy = WIDTH // 2, HEIGHT // 2 - 40
    if match.phase == "countdown":
        n = max(1, math.ceil(match.phase_timer / 50))
        t = 1 - (match.phase_timer - (n - 1) * 50) / 50
        final = match.score[0] == ROUNDS_TO_WIN - 1 and match.score[1] == ROUNDS_TO_WIN - 1
        head = banner_text("FINAL ROUND" if final else f"ROUND {match.round}", 54, (255, 230, 150), (255, 160, 40))
        blit_center(screen, head, cx, cy - 120)
        img = banner_text(str(n), 150, (255, 255, 255), (140, 120, 255))
        scale = 1.5 - 0.5 * min(1.0, t * 5)
        img = pygame.transform.rotozoom(img, 0, scale)
        img.set_alpha(int(255 * min(1.0, (1 - t) * 3)))
        blit_center(screen, img, cx, cy + 20)
    elif match.phase == "fight" and match.fight_frames < 55:
        t = match.fight_frames / 55
        img = banner_text("FIGHT!", 140, (255, 240, 200), (255, 90, 40))
        img = pygame.transform.rotozoom(img, 0, 0.8 + 0.4 * min(1.0, t * 4))
        img.set_alpha(int(255 * (1 - t ** 3)))
        blit_center(screen, img, cx, cy)
    elif match.phase == "ko":
        elapsed = KO_FRAMES - match.phase_timer
        if match.ko_reason == "time":
            word = "TIME!"
        else:
            word = "DOUBLE K.O." if match.round_winner == 3 else "K.O.!"
        img = banner_text(word, 150, (255, 250, 240), (255, 40, 40))
        scale = max(1.0, 2.2 - elapsed * 0.08)
        blit_center(screen, pygame.transform.rotozoom(img, 0, scale), cx, cy)
        if elapsed > 45:
            if match.round_winner in (1, 2):
                who = titles[match.round_winner - 1]
                col = (130, 205, 255) if match.round_winner == 1 else (255, 180, 110)
                sub = banner_text(f"{who} takes the round", 44, col)
            else:
                sub = banner_text("Draw round", 44, (230, 230, 230))
            blit_center(screen, sub, cx, cy + 110)


# ─────────────────────────────────────────────
#  SETTINGS FILE
# ─────────────────────────────────────────────
DEFAULT_SETTINGS = dict(map=0, mode="ai", difficulty="Medium", relay="", address="", muted=False)


def load_settings():
    data = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            data.update({k: v for k, v in json.load(f).items() if k in DEFAULT_SETTINGS})
    except (OSError, ValueError):
        pass
    return data


def save_settings(data):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


# ─────────────────────────────────────────────
#  WINDOW
# ─────────────────────────────────────────────
class Display:
    """
    The game always draws on a 1920×1080 canvas.  The window can be any size
    (laptops, 4K, fullscreen): the canvas is scaled to fit, letterboxed, and
    mouse positions are mapped back.  At exactly 1920×1080 the canvas *is* the
    window, so there is no scaling cost at all.
    """

    def __init__(self, fullscreen=False):
        self.fullscreen = fullscreen
        self.windowed_size = self._fit_window()
        self.fast = False                    # nearest-neighbour scaling on slow machines
        self.slow_frames = 0
        self._canvas_surf = None
        self._open()

    @staticmethod
    def _fit_window():
        try:
            dw, dh = pygame.display.get_desktop_sizes()[0]
        except (pygame.error, IndexError, AttributeError):
            return WIDTH, HEIGHT
        if dw >= WIDTH and dh >= HEIGHT + 60:
            return WIDTH, HEIGHT
        scale = min(dw * 0.94 / WIDTH, dh * 0.86 / HEIGHT)
        return int(WIDTH * scale), int(HEIGHT * scale)

    def _open(self):
        if self.fullscreen:
            pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self.layout()

    def layout(self):
        win = pygame.display.get_surface()
        ww, wh = win.get_size()
        if ww < 16 or wh < 16:          # minimised: keep the previous layout
            return
        if (ww, wh) == (WIDTH, HEIGHT):
            self.direct = True
            self.canvas = win
            self.rect = win.get_rect()
            return
        self.direct = False
        if self._canvas_surf is None:
            self._canvas_surf = pygame.Surface((WIDTH, HEIGHT)).convert()
        self.canvas = self._canvas_surf
        scale = min(ww / WIDTH, wh / HEIGHT)
        self.rect = pygame.Rect(0, 0, max(1, int(WIDTH * scale)), max(1, int(HEIGHT * scale)))
        self.rect.center = (ww // 2, wh // 2)
        self._scaled = pygame.Surface(self.rect.size).convert()
        win.fill((0, 0, 0))
        if not self.fullscreen:
            self.windowed_size = (ww, wh)

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self._open()

    def present(self, frame_ms):
        if not self.direct:
            if frame_ms > 15 and not self.fast:
                self.slow_frames += 1
                self.fast = self.slow_frames > 90      # sustained slowness → cheaper scaling
            win = pygame.display.get_surface()
            scale = pygame.transform.scale if self.fast else pygame.transform.smoothscale
            if self.rect.topleft == (0, 0) and self.rect.size == win.get_size():
                scale(self.canvas, self.rect.size, win)
            else:
                scale(self.canvas, self.rect.size, self._scaled)
                win.blit(self._scaled, self.rect.topleft)
        pygame.display.flip()

    def to_canvas(self, pos):
        if self.direct:
            return pos
        x = (pos[0] - self.rect.x) * WIDTH / self.rect.width
        y = (pos[1] - self.rect.y) * HEIGHT / self.rect.height
        return int(x), int(y)


_display = None


def mouse_pos():
    """Mouse position in canvas (1920×1080) coordinates."""
    pos = pygame.mouse.get_pos()
    return _display.to_canvas(pos) if _display else pos


def make_icon():
    s = pygame.Surface((32, 32), pygame.SRCALPHA)
    pygame.draw.circle(s, (40, 30, 80), (16, 16), 15)
    pygame.draw.circle(s, (180, 140, 255), (16, 16), 15, 2)
    pygame.draw.line(s, (235, 235, 255), (9, 23), (23, 9), 4)
    pygame.draw.line(s, (255, 220, 90), (8, 17), (15, 24), 3)
    return s


# ─────────────────────────────────────────────
#  APP
# ─────────────────────────────────────────────
MODES = [("ai", "VS AI"), ("local", "LOCAL 2P"), ("aivai", "AI VS AI"), ("online", "ONLINE")]
MODE_BLURBS = {
    "ai": "You against the trained neural-network AI.",
    "local": "Two players, one keyboard.",
    "aivai": "Sit back and watch two AIs fight it out.",
    "online": "Play a friend over LAN or the internet.",
}
DIFF_COLORS = {"Easy": (90, 220, 120), "Medium": (255, 200, 80), "Hard": (255, 80, 80)}


class Session:
    """Everything about the match currently being played."""

    def __init__(self, mode, map_index, difficulty="Medium", peer=None):
        self.mode = mode
        self.difficulty = difficulty
        self.peer = peer
        self.last_seq = -1
        self.leave_prompt = False
        self.map_index = map_index
        if mode == "local":
            self.labels, self.titles = ("P1", "P2"), ("PLAYER 1", "PLAYER 2")
        elif mode == "ai":
            self.labels, self.titles = ("YOU", f"AI {difficulty.upper()}"), ("YOU", f"AI · {difficulty.upper()}")
        elif mode == "aivai":
            self.labels, self.titles = ("BLUE AI", "ORANGE AI"), (f"BLUE AI · {difficulty.upper()}", f"ORANGE AI · {difficulty.upper()}")
        elif mode == "host":
            self.labels, self.titles = ("YOU", "RIVAL"), ("YOU", "RIVAL")
        else:  # client
            self.labels, self.titles = ("RIVAL", "YOU"), ("RIVAL", "YOU")
        self.new_match()

    def new_match(self):
        self.match = Match(self.map_index, self.labels)
        self.ai = [None, None]
        if self.mode == "ai":
            self.ai[1] = AIController(self.difficulty)
        elif self.mode == "aivai":
            self.ai = [AIController(self.difficulty), AIController(self.difficulty)]

    def local_side(self):
        return {"ai": 1, "host": 1, "client": 2}.get(self.mode, 0)

    def hint(self):
        if self.mode == "local":
            return ("P1: WASD move · LShift sprint · Q dash · F melee · E shoot        "
                    "P2: Arrows · RShift sprint · / dash · RCtrl melee · . shoot        Esc pause")
        if self.mode == "aivai":
            return "Spectating AI vs AI        Esc pause"
        esc = "Esc pause" if self.mode == "ai" else "Esc leave"
        return f"Move WASD/Arrows · Sprint Shift · Dash Q/Space · Melee F/Left click · Shoot E/Right click        {esc}"

    def winner_text(self):
        w = self.match.match_winner
        if w == 3:
            return "DRAW!", (230, 230, 230)
        col = (110, 200, 255) if w == 1 else (255, 170, 90)
        if self.mode == "local":
            return f"PLAYER {w} WINS!", col
        if self.mode == "aivai":
            return ("BLUE AI WINS!" if w == 1 else "ORANGE AI WINS!"), col
        if self.local_side() == w:
            return "VICTORY!", (255, 220, 90)
        return ("DEFEAT" if self.mode != "ai" else "THE AI WINS"), (255, 110, 110)


class App:
    def __init__(self, args):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("Arena Fighters")
        pygame.display.set_icon(make_icon())
        global _display
        self.display = _display = Display(args.fullscreen)
        self.clock = pygame.time.Clock()
        self.world = pygame.Surface((WIDTH, HEIGHT)).convert()
        self.sfx = SoundBank()
        self.settings = load_settings()
        self.sfx.muted = bool(self.settings.get("muted"))
        self.args = args
        if args.relay is not None:
            self.settings["relay"] = args.relay
        self.maps = shared_maps()
        self.selected_map = args.map if args.map is not None else int(self.settings["map"]) % len(self.maps)
        self.mode = args.mode if args.mode in dict(MODES) else self.settings["mode"]
        if self.mode not in dict(MODES):
            self.mode = "ai"
        self.difficulty = args.difficulty or self.settings["difficulty"]
        if self.difficulty not in DIFFICULTIES:
            self.difficulty = "Medium"
        self.autostart = args.mode in ("ai", "local", "aivai")

        self.state = "loading"
        self.load_step = 0
        self.running = True
        self.tick = 0
        self.session = None
        self.toast_text, self.toast_until = "", 0
        self.particles, self.texts, self.rings = [], [], []
        self.shake = 0.0
        self.flash = 0
        self.connector = None
        self.connect_role = ""
        self.handshake_deadline = 0
        self.lobby_status = ""
        self.lobby_error = ""
        self.beacon = None
        self.scanner = None
        self.lan_buttons = []
        self._build_widgets()

    @property
    def screen(self):
        return self.display.canvas

    # ── widgets ────────────────────────────────────────────────
    def _build_widgets(self):
        cx = WIDTH // 2
        self.mode_btns = [Button(label, cx - 640 + i * 320 + 10, 250, 300, 64, (26, 24, 52), (170, 140, 255))
                          for i, (_m, label) in enumerate(MODES)]
        self.card_rects = [pygame.Rect(124 + i * 424, 392, 400, 225) for i in range(4)]
        self.diff_btns = [Button(d, cx - 350 + i * 240, 712, 220, 58, (26, 24, 52), DIFF_COLORS[d])
                          for i, d in enumerate(DIFFICULTIES)]
        self.start_btn = Button("START", cx - 190, 800, 380, 76, (40, 30, 80), (190, 150, 255))
        self.quit_btn = Button("Quit", cx - 120, 892, 240, 52, (60, 20, 20), (220, 80, 80))
        # game over / pause
        BW, BH = 380, 72
        self.rematch_btn = Button("Rematch", cx - BW // 2, HEIGHT // 2 + 130, BW, BH, (35, 30, 70), (180, 140, 255))
        self.menu_btn = Button("Main Menu", cx - BW // 2, HEIGHT // 2 + 220, BW, BH, (20, 40, 60), (80, 180, 255))
        self.exit_btn = Button("Exit Game", cx - BW // 2, HEIGHT // 2 + 310, BW, BH, (60, 20, 20), (220, 80, 80))
        self.resume_btn = Button("Resume", cx - BW // 2, HEIGHT // 2 + 10, BW, BH, (35, 30, 70), (180, 140, 255))
        self.pause_menu_btn = Button("Main Menu", cx - BW // 2, HEIGHT // 2 + 100, BW, BH, (20, 40, 60), (80, 180, 255))
        self.pause_exit_btn = Button("Exit Game", cx - BW // 2, HEIGHT // 2 + 190, BW, BH, (60, 20, 20), (220, 80, 80))
        self.leave_yes_btn = Button("Leave match", cx - BW // 2, HEIGHT // 2 + 20, BW, BH, (60, 20, 20), (220, 80, 80))
        self.leave_no_btn = Button("Keep playing", cx - BW // 2, HEIGHT // 2 + 110, BW, BH, (35, 30, 70), (180, 140, 255))
        # lobby
        self.relay_field = TextField("Relay server  (optional – leave empty for LAN / direct IP)",
                                     cx - 560, 300, 1120, 60, self.settings.get("relay", ""), "e.g.  my-server.com:7777")
        self.addr_field = TextField("Join: host IP  –  or room code when using a relay",
                                    cx - 560, 450, 760, 60, self.settings.get("address", ""), "e.g.  192.168.1.20")
        self.host_btn = Button("Host Game", cx - 560, 560, 360, 72, (30, 50, 40), (90, 230, 140))
        self.join_btn = Button("Join", cx + 220, 446, 340, 68, (30, 40, 70), (100, 180, 255))
        self.back_btn = Button("Back", cx - 120, HEIGHT - 120, 240, 60, (40, 24, 24), (220, 110, 110))
        self.cancel_btn = Button("Cancel", cx - 160, 860, 320, 64, (60, 20, 20), (220, 80, 80))

    # ── main loop ──────────────────────────────────────────────
    def run(self):
        while self.running:
            self.tick += 1
            events = []
            for e in pygame.event.get():
                if e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
                    e = pygame.event.Event(e.type, {**e.dict, "pos": self.display.to_canvas(e.pos)})
                if e.type == pygame.KEYDOWN and (e.key == pygame.K_F11 or
                                                 (e.key == pygame.K_RETURN and e.mod & pygame.KMOD_ALT)):
                    self.display.toggle_fullscreen()
                    continue
                events.append(e)
            for e in events:
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED):
                    self.display.layout()
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_m and not self._typing():
                    self.settings["muted"] = self.sfx.toggle_mute()
                    self.show_toast("Sound off" if self.sfx.muted else "Sound on", 90)
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    self._click_sound(e)
            getattr(self, "state_" + self.state)(events)
            self._draw_toast()
            self.display.present(self.clock.get_rawtime())
            self.clock.tick(FPS)
        self.shutdown()

    def shutdown(self):
        self.leave_session(notify=True)
        self._stop_lobby_net()
        self.settings.update(map=self.selected_map, mode=self.mode, difficulty=self.difficulty,
                             relay=self.relay_field.text.strip(), address=self.addr_field.text.strip())
        save_settings(self.settings)
        pygame.quit()

    def _typing(self):
        return self.state == "lobby" and (self.relay_field.focused or self.addr_field.focused)

    def _click_sound(self, e):
        btns = []
        if self.state == "menu":
            btns = self.mode_btns + self.diff_btns + [self.start_btn, self.quit_btn]
        elif self.state == "lobby":
            btns = [self.host_btn, self.join_btn, self.back_btn, self.cancel_btn] + [b for b, _ in self.lan_buttons]
        elif self.state in ("over", "pause"):
            btns = [self.rematch_btn, self.menu_btn, self.exit_btn, self.resume_btn, self.pause_menu_btn, self.pause_exit_btn]
        if any(b.rect.collidepoint(e.pos) for b in btns) or (self.state == "menu" and any(r.collidepoint(e.pos) for r in self.card_rects)):
            self.sfx.play("click")

    def show_toast(self, text, frames=240):
        self.toast_text, self.toast_until = text, self.tick + frames

    def _draw_toast(self):
        if self.tick < self.toast_until and self.toast_text:
            img = get_font(22, bold=False).render(self.toast_text, True, (255, 255, 255))
            r = pygame.Rect(0, 0, img.get_width() + 40, 50)
            r.center = (WIDTH // 2, HEIGHT - 140)
            draw_panel(self.screen, r, (40, 20, 60), 230, 14, (200, 140, 255))
            self.screen.blit(img, img.get_rect(center=r.center))

    # ── loading ────────────────────────────────────────────────
    def state_loading(self, events):
        steps = len(self.maps) + 1
        self.screen.fill((8, 8, 22))
        draw_text_center(self.screen, "ARENA FIGHTERS", get_font(88), (225, 215, 255), (WIDTH // 2, HEIGHT // 2 - 80))
        msg = "Forging the arenas…" if self.load_step < len(self.maps) else "Waking up the AI…"
        draw_text_center(self.screen, msg, get_font(24, bold=False), (170, 170, 210), (WIDTH // 2, HEIGHT // 2 + 20))
        bar = pygame.Rect(WIDTH // 2 - 300, HEIGHT // 2 + 60, 600, 16)
        draw_hud_bar(self.screen, bar.x, bar.y, bar.w, bar.h, self.load_step / steps, (170, 140, 255), border=(110, 100, 180), radius=8)
        if self.tick < 2:       # let the first frame show before the heavy work
            return
        if self.load_step < len(self.maps):
            self.maps[self.load_step].static_layer()
        else:
            load_policy()
        self.load_step += 1
        if self.load_step > steps:
            if self.autostart:
                self.start_offline(self.mode)
            elif self.args.mode == "online":
                self.open_lobby()
            else:
                self.state = "menu"

    # ── menu ───────────────────────────────────────────────────
    def state_menu(self, events):
        for e in events:
            for (mode, _label), b in zip(MODES, self.mode_btns):
                if b.clicked(e):
                    self.mode = mode
            for i, r in enumerate(self.card_rects):
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and r.collidepoint(e.pos):
                    self.selected_map = i
            if self.mode in ("ai", "aivai"):
                for d, b in zip(DIFFICULTIES, self.diff_btns):
                    if b.clicked(e):
                        self.difficulty = d
            if self.start_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER)):
                self.sfx.play("fight", 0.5)
                if self.mode == "online":
                    self.open_lobby()
                else:
                    self.start_offline(self.mode)
                return
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.running = False
                elif e.key in (pygame.K_LEFT, pygame.K_a):
                    self.selected_map = (self.selected_map - 1) % len(self.maps)
                elif e.key in (pygame.K_RIGHT, pygame.K_d):
                    self.selected_map = (self.selected_map + 1) % len(self.maps)
            if self.quit_btn.clicked(e):
                self.running = False
        self.draw_menu_background()
        self.draw_menu()

    def draw_menu_background(self):
        m = self.maps[self.selected_map]
        self.screen.blit(m.static_layer(), (0, 0))
        anim = m.animator()
        anim.update()
        anim.draw_under(self.screen, self.tick)
        anim.draw_over(self.screen, self.tick)
        shade = cached("menu_shade", self._menu_shade)
        self.screen.blit(shade, (0, 0))

    @staticmethod
    def _menu_shade():
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for y in range(HEIGHT):
            a = int(150 + 70 * abs(y / HEIGHT - 0.42))
            pygame.draw.line(s, (6, 6, 20, min(235, a)), (0, y), (WIDTH, y))
        return s

    def draw_menu(self):
        cx = WIDTH // 2
        title = banner_text("ARENA FIGHTERS", 104, (235, 225, 255), (140, 100, 255))
        bob = math.sin(self.tick * 0.03) * 4
        blit_center(self.screen, title, cx, 112 + bob)
        draw_text_center(self.screen, "2D arena brawler with a reinforcement-learning AI", get_font(22, bold=False),
                         (190, 185, 230), (cx, 190))

        draw_text_center(self.screen, "GAME MODE", get_font(18), (170, 165, 220), (cx, 230))
        for (mode, _label), b in zip(MODES, self.mode_btns):
            b.draw(self.screen, get_font(26), selected=(mode == self.mode))

        draw_text_center(self.screen, "ARENA", get_font(18), (170, 165, 220), (cx, 368))
        for i, (r, m) in enumerate(zip(self.card_rects, self.maps)):
            sel = i == self.selected_map
            hov = r.collidepoint(mouse_pos())
            lift = -8 if (sel or hov) else 0
            rr = r.move(0, lift)
            if sel:
                g = rr.inflate(26, 26)
                gs = pygame.Surface(g.size, pygame.SRCALPHA)
                pygame.draw.rect(gs, (*m.accent, 90), gs.get_rect(), border_radius=22)
                self.screen.blit(gs, g.topleft)
            self.screen.blit(m.thumbnail(r.size), rr.topleft)
            pygame.draw.rect(self.screen, m.accent if sel else (90, 90, 130), rr, 4 if sel else 2, border_radius=6)
            label_r = pygame.Rect(rr.x, rr.bottom - 46, rr.width, 46)
            ls = pygame.Surface(label_r.size, pygame.SRCALPHA)
            ls.fill((0, 0, 0, 150))
            self.screen.blit(ls, label_r.topleft)
            draw_text_center(self.screen, m.name, get_font(24), (255, 255, 255) if sel else (210, 210, 230), label_r.center)
            draw_text_center(self.screen, MAP_DESCRIPTIONS[i], get_font(17, bold=False), (180, 180, 210),
                             (r.centerx, r.bottom + 22))

        if self.mode in ("ai", "aivai"):
            draw_text_center(self.screen, "AI DIFFICULTY", get_font(18), (170, 165, 220), (cx, 690))
            for d, b in zip(DIFFICULTIES, self.diff_btns):
                b.draw(self.screen, get_font(24), DIFF_COLORS[d] if d == self.difficulty else (80, 80, 110), selected=(d == self.difficulty))
        else:
            draw_text_center(self.screen, MODE_BLURBS[self.mode], get_font(26, bold=False), (215, 210, 245), (cx, 740))

        self.start_btn.text = "CONTINUE" if self.mode == "online" else "START BATTLE"
        self.start_btn.draw(self.screen, get_font(32), selected=True)
        self.quit_btn.draw(self.screen, get_font(22))

        # control guide
        ctrl_r = pygame.Rect(cx - 640, HEIGHT - 116, 1280, 92)
        draw_panel(self.screen, ctrl_r, (8, 8, 22), 210, 12, (60, 60, 100))
        rows = [("P1 / solo", "WASD move · LShift sprint · Q dash · F melee · E shoot", (140, 200, 255)),
                ("P2", "Arrows move · RShift sprint · / dash · RCtrl melee · . shoot", (255, 180, 120))]
        for li, (tag, txt, col) in enumerate(rows):
            draw_text_center(self.screen, f"[{tag}]  {txt}", get_font(21, bold=False), col, (cx, ctrl_r.y + 26 + li * 32))
        foot = get_font(15, bold=False).render(f"F11 fullscreen · M mute · AI: {policy_status()}", True, (130, 130, 170))
        self.screen.blit(foot, (WIDTH - foot.get_width() - 20, HEIGHT - 24))

    # ── starting / ending matches ──────────────────────────────
    def start_offline(self, mode):
        self.session = Session(mode, self.selected_map, self.difficulty)
        self._reset_fx()
        self.state = "game"

    def _reset_fx(self):
        self.particles, self.texts, self.rings = [], [], []
        self.shake = 0.0
        self.flash = 0

    def leave_session(self, notify=True, toast=""):
        s = self.session
        if s and s.peer:
            if notify:
                s.peer.close_gracefully()
            else:
                s.peer.close()
        self.session = None
        if toast:
            self.show_toast(toast)

    def back_to_menu(self, toast=""):
        self.leave_session(notify=True, toast=toast)
        self.state = "menu"

    # ── online lobby ───────────────────────────────────────────
    def open_lobby(self):
        self.state = "lobby"
        self.lobby_error = ""
        self.lobby_status = ""
        if self.scanner is None:
            self.scanner = LanScanner()

    def _stop_lobby_net(self):
        if self.connector:
            self.connector.cancel()
            self.connector = None
        if self.beacon:
            self.beacon.close()
            self.beacon = None
        if self.scanner:
            self.scanner.close()
            self.scanner = None

    def _relay(self):
        return self.relay_field.text.strip() or None

    def start_hosting(self):
        self.lobby_error = ""
        self.connector = HostConnector(relay=self._relay())
        self.connect_role = "host"
        self.handshake_deadline = 0
        if not self._relay():
            self.beacon = LanBeacon(dict(port=DEFAULT_PORT, map=self.maps[self.selected_map].name,
                                         name=platform.node() or "Host"))

    def start_joining(self, target):
        self.lobby_error = ""
        if not target.strip():
            self.lobby_error = "Type the host's IP address (or the room code when using a relay)."
            return
        self.connector = JoinConnector(target, relay=self._relay())
        self.connect_role = "client"
        self.handshake_deadline = 0

    def cancel_connect(self, error=""):
        if self.connector:
            self.connector.cancel()
            self.connector = None
        if self.beacon:
            self.beacon.close()
            self.beacon = None
        self.lobby_error = error

    def _poll_connection(self):
        c = self.connector
        if c is None:
            return
        if self.beacon:
            self.beacon.tick()
        if not c.done:
            return
        if c.error or c.peer is None:
            self.cancel_connect(c.error or "Could not connect.")
            return
        peer = c.peer
        if not peer.alive:
            self.cancel_connect(peer.error or "Connection closed.")
            return
        if self.handshake_deadline == 0:
            self.handshake_deadline = self.tick + 10 * FPS
            if self.connect_role == "client":
                peer.send({"t": "hello", "v": PROTOCOL_VERSION})
        if self.tick > self.handshake_deadline:
            peer.close()
            self.cancel_connect("The other side did not answer (different game version?).")
            return
        for msg in peer.messages():
            kind = msg.get("t")
            if self.connect_role == "host" and kind == "hello":
                if msg.get("v") != PROTOCOL_VERSION:
                    peer.send({"t": "reject", "reason": "version mismatch – update the game"})
                    self.cancel_connect("A player with a different game version tried to join.")
                    return
                peer.send({"t": "welcome", "v": PROTOCOL_VERSION, "map": self.selected_map})
                self._begin_online("host", self.selected_map, peer)
                return
            if self.connect_role == "client" and kind == "welcome":
                self._begin_online("client", int(msg.get("map", 0)), peer)
                return
            if kind == "reject":
                peer.close()
                self.cancel_connect("Host refused: " + msg.get("reason", ""))
                return

    def _begin_online(self, role, map_index, peer):
        self.connector = None
        self._stop_lobby_net()
        self.session = Session(role, map_index, peer=peer)
        self._reset_fx()
        self.state = "game"
        self.sfx.play("pickup")

    def state_lobby(self, events):
        connecting = self.connector is not None
        for e in events:
            if connecting:
                if self.cancel_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    self.cancel_connect()
                continue
            enter_relay = self.relay_field.handle(e)
            enter_addr = self.addr_field.handle(e)
            if self.host_btn.clicked(e) or enter_relay:
                self.start_hosting()
            elif self.join_btn.clicked(e) or enter_addr:
                self.start_joining(self.addr_field.text)
            elif self.back_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE and not self._typing()):
                self._stop_lobby_net()
                self.state = "menu"
                return
            for b, game in self.lan_buttons:
                if b.clicked(e):
                    self.relay_field.text = ""
                    self.addr_field.text = game["addr"]
                    self.start_joining(game["addr"])
        self._poll_connection()
        if self.state != "lobby":
            return

        self.draw_menu_background()
        cx = WIDTH // 2
        blit_center(self.screen, banner_text("PLAY ONLINE", 84, (235, 225, 255), (80, 200, 255)), cx, 110)
        draw_text_center(self.screen, f"Arena: {self.maps[self.selected_map].name}  (the host's choice is used)",
                         get_font(22, bold=False), (190, 190, 230), (cx, 190))

        if self.connector is not None:
            c = self.connector
            panel = pygame.Rect(cx - 520, 300, 1040, 500)
            draw_panel(self.screen, panel, (10, 10, 28), 225, 18, (110, 100, 200))
            dots = "." * (1 + (self.tick // 20) % 3)
            if self.connect_role == "host":
                if getattr(c, "room", ""):
                    draw_text_center(self.screen, "ROOM CODE", get_font(26), (180, 180, 230), (cx, 380))
                    blit_center(self.screen, banner_text(c.room, 110, (255, 240, 160), (255, 170, 40)), cx, 480)
                    draw_text_center(self.screen, "Give this code to your friend. They type it in the Join box.",
                                     get_font(22, bold=False), (200, 200, 240), (cx, 580))
                elif getattr(c, "addresses", None):
                    draw_text_center(self.screen, "YOUR ADDRESS", get_font(26), (180, 180, 230), (cx, 380))
                    blit_center(self.screen, banner_text(c.addresses[0], 70, (200, 255, 220), (40, 220, 140)), cx, 465)
                    draw_text_center(self.screen, "Players on the same network will also see you under 'Games on your network'.",
                                     get_font(22, bold=False), (200, 200, 240), (cx, 560))
                    draw_text_center(self.screen, f"Over the internet: forward TCP port {DEFAULT_PORT}, use a VPN like Tailscale, or use a relay server.",
                                     get_font(19, bold=False), (160, 160, 200), (cx, 600))
            status = c.status if not c.done else "Connected – starting"
            draw_text_center(self.screen, status.rstrip("…") + dots, get_font(26, bold=False), (230, 230, 255), (cx, 720))
            self.cancel_btn.draw(self.screen, get_font(26))
            return

        self.relay_field.draw(self.screen, self.tick)
        self.addr_field.draw(self.screen, self.tick)
        self.join_btn.draw(self.screen, get_font(28))
        self.host_btn.draw(self.screen, get_font(28))
        tip = "Host with a relay → you get a room code." if self._relay() else f"Host directly → friends join with your IP (port {DEFAULT_PORT})."
        draw_text_center(self.screen, tip, get_font(20, bold=False), (180, 200, 190), (cx + 190, 596))

        # LAN games list
        games = self.scanner.poll() if self.scanner else []
        lan_r = pygame.Rect(cx - 560, 670, 1120, 250)
        draw_panel(self.screen, lan_r, (10, 10, 26), 200, 14, (70, 70, 120))
        draw_text_shadow(self.screen, "GAMES ON YOUR NETWORK", get_font(18), (170, 170, 220), (lan_r.x + 20, lan_r.y + 14))
        self.lan_buttons = []
        if not games:
            msg = "Searching" + "." * (1 + (self.tick // 20) % 3) if self.scanner and self.scanner.sock else "LAN discovery unavailable on this machine"
            draw_text_center(self.screen, msg, get_font(22, bold=False), (130, 130, 170), lan_r.center)
        for i, g in enumerate(games[:4]):
            b = Button(f"{g.get('name', 'Host')}  ·  {g.get('map', '')}  ·  {g['addr']}",
                       lan_r.x + 20, lan_r.y + 50 + i * 48, lan_r.width - 40, 42, (20, 30, 50), (90, 200, 255))
            b.draw(self.screen, get_font(20, bold=False))
            self.lan_buttons.append((b, g))
        if self.lobby_error:
            draw_text_center(self.screen, self.lobby_error, get_font(22, bold=False), (255, 120, 120), (cx, 645))
        self.back_btn.draw(self.screen, get_font(24))

    # ── gameplay ───────────────────────────────────────────────
    def _gather_inputs(self, allow_input):
        s = self.session
        m = s.match
        keys = pygame.key.get_pressed()
        fighting = m.phase == "fight"
        in1 = in2 = NO_INPUT
        if s.mode == "local" and allow_input:
            in1, in2 = read_input(keys, SCHEME_P1), read_input(keys, SCHEME_P2)
        elif s.mode in ("ai", "host") and allow_input:
            in1 = read_input(keys, SCHEME_SOLO, mouse=True)
        if s.ai[0] and fighting:
            in1 = input_from_tuple(s.ai[0].get_input(m.p1, m.p2, m.arena, m.bullets))
        if s.ai[1] and fighting:
            in2 = input_from_tuple(s.ai[1].get_input(m.p2, m.p1, m.arena, m.bullets))
        if s.mode == "host":
            x, y, sprint, bits = s.peer.take_input()
            in2 = PlayerInput(max(-1, min(1, x)), max(-1, min(1, y)), sprint,
                              bool(bits & BTN_DASH), bool(bits & BTN_MELEE), bool(bits & BTN_SHOOT))
        return in1, in2

    def update_session(self, allow_input=True):
        """Advance the match one frame (or apply the host's snapshot when we're a client)."""
        s = self.session
        if s.peer is not None:
            for msg in s.peer.messages():      # a goodbye explains the disconnect that follows it
                if msg.get("t") == "bye":
                    who = "The host" if s.mode == "client" else "Your opponent"
                    self.leave_session(notify=False)
                    self.state = "menu"
                    self.show_toast(f"{who} left the match.")
                    return False
            if not s.peer.alive:
                self.back_to_menu("Connection lost: " + (s.peer.error or "disconnected"))
                return False
        if s.mode == "client":
            seq, snap = s.peer.latest_state()
            if snap is not None and seq != s.last_seq:
                s.match.apply_snapshot(snap)
                s.last_seq = seq
            self.handle_events(s.peer.take_events())
            inp = read_input(pygame.key.get_pressed(), SCHEME_SOLO, mouse=True) if allow_input else NO_INPUT
            bits = (BTN_DASH if inp.dash else 0) | (BTN_MELEE if inp.melee else 0) | (BTN_SHOOT if inp.shoot else 0)
            s.peer.send_state({"t": "i", "x": inp.dx, "y": inp.dy, "s": int(bool(inp.sprint)), "b": bits})
        else:
            in1, in2 = self._gather_inputs(allow_input)
            s.match.step(in1, in2)
            self.handle_events(s.match.events)
            if s.mode == "host":
                s.peer.send_state(s.match.snapshot())
        return True

    def handle_events(self, events):
        s = self.session
        for ev in events:
            kind = ev[0]
            if kind == "hit":
                _, x, y, dmg, target, melee = ev
                for _ in range(16 if melee else 10):
                    self.particles.append(Particle(x, y, (255, 80, 80), (3, 9), (14, 30), (3, 7)))
                for _ in range(6):
                    self.particles.append(Particle(x, y, (255, 230, 180), (4, 10), (8, 16), (2, 4), 0))
                self.rings.append(Shockwave(x, y, (255, 200, 200), 80 if melee else 60))
                self.texts.append(FloatingText(f"-{dmg}", x + random.randint(-12, 12), y - 46,
                                               (255, 90, 90) if melee else (255, 200, 90), 30 if melee else 26))
                mine = s.local_side() == target
                self.shake = max(self.shake, (12 if melee else 8) + (4 if mine else 0))
                if mine:
                    self.flash = 8
                self.sfx.play("hit", 0.9 if melee else 0.7)
            elif kind == "shoot":
                _, x, y, widx = ev
                w = WEAPON_TYPES[widx]
                for _ in range(5):
                    self.particles.append(Particle(x, y, w.glow, (1, 4), (6, 12), (2, 4), 0))
                self.sfx.play(f"shoot_{widx}", 0.8)
            elif kind == "impact":
                _, x, y, widx = ev
                w = WEAPON_TYPES[widx]
                for _ in range(8):
                    self.particles.append(Particle(x, y, w.glow, (2, 6), (10, 20), (2, 5), 0.1))
                self.rings.append(Shockwave(x, y, w.glow, 36, 12, 4))
                self.sfx.play("impact", 0.6)
            elif kind == "pickup":
                _, x, y, widx, who = ev
                w = WEAPON_TYPES[widx]
                for _ in range(14):
                    self.particles.append(Particle(x, y, w.glow, (2, 6), (16, 30), (3, 6), -0.05))
                self.rings.append(Shockwave(x, y, w.glow, 70, 20, 5))
                self.texts.append(FloatingText(f"+{w.name}", x, y - 50, w.color, 24, 70))
                self.sfx.play("pickup", 0.8)
            elif kind == "swing":
                self.sfx.play("swing", 0.7)
            elif kind == "dash":
                self.sfx.play("dash", 0.6)
            elif kind == "count":
                self.sfx.play("beep", 0.8)
            elif kind == "fight":
                self.sfx.play("fight", 0.8)
            elif kind == "ko":
                _, w, reason, x, y = ev
                if reason == "ko":
                    for _ in range(40):
                        self.particles.append(Particle(x, y, random.choice([(255, 80, 80), (255, 220, 90), (255, 255, 255)]),
                                                       (3, 12), (25, 50), (3, 8), 0.12))
                    self.rings.append(Shockwave(x, y, (255, 255, 255), 220, 30, 10))
                    self.shake = 22
                    self.flash = 14
                self.sfx.play("ko")
            elif kind == "over":
                self.sfx.play("win")

    def update_fx(self):
        for lst in (self.particles, self.texts, self.rings):
            for item in lst:
                item.update()
            lst[:] = [i for i in lst if i.life > 0]
        self.shake *= 0.86
        if self.shake < 0.5:
            self.shake = 0
        if self.flash > 0:
            self.flash -= 1

    def draw_scene(self):
        s = self.session
        m = s.match
        w = self.world
        m.arena.map.draw(w, self.tick)
        for pickup in m.arena.weapon_pickups:
            pickup.draw(w)
        for ring in self.rings:
            ring.draw(w)
        for b in m.bullets:
            b.draw(w)
        for p in sorted(m.players(), key=lambda pl: pl.y):
            if not (m.phase in ("ko", "over") and p.is_dead()) or (self.tick // 4) % 2:
                p.draw(w)
        for pt in self.particles:
            pt.draw(w)
        for t in self.texts:
            t.draw(w)
        m.arena.map.draw_overlay(w, self.tick)
        if self.shake:
            ox = int(random.uniform(-self.shake, self.shake))
            oy = int(random.uniform(-self.shake, self.shake))
            self.screen.fill((0, 0, 0))
            self.screen.blit(w, (ox, oy))
        else:
            self.screen.blit(w, (0, 0))
        if self.flash:
            fl = cached("flash", lambda: self._flat_overlay((255, 40, 40)))
            fl.set_alpha(int(10 * self.flash))
            self.screen.blit(fl, (0, 0))
        draw_game_hud(self.screen, m, s.titles, s.hint(), self.tick)
        draw_banners(self.screen, m, s.titles)

    @staticmethod
    def _flat_overlay(color, alpha=255):
        s = pygame.Surface((WIDTH, HEIGHT))
        s.fill(color)
        s.set_alpha(alpha)
        return s

    def _dim(self, alpha=150):
        ov = cached(("dim", alpha), lambda: self._flat_overlay((10, 10, 25), alpha))
        self.screen.blit(ov, (0, 0))

    def state_game(self, events):
        s = self.session
        online = s.peer is not None
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                if online:
                    s.leave_prompt = not s.leave_prompt
                else:
                    self.state = "pause"
                    return
            if online and s.leave_prompt:
                if self.leave_yes_btn.clicked(e):
                    self.back_to_menu()
                    return
                if self.leave_no_btn.clicked(e):
                    s.leave_prompt = False
        if not self.update_session(allow_input=not (online and s.leave_prompt)):
            return
        self.update_fx()
        self.draw_scene()
        if online and s.leave_prompt:
            self._dim(160)
            blit_center(self.screen, banner_text("LEAVE MATCH?", 90, (255, 230, 230), (255, 60, 60)), WIDTH // 2, HEIGHT // 2 - 100)
            self.leave_yes_btn.draw(self.screen, get_font(26))
            self.leave_no_btn.draw(self.screen, get_font(26))
        if s.match.phase == "over":
            self.state = "over"

    def state_pause(self, events):
        for e in events:
            if self.resume_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                self.state = "game"
            elif self.pause_menu_btn.clicked(e):
                self.back_to_menu()
                return
            elif self.pause_exit_btn.clicked(e):
                self.running = False
        if self.session is None:
            return
        self.draw_scene()
        self._dim(150)
        blit_center(self.screen, banner_text("PAUSED", 110, (230, 230, 255), (120, 100, 255)), WIDTH // 2, HEIGHT // 2 - 110)
        draw_text_center(self.screen, "Press Esc to resume", get_font(24, bold=False), (190, 190, 230), (WIDTH // 2, HEIGHT // 2 - 30))
        self.resume_btn.draw(self.screen, get_font(30))
        self.pause_menu_btn.draw(self.screen, get_font(30))
        self.pause_exit_btn.draw(self.screen, get_font(30))

    def state_over(self, events):
        s = self.session
        is_client = s.mode == "client"
        for e in events:
            if not is_client and (self.rematch_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_r))):
                s.new_match()
                self._reset_fx()
                self.state = "game"
                return
            if self.menu_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                self.back_to_menu()
                return
            if self.exit_btn.clicked(e):
                self.running = False
                return
        if not self.update_session(allow_input=False):
            return
        if is_client and s.match.phase != "over":
            self._reset_fx()
            self.state = "game"
            return
        if self.tick % 14 == 0:
            for _ in range(14):
                self.particles.append(Particle(random.randint(WIDTH // 4, 3 * WIDTH // 4), random.randint(HEIGHT // 5, HEIGHT // 2),
                                               random.choice([(255, 220, 60), (100, 220, 255), (255, 100, 180), (80, 255, 120)]),
                                               (2, 7), (30, 60), (3, 7), 0.15))
        self.update_fx()
        self.draw_scene()
        self._dim(165)
        text, col = s.winner_text()
        blit_center(self.screen, banner_text(text, 120, col, shade_color(col, -60)), WIDTH // 2, HEIGHT // 2 - 250)
        m = s.match
        draw_text_center(self.screen, f"{m.score[0]}  –  {m.score[1]}", get_font(64), (240, 240, 255), (WIDTH // 2, HEIGHT // 2 - 140))
        # match stats
        st = m.stats
        rows = [("Damage dealt", "dmg"), ("Hits landed", "hits"), ("Shots fired", "shots"), ("Weapons picked", "pickups")]
        panel = pygame.Rect(WIDTH // 2 - 330, HEIGHT // 2 - 95, 660, 200)
        draw_panel(self.screen, panel, (12, 12, 30), 220, 14, (90, 90, 150))
        draw_text_center(self.screen, s.titles[0], get_font(20), (130, 205, 255), (panel.x + 110, panel.y + 26))
        draw_text_center(self.screen, s.titles[1], get_font(20), (255, 180, 110), (panel.right - 110, panel.y + 26))
        for i, (name, key) in enumerate(rows):
            y = panel.y + 66 + i * 34
            draw_text_center(self.screen, name, get_font(20, bold=False), (190, 190, 225), (panel.centerx, y))
            draw_text_center(self.screen, str(st[0][key]), get_font(22), (240, 240, 255), (panel.x + 110, y))
            draw_text_center(self.screen, str(st[1][key]), get_font(22), (240, 240, 255), (panel.right - 110, y))
        if is_client:
            draw_text_center(self.screen, "Waiting for the host to start a rematch" + "." * (1 + (self.tick // 20) % 3),
                             get_font(26, bold=False), (220, 220, 255), (WIDTH // 2, HEIGHT // 2 + 165))
            self.menu_btn.text = "Leave"
        else:
            self.menu_btn.text = "Main Menu"
            self.rematch_btn.draw(self.screen, get_font(30))
        self.menu_btn.draw(self.screen, get_font(30))
        self.exit_btn.draw(self.screen, get_font(30))


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Arena Fighters")
    ap.add_argument("--fullscreen", action="store_true", help="start in fullscreen (F11 toggles)")
    ap.add_argument("--mode", choices=["menu", "ai", "local", "aivai", "online"], default="menu",
                    help="skip the menu and start this mode directly")
    ap.add_argument("--difficulty", choices=["Easy", "Medium", "Hard"], help="AI difficulty")
    ap.add_argument("--map", type=int, choices=range(4), help="arena index 0-3")
    ap.add_argument("--relay", help="relay server host:port for online play")
    return ap.parse_args(argv)


def main(argv=None):
    App(parse_args(argv)).run()


if __name__ == "__main__":
    main()
