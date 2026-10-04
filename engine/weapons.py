import math
import random
import pygame as pg
from . import assets
from .settings import W, VIEW_H


class Weapon:
    """Hitscan weapon base. Subclass and set stats / frames to add new guns.
    Ammo is unlimited; the cost is reloading: firing uses up the clip, and an empty clip (or R)
    starts a reload that takes `reload_time`, during which the gun dips out of view."""
    name = "weapon"
    short_name = None    # for the status bar when the name doesn't fit
    damage = 10
    cooldown = 0.4
    pellets = 1
    spread = 0.0         # radians, random per pellet
    clip = 12            # shots per reload
    reload_time = 1.5    # seconds
    unlock_wave = 1      # first wave you can use it (cheat weapons ignore this: see Game.select_weapon)
    sound = "pistol"
    pierce = False       # hit every enemy along the ray, not just the nearest
    margin = 0           # gap between the weapon and the right edge of the screen
    drop = 8             # pixels hidden below the bottom of the view
    cheat = False        # locked until the player opts in (and loses leaderboard eligibility)

    def __init__(self):
        self.timer = 0.0
        self.flash = 0.0
        self.in_clip = self.clip
        self.reload_t = 0.0  # time left on the current reload (0 = not reloading)
        self.channel = None  # reload sound, so it can be cut off when the reload ends
        self._sized = {}
        self.prepare(1)

    def prepare(self, k):
        """Build (or reuse) the sprites for render scale k (1 = the retro 320x200 view)."""
        if k not in self._sized:
            # convert_alpha: the display's own pixel format; RLE: transparent and opaque runs are
            # skipped / copied instead of blended pixel by pixel (much faster, above all in the browser)
            frames = [f.convert_alpha() for f in self.make_frames(k)]  # (idle, firing)
            for f in frames:
                # The photos are almost-but-not-quite opaque (alpha ~200-254), which RLE can't skip
                # blending for: make those pixels fully opaque.
                solid = pg.mask.from_surface(f, 199).to_surface(setcolor=(0, 0, 0, 255), unsetcolor=(0, 0, 0, 0))
                f.blit(solid, (0, 0), special_flags=pg.BLEND_RGBA_MAX)
                f.set_alpha(255, pg.RLEACCEL)
            self._sized[k] = frames
        self.k, self.frames = k, self._sized[k]

    def make_frames(self, k):
        raise NotImplementedError

    @property
    def reloading(self):
        return self.reload_t > 0

    def reload(self, game):
        if self.reloading or self.in_clip >= self.clip:
            return
        self.reload_t = self.reload_time
        self.flash = 0.0
        self.channel = game.play("reload")

    def refill(self):
        """Instantly full clip (between waves)."""
        self.stop_reload()
        self.in_clip = self.clip

    def stop_reload(self):
        """Cancel a reload (switching weapons). The clip stays as it was."""
        self.reload_t = 0.0
        if self.channel:
            self.channel.fadeout(80)
            self.channel = None

    def update(self, dt):
        self.timer = max(0.0, self.timer - dt)
        self.flash = max(0.0, self.flash - dt)
        if self.reloading:
            self.reload_t -= dt
            if self.reload_t <= 0:
                self.stop_reload()  # the sound is longer than most reloads: cut it off
                self.in_clip = self.clip

    def fire(self, game):
        if self.timer > 0 or self.reloading:
            return False
        if self.in_clip <= 0:
            self.reload(game)
            return False
        if not game.powerups.active("INFINITE AMMO"):
            self.in_clip -= 1
        self.timer = self.cooldown / game.powerups.fire_rate
        self.flash = 0.08
        for _ in range(self.pellets):
            game.hitscan(random.uniform(-self.spread, self.spread), self.damage * game.powerups.damage_mult, self.pierce)
        game.play(self.sound)
        if self.in_clip <= 0:
            self.reload(game)
        return True

    def reload_dip(self):
        """How far the gun has dipped out of view for the reload, 0..1 (down, then back up)."""
        if not self.reloading:
            return 0.0
        return math.sin(math.pi * (1 - self.reload_t / self.reload_time)) ** 0.5

    def draw(self, screen, bob):
        img = self.frames[1 if self.flash > 0 else 0]
        recoil = int(self.timer / self.cooldown * 10 * self.k) if self.cooldown else 0
        x, y = self.pos(img, bob)
        screen.blit(img, (x, y + recoil + int(self.reload_dip() * img.get_height() * 0.7)))

    def pos(self, img, bob):
        """Top-left of the held weapon: anchored to the bottom-right corner of the view."""
        k = self.k
        return (int(W * k - self.margin * k - img.get_width() + bob[0] * k),
                int(VIEW_H * k - img.get_height() + self.drop * k + bob[1] * k))


class Pistol(Weapon):
    name, damage, cooldown = "PISTOL", 15, 0.35
    clip, reload_time = 12, 1.3

    def make_frames(self, k):
        img = assets.held_sprite("weapons/pistol.png", 0.33 * k)
        return img, assets.muzzle_flash(img, (0.36, 0.02), round(30 * k))


class Shotgun(Weapon):
    name, damage, cooldown = "SHOTGUN", 10, 0.9
    pellets, spread, sound = 7, 0.07, "shotgun"
    clip, reload_time, unlock_wave = 6, 2.2, 7

    def make_frames(self, k):
        img = assets.held_sprite("weapons/Shotgun.webp", 0.6 * k)
        return img, assets.muzzle_flash(img, (0.27, 0.03), round(44 * k))


class AssaultRifle(Weapon):
    """Fast full-auto with a little spread."""
    name, damage, cooldown = "ASSAULT RIFLE", 12, 0.1
    spread, sound = 0.02, "rifle"
    clip, reload_time, unlock_wave = 30, 2.0, 21

    def make_frames(self, k):
        img = assets.held_sprite("weapons/AssaultRifle.png", 0.3 * k)
        return img, assets.muzzle_flash(img, (0.06, 0.18), round(34 * k))


class TylerBeam(Weapon):
    """Continuous piercing beam made of tiled Tyler faces, fired from an open purple palm."""
    name, damage, cooldown = "TYLER DEATH BEAM", 60, 0.08
    short_name = "TYLER BEAM"
    pierce, sound, cheat = True, "beam", True
    clip, reload_time = 100, 2.5
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
        if super().fire(game) and not self.reloading:
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


# Register new weapons here. Number keys (1, 2, ...) go to the non-cheat weapons in this order;
# cheat weapons have their own key (T for the Tyler Death Beam).
WEAPON_TYPES = [Pistol, Shotgun, AssaultRifle, TylerBeam]
