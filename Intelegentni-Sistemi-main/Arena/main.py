import os
import sys
import pygame
import math
import random
 
if __package__ is None or __package__ == "":
    if "__file__" in globals():
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    else:
        arena_path = os.path.join(os.getcwd(), "Arena")
        if os.path.isdir(arena_path):
            sys.path.insert(0, arena_path)
    from settings import *
    from env import Arenaenv
    from player import Player
    from weapon import WeaponSpawner, Projectile
else:
    from .settings import *
    from .env import Arenaenv
    from .player import Player
    from .weapon import WeaponSpawner, Projectile

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption(TITLE)
clock = pygame.time.Clock()
 
# ──────────────────────────────────────────────────────────────────────────────
#  FONTS
# ──────────────────────────────────────────────────────────────────────────────
try:
    font_title  = pygame.font.SysFont("impact",   72, bold=True)
    font_sub    = pygame.font.SysFont("consolas", 22, bold=True)
    font_small  = pygame.font.SysFont("consolas", 16)
    font_hud    = pygame.font.SysFont("consolas", 18, bold=True)
except:
    font_title = font_sub = font_small = font_hud = pygame.font.SysFont(None, 36)
 
# ──────────────────────────────────────────────────────────────────────────────
#  PARTICLE SYSTEM  (menu eye-candy)
# ──────────────────────────────────────────────────────────────────────────────
class Particle:
    def __init__(self):
        self.reset()
 
    def reset(self):
        self.x   = random.uniform(0, SCREEN_W)
        self.y   = random.uniform(0, SCREEN_H)
        self.vx  = random.uniform(-0.4, 0.4)
        self.vy  = random.uniform(-0.8, -0.2)
        self.life= random.randint(80, 200)
        self.max = self.life
        self.r   = random.randint(1, 3)
        self.col = random.choice([(255,80,60),(255,160,50),(200,50,255),(50,180,255)])
 
    def update(self):
        self.x   += self.vx
        self.y   += self.vy
        self.life -= 1
        if self.life <= 0:
            self.reset()
 
    def draw(self, surface):
        alpha = int(220 * (self.life / self.max))
        s = pygame.Surface((self.r*2, self.r*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.col, alpha), (self.r, self.r), self.r)
        surface.blit(s, (int(self.x)-self.r, int(self.y)-self.r))
 
particles = [Particle() for _ in range(90)]
 
 
# ──────────────────────────────────────────────────────────────────────────────
#  DRAW HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def draw_bar(surface, x, y, w, h, ratio, full_color, empty_color=(50,50,50)):
    ratio = max(0.0, min(1.0, ratio))
    pygame.draw.rect(surface, empty_color, (x, y, w, h), border_radius=3)
    if ratio > 0:
        pygame.draw.rect(surface, full_color,
                         (x, y, int(w * ratio), h), border_radius=3)
    pygame.draw.rect(surface, (200,200,200), (x, y, w, h), 1, border_radius=3)
 
 
