# language: Python, file: main.py, target: cross-platform
import socket
import threading
import time
import pygame

from shared.protocol import encode, decode
from shared.world import World, W, H, SIZE

PORT = 5555
TICK = 1 / 30
FPS = 60

STATE_MENU = "menu"
STATE_HOST_LOBBY = "host_lobby"
STATE_CLIENT_LOBBY = "client_lobby"
STATE_GAME = "game"


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("Сетевая 2D-игра")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 16)
        self.font_big = pygame.font.SysFont("Arial", 32)
        self.font_mid = pygame.font.SysFont("Arial", 22)

        self.state = STATE_MENU
        self.running = True
        self.mode = None

        self.world = World()
        self.my_id = None
        self.host_conn = None
        self.host_lock = threading.Lock()

        self.sock = None
        self.client_lock = threading.Lock()
        self.server_ip = "127.0.0.1"
        self.ip_input = ""

        self.state_players = {}
        self.prev_state_players = {}
        self.state_bullets = []
        self.state_time = 0.0
        self.prev_time = 0.0

    # ---------- МЕНЮ ----------

    def draw_menu(self):
        self.screen.fill((20, 20, 30))
        title = self.font_big.render("Сетевая 2D-игра", True, (255, 255, 255))
        self.screen.blit(title, (W // 2 - title.get_width() // 2, 140))

        buttons = [
            ("Создать игру (хост)", 260),
            ("Подключиться (гость)", 330),
            ("Выход", 400),
        ]
        self.menu_buttons = []
        for text, y in buttons:
            rect = pygame.Rect(W // 2 - 150, y, 300, 50)
            mouse = pygame.mouse.get_pos()
            hover = rect.collidepoint(mouse)
            color = (60, 100, 160) if hover else (40, 60, 100)
            pygame.draw.rect(self.screen, color, rect, border_radius=8)
            pygame.draw.rect(self.screen, (100, 140, 200), rect, 2, border_radius=8)
            t = self.font_mid.render(text, True, (255, 255, 255))
            self.screen.blit(t, (rect.centerx - t.get_width() // 2,
                                 rect.centery - t.get_height() // 2))
            self.menu_buttons.append((rect, text))

    def handle_menu_click(self, pos):
        for rect, text in self.menu_buttons:
            if rect.collidepoint(pos):
                if text == "Создать игру (хост)":
                    self.start_host()
                elif text == "Подключиться (гость)":
                    self.state = STATE_CLIENT_LOBBY
                elif text == "Выход":
                    self.running = False

    # ---------- ХОСТ ----------

    def start_host(self):
        self.mode = "host"
        self.my_id = self.world.add_player("Host")
        self.state = STATE_HOST_LOBBY
        threading.Thread(target=self.host_server_thread, daemon=True).start()

    def host_server_thread(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", PORT))
        srv.listen(1)
        print(f"[host] ждём игрока 2 на порту {PORT}")

        conn, addr = srv.accept()
        print(f"[host] игрок 2 подключился: {addr}")

        with self.host_lock:
            self.host_conn = conn
            guest_id = self.world.add_player("Guest")

        conn.sendall(encode("welcome", {"id": guest_id}))
        threading.Thread(target=self.host_recv_thread, args=(conn, guest_id), daemon=True).start()

        self.state = STATE_GAME

        while True:
            with self.host_lock:
                self.world.tick()
                snap = self.world.snapshot()
            try:
                conn.sendall(encode("state", snap))
            except OSError:
                break
            time.sleep(TICK)

    def host_recv_thread(self, conn, guest_id):
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
                    with self.host_lock:
                        self.world.set_input(guest_id, msg["p"]["dx"], msg["p"]["dy"])
                elif msg["t"] == "shoot":
                    with self.host_lock:
                        self.world.shoot(guest_id)

        with self.host_lock:
            self.world.remove_player(guest_id)
        print("[host] игрок 2 отключился")

    # ---------- ГОСТЬ ----------

    def start_client(self, ip):
        self.mode = "client"
        self.server_ip = ip
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print(f"[client] подключаюсь к {ip}:{PORT}...")
            self.sock.connect((ip, PORT))
            print("[client] подключён")
        except OSError as e:
            print(f"[client] ошибка подключения: {e}")
            self.state = STATE_MENU
            return

        threading.Thread(target=self.client_recv_thread, daemon=True).start()
        self.state = STATE_GAME

    def client_recv_thread(self):
        buf = b""
        while self.running:
            try:
                chunk = self.sock.recv(65536)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                msg = decode(line)
                if msg["t"] == "welcome":
                    self.my_id = msg["p"]["id"]
                    print(f"[client] я игрок id={self.my_id}")
                elif msg["t"] == "state":
                    with self.client_lock:
                        self.prev_state_players = self.state_players
                        self.prev_time = self.state_time
                        self.state_players = msg["p"]["players"]
                        self.state_bullets = msg["p"]["bullets"]
                        self.state_time = time.time()

    # ---------- ЛОББИ ГОСТЯ ----------

    def draw_client_lobby(self):
        self.screen.fill((20, 20, 30))
        title = self.font_big.render("Подключение к игре", True, (255, 255, 255))
        self.screen.blit(title, (W // 2 - title.get_width() // 2, 140))

        label = self.font_mid.render("Введите IP хоста и нажмите Enter:", True, (200, 200, 200))
        self.screen.blit(label, (W // 2 - label.get_width() // 2, 230))

        box = pygame.Rect(W // 2 - 200, 280, 400, 50)
        pygame.draw.rect(self.screen, (40, 40, 60), box, border_radius=8)
        pygame.draw.rect(self.screen, (100, 180, 255), box, 2, border_radius=8)

        text = self.ip_input if self.ip_input else "127.0.0.1"
        text_color = (255, 255, 255) if self.ip_input else (120, 120, 120)
        t = self.font_mid.render(text, True, text_color)
        self.screen.blit(t, (box.x + 15, box.centery - t.get_height() // 2))

        hint = self.font.render("Например: 192.168.1.42", True, (120, 120, 140))
        self.screen.blit(hint, (W // 2 - hint.get_width() // 2, 345))

        back = self.font.render("Esc — назад", True, (150, 150, 150))
        self.screen.blit(back, (20, H - 30))

    # ---------- ЛОББИ ХОСТА ----------

    def draw_host_lobby(self):
        self.screen.fill((20, 20, 30))
        title = self.font_big.render("Хост — ожидание игрока", True, (255, 255, 255))
        self.screen.blit(title, (W // 2 - title.get_width() // 2, 180))

        local_ip = self.get_local_ip()
        ip_text = self.font_mid.render(f"Ваш IP: {local_ip}", True, (150, 220, 150))
        self.screen.blit(ip_text, (W // 2 - ip_text.get_width() // 2, 260))

        hint = self.font.render("Сообщите этот IP второму игроку", True, (200, 200, 200))
        self.screen.blit(hint, (W // 2 - hint.get_width() // 2, 300))

        dots = "." * (int(time.time() * 2) % 4)
        wait = self.font_mid.render(f"Ждём подключения{dots}", True, (255, 200, 100))
        self.screen.blit(wait, (W // 2 - wait.get_width() // 2, 360))

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except OSError:
            return "127.0.0.1"

    # ---------- ИГРА ----------

    def update_game_host(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_SPACE]:
            with self.host_lock:
                self.world.shoot(self.my_id)

        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])

        with self.host_lock:
            self.world.set_input(self.my_id, dx, dy)
            snap = self.world.snapshot()

        self.render_game(snap["players"], snap["bullets"], alpha=1.0)

    def update_game_client(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_SPACE]:
            try:
                self.sock.sendall(encode("shoot", {}))
            except OSError:
                self.running = False

        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        try:
            self.sock.sendall(encode("input", {"dx": dx, "dy": dy}))
        except OSError:
            self.running = False
            return

        with self.client_lock:
            snap = dict(self.state_players)
            snap_prev = dict(self.prev_state_players)
            snap_bullets = list(self.state_bullets)
            t_cur = self.state_time
            t_prev = self.prev_time

        now = time.time()
        dt = t_cur - t_prev
        alpha = min(1.0, (now - t_cur) / dt) if dt > 0 else 1.0
        alpha = max(0.0, alpha)

        self.render_game(snap, snap_bullets, alpha=alpha, prev=snap_prev)

    def render_game(self, players, bullets, alpha=1.0, prev=None):
        self.screen.fill((20, 20, 30))

        for b in bullets:
            pygame.draw.rect(self.screen, (255, 230, 100), (b["x"], b["y"], 6, 6))

        for pid_s, p in players.items():
            pid = int(pid_s)
            if not p["alive"]:
                continue

            if prev is not None:
                p_prev = prev.get(pid_s, p)
                x = p_prev["x"] + (p["x"] - p_prev["x"]) * alpha
                y = p_prev["y"] + (p["y"] - p_prev["y"]) * alpha
            else:
                x, y = p["x"], p["y"]

            color = (100, 220, 120) if pid == self.my_id else (220, 100, 100)
            pygame.draw.rect(self.screen, color, (x, y, SIZE, SIZE))

            label = self.font.render(p["name"], True, (255, 255, 255))
            self.screen.blit(label, (x, y - 34))

            bar_w = SIZE
            bar_h = 5
            hp_frac = max(0, p["hp"]) / 100
            pygame.draw.rect(self.screen, (60, 60, 60), (x, y - 12, bar_w, bar_h))
            pygame.draw.rect(self.screen, (220, 60, 60), (x, y - 12, bar_w * hp_frac, bar_h))

        role = "HOST" if self.mode == "host" else "CLIENT"
        info = self.font.render(f"{role}  id={self.my_id}  WASD + Пробел — стрелять", True, (200, 200, 200))
        self.screen.blit(info, (10, 10))

    # ---------- ГЛАВНЫЙ ЦИКЛ ----------

    def run(self):
        while self.running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False

                if self.state == STATE_MENU:
                    if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                        self.handle_menu_click(ev.pos)

                elif self.state == STATE_CLIENT_LOBBY:
                    if ev.type == pygame.KEYDOWN:
                        if ev.key == pygame.K_ESCAPE:
                            self.state = STATE_MENU
                            self.ip_input = ""
                        elif ev.key == pygame.K_RETURN:
                            ip = self.ip_input.strip() or "127.0.0.1"
                            self.start_client(ip)
                        elif ev.key == pygame.K_BACKSPACE:
                            self.ip_input = self.ip_input[:-1]
                        else:
                            ch = ev.unicode
                            if ch and (ch.isdigit() or ch == "."):
                                self.ip_input += ch

                elif self.state == STATE_GAME:
                    if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                        if self.mode == "host":
                            with self.host_lock:
                                self.world.shoot(self.my_id)
                        elif self.mode == "client":
                            try:
                                self.sock.sendall(encode("shoot", {}))
                            except OSError:
                                pass

            if self.state == STATE_MENU:
                self.draw_menu()
            elif self.state == STATE_HOST_LOBBY:
                self.draw_host_lobby()
            elif self.state == STATE_CLIENT_LOBBY:
                self.draw_client_lobby()
            elif self.state == STATE_GAME:
                if self.mode == "host":
                    self.update_game_host()
                elif self.mode == "client":
                    self.update_game_client()

            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()


if __name__ == "__main__":
    Game().run()