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

        self.radius = 20

    def move(self, dx, dy, sprint):

        if self.dash_timer > 0:
            self.x += self.dash_dx * self.dash_speed
            self.y += self.dash_dy * self.dash_speed
            self.dash_timer -= 1
            self.cooldown_timer -= 1
            return
            
        length=math.hypot(dx,dy)

        if length != 0:
            dx /= length
            dy /= length

        if sprint and self.stamina > 0:
            speed = self.sprint_speed
            self.stamina -= self.stamina_drain
        else:
            speed = self.walk_speed
            self.stamina = min(self.max_stamina, self.stamina + self.stamina_regen)
        
        self.x += dx * speed
        self.y += dy * speed

        if self.cooldown_timer > 0:
            self.cooldown_timer -=1

    def start_dash(self, dx, dy):
        if self.cooldown_timer > 0 or self.dash_timer > 0:
            return
    
        if self.stamina < self.dash_stamina_cost:
            return

        if dx == 0 and dy == 0:
            return

        length=math.hypot(dx,dy)

        if length != 0:
            dx /= length
            dy /= length

        self.dash_dx = dx
        self.dash_dy = dy
        self.dash_timer = self.dash_duration
        self.cooldown_timer = self.dash_cooldown

        self.stamina -= self.dash_stamina_cost