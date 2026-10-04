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
    colors = ((255, 90, 0), (255, 200, 40), (255, 255, 200))  # outer, middle, core
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
                outer, mid, core = cls.colors
                pg.draw.circle(s, (*outer, fade), (32, 32), r)
                pg.draw.circle(s, (*mid, fade), (32, 32), r * 2 // 3)
                pg.draw.circle(s, (*core, fade), (32, 32), max(1, r // 3 - i))
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
                target.hurt(int(dmg * self.self_damage), "grenade")
            else:
                target.hurt(dmg * game.powerups.damage_mult)


class Puff(Explosion):
    """Purple magic burst (mage teleports, rune eruptions)."""
    scale = 1.0
    duration = 0.35
    colors = ((120, 30, 220), (190, 110, 255), (245, 225, 255))
    _frames = None


# --- enemy projectiles -----------------------------------------------------------
# All of these can be dodged: they travel at a visible speed, turn slowly or give a warning first.

def _hits_player(p, x, y, z_mid, reach):
    """Body is a cylinder from the player's feet to just over eye height (jumping lifts it)."""
    return p.alive and math.hypot(p.x - x, p.y - y) < reach + p.radius and p.z - 0.05 < z_mid < p.z + 0.75


class EnemyShot:
    """Projectile flying at `angle`. turn_rate > 0 makes it home in, but only that many radians/sec,
    so a sharp sidestep still shakes it. Subclass and set stats / draw() for new shots."""
    scale = 0.3
    speed = 8.0
    damage = 10
    life = 4.0
    turn_rate = 0.0
    radius = 0.12
    height = 0.45  # flight height of the shot's centre
    _frames = {}

    def __init__(self, x, y, angle, source, damage=None):
        self.x, self.y, self.angle, self.source = x, y, angle, source
        self.z = self.height - self.scale / 2  # renderer wants the sprite's bottom
        if damage is not None:
            self.damage = damage
        self.t = 0.0
        self.dead = False

    @classmethod
    def frames(cls):
        if cls not in EnemyShot._frames:
            EnemyShot._frames[cls] = cls.draw()
        return EnemyShot._frames[cls]

    @property
    def image(self):
        f = self.frames()
        return f[int(self.t * 12) % len(f)]

    def update(self, dt, game):
        self.t += dt
        if self.t > self.life:
            self.dead = True
            return
        p = game.player
        if self.turn_rate:
            want = math.atan2(p.y - self.y, p.x - self.x)
            diff = (want - self.angle + math.pi) % (2 * math.pi) - math.pi
            self.angle += max(-self.turn_rate * dt, min(self.turn_rate * dt, diff))
        nx = self.x + math.cos(self.angle) * self.speed * dt
        ny = self.y + math.sin(self.angle) * self.speed * dt
        if game.world.tile(int(nx), int(ny)):
            self.dead = True
            return
        self.x, self.y = nx, ny
        if _hits_player(p, self.x, self.y, self.height, self.radius):
            p.hurt(self.damage, self.source)
            game.play("hurt")
            self.dead = True


class Arrow(EnemyShot):
    """Fast and straight: strafe out of its line, or jump over it."""
    speed, damage, scale, height = 8.5, 10, 0.35, 0.4

    @staticmethod
    def draw():
        s = pg.Surface((32, 32), pg.SRCALPHA)
        pg.draw.line(s, (255, 240, 180), (2, 16), (26, 16), 2)
        pg.draw.polygon(s, (230, 230, 240), [(31, 16), (24, 12), (24, 20)])
        pg.draw.polygon(s, (220, 40, 40), [(2, 16), (7, 11), (9, 16)])
        pg.draw.polygon(s, (220, 40, 40), [(2, 16), (7, 21), (9, 16)])
        return [s]


class MagicOrb(EnemyShot):
    """Slow seeker. It turns gently, so sidestep it at the last moment."""
    speed, damage, scale, life, turn_rate, radius, height = 3.2, 14, 0.4, 5.0, 1.4, 0.15, 0.5

    @staticmethod
    def draw():
        frames = []
        for r in (11, 13):
            s = pg.Surface((32, 32), pg.SRCALPHA)
            pg.draw.circle(s, (120, 30, 220, 110), (16, 16), r + 3)
            pg.draw.circle(s, (180, 90, 255), (16, 16), r - 2)
            pg.draw.circle(s, (245, 225, 255), (16, 16), r // 2)
            frames.append(s)
        return frames


class Rune:
    """Glowing circle marked on the floor under the player. Erupts after `delay`: get out of it."""
    scale = 2.4          # sprite width, i.e. the circle's diameter
    delay = 1.2
    radius = 1.0         # damage radius (a little inside the drawn ring)
    damage = 20
    z = 0.0
    _frames = None

    def __init__(self, x, y, source, damage=None):
        self.x, self.y, self.source = x, y, source
        if damage is not None:
            self.damage = damage
        self.t = 0.0
        self.dead = False

    @classmethod
    def frames(cls):
        if cls._frames is None:
            cls._frames = []
            for i in range(6):  # brighter and redder as it charges
                s = pg.Surface((64, 64), pg.SRCALPHA)
                col = (150 + i * 20, 60 - i * 8, 255 - i * 30)
                rect = pg.Rect(2, 50, 60, 12)
                pg.draw.ellipse(s, (*col, 60 + i * 25), rect)
                pg.draw.ellipse(s, (*col, 255), rect, 2)
                pg.draw.ellipse(s, (255, 230, 255, 200), rect.inflate(-30, -6), 1)
                cls._frames.append(s)
        return cls._frames

    @property
    def image(self):
        f = self.frames()
        i = min(len(f) - 1, int(self.t / self.delay * len(f)))
        return f[i] if int(self.t * (6 + 14 * self.t / self.delay)) % 2 else f[max(0, i - 2)]  # flicker faster

    def update(self, dt, game):
        self.t += dt
        if self.t < self.delay:
            return
        self.dead = True
        game.world.effects.append(Puff(self.x, self.y, 0.5))
        game.play("explosion")
        p = game.player
        if p.alive and math.hypot(p.x - self.x, p.y - self.y) < self.radius and p.z < 0.3:
            p.hurt(self.damage, self.source)
            game.play("hurt")
