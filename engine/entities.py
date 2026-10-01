import math
import random
from . import assets


class Player:
    radius = 0.25

    def __init__(self, x, y, angle=0.0):
        self.x, self.y, self.angle = x, y, angle
        self.health = 100
        self.hurt_flash = 0.0

    @property
    def alive(self):
        return self.health > 0

    def hurt(self, dmg):
        self.health = max(0, self.health - dmg)
        self.hurt_flash = 0.3


class Enemy:
    """Base enemy. Subclass and override stats / make_frames() to add new types."""
    health = 60
    speed = 1.5
    radius = 0.35
    scale = 0.9          # sprite height in world units
    damage = 8
    accuracy = 0.6
    attack_range = 7.0
    attack_cooldown = 1.6
    sight_range = 14.0
    _frame_cache = {}

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.hp = self.health
        self.state = "idle"
        self.timer = self.cooldown = self.anim = 0.0

    @classmethod
    def make_frames(cls):
        raise NotImplementedError

    @property
    def frames(self):
        cache = Enemy._frame_cache
        if type(self) not in cache:
            cache[type(self)] = self.make_frames()
        return cache[type(self)]

    @property
    def alive(self):
        return self.state != "dead"

    @property
    def image(self):
        f = self.frames
        if self.state in ("dead", "pain", "attack"):
            return f[self.state]
        if self.state == "idle":
            return f["walk"][0]
        return f["walk"][int(self.anim * 6) % len(f["walk"])]

    def hurt(self, dmg):
        if not self.alive:
            return
        self.hp -= dmg
        if self.hp <= 0:
            self.state = "dead"
        else:
            self.state, self.timer = "pain", 0.2

    def update(self, dt, game):
        if not self.alive:
            return
        self.anim += dt
        self.timer -= dt
        self.cooldown -= dt
        p = game.player
        dx, dy = p.x - self.x, p.y - self.y
        dist = math.hypot(dx, dy) or 1e-6
        sees = dist < self.sight_range and game.world.line_of_sight(self.x, self.y, p.x, p.y)

        if self.state == "idle":
            if sees:
                self.state = "chase"
        elif self.state == "pain":
            if self.timer <= 0:
                self.state = "chase"
        elif self.state == "attack":
            if self.timer <= 0:
                if sees and p.alive and dist < self.attack_range and random.random() < self.accuracy:
                    p.hurt(self.damage)
                    game.play("hurt")
                self.state, self.cooldown = "chase", self.attack_cooldown
        elif self.state == "chase":
            if sees and p.alive and dist < self.attack_range and self.cooldown <= 0:
                self.state, self.timer = "attack", 0.5
            elif dist > 1.0:
                step = self.speed * dt
                game.world.move(self, dx / dist * step, dy / dist * step)


class Imp(Enemy):
    @classmethod
    def make_frames(cls):
        return assets.enemy_frames((150, 60, 40), (255, 220, 0))


class Brute(Enemy):
    health = 200
    speed = 1.0
    radius = 0.45
    scale = 1.25
    damage = 20
    accuracy = 0.5
    attack_range = 2.0
    attack_cooldown = 1.2

    @classmethod
    def make_frames(cls):
        return assets.enemy_frames((70, 120, 60), (255, 40, 40), horns=False)


# Map character -> enemy class. Register new enemy types here.
ENEMY_TYPES = {"I": Imp, "B": Brute}
