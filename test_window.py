# language: Python, file: game.py, target: cross-platform
import pygame

W, H = 800, 600
FPS = 60
SPEED = 5          # пикселей за кадр
SIZE = 32          # размер квадрата

pygame.init()
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Game — один игрок")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 16)

# игрок
player = {"x": W // 2, "y": H // 2}

running = True
while running:
    # --- события ---
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False

    # --- ввод ---
    keys = pygame.key.get_pressed()
    dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
    dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])

    # --- движение ---
    player["x"] += dx * SPEED
    player["y"] += dy * SPEED

    # не выпускаем за границы
    player["x"] = max(0, min(W - SIZE, player["x"]))
    player["y"] = max(0, min(H - SIZE, player["y"]))

    # --- рендер ---
    screen.fill((20, 20, 30))
    pygame.draw.rect(screen, (100, 220, 120),
                     (player["x"], player["y"], SIZE, SIZE))

    # координаты текстом
    label = font.render(f"x={player['x']}, y={player['y']}", True, (200, 200, 200))
    screen.blit(label, (10, 10))

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()