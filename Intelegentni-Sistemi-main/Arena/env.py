import math

class Arenaenv:
    
    def __init__(self, player):
        self.width = 1920
        self.height = 1080
        self.player = player

    def border(self):
        r = self.player.radius
        self.player.x = max(r, min(self.player.x, self.width - r))
        self.player.y = max(r, min(self.player.y, self.height - r))

    def get_state(self):
        return [self.player.x, self.player.y, self.player.stamina]


def resolve_collision(p1, p2):
    dx = p2.x - p1.x
    dy = p2.y - p1.y

    distance = math.hypot(dx, dy)
    min_distance = p1.radius + p2.radius

    if distance == 0:
        dx, dy = 1, 0
        distance = 1

    if distance < min_distance:
        # overlap amount
        overlap = min_distance - distance

        # normalize direction
        nx = dx / distance
        ny = dy / distance

        # push both players away equally
        p1.x -= nx * overlap / 2
        p1.y -= ny * overlap / 2

        p2.x += nx * overlap / 2
        p2.y += ny * overlap / 2