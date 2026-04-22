import pygame
import math
from env import Arenaenv, resolve_collision
from player import Player

pygame.init()
screen = pygame.display.set_mode((1920,1080))
clock = pygame.time.Clock()

WIDTH, HEIGHT = screen.get_size()

font = pygame.font.SysFont(None, 72)
small_font = pygame.font.SysFont(None, 48)

# Load menu background
menu_bg = pygame.image.load("Content/starting_menu.png").convert()
menu_bg = pygame.transform.scale(menu_bg, (WIDTH, HEIGHT))

# Dark overlay
overlay = pygame.Surface((WIDTH, HEIGHT))
overlay.set_alpha(120)
overlay.fill((0, 0, 0))

# GAME STATE
MENU = 0
GAME = 1
GAME_OVER = 2
state = MENU
winner_text = ""

# GAME HELPERS

def reset_game():
    global player1, player2, env, winner_text
    player1 = Player(480, 540)
    player2 = Player(1440, 540)
    env = Arenaenv(player1)
    winner_text = ""


def draw_health_bar(surface, player):
    bar_width = 84
    bar_height = 10
    bar_x = player.x - bar_width / 2
    bar_y = player.y - player.radius - 24
    health_ratio = player.health / player.max_health

    pygame.draw.rect(surface, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height), border_radius=4)
    pygame.draw.rect(surface, (180, 40, 40), (bar_x, bar_y, bar_width * health_ratio, bar_height), border_radius=4)


def draw_player(surface, player, body_color):
    import math

    color = body_color
    if player.hit_timer > 0:
        color = (255, 180, 180)

    pygame.draw.circle(surface, color, (int(player.x), int(player.y)), player.radius)
    draw_health_bar(surface, player)

    angle = math.atan2(player.facing_dy, player.facing_dx)
    if player.is_attacking():
        progress = 1 - (player.attack_timer / player.attack_duration)
        swing_offset = math.sin(progress * math.pi) * 0.9
        tip_angle = angle + swing_offset
    else:
        tip_angle = angle - 0.4

    sword_length = player.radius + 24
    start_x = player.x + math.cos(tip_angle) * 10
    start_y = player.y + math.sin(tip_angle) * 10
    end_x = player.x + math.cos(tip_angle) * sword_length
    end_y = player.y + math.sin(tip_angle) * sword_length

    pygame.draw.line(surface, (220, 220, 220), (start_x, start_y), (end_x, end_y), 6)
    guard_start = (player.x + math.cos(tip_angle + math.pi / 2) * 6,
                   player.y + math.sin(tip_angle + math.pi / 2) * 6)
    guard_end = (player.x + math.cos(tip_angle - math.pi / 2) * 6,
                 player.y + math.sin(tip_angle - math.pi / 2) * 6)
    pygame.draw.line(surface, (180, 180, 180), guard_start, guard_end, 4)

