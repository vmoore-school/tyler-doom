"""Al Gore's Tree of Life, the enchanted golden apples it drops, and power-ups."""
import math
import os
import random
import pygame as pg
from .assets import PHOTO_DIR

# name -> (duration seconds, 0 = instant)
POWERUPS = {
    "QUAD DAMAGE": 12,
    "HASTE": 12,
    "INVULNERABLE": 8,
    "INFINITE AMMO": 12,
    "MEGA HEALTH": 0,
    "GRENADE BAG": 0,
}


class Powerups:
    def __init__(self):
        self.timers = {}
        self.message, self.message_t = "", 0.0

    def active(self, name):
        return self.timers.get(name, 0) > 0

    @property
    def damage_mult(self):
        return 3.0 if self.active("QUAD DAMAGE") else 1.0

    @property
    def speed_mult(self):
        return 1.7 if self.active("HASTE") else 1.0

    @property
    def fire_rate(self):
        return 2.0 if self.active("HASTE") else 1.0

    def grant(self, name, game):
        p = game.player
        if name == "MEGA HEALTH":
            p.health = min(200, p.health + 100)
        elif name == "GRENADE BAG":
            game.grenades += 3
        else:
            self.timers[name] = POWERUPS[name]
        self.message, self.message_t = name + "!", 2.0
        game.play("powerup")

    def grant_random(self, game):
        self.grant(random.choice(list(POWERUPS)), game)

    def update(self, dt, game):
        for k in self.timers:
            self.timers[k] = max(0.0, self.timers[k] - dt)
        self.message_t = max(0.0, self.message_t - dt)
        game.player.invulnerable = self.active("INVULNERABLE")


def _load(name):
    return pg.image.load(os.path.join(PHOTO_DIR, name)).convert_alpha()


class GoldenApple:
    scale = 0.3
    _image = None

    def __init__(self, x, y, z=1.2):
        self.x, self.y, self.z = x, y, z
        self.vz = 0.0
        self.t = random.random() * 6
        self.dead = False

    @property
    def image(self):
        if GoldenApple._image is None:
            GoldenApple._image = pg.transform.smoothscale(_load("apple.gif"), (32, 32))
        return GoldenApple._image

    def update(self, dt, game):
        self.t += dt
        if self.vz is not None:  # falling from the tree
            self.vz -= 9 * dt
            self.z += self.vz * dt
            if self.z <= 0.1:
                self.vz = None
        else:
            self.z = 0.1 + 0.05 * math.sin(self.t * 3)  # hover
        p = game.player
        if p.alive and math.hypot(p.x - self.x, p.y - self.y) < 0.6:
            self.dead = True
            game.powerups.grant_random(game)


class TreeOfLife:
    """Al Gore's Tree of Life. Periodically drops golden apples around itself."""
    scale = 1.8
    z = 0.0
    drop_every = 5.0
    max_apples = 3
    _image = None

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.timer = 1.0
        self.apples = []
        self.dead = False

    @classmethod
    def make_image(cls):
        s = pg.Surface((64, 64), pg.SRCALPHA)
        pg.draw.polygon(s, (90, 55, 25), [(27, 63), (37, 63), (35, 30), (29, 30)])
        pg.draw.line(s, (90, 55, 25), (31, 40), (20, 30), 3)
        pg.draw.line(s, (90, 55, 25), (33, 38), (45, 28), 3)
        for cx, cy, r in ((32, 22, 20), (16, 26, 12), (48, 26, 12), (22, 12, 11), (42, 12, 11)):
            pg.draw.circle(s, (30, 110, 40), (cx, cy), r)
        for cx, cy in ((12, 30), (52, 22), (20, 6), (46, 34), (8, 20)):
            pg.draw.circle(s, (240, 200, 60), (cx, cy), 2)
        # Al Gore, cut out of his dark backdrop, nestled in the canopy.
        gore = _load("al gore.png")
        w, h = gore.get_size()
        gore = pg.transform.smoothscale(gore.subsurface((int(w * 0.27), int(h * 0.08), int(w * 0.48), int(h * 0.87))), (26, 26))
        bg = gore.get_at((0, 0))
        for y in range(26):
            for x in range(26):
                c = gore.get_at((x, y))
                if sum(abs(c[i] - bg[i]) for i in range(3)) < 24:
                    gore.set_at((x, y), (0, 0, 0, 0))
        s.blit(gore, (19, 8))
        return s

    @property
    def image(self):
        if TreeOfLife._image is None:
            TreeOfLife._image = self.make_image()
        return TreeOfLife._image

    def update(self, dt, game):
        self.apples = [a for a in self.apples if not a.dead]
        self.timer -= dt
        if self.timer > 0 or len(self.apples) >= self.max_apples:
            return
        self.timer = self.drop_every
        for _ in range(10):  # find a free spot near the tree
            a = random.uniform(0, 2 * math.pi)
            r = random.uniform(0.6, 1.4)
            x, y = self.x + math.cos(a) * r, self.y + math.sin(a) * r
            if not game.world.tile(int(x), int(y)):
                apple = GoldenApple(x, y)
                self.apples.append(apple)
                game.world.items.append(apple)
                return
