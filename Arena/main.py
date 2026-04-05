import pygame
import math

from env import Arenaenv
from player import Player

pygame.init()
screen = pygame.display.set_mode((800,600))
clock = pygame.time.Clock()

font = pygame.font.SysFont(None, 48)

# Game state
MENU = 0
GAME = 1
state = MENU

player = Player(400, 300)
env = Arenaenv(player)

running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    keys = pygame.key.get_pressed()

    # ===== MENU STATE =====
    if state == MENU:
        screen.fill((20, 20, 20))

        title = font.render("My Game", True, (255, 255, 255))
        start_text = font.render("Press ENTER to Start", True, (200, 200, 200))
        quit_text = font.render("Press ESC to Quit", True, (200, 200, 200))

        screen.blit(title, (300, 200))
        screen.blit(start_text, (220, 300))
        screen.blit(quit_text, (240, 360))

        if keys[pygame.K_RETURN]:
            state = GAME
        if keys[pygame.K_ESCAPE]:
            running = False

    # ===== GAME STATE =====
    elif state == GAME:
        # End program
        if keys[pygame.K_ESCAPE]:
            running = False

        dx, dy = 0, 0

        if keys[pygame.K_a]:
            dx -= 1
        if keys[pygame.K_d]:
            dx += 1
        if keys[pygame.K_w]:
            dy -= 1
        if keys[pygame.K_s]:
            dy += 1

        sprint = keys[pygame.K_LSHIFT]

        # Dash
        if keys[pygame.K_q]:
            player.start_dash(dx, dy)

        player.move(dx, dy, sprint)
        env.border()

        screen.fill((30,30,30))

        pygame.draw.circle(screen, (0,200,255), (player.x, player.y), player.radius)

        # Stamina bar
        STAMINA_BAR_WIDTH = player.radius * 2
        STAMINA_BAR_HEIGHT = 6
        STAMINA_BAR_OFFSET = player.radius + 10

        stamina_ratio = player.stamina / player.max_stamina

        if stamina_ratio > 0.5:
            color = (0, 220, 0)
        elif stamina_ratio > 0.25:
            color = (230, 180, 0)
        else:
            color = (220, 0 , 0)

        pygame.draw.rect(screen, (60, 60, 60),
                        (
                            player.x - player.radius,
                            player.y - STAMINA_BAR_OFFSET,
                            STAMINA_BAR_WIDTH,
                            STAMINA_BAR_HEIGHT
                        ))

        pygame.draw.rect(screen, color,
                        (
                            player.x - player.radius,
                            player.y - STAMINA_BAR_OFFSET,
                            STAMINA_BAR_WIDTH * stamina_ratio,
                            STAMINA_BAR_HEIGHT
                        ))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
