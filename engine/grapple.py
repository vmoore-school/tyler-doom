import math
import os
import pygame as pg
from .assets import PHOTO_DIR
from .settings import VIEW_H
from .world import cast_ray


class Grapple:
    """Hold to fire: the arm stretches out, grabs the wall, and pulls the player in."""
    range = 14.0
    extend_speed = 40.0   # world units/sec the hand travels
    pull_speed = 10.0
    retract_time = 0.15
    arm_width = 60
    screen_x = 25         # left edge of the arm on screen
    min_len, max_len = 30, 125  # on-screen arm height range (pixels)

    def __init__(self):
        load = lambda f: pg.image.load(os.path.join(PHOTO_DIR, f)).convert_alpha()
        self.img_open, self.img_closed = load("grapple_open.png"), load("grapple_close.png")
        self.state = "idle"
        self.t = 0.0
        self.target = None

    @property
    def busy(self):
        return self.state != "idle"

    def fire(self, game):
        if self.state != "idle":
            return
        p = game.player
        dist = cast_ray(game.world, p.x, p.y, p.angle)[0]
        self.reach = min(dist, self.range)
        stop = max(0.0, dist - p.radius - 0.2)
        self.target = (p.x + math.cos(p.angle) * stop, p.y + math.sin(p.angle) * stop) if dist <= self.range else None
        self.state, self.t = "extend", 0.0

    def release(self):
        if self.state in ("extend", "pull"):
            self.state, self.t = "retract", 0.0

    def update(self, dt, game):
        self.t += dt
        if self.state == "extend":
            if self.t * self.extend_speed >= self.reach:
                self.state, self.t = ("pull" if self.target else "retract"), 0.0
        elif self.state == "pull":
            p = game.player
            dx, dy = self.target[0] - p.x, self.target[1] - p.y
            dist = math.hypot(dx, dy)
            step = min(dist, self.pull_speed * dt)
            if dist < 0.05:
                self.release()
                return
            ox, oy = p.x, p.y
            game.world.move(p, dx / dist * step, dy / dist * step)
            if math.hypot(p.x - ox, p.y - oy) < step * 0.1:  # snagged on a corner
                self.release()
        elif self.state == "retract" and self.t >= self.retract_time:
            self.state = "idle"

    def progress(self):
        if self.state == "extend":
            return min(1.0, self.t * self.extend_speed / max(self.reach, 1e-3))
        if self.state == "pull":
            return 1.0
        if self.state == "retract":
            return max(0.0, 1 - self.t / self.retract_time)
        return 0.0

    def draw(self, screen, bob):
        if self.state == "idle":
            return
        img = self.img_closed if self.state == "pull" else self.img_open
        h = int(self.min_len + (self.max_len - self.min_len) * self.progress())
        arm = pg.transform.scale(img, (self.arm_width, h))  # stretchy on purpose
        x = self.screen_x + int(bob[0])
        screen.blit(arm, (x, VIEW_H - h + 8 + int(bob[1])))
