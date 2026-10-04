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
    pierce = False       # hit every enemy along the ray, not just the nearest
    margin = 0           # gap between the weapon and the right edge of the screen
    drop = 8             # pixels hidden below the bottom of the view
    cheat = False        # locked until the player opts in (and loses leaderboard eligibility)

    def __init__(self):
        self.timer = 0.0
        self.flash = 0.0
        self.frames = list(self.make_frames())  # (idle, firing), already at screen size

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
        x, y = self.pos(img, bob)
        screen.blit(img, (x, y + recoil))

    def pos(self, img, bob):
        """Top-left of the held weapon: anchored to the bottom-right corner."""
        return (W - self.margin - img.get_width() + int(bob[0]),
                VIEW_H - img.get_height() + self.drop + int(bob[1]))


class Pistol(Weapon):
    name, damage, cooldown, ammo = "PISTOL", 15, 0.35, 60

    def make_frames(self):
        img = assets.held_sprite("weapons/pistol.png", 0.33)
        return img, assets.muzzle_flash(img, (0.36, 0.02), 30)


class Shotgun(Weapon):
    name, damage, cooldown, ammo = "SHOTGUN", 10, 0.9, 20
    pellets, spread, sound = 7, 0.07, "shotgun"

    def make_frames(self):
        img = assets.held_sprite("weapons/Shotgun.webp", 0.6)
        return img, assets.muzzle_flash(img, (0.27, 0.03), 44)


class TylerBeam(Weapon):
    """Continuous piercing beam made of tiled Tyler faces, fired from an open purple palm."""
    name, damage, cooldown, ammo = "TYLER DEATH BEAM", 60, 0.08, 999
    pierce, sound, cheat = True, "beam", True
    margin, drop = 6, 4
    palm = (0.5, 0.6)  # beam origin as a fraction of the open hand

    def __init__(self):
        super().__init__()
        self.tile = assets.load_face(*assets.TYLER, size=(48, 48))
        self.t = 0.0

    def make_frames(self):
        # Left-hand photos: mirror them into a right hand and turn them purple. Same scale for
        # both so the hand doesn't change size when it opens.
        closed, open_ = (assets.hue_shift(assets.held_sprite(f, 0.4, flip=True), 255, sat=1.6)
                         for f in ("weapons/grapple_hand_closed.png", "weapons/grapple_hand_open.png"))
        return closed, open_

    def fire(self, game):
        if super().fire(game):
            self.flash = self.cooldown + 0.02  # keep beam visible while held

    def update(self, dt):
        super().update(dt)
        self.t += dt

    def draw(self, screen, bob):
        if self.flash > 0:  # beam first, so the hand covers its base
            hand = self.frames[1]
            hx, hy = self.pos(hand, bob)
            x0, y0 = hx + hand.get_width() * self.palm[0], hy + hand.get_height() * self.palm[1]

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
        super().draw(screen, bob)


# Order = number key bindings (1, 2, ...). Register new weapons here.
WEAPON_TYPES = [Pistol, Shotgun, TylerBeam]
