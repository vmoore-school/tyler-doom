import asyncio
import json
import math
import os
import sys
import pygame as pg

from engine import assets
from engine.settings import W, H, VIEW_H, BAR_H, SCALE, FOV, RESOLUTIONS, FPS, MOUSE_SENS, MOVE_SPEED, PITCH_SENS, MAX_PITCH, HEADSHOT_MULT
from engine.world import World, LEVEL, cast_ray
from engine.entities import Player, SPAWN_POOL
from engine.weapons import WEAPON_TYPES
from engine.render import Renderer
from engine.grapple import Grapple
from engine.webcam import WebcamPortrait
from engine.projectiles import Grenade, Rune
from engine.pickups import Powerups
from engine import boss
from engine.menus import Menus
from engine.leaderboard import Leaderboard, NAME_MAX, clean_name

WEB = sys.platform == "emscripten"  # running in the browser via pygbag
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
SETTINGS_KEY = "doomish-settings"  # browser localStorage key (the web build's files don't survive a reload)
DEFAULT_SETTINGS = {"fullscreen": False, "resolution": "retro", "name": ""}


class Game:
    def __init__(self):
        pg.mixer.pre_init(22050, -16, 1, 256)
        pg.init()
        pg.display.set_caption("TYLER DOOM")
        self.settings = self.load_settings()
        self.clock = pg.time.Clock()
        self.font = pg.font.Font(None, 18)
        self.big = pg.font.Font(None, 32)
        self.mid = pg.font.Font(None, 22)
        self.bar_font = pg.font.Font(None, 26)
        self.label_font = pg.font.Font(None, 12)
        self.portrait = WebcamPortrait(size=(BAR_H - 4, BAR_H - 4))
        self.wall_textures = {k: f() for k, f in assets.WALLS.items()}
        self.weapons = []
        self.menu = Menus(self)
        self.apply_display()  # the window has to exist before images can be loaded
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
        self.leaderboard = Leaderboard()
        self.reset()
        self.menu.open("main")

    # --- settings / display ---

    @staticmethod
    def load_settings():
        settings = dict(DEFAULT_SETTINGS)
        try:
            if WEB:
                import platform  # pygbag's bridge to the page's JavaScript
                saved = platform.window.localStorage.getItem(SETTINGS_KEY)
                saved = json.loads(saved) if saved else {}
            else:
                with open(SETTINGS_FILE) as f:
                    saved = json.load(f)
            settings.update({k: v for k, v in saved.items() if k in DEFAULT_SETTINGS})
        except Exception:  # missing / corrupt / storage blocked: use the defaults
            pass
        if settings["resolution"] not in RESOLUTIONS:
            settings["resolution"] = "retro"
        return settings

    def save_settings(self):
        try:
            if WEB:
                import platform
                platform.window.localStorage.setItem(SETTINGS_KEY, json.dumps(self.settings))
            else:
                with open(SETTINGS_FILE, "w") as f:
                    json.dump(self.settings, f, indent=2)
        except Exception as e:  # the setting still applies for this session
            print("couldn't save settings:", e)

    def change_setting(self, key, value):
        self.settings[key] = value
        self.save_settings()
        self.apply_display()

    def view_size(self, resolution):
        """Size of the game picture (3D view + status bar) for a resolution setting."""
        m = self.content_rect.width / W  # how much the 320x200 picture is scaled up on screen
        k = {"retro": 1, "medium": max(1.0, m / 2), "full": m}[resolution]
        return round(W * k), round(H * k)

    def apply_display(self):
        """(Re)create the window and the surfaces everything is drawn on."""
        if self.settings["fullscreen"] and not WEB:
            self.window = pg.display.set_mode((0, 0), pg.FULLSCREEN)
        else:
            self.window = pg.display.set_mode((W * SCALE, H * SCALE))
        ww, wh = self.window.get_size()
        m = min(ww / W, wh / H)  # keep the 16:10 picture, with black bars if the screen differs
        self.content_rect = pg.Rect(0, 0, round(W * m), round(H * m))
        self.content_rect.center = (ww // 2, wh // 2)
        vw, vh = self.view_size(self.settings["resolution"])
        self.k = vw / W
        self.view = pg.Surface((vw, vh))  # 3D world, weapons, grapple: drawn at the chosen resolution
        self.renderer = Renderer(self.wall_textures, vw, round(VIEW_H * self.k))
        # The HUD is pixel art laid out for 320x200: at higher resolutions it gets its own
        # transparent layer that's scaled up (sharply) over the view.
        self.screen = self.view if vw == W else pg.Surface((W, H), pg.SRCALPHA)
        self._hud_cache = {}  # blit_hud's scaled tiles
        for w in self.weapons:
            w.prepare(self.k)
        self.menu.resize(self.content_rect.size)

    @staticmethod
    def lock_mouse():
        pg.event.set_grab(True)
        pg.mouse.set_visible(False)
        if hasattr(pg.mouse, "set_relative_mode"):  # pygame-ce: real pointer lock in the browser
            pg.mouse.set_relative_mode(True)

    @staticmethod
    def unlock_mouse():
        if hasattr(pg.mouse, "set_relative_mode"):
            pg.mouse.set_relative_mode(False)
        pg.event.set_grab(False)
        pg.mouse.set_visible(True)

    def quit(self):
        self.portrait.stop()
        pg.quit()
        sys.exit()

    def pause(self):
        self.grapple.release()
        self.menu.open("pause")

    def reset(self):
        self.world = World(LEVEL)
        self.player = Player(*self.world.start)
        self.weapons = [w() for w in WEAPON_TYPES]
        for w in self.weapons:
            w.prepare(self.k)
        self.weapon = self.weapons[0]
        self.grapple = Grapple()
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
        self.beam_enabled = False      # the Tyler Death Beam is opt-in per round (press T)
        self.leaderboard_valid = True  # turned off by enabling the beam
        self.kills = 0
        self.name_entry = None   # text being typed on the death screen, or None
        self.score_handled = False  # name prompt shown (submitted or skipped) for this run
        self.submit_req = None   # leaderboard Request for this run's score
        self.notice, self.notice_t = None, 0.0
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

    def enable_beam(self):
        if self.beam_enabled:
            return
        self.beam_enabled, self.leaderboard_valid = True, False
        self.show_notice(("TYLER DEATH BEAM ENABLED", "Leaderboard entries for this round will not be valid",
                          "Press 3 to use it"), 4.0, warning=True)

    def select_weapon(self, i):
        w = self.weapons[i]
        if w.cheat and not self.beam_enabled:
            self.show_notice((f"{w.name} IS LOCKED", "Press T to enable it (disables the leaderboard)"), 2.0)
            return
        self.weapon = w

    def show_notice(self, lines, dur, warning=False):
        self.notice, self.notice_t, self.notice_warning = lines, dur, warning

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
            self.player.hurt(q["dmg"], q["verity"])
            self.play("hurt")
            right = q["answers"][q["correct"]]
            self.say(f"WRONG. It's {right}. I know everything.", 2.5)

    RADAR_R = 16

    def draw_radar(self):
        """Top-right compass: a blip on the ring for each enemy, in its direction relative
        to where you're facing (up = ahead). Closer enemies are bigger and brighter."""
        r, p, scr = self.RADAR_R, self.player, self.screen
        cx, cy = W - r - 4, r + 4
        bg = pg.Surface((r * 2 + 2, r * 2 + 2), pg.SRCALPHA)
        pg.draw.circle(bg, (0, 0, 0, 140), (r + 1, r + 1), r + 1)
        scr.blit(bg, (cx - r - 1, cy - r - 1))
        pg.draw.circle(scr, (90, 90, 90), (cx, cy), r, 1)
        half = FOV / 2  # view cone
        for a in (-half, half):
            pg.draw.line(scr, (60, 90, 60), (cx, cy), (cx + math.sin(a) * (r - 1), cy - math.cos(a) * (r - 1)))
        for e in self.world.enemies:
            if not e.alive:
                continue
            rel = math.atan2(e.y - p.y, e.x - p.x) - p.angle
            k = max(0.0, 1 - math.hypot(e.x - p.x, e.y - p.y) / 25)  # 1 = on top of you
            col = (255, 220, 0) if isinstance(e, boss.Verity) else (255, int(40 + 60 * (1 - k)), int(40 + 60 * (1 - k)))
            col = tuple(int(c * (0.45 + 0.55 * k)) for c in col)
            size = 4 if isinstance(e, boss.Verity) else 1 + round(2 * k)
            pg.draw.circle(scr, col, (cx + math.sin(rel) * (r - 2), cy - math.cos(rel) * (r - 2)), size)
        scr.fill((0, 255, 0), (cx - 1, cy - 1, 3, 3))

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
            z = 0.5 + p.z + p.pitch * along / self.renderer.base_proj
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
        up = p.pitch / self.renderer.base_proj  # look up to throw higher/further
        speed = 7.0
        self.world.projectiles.append(
            Grenade(p.x + c * 0.3, p.y + s * 0.3, 0.45, c * speed, s * speed, 2.5 + up * speed))

    # --- leaderboard: name prompt after a valid run ---

    def death_scene_done(self):
        return (self.death_t or 0.0) > (3.2 if self.killed_by_verity() else 1.5)

    def start_name_entry(self):
        self.score_handled = True
        self.name_entry = clean_name(self.settings.get("name", ""))
        pg.key.start_text_input()

    def handle_name_entry(self, ev):
        if ev.type == pg.TEXTINPUT:
            self.name_entry = (self.name_entry + ev.text.upper())[:NAME_MAX]
        elif ev.type == pg.KEYDOWN:
            if ev.key == pg.K_BACKSPACE:
                self.name_entry = self.name_entry[:-1]
            elif ev.key in (pg.K_RETURN, pg.K_KP_ENTER):
                name = clean_name(self.name_entry)
                if name:
                    self.settings["name"] = name
                    self.save_settings()
                    self.submit_req = self.leaderboard.submit(name, self.wave, self.kills)
                    self.end_name_entry()
            elif ev.key == pg.K_ESCAPE:
                self.end_name_entry()

    def end_name_entry(self):
        self.name_entry = None
        pg.key.stop_text_input()

    def handle_input(self, dt):
        for ev in pg.event.get():
            if ev.type == pg.QUIT:
                self.quit()
            if self.menu.active:
                self.menu.handle(ev)
                continue
            if WEB and ev.type == pg.MOUSEBUTTONDOWN:  # browsers only lock the mouse after a click (Esc unlocks)
                self.lock_mouse()
            if self.name_entry is not None:
                self.handle_name_entry(ev)
                continue
            if ev.type == pg.KEYDOWN:
                if ev.key in (pg.K_TAB, pg.K_ESCAPE):
                    self.pause()
                    return
                if ev.key == pg.K_r and not self.player.alive:
                    self.reset()
                elif ev.key == pg.K_t and self.player.alive:
                    self.enable_beam()
                elif self.quiz and ev.key in (pg.K_z, pg.K_x, pg.K_c):
                    self.answer_quiz((pg.K_z, pg.K_x, pg.K_c).index(ev.key))
                elif ev.key == pg.K_SPACE and self.player.alive and self.player.z == 0:
                    self.player.vz = 4.2  # jump
                elif pg.K_1 <= ev.key < pg.K_1 + len(self.weapons):
                    self.select_weapon(ev.key - pg.K_1)
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
        if not p.alive or self.menu.active:
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
        self.notice_t = max(0.0, self.notice_t - dt)
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
        for e in self.world.enemies:
            if not e.alive and not getattr(e, "counted", False):
                e.counted = True
                self.kills += 1
        self.world.enemies = [e for e in self.world.enemies if e.alive or e.dead_time < 2.0]
        if not self.player.alive:
            if self.death_t is None:
                self.death_t, self.dead_face = 0.0, self.portrait.snapshot()
                self.deaths += 1
                self.quiz = None
                self.invert_t = self.backrooms_t = 0.0
            self.death_t += dt
            if self.killed_by_verity() and 1.6 < self.death_t < 3.2 and self.death_t >= self.next_chomp:
                self.play("chomp")
                self.next_chomp = self.death_t + 0.22
            if (self.death_scene_done() and not self.score_handled and self.leaderboard.enabled
                    and self.leaderboard_valid):
                self.start_name_entry()
            return
        v = self.boss()
        if v and not v.alive:  # Verity's minions vanish with him
            for e in self.world.enemies:
                if isinstance(e, boss.VerityVariant) and e.alive:
                    e.state = "dead"
                    e.counted = True  # vanished, not killed
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
        self.draw_rune_warning()
        if p.hurt_flash > 0:
            ov = pg.Surface((W, VIEW_H), pg.SRCALPHA)
            ov.fill((255, 0, 0, int(p.hurt_flash * 300)))
            scr.blit(ov, (0, 0))
        for i in range(self.grenades):  # under the radar, out of the way of the held weapon
            scr.blit(self.grenade_icon, (W - 18 - i * 16, self.RADAR_R * 2 + 10))
        y = 3
        for name, t in self.powerups.timers.items():
            if t > 0:
                scr.blit(self.font.render(f"{name} {math.ceil(t)}", True, (255, 215, 0)), (3, y))
                y += 12
        if self.powerups.message_t > 0:
            img = self.big.render(self.powerups.message, True, (255, 215, 0))
            scr.blit(img, img.get_rect(center=(cx, cy + 34)))
        if p.alive:
            self.draw_radar()
        self.draw_status_bar()
        msgs = []
        if p.alive:
            self.draw_boss_ui()
        else:
            t = self.death_t or 0.0
            if self.killed_by_verity():
                boss.draw_brain_eating(scr, t, self.dead_face, self.big)
            else:
                self.draw_death(t)
            if self.death_scene_done():
                self.draw_score_status()
        if p.alive and self.countdown is not None:
            msgs = [f"WAVE {self.wave} CLEARED", f"next wave in {math.ceil(self.countdown)}"]
        for i, msg in enumerate(msgs):
            img = self.big.render(msg, True, (255, 40, 40))
            scr.blit(img, img.get_rect(center=(cx, cy - 40 + i * 24)))
        if self.notice_t > 0 and p.alive and not self.menu.active:
            self.draw_notice()

    def draw_score_status(self):
        """Death screen footer: name prompt / submission status, then the restart hint."""
        scr, cx = self.screen, W // 2
        if self.name_entry is not None:
            box = pg.Rect(0, 0, 170, 31)
            box.midbottom = (cx, VIEW_H - 2)
            bg = pg.Surface(box.size, pg.SRCALPHA)
            bg.fill((0, 0, 0, 200))
            scr.blit(bg, box)
            pg.draw.rect(scr, (255, 215, 0), box, 1)
            lines = [(self.label_font, "NAME FOR THE LEADERBOARD", (255, 215, 0)),
                     (self.font, self.name_entry + ("_" if pg.time.get_ticks() // 400 % 2 else " "), (255, 255, 255)),
                     (self.label_font, "Enter: submit    Esc: skip", (200, 200, 200))]
            y = box.y + 2
            for font, text, color in lines:
                img = font.render(text, True, color)
                scr.blit(img, img.get_rect(midtop=(cx, y)))
                y += img.get_height()
            return
        status = None
        if not self.leaderboard_valid and self.leaderboard.enabled:
            status = ("Tyler Death Beam used - score not submitted", (255, 120, 120))
        elif self.submit_req:
            status = {"pending": ("Submitting score...", (255, 215, 0)),
                      "ok": ("Score submitted to the leaderboard!", (120, 255, 120)),
                      "error": (f"Couldn't submit: {self.submit_req.error}", (255, 120, 120))}[self.submit_req.status]
        if status:
            img = self.font.render(*status[:1], True, status[1])
            scr.blit(img, img.get_rect(center=(cx, VIEW_H - 24)))
        img = self.font.render(f"DIED ON WAVE {self.wave}  -  {self.kills} KILLS  -  press R", True, (255, 60, 60))
        scr.blit(img, img.get_rect(center=(cx, VIEW_H - 10)))

    def draw_notice(self):
        """Boxed message in the lower middle of the view (beam warning, locked weapon)."""
        title, *rest = self.notice
        imgs = [self.mid.render(title, True, (255, 60, 60) if self.notice_warning else (255, 215, 0))]
        imgs += [self.font.render(line, True, (255, 255, 255)) for line in rest]
        box = pg.Rect(0, 0, max(i.get_width() for i in imgs) + 16, sum(i.get_height() + 2 for i in imgs) + 10)
        box.center = (W // 2, VIEW_H - 50)
        bg = pg.Surface(box.size, pg.SRCALPHA)
        bg.fill((0, 0, 0, 190))
        self.screen.blit(bg, box)
        if self.notice_warning:
            pg.draw.rect(self.screen, (255, 60, 60), box, 1)
        y = box.y + 6
        for img in imgs:
            self.screen.blit(img, img.get_rect(midtop=(W // 2, y)))
            y += img.get_height() + 2

    def draw_rune_warning(self):
        """Runes land under your feet, out of view: glow purple from the bottom of the screen
        (faster as it's about to erupt) while you're standing in one."""
        p = self.player
        runes = [r for r in self.world.projectiles if isinstance(r, Rune)
                 and math.hypot(r.x - p.x, r.y - p.y) < r.radius + p.radius]
        if not runes or not p.alive:
            return
        k = max(r.t / r.delay for r in runes)
        pulse = 0.6 + 0.4 * math.sin(k * k * 40)
        ov = pg.Surface((W, 50), pg.SRCALPHA)
        for y in range(50):
            ov.fill((170, 60, 255, int(pulse * 150 * y / 50)), (0, y, W, 1))
        self.screen.blit(ov, (0, VIEW_H - 50))
        img = self.font.render("RUNE! MOVE!", True, (235, 200, 255))
        self.screen.blit(img, img.get_rect(center=(W // 2, VIEW_H - 30)))

    def killed_by_verity(self):
        return isinstance(self.player.killer, boss.Verity)

    def draw_death(self, t):
        """Generic death screen: fade to red, your greyed-out face next to whoever got you."""
        scr, cx, cy = self.screen, W // 2, VIEW_H // 2
        shade = pg.Surface((W, VIEW_H), pg.SRCALPHA)
        shade.fill((60, 0, 0, min(210, int(t * 260))))
        scr.blit(shade, (0, 0))
        if t < 0.5:
            return
        a = min(255, int((t - 0.5) * 400))  # everything below fades in
        img = self.big.render("YOU DIED", True, (220, 30, 30))
        img.set_alpha(a)
        scr.blit(img, img.get_rect(center=(cx, 22)))
        if self.dead_face:
            face = pg.transform.grayscale(pg.transform.smoothscale(self.dead_face, (72, 72)))
            face.fill((255, 150, 150), special_flags=pg.BLEND_RGB_MULT)
            face.set_alpha(a)
            scr.blit(face, (cx - 92, cy - 40))
        k = self.player.killer
        if k == "grenade":
            name, sprite = "YOUR OWN GRENADE", Grenade.frames()[0]
        elif k is not None and hasattr(k, "get_frames"):
            name, sprite = (k.title or type(k).__name__).upper(), k.get_frames()["attack"]
        else:
            name, sprite = "SOMETHING", None
        if sprite:
            sprite = pg.transform.smoothscale(sprite, (72, 72))
            sprite.set_alpha(a)
            scr.blit(sprite, (cx + 20, cy - 40))
        img = self.font.render(f"KILLED BY {name}", True, (255, 200, 200))
        img.set_alpha(a)
        scr.blit(img, img.get_rect(center=(cx, cy + 42)))

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

    HUD_TILE = 40

    def blit_hud(self, view):
        """Scale the 320x200 HUD layer up over the view. Scaling and alpha-blending the whole
        layer every frame is slow (very slow in the browser), and most of it is transparent and
        unchanged frame to frame. So it's done in tiles: each tile is rescaled only when its pixels
        change and skipped when empty, and the solid status bar is kept as a fast opaque surface."""
        hud, cache = self.screen, self._hud_cache
        vw, vh = view.get_size()
        if cache.get("size") != (vw, vh):
            cache.clear()
            cache["size"] = (vw, vh)
        sx, sy = vw / W, vh / H
        bar = hud.subsurface((0, VIEW_H, W, BAR_H))
        data = pg.image.tobytes(bar, "RGB")
        c = cache.get("bar")
        if c is None or c[0] != data:
            bar_y = round(VIEW_H * sy)
            c = cache["bar"] = (data, pg.transform.scale(bar, (vw, vh - bar_y)).convert(), (0, bar_y))
        view.blit(c[1], c[2])
        t = self.HUD_TILE
        for ty in range(0, VIEW_H, t):
            for tx in range(0, W, t):
                r = pg.Rect(tx, ty, min(t, W - tx), min(t, VIEW_H - ty))
                tile = hud.subsurface(r)
                data = pg.image.tobytes(tile, "RGBA")
                c = cache.get((tx, ty))
                if c is None or c[0] != data:
                    img = pos = None
                    if tile.get_bounding_rect().w:  # anything drawn here?
                        pos = (round(r.x * sx), round(r.y * sy))
                        size = (round(r.right * sx) - pos[0], round(r.bottom * sy) - pos[1])
                        img = pg.transform.scale(tile, size).convert_alpha()
                    c = cache[(tx, ty)] = (data, img, pos)
                if c[1] is not None:
                    view.blit(c[1], c[2])

    def draw_frame(self):
        view, s = self.view, self.k
        self.renderer.render(view, self.world, self.player)
        if self.player.alive and not self.menu.title_screen:
            bob = (math.sin(self.walk_t * 8) * 4, abs(math.cos(self.walk_t * 8)) * 4)
            self.weapon.draw(view, bob)
            self.grapple.draw(view, self, bob)
            if self.throw_t > 0.2:  # grenade leaving the hand
                t = (0.4 - self.throw_t) / 0.2
                img = pg.transform.smoothscale(Grenade.frames()[0], (int((50 - 30 * t) * s),) * 2)
                view.blit(img, (int((W // 2 + 40 - 30 * t) * s), int((VIEW_H - 40 - 50 * t) * s)))
        if not self.menu.title_screen:
            if self.screen is not view:
                self.screen.fill((0, 0, 0, 0))
            self.draw_hud()
            if self.screen is not view:
                self.blit_hud(view)
        win, rect = self.window, self.content_rect
        if rect.size != win.get_size():
            win.fill((0, 0, 0))  # letterbox bars
        if view.get_size() == rect.size:
            win.blit(view, rect)
        else:
            pg.transform.scale(view, rect.size, win.subsurface(rect))
        if self.menu.active:
            self.menu.draw(win.subsurface(rect))

    async def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000, 0.05)
            self.handle_input(dt)
            self.leaderboard.poll()
            if self.menu.title_screen:  # slowly look around the level behind the title
                self.player.angle += 0.15 * dt
            elif not self.menu.active:
                self.update(dt)
            self.draw_frame()
            pg.display.flip()
            await asyncio.sleep(0)  # hand control back to the browser each frame


if __name__ == "__main__":
    asyncio.run(Game().run())