# BUTTON CLASS
class Button:
    def __init__(self, text, x, y, width, height):
        self.text = text
        self.rect = pygame.Rect(x, y, width, height)

    def draw(self, screen, font):
        mouse_pos = pygame.mouse.get_pos()
        hovered = self.rect.collidepoint(mouse_pos)

        # Colors
        base_color = (0, 0, 0)          # black
        hover_color = (80, 0, 0)        # dark red
        border_color = (120, 0, 0)      # red border
        text_color = (255, 255, 255)    # white text (better on black)

        color = hover_color if hovered else base_color

        # Glow effect (only on hover)
        if hovered:
            glow_rect = self.rect.inflate(10, 10)
            pygame.draw.rect(screen, hover_color , glow_rect, border_radius=20)

        # Main button
        pygame.draw.rect(screen, color, self.rect, border_radius=15)

        # Border
        pygame.draw.rect(screen, border_color, self.rect, 2, border_radius=15)

        # Text
        text_surf = font.render(self.text, True,text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def is_clicked(self, event):
        return (
            event.type == pygame.MOUSEBUTTONDOWN and
            event.button == 1 and
            self.rect.collidepoint(event.pos)
        )

# CREATE BUTTONS
button_width = 300
button_height = 80

start_button = Button(
    "START",
    WIDTH // 2 - button_width // 2,
    HEIGHT // 2,
    button_width,
    button_height
)

exit_button = Button(
    "EXIT",
    WIDTH // 2 - button_width // 2,
    HEIGHT // 2 + 120,
    button_width,
    button_height
)

# PLAYERS
player1 = Player(480, 540)
player2 = Player(1440, 540)

env = Arenaenv(player1)

running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if state == MENU:
            if start_button.is_clicked(event):
                state = GAME
            if exit_button.is_clicked(event):
                running = False

    keys = pygame.key.get_pressed()

    # ===== MENU =====
    if state == MENU:
        screen.blit(menu_bg, (0, 0))
        screen.blit(overlay, (0, 0))

       # BIG title
        title_font = pygame.font.SysFont("arialblack", 110)

        title_text = "MY GAME"

        # Shadow
        shadow = title_font.render(title_text, True, (0, 0, 0))
        shadow_rect = shadow.get_rect(center=(WIDTH // 2 + 5, HEIGHT // 2 - 180 + 5))
        screen.blit(shadow, shadow_rect)

        # Main text
        title = title_font.render(title_text, True, (255, 255, 255))
        title_rect = title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 180))
        screen.blit(title, title_rect)

        # Accent glow
        glow = title_font.render(title_text, True, (100, 170, 255))
        glow.set_alpha(60)
        glow_rect = glow.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 180))
        screen.blit(glow, glow_rect)

        start_button.draw(screen, small_font)
        exit_button.draw(screen, small_font)

        hint = small_font.render("ENTER = Start | ESC = Exit", True, (180, 180, 180))
        hint_rect = hint.get_rect(center=(WIDTH // 2, HEIGHT - 80))
        screen.blit(hint, hint_rect)

        if keys[pygame.K_RETURN]:
            state = GAME
        if keys[pygame.K_ESCAPE]:
            running = False

    # ===== GAME =====
    elif state == GAME:
        if keys[pygame.K_ESCAPE]:
            running = False

        # PLAYER 1
        dx1, dy1 = 0, 0
        if keys[pygame.K_a]: dx1 -= 1
        if keys[pygame.K_d]: dx1 += 1
        if keys[pygame.K_w]: dy1 -= 1
        if keys[pygame.K_s]: dy1 += 1

        sprint1 = keys[pygame.K_LSHIFT]

        if keys[pygame.K_q]:
            player1.start_dash(dx1, dy1)
        if keys[pygame.K_f]:
            player1.start_attack(dx1, dy1)

        player1.move(dx1, dy1, sprint1)

        # PLAYER 2
        dx2, dy2 = 0, 0
        if keys[pygame.K_LEFT]: dx2 -= 1
        if keys[pygame.K_RIGHT]: dx2 += 1
        if keys[pygame.K_UP]: dy2 -= 1
        if keys[pygame.K_DOWN]: dy2 += 1

        sprint2 = keys[pygame.K_RSHIFT]

        if keys[pygame.K_SLASH]:
            player2.start_dash(dx2, dy2)
        if keys[pygame.K_RCTRL]:
            player2.start_attack(dx2, dy2)

        player2.move(dx2, dy2, sprint2)

        # ATTACKS
        for attacker, target in ((player1, player2), (player2, player1)):
            if attacker.attack_active() and not attacker.attack_hit_registered and attacker.attack_timer == attacker.attack_duration - 4:
                dx = target.x - attacker.x
                dy = target.y - attacker.y
                distance = math.hypot(dx, dy)
                dot = dx * attacker.facing_dx + dy * attacker.facing_dy

                attacker.attack_hit_registered = True
                if distance <= attacker.attack_range + target.radius and dot > 0:
                    target.take_hit(attacker.attack_damage)

        player1.update()
        player2.update()

        # COLLISION / BORDERS
        resolve_collision(player1, player2)

        env.player = player1
        env.border()
        env.player = player2
        env.border()

        # BACKGROUND
        screen.fill((30, 30, 30))

        # DRAW PLAYERS
        draw_player(screen, player1, (0, 200, 255))
        draw_player(screen, player2, (255, 100, 100))

        # STAMINA BAR
        def draw_stamina(player):
            width = player.radius * 2
            height = 6
            offset = player.radius + 28

            ratio = player.stamina / player.max_stamina

            if ratio > 0.5:
                color = (0, 220, 0)
            elif ratio > 0.25:
                color = (230, 180, 0)
            else:
                color = (220, 0, 0)

            pygame.draw.rect(screen, (60, 60, 60),
                (player.x - player.radius, player.y - offset, width, height))

            pygame.draw.rect(screen, color,
                (player.x - player.radius, player.y - offset, width * ratio, height))

        draw_stamina(player1)
        draw_stamina(player2)

        game_hint = small_font.render("F=Attack | RCTRL=Attack | Q/Slash=Dash | Shift=Sprint", True, (220, 220, 220))
        hint_rect = game_hint.get_rect(center=(WIDTH // 2, HEIGHT - 40))
        screen.blit(game_hint, hint_rect)

        if player1.is_dead() or player2.is_dead():
            state = GAME_OVER
            winner_text = "PLAYER 2 WINS!" if player1.is_dead() else "PLAYER 1 WINS!"

    elif state == GAME_OVER:
        screen.blit(menu_bg, (0, 0))
        screen.blit(overlay, (0, 0))

        end_font = pygame.font.SysFont("arialblack", 100)
        text = end_font.render(winner_text, True, (255, 230, 50))
        text_rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 80))
        screen.blit(text, text_rect)

        reset_hint = small_font.render("PRESS ENTER TO RESTART OR ESC TO EXIT", True, (220, 220, 220))
        reset_rect = reset_hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 60))
        screen.blit(reset_hint, reset_rect)

        if keys[pygame.K_RETURN]:
            reset_game()
            state = GAME
        if keys[pygame.K_ESCAPE]:
            running = False

    pygame.display.flip()
    clock.tick(60)

pygame.quit()