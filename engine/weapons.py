import math
import os
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
    melee = False        # no clip / reloading (the status bar shows MELEE instead of ammo)
    infinite = False     # never uses up its clip or reloads (the status bar shows INF)

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
        if self.infinite or self.reloading or self.in_clip >= self.clip:
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
        if not (self.infinite or game.powerups.active("INFINITE AMMO")):
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


class Fist(Weapon):
    """Melee punch with the (mirrored) closed grapple hand. The fist rests low in the bottom-right,
    then: a short pull back, a fast jab up toward the crosshair (shrinking as it reaches away
    from you; the hit lands at full reach), a brief hold, and an eased return."""
    name, damage, cooldown = "FIST", 45, 0.38
    melee, sound = True, "swing"
    reach = 1.5          # world units
    arc = math.radians(35)  # half-angle of the area in front of you that a punch hits
    knockback = 0.3
    clip = 1
    margin, drop = 10, 52   # rest pose: low in the right corner
    PUNCH_SOUNDS = 6        # weapons/punch1.mp3 .. punch6.mp3 (one is picked at random per hit)
    # Keyframes over the punch (fraction of it): (time, offset x, offset y, scale, tilt degrees).
    # Offsets are fractions of the way from the rest pose to the target near the crosshair.
    KEYS = [(0.00, 0.00, 0.00, 1.00, 0),
            (0.12, -0.06, -0.08, 1.06, -4),  # pull back (down/right, a touch bigger: nearer you)
            (0.32, 1.00, 1.00, 0.68, 6),     # full reach
            (0.42, 0.97, 0.97, 0.70, 5),     # hold
            (1.00, 0.00, 0.00, 1.00, 0)]     # back to rest
    HIT_AT = 0.30
    WRIST = (0.06, 0.38)  # wrist centre, as fractions of the fist's size from its centre (mirrored sprite)
    ARM_W = 0.85          # forearm width as a fraction of the fist's width
    ELBOW = (5, 120)      # where the forearm ends, off the bottom-right corner (retro pixels past it)

    def __init__(self):
        self.swing_len = 0.0
        self.game = None
        self.hit_pending = False
        self._xf = {}  # (render scale, scale step, angle step) -> transformed sprite
        super().__init__()

    def make_frames(self, k):
        img = assets.held_sprite("weapons/grapple_hand_closed.png", 1.0, flip=True)  # left hand -> right
        scale = 100 * k / img.get_height()
        img = pg.transform.smoothscale(img, (round(img.get_width() * scale), round(img.get_height() * scale)))
        # Forearm (wrist at the top), sized to the fist once; stretched/rotated per frame in draw().
        arm = assets.held_sprite("weapons/grapple_arm.png", 1.0, flip=True)
        self.arm = pg.transform.smoothscale(arm, (round(img.get_width() * self.ARM_W), round(img.get_width() * self.ARM_W * arm.get_height() / arm.get_width())))
        return img, img

    def reload(self, game):
        pass

    def refill(self):
        pass

    def fire(self, game):
        if self.timer > 0:
            return False
        self.swing_len = self.timer = self.cooldown / game.powerups.fire_rate
        self.game, self.hit_pending = game, True  # the sound plays when the punch lands (see strike)
        return True

    def update(self, dt):
        super().update(dt)
        if self.hit_pending and self.progress() >= self.HIT_AT:
            self.hit_pending = False
            self.strike(self.game)

    def progress(self):
        """0..1 through the current punch (1 = idle)."""
        return 1.0 if self.swing_len <= 0 else 1 - self.timer / self.swing_len

    def strike(self, game):
        """Hit every enemy in a short arc in front of you (that isn't behind a wall)."""
        p = game.player
        if not p.alive:
            return
        hit = False
        for e in game.world.enemies:
            if not e.alive:
                continue
            dx, dy = e.x - p.x, e.y - p.y
            d = math.hypot(dx, dy)
            rel = (math.atan2(dy, dx) - p.angle + math.pi) % (2 * math.pi) - math.pi
            if d - e.radius > self.reach or abs(rel) > self.arc or not game.world.line_of_sight(p.x, p.y, e.x, e.y):
                continue
            e.hurt(self.damage * game.powerups.damage_mult)
            if d > 1e-6:
                game.world.move(e, dx / d * self.knockback, dy / d * self.knockback)
            hit = True
        game.play(f"punch{random.randint(1, self.PUNCH_SOUNDS)}" if hit else "swing")

    def pose(self):
        """(offset x, offset y, scale, tilt) at the current point of the punch."""
        u = self.progress()
        for (t0, *a), (t1, *b) in zip(self.KEYS, self.KEYS[1:]):
            if u <= t1:
                t = (u - t0) / (t1 - t0)
                t = 1 - (1 - t) ** 3 if t1 <= 0.32 else t * t * (3 - 2 * t)  # snappy out, smooth back
                return [x + (y - x) * t for x, y in zip(a, b)]
        return list(self.KEYS[-1][1:])

    def transformed(self, scale, tilt):
        """The fist scaled and tilted (cached in small steps; rotozoom is smooth but slow)."""
        key = (self.k, round(scale * 50), round(tilt / 2))
        if key not in self._xf:
            sc, a = key[1] / 50, key[2] * 2
            self._xf[key] = self.frames[0] if (sc, a) == (1.0, 0) else pg.transform.rotozoom(self.frames[0], a, sc)
        return self._xf[key]

    def draw(self, screen, bob):
        img = self.frames[0]
        k = self.k
        x, y = self.pos(img, bob)
        rest = pg.Vector2(x + img.get_width() / 2, y + img.get_height() / 2)
        # Knuckles (top of the sprite) end up just below and right of the crosshair.
        target = pg.Vector2(W * k / 2 + 12 * k, VIEW_H * k / 2 + 6 * k + img.get_height() * 0.68 / 2)
        ox, oy, scale, tilt = self.pose()
        centre = pg.Vector2(rest.x + (target.x - rest.x) * ox, rest.y + (target.y - rest.y) * oy)
        if self.progress() < 1:  # forearm from the wrist to off-screen, so the cut-off wrist never shows
            wrist = centre + pg.Vector2(self.WRIST[0] * img.get_width(), self.WRIST[1] * img.get_height()).rotate(-tilt) * scale
            elbow = pg.Vector2(W * k + self.ELBOW[0] * k + bob[0] * k, VIEW_H * k + self.ELBOW[1] * k + bob[1] * k)
            v = wrist - elbow
            length = v.length()
            if length > 1:
                width = max(1, round(self.arm.get_width() * scale))
                arm = pg.transform.scale(self.arm, (width, round(length) + width // 3))  # a little overlap under the fist
                arm = pg.transform.rotate(arm, math.degrees(math.atan2(-v.x, -v.y)))  # wrist end points at the fist
                mid = elbow + v / 2 + v.normalize() * (width // 6)
                screen.blit(arm, arm.get_rect(center=(round(mid.x), round(mid.y))))
        fist = self.transformed(scale, tilt)
        screen.blit(fist, fist.get_rect(center=(round(centre.x), round(centre.y))))


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
    pierce, sound, cheat, infinite = True, "beam", True, True
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
WEAPON_TYPES = [Fist, Pistol, Shotgun, AssaultRifle, TylerBeam]
STARTING_WEAPON = Pistol
