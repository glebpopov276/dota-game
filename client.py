# language: Python, file: client.py, target: cross-platform
import socket
import threading
import pygame

from shared.protocol import encode, decode
from shared.world import W, H, SIZE

SERVER_IP = "127.0.0.1"
PORT = 5555
FPS = 60

state = {}
my_id = None
sock = None
running = True
lock = threading.Lock()


def recv_loop():
    global state, my_id, running
    buf = b""
    while running:
        try:
            chunk = sock.recv(4096)
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            msg = decode(line)
            if msg["t"] == "welcome":
                my_id = msg["p"]["id"]
                print(f"[client] я игрок id={my_id}")
            elif msg["t"] == "state":
                with lock:
                    state = msg["p"]["players"]


def main():
    global sock, running
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"[client] подключаюсь к {SERVER_IP}:{PORT}...")
    sock.connect((SERVER_IP, PORT))
    print("[client] подключён")

    threading.Thread(target=recv_loop, daemon=True).start()

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Client — игрок 2")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 16)

    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        try:
            sock.sendall(encode("input", {"dx": dx, "dy": dy}))
        except OSError:
            running = False
            break

        with lock:
            snap = dict(state)

        screen.fill((20, 20, 30))
        for pid_s, p in snap.items():
            pid = int(pid_s)
            color = (100, 220, 120) if pid == my_id else (220, 100, 100)
            pygame.draw.rect(screen, color, (p["x"], p["y"], SIZE, SIZE))
            label = font.render(p["name"], True, (255, 255, 255))
            screen.blit(label, (p["x"], p["y"] - 18))

        info = font.render(f"CLIENT  id={my_id}  WASD — двигать", True, (200, 200, 200))
        screen.blit(info, (10, 10))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sock.close()


if __name__ == "__main__":
    main()