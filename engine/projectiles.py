"""Physics projectiles (thrown/bouncing) and short-lived visual effects.
Anything here is drawn by the renderer as a sprite: needs x, y, z, scale, image."""
import math
import os
import pygame as pg
from .assets import PHOTO_DIR


def _square(img, size):
    side = max(img.get_size())
    sq = pg.Surface((side, side), pg.SRCALPHA)
    sq.blit(img, ((side - img.get_width()) // 2, (side - img.get_height()) // 2))
    return pg.transform.smoothscale(sq, (size, size))


class Explosion:
    scale = 1.4
    duration = 0.45
    _frames = None

    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z - self.scale / 2
        self.t = 0.0
        self.dead = False

    @classmethod
    def frames(cls):
        if cls._frames is None:
            cls._frames = []
            for i in range(6):
                s = pg.Surface((64, 64), pg.SRCALPHA)
                r = 10 + i * 4
                fade = 255 - i * 40
                pg.draw.circle(s, (255, 90, 0, fade), (32, 32), r)
                pg.draw.circle(s, (255, 200, 40, fade), (32, 32), r * 2 // 3)
                pg.draw.circle(s, (255, 255, 200, fade), (32, 32), max(1, r // 3 - i))
                cls._frames.append(s)
        return cls._frames

    @property
    def image(self):
        f = self.frames()
        return f[min(len(f) - 1, int(self.t / self.duration * len(f)))]

    def update(self, dt, game):
        self.t += dt
        self.dead = self.t >= self.duration


class Grenade:
    """Bouncing grenade. Subclass and change stats / image_file for other throwables."""
    image_file = "grenade.png"
    scale = 0.35
    fuse = 1.8
    gravity = 12.0
    bounce = 0.45
    blast_radius = 3.0
    blast_damage = 160
    self_damage = 0.3     # fraction of blast damage the player takes
    spin_frames = 8
    _frames = {}

    def __init__(self, x, y, z, vx, vy, vz):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, vy, vz
        self.t = 0.0
        self.dead = False

    @classmethod
    def frames(cls):
        if cls not in Grenade._frames:
            img = _square(pg.image.load(os.path.join(PHOTO_DIR, cls.image_file)).convert_alpha(), 48)
            frames = []
            for i in range(cls.spin_frames):
                r = pg.transform.rotate(img, i * 360 / cls.spin_frames)
                frames.append(r.subsurface(r.get_rect().inflate(-(r.get_width() - 48), -(r.get_height() - 48))).copy())
            Grenade._frames[cls] = frames
        return Grenade._frames[cls]

    @property
    def image(self):
        f = self.frames()
        return f[int(self.t * 20) % len(f)]

    def update(self, dt, game):
        self.t += dt
        w = game.world
        nx = self.x + self.vx * dt
        if w.tile(int(nx), int(self.y)):
            self.vx *= -self.bounce
        else:
            self.x = nx
        ny = self.y + self.vy * dt
        if w.tile(int(self.x), int(ny)):
            self.vy *= -self.bounce
        else:
            self.y = ny
        self.vz -= self.gravity * dt
        self.z += self.vz * dt
        if self.z < 0:
            self.z, self.vz = 0.0, -self.vz * self.bounce
            self.vx *= 0.7
            self.vy *= 0.7
        direct_hit = any(e.alive and self.z < e.scale and math.hypot(e.x - self.x, e.y - self.y) < e.radius + 0.1
                         for e in w.enemies)
        if direct_hit or self.t >= self.fuse:
            self.explode(game)

    def explode(self, game):
        self.dead = True
        w = game.world
        w.effects.append(Explosion(self.x, self.y, self.z + 0.3))
        game.play("explosion")
        for target in w.enemies + [game.player]:
            d = math.hypot(target.x - self.x, target.y - self.y)
            if d >= self.blast_radius or not target.alive or not w.line_of_sight(self.x, self.y, target.x, target.y):
                continue
            dmg = self.blast_damage * (1 - d / self.blast_radius)
            if target is game.player:
                target.hurt(int(dmg * self.self_damage))
            else:
                target.hurt(dmg * game.powerups.damage_mult)
