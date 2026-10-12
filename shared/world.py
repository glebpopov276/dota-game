# language: Python, file: shared/world.py
import math
import time

W, H = 800, 600
SPEED = 5
SIZE = 32
BULLET_SPEED = 12
BULLET_SIZE = 8
BULLET_LIFE = 2.0
SHOOT_COOLDOWN = 0.3
MAX_HP = 100
DAMAGE = 20
RESPAWN_TIME = 2.0
SCORE_TO_WIN = 5
TURN_SPEED = 0.2   # ← скорость поворота: 0.05 медленно, 0.4 быстро


class World:
    def __init__(self):
        self.players = {}
        self.bullets = []
        self.next_id = 1
        self.next_bullet_id = 1
        self.match_over = False
        self.winner_id = None

    def add_player(self, name: str = None) -> int:
        pid = self.next_id
        self.next_id += 1
        self.players[pid] = {
            "x": W // 2 + (pid - 1) * 60 - 60,
            "y": H // 2,
            "dx": 0,
            "dy": 0,
            "dir_x": 1,
            "dir_y": 0,
            "angle": 0,
            "target_angle": 0,
            "hp": MAX_HP,
            "alive": True,
            "respawn_at": 0.0,
            "last_shot": 0.0,
            "score": 0,
            "name": name or f"P{pid}",
        }
        return pid

    def remove_player(self, pid: int):
        self.players.pop(pid, None)

    def reset(self):
        self.match_over = False
        self.winner_id = None
        self.bullets = []
        for pid, p in self.players.items():
            p["hp"] = MAX_HP
            p["alive"] = True
            p["score"] = 0
            p["x"] = W // 2 + (pid - 1) * 60 - 60
            p["y"] = H // 2
            p["respawn_at"] = 0.0
            p["last_shot"] = 0.0
            p["angle"] = 0
            p["target_angle"] = 0

    def set_input(self, pid: int, dx: int, dy: int):
        if pid not in self.players:
            return
        p = self.players[pid]
        if self.match_over:
            p["dx"] = 0
            p["dy"] = 0
            return
        p["dx"] = max(-1, min(1, int(dx)))
        p["dy"] = max(-1, min(1, int(dy)))
        if dx != 0 or dy != 0:
            length = math.hypot(dx, dy)
            p["dir_x"] = dx / length
            p["dir_y"] = dy / length
            # ставим ЦЕЛЕВОЙ угол, а не текущий
            angle = -math.degrees(math.atan2(dy, dx))
            p["target_angle"] = angle

    def shoot(self, pid: int):
        if self.match_over:
            return
        now = time.time()
        p = self.players.get(pid)
        if not p or not p["alive"]:
            return
        if now - p["last_shot"] < SHOOT_COOLDOWN:
            return
        p["last_shot"] = now
        bx = p["x"] + SIZE / 2
        by = p["y"] + SIZE / 2
        # стреляем по ТЕКУЩЕМУ углу спрайта, а не по направлению ввода
        # angle отсчитывается так: 0° — вправо, +90° — вверх (или наоборот,
        # зависит от того, как отрисован спрайт)
        rad = math.radians(p["angle"])
        # при "angle = 0 → вправо" используем:
        vx = math.cos(rad) * BULLET_SPEED
        vy = -math.sin(rad) * BULLET_SPEED
        self.bullets.append({
            "id": self.next_bullet_id,
            "owner": pid,
            "x": bx,
            "y": by,
            "vx": vx,
            "vy": vy,
            "born": now,
        })
        self.next_bullet_id += 1

    def tick(self):
        if self.match_over:
            return

        now = time.time()

        for p in self.players.values():
            if not p["alive"]:
                if now >= p["respawn_at"]:
                    p["alive"] = True
                    p["hp"] = MAX_HP
                    p["x"] = W // 2
                    p["y"] = H // 2
                continue

            p["x"] = max(0, min(W - SIZE, p["x"] + p["dx"] * SPEED))
            p["y"] = max(0, min(H - SIZE, p["y"] + p["dy"] * SPEED))

            # --- ПЛАВНЫЙ ПОВОРОТ ---
            diff = p["target_angle"] - p["angle"]
            while diff > 180:
                diff -= 360
            while diff < -180:
                diff += 360
            p["angle"] += diff * TURN_SPEED

        alive_bullets = []
        for b in self.bullets:
            if now - b["born"] > BULLET_LIFE:
                continue

            b["x"] += b["vx"]
            b["y"] += b["vy"]

            if b["x"] < -20 or b["x"] > W + 20 or b["y"] < -20 or b["y"] > H + 20:
                continue

            hit = False
            for pid, p in self.players.items():
                if pid == b["owner"] or not p["alive"]:
                    continue
                if (p["x"] <= b["x"] <= p["x"] + SIZE and
                        p["y"] <= b["y"] <= p["y"] + SIZE):
                    p["hp"] -= DAMAGE
                    hit = True
                    if p["hp"] <= 0:
                        p["hp"] = 0
                        p["alive"] = False
                        p["respawn_at"] = now + RESPAWN_TIME

                        killer = self.players.get(b["owner"])
                        if killer:
                            killer["score"] += 1
                            if killer["score"] >= SCORE_TO_WIN:
                                self.match_over = True
                                self.winner_id = b["owner"]
                    break

            if not hit:
                alive_bullets.append(b)

        self.bullets = alive_bullets

    def snapshot(self) -> dict:
        return {
            "players": {
                str(pid): {
                    "x": p["x"], "y": p["y"], "name": p["name"],
                    "hp": p["hp"], "alive": p["alive"],
                    "score": p["score"],
                    "angle": p["angle"],
                }
                for pid, p in self.players.items()
            },
            "bullets": [
                {"x": b["x"], "y": b["y"]}
                for b in self.bullets
            ],
            "match_over": self.match_over,
            "winner_id": self.winner_id,
        }