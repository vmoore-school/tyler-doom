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
        self._sized = {}
        self.prepare(1)

    def prepare(self, k):
        """Build (or reuse) the sprites for render scale k (1 = the retro 320x200 view)."""
        if k not in self._sized:
            self._sized[k] = list(self.make_frames(k))  # (idle, firing)
        self.k, self.frames = k, self._sized[k]

    def make_frames(self, k):
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
        recoil = int(self.timer / self.cooldown * 10 * self.k) if self.cooldown else 0
        x, y = self.pos(img, bob)
        screen.blit(img, (x, y + recoil))

    def pos(self, img, bob):
        """Top-left of the held weapon: anchored to the bottom-right corner of the view."""
        k = self.k
        return (int(W * k - self.margin * k - img.get_width() + bob[0] * k),
                int(VIEW_H * k - img.get_height() + self.drop * k + bob[1] * k))


class Pistol(Weapon):
    name, damage, cooldown, ammo = "PISTOL", 15, 0.35, 60

    def make_frames(self, k):
        img = assets.held_sprite("weapons/pistol.png", 0.33 * k)
        return img, assets.muzzle_flash(img, (0.36, 0.02), round(30 * k))


class Shotgun(Weapon):
    name, damage, cooldown, ammo = "SHOTGUN", 10, 0.9, 20
    pellets, spread, sound = 7, 0.07, "shotgun"

    def make_frames(self, k):
        img = assets.held_sprite("weapons/Shotgun.webp", 0.6 * k)
        return img, assets.muzzle_flash(img, (0.27, 0.03), round(44 * k))


class TylerBeam(Weapon):
    """Continuous piercing beam made of tiled Tyler faces, fired from an open purple palm."""
    name, damage, cooldown, ammo = "TYLER DEATH BEAM", 60, 0.08, 999
    pierce, sound, cheat = True, "beam", True
    margin, drop = 6, 4
    palm = (0.5, 0.6)  # beam origin as a fraction of the open hand
    _purple = None     # full-size purple hands, shared by every render scale

    def __init__(self):
        self.t = 0.0
        self.tiles = {}  # beam face tile per render scale
        super().__init__()

    def make_frames(self, k):
        # Left-hand photos: mirror them into a right hand and turn them purple (once, at full
        # size, since hue shifting is slow). Same scale for both so the hand doesn't change size.
        if TylerBeam._purple is None:
            TylerBeam._purple = [assets.hue_shift(assets.held_sprite(f, 1.0, flip=True), 255, sat=1.6)
                                 for f in ("weapons/grapple_hand_closed.png", "weapons/grapple_hand_open.png")]
        self.tiles[k] = assets.load_face(*assets.TYLER, size=(round(30 * k),) * 2)
        return [pg.transform.smoothscale(img, (round(img.get_width() * 0.4 * k), round(img.get_height() * 0.4 * k)))
                for img in TylerBeam._purple]

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

            k = self.k
            x1, y1 = W * k / 2, VIEW_H * k / 2
            pg.draw.line(screen, (255, 80, 220), (x0, y0), (x1, y1), max(1, round(6 * k)))
            n = 6
            scroll = (self.t * 4) % 1
            for i in reversed(range(n)):  # far tiles first, near tiles on top
                f = (i + scroll) / n
                size = max(1, int((30 - 20 * f) * k))
                x = x0 + (x1 - x0) * f + math.sin(self.t * 30 + i) * 2 * k
                y = y0 + (y1 - y0) * f
                img = pg.transform.scale(self.tiles[k], (size, size))  # not smoothscale: keeps the colorkey edge clean
                screen.blit(img, (x - size / 2, y - size / 2))
        super().draw(screen, bob)


# Order = number key bindings (1, 2, ...). Register new weapons here.
WEAPON_TYPES = [Pistol, Shotgun, TylerBeam]
