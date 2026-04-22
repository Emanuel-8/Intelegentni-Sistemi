import math

class Player:

    def __init__(self, x, y):
        self.x = x
        self.y = y

        self.walk_speed = 5
        self.sprint_speed = 9

        self.max_stamina = 100
        self.stamina = 100
        self.stamina_drain = 1.5
        self.stamina_regen = 1

        self.dash_speed = 20
        self.dash_duration = 8
        self.dash_cooldown = 120
        self.dash_stamina_cost = 20

        self.dash_timer = 0
        self.cooldown_timer = 0
        self.dash_dx = 0
        self.dash_dy = 0

        self.attack_damage = 25
        self.attack_range = 80
        self.attack_duration = 12
        self.attack_cooldown = 45
        self.attack_timer = 0
        self.attack_cooldown_timer = 0
        self.attack_hit_registered = False

        self.max_health = 100
        self.health = self.max_health

        self.radius = 30
        self.facing_dx = 1
        self.facing_dy = 0

        self.hit_timer = 0
        self.hit_flash_time = 12

    def move(self, dx, dy, sprint):

        # DASH
        if self.dash_timer > 0:
            self.x += self.dash_dx * self.dash_speed
            self.y += self.dash_dy * self.dash_speed
            self.dash_timer -= 1
            return

        # NORMAL MOVEMENT
        length = math.hypot(dx, dy)
        if length != 0:
            dx /= length
            dy /= length
            self.facing_dx = dx
            self.facing_dy = dy

        if sprint and self.stamina > 0:
            speed = self.sprint_speed
            self.stamina -= self.stamina_drain
        else:
            speed = self.walk_speed
            self.stamina = min(self.max_stamina, self.stamina + self.stamina_regen)

        self.x += dx * speed
        self.y += dy * speed

    def update(self):
        if self.cooldown_timer > 0:
            self.cooldown_timer -= 1

        if self.attack_timer > 0:
            self.attack_timer -= 1

        if self.attack_cooldown_timer > 0:
            self.attack_cooldown_timer -= 1

        if self.hit_timer > 0:
            self.hit_timer -= 1

    def start_attack(self, dx, dy):
        if self.attack_cooldown_timer > 0 or self.attack_timer > 0:
            return

        if dx == 0 and dy == 0:
            dx = self.facing_dx
            dy = self.facing_dy

        length = math.hypot(dx, dy)
        if length != 0:
            dx /= length
            dy /= length
            self.facing_dx = dx
            self.facing_dy = dy
        else:
            dx = self.facing_dx
            dy = self.facing_dy

        self.attack_timer = self.attack_duration
        self.attack_cooldown_timer = self.attack_cooldown
        self.attack_hit_registered = False

    def is_attacking(self):
        return self.attack_timer > 0

    def attack_active(self):
        return self.attack_timer > 0 and self.attack_timer <= self.attack_duration - 4

    def take_hit(self, damage):
        self.health = max(0, self.health - damage)
        self.hit_timer = self.hit_flash_time

    def is_dead(self):
        return self.health <= 0

    def start_dash(self, dx, dy):
        if self.cooldown_timer > 0 or self.dash_timer > 0:
            return

        if self.stamina < self.dash_stamina_cost:
            return

        if dx == 0 and dy == 0:
            return

        length = math.hypot(dx, dy)
        if length != 0:
            dx /= length
            dy /= length

        self.dash_dx = dx
        self.dash_dy = dy
        self.dash_timer = self.dash_duration
        self.cooldown_timer = self.dash_cooldown

        self.stamina -= self.dash_stamina_cost