def draw_player(surface, player, tick):
    # dash trail
    for i, (tx, ty) in enumerate(player.trail):
        alpha = int(120 * (i / max(len(player.trail),1)))
        ts = pygame.Surface((player.radius*2, player.radius*2), pygame.SRCALPHA)
        pygame.draw.circle(ts, (*player.color, alpha),
                           (player.radius, player.radius), player.radius)
        surface.blit(ts, (int(tx)-player.radius, int(ty)-player.radius))
 
    # glow if dashing
    if player.is_dashing:
        gs = pygame.Surface((player.radius*4, player.radius*4), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*player.color, 80),
                           (player.radius*2, player.radius*2), player.radius*2)
        surface.blit(gs, (int(player.x)-player.radius*2, int(player.y)-player.radius*2))
 
    # main circle
    pygame.draw.circle(surface, player.color, (int(player.x), int(player.y)), player.radius)
    # rim
    rim = tuple(min(255, c+60) for c in player.color)
    pygame.draw.circle(surface, rim, (int(player.x), int(player.y)), player.radius, 2)
 
    BAR_W = player.radius * 2 + 6
    bx = int(player.x) - BAR_W // 2
    BAR_OFFSET = player.radius + 8
 
    # HP bar (red)
    draw_bar(surface, bx, int(player.y) - BAR_OFFSET - 10,
             BAR_W, 6, player.hp / player.max_hp, (220,50,50))
 
    # Stamina bar
    ratio = player.stamina / player.max_stamina
    if ratio > 0.5:   stam_col = (0, 210, 0)
    elif ratio > 0.25: stam_col = (230, 180, 0)
    else:              stam_col = (220, 50, 0)
    draw_bar(surface, bx, int(player.y) - BAR_OFFSET - 2,
             BAR_W, 5, ratio, stam_col)
 
    # weapon label
    if player.weapon:
        lbl = font_small.render(player.weapon.name, True, (240,240,160))
        surface.blit(lbl, (int(player.x) - lbl.get_width()//2,
                           int(player.y) + player.radius + 4))
 
 
# ──────────────────────────────────────────────────────────────────────────────
#  MENU DRAWING
# ──────────────────────────────────────────────────────────────────────────────
_menu_bg = None
def _build_menu_bg():
    global _menu_bg
    _menu_bg = pygame.Surface((SCREEN_W, SCREEN_H))
    # deep dark gradient
    for y in range(SCREEN_H):
        t = y / SCREEN_H
        r = int(8  + 12 * t)
        g = int(5  +  8 * t)
        b = int(20 + 25 * t)
        pygame.draw.line(_menu_bg, (r, g, b), (0, y), (SCREEN_W, y))
    # faint grid
    for gx in range(0, SCREEN_W, 60):
        pygame.draw.line(_menu_bg, (30, 28, 45), (gx, 0), (gx, SCREEN_H))
    for gy in range(0, SCREEN_H, 60):
        pygame.draw.line(_menu_bg, (30, 28, 45), (0, gy), (SCREEN_W, gy))
 
_build_menu_bg()
 
 
def draw_menu(surface, tick):
    surface.blit(_menu_bg, (0, 0))
 
    for p in particles:
        p.update()
        p.draw(surface)
 
    # glowing title
    pulse = 0.5 + 0.5 * math.sin(tick * 0.04)
    glow_alpha = int(80 + 60 * pulse)
    title_surf = font_title.render(TITLE, True, (255, 80, 50))
    gw, gh = title_surf.get_size()
    glow_s = pygame.Surface((gw + 40, gh + 20), pygame.SRCALPHA)
    glow_text = font_title.render(TITLE, True, (255, 120, 80, glow_alpha))
    for ox, oy in [(-3,0),(3,0),(0,-3),(0,3)]:
        glow_s.blit(glow_text, (20 + ox, 10 + oy))
    surface.blit(glow_s, (SCREEN_W//2 - (gw+40)//2, 80))
    surface.blit(title_surf, (SCREEN_W//2 - gw//2, 90))
 
    sub = font_sub.render("2D FIGHTING ARENA", True, (160, 130, 200))
    surface.blit(sub, (SCREEN_W//2 - sub.get_width()//2, 168))
 
    # divider
    pygame.draw.line(surface, (180, 60, 40),
                     (SCREEN_W//2 - 180, 200), (SCREEN_W//2 + 180, 200), 2)
 
    # menu options
    options = [
        ("[  ENTER  ]  START GAME", (255, 210, 80)),
        ("[    M    ]  SELECT MAP",  (140, 200, 255)),
        ("[   ESC   ]  QUIT",        (180, 140, 140)),
    ]
    for i, (text, col) in enumerate(options):
        blink = True
        if i == 0:
            blink = (tick // 30) % 2 == 0
        if blink:
            lbl = font_sub.render(text, True, col)
            surface.blit(lbl, (SCREEN_W//2 - lbl.get_width()//2, 240 + i*50))
 
    # version / credit
    credit = font_small.render("v0.1  |  W A S D · SHIFT · Q", True, (80,70,100))
    surface.blit(credit, (SCREEN_W//2 - credit.get_width()//2, SCREEN_H - 38))
 
 
# ──────────────────────────────────────────────────────────────────────────────
#  MAP SELECT DRAWING
# ──────────────────────────────────────────────────────────────────────────────
MAP_COLORS = [
    {"bg": (180, 140, 70),  "accent": (220, 180, 90),  "desc": "Crumbling desert ruins. Open sightlines."},
    {"bg": (38, 32, 55),    "accent": (130, 100, 200), "desc": "Ancient stone dungeon. Tight corridors."},
    {"bg": (36, 70, 36),    "accent": (80, 160, 70),   "desc": "Dense forest. Rocky clusters & logs."},
]
MAP_NAMES = ["DESERT RUINS", "STONE DUNGEON", "DARK FOREST"]
 
 
def draw_map_select(surface, selected_map, tick):
    surface.blit(_menu_bg, (0, 0))
 
    title_s = font_sub.render("SELECT MAP", True, (255, 210, 80))
    surface.blit(title_s, (SCREEN_W//2 - title_s.get_width()//2, 40))
    pygame.draw.line(surface, (200, 150, 40),
                     (SCREEN_W//2 - 160, 72), (SCREEN_W//2 + 160, 72), 2)
 
    card_w, card_h = 220, 290
    spacing = 30
    total   = 3 * card_w + 2 * spacing
    start_x = (SCREEN_W - total) // 2
 
    for i in range(3):
        mc   = MAP_COLORS[i]
        cx   = start_x + i * (card_w + spacing)
        cy   = 110
        rect = pygame.Rect(cx, cy, card_w, card_h)
 
        # card bg
        s_card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        s_card.fill((*mc["bg"], 200))
        surface.blit(s_card, (cx, cy))
 
        # selection highlight
        if i == selected_map:
            glow_tick = 0.5 + 0.5 * math.sin(tick * 0.06)
            bord_col  = tuple(int(c * (0.8 + 0.2 * glow_tick)) for c in mc["accent"])
            pygame.draw.rect(surface, bord_col, rect, 3, border_radius=6)
            sel_lbl = font_small.render("◄ SELECTED ►", True, mc["accent"])
            surface.blit(sel_lbl, (cx + card_w//2 - sel_lbl.get_width()//2, cy + card_h + 6))
        else:
            pygame.draw.rect(surface, (80, 75, 100), rect, 2, border_radius=6)
 
        # map name
        name_s = font_hud.render(MAP_NAMES[i], True, (240, 235, 255))
        surface.blit(name_s, (cx + card_w//2 - name_s.get_width()//2, cy + 16))
 
        # mini scene preview
        preview_rect = pygame.Rect(cx + 14, cy + 50, card_w - 28, 140)
        preview_surf = pygame.Surface((preview_rect.w, preview_rect.h), pygame.SRCALPHA)
        if i == 0:
            _preview_desert(preview_surf)
        elif i == 1:
            _preview_dungeon(preview_surf)
        else:
            _preview_forest(preview_surf)
        surface.blit(preview_surf, preview_rect.topleft)
 
        # description
        words = mc["desc"].split(".")
        for j, word in enumerate(words):
            if word.strip():
                d_lbl = font_small.render(word.strip()+".", True, (200, 195, 220))
                surface.blit(d_lbl, (cx + card_w//2 - d_lbl.get_width()//2,
                                     cy + 202 + j * 20))
 
    hint1 = font_sub.render("[ ← → ]  choose   [ ENTER ]  confirm", True, (160, 155, 200))
    surface.blit(hint1, (SCREEN_W//2 - hint1.get_width()//2, SCREEN_H - 55))
    hint2 = font_small.render("[ ESC ] back to menu", True, (100, 95, 130))
    surface.blit(hint2, (SCREEN_W//2 - hint2.get_width()//2, SCREEN_H - 28))
 
 
def _preview_desert(surface):
    r = surface.get_rect()
    surface.fill((180, 145, 80))
    pygame.draw.circle(surface, (140, 108, 48), (r.w//2, r.h//2), 20)
    pygame.draw.rect(surface, (150,115,55), (20, 20, 70, 12))
    pygame.draw.rect(surface, (150,115,55), (r.w-90, r.h-32, 70, 12))
 
 
def _preview_dungeon(surface):
    r = surface.get_rect()
    surface.fill((25, 20, 35))
    for row in range(r.h//20 + 1):
        for col in range(r.w//20 + 1):
            c = 42 if (row + col) % 2 == 0 else 36
            pygame.draw.rect(surface, (c, c, c + 5),
                             (col * 20, row * 20, 18, 18))
    pygame.draw.rect(surface, (60, 55, 75), (20, 20, 20, 55))
    pygame.draw.rect(surface, (60, 55, 75), (r.w - 40, 20, 20, 55))
 
 
def _preview_forest(surface):
    r = surface.get_rect()
    surface.fill((40, 72, 40))
    for tx, ty, tr in [(30, 35, 18), (r.w-40, 30, 16),
                       (r.w//2, 20, 14)]:
        pygame.draw.circle(surface, (30, 58, 28), (tx, ty), tr)
    pygame.draw.rect(surface, (60, 40, 18), (50, r.h-40, 60, 12))
 
 
# ──────────────────────────────────────────────────────────────────────────────
#  GAME HUD
# ──────────────────────────────────────────────────────────────────────────────
def draw_hud(surface, player, map_id):
    # semi-transparent HUD strip
    hud = pygame.Surface((SCREEN_W, 44), pygame.SRCALPHA)
    hud.fill((0, 0, 0, 140))
    surface.blit(hud, (0, 0))
 
    # HP
    hp_lbl = font_hud.render("HP", True, (220, 80, 80))
    surface.blit(hp_lbl, (12, 12))
    draw_bar(surface, 46, 14, 140, 16, player.hp/player.max_hp, (220,60,60))
    hp_num = font_small.render(f"{int(player.hp)}/{player.max_hp}", True, (255,200,200))
    surface.blit(hp_num, (192, 14))
 
    # Stamina
    st_lbl = font_hud.render("STA", True, (60, 200, 60))
    surface.blit(st_lbl, (250, 12))
    ratio = player.stamina / player.max_stamina
    sc = (0,210,0) if ratio > 0.5 else (230,180,0) if ratio > 0.25 else (220,50,0)
    draw_bar(surface, 294, 14, 120, 16, ratio, sc)
    st_num = font_small.render(f"{int(player.stamina)}/{player.max_stamina}", True, (200,255,200))
    surface.blit(st_num, (420, 14))
 
    # Weapon
    if player.weapon:
        w_lbl = font_hud.render(f"⚔ {player.weapon.name}", True, player.weapon.proj_color)
        surface.blit(w_lbl, (500, 12))
        cd_ratio = 1.0 - (player.attack_timer / player.weapon.cooldown) if player.weapon else 0
        draw_bar(surface, 500, 32, 100, 5, max(0, min(1, cd_ratio)), (160,160,255))
    else:
        w_lbl = font_hud.render("No weapon", True, (140,130,150))
        surface.blit(w_lbl, (500, 12))
 
    # Map name (right)
    mn = font_small.render(MAP_NAMES[map_id], True, (160, 155, 180))
    surface.blit(mn, (SCREEN_W - mn.get_width() - 12, 14))
 
    # Controls hint bottom
    ctrl = font_small.render("WASD move  SHIFT sprint  Q dash  SPACE attack  ESC menu", True, (80,78,95))
    surface.blit(ctrl, (SCREEN_W//2 - ctrl.get_width()//2, SCREEN_H - 20))
 
 
# ──────────────────────────────────────────────────────────────────────────────
#  GAME STATE
# ──────────────────────────────────────────────────────────────────────────────
MENU_STATE      = 0
MAP_SELECT_STATE= 1
GAME_STATE      = 2
 
state        = MENU_STATE
selected_map = 0
tick         = 0
 
player      = None
env         = None
spawner     = None
projectiles = []
 
def start_game(map_id):
    global player, env, spawner, projectiles
    player = Player(0, 0)
    env = Arenaenv(player, map_id)
    spawn_x, spawn_y = random.choice(env.spawn_points)
    player.x, player.y = spawn_x, spawn_y
    spawner = WeaponSpawner(env.spawn_points)
    projectiles = []
 
 
# ──────────────────────────────────────────────────────────────────────────────
#  MAIN LOOP
# ──────────────────────────────────────────────────────────────────────────────
running = True
while running:
    dt   = clock.tick(FPS)
    tick += 1
 
    # ── events ────────────────────────────────────────────────────────────────
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
 
        if event.type == pygame.KEYDOWN:
            if state == MENU_STATE:
                if event.key == pygame.K_RETURN:
                    start_game(selected_map)
                    state = GAME_STATE
                elif event.key == pygame.K_m:
                    state = MAP_SELECT_STATE
                elif event.key == pygame.K_ESCAPE:
                    running = False
 
            elif state == MAP_SELECT_STATE:
                if event.key == pygame.K_LEFT:
                    selected_map = (selected_map - 1) % 3
                elif event.key == pygame.K_RIGHT:
                    selected_map = (selected_map + 1) % 3
                elif event.key == pygame.K_RETURN:
                    start_game(selected_map)
                    state = GAME_STATE
                elif event.key == pygame.K_ESCAPE:
                    state = MENU_STATE
 
            elif state == GAME_STATE:
                if event.key == pygame.K_ESCAPE:
                    state = MENU_STATE
 
    keys = pygame.key.get_pressed()
 
    # ── MENU ──────────────────────────────────────────────────────────────────
    if state == MENU_STATE:
        draw_menu(screen, tick)
 
    # ── MAP SELECT ────────────────────────────────────────────────────────────
    elif state == MAP_SELECT_STATE:
        draw_map_select(screen, selected_map, tick)
 
    # ── GAME ──────────────────────────────────────────────────────────────────
    elif state == GAME_STATE:
        dx, dy = 0, 0
        if keys[pygame.K_a]: dx -= 1
        if keys[pygame.K_d]: dx += 1
        if keys[pygame.K_w]: dy -= 1
        if keys[pygame.K_s]: dy += 1
 
        sprint = keys[pygame.K_LSHIFT]
 
        if keys[pygame.K_q]:
            player.start_dash(dx, dy)
 
        # attack
        if keys[pygame.K_SPACE]:
            if player.attack():
                if not player.weapon.is_melee:
                    # fire projectile towards mouse
                    mx, my = pygame.mouse.get_pos()
                    pdx = mx - player.x
                    pdy = my - player.y
                    length = math.hypot(pdx, pdy)
                    if length:
                        pdx /= length
                        pdy /= length
                    projectiles.append(
                        Projectile(player.x, player.y, pdx, pdy, player.weapon, player)
                    )
 
        player.move(dx, dy, sprint)
        env.border()
        env.resolve_player_obstacles()
 
        # projectiles
        for proj in projectiles:
            proj.update(env.obstacles)
        projectiles = [p for p in projectiles if p.alive]
 
        # weapon spawner
        spawner.update(env.obstacles)
        spawner.check_pickups(player)
 
        # ── draw ──────────────────────────────────────────────────────────────
        env.draw_background(screen)
        env.draw_obstacles(screen)
        spawner.draw(screen)
 
        for proj in projectiles:
            proj.draw(screen)
 
        draw_player(screen, player, tick)
        draw_hud(screen, player, env.map_id)
 
    pygame.display.flip()
 
pygame.quit()