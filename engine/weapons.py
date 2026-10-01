import random
import pygame as pg
from . import assets
from .settings import W, H


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

    def __init__(self):
        self.timer = 0.0
        self.flash = 0.0
        idle, fire = self.make_frames()
        size = (int(idle.get_width() * self.draw_scale), int(idle.get_height() * self.draw_scale))
        self.frames = [pg.transform.scale(idle, size), pg.transform.scale(fire, size)]

    def make_frames(self):
        raise NotImplementedError

    def update(self, dt):
        self.timer = max(0.0, self.timer - dt)
        self.flash = max(0.0, self.flash - dt)

    def fire(self, game):
        if self.timer > 0 or self.ammo <= 0:
            return False
        self.ammo -= 1
        self.timer = self.cooldown
        self.flash = 0.08
        for _ in range(self.pellets):
            game.hitscan(random.uniform(-self.spread, self.spread), self.damage)
        game.play(self.sound)
        return True

    def draw(self, screen, bob):
        img = self.frames[1 if self.flash > 0 else 0]
        recoil = int(self.timer / self.cooldown * 10) if self.cooldown else 0
        x = W // 2 - img.get_width() // 2 + int(bob[0])
        y = H - img.get_height() + 8 + int(bob[1]) + recoil
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


# Order = number key bindings (1, 2, ...). Register new weapons here.
WEAPON_TYPES = [Pistol, Shotgun]
