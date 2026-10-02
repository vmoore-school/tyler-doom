import math
import sys
import pygame as pg

from engine import assets
from engine.settings import W, H, VIEW_H, BAR_H, SCALE, FPS, MOUSE_SENS, MOVE_SPEED, PITCH_SENS, MAX_PITCH, HEADSHOT_MULT
from engine.world import World, LEVEL, cast_ray
from engine.entities import Player, SPAWN_POOL
from engine.weapons import WEAPON_TYPES
from engine.render import Renderer
from engine.grapple import Grapple
from engine.webcam import WebcamPortrait
from engine.projectiles import Grenade
from engine.pickups import Powerups, TreeOfLife


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
        self.bar_font = pg.font.Font(None, 26)
        self.label_font = pg.font.Font(None, 12)
        self.portrait = WebcamPortrait(size=(BAR_H - 4, BAR_H - 4))
        self.renderer = Renderer({k: f() for k, f in assets.WALLS.items()})
        self.sounds = {
            "pistol": assets.noise_sound(0.15, 0.5, 3, 1),
            "shotgun": assets.noise_sound(0.35, 0.8, 2, 2),
            "hurt": assets.noise_sound(0.1, 0.3, 1, 3),
            "beam": assets.noise_sound(0.09, 0.15, 0.5, 4),
            "explosion": assets.noise_sound(0.7, 1.0, 1.5, 5),
            "powerup": assets.noise_sound(0.25, 0.25, 0.3, 6),
        }
        Grenade.frames()
        self.grenade_icon = pg.transform.smoothscale(Grenade.frames()[0], (14, 14))
        for cls in SPAWN_POOL:  # build sprites up front to avoid mid-game hitches
            cls.get_frames()
        pg.event.set_grab(True)
        pg.mouse.set_visible(False)
        self.reset()

    def reset(self):
        self.world = World(LEVEL)
        self.player = Player(*self.world.start)
        self.weapons = [w() for w in WEAPON_TYPES]
        self.weapon = self.weapons[0]
        self.grapple = Grapple()
        self.minimap = self.build_minimap()
        self.walk_t = 0.0
        self.headshot_flash = 0.0
        self.grenades = self.max_grenades = 3
        self.powerups = Powerups()
        self.throw_t = 0.0  # throw animation / cooldown timer
        self.wave = 1
        self.countdown = None
        self.world.spawn_wave(self.wave_size(), self.player)
        self.world.spawn_tree(self.player)

    MINIMAP_CELL = 2

    def build_minimap(self):
        c = self.MINIMAP_CELL
        grid = self.world.grid
        surf = pg.Surface((len(grid[0]) * c, len(grid) * c), pg.SRCALPHA)
        surf.fill((0, 0, 0, 140))
        for y, row in enumerate(grid):
            for x, t in enumerate(row):
                if t:
                    surf.fill((150, 150, 150, 200), (x * c, y * c, c, c))
        return surf

    def draw_minimap(self):
        c, ox, oy = self.MINIMAP_CELL, W - self.minimap.get_width() - 3, 3
        scr, p = self.screen, self.player
        scr.blit(self.minimap, (ox, oy))
        to_px = lambda x, y: (ox + int(x * c), oy + int(y * c))
        for e in self.world.enemies:
            if e.alive:
                scr.fill((255, 40, 40), (*to_px(e.x - 0.5, e.y - 0.5), 2, 2))

        for i in self.world.items:
            col = (0, 200, 60) if isinstance(i, TreeOfLife) else (255, 215, 0)
            scr.fill(col, (*to_px(i.x - 0.5, i.y - 0.5), 2, 2))
        for g in self.world.projectiles:
            scr.fill((255, 160, 0), (*to_px(g.x, g.y), 1, 1))
        px, py = to_px(p.x, p.y)
        pg.draw.line(scr, (255, 255, 0), (px, py), (px + int(math.cos(p.angle) * 5), py + int(math.sin(p.angle) * 5)))
        scr.fill((0, 255, 0), (px - 1, py - 1, 3, 3))

    def wave_size(self):
        return self.wave + 2

    def play(self, name):
        snd = self.sounds.get(name)
        if snd:
            snd.play()

    def hitscan(self, angle_offset, damage, pierce=False):
        """Fire a ray from the player; damage the nearest enemy in front of the wall
        (or every enemy along the ray if pierce). Hits in the head zone deal bonus damage."""
        p = self.player
        ang = p.angle + angle_offset
        wall = cast_ray(self.world, p.x, p.y, ang)[0]
        c, s = math.cos(ang), math.sin(ang)
        hits = []
        for e in self.world.enemies:
            if not e.alive:
                continue
            dx, dy = e.x - p.x, e.y - p.y
            along = dx * c + dy * s
            if not (0 < along < wall and abs(dy * c - dx * s) < e.radius):
                continue
            # Height (world units, floor = 0, eye = 0.5) the crosshair points at at this distance.
            z = 0.5 + p.pitch * along / self.renderer.proj
            if 0 <= z <= e.scale:
                hits.append((along, e, z >= e.scale * (1 - e.head_frac)))
        hits.sort(key=lambda h: h[0])
        for _, e, head in (hits if pierce else hits[:1]):
            if head:
                self.headshot_flash = 0.4
            e.hurt(damage * HEADSHOT_MULT if head else damage)

    def throw_grenade(self):
        p = self.player
        if not p.alive or self.grenades <= 0 or self.throw_t > 0:
            return
        self.grenades -= 1
        self.throw_t = 0.4
        c, s = math.cos(p.angle), math.sin(p.angle)
        up = p.pitch / self.renderer.proj  # look up to throw higher/further
        speed = 7.0
        self.world.projectiles.append(
            Grenade(p.x + c * 0.3, p.y + s * 0.3, 0.45, c * speed, s * speed, 2.5 + up * speed))

    def handle_input(self, dt):
        for ev in pg.event.get():
            if ev.type == pg.QUIT or (ev.type == pg.KEYDOWN and ev.key == pg.K_ESCAPE):
                self.portrait.stop()
                pg.quit()
                sys.exit()
            if ev.type == pg.KEYDOWN:
                if ev.key == pg.K_r and not self.player.alive:
                    self.reset()
                elif pg.K_1 <= ev.key < pg.K_1 + len(self.weapons):
                    self.weapon = self.weapons[ev.key - pg.K_1]
            if (ev.type == pg.MOUSEBUTTONDOWN and ev.button == 3) or (ev.type == pg.KEYDOWN and ev.key == pg.K_e):
                if self.player.alive:
                    self.grapple.fire(self)
            if (ev.type == pg.MOUSEBUTTONUP and ev.button == 3) or (ev.type == pg.KEYUP and ev.key == pg.K_e):
                self.grapple.release()
            if (ev.type == pg.MOUSEBUTTONDOWN and ev.button == 2) or (ev.type == pg.KEYDOWN and ev.key == pg.K_g):
                self.throw_grenade()
            if ev.type == pg.MOUSEMOTION:
                self.player.angle += ev.rel[0] * MOUSE_SENS
                self.player.pitch = max(-MAX_PITCH, min(MAX_PITCH, self.player.pitch - ev.rel[1] * PITCH_SENS))
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
            step = MOVE_SPEED * self.powerups.speed_mult * dt / n
            self.world.move(p, mx * step, my * step)
            self.walk_t += dt
        if pg.mouse.get_pressed()[0] or keys[pg.K_SPACE]:
            self.weapon.fire(self)

    def update(self, dt):
        self.weapon.update(dt)
        self.grapple.update(dt, self)
        self.player.hurt_flash = max(0.0, self.player.hurt_flash - dt)
        self.headshot_flash = max(0.0, self.headshot_flash - dt)
        self.throw_t = max(0.0, self.throw_t - dt)
        w = self.world
        self.powerups.update(dt, self)
        for obj in w.projectiles + w.effects + w.items:
            obj.update(dt, self)
        w.projectiles = [o for o in w.projectiles if not o.dead]
        w.effects = [o for o in w.effects if not o.dead]
        w.items = [o for o in w.items if not o.dead]
        self.world.update_flow(self.player)
        for e in self.world.enemies:
            e.update(dt, self)
        self.world.enemies = [e for e in self.world.enemies if e.alive or e.dead_time < 2.0]
        if not self.player.alive:
            return
        if self.countdown is None:
            if not any(e.alive for e in self.world.enemies):
                self.countdown = 5.0
                self.player.health = 100
                self.grenades = self.max_grenades
                for w in self.weapons:
                    w.refill()
        else:
            self.countdown -= dt
            if self.countdown <= 0:
                self.countdown = None
                self.wave += 1
                self.world.enemies.clear()
                self.world.spawn_wave(self.wave_size(), self.player)
                self.world.spawn_tree(self.player)

    def draw_hud(self):
        scr, p = self.screen, self.player
        cx, cy = W // 2, VIEW_H // 2
        pg.draw.line(scr, (0, 255, 0), (cx - 4, cy), (cx + 4, cy))
        pg.draw.line(scr, (0, 255, 0), (cx, cy - 4), (cx, cy + 4))
        if self.headshot_flash > 0:
            for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):  # hit marker
                pg.draw.line(scr, (255, 60, 60), (cx + 4 * sx, cy + 4 * sy), (cx + 8 * sx, cy + 8 * sy), 2)
            img = self.font.render("HEADSHOT", True, (255, 60, 60))
            scr.blit(img, img.get_rect(center=(cx, cy + 18)))
        if p.hurt_flash > 0:
            ov = pg.Surface((W, VIEW_H), pg.SRCALPHA)
            ov.fill((255, 0, 0, int(p.hurt_flash * 300)))
            scr.blit(ov, (0, 0))
        for i in range(self.grenades):
            scr.blit(self.grenade_icon, (W - 18 - i * 16, VIEW_H - 18))
        y = 3
        for name, t in self.powerups.timers.items():
            if t > 0:
                scr.blit(self.font.render(f"{name} {math.ceil(t)}", True, (255, 215, 0)), (3, y))
                y += 12
        if self.powerups.message_t > 0:
            img = self.big.render(self.powerups.message, True, (255, 215, 0))
            scr.blit(img, img.get_rect(center=(cx, cy + 34)))
        self.draw_minimap()
        self.draw_status_bar()
        msgs = []
        if not p.alive:
            msgs = [f"YOU DIED ON WAVE {self.wave}", "press R"]
        elif self.countdown is not None:
            msgs = [f"WAVE {self.wave} CLEARED", f"next wave in {math.ceil(self.countdown)}"]
        for i, msg in enumerate(msgs):
            img = self.big.render(msg, True, (255, 40, 40))
            scr.blit(img, img.get_rect(center=(cx, cy - 40 + i * 24)))

    def draw_status_bar(self):
        """Classic Doom layout: ammo | health | face | wave | enemies left."""
        scr, p = self.screen, self.player
        top = VIEW_H
        pg.draw.rect(scr, (70, 70, 70), (0, top, W, BAR_H))
        pg.draw.line(scr, (120, 120, 120), (0, top), (W, top))
        left = sum(e.alive for e in self.world.enemies)
        face_w = BAR_H - 4
        face_x = W // 2 - face_w // 2
        boxes = [  # (x, width, value, label)
            (2, 66, self.weapon.ammo, self.weapon.name),
            (70, 66, f"{p.health}%", "HEALTH"),
            (face_x + face_w + 4, 70, self.wave, "WAVE"),
            (face_x + face_w + 76, 70, left, "LEFT"),
        ]
        for x, w, value, label in boxes:
            pg.draw.rect(scr, (45, 45, 45), (x, top + 2, w, BAR_H - 4))
            pg.draw.rect(scr, (100, 100, 100), (x, top + 2, w, BAR_H - 4), 1)
            img = self.bar_font.render(str(value), True, (200, 30, 30))
            scr.blit(img, img.get_rect(center=(x + w // 2, top + 13)))
            img = self.label_font.render(label[:12], True, (200, 200, 200))
            scr.blit(img, img.get_rect(center=(x + w // 2, top + BAR_H - 7)))
        face = self.portrait.render(p.health, p.hurt_flash, not p.alive)
        pg.draw.rect(scr, (20, 20, 20), (face_x - 2, top + 1, face_w + 4, BAR_H - 2))
        scr.blit(face, (face_x, top + 2))

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000, 0.05)
            self.handle_input(dt)
            self.update(dt)
            self.renderer.render(self.screen, self.world, self.player)
            if self.player.alive:
                bob = (math.sin(self.walk_t * 8) * 4, abs(math.cos(self.walk_t * 8)) * 4)
                self.weapon.draw(self.screen, bob)
                self.grapple.draw(self.screen, bob)
                if self.throw_t > 0.2:  # grenade leaving the hand
                    k = (0.4 - self.throw_t) / 0.2
                    img = pg.transform.smoothscale(Grenade.frames()[0], (int(50 - 30 * k),) * 2)
                    self.screen.blit(img, (W // 2 + 40 - int(30 * k), VIEW_H - 40 - int(50 * k)))
            self.draw_hud()
            pg.transform.scale(self.screen, self.window.get_size(), self.window)
            pg.display.flip()


if __name__ == "__main__":
    Game().run()
