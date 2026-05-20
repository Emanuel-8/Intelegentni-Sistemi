import pygame
import math
import random
 
if __package__ is None or __package__ == "":
    from settings import *
else:
    from .settings import *
 
 
# ──────────────────────────────────────────────────────────────────────────────
#  OBSTACLE BASE
# ──────────────────────────────────────────────────────────────────────────────
class Obstacle:
    def collide_point(self, x, y):
        return False
 
    def collide_circle(self, cx, cy, r):
        return False
 
    def draw(self, surface):
        pass
 
 
class RectObstacle(Obstacle):
    def __init__(self, x, y, w, h, color, border_color=None):
        self.rect  = pygame.Rect(x, y, w, h)
        self.color = color
        self.border_color = border_color or tuple(max(0, c-40) for c in color)
 
    def collide_point(self, x, y):
        return self.rect.collidepoint(x, y)
 
    def collide_circle(self, cx, cy, r):
        # closest point on rect
        nearest_x = max(self.rect.left, min(cx, self.rect.right))
        nearest_y = max(self.rect.top,  min(cy, self.rect.bottom))
        return math.hypot(cx - nearest_x, cy - nearest_y) < r
 
    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect)
        pygame.draw.rect(surface, self.border_color, self.rect, 2)
 
 
class CircleObstacle(Obstacle):
    def __init__(self, x, y, r, color, border_color=None):
        self.x = x
        self.y = y
        self.r = r
        self.color = color
        self.border_color = border_color or tuple(max(0, c-40) for c in color)
 
    def collide_point(self, x, y):
        return math.hypot(x - self.x, y - self.y) < self.r
 
    def collide_circle(self, cx, cy, cr):
        return math.hypot(cx - self.x, cy - self.y) < self.r + cr
 
    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (self.x, self.y), self.r)
        pygame.draw.circle(surface, self.border_color, (self.x, self.y), self.r, 2)
 
 
