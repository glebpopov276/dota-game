# language: Python, file: host.py, target: cross-platform
import socket
import threading
import time
import pygame

from shared.protocol import encode, decode
from shared.world import World, W, H, SIZE

PORT = 5555
TICK = 1 / 30
FPS = 60
MY_NAME = "Host"

world = World()
host_id = world.add_player(MY_NAME)
guest_sock = None
lock = threading.Lock()


def server_thread():
    global guest_sock
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(1)
    print(f"[host] ждём игрока 2 на порту {PORT}")

    conn, addr = srv.accept()
    print(f"[host] игрок 2 подключился: {addr}")

    with lock:
        guest_sock = conn
        guest_id = world.add_player("Guest")

    conn.sendall(encode("welcome", {"id": guest_id}))

    threading.Thread(target=recv_guest, args=(conn, guest_id), daemon=True).start()

    while True:
        with lock:
            world.tick()
            snap = world.snapshot()
        try:
            conn.sendall(encode("state", {"players": snap}))
        except OSError:
            break
        time.sleep(TICK)


def recv_guest(conn, guest_id):
    buf = b""
    while True:
        try:
            chunk = conn.recv(4096)
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            msg = decode(line)
            if msg["t"] == "input":
                with lock:
                    world.set_input(guest_id, msg["p"]["dx"], msg["p"]["dy"])

    with lock:
        world.remove_player(guest_id)
    print("[host] игрок 2 отключился")


def main():
    threading.Thread(target=server_thread, daemon=True).start()

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption(f"Host — {MY_NAME} (id={host_id})")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 16)

    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])

        with lock:
            world.set_input(host_id, dx, dy)
            snap = world.snapshot()

        screen.fill((20, 20, 30))
        for pid_s, p in snap.items():
            pid = int(pid_s)
            color = (100, 220, 120) if pid == host_id else (220, 100, 100)
            pygame.draw.rect(screen, color, (p["x"], p["y"], SIZE, SIZE))
            label = font.render(p["name"], True, (255, 255, 255))
            screen.blit(label, (p["x"], p["y"] - 18))

        info = font.render(f"HOST  id={host_id}  WASD — двигать", True, (200, 200, 200))
        screen.blit(info, (10, 10))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()