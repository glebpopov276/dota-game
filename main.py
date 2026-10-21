# language: Python, file: main.py, target: cross-platform (Android + PC)
import socket
import threading
import time

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, Rectangle, PushMatrix, PopMatrix, Rotate
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.audio import SoundLoader
from kivy.core.image import Image as CoreImage

from shared.protocol import encode, decode
from shared.world import World, W, H, SIZE, SCORE_TO_WIN

PORT = 5555
TICK = 1 / 30
FPS = 60

STATE_MENU = "menu"
STATE_HOST_LOBBY = "host_lobby"
STATE_CLIENT_LOBBY = "client_lobby"
STATE_GAME = "game"
STATE_WIN = "win"


class GameWidget(Widget):
    pass


class Game(App):
    def build(self):
        Window.clearcolor = (0.08, 0.08, 0.12, 1)

        self.state = STATE_MENU
        self.mode = None
        self.world = World()
        self.my_id = None
        self.host_lock = threading.Lock()
        self.host_conn = None
        self.sock = None
        self.client_lock = threading.Lock()
        self.ip_input = ""
        self.server_ip = "127.0.0.1"

        self.state_players = {}
        self.prev_state_players = {}
        self.state_bullets = []
        self.state_time = 0.0
        self.prev_time = 0.0

        self.match_over = False
        self.winner_id = None
        self.reset_requested = False

        # Клавиши (для PC)
        self.keys_pressed = set()
        Window.bind(on_key_down=self._on_key_down, on_key_up=self._on_key_up)

        # Загрузка спрайтов
        try:
            self.tex_host = CoreImage("assets/sprites/player1.png").texture
            self.tex_guest = CoreImage("assets/sprites/player2.png").texture
        except Exception as e:
            print(f"[warn] спрайты: {e}")
            self.tex_host = None
            self.tex_guest = None

        # Загрузка звуков
        try:
            self.snd_shoot = SoundLoader.load("assets/sounds/shoot.wav")
            self.snd_hit = SoundLoader.load("assets/sounds/hit.wav")
            self.snd_death = SoundLoader.load("assets/sounds/death.wav")
            self.snd_win = SoundLoader.load("assets/sounds/win.wav")
            if self.snd_shoot:
                self.snd_shoot.volume = 0.1
            if self.snd_hit:
                self.snd_hit.volume = 0.12
            if self.snd_death:
                self.snd_death.volume = 0.15
            if self.snd_win:
                self.snd_win.volume = 0.2
        except Exception as e:
            print(f"[warn] звуки: {e}")
            self.snd_shoot = self.snd_hit = self.snd_death = self.snd_win = None

        self.root = FloatLayout()
        self.show_menu()

        Clock.schedule_interval(self.update, 1 / FPS)
        return self.root

    # ---------- КЛАВИАТУРА ----------

    def _on_key_down(self, window, key, scancode, codepoint, modifiers):
        self.keys_pressed.add(key)

    def _on_key_up(self, window, key, scancode):
        self.keys_pressed.discard(key)

    def clear_root(self):
        self.root.clear_widgets()
        self.root.canvas.clear()

    # ---------- МЕНЮ ----------

    def show_menu(self):
        self.state = STATE_MENU
        self.clear_root()

        title = Label(
            text="Сетевая 2D-игра",
            font_size=48,
            size_hint=(1, 0.2),
            pos_hint={"center_x": 0.5, "top": 0.95},
        )
        self.root.add_widget(title)

        box = BoxLayout(
            orientation="vertical",
            spacing=20,
            size_hint=(0.6, 0.5),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        btn_host = Button(text="Создать игру (хост)", font_size=24)
        btn_host.bind(on_press=lambda x: self.start_host())
        box.add_widget(btn_host)

        btn_client = Button(text="Подключиться (гость)", font_size=24)
        btn_client.bind(on_press=lambda x: self.show_client_lobby())
        box.add_widget(btn_client)

        btn_exit = Button(text="Выход", font_size=24)
        btn_exit.bind(on_press=lambda x: self.stop())
        box.add_widget(btn_exit)

        self.root.add_widget(box)

    # ---------- ЛОББИ ГОСТЯ ----------

    def show_client_lobby(self):
        self.state = STATE_CLIENT_LOBBY
        self.clear_root()

        title = Label(
            text="Подключение к игре",
            font_size=40,
            size_hint=(1, 0.15),
            pos_hint={"center_x": 0.5, "top": 0.95},
        )
        self.root.add_widget(title)

        label = Label(
            text="Введите IP хоста:",
            font_size=24,
            size_hint=(1, 0.1),
            pos_hint={"center_x": 0.5, "center_y": 0.7},
        )
        self.root.add_widget(label)

        self.ip_field = TextInput(
            text="127.0.0.1",
            multiline=False,
            font_size=24,
            size_hint=(0.6, 0.08),
            pos_hint={"center_x": 0.5, "center_y": 0.55},
        )
        self.root.add_widget(self.ip_field)

        btn = Button(
            text="Подключиться",
            font_size=28,
            size_hint=(0.4, 0.1),
            pos_hint={"center_x": 0.5, "center_y": 0.4},
        )
        btn.bind(on_press=lambda x: self.start_client(self.ip_field.text.strip() or "127.0.0.1"))
        self.root.add_widget(btn)

        btn_back = Button(
            text="← Назад",
            font_size=20,
            size_hint=(0.2, 0.08),
            pos_hint={"x": 0.02, "y": 0.02},
        )
        btn_back.bind(on_press=lambda x: self.show_menu())
        self.root.add_widget(btn_back)

    # ---------- ХОСТ ----------

    def start_host(self):
        self.mode = "host"
        self.my_id = self.world.add_player("Host")
        self.show_host_lobby()
        threading.Thread(target=self.host_server_thread, daemon=True).start()

    def show_host_lobby(self):
        self.state = STATE_HOST_LOBBY
        self.clear_root()

        title = Label(
            text="Хост — ожидание игрока",
            font_size=36,
            size_hint=(1, 0.15),
            pos_hint={"center_x": 0.5, "top": 0.95},
        )
        self.root.add_widget(title)

        local_ip = self.get_local_ip()
        ip_lbl = Label(
            text=f"Ваш IP: {local_ip}",
            font_size=32,
            color=(0.6, 0.9, 0.6, 1),
            size_hint=(1, 0.1),
            pos_hint={"center_x": 0.5, "center_y": 0.6},
        )
        self.root.add_widget(ip_lbl)

        hint = Label(
            text="Сообщите этот IP второму игроку",
            font_size=20,
            size_hint=(1, 0.1),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        self.root.add_widget(hint)

        wait = Label(
            text="Ждём подключения...",
            font_size=26,
            color=(1, 0.8, 0.4, 1),
            size_hint=(1, 0.1),
            pos_hint={"center_x": 0.5, "center_y": 0.4},
        )
        self.root.add_widget(wait)

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

        Clock.schedule_once(lambda dt: self.show_game(), 0)

        while True:
            with self.host_lock:
                if self.reset_requested:
                    self.world.reset()
                    self.reset_requested = False
                    self.match_over = False
                    self.winner_id = None

                self.world.tick()
                snap = self.world.snapshot()

                if snap["match_over"] and not self.match_over:
                    self.match_over = True
                    self.winner_id = snap["winner_id"]
                    Clock.schedule_once(lambda dt: self.show_win_screen(), 0)
                    if self.snd_win:
                        self.snd_win.play()

            try:
                conn.sendall(encode("state", snap))
                if self.match_over:
                    conn.sendall(encode("match_end", {"winner_id": self.winner_id}))
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
                elif msg["t"] == "reset":
                    with self.host_lock:
                        self.reset_requested = True
                        self.match_over = False
                        self.winner_id = None
                    Clock.schedule_once(lambda dt: self.show_game(), 0)

        with self.host_lock:
            self.world.remove_player(guest_id)

    # ---------- ГОСТЬ ----------

    def start_client(self, ip):
        self.mode = "client"
        self.server_ip = ip
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((ip, PORT))
            print(f"[client] подключён к {ip}")
        except OSError as e:
            print(f"[client] ошибка: {e}")
            self.show_menu()
            return

        threading.Thread(target=self.client_recv_thread, daemon=True).start()
        Clock.schedule_once(lambda dt: self.show_game(), 0)

    def client_recv_thread(self):
        buf = b""
        while True:
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
                elif msg["t"] == "state":
                    with self.client_lock:
                        self.prev_state_players = self.state_players
                        self.prev_time = self.state_time
                        self.state_players = msg["p"]["players"]
                        self.state_bullets = msg["p"]["bullets"]
                        self.state_time = time.time()
                elif msg["t"] == "match_end":
                    self.match_over = True
                    self.winner_id = msg["p"]["winner_id"]
                    Clock.schedule_once(lambda dt: self.show_win_screen(), 0)
                    if self.snd_win:
                        self.snd_win.play()

    # ---------- ИГРА ----------

    def show_game(self):
        self.state = STATE_GAME
        self.clear_root()

        self.game_widget = GameWidget()
        self.root.add_widget(self.game_widget)

        pad = 90
        self.btn_up = Button(text="↑", size_hint=(None, None), size=(pad, pad),
                             pos_hint={"x": 0.06, "y": 0.28})
        self.btn_down = Button(text="↓", size_hint=(None, None), size=(pad, pad),
                               pos_hint={"x": 0.06, "y": 0.02})
        self.btn_left = Button(text="←", size_hint=(None, None), size=(pad, pad),
                               pos_hint={"x": 0.005, "y": 0.15})
        self.btn_right = Button(text="→", size_hint=(None, None), size=(pad, pad),
                                pos_hint={"x": 0.115, "y": 0.15})
        self.btn_shoot = Button(text="ОГОНЬ", size_hint=(None, None), size=(150, 150),
                                pos_hint={"right": 0.98, "y": 0.1},
                                background_color=(1, 0.3, 0.3, 1))

        for b in (self.btn_up, self.btn_down, self.btn_left, self.btn_right, self.btn_shoot):
            self.root.add_widget(b)

    def _btn_active(self, b):
        return b.state == "down"

    def get_input_dx(self):
        dx = 0
        if self._btn_active(self.btn_left):
            dx -= 1
        if self._btn_active(self.btn_right):
            dx += 1
        # Клавиши A / D и стрелки
        if 97 in self.keys_pressed or 276 in self.keys_pressed:
            dx -= 1
        if 100 in self.keys_pressed or 275 in self.keys_pressed:
            dx += 1
        return max(-1, min(1, dx))

    def get_input_dy(self):
        dy = 0
        if self._btn_active(self.btn_up):
            dy -= 1
        if self._btn_active(self.btn_down):
            dy += 1
        # Клавиши W / S и стрелки
        if 119 in self.keys_pressed or 273 in self.keys_pressed:
            dy -= 1
        if 115 in self.keys_pressed or 274 in self.keys_pressed:
            dy += 1
        return max(-1, min(1, dy))

    def update(self, dt):
        if self.state != STATE_GAME:
            return
        if not hasattr(self, "game_widget"):
            return

        if self.mode == "host":
            self.update_host()
        elif self.mode == "client":
            self.update_client()

    def update_host(self):
        dx = self.get_input_dx()
        dy = self.get_input_dy()

        if self._btn_active(self.btn_shoot) or 32 in self.keys_pressed:
            with self.host_lock:
                self.world.shoot(self.my_id)
            if self.snd_shoot:
                self.snd_shoot.play()

        with self.host_lock:
            self.world.set_input(self.my_id, dx, dy)
            snap = self.world.snapshot()

        self.render_game(snap["players"], snap["bullets"])

    def update_client(self):
        dx = self.get_input_dx()
        dy = self.get_input_dy()

        if self._btn_active(self.btn_shoot) or 32 in self.keys_pressed:
            try:
                self.sock.sendall(encode("shoot", {}))
                if self.snd_shoot:
                    self.snd_shoot.play()
            except OSError:
                pass

        try:
            self.sock.sendall(encode("input", {"dx": dx, "dy": dy}))
        except OSError:
            return

        with self.client_lock:
            snap = dict(self.state_players)
            bullets = list(self.state_bullets)

        self.render_game(snap, bullets)

    def render_game(self, players, bullets):
        w = self.game_widget
        w.canvas.clear()

        sw, sh = Window.size
        scale_x = sw / W
        scale_y = sh / H

        with w.canvas:
            Color(0.08, 0.08, 0.12, 1)
            Rectangle(pos=(0, 0), size=(sw, sh))

            # Пули
            Color(1, 0.9, 0.3, 1)
            for b in bullets:
                bx = b["x"] * scale_x
                by = sh - b["y"] * scale_y
                Rectangle(pos=(bx, by), size=(8, 8))

            # Игроки
            for pid_s, p in players.items():
                if not p["alive"]:
                    continue
                pid = int(pid_s)
                angle = p.get("angle", 0)

                x = p["x"] * scale_x
                y = sh - (p["y"] + SIZE) * scale_y
                cx = x + (SIZE * scale_x) / 2
                cy = y + (SIZE * scale_y) / 2

                PushMatrix()
                Rotate(angle=-angle +180 , origin=(cx, cy))

                tex = self.tex_host if pid == self.my_id else self.tex_guest
                if tex:
                    Color(1, 1, 1, 1)
                    Rectangle(texture=tex,
                              pos=(cx - (SIZE * scale_x) / 2, cy - (SIZE * scale_y) / 2),
                              size=(SIZE * scale_x, SIZE * scale_y))
                else:
                    if pid == self.my_id:
                        Color(0.4, 0.9, 0.4, 1)
                    else:
                        Color(0.9, 0.4, 0.4, 1)
                    Rectangle(pos=(cx - (SIZE * scale_x) / 2, cy - (SIZE * scale_y) / 2),
                              size=(SIZE * scale_x, SIZE * scale_y))

                PopMatrix()

    # ---------- ЭКРАН ПОБЕДЫ ----------

    def show_win_screen(self):
        self.state = STATE_WIN
        self.clear_root()

        if self.winner_id == self.my_id:
            text = "ПОБЕДА!"
            color = (0.4, 1, 0.4, 1)
        else:
            text = "ПОРАЖЕНИЕ"
            color = (1, 0.4, 0.4, 1)

        title = Label(
            text=text,
            font_size=64,
            color=color,
            size_hint=(1, 0.2),
            pos_hint={"center_x": 0.5, "top": 0.9},
        )
        self.root.add_widget(title)

        players_dict = self.world.players if self.mode == "host" else self.state_players
        winner_name = "?"
        if self.mode == "host":
            if self.winner_id in players_dict:
                winner_name = players_dict[self.winner_id]["name"]
        else:
            if str(self.winner_id) in players_dict:
                winner_name = players_dict[str(self.winner_id)]["name"]

        sub = Label(
            text=f"Победитель: {winner_name}",
            font_size=36,
            size_hint=(1, 0.15),
            pos_hint={"center_x": 0.5, "center_y": 0.6},
        )
        self.root.add_widget(sub)

        score_host = 0
        score_guest = 0
        for pid_s, p in players_dict.items():
            if p["name"] == "Host":
                score_host = p["score"]
            elif p["name"] == "Guest":
                score_guest = p["score"]

        score_lbl = Label(
            text=f"{score_host} : {score_guest}",
            font_size=64,
            color=(1, 0.85, 0.3, 1),
            size_hint=(1, 0.2),
            pos_hint={"center_x": 0.5, "center_y": 0.4},
        )
        self.root.add_widget(score_lbl)

        btn = Button(
            text="Рестарт",
            font_size=28,
            size_hint=(0.4, 0.12),
            pos_hint={"center_x": 0.5, "y": 0.1},
        )
        btn.bind(on_press=lambda x: self.request_reset())
        self.root.add_widget(btn)

    def request_reset(self):
        if self.mode == "host":
            with self.host_lock:
                self.reset_requested = True
            self.match_over = False
            self.winner_id = None
            self.show_game()
        elif self.mode == "client":
            try:
                self.sock.sendall(encode("reset", {}))
            except OSError:
                pass
            self.match_over = False
            self.winner_id = None
            self.show_game()

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except OSError:
            return "127.0.0.1"


if __name__ == "__main__":
    Game().run()