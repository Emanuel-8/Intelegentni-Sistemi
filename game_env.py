import math
import random
import pygame

# ─────────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────────
WIDTH, HEIGHT = 1920, 1080
FPS = 60
MAX_WEAPON_PICKUPS = 5
WEAPON_RESPAWN_INTERVAL = 300

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
        if len(self.trail) > 6: self.trail.pop(0)
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
        self.radius = 28
        self.bob = random.uniform(0, math.pi * 2)
        self.age = 0

    def draw(self, surface):
        self.age += 1
        bob_y = math.sin(self.age * 0.05 + self.bob) * 6
        cx, cy = int(self.x), int(self.y + bob_y)
        # outer glow rings
        for r in range(38, 28, -2):
            alpha = int(55 * (38 - r) / 10)
            s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.weapon.glow, alpha), (r, r), r)
            surface.blit(s, (cx - r, cy - r))
        # base circle
        pygame.draw.circle(surface, (20, 20, 40), (cx, cy), self.radius)
        pygame.draw.circle(surface, self.weapon.color, (cx, cy), self.radius, 3)
        # weapon sprite centered
        spr = self.weapon.get_sprite()
        if spr:
            spr_scaled = pygame.transform.scale(spr, (42, int(42 * spr.get_height() / spr.get_width())))
            surface.blit(spr_scaled, spr_scaled.get_rect(center=(cx, cy)))
        # name tag above
        nfont = pygame.font.SysFont("arialblack", 16)
        ntag = nfont.render(self.weapon.name, True, (240, 240, 240))
        nr = ntag.get_rect(center=(cx, cy - self.radius - 14))
        bg = pygame.Surface((nr.width + 12, nr.height + 6), pygame.SRCALPHA)
        pygame.draw.rect(bg, (0, 0, 0, 160), (0, 0, nr.width + 12, nr.height + 6), border_radius=5)
        pygame.draw.rect(bg, (*self.weapon.glow, 140), (0, 0, nr.width + 12, nr.height + 6), 1, border_radius=5)
        surface.blit(bg, (nr.x - 6, nr.y - 3))
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

        hit = self.hit_timer > 0
        gc = (255, 80, 80) if hit else self.glow_color
        for r in range(self.radius + 14, self.radius, -3):
            a = int(50 * (r - self.radius) / 14)
            s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*gc, a), (r, r), r)
            surface.blit(s, (int(self.x) - r, int(self.y) - r))

        body_color = (255, 120, 120) if hit else self.color
        pygame.draw.circle(surface, body_color, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surface, (255, 255, 255), (int(self.x), int(self.y)), self.radius, 3)

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

        # direction dot
        fx = self.x + self.facing_dx * (self.radius - 8)
        fy = self.y + self.facing_dy * (self.radius - 8)
        pygame.draw.circle(surface, (255, 255, 255), (int(fx), int(fy)), 5)

        # melee weapon swing (only for sword / non-projectile weapons)
        if self.is_attacking() and not self.weapon.projectile:
            angle = math.atan2(self.facing_dy, self.facing_dx)
            progress = 1 - (self.attack_timer / self.attack_duration)
            # swing arc: starts at -70 deg, sweeps +140 deg through the hit
            swing_offset = -1.22 + progress * 2.44   # radians (-70° to +70°)
            tip_angle = angle + swing_offset

            # soft motion blur behind the blade, without turning the swing into a lightbar
            for ti in range(5):
                blur_progress = max(0.0, progress - ti * 0.08)
                blur_angle = angle - 1.05 + blur_progress * 2.1
                blur_dx = math.cos(blur_angle)
                blur_dy = math.sin(blur_angle)
                blur_x = int(self.x + blur_dx * (self.radius + 10 + ti * 3))
                blur_y = int(self.y + blur_dy * (self.radius + 10 + ti * 3))
                blur_s = pygame.Surface((34, 34), pygame.SRCALPHA)
                pygame.draw.circle(blur_s, (*self.weapon.glow, 70 - ti * 10), (17, 17), 12 - ti)
                surface.blit(blur_s, (blur_x - 17, blur_y - 17))

            # draw the sword sprite rotated along the swing angle
            spr = self.weapon.get_sprite()
            if spr:
                blade_angle_deg = -math.degrees(tip_angle)
                big_spr = pygame.transform.scale(spr, (78, int(78 * spr.get_height() / spr.get_width())))
                rot_spr = pygame.transform.rotate(big_spr, blade_angle_deg)
                mid_x = int(self.x + math.cos(tip_angle) * (self.radius + 24))
                mid_y = int(self.y + math.sin(tip_angle) * (self.radius + 24))
                surface.blit(rot_spr, rot_spr.get_rect(center=(mid_x, mid_y)))

            # small hilt flash at the hand to make the weapon read as a sword
            hilt_x = int(self.x + math.cos(angle) * (self.radius - 3))
            hilt_y = int(self.y + math.sin(angle) * (self.radius - 3))
            pygame.draw.circle(surface, self.weapon.glow, (hilt_x, hilt_y), 4)
            pygame.draw.circle(surface, (255, 255, 255), (hilt_x, hilt_y), 2)

        # health bar (directly above player)
        bw, bh = 64, 9
        bx = self.x - bw // 2
        by = self.y - self.radius - 18
        pygame.draw.rect(surface, (20, 20, 20), (bx, by, bw, bh), border_radius=5)
        hp_frac = max(0, self.health / self.max_health)
        hp_color = (int(40 + 200 * (1 - hp_frac)), int(180 * hp_frac), 40)
        if bw * hp_frac > 0:
            pygame.draw.rect(surface, hp_color, (bx, by, bw * hp_frac, bh), border_radius=5)
        pygame.draw.rect(surface, (180, 180, 180), (bx, by, bw, bh), 1, border_radius=5)

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

    def draw(self, surface):
        if self.shape == "rect":
            ss = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            ss.fill((0, 0, 0, 60))
            surface.blit(ss, (self.x + 6, self.y + 6))
            pygame.draw.rect(surface, self.color, (self.x, self.y, self.w, self.h), border_radius=10)
            pygame.draw.rect(surface, self.edge, (self.x, self.y, self.w, self.h), 3, border_radius=10)
        else:
            cx, cy = int(self.x), int(self.y)
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
                px = self.x + dx / dist * md; py = self.y + dy / dist * md
        return px, py

# ─────────────────────────────────────────────
#  MAP DECORATIONS  (trees, rocks, crystals)
# ─────────────────────────────────────────────
def draw_tree(surface, x, y, trunk_col=(80,55,30), leaf_col=(40,110,40), size=1.0):
    """Draw a top-down tree: shadow, trunk, canopy layers."""
    r = int(22 * size)
    # shadow
    sh = pygame.Surface((r*3, r*2), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0,0,0,55), (0, 0, r*3, r*2))
    surface.blit(sh, (x - r + 8, y - r//2 + 10))
    # trunk
    pygame.draw.circle(surface, trunk_col, (x, y), int(7*size))
    # outer canopy (darker)
    dark = tuple(max(0, c-30) for c in leaf_col)
    pygame.draw.circle(surface, dark, (x, y - int(4*size)), r+2)
    # mid canopy
    pygame.draw.circle(surface, leaf_col, (x, y - int(4*size)), r)
    # highlight blob (top-left)
    hi = tuple(min(255, c+45) for c in leaf_col)
    pygame.draw.circle(surface, hi, (x - int(6*size), y - int(8*size)), int(r*0.5))
    # small shadow blob (bottom-right)
    pygame.draw.circle(surface, dark, (x + int(5*size), y + int(2*size)), int(r*0.45))

def draw_rock(surface, x, y, color=(100,100,110), edge=(160,160,180), size=1.0):
    """Draw a top-down rock: shadow + irregular polygon."""
    pts_offsets = [(0,-1),(0.7,-0.6),(1,-0.1),(0.65,0.7),(0,1),(-0.65,0.65),(-1,0.05),(-0.6,-0.7)]
    r = int(18 * size)
    sh_pts = [(x + int(dx*r)+7, y + int(dy*r)+8) for dx,dy in pts_offsets]
    sh = pygame.Surface((r*4, r*4), pygame.SRCALPHA)
    adjusted = [(px - (x-r*2), py - (y-r*2)) for px,py in sh_pts]
    if len(adjusted) >= 3:
        pygame.draw.polygon(sh, (0,0,0,60), adjusted)
    surface.blit(sh, (x-r*2, y-r*2))
    pts = [(x + int(dx*r), y + int(dy*r)) for dx,dy in pts_offsets]
    if len(pts) >= 3:
        pygame.draw.polygon(surface, color, pts)
        pygame.draw.polygon(surface, edge, pts, 2)
    # highlight
    hi = tuple(min(255,c+50) for c in color)
    hl = [(x + int(dx*r*0.55) - int(r*0.2), y + int(dy*r*0.55) - int(r*0.25))
          for dx,dy in pts_offsets[:4]]
    if len(hl) >= 3:
        pygame.draw.polygon(surface, hi, hl)

def draw_neon_crystal(surface, x, y, color=(0,220,200), size=1.0, tick=0):
    r = int(14 * size)
    pulse = 0.85 + 0.15 * math.sin(tick * 0.06 + x * 0.01)
    pr = int(r * pulse)
    glow_s = pygame.Surface((pr*6, pr*6), pygame.SRCALPHA)
    pygame.draw.circle(glow_s, (*color, 50), (pr*3, pr*3), pr*3)
    surface.blit(glow_s, (x - pr*3, y - pr*3))
    pts = [(x, y-pr*2),(x+pr,y),(x,y+pr),(x-pr,y)]
    pygame.draw.polygon(surface, color, pts)
    hi = tuple(min(255,c+80) for c in color)
    pygame.draw.polygon(surface, hi, pts, 2)

def draw_ruins_column(surface, x, y, color=(75,75,120), edge=(130,120,200), size=1.0):
    w = int(16*size); h = int(36*size)
    # shadow
    pygame.draw.ellipse(surface, (0,0,0,50), (x-w+5, y+h//2+4, w*2, h//3))
    # shaft
    pygame.draw.rect(surface, color, (x-w//2, y-h//2, w, h), border_radius=3)
    pygame.draw.rect(surface, edge, (x-w//2, y-h//2, w, h), 2, border_radius=3)
    # capital at top
    cap_w = int(w*1.6)
    pygame.draw.rect(surface, tuple(min(255,c+20) for c in color),
                     (x-cap_w//2, y-h//2-6, cap_w, 8), border_radius=2)
    pygame.draw.rect(surface, edge, (x-cap_w//2, y-h//2-6, cap_w, 8), 1, border_radius=2)

def draw_dead_tree(surface, x, y, color=(60,40,25), size=1.0):
    """Bare/dead tree for quarry / dark maps."""
    r = int(5*size)
    # trunk
    pygame.draw.line(surface, color, (x, y+int(20*size)), (x, y-int(14*size)), int(5*size))
    # branches
    blen = int(14*size)
    for ang in [-0.9, -0.5, 0.5, 0.9]:
        bx = x + int(math.cos(ang - math.pi/2) * blen)
        by = (y - int(8*size)) + int(math.sin(ang - math.pi/2) * blen)
        pygame.draw.line(surface, color, (x, y - int(8*size)), (bx, by), int(3*size))
    pygame.draw.circle(surface, (0,0,0,40), (x+4, y+int(18*size)), int(9*size))

def draw_bush(surface, x, y, color=(55,130,60), size=1.0):
    r = int(12 * size)
    shadow = pygame.Surface((r * 4, r * 3), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 45), (0, 0, r * 4, r * 2))
    surface.blit(shadow, (x - r * 2 + 5, y - r + 8))
    for ox, oy, scale in [(-8, 0, 0.9), (0, -4, 1.1), (9, 1, 0.95)]:
        rr = int(r * scale)
        pygame.draw.circle(surface, color, (x + ox, y + oy), rr)
    hi = tuple(min(255, c + 35) for c in color)
    pygame.draw.circle(surface, hi, (x - 4, y - 6), int(r * 0.55))

def draw_stump(surface, x, y, color=(95, 70, 45), edge=(140, 105, 70), size=1.0):
    w = int(18 * size)
    h = int(14 * size)
    pygame.draw.ellipse(surface, (0, 0, 0, 50), (x - w, y + h // 2 + 4, w * 2, h))
    pygame.draw.rect(surface, color, (x - w // 2, y - h // 2, w, h), border_radius=4)
    pygame.draw.rect(surface, edge, (x - w // 2, y - h // 2, w, h), 2, border_radius=4)
    pygame.draw.circle(surface, tuple(min(255, c + 20) for c in color), (x - w // 6, y - h // 6), max(2, int(4 * size)))

def draw_ruin_debris(surface, x, y, color=(100, 95, 150), edge=(170, 160, 220), size=1.0):
    r = int(14 * size)
    pts = [(x - r, y + 2), (x - r // 2, y - r), (x + r // 3, y - r // 2), (x + r, y + r // 3), (x, y + r)]
    pygame.draw.polygon(surface, (0, 0, 0, 50), [(px + 4, py + 5) for px, py in pts])
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(surface, edge, pts, 2)

def draw_crate(surface, x, y, color=(120, 90, 55), edge=(180, 135, 80), size=1.0):
    w = int(22 * size)
    h = int(18 * size)
    pygame.draw.ellipse(surface, (0, 0, 0, 50), (x - w // 2, y + h // 2 + 5, w, h // 2))
    pygame.draw.rect(surface, color, (x - w // 2, y - h // 2, w, h), border_radius=3)
    pygame.draw.rect(surface, edge, (x - w // 2, y - h // 2, w, h), 2, border_radius=3)
    pygame.draw.line(surface, edge, (x - w // 2 + 3, y - h // 2 + 3), (x + w // 2 - 3, y + h // 2 - 3), 2)
    pygame.draw.line(surface, edge, (x - w // 2 + 3, y + h // 2 - 3), (x + w // 2 - 3, y - h // 2 + 3), 2)

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
    def __init__(self, name, top_color, bottom_color, accent, player_starts, obstacles, decor=None):
        self.name = name; self.top_color = top_color; self.bottom_color = bottom_color
        self.accent = accent; self.player_starts = player_starts; self.obstacles = obstacles
        self.decor = decor or []
        self._bg = None
        self._decor_surf = None

    def _build_bg(self):
        bg = pygame.Surface((WIDTH, HEIGHT))
        for y in range(HEIGHT):
            t = y / HEIGHT
            c = tuple(int(self.top_color[i] * (1 - t) + self.bottom_color[i] * t) for i in range(3))
            pygame.draw.line(bg, c, (0, y), (WIDTH, y))
        # subtle ground texture dots
        rng = random.Random(42)
        for _ in range(600):
            gx = rng.randint(0, WIDTH-1); gy = rng.randint(0, HEIGHT-1)
            t = gy / HEIGHT
            base = tuple(int(self.top_color[i] * (1 - t) + self.bottom_color[i] * t) for i in range(3))
            shade = tuple(max(0, min(255, c + rng.randint(-18, 18))) for c in base)
            pygame.draw.circle(bg, shade, (gx, gy), rng.randint(2, 5))
        return bg

    def _build_decor_surf(self):
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for item in self.decor:
            kind = item[0]
            if kind == 'tree':
                _, x, y, sz = item
                draw_tree(s, x, y,
                          trunk_col=(70,48,24),
                          leaf_col=(38,115,45), size=sz)
            elif kind == 'rock_forest':
                _, x, y, sz = item
                draw_rock(s, x, y, (85,92,80), (130,145,110), sz)
            elif kind == 'dead_tree':
                _, x, y, sz = item
                draw_dead_tree(s, x, y, (70,48,28), sz)
            elif kind == 'rock_quarry':
                _, x, y, sz = item
                draw_rock(s, x, y, (120,95,65), (185,145,90), sz)
            elif kind == 'column':
                _, x, y, sz = item
                draw_ruins_column(s, x, y, (75,75,120), (130,120,200), sz)
            elif kind == 'rock_ruins':
                _, x, y, sz = item
                draw_rock(s, x, y, (80,78,130), (140,130,210), sz)
            elif kind == 'bush_forest':
                _, x, y, sz = item
                draw_bush(s, x, y, (45,125,55), sz)
            elif kind == 'bush_quarry':
                _, x, y, sz = item
                draw_bush(s, x, y, (90,95,60), sz)
            elif kind == 'stump':
                _, x, y, sz = item
                draw_stump(s, x, y, (100, 75, 45), (150, 115, 70), sz)
            elif kind == 'ruin_debris':
                _, x, y, sz = item
                draw_ruin_debris(s, x, y, (98, 96, 156), (170, 164, 230), sz)
            elif kind == 'crate_neon':
                _, x, y, sz = item
                draw_crate(s, x, y, (55, 55, 80), (0, 220, 180), sz)
            # crystals drawn live (animated), skip here
        return s

    def draw(self, surface, tick=0):
        if self._bg is None: self._bg = self._build_bg()
        if self._decor_surf is None: self._decor_surf = self._build_decor_surf()
        surface.blit(self._bg, (0, 0))
        surface.blit(self._decor_surf, (0, 0))
        # draw animated neon crystals live
        for item in self.decor:
            if item[0] == 'crystal':
                _, x, y, col = item
                draw_neon_crystal(surface, x, y, col, size=1.0, tick=tick)
        for ob in self.obstacles: ob.draw(surface)

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
             Obstacle.rect(1200,180,240,40,(70,75,65),(110,120,90))], d[0]),
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
             Obstacle.circle(1580,400,36,(120,95,65),(190,145,90))], d[1]),
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
             Obstacle.circle(1380,560,34,(85,80,135),(140,130,210))], d[2]),
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
             Obstacle.circle(1520,730,40,(20,20,60),(60,255,200))], d[3]),
    ]

MAP_NAMES = ["Forest Canyon", "Sunset Quarry", "Ruins Arena", "Neon Void"]
MAP_DESCRIPTIONS = [
    "Lush canyon with stone pillars and tree clusters.",
    "Blazing quarry with high walls and rock formations.",
    "Ancient ruins with columns and mystical arches.",
    "Cyberpunk void with glowing geometric obstacles.",
]

# ─────────────────────────────────────────────
#  ARENA
# ─────────────────────────────────────────────
class Arena:
    def __init__(self, player1, player2, map_index=0):
        self.player1 = player1; self.player2 = player2
        self.all_maps = create_maps(); self.map_index = map_index
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

def draw_panel(surface, rect, bg=(20, 20, 40), alpha=200, radius=16, border=(100, 100, 160)):
    s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    shadow = pygame.Surface((rect.width + 18, rect.height + 18), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 70), (8, 8, rect.width, rect.height), border_radius=radius + 2)
    surface.blit(shadow, (rect.x - 8, rect.y - 8))
    pygame.draw.rect(s, (*bg, alpha), (0, 0, rect.width, rect.height), border_radius=radius)
    pygame.draw.rect(s, (*border, 190), (0, 0, rect.width, rect.height), 2, border_radius=radius)
    surface.blit(s, rect.topleft)

def draw_hud_bar(surface, x, y, w, h, frac, fill_color, bg=(20,20,20), border=(160,160,160), radius=5):
    pygame.draw.rect(surface, bg, (x, y, w, h), border_radius=radius)
    if frac > 0:
        fw = max(radius * 2, int(w * frac))
        pygame.draw.rect(surface, fill_color, (x, y, fw, h), border_radius=radius)
    pygame.draw.rect(surface, border, (x, y, w, h), 1, border_radius=radius)

class Button:
    def __init__(self, text, x, y, w, h, base=(30,30,55), accent=(140,120,255)):
        self.text = text; self.rect = pygame.Rect(x, y, w, h)
        self.base = base; self.accent = accent

    def draw(self, surface, font, override_accent=None):
        ac = override_accent or self.accent
        hovered = self.rect.collidepoint(pygame.mouse.get_pos())
        col = tuple(min(255, c + 28) for c in self.base) if hovered else self.base
        shadow = self.rect.inflate(12, 12)
        gs = pygame.Surface((shadow.width, shadow.height), pygame.SRCALPHA)
        pygame.draw.rect(gs, (0, 0, 0, 70), (4, 6, shadow.width - 8, shadow.height - 8), border_radius=22)
        surface.blit(gs, shadow.topleft)
        if hovered:
            glow = self.rect.inflate(14, 14)
            gs = pygame.Surface((glow.width, glow.height), pygame.SRCALPHA)
            pygame.draw.rect(gs, (*ac, 80), (0, 0, glow.width, glow.height), border_radius=22)
            surface.blit(gs, glow.topleft)
        pygame.draw.rect(surface, col, self.rect, border_radius=22)
        pygame.draw.rect(surface, ac, self.rect, 2, border_radius=22)
        label = font.render(self.text, True, (245, 245, 255))
        surface.blit(label, label.get_rect(center=self.rect.center))

    def clicked(self, event):
        return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos)

# ─────────────────────────────────────────────
#  PARTICLES
# ─────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, color):
        self.x, self.y = x, y; self.color = color
        angle = random.uniform(0, math.pi * 2); speed = random.uniform(2, 7)
        self.vx = math.cos(angle) * speed; self.vy = math.sin(angle) * speed
        self.life = random.randint(15, 35); self.max_life = self.life
        self.r = random.randint(3, 7)

    def update(self):
        self.x += self.vx; self.y += self.vy
        self.vy += 0.2; self.vx *= 0.95; self.vy *= 0.95; self.life -= 1

    def draw(self, surface):
        a = int(255 * self.life / self.max_life)
        s = pygame.Surface((self.r * 2, self.r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, a), (self.r, self.r), self.r)
        surface.blit(s, (int(self.x) - self.r, int(self.y) - self.r))

# ─────────────────────────────────────────────
#  DRAW IN-GAME HUD  (no overlap version)
# ─────────────────────────────────────────────
def draw_game_hud(screen, p1, p2, arena, tick, BODY_FONT, SMALL_FONT, TINY_FONT):
    PAD = 18
    PW = 320   # panel width
    PH = 160   # panel height

    # ── P1 panel — top-left ──
    p1r = pygame.Rect(PAD, PAD, PW, PH)
    draw_panel(screen, p1r, (8, 16, 30), 210, 14, (80, 140, 200))
    # player color dot
    pygame.draw.circle(screen, p1.color, (p1r.x + 22, p1r.y + 24), 10)
    pygame.draw.circle(screen, p1.glow_color, (p1r.x + 22, p1r.y + 24), 10, 2)
    draw_text_shadow(screen, "PLAYER 1", BODY_FONT, (120, 200, 255), (p1r.x + 38, p1r.y + 14))
    # HP label + bar
    draw_text_shadow(screen, "HP", TINY_FONT, (160, 220, 160), (p1r.x + PAD, p1r.y + 50))
    hp1 = max(0, p1.health / p1.max_health)
    hp1_col = (int(40 + 200 * (1 - hp1)), int(180 * hp1), 40)
    draw_hud_bar(screen, p1r.x + 48, p1r.y + 52, PW - 66, 14, hp1, hp1_col, border=(80,140,80))
    hp_txt = TINY_FONT.render(f"{int(p1.health)}/{p1.max_health}", True, (200,240,200))
    hp_txt_x = p1r.x + 48 + (PW - 66) - hp_txt.get_width() - 8
    screen.blit(hp_txt, (hp_txt_x, p1r.y + 50))
    # Stamina bar
    draw_text_shadow(screen, "SP", TINY_FONT, (100, 180, 230), (p1r.x + PAD, p1r.y + 76))
    draw_hud_bar(screen, p1r.x + 48, p1r.y + 78, PW - 66, 10, p1.stamina / p1.max_stamina,
                 (60, 180, 230), border=(60,130,180))
    # Weapon icon + name + ammo
    spr = p1.weapon.get_sprite()
    wy = p1r.y + 102
    if spr:
        spr_s = pygame.transform.scale(spr, (40, int(40 * spr.get_height() / spr.get_width())))
        screen.blit(spr_s, (p1r.x + PAD, wy))
    draw_text_shadow(screen, p1.weapon.name, SMALL_FONT, p1.weapon.color, (p1r.x + 62, wy + 2))
    if p1.weapon.projectile:
        ammo_col = (255, 200, 80) if p1.display_ammo() != "∞" and p1.ammo <= 3 else (200, 200, 200)
        draw_text_shadow(screen, f"Ammo: {p1.display_ammo()}", SMALL_FONT, ammo_col, (p1r.x + 62, wy + 24))

    # ── P2 panel — top-right ──
    p2r = pygame.Rect(WIDTH - PAD - PW, PAD, PW, PH)
    draw_panel(screen, p2r, (30, 14, 8), 210, 14, (200, 130, 80))
    pygame.draw.circle(screen, p2.color, (p2r.x + PW - 22, p2r.y + 24), 10)
    pygame.draw.circle(screen, p2.glow_color, (p2r.x + PW - 22, p2r.y + 24), 10, 2)
    p2_label = BODY_FONT.render("PLAYER 2", True, (255, 170, 100))
    screen.blit(p2_label, (p2r.x + PW - 38 - p2_label.get_width(), p2r.y + 14))
    # HP
    draw_text_shadow(screen, "HP", TINY_FONT, (220, 160, 100), (p2r.x + PAD, p2r.y + 50))
    hp2 = max(0, p2.health / p2.max_health)
    hp2_col = (int(40 + 200 * (1 - hp2)), int(180 * hp2), 40)
    draw_hud_bar(screen, p2r.x + 48, p2r.y + 52, PW - 66, 14, hp2, hp2_col, border=(140,80,40))
    hp_txt2 = TINY_FONT.render(f"{int(p2.health)}/{p2.max_health}", True, (240,210,180))
    hp_txt2_x = p2r.x + 48 + (PW - 66) - hp_txt2.get_width() - 8
    screen.blit(hp_txt2, (hp_txt2_x, p2r.y + 50))
    # Stamina
    draw_text_shadow(screen, "SP", TINY_FONT, (200, 140, 80), (p2r.x + PAD, p2r.y + 76))
    draw_hud_bar(screen, p2r.x + 48, p2r.y + 78, PW - 66, 10, p2.stamina / p2.max_stamina,
                 (230, 140, 60), border=(180,110,50))
    # Weapon
    spr2 = p2.weapon.get_sprite()
    wy2 = p2r.y + 102
    if spr2:
        spr2_s = pygame.transform.scale(spr2, (40, int(40 * spr2.get_height() / spr2.get_width())))
        screen.blit(spr2_s, (p2r.x + PAD, wy2))
    draw_text_shadow(screen, p2.weapon.name, SMALL_FONT, p2.weapon.color, (p2r.x + 62, wy2 + 2))
    if p2.weapon.projectile:
        ammo2_col = (255, 200, 80) if p2.display_ammo() != "∞" and p2.ammo <= 3 else (200, 200, 200)
        draw_text_shadow(screen, f"Ammo: {p2.display_ammo()}", SMALL_FONT, ammo2_col, (p2r.x + 62, wy2 + 24))

    # ── Map name — top-center ──
    map_label = SMALL_FONT.render(arena.map.name, True, (220, 220, 255))
    map_label_rect = map_label.get_rect(center=(WIDTH // 2, 32))
    draw_text_shadow(screen, arena.map.name, SMALL_FONT, (220, 220, 255), map_label_rect.topleft, shadow=(2, 2))

    # ── Controls reminder — bottom-center, compact ──
    bottom_r = pygame.Rect(WIDTH // 2 - 480, HEIGHT - 52, 960, 38)
    draw_panel(screen, bottom_r, (6, 6, 18), 180, 10, (50, 50, 90))
    ctrl = TINY_FONT.render(
        "P1: WASD Move  LSHIFT Sprint  Q Dash  F Melee  E Shoot        "
        "P2: Arrows Move  RSHIFT Sprint  / Dash  RCTRL Melee  . Shoot",
        True, (140, 140, 180))
    screen.blit(ctrl, ctrl.get_rect(center=bottom_r.center))

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Arena Fighters")
    clock = pygame.time.Clock()

    TITLE_FONT  = pygame.font.SysFont("arialblack", 96)
    HEADER_FONT = pygame.font.SysFont("arialblack", 48)
    MENU_FONT   = pygame.font.SysFont(None, 46)
    BODY_FONT   = pygame.font.SysFont("arialblack", 22)
    SMALL_FONT  = pygame.font.SysFont(None, 28)
    TINY_FONT   = pygame.font.SysFont(None, 22)

    MENU, GAME, GAME_OVER, PAUSE = 0, 1, 2, 3
    state = MENU
    selected_map = 0
    winner_text = ""
    winner_color = (255, 220, 80)

    # menu background
    menu_bg = pygame.Surface((WIDTH, HEIGHT))
    for y in range(HEIGHT):
        t = y / HEIGHT
        c = (int(8 + t * 22), int(8 + t * 20), int(30 + t * 60))
        pygame.draw.line(menu_bg, c, (0, y), (WIDTH, y))
    for gx in range(0, WIDTH, 80):
        pygame.draw.line(menu_bg, (30, 30, 60), (gx, 0), (gx, HEIGHT))
    for gy in range(0, HEIGHT, 80):
        pygame.draw.line(menu_bg, (30, 30, 60), (0, gy), (WIDTH, gy))

    BTN_W, BTN_H = 380, 72
    cx = WIDTH // 2
    start_btn   = Button("Start Battle", cx - BTN_W // 2, HEIGHT // 2 + 80, BTN_W, BTN_H,
                         (35, 30, 70), (180, 140, 255))
    exit_btn    = Button("Exit",          cx - BTN_W // 2, HEIGHT // 2 + 170, BTN_W, BTN_H,
                         (60, 20, 20), (220, 80, 80))
    rematch_btn = Button("Rematch",      cx - BTN_W // 2, HEIGHT // 2 + 30,  BTN_W, BTN_H,
                         (35, 30, 70), (180, 140, 255))
    menu_btn    = Button("Main Menu",    cx - BTN_W // 2, HEIGHT // 2 + 120, BTN_W, BTN_H,
                         (20, 40, 60), (80, 180, 255))
    go_exit_btn = Button("Exit",          cx - BTN_W // 2, HEIGHT // 2 + 210, BTN_W, BTN_H,
                         (60, 20, 20), (220, 80, 80))
    resume_btn  = Button("Resume",        cx - BTN_W // 2, HEIGHT // 2 + 10,  BTN_W, BTN_H,
                         (35, 30, 70), (180, 140, 255))
    pause_menu_btn = Button("Main Menu",   cx - BTN_W // 2, HEIGHT // 2 + 100, BTN_W, BTN_H,
                         (20, 40, 60), (80, 180, 255))
    pause_exit_btn = Button("Exit",        cx - BTN_W // 2, HEIGHT // 2 + 190, BTN_W, BTN_H,
                         (60, 20, 20), (220, 80, 80))

    MAP_BW, MAP_BH = 330, 64
    map_btns = [
        Button(MAP_NAMES[i],
               cx - 700 + i * 352, HEIGHT // 2 - 60,
               MAP_BW, MAP_BH,
               [(30,40,30),(50,28,10),(20,18,50),(5,5,20)][i],
               [(80,220,80),(255,140,40),(160,120,255),(0,220,200)][i])
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
        bullets = []; particles = []; winner_text = ""

    def spawn_particles(x, y, color, n=12):
        for _ in range(n): particles.append(Particle(x, y, color))

    tick = 0
    running = True

    while running:
        tick += 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if state == MENU:
                if start_btn.clicked(event):
                    arena.switch_map(selected_map); reset_game(); state = GAME
                if exit_btn.clicked(event): running = False
                for i, mb in enumerate(map_btns):
                    if mb.clicked(event): selected_map = i

            elif state == GAME_OVER:
                if rematch_btn.clicked(event): reset_game(); state = GAME
                if menu_btn.clicked(event): state = MENU
                if go_exit_btn.clicked(event): running = False
            elif state == PAUSE:
                if resume_btn.clicked(event): state = GAME
                if pause_menu_btn.clicked(event): state = MENU
                if pause_exit_btn.clicked(event): running = False

            if event.type == pygame.KEYDOWN:
                if state == GAME and event.key == pygame.K_ESCAPE:
                    state = PAUSE
                elif state == PAUSE and event.key == pygame.K_ESCAPE:
                    state = GAME

        keys = pygame.key.get_pressed()

        # ── MENU ──
        if state == MENU:
            screen.blit(menu_bg, (0, 0))
            if tick % 4 == 0:
                particles.append(Particle(random.randint(0, WIDTH), random.randint(0, HEIGHT), (180, 160, 255)))
            for pt in particles[:]:
                pt.update(); pt.draw(screen)
                if pt.life <= 0: particles.remove(pt)

            # title
            title_surf = TITLE_FONT.render("ARENA FIGHTERS", True, (220, 210, 255))
            tx = cx - title_surf.get_width() // 2
            draw_text_shadow(screen, "ARENA FIGHTERS", TITLE_FONT, (220, 210, 255), (tx, 60))
            sub = SMALL_FONT.render("Choose your arena and fight!", True, (180, 180, 220))
            screen.blit(sub, sub.get_rect(center=(cx, 178)))

            # weapon showcase strip
            strip_r = pygame.Rect(cx - 520, 210, 1040, 90)
            draw_panel(screen, strip_r, (10, 10, 30), 180, 12, (70, 70, 110))
            wlabel = TINY_FONT.render("AVAILABLE WEAPONS", True, (160, 160, 200))
            screen.blit(wlabel, wlabel.get_rect(center=(cx, 222)))
            for wi, wt in enumerate(WEAPON_TYPES):
                spr = wt.get_sprite()
                wx_center = cx - 440 + wi * 220
                if spr:
                    spr_big = pygame.transform.scale(spr, (56, int(56 * spr.get_height() / spr.get_width())))
                    screen.blit(spr_big, spr_big.get_rect(center=(wx_center, 258)))
                wname = TINY_FONT.render(wt.name, True, wt.color)
                screen.blit(wname, wname.get_rect(center=(wx_center, 282)))

            # map buttons
            map_section_label = SMALL_FONT.render("SELECT MAP", True, (180, 180, 220))
            screen.blit(map_section_label, map_section_label.get_rect(center=(cx, HEIGHT // 2 - 90)))
            for i, mb in enumerate(map_btns):
                is_active = (i == selected_map)
                ac = mb.accent if is_active else (70, 70, 100)
                if is_active:
                    gr = mb.rect.inflate(16, 16)
                    gs = pygame.Surface((gr.width, gr.height), pygame.SRCALPHA)
                    pygame.draw.rect(gs, (*mb.accent, 60), (0, 0, gr.width, gr.height), border_radius=20)
                    screen.blit(gs, gr.topleft)
                mb.draw(screen, MENU_FONT, ac)
                desc = TINY_FONT.render(MAP_DESCRIPTIONS[i], True, (160, 160, 190))
                screen.blit(desc, desc.get_rect(center=(mb.rect.centerx, mb.rect.bottom + 18)))

            # control guide
            ctrl_r = pygame.Rect(cx - 580, HEIGHT - 170, 1160, 100)
            draw_panel(screen, ctrl_r, (8, 8, 22), 200, 12, (60, 60, 100))
            ctrl_title = TINY_FONT.render("CONTROLS", True, (160, 160, 200))
            screen.blit(ctrl_title, ctrl_title.get_rect(center=(cx, HEIGHT - 158)))
            for li, (tag, txt, col) in enumerate([
                ("P1", "WASD Move  |  LSHIFT Sprint  |  Q Dash  |  F Melee  |  E Shoot", (140, 200, 255)),
                ("P2", "Arrows Move  |  RSHIFT Sprint  |  / Dash  |  RCTRL Melee  |  . Shoot", (255, 180, 120)),
            ]):
                ts = SMALL_FONT.render(f"[{tag}]  {txt}", True, col)
                screen.blit(ts, ts.get_rect(center=(cx, HEIGHT - 130 + li * 34)))

            start_btn.draw(screen, MENU_FONT)
            exit_btn.draw(screen, MENU_FONT)

            if keys[pygame.K_RETURN]: arena.switch_map(selected_map); reset_game(); state = GAME
            if keys[pygame.K_ESCAPE]: running = False

        # ── GAME ──
        elif state == GAME:
            arena.update()

            dx1 = keys[pygame.K_d] - keys[pygame.K_a]
            dy1 = keys[pygame.K_s] - keys[pygame.K_w]
            sprint1 = keys[pygame.K_LSHIFT]
            if keys[pygame.K_q]: p1.start_dash(dx1, dy1)
            if keys[pygame.K_f]: p1.start_attack(dx1, dy1)
            if keys[pygame.K_e]:
                b = p1.start_shoot()
                if b: bullets.append(b)
            p1.move(dx1, dy1, sprint1, arena)

            dx2 = keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]
            dy2 = keys[pygame.K_DOWN]  - keys[pygame.K_UP]
            sprint2 = keys[pygame.K_RSHIFT]
            if keys[pygame.K_SLASH] or keys[pygame.K_QUESTION]: p2.start_dash(dx2, dy2)
            if keys[pygame.K_RCTRL]: p2.start_attack(dx2, dy2)
            if keys[pygame.K_PERIOD]:
                b = p2.start_shoot()
                if b: bullets.append(b)
            p2.move(dx2, dy2, sprint2, arena)

            p1.update(); p2.update()
            arena.resolve_obstacle_collision(p1)
            arena.resolve_obstacle_collision(p2)
            resolve_player_collision(p1, p2)

            for attacker, defender in [(p1, p2), (p2, p1)]:
                if attacker.attack_active() and not attacker.attack_hit_registered:
                    ax = attacker.x + attacker.facing_dx * attacker.attack_range
                    ay = attacker.y + attacker.facing_dy * attacker.attack_range
                    if defender.collides_with(ax, ay, 20):
                        defender.take_hit(attacker.attack_damage)
                        attacker.attack_hit_registered = True
                        spawn_particles(defender.x, defender.y, (255, 80, 80))

            for pickup in arena.weapon_pickups[:]:
                if pickup.check_pickup(p1):
                    spawn_particles(pickup.x, pickup.y, pickup.weapon.color, 10)
                    p1.pick_weapon(pickup.weapon); arena.weapon_pickups.remove(pickup)
                elif pickup.check_pickup(p2):
                    spawn_particles(pickup.x, pickup.y, pickup.weapon.color, 10)
                    p2.pick_weapon(pickup.weapon); arena.weapon_pickups.remove(pickup)

            for bullet in bullets[:]:
                bullet.update(); hit = False
                if not arena.map.is_within_bounds(bullet.x, bullet.y, bullet.radius):
                    hit = True
                elif arena.map.collides_with_obstacle(bullet.x, bullet.y, bullet.radius):
                    spawn_particles(bullet.x, bullet.y, bullet.color, 6); hit = True
                elif bullet.owner is not p1 and p1.collides_with(bullet.x, bullet.y, bullet.radius):
                    p1.take_hit(bullet.damage); spawn_particles(p1.x, p1.y, (255, 80, 80), 10); hit = True
                elif bullet.owner is not p2 and p2.collides_with(bullet.x, bullet.y, bullet.radius):
                    p2.take_hit(bullet.damage); spawn_particles(p2.x, p2.y, (255, 80, 80), 10); hit = True
                if hit: bullets.remove(bullet)

            for pt in particles[:]:
                pt.update()
                if pt.life <= 0: particles.remove(pt)

            arena.draw(screen, tick)
            for pt in particles: pt.draw(screen)
            for b in bullets: b.draw(screen)
            p1.draw(screen); p2.draw(screen)

            draw_game_hud(screen, p1, p2, arena, tick, BODY_FONT, SMALL_FONT, TINY_FONT)

            if p1.is_dead() or p2.is_dead():
                if p1.is_dead():
                    winner_text = "PLAYER 2 WINS!"; winner_color = (255, 170, 80)
                    spawn_particles(p2.x, p2.y, (255, 220, 60), 30)
                else:
                    winner_text = "PLAYER 1 WINS!"; winner_color = (100, 210, 255)
                    spawn_particles(p1.x, p1.y, (100, 200, 255), 30)
                state = GAME_OVER

        # ── GAME OVER ──
        elif state == GAME_OVER:
            arena.draw(screen, tick)
            for pt in particles[:]:
                pt.update(); pt.draw(screen)
                if pt.life <= 0: particles.remove(pt)

            if tick % 18 == 0:
                for _ in range(16):
                    particles.append(Particle(
                        random.randint(WIDTH // 4, 3 * WIDTH // 4),
                        random.randint(HEIGHT // 4, 3 * HEIGHT // 4),
                        random.choice([(255,220,60),(100,220,255),(255,100,180),(80,255,120)])))

            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((96, 96, 96, 160))
            screen.blit(overlay, (0, 0))

            tw = TITLE_FONT.render(winner_text, True, winner_color)
            screen.blit(tw, tw.get_rect(center=(cx, HEIGHT // 2 - 100)))

            sub2 = HEADER_FONT.render("GG!", True, (200, 200, 255))
            screen.blit(sub2, sub2.get_rect(center=(cx, HEIGHT // 2 - 20)))

            rematch_btn.draw(screen, MENU_FONT)
            menu_btn.draw(screen, MENU_FONT)
            go_exit_btn.draw(screen, MENU_FONT)

        # ── PAUSE ──
        elif state == PAUSE:
            arena.draw(screen, tick)
            for pt in particles:
                pt.draw(screen)
            for b in bullets:
                b.draw(screen)
            p1.draw(screen); p2.draw(screen)
            draw_game_hud(screen, p1, p2, arena, tick, BODY_FONT, SMALL_FONT, TINY_FONT)

            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((96, 96, 96, 150))
            screen.blit(overlay, (0, 0))

            pause_title = TITLE_FONT.render("PAUSED", True, (230, 230, 255))
            screen.blit(pause_title, pause_title.get_rect(center=(cx, HEIGHT // 2 - 90)))
            pause_hint = SMALL_FONT.render("Press Esc to resume", True, (180, 180, 220))
            screen.blit(pause_hint, pause_hint.get_rect(center=(cx, HEIGHT // 2 - 28)))

            resume_btn.draw(screen, MENU_FONT)
            pause_menu_btn.draw(screen, MENU_FONT)
            pause_exit_btn.draw(screen, MENU_FONT)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()