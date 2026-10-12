# language: Python, file: game.py, target: cross-platform
import pygame

W, H = 800, 600
FPS = 60
SPEED = 5
SIZE = 32

pygame.init()
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Game — два игрока (локально)")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 16)

# --- игроки ---
# id -> {"x":, "y":, "color":, "name":}
# СЕЙЧАС: локально, чтобы подготовить структуру под сеть
# СКОРО: будет приходить от сервера (snapshot)
players = {
    1: {"x": W // 2 - 60, "y": H // 2, "color": (100, 220, 120), "name": "P1"},
    2: {"x": W // 2 + 60, "y": H // 2, "color": (220, 100, 100), "name": "P2"},
}

# мой id — кого я двигаю с клавиатуры
my_id = 1

running = True
while running:
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False

    # --- ввод двигает ТОЛЬКО моего игрока ---
    keys = pygame.key.get_pressed()
    dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
    dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])

    me = players[my_id]
    me["x"] += dx * SPEED
    me["y"] += dy * SPEED

    # границы — для всех игроков
    for p in players.values():
        p["x"] = max(0, min(W - SIZE, p["x"]))
        p["y"] = max(0, min(H - SIZE, p["y"]))

    # --- рендер всех игроков ---
    screen.fill((20, 20, 30))
    for pid, p in players.items():
        pygame.draw.rect(screen, p["color"], (p["x"], p["y"], SIZE, SIZE))
        label = font.render(p["name"], True, (255, 255, 255))
        screen.blit(label, (p["x"], p["y"] - 18))

    # инфо в углу
    info = font.render(f"my_id={my_id}  —  WASD двигает меня (зелёный)", True, (200, 200, 200))
    screen.blit(info, (10, 10))

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()