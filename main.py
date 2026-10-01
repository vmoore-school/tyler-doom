import math
import sys
import pygame as pg

from engine import assets
from engine.settings import W, H, SCALE, FPS, MOUSE_SENS, MOVE_SPEED
from engine.world import World, LEVEL, cast_ray
from engine.entities import Player
from engine.weapons import WEAPON_TYPES
from engine.render import Renderer


class Game:
    def __init__(self):
        pg.mixer.pre_init(22050, -16, 1, 256)
        pg.init()
        self.window = pg.display.set_mode((W * SCALE, H * SCALE))
        pg.display.set_caption("Doom-ish")
        self.screen = pg.Surface((W, H))
        self.clock = pg.time.Clock()
        self.font = pg.font.Font(None, 18)
        self.big = pg.font.Font(None, 32)
        self.renderer = Renderer({k: f() for k, f in assets.WALLS.items()})
        self.sounds = {
            "pistol": assets.noise_sound(0.15, 0.5, 3, 1),
            "shotgun": assets.noise_sound(0.35, 0.8, 2, 2),
            "hurt": assets.noise_sound(0.1, 0.3, 1, 3),
        }
        pg.event.set_grab(True)
        pg.mouse.set_visible(False)
        self.reset()

    def reset(self):
        self.world = World(LEVEL)
        self.player = Player(*self.world.start)
        self.weapons = [w() for w in WEAPON_TYPES]
        self.weapon = self.weapons[0]
        self.walk_t = 0.0

    def play(self, name):
        snd = self.sounds.get(name)
        if snd:
            snd.play()

    def hitscan(self, angle_offset, damage):
        """Fire a ray from the player; damage the nearest enemy in front of the wall."""
        p = self.player
        ang = p.angle + angle_offset
        wall = cast_ray(self.world, p.x, p.y, ang)[0]
        c, s = math.cos(ang), math.sin(ang)
        best = None
        for e in self.world.enemies:
            if not e.alive:
                continue
            dx, dy = e.x - p.x, e.y - p.y
            along = dx * c + dy * s
            if 0 < along < wall and abs(dy * c - dx * s) < e.radius:
                if best is None or along < best[0]:
                    best = (along, e)
        if best:
            best[1].hurt(damage)

    def handle_input(self, dt):
        for ev in pg.event.get():
            if ev.type == pg.QUIT or (ev.type == pg.KEYDOWN and ev.key == pg.K_ESCAPE):
                pg.quit()
                sys.exit()
            if ev.type == pg.KEYDOWN:
                if ev.key == pg.K_r and not self.player.alive:
                    self.reset()
                elif pg.K_1 <= ev.key < pg.K_1 + len(self.weapons):
                    self.weapon = self.weapons[ev.key - pg.K_1]
            if ev.type == pg.MOUSEMOTION:
                self.player.angle += ev.rel[0] * MOUSE_SENS
        p = self.player
        if not p.alive:
            return
        keys = pg.key.get_pressed()
        if keys[pg.K_LEFT]:
            p.angle -= 2.5 * dt
        if keys[pg.K_RIGHT]:
            p.angle += 2.5 * dt
        fwd = (keys[pg.K_w] or keys[pg.K_UP]) - (keys[pg.K_s] or keys[pg.K_DOWN])
        strafe = keys[pg.K_d] - keys[pg.K_a]
        if fwd or strafe:
            c, s = math.cos(p.angle), math.sin(p.angle)
            mx, my = fwd * c - strafe * s, fwd * s + strafe * c
            n = math.hypot(mx, my)
            step = MOVE_SPEED * dt / n
            self.world.move(p, mx * step, my * step)
            self.walk_t += dt
        if pg.mouse.get_pressed()[0] or keys[pg.K_SPACE]:
            self.weapon.fire(self)

    def update(self, dt):
        self.weapon.update(dt)
        self.player.hurt_flash = max(0.0, self.player.hurt_flash - dt)
        for e in self.world.enemies:
            e.update(dt, self)

    def draw_hud(self):
        scr, p = self.screen, self.player
        cx, cy = W // 2, H // 2
        pg.draw.line(scr, (0, 255, 0), (cx - 4, cy), (cx + 4, cy))
        pg.draw.line(scr, (0, 255, 0), (cx, cy - 4), (cx, cy + 4))
        if p.hurt_flash > 0:
            ov = pg.Surface((W, H), pg.SRCALPHA)
            ov.fill((255, 0, 0, int(p.hurt_flash * 300)))
            scr.blit(ov, (0, 0))
        pg.draw.rect(scr, (30, 30, 30), (0, H - 14, W, 14))
        txt = f"HEALTH {p.health}    {self.weapon.name} {self.weapon.ammo}    [1-{len(self.weapons)}] switch"
        scr.blit(self.font.render(txt, True, (220, 200, 60)), (4, H - 12))
        msg = None
        if not p.alive:
            msg = "YOU DIED - press R"
        elif not any(e.alive for e in self.world.enemies):
            msg = "ROOM CLEAR"
        if msg:
            img = self.big.render(msg, True, (255, 40, 40))
            scr.blit(img, img.get_rect(center=(cx, cy - 30)))

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000, 0.05)
            self.handle_input(dt)
            self.update(dt)
            self.renderer.render(self.screen, self.world, self.player)
            if self.player.alive:
                bob = (math.sin(self.walk_t * 8) * 4, abs(math.cos(self.walk_t * 8)) * 4)
                self.weapon.draw(self.screen, bob)
            self.draw_hud()
            pg.transform.scale(self.screen, self.window.get_size(), self.window)
            pg.display.flip()


if __name__ == "__main__":
    Game().run()
