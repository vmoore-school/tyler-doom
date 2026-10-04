"""VERITY - the omniscient smiley-face AI boss (from the ThatMob Minecraft ARG).
Appears every few waves and gets stronger each encounter."""
import datetime
import getpass
import math
import os
import random
import pygame as pg
from .assets import PHOTO_DIR
from .entities import Enemy
from .settings import W, VIEW_H

_cache = {}


def _img(name, size):
    key = (name, size)
    if key not in _cache:
        _cache[key] = pg.transform.smoothscale(pg.image.load(os.path.join(PHOTO_DIR, name)).convert_alpha(), (size, size))
    return _cache[key]


def _tint(img, add=(0, 0, 0), mult=(255, 255, 255)):
    out = img.copy()
    out.fill(add, special_flags=pg.BLEND_RGB_ADD)
    out.fill(mult, special_flags=pg.BLEND_RGB_MULT)
    return out


def taylor_swift_age(today=None):
    today = today or datetime.date.today()
    born = datetime.date(1989, 12, 13)
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


# --- projectile art ----------------------------------------------------------

def _surface():
    return pg.Surface((48, 48), pg.SRCALPHA)


def eiffel_tower():
    s = _surface()
    iron = (110, 80, 50)
    pg.draw.polygon(s, iron, [(24, 2), (27, 20), (34, 38), (40, 47), (32, 47), (24, 38), (16, 47), (8, 47), (14, 38), (21, 20)], 0)
    pg.draw.polygon(s, (0, 0, 0, 0), [(24, 40), (30, 47), (18, 47)])
    for y in (20, 30, 38):
        pg.draw.line(s, (160, 120, 70), (24 - y // 3, y), (24 + y // 3, y), 2)
    pg.draw.line(s, (60, 40, 25), (24, 0), (24, 6), 2)
    return s


def baguette():
    s = _surface()
    pts = [(6, 40), (40, 6), (44, 10), (10, 44)]
    pg.draw.polygon(s, (215, 160, 80), pts)
    pg.draw.circle(s, (215, 160, 80), (8, 42), 3)
    pg.draw.circle(s, (215, 160, 80), (42, 8), 3)
    for i in range(4):
        c = 14 + i * 7
        pg.draw.line(s, (250, 220, 160), (c - 2, 48 - c - 2), (c + 3, 48 - c + 3), 2)
    return s


def music_note():
    s = _surface()
    col = (230, 120, 220)
    pg.draw.ellipse(s, col, (10, 32, 14, 10))
    pg.draw.ellipse(s, col, (28, 28, 14, 10))
    pg.draw.line(s, col, (23, 36), (23, 10), 3)
    pg.draw.line(s, col, (41, 32), (41, 6), 3)
    pg.draw.line(s, col, (23, 10), (41, 6), 5)
    pg.draw.circle(s, (255, 255, 255), (8, 8), 2)  # sparkle
    return s


def encyclopedia():
    s = _surface()
    pg.draw.rect(s, (40, 60, 140), (8, 10, 32, 28), border_radius=2)
    pg.draw.rect(s, (240, 235, 210), (10, 34, 28, 4))
    pg.draw.rect(s, (220, 190, 60), (8, 10, 32, 28), 2, border_radius=2)
    f = pg.font.Font(None, 28)
    s.blit(f.render("?", True, (255, 215, 0)), (19, 14))
    return s


def brain(size=40):
    s = pg.Surface((size, size), pg.SRCALPHA)
    pg.draw.ellipse(s, (240, 150, 170), (0, size // 6, size, size * 2 // 3))
    for i in range(5):
        x = size * (i + 1) // 6
        pg.draw.arc(s, (190, 90, 120), (x - size // 8, size // 4, size // 4, size // 3), 0, math.pi, 2)
        pg.draw.arc(s, (190, 90, 120), (x - size // 8, size // 2, size // 4, size // 4), math.pi, 2 * math.pi, 2)
    pg.draw.line(s, (170, 70, 100), (size // 2, size // 6), (size // 2, size * 5 // 6), 2)
    return s


ART = {}


def art(name):
    if name not in ART:
        base = {"eiffel": eiffel_tower, "baguette": baguette, "note": music_note, "book": encyclopedia}[name]()
        ART[name] = [base] + [pg.transform.rotate(base, a) for a in range(45, 360, 45)]
    return ART[name]


class Missile:
    """Boss projectile. Hits the player in flight, or splashes on landing if `splash` > 0."""

    def __init__(self, x, y, z, vx, vy, vz, kind, damage, scale=0.5, gravity=0.0, homing=0.0,
                 life=6.0, splash=0.0, spin=True, source=None):
        self.x, self.y, self.z, self.vx, self.vy, self.vz = x, y, z, vx, vy, vz
        self.kind, self.damage, self.scale = kind, damage, scale
        self.gravity, self.homing, self.life, self.splash, self.spin = gravity, homing, life, splash, spin
        self.source = source  # who threw it, for the death screen
        self.t = 0.0
        self.dead = False

    @property
    def image(self):
        f = art(self.kind)
        return f[int(self.t * 12) % len(f)] if self.spin else f[0]

    def update(self, dt, game):
        self.t += dt
        if self.t > self.life:
            self.dead = True
            return
        p = game.player
        if self.homing:
            dx, dy = p.x - self.x, p.y - self.y
            d = math.hypot(dx, dy) or 1e-6
            speed = math.hypot(self.vx, self.vy)
            k = min(1.0, self.homing * dt)
            self.vx += (dx / d * speed - self.vx) * k
            self.vy += (dy / d * speed - self.vy) * k
        self.vz -= self.gravity * dt
        nx, ny, nz = self.x + self.vx * dt, self.y + self.vy * dt, self.z + self.vz * dt
        if game.world.tile(int(nx), int(ny)):
            self.dead = True
            return
        self.x, self.y, self.z = nx, ny, nz
        d = math.hypot(p.x - self.x, p.y - self.y)
        if self.z <= 0:
            self.dead = True
            if self.splash and d < self.splash and p.z < 0.3:  # jump to dodge!
                p.hurt(self.damage, self.source)
                game.play("hurt")
            return
        if p.alive and d < 0.45 and p.z - 0.1 < self.z < p.z + 1.0:
            p.hurt(self.damage, self.source)
            game.play("hurt")
            self.dead = True


# --- Verity variants (minions) ----------------------------------------------

class VerityVariant(Enemy):
    scale, radius, health, speed = 0.8, 0.35, 80, 2.2
    head_frac = 0.6
    add, mult = (0, 0, 0), (255, 255, 255)
    title = "Variant"

    @classmethod
    def make_frames(cls):
        base = _tint(_img("boss/verity.png", 64), cls.add, cls.mult)
        att = _tint(_img("boss/verity_attack.webp", 64), cls.add, cls.mult)
        dead = pg.Surface((64, 64), pg.SRCALPHA)
        dead.blit(pg.transform.smoothscale(_tint(base, mult=(90, 90, 90)), (64, 20)), (0, 44))
        return {"walk": [base], "attack": att, "pain": _tint(base, add=(120, 120, 120)), "dead": dead}

    @property
    def z(self):
        return 0.25 + 0.1 * math.sin(self.anim * 3) if self.alive else 0.0


class Falsity(VerityVariant):
    """Blue. Lies to your mouse: inverts your aim."""
    add, mult, title = (0, 0, 200), (80, 110, 255), "Falsity"
    attack_range = 8.0

    def perform_attack(self, game, sees, dist):
        if sees:
            game.invert_t = 3.0
            game.say("Falsity: everything you know is a lie.", 2.0)


class Cruelty(VerityVariant):
    """Red. Fast and violent."""
    add, mult, title = (0, 0, 0), (255, 50, 40), "Cruelty"
    speed, damage, attack_range, attack_cooldown = 3.4, 18, 1.6, 0.9


class Lovity(VerityVariant):
    """Pink. Heals Verity."""
    add, mult, title = (0, 0, 180), (255, 130, 230), "Lovity"
    attack_range, attack_cooldown = 30.0, 3.0

    def perform_attack(self, game, sees, dist):
        for e in game.world.enemies:
            if isinstance(e, Verity) and e.alive:
                e.hp = min(e.max_hp, e.hp + 40 * e.level)
                game.say("Lovity: <3 <3 <3 (Verity healed)", 1.5)


VARIANTS = [Falsity, Cruelty, Lovity]


# --- the boss ------------------------------------------------------------------

class Verity(Enemy):
    scale, radius = 1.45, 0.6  # with his float, stays under WALL_H
    head_frac = 0.5
    base_health = 1200
    attack_names = ["eiffel", "baguettes", "eras", "encyclopedia", "quiz", "variants", "backrooms"]

    def __init__(self, x, y, level=1):
        super().__init__(x, y)
        self.level = level
        self.max_hp = self.hp = self.base_health * (1 + 0.75 * (level - 1))
        self.power = 1 + 0.35 * (level - 1)          # damage / projectile scaling
        self.attack_cooldown = 2.6 / (1 + 0.2 * (level - 1))
        self.speed = 1.4 + 0.15 * level
        self.state = "chase"
        self.cooldown = 2.0
        self.flash = self.stun = self.attack_anim = self.unseen = 0.0
        self.last_attack = None

    @classmethod
    def make_frames(cls):
        base = _img("boss/verity.png", 96)
        att = _img("boss/verity_attack.webp", 96)
        dead = pg.Surface((96, 96), pg.SRCALPHA)
        dead.blit(pg.transform.smoothscale(_tint(att, mult=(120, 60, 60)), (96, 30)), (0, 66))
        return {"walk": [base], "attack": att, "pain": _tint(base, add=(120, 120, 120)),
                "stun": _tint(base, mult=(150, 150, 255)), "dead": dead}

    @property
    def z(self):
        return 0.25 + 0.1 * math.sin(self.anim * 2) if self.alive else 0.0

    @property
    def image(self):
        f = self.frames
        if not self.alive:
            return f["dead"]
        if self.flash > 0:
            return f["pain"]
        if self.stun > 0:
            return f["stun"]
        if self.attack_anim > 0 or self.hp < self.max_hp / 3:
            return f["attack"]
        return f["walk"][0]

    def hurt(self, dmg):
        if not self.alive:
            return
        self.hp -= dmg * (2 if self.stun > 0 else 1)
        self.flash = 0.08
        if self.hp <= 0:
            self.state = "dead"

    def update(self, dt, game):
        if not self.alive:
            self.dead_time += dt
            return
        self.anim += dt
        self.flash = max(0.0, self.flash - dt)
        self.stun = max(0.0, self.stun - dt)
        self.attack_anim = max(0.0, self.attack_anim - dt)
        p = game.player
        dx, dy = p.x - self.x, p.y - self.y
        dist = math.hypot(dx, dy) or 1e-6
        sees = game.world.line_of_sight(self.x, self.y, p.x, p.y)
        self.unseen = 0.0 if sees else self.unseen + dt
        if self.stun > 0:
            return
        # Hover at a comfortable lecturing distance.
        step = self.speed * dt
        if not sees or dist > 7:
            if not sees:
                nxt = game.world.next_step(self.x, self.y)
                if nxt:
                    dx, dy = nxt[0] - self.x, nxt[1] - self.y
                    dist = math.hypot(dx, dy) or 1e-6
            game.world.move(self, dx / dist * step, dy / dist * step)
        elif dist < 4:
            game.world.move(self, -dx / dist * step, -dy / dist * step)
        enraged = self.hp < self.max_hp / 2
        self.cooldown -= dt * (1.5 if enraged else 1.0)
        if not p.alive:
            return
        if self.unseen > 5:
            self.unseen = 0
            self.attack("backrooms", game)
        elif self.cooldown <= 0 and sees:
            choices = [a for a in self.attack_names if a != self.last_attack]
            if any(isinstance(e, VerityVariant) and e.alive for e in game.world.enemies):
                choices.remove("variants") if "variants" in choices else None
            self.attack(random.choice(choices), game)
            self.cooldown = self.attack_cooldown

    def attack(self, name, game):
        self.last_attack = name
        self.attack_anim = 0.7
        getattr(self, "attack_" + name)(game)

    def _aim(self, game):
        p = game.player
        return math.atan2(p.y - self.y, p.x - self.x), math.hypot(p.x - self.x, p.y - self.y)

    def attack_eiffel(self, game):
        """France: lobs spinning Eiffel Towers at you."""
        game.say(random.choice(["Bonjour! Have you seen Paris?", "330 metres of French iron, just for you.",
                                "Ooh la la. Catch!"]))
        ang, dist = self._aim(game)
        n = 2 + self.level
        g, speed, z0 = 6.0, 6.0, 1.2
        for i in range(n):
            a = ang + (i - (n - 1) / 2) * 0.12
            t = max(0.3, dist / speed)
            game.world.projectiles.append(Missile(
                self.x, self.y, z0, math.cos(a) * speed, math.sin(a) * speed, (0.5 * g * t * t - z0) / t,
                "eiffel", int(18 * self.power), scale=0.9, gravity=g, splash=1.0, source=self))

    def attack_baguettes(self, game):
        """France: baguettes rain from the sky around you. Jump or run!"""
        game.say("Une baguette pour vous! Et pour vous! ET POUR VOUS!")
        p = game.player
        for _ in range(5 + 2 * self.level):
            x, y = p.x + random.uniform(-2.5, 2.5), p.y + random.uniform(-2.5, 2.5)
            if not game.world.tile(int(x), int(y)):
                game.world.projectiles.append(Missile(
                    x, y, random.uniform(1.6, 1.9), 0, 0, 0, "baguette", int(14 * self.power),
                    scale=0.6, gravity=4.0, splash=0.8, source=self))  # drop from just under the wall tops

    def attack_eras(self, game):
        """Taylor Swift's age: a ring of exactly that many music notes."""
        age = taylor_swift_age()
        game.say(f"Taylor Swift is {age} years old. I know. Here are {age} notes.")
        for i in range(age):
            a = i / age * 2 * math.pi + self.anim
            game.world.projectiles.append(Missile(
                self.x, self.y, 0.5, math.cos(a) * 3.5, math.sin(a) * 3.5, 0, "note",
                int(6 * self.power), scale=0.35, spin=False, life=8, source=self))

    def attack_encyclopedia(self, game):
        """Knowledge: homing encyclopedias, while reciting things he shouldn't know."""
        game.say(random.choice(self.creepy_facts(game)))
        ang, _ = self._aim(game)
        for i in range(1 + self.level):
            a = ang + random.uniform(-1.2, 1.2)
            game.world.projectiles.append(Missile(
                self.x, self.y, 0.8, math.cos(a) * 3.2, math.sin(a) * 3.2, 0, "book",
                int(12 * self.power), scale=0.45, homing=1.8, life=7, spin=False, source=self))

    def attack_quiz(self, game):
        """Knowledge: pop quiz. Right answer stuns him, wrong answer hurts."""
        game.say("POP QUIZ! I know everything. Do you?")
        game.start_quiz(self)

    def attack_variants(self, game):
        """Summons Falsity, Cruelty and Lovity."""
        game.say("Meet my friends. Falsity. Cruelty. Lovity.")
        for i in range(1 + self.level // 2 + 1):
            cls = VARIANTS[i % 3] if i < 3 else random.choice(VARIANTS)
            a = random.uniform(0, 2 * math.pi)
            x, y = self.x + math.cos(a), self.y + math.sin(a)
            if game.world.tile(int(x), int(y)):
                x, y = self.x, self.y
            v = cls(x, y)
            v.state = "chase"
            game.world.enemies.append(v)

    def attack_backrooms(self, game):
        """'Verity's from Minecraft, he belongs to the Backrooms.' Teleports next to you."""
        game.say("Verity's from Minecraft... he belongs to the Backrooms.", 3.0)
        game.backrooms_t = 3.0
        p = game.player
        spots = [(x, y) for (x, y) in game.world.free_tiles(p, 2.5) if math.hypot(x - p.x, y - p.y) < 4.5]
        if spots:
            self.x, self.y = random.choice(spots)

    def creepy_facts(self, game):
        now = datetime.datetime.now()
        try:
            user = getpass.getuser()
        except Exception:
            user = "friend"
        return [
            f"Hello, {user}. I am your personal helper friend.",
            f"It is {now:%H:%M}. Shouldn't you be doing your homework?",
            f"You have {game.player.health} health. I counted.",
            f"You have died {game.deaths} times. I remember every one.",
            f"Today is {now:%A}. I know everything.",
            "I've read every book ever written. Have some.",
        ]


QUIZ = [
    lambda g: ("How old is Taylor Swift?", taylor_swift_age(), [taylor_swift_age() + d for d in (-3, 2, 5)]),
    lambda g: ("What is the capital of France?", "Paris", ["Lyon", "Minecraft", "The Backrooms"]),
    lambda g: ("How tall is the Eiffel Tower?", "330 m", ["33 m", "3 km", "64 blocks"]),
    lambda g: ("What wave is it?", g.wave, [g.wave - 1, g.wave + 1, g.wave * 2]),
    lambda g: ("What year is Taylor Swift's album '1989' from?", 2014, [1989, 2006, 2019]),
    lambda g: ("What are Verity's variants called?", "Falsity, Cruelty, Lovity",
               ["Honesty, Kindness, Hate", "Steve, Alex, Herobrine", "Clark, Pirate, Skunk"]),
]


def make_question(game):
    q, right, wrong = random.choice(QUIZ)(game)
    answers = [right] + random.sample(wrong, 2)
    random.shuffle(answers)
    return q, [str(a) for a in answers], answers.index(right)


# --- death cutscene: Verity eats your brain out of your webcam face ------------

def draw_brain_eating(screen, t, face, big_font):
    cx, cy = W // 2, VIEW_H // 2
    shade = pg.Surface((W, VIEW_H), pg.SRCALPHA)
    shade.fill((20, 0, 0, min(230, int(t * 300))))
    screen.blit(shade, (0, 0))
    hs = 80
    hx, hy = cx - 85, cy - 25
    head = pg.transform.smoothscale(face, (hs, hs))
    bites = min(7, int(max(0.0, t - 1.6) / 0.22))
    for i in range(bites):  # bite marks out of the top of your head
        bx = hx + 12 + (i * 37) % (hs - 24)
        pg.draw.circle(head, (90, 0, 0), (bx - hx, 6 + (i % 3) * 6), 9)
        pg.draw.line(head, (150, 0, 0), (bx - hx, 14), (bx - hx, 14 + 10 + i * 3), 2)
    screen.blit(head, (hx, hy))
    vs = 96
    vx = int(W + 10 + (cx - 15 - W - 10) * min(1.0, t))
    chomp = 1 + 0.08 * math.sin(t * 25) if 1.6 < t < 3.2 else 1
    v_img = _img("boss/verity_attack.webp" if t > 1.0 else "boss/verity.png", vs)
    v_img = pg.transform.smoothscale(v_img, (int(vs * chomp), int(vs / chomp)))
    vy = cy - 60
    screen.blit(v_img, (vx, vy))
    mouth = (vx + vs // 2, vy + int(vs * 0.66))
    if 1.0 < t < 3.2:  # brain floats from head to mouth and gets eaten
        k = min(1.0, (t - 1.0) / 0.6)
        sx, sy = hx + hs // 2, hy
        bx, by = sx + (mouth[0] - sx) * k, sy - 25 * math.sin(k * math.pi) + (mouth[1] - sy) * k
        size = int(36 * (1 - max(0.0, t - 1.6) / 1.6))
        if size > 2:
            b = brain(size)
            screen.blit(b, (bx - size // 2, by - size // 2))
    if t > 3.2:
        img = big_font.render("VERITY ATE YOUR BRAIN", True, (255, 220, 0))
        screen.blit(img, img.get_rect(center=(cx, 18)))
