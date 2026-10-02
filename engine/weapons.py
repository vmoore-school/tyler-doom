import math
import random
import pygame as pg
from . import assets
from .settings import W, VIEW_H


class Weapon:
    """Hitscan weapon base. Subclass and set stats / frames to add new guns."""
    name = "weapon"
    damage = 10
    cooldown = 0.4
    pellets = 1
    spread = 0.0         # radians, random per pellet
    ammo = 50
    sound = "pistol"
    draw_scale = 2.5
    pierce = False       # hit every enemy along the ray, not just the nearest
    offset_x = 0         # horizontal screen offset of the held weapon

    def __init__(self):
        self.timer = 0.0
        self.flash = 0.0
        idle, fire = self.make_frames()
        size = (int(idle.get_width() * self.draw_scale), int(idle.get_height() * self.draw_scale))
        self.frames = [pg.transform.scale(idle, size), pg.transform.scale(fire, size)]

    def make_frames(self):
        raise NotImplementedError

    def refill(self):
        self.ammo = type(self).ammo

    def update(self, dt):
        self.timer = max(0.0, self.timer - dt)
        self.flash = max(0.0, self.flash - dt)

    def fire(self, game):
        if self.timer > 0 or self.ammo <= 0:
            return False
        if not game.powerups.active("INFINITE AMMO"):
            self.ammo -= 1
        self.timer = self.cooldown / game.powerups.fire_rate
        self.flash = 0.08
        for _ in range(self.pellets):
            game.hitscan(random.uniform(-self.spread, self.spread), self.damage * game.powerups.damage_mult, self.pierce)
        game.play(self.sound)
        return True

    def draw(self, screen, bob):
        img = self.frames[1 if self.flash > 0 else 0]
        recoil = int(self.timer / self.cooldown * 10) if self.cooldown else 0
        x = W // 2 + self.offset_x - img.get_width() // 2 + int(bob[0])
        y = VIEW_H - img.get_height() + 8 + int(bob[1]) + recoil
        screen.blit(img, (x, y))


class Pistol(Weapon):
    name, damage, cooldown, ammo = "PISTOL", 15, 0.35, 60

    def make_frames(self):
        return assets.pistol(), assets.pistol(True)


class Shotgun(Weapon):
    name, damage, cooldown, ammo = "SHOTGUN", 10, 0.9, 20
    pellets, spread, sound = 7, 0.07, "shotgun"

    def make_frames(self):
        return assets.shotgun(), assets.shotgun(True)


class TylerBeam(Weapon):
    """Continuous piercing beam made of tiled Tyler faces."""
    name, damage, cooldown, ammo = "TYLER DEATH BEAM", 60, 0.08, 999
    pierce, sound = True, "beam"
    offset_x, draw_scale = 75, 2.0

    def __init__(self):
        super().__init__()
        self.tile = assets.load_face(*assets.TYLER, size=(48, 48))
        self.t = 0.0

    def make_frames(self):
        return assets.tyler_beam(), assets.tyler_beam(True)

    def fire(self, game):
        if super().fire(game):
            self.flash = self.cooldown + 0.02  # keep beam visible while held

    def update(self, dt):
        super().update(dt)
        self.t += dt

    def draw(self, screen, bob):
        super().draw(screen, bob)
        if self.flash > 0:
            gun_h = self.frames[0].get_height()
            x0 = W / 2 + self.offset_x + bob[0]
            y0 = VIEW_H - gun_h + 8 + bob[1] + 14 * self.draw_scale  # muzzle

            x1, y1 = W / 2, VIEW_H / 2
            pg.draw.line(screen, (255, 80, 220), (x0, y0), (x1, y1), 6)
            n = 6
            scroll = (self.t * 4) % 1
            for i in reversed(range(n)):  # far tiles first, near tiles on top
                f = (i + scroll) / n
                size = int(30 - 20 * f)
                x = x0 + (x1 - x0) * f + math.sin(self.t * 30 + i) * 2
                y = y0 + (y1 - y0) * f
                img = pg.transform.scale(self.tile, (size, size))
                screen.blit(img, (x - size / 2, y - size / 2))


# Order = number key bindings (1, 2, ...). Register new weapons here.
WEAPON_TYPES = [Pistol, Shotgun, TylerBeam]