# ──────────────────────────────────────────────────────────────────────────────
#  MAP BACKGROUNDS  (drawn before obstacles)
# ──────────────────────────────────────────────────────────────────────────────
def _draw_desert_bg(surface):
    surface.fill((194, 154, 90))
    # sand dune lines
    for i in range(0, SCREEN_H, 40):
        alpha = 30
        col = (210, 170, 100) if (i // 40) % 2 == 0 else (180, 140, 70)
        pygame.draw.line(surface, col, (0, i), (SCREEN_W, i + 20), 40)
    # grit noise (static)
    random.seed(42)
    for _ in range(400):
        gx = random.randint(0, SCREEN_W)
        gy = random.randint(0, SCREEN_H)
        pygame.draw.circle(surface, (160, 120, 60), (gx, gy), 1)
 
 
def _draw_dungeon_bg(surface):
    surface.fill((28, 22, 38))
    # stone tiles
    TILE = 60
    for row in range(SCREEN_H // TILE + 1):
        for col in range(SCREEN_W // TILE + 1):
            x = col * TILE + (20 if row % 2 else 0)
            y = row * TILE
            c = 35 if (row + col) % 2 == 0 else 30
            pygame.draw.rect(surface, (c, c, c+4), (x, y, TILE-2, TILE-2))
    # subtle vignette
    vsurf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    for i in range(80):
        alpha = i * 2
        r = max(SCREEN_W, SCREEN_H) - i * 5
        pygame.draw.rect(vsurf, (0, 0, 0, alpha),
                         (i*3, i*2, SCREEN_W - i*6, SCREEN_H - i*4), 4)
    surface.blit(vsurf, (0, 0))
 
 
def _draw_forest_bg(surface):
    surface.fill((44, 78, 44))
    # grass patches
    random.seed(7)
    for _ in range(300):
        gx = random.randint(0, SCREEN_W)
        gy = random.randint(0, SCREEN_H)
        gr = random.randint(10, 30)
        shade = random.randint(0, 2)
        col = [(38,72,38),(52,88,46),(30,60,30)][shade]
        pygame.draw.ellipse(surface, col, (gx-gr, gy-gr//2, gr*2, gr))
 
 
# ──────────────────────────────────────────────────────────────────────────────
#  MAP DEFINITIONS
# ──────────────────────────────────────────────────────────────────────────────
def _make_desert_map():
    obs = [
        # ruined walls
        RectObstacle(100, 80,  160, 22,  (160, 120, 60), (120,90,40)),
        RectObstacle(100, 80,  22,  120, (160, 120, 60), (120,90,40)),
        RectObstacle(640, 80,  160, 22,  (160, 120, 60), (120,90,40)),
        RectObstacle(778, 80,  22,  120, (160, 120, 60), (120,90,40)),
        RectObstacle(100, 500, 160, 22,  (160, 120, 60), (120,90,40)),
        RectObstacle(100, 400, 22,  122, (160, 120, 60), (120,90,40)),
        RectObstacle(640, 500, 160, 22,  (160, 120, 60), (120,90,40)),
        RectObstacle(778, 400, 22,  122, (160, 120, 60), (120,90,40)),
        # center rocks
        CircleObstacle(450, 325, 38, (140,105,50), (100,75,30)),
        CircleObstacle(390, 290, 22, (148,110,55), (108,80,35)),
        CircleObstacle(510, 360, 18, (138,100,48), (98,70,28)),
        # side rocks
        CircleObstacle(200, 300, 28, (145,108,52)),
        CircleObstacle(700, 320, 28, (145,108,52)),
    ]
    spawn_pts = [
        (300,200),(600,200),(150,400),(750,400),
        (450,150),(450,500),(250,500),(650,100),
    ]
    return obs, spawn_pts, _draw_desert_bg
 
 
def _make_dungeon_map():
    W_COL = (70, 65, 80)
    obs = [
        # cross pillars
        RectObstacle(210, 140, 50, 130, W_COL),
        RectObstacle(640, 140, 50, 130, W_COL),
        RectObstacle(210, 380, 50, 130, W_COL),
        RectObstacle(640, 380, 50, 130, W_COL),
        # center wall segments
        RectObstacle(370, 200, 160, 24,  W_COL),
        RectObstacle(370, 426, 160, 24,  W_COL),
        RectObstacle(180, 300, 24,  50,  W_COL),
        RectObstacle(696, 300, 24,  50,  W_COL),
        # corner pillars (small)
        CircleObstacle(450, 325, 30, (55,50,65),(30,25,40)),
    ]
    spawn_pts = [
        (100,100),(800,100),(100,550),(800,550),
        (450,100),(450,550),(150,325),(750,325),
    ]
    return obs, spawn_pts, _draw_dungeon_bg
 
 
def _make_forest_map():
    TRUNK = (60, 40, 20)
    ROCK  = (90, 95, 80)
    obs = [
        # trees (circles)
        CircleObstacle(150, 120, 30, (34,60,28), (20,44,16)),
        CircleObstacle(720, 150, 28, (34,60,28), (20,44,16)),
        CircleObstacle(180, 500, 32, (34,60,28), (20,44,16)),
        CircleObstacle(740, 480, 30, (34,60,28), (20,44,16)),
        CircleObstacle(400, 100, 26, (34,60,28), (20,44,16)),
        CircleObstacle(380, 550, 26, (34,60,28), (20,44,16)),
        # rock clusters
        CircleObstacle(340, 280, 22, ROCK),
        CircleObstacle(370, 300, 18, ROCK),
        CircleObstacle(355, 260, 14, ROCK),
        CircleObstacle(560, 360, 20, ROCK),
        CircleObstacle(585, 380, 16, ROCK),
        # log barrier
        RectObstacle(250, 380, 140, 20, TRUNK, (40,25,10)),
        RectObstacle(520, 180, 20, 110, TRUNK, (40,25,10)),
    ]
    spawn_pts = [
        (300,200),(620,200),(280,440),(640,440),
        (450,300),(150,300),(700,300),(450,500),
    ]
    return obs, spawn_pts, _draw_forest_bg
 
 
MAP_BUILDERS = [_make_desert_map, _make_dungeon_map, _make_forest_map]
MAP_NAMES    = ["DESERT RUINS", "STONE DUNGEON", "DARK FOREST"]
 
 
# ──────────────────────────────────────────────────────────────────────────────
#  ARENA ENV
# ──────────────────────────────────────────────────────────────────────────────
class Arenaenv:
    def __init__(self, player, map_id=MAP_DESERT):
        self.width  = SCREEN_W
        self.height = SCREEN_H
        self.player = player
 
        self._bg_surface = pygame.Surface((SCREEN_W, SCREEN_H))
        self.load_map(map_id)
 
    def load_map(self, map_id):
        self.map_id = map_id
        obs, spawn_pts, bg_fn = MAP_BUILDERS[map_id]()
        self.obstacles   = obs
        self.spawn_points= spawn_pts
 
        bg_fn(self._bg_surface)   # render background once
 
    def border(self):
        p = self.player
        p.x = max(p.radius, min(p.x, self.width  - p.radius))
        p.y = max(p.radius, min(p.y, self.height - p.radius))
 
    def resolve_player_obstacles(self):
        """Push player out of any overlapping obstacles."""
        p = self.player
        for obs in self.obstacles:
            if isinstance(obs, RectObstacle):
                if obs.collide_circle(p.x, p.y, p.radius):
                    # find overlap direction
                    nearest_x = max(obs.rect.left, min(p.x, obs.rect.right))
                    nearest_y = max(obs.rect.top,  min(p.y, obs.rect.bottom))
                    dx = p.x - nearest_x
                    dy = p.y - nearest_y
                    dist = math.hypot(dx, dy)
                    if dist == 0:
                        dx, dy, dist = 1, 0, 1
                    overlap = p.radius - dist
                    p.x += dx / dist * overlap
                    p.y += dy / dist * overlap
            elif isinstance(obs, CircleObstacle):
                dist = math.hypot(p.x - obs.x, p.y - obs.y)
                min_dist = p.radius + obs.r
                if dist < min_dist:
                    if dist == 0:
                        p.x += min_dist
                    else:
                        push = (min_dist - dist) / dist
                        p.x += (p.x - obs.x) * push
                        p.y += (p.y - obs.y) * push
 
    def draw_background(self, surface):
        surface.blit(self._bg_surface, (0, 0))
 
    def draw_obstacles(self, surface):
        for obs in self.obstacles:
            obs.draw(surface)
 
    def get_state(self):
        return [self.player.x, self.player.y, self.player.stamina,
                self.player.hp, self.map_id]
 