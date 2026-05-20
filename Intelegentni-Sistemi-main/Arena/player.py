
import math
 
if __package__ is None or __package__ == "":
    from settings import *
else:
    from .settings import *
 
 
class Player:
    def __init__(self, x, y, color=(0, 200, 255)):
        self.x = x
        self.y = y
        self.color = color
        self.radius = PLAYER_RADIUS
 
        self.walk_speed   = PLAYER_WALK_SPEED
        self.sprint_speed = PLAYER_SPRINT_SPEED
 
        self.max_stamina   = PLAYER_STAMINA_MAX
        self.stamina       = PLAYER_STAMINA_MAX
        self.stamina_drain = PLAYER_STAMINA_DRAIN
        self.stamina_regen = PLAYER_STAMINA_REGEN
 
        self.dash_speed    = PLAYER_DASH_SPEED
        self.dash_duration = PLAYER_DASH_DURATION
        self.dash_cooldown = PLAYER_DASH_COOLDOWN
        self.dash_stamina_cost = PLAYER_DASH_COST
 
        self.dash_timer    = 0
        self.cooldown_timer= 0
        self.dash_dx       = 0
        self.dash_dy       = 0
 
        self.hp     = PLAYER_MAX_HP
        self.max_hp = PLAYER_MAX_HP
 
        self.weapon         = None   # equipped Weapon instance
        self.attack_timer   = 0
        self.is_dashing     = False
 
        # trail effect
        self.trail = []
 
    # ── movement ──────────────────────────────────────────────────────────────
    def move(self, dx, dy, sprint):
        length = math.hypot(dx, dy)
        moving = length > 0
        if moving or self.is_dashing:
            self.trail.append((self.x, self.y))
            if len(self.trail) > 8:
                self.trail.pop(0)
 
        if self.dash_timer > 0:
            self.x += self.dash_dx * self.dash_speed
            self.y += self.dash_dy * self.dash_speed
            self.dash_timer -= 1
            self.cooldown_timer = max(0, self.cooldown_timer - 1)
            self.is_dashing = True
            if self.attack_timer > 0:
                self.attack_timer -= 1
            return
 
        self.is_dashing = False
        if length:
            dx /= length
            dy /= length
 
        if sprint and self.stamina > 0 and moving:
            speed = self.sprint_speed
            self.stamina = max(0, self.stamina - self.stamina_drain)
        else:
            speed = self.walk_speed
            self.stamina = min(self.max_stamina, self.stamina + self.stamina_regen)
 
        self.x += dx * speed
        self.y += dy * speed
 
        if self.cooldown_timer > 0:
            self.cooldown_timer -= 1
 
        if self.attack_timer > 0:
            self.attack_timer -= 1
 
    def start_dash(self, dx, dy):
        if self.cooldown_timer > 0 or self.dash_timer > 0:
            return
        if self.stamina < self.dash_stamina_cost:
            return
        if dx == 0 and dy == 0:
            return
 
        length = math.hypot(dx, dy)
        if length:
            dx /= length
            dy /= length
 
        self.dash_dx = dx
        self.dash_dy = dy
        self.dash_timer    = self.dash_duration
        self.cooldown_timer= self.dash_cooldown
        self.stamina      -= self.dash_stamina_cost
 
    # ── combat ────────────────────────────────────────────────────────────────
    def attack(self):
        """Return True if attack fires this frame."""
        if self.weapon is None:
            return False
        if self.attack_timer > 0:
            return False
        self.attack_timer = self.weapon.cooldown
        return True
 
    def take_damage(self, amount):
        self.hp = max(0, self.hp - amount)
 
    def is_alive(self):
        return self.hp > 0
 
    # ── serialise position for env ────────────────────────────────────────────
    def get_state(self):
        wid = self.weapon.weapon_id if self.weapon else -1
        return [self.x, self.y, self.stamina, self.hp, wid]
 