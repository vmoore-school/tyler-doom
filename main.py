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
from engine import boss


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
            "chomp": assets.noise_sound(0.12, 0.6, 4, 7),
        }
        Grenade.frames()
        self.grenade_icon = pg.transform.smoothscale(Grenade.frames()[0], (14, 14))
        for cls in SPAWN_POOL + [boss.Verity] + boss.VARIANTS:  # build sprites up front to avoid mid-game hitches
            cls.get_frames()
        self.deaths = 0
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
        self.speech, self.speech_t = "", 0.0
        self.quiz = None
        self.backrooms_t = self.invert_t = 0.0
        self.death_t, self.dead_face, self.next_chomp = None, None, 0.0
        self.start_wave()

    BOSS_EVERY = 7

    def start_wave(self):
        """Normal waves grow by one enemy each time; every BOSS_EVERY waves, Verity shows up."""
        if self.wave % self.BOSS_EVERY == 0:
            level = self.wave // self.BOSS_EVERY  # stronger every encounter
            x, y = max(self.world.free_tiles(self.player, 8.0),
                       key=lambda t: math.hypot(t[0] - self.player.x, t[1] - self.player.y))
            self.world.enemies.append(boss.Verity(x, y, level))
            self.say(f"IT'S ME. IT'S VERITY. (Level {level})", 3.0)
        else:
            self.world.spawn_wave(self.wave_size(), self.player)
        self.world.spawn_tree(self.player)

    def skip_to_boss(self):
        """Debug/cheat: jump straight to the next Verity wave."""
        v = self.boss()
        if v and v.alive:
            return
        self.wave = (self.wave // self.BOSS_EVERY + 1) * self.BOSS_EVERY
        self.countdown, self.quiz = None, None
        self.world.enemies.clear()
        self.world.projectiles.clear()
        self.start_wave()

    def boss(self):
        return next((e for e in self.world.enemies if isinstance(e, boss.Verity)), None)

    def say(self, text, dur=2.5):
        self.speech, self.speech_t = text, dur

    def start_quiz(self, verity):
        q, answers, correct = boss.make_question(self)
        self.quiz = {"q": q, "answers": answers, "correct": correct, "t": 6.0,
                     "dmg": int(25 * verity.power), "verity": verity}

    def answer_quiz(self, i):
        q, self.quiz = self.quiz, None
        if i == q["correct"]:
            q["verity"].stun = 3.0
            self.say("Correct?! Impossible... (Verity is stunned: double damage!)", 2.5)
        else:
            self.player.hurt(q["dmg"])
            self.play("hurt")
            right = q["answers"][q["correct"]]
            self.say(f"WRONG. It's {right}. I know everything.", 2.5)

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
            z = 0.5 + p.z + p.pitch * along / self.renderer.proj
            z0 = getattr(e, "z", 0.0)  # floating enemies
            if z0 <= z <= z0 + e.scale:
                hits.append((along, e, z >= z0 + e.scale * (1 - e.head_frac)))
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
                elif ev.key == pg.K_p and self.player.alive:
                    self.skip_to_boss()
                elif self.quiz and ev.key in (pg.K_z, pg.K_x, pg.K_c):
                    self.answer_quiz((pg.K_z, pg.K_x, pg.K_c).index(ev.key))
                elif ev.key == pg.K_SPACE and self.player.alive and self.player.z == 0:
                    self.player.vz = 4.2  # jump
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
                inv = -1 if self.invert_t > 0 else 1  # Falsity lies to your mouse
                self.player.angle += ev.rel[0] * MOUSE_SENS * inv
                self.player.pitch = max(-MAX_PITCH, min(MAX_PITCH, self.player.pitch - ev.rel[1] * PITCH_SENS * inv))
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
        if pg.mouse.get_pressed()[0]:
            self.weapon.fire(self)

    def update(self, dt):
        self.weapon.update(dt)
        self.grapple.update(dt, self)
        self.player.hurt_flash = max(0.0, self.player.hurt_flash - dt)
        self.headshot_flash = max(0.0, self.headshot_flash - dt)
        self.throw_t = max(0.0, self.throw_t - dt)
        self.speech_t = max(0.0, self.speech_t - dt)
        self.backrooms_t = max(0.0, self.backrooms_t - dt)
        self.invert_t = max(0.0, self.invert_t - dt)
        p = self.player
        p.vz -= 12.0 * dt  # jump physics
        p.z = max(0.0, p.z + p.vz * dt)
        if p.z == 0:
            p.vz = 0.0
        if self.quiz:
            self.quiz["t"] -= dt
            if self.quiz["t"] <= 0 or not self.quiz["verity"].alive:
                if self.quiz["verity"].alive:
                    self.answer_quiz(-1)
                else:
                    self.quiz = None
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
            if self.death_t is None:
                self.death_t, self.dead_face = 0.0, self.portrait.snapshot()
                self.deaths += 1
                self.quiz = None
                self.invert_t = self.backrooms_t = 0.0
            self.death_t += dt
            if 1.6 < self.death_t < 3.2 and self.death_t >= self.next_chomp:
                self.play("chomp")
                self.next_chomp = self.death_t + 0.22
            return
        v = self.boss()
        if v and not v.alive:  # Verity's minions vanish with him
            for e in self.world.enemies:
                if isinstance(e, boss.VerityVariant) and e.alive:
                    e.state = "dead"
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
                self.world.projectiles.clear()
                self.start_wave()

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
        if p.alive:
            self.draw_boss_ui()
        else:
            boss.draw_brain_eating(scr, self.death_t or 0.0, self.dead_face, self.big)
            if (self.death_t or 0) > 3.2:
                img = self.font.render(f"DIED ON WAVE {self.wave}  -  press R", True, (255, 60, 60))
                scr.blit(img, img.get_rect(center=(cx, VIEW_H - 10)))
        if p.alive and self.countdown is not None:
            msgs = [f"WAVE {self.wave} CLEARED", f"next wave in {math.ceil(self.countdown)}"]
        for i, msg in enumerate(msgs):
            img = self.big.render(msg, True, (255, 40, 40))
            scr.blit(img, img.get_rect(center=(cx, cy - 40 + i * 24)))

    def draw_boss_ui(self):
        scr = self.screen
        if self.backrooms_t > 0:  # the Backrooms: buzzing yellow haze
            ov = pg.Surface((W, VIEW_H), pg.SRCALPHA)
            ov.fill((210, 190, 70, 70 + int(30 * math.sin(self.backrooms_t * 40))))
            scr.blit(ov, (0, 0))
        if self.invert_t > 0:
            img = self.font.render("CONTROLS INVERTED", True, (90, 140, 255))
            scr.blit(img, img.get_rect(center=(W // 2, VIEW_H - 30)))
        v = self.boss()
        if v and v.alive:
            bw = 160
            x = W // 2 - bw // 2
            pg.draw.rect(scr, (40, 0, 0), (x, 4, bw, 7))
            pg.draw.rect(scr, (255, 210, 0), (x, 4, int(bw * max(0, v.hp) / v.max_hp), 7))
            pg.draw.rect(scr, (0, 0, 0), (x, 4, bw, 7), 1)
            img = self.font.render(f"VERITY  Lv {v.level}" + ("  STUNNED" if v.stun > 0 else ""), True, (255, 220, 0))
            scr.blit(img, img.get_rect(center=(W // 2, 18)))
        if self.speech_t > 0 and self.speech:
            img = self.font.render(self.speech, True, (255, 240, 120))
            box = img.get_rect(center=(W // 2, 32)).inflate(8, 4)
            bg = pg.Surface(box.size, pg.SRCALPHA)
            bg.fill((0, 0, 0, 170))
            scr.blit(bg, box)
            scr.blit(img, img.get_rect(center=box.center))
        if self.quiz:
            q = self.quiz
            box = pg.Rect(30, 44, W - 60, 62)
            bg = pg.Surface(box.size, pg.SRCALPHA)
            bg.fill((20, 20, 60, 220))
            scr.blit(bg, box)
            pg.draw.rect(scr, (255, 210, 0), box, 1)
            scr.blit(self.font.render(f"{q['q']}  ({math.ceil(q['t'])})", True, (255, 255, 255)), (box.x + 6, box.y + 5))
            for i, a in enumerate(q["answers"]):
                scr.blit(self.font.render(f"[{'ZXC'[i]}] {a}", True, (255, 220, 0)), (box.x + 10, box.y + 20 + i * 13))

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
