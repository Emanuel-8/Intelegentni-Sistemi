import math
import random
import pygame
 
if __package__ is None or __package__ == "":
    from settings import *
else:
    from .settings import *
 
 
# ──────────────────────────────────────────────────────────────────────────────
#  WEAPON DEFINITIONS
# ──────────────────────────────────────────────────────────────────────────────
WEAPON_DEFS = [
    # id, name, damage, cooldown, range, proj_speed, proj_color, proj_radius, is_melee
    (0, "Sword",     25, 20,  60,  0,  (220, 220,  60), 0, True),
    (1, "Bow",       18, 35, 500,  9,  (230, 140,  40), 5, False),
    (2, "Dagger",    12, 10,  45,  0,  (180, 255, 180), 0, True),
    (3, "Crossbow",  30, 55, 500, 12,  (255,  80,  80), 6, False),
    (4, "Staff",     20, 28, 500,  8,  ( 80, 130, 255), 7, False),
]
 
 
class Weapon:
    def __init__(self, weapon_id):
        d = WEAPON_DEFS[weapon_id]
        self.weapon_id   = d[0]
        self.name        = d[1]
        self.damage      = d[2]
        self.cooldown    = d[3]
        self.range       = d[4]
        self.proj_speed  = d[5]
        self.proj_color  = d[6]
        self.proj_radius = d[7]
        self.is_melee    = d[8]
 
    # ── icons drawn procedurally ──────────────────────────────────────────────
    def draw_pickup(self, surface, x, y, pulse):
        """Draw the weapon as a glowing pickup on the map."""
        glow_r = 18 + int(4 * pulse)
        glow_surf = pygame.Surface((glow_r*2, glow_r*2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*self.proj_color, 60), (glow_r, glow_r), glow_r)
        surface.blit(glow_surf, (x - glow_r, y - glow_r))
        pygame.draw.circle(surface, self.proj_color, (int(x), int(y)), 10)
 
        # small label
        if not hasattr(Weapon, "_label_font"):
            Weapon._label_font = pygame.font.SysFont("consolas", 11, bold=True)
        lbl = Weapon._label_font.render(self.name, True, C_WHITE)
        surface.blit(lbl, (x - lbl.get_width()//2, y + 14))
 
 
class WeaponPickup:
    def __init__(self, x, y, weapon_id):
        self.x = x
        self.y = y
        self.weapon  = Weapon(weapon_id)
        self.alive   = True
        self._tick   = random.uniform(0, math.pi * 2)
 
    def update(self):
        self._tick += 0.07
 
    def draw(self, surface):
        pulse = math.sin(self._tick)
        self.weapon.draw_pickup(surface, self.x, self.y, pulse)
 
    def check_pickup(self, player):
        dist = math.hypot(player.x - self.x, player.y - self.y)
        if dist < player.radius + WEAPON_PICKUP_RADIUS:
            player.weapon = Weapon(self.weapon.weapon_id)
            self.alive = False
 
 
# ──────────────────────────────────────────────────────────────────────────────
#  PROJECTILE
# ──────────────────────────────────────────────────────────────────────────────
class Projectile:
    def __init__(self, x, y, dx, dy, weapon, owner):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.weapon  = weapon
        self.owner   = owner
        self.alive   = True
        self.traveled= 0
 
    def update(self, obstacles):
        self.x += self.dx * self.weapon.proj_speed
        self.y += self.dy * self.weapon.proj_speed
        self.traveled += self.weapon.proj_speed
 
        if self.traveled > self.weapon.range:
            self.alive = False
            return
 
        # out of screen
        if not (0 <= self.x <= SCREEN_W and 0 <= self.y <= SCREEN_H):
            self.alive = False
            return
 
        # obstacle collision
        for obs in obstacles:
            if obs.collide_point(self.x, self.y):
                self.alive = False
                return
 
    def draw(self, surface):
        pygame.draw.circle(surface, self.weapon.proj_color,
                           (int(self.x), int(self.y)), self.weapon.proj_radius)
        # trail dot
        trail_x = int(self.x - self.dx * self.weapon.proj_speed * 2)
        trail_y = int(self.y - self.dy * self.weapon.proj_speed * 2)
        pygame.draw.circle(surface, (*self.weapon.proj_color[:3], 100),
                           (trail_x, trail_y), max(2, self.weapon.proj_radius - 2))
 
 
# ──────────────────────────────────────────────────────────────────────────────
#  WEAPON SPAWNER
# ──────────────────────────────────────────────────────────────────────────────
class WeaponSpawner:
    def __init__(self, spawn_points):
        self.spawn_points = spawn_points   # list of (x,y)
        self.pickups      = []
        self.timer        = WEAPON_SPAWN_INTERVAL // 2  # first spawn sooner
 
    def update(self, obstacles):
        self.timer -= 1
        for p in self.pickups:
            p.update()
        self.pickups = [p for p in self.pickups if p.alive]
 
        if self.timer <= 0 and len(self.pickups) < 4:
            self.timer = WEAPON_SPAWN_INTERVAL
            self._spawn(obstacles)
 
    def _spawn(self, obstacles):
        for sx, sy in random.sample(self.spawn_points, len(self.spawn_points)):
            # don't spawn too close to an existing pickup
            too_close = any(math.hypot(p.x-sx, p.y-sy) < 60 for p in self.pickups)
            in_wall   = any(obs.collide_point(sx, sy) for obs in obstacles)
            if not too_close and not in_wall:
                wid = random.randint(0, len(WEAPON_DEFS)-1)
                self.pickups.append(WeaponPickup(sx, sy, wid))
                return
 
    def check_pickups(self, player):
        for p in self.pickups:
            p.check_pickup(player)
 
    def draw(self, surface):
        for p in self.pickups:
            p.draw(surface)
 