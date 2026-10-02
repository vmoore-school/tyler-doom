import math
import random
from . import assets


class Player:
    radius = 0.25

    def __init__(self, x, y, angle=0.0):
        self.x, self.y, self.angle = x, y, angle
        self.pitch = 0.0  # vertical look: horizon offset in screen pixels (+ = looking up)
        self.z = self.vz = 0.0  # jump height above the floor
        self.health = 100
        self.hurt_flash = 0.0
        self.invulnerable = False

    @property
    def alive(self):
        return self.health > 0

    def hurt(self, dmg):
        if self.invulnerable:
            return
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
    head_frac = 0.38     # top fraction of the sprite that counts as a headshot
    _frame_cache = {}

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.hp = self.health
        self.state = "idle"
        self.timer = self.cooldown = self.anim = self.dead_time = 0.0

    @classmethod
    def make_frames(cls):
        raise NotImplementedError

    @classmethod
    def get_frames(cls):
        if cls not in Enemy._frame_cache:
            Enemy._frame_cache[cls] = cls.make_frames()
        return Enemy._frame_cache[cls]

    @property
    def frames(self):
        return self.get_frames()

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

    def perform_attack(self, game, sees, dist):
        """Resolve an attack once the wind-up finishes. Override for special attacks."""
        if sees and dist < self.attack_range and random.random() < self.accuracy:
            game.player.hurt(self.damage)
            game.play("hurt")

    def update(self, dt, game):
        if not self.alive:
            self.dead_time += dt
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
                if p.alive:
                    self.perform_attack(game, sees, dist)
                self.state, self.cooldown = "chase", self.attack_cooldown
        elif self.state == "chase":
            if sees and p.alive and dist < self.attack_range and self.cooldown <= 0:
                self.state, self.timer = "attack", 0.5
            elif dist > 1.0:
                if not sees:  # path around walls towards the player
                    nxt = game.world.next_step(self.x, self.y)
                    if nxt:
                        dx, dy = nxt[0] - self.x, nxt[1] - self.y
                        dist = math.hypot(dx, dy) or 1e-6
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


class Friend(Enemy):
    """Demon body with a face cut out of a photo in the assets/ folder."""
    photo = None
    crop = (0, 0, 1, 1)  # face region as fractions (x, y, w, h)
    rotate = 0
    skin = (120, 60, 50)
    head_frac = 0.47

    @classmethod
    def make_frames(cls):
        face = assets.load_face(cls.photo, cls.crop, cls.rotate)
        return assets.enemy_frames(cls.skin, (255, 220, 0), face=face)


class Grinner(Friend):
    photo, crop, rotate = "Image.jpeg", (0.25, 0.12, 0.6, 0.55), -90
    speed, skin = 2.0, (60, 60, 70)


class Starer(Friend):
    photo, crop = "Image.png", (0.15, 0.0, 0.65, 0.55)
    accuracy, skin = 0.75, (40, 40, 45)


class Tyler(Friend):
    photo, crop = "Tyler photo 1.jpg", (0.25, 0.22, 0.5, 0.48)
    health, skin = 90, (150, 150, 155)


class Kieran(Friend):
    photo, crop = "w4efwfew.png", (0.08, 0.23, 0.84, 0.62)
    health, speed, radius, scale, damage = 160, 1.1, 0.45, 1.25, 15
    skin = (70, 75, 90)


# Map character -> enemy class. Register new enemy types here.
ENEMY_TYPES = {"I": Imp, "B": Brute, "G": Grinner, "S": Starer, "T": Tyler, "K": Kieran}
# Classes that waves pick from at random.
SPAWN_POOL = [Imp, Brute, Grinner, Starer, Tyler, Kieran]
