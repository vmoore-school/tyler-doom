import math
import os
import pygame as pg
from .assets import PHOTO_DIR
from .settings import W, VIEW_H, WALL_H
from .world import cast_ray


class Grapple:
    """Hold to fire: a hand flies out from your left shoulder in 3D towards the crosshair, trailing
    a chain of forearms. It grabs whatever it hits (wall or floor, no range limit), closes, and
    reels you in, up the wall if you grabbed it high. Release (or arrive) to let go."""
    extend_speed = 40.0   # world units/sec the hand travels out
    retract_speed = 60.0
    pull_speed = 10.0
    max_lift = 1.3        # highest the pull can lift you (eye stays under the wall tops)
    shoulder = (0.35, -0.3, -0.45)  # forward, right, up from the eye: where the chain starts
    link_len = 0.7        # world length of one forearm link
    link_w = 0.16         # world width of the chain
    hand_size = 0.4       # world size of the hand

    def __init__(self):
        load = lambda f: pg.image.load(os.path.join(PHOTO_DIR, f)).convert_alpha()
        trim = lambda img: img.subsurface(img.get_bounding_rect()).copy()
        self.img_arm = trim(load("weapons/grapple_arm.png"))  # wrist at the top
        self.img_open = trim(load("weapons/grapple_hand_open.png"))
        self.img_closed = trim(load("weapons/grapple_hand_closed.png"))
        self.state = "idle"
        self.hand = self.target = None

    @property
    def busy(self):
        return self.state != "idle"

    def shoulder_pos(self, p):
        f, r, u = self.shoulder
        c, s = math.cos(p.angle), math.sin(p.angle)
        return (p.x + c * f - s * r, p.y + s * f + c * r, p.z + 0.5 + u)

    def fire(self, game):
        if self.state != "idle":
            return
        p, proj = game.player, game.renderer.proj
        c, s = math.cos(p.angle), math.sin(p.angle)
        eye = 0.5 + p.z
        slope = p.pitch / proj  # height gained per unit travelled along the aim (same as hitscan)
        dist = cast_ray(game.world, p.x, p.y, p.angle)[0]
        self.grabbed = True
        if slope < 0 and eye / -slope < dist:  # aiming at the floor before the wall
            dist = eye / -slope
        elif eye + slope * dist > WALL_H:  # aiming over the top of the wall: nothing to grab
            self.grabbed = False
        dist = max(0.1, dist - 0.05)  # sit just in front of the surface
        self.target = (p.x + c * dist, p.y + s * dist, max(0.0, eye + slope * dist))
        self.hand = self.shoulder_pos(p)
        self.state = "extend"

    def release(self):
        if self.state in ("extend", "pull"):
            self.state = "retract"

    def _move_hand(self, goal, speed, dt):
        """Move the hand towards goal; True once it's there."""
        d = [g - h for g, h in zip(goal, self.hand)]
        n = math.sqrt(sum(v * v for v in d))
        if n <= speed * dt:
            self.hand = tuple(goal)
            return True
        self.hand = tuple(h + v / n * speed * dt for h, v in zip(self.hand, d))
        return False

    def update(self, dt, game):
        p = game.player
        if self.state == "extend":
            if self._move_hand(self.target, self.extend_speed, dt):
                self.state = "pull" if self.grabbed else "retract"
        elif self.state == "pull":
            tx, ty, tz = self.target
            dx, dy = tx - p.x, ty - p.y
            flat = math.hypot(dx, dy)
            stop = p.radius + 0.2
            dz = min(self.max_lift, max(0.0, tz - 0.5)) - p.z  # bring your eye level with the grab point
            hx, hy = (dx / flat * (flat - stop), dy / flat * (flat - stop)) if flat > stop else (0.0, 0.0)
            dist = math.sqrt(hx * hx + hy * hy + dz * dz)
            if dist < 0.05:
                self.release()
                return
            step = min(dist, self.pull_speed * dt)
            ox, oy, oz = p.x, p.y, p.z
            game.world.move(p, hx / dist * step, hy / dist * step)
            p.z = max(0.0, p.z + dz / dist * step)
            p.vz = 0.0  # the hand holds you up; gravity takes over when you let go
            if math.sqrt((p.x - ox) ** 2 + (p.y - oy) ** 2 + (p.z - oz) ** 2) < step * 0.1:  # snagged
                self.release()
        elif self.state == "retract":
            if self._move_hand(self.shoulder_pos(p), self.retract_speed, dt):
                self.state = "idle"

    # --- drawing: project the chain and hand into the view with perspective ---

    def project(self, game, pt):
        """World point -> (screen x, screen y, depth), matching the renderer's projection."""
        p, r = game.player, game.renderer
        dx, dy = pt[0] - p.x, pt[1] - p.y
        c, s = math.cos(p.angle), math.sin(p.angle)
        depth = dx * c + dy * s
        side = -dx * s + dy * c
        return (W / 2 + side / depth * r.proj, r.horizon + r.proj / depth * (0.5 + p.z - pt[2]), depth)

    def draw(self, screen, game, bob):
        if self.state == "idle":
            return
        p, proj = game.player, game.renderer.proj
        a, b = self.shoulder_pos(p), self.hand
        length = math.dist(a, b)
        near = 0.15  # don't project anything closer than this
        pts = []
        for i in range(int(length / self.link_len) + 2):  # link boundaries, shoulder to hand
            t = min(1.0, i * self.link_len / length) if length else 1.0
            pts.append(tuple(av + (bv - av) * t for av, bv in zip(a, b)))
            if t >= 1.0:
                break
        bx, by = int(bob[0]), int(bob[1])
        angle = 0.0
        for far, close in reversed(list(zip(pts[1:], pts[:-1]))):  # far links first
            (fx, fy, fd), (cx, cy, cd) = self.project(game, far), self.project(game, close)
            if fd < near:
                continue
            if cd < near:  # clip the link at the near plane
                k = (near - fd) / (cd - fd)
                close = tuple(fv + (cv - fv) * k for fv, cv in zip(far, close))
                cx, cy, cd = self.project(game, close)
            vx, vy = fx - cx, fy - cy
            seg = math.hypot(vx, vy)
            width = proj / ((fd + cd) / 2) * self.link_w
            if seg < 1 or width < 1:
                continue
            angle = math.degrees(math.atan2(-vx, -vy))  # wrist end of the image points at the hand
            img = pg.transform.rotate(pg.transform.smoothscale(self.img_arm, (int(width), int(seg) + 2)), angle)
            screen.blit(img, img.get_rect(center=((fx + cx) / 2 + bx, (fy + cy) / 2 + by)))
        hx, hy, hd = self.project(game, b)
        if hd >= near:
            hand = self.img_closed if self.state == "pull" else self.img_open
            size = proj / hd * self.hand_size
            k = size / max(hand.get_size())
            img = pg.transform.smoothscale(hand, (max(1, int(hand.get_width() * k)), max(1, int(hand.get_height() * k))))
            img = pg.transform.rotate(img, angle)  # fingers point away from you
            screen.blit(img, img.get_rect(center=(hx + bx, hy + by)))
