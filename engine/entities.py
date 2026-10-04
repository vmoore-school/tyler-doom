import math
import random
from . import assets
from .projectiles import Arrow, MagicOrb, Rune, Puff


class Player:
    radius = 0.25

    def __init__(self, x, y, angle=0.0):
        self.x, self.y, self.angle = x, y, angle
        self.pitch = 0.0  # vertical look: horizon offset in screen pixels (+ = looking up)
        self.z = self.vz = 0.0  # jump height above the floor
        self.health = 100
        self.hurt_flash = 0.0
        self.invulnerable = False
        self.killer = None  # whatever dealt the killing blow (picks the death screen)

    @property
    def alive(self):
        return self.health > 0

    def hurt(self, dmg, source=None):
        if self.invulnerable or not self.alive:
            return
        self.health = max(0, self.health - dmg)
        self.hurt_flash = 0.3
        if not self.alive:
            self.killer = source


class Enemy:
    """Base enemy: idle -> chase -> attack (wind-up, shown with the attack sprite) -> recover -> chase.
    Attacks only resolve when the wind-up ends, so the player always gets a chance to react.
    Subclass and override stats, think() (movement) and perform_attack() to add new types."""
    health = 60
    speed = 1.5
    radius = 0.35
    scale = 0.9          # sprite height in world units
    damage = 8
    attack_range = 1.5   # how close the player must be to start (and, for melee, to take) the hit
    attack_cooldown = 1.6
    windup = 0.5         # telegraph time before the attack lands
    recovery = 0.0       # stands still this long after attacking
    sight_range = 14.0
    head_frac = 0.38     # top fraction of the sprite that counts as a headshot
    title = None         # name on the death screen (defaults to the class name)
    weapon = None        # sword / bow / staff drawn on the sprite
    hp_mult = speed_mult = cooldown_mult = 1.0  # per-face tweaks
    _frame_cache = {}

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.hp = self.health * self.hp_mult
        self.speed = self.speed * self.speed_mult
        self.state = "idle"
        self.timer = self.cooldown = self.anim = self.dead_time = 0.0
        self.strafe_dir = random.choice((-1, 1))
        self.strafe_t = 0.0

    @classmethod
    def make_frames(cls):
        raise NotImplementedError

    @classmethod
    def get_frames(cls):
        if cls not in Enemy._frame_cache:
            Enemy._frame_cache[cls] = cls.make_frames()
        return Enemy._frame_cache[cls]

    @property
    def frames(self):
        return self.get_frames()

    @property
    def alive(self):
        return self.state != "dead"

    @property
    def image(self):
        f = self.frames
        if self.state in ("dead", "pain", "attack"):
            return f[self.state]
        if self.state in ("idle", "recover"):
            return f["walk"][0]
        return f["walk"][int(self.anim * 6) % len(f["walk"])]

    def hurt(self, dmg):
        if not self.alive:
            return
        self.hp -= dmg
        if self.hp <= 0:
            self.state = "dead"
        else:
            self.state, self.timer = "pain", 0.2  # flinching cancels a wind-up

    def perform_attack(self, game, sees, dist):
        """Resolve an attack once the wind-up finishes. Default: a melee hit that only lands
        if the player is still in reach."""
        if sees and dist < self.attack_range:
            game.player.hurt(self.damage, self)
            game.play("hurt")

    def update(self, dt, game):
        if not self.alive:
            self.dead_time += dt
            return
        self.anim += dt
        self.timer -= dt
        self.cooldown -= dt
        p = game.player
        dx, dy = p.x - self.x, p.y - self.y
        dist = math.hypot(dx, dy) or 1e-6
        sees = dist < self.sight_range and game.world.line_of_sight(self.x, self.y, p.x, p.y)

        if self.state == "idle":
            if sees:
                self.state = "chase"
        elif self.state == "pain":
            if self.timer <= 0:
                self.state = "chase"
        elif self.state == "attack":
            if self.timer <= 0:
                if p.alive:
                    self.perform_attack(game, sees, dist)
                self.cooldown = self.attack_cooldown * self.cooldown_mult
                self.state, self.timer = "recover", self.recovery
        elif self.state == "recover":
            if self.timer <= 0:
                self.state = "chase"
        elif self.state == "chase":
            self.think(dt, game, sees, dist, dx, dy)

    def ready(self, game, sees, dist):
        return sees and game.player.alive and dist < self.attack_range and self.cooldown <= 0

    def start_attack(self):
        self.state, self.timer = "attack", self.windup

    def think(self, dt, game, sees, dist, dx, dy):
        """Chase-state behaviour. Default: walk up and attack when in range."""
        if self.ready(game, sees, dist):
            self.start_attack()
        elif dist > 1.0:
            self.approach(dt, game, sees, dist, dx, dy)

    # --- movement helpers ---

    def approach(self, dt, game, sees, dist, dx, dy, mult=1.0):
        """Head for the player, pathing around walls when they're out of sight."""
        if not sees:
            nxt = game.world.next_step(self.x, self.y)
            if nxt:
                dx, dy = nxt[0] - self.x, nxt[1] - self.y
                dist = math.hypot(dx, dy) or 1e-6
        step = self.speed * mult * dt
        game.world.move(self, dx / dist * step, dy / dist * step)

    def kite(self, dt, game, dist, dx, dy, back=0.0, mult=0.6):
        """Circle-strafe around the player (and back off if back > 0). Flips direction now and
        then, or when it bumps into a wall."""
        self.strafe_t -= dt
        if self.strafe_t <= 0:
            self.strafe_dir, self.strafe_t = random.choice((-1, 1)), random.uniform(1.0, 2.5)
        ux, uy = dx / dist, dy / dist
        mx = -uy * self.strafe_dir - ux * back
        my = ux * self.strafe_dir - uy * back
        n = math.hypot(mx, my) or 1e-6
        step = self.speed * mult * dt
        ox, oy = self.x, self.y
        game.world.move(self, mx / n * step, my / n * step)
        if math.hypot(self.x - ox, self.y - oy) < step * 0.3:
            self.strafe_dir = -self.strafe_dir


# --- roles: how an enemy fights ------------------------------------------------

class Brawler(Enemy):
    """Melee. Fast rusher, but raises its sword before swinging and is left open afterwards.
    Back off during the wind-up and the swing whiffs."""
    role, weapon = "Brawler", "sword"
    health, speed, damage = 70, 2.3, 15  # a bit slower than you, so you can kite it
    attack_range, windup, recovery, attack_cooldown = 1.5, 0.5, 0.6, 0.8

    def think(self, dt, game, sees, dist, dx, dy):
        if self.ready(game, sees, dist):
            self.start_attack()
        elif dist > 0.9:
            self.approach(dt, game, sees, dist, dx, dy)


class Archer(Enemy):
    """Ranged. Keeps its distance and strafes, draws the bow (glint) then looses an arrow
    at where you are. Keep moving sideways, or jump it."""
    role, weapon = "Archer", "bow"
    health, speed, damage = 45, 1.8, 10
    attack_range, windup, attack_cooldown = 11.0, 0.75, 2.2
    near, far = 4.0, 8.0  # preferred distance band

    def think(self, dt, game, sees, dist, dx, dy):
        if not sees or dist > self.far:
            self.approach(dt, game, sees, dist, dx, dy)
        else:
            self.kite(dt, game, dist, dx, dy, back=1.0 if dist < self.near else 0.0)
        if self.ready(game, sees, dist):
            self.start_attack()

    def perform_attack(self, game, sees, dist):
        if sees:
            p = game.player
            ang = math.atan2(p.y - self.y, p.x - self.x)
            game.world.projectiles.append(Arrow(self.x, self.y, ang, self, self.damage))


class Mage(Enemy):
    """Magic. Slow caster that alternates a homing orb (sidestep it late) with a rune under your
    feet (step out before it erupts). Blinks away if you get close."""
    role, weapon = "Mage", "staff"
    health, speed, damage = 55, 1.3, 14
    attack_range, windup, recovery, attack_cooldown = 12.0, 0.8, 0.3, 3.0
    near, far = 5.0, 9.0
    blink_cooldown = 6.0

    def __init__(self, x, y):
        super().__init__(x, y)
        self.spell = random.choice(("orb", "rune"))
        self.blink_t = 0.0

    def think(self, dt, game, sees, dist, dx, dy):
        self.blink_t -= dt
        if sees and dist < 2.5 and self.blink_t <= 0 and self.blink(game):
            return
        if not sees or dist > self.far:
            self.approach(dt, game, sees, dist, dx, dy)
        else:
            self.kite(dt, game, dist, dx, dy, back=0.6 if dist < self.near else 0.0, mult=0.5)
        if self.ready(game, sees, dist):
            self.start_attack()

    def blink(self, game):
        p, w = game.player, game.world
        spots = [(x, y) for x, y in w.free_tiles(p, self.near)
                 if math.hypot(x - self.x, y - self.y) < 7 and w.line_of_sight(x, y, p.x, p.y)]
        if not spots:
            return False
        w.effects.append(Puff(self.x, self.y, 0.5))
        self.x, self.y = random.choice(spots)
        w.effects.append(Puff(self.x, self.y, 0.5))
        self.blink_t = self.blink_cooldown
        self.cooldown = max(self.cooldown, 1.0)  # no instant cast after teleporting
        return True

    def perform_attack(self, game, sees, dist):
        if not sees:
            return
        p = game.player
        if self.spell == "orb":
            ang = math.atan2(p.y - self.y, p.x - self.x)
            game.world.projectiles.append(MagicOrb(self.x, self.y, ang, self, self.damage))
        else:
            game.world.projectiles.append(Rune(p.x, p.y, self, int(self.damage * 1.4)))
        self.spell = "rune" if self.spell == "orb" else "orb"


ROLES = [Brawler, Archer, Mage]


# --- faces: who the enemy is ---------------------------------------------------

class Friend(Enemy):
    """Demon body with a face cut out of a photo in the assets/ folder."""
    photo = None
    crop = (0, 0, 1, 1)  # face region as fractions (x, y, w, h)
    rotate = 0
    skin = (120, 60, 50)
    head_frac = 0.47

    @classmethod
    def make_frames(cls):
        face = assets.load_face(cls.photo, cls.crop, cls.rotate)
        return assets.enemy_frames(cls.skin, (255, 220, 0), face=face, weapon=cls.weapon)


class Grinner(Friend):
    photo, crop, rotate = "Image.jpeg", (0.25, 0.12, 0.6, 0.55), -90
    skin, speed_mult = (60, 60, 70), 1.15


class Starer(Friend):
    photo, crop = "Image.png", (0.15, 0.0, 0.65, 0.55)
    skin, cooldown_mult = (40, 40, 45), 0.85


class Tyler(Friend):
    photo, crop = "Tyler photo 1.jpg", (0.25, 0.22, 0.5, 0.48)
    skin, hp_mult = (150, 150, 155), 1.4


class Kieran(Friend):
    photo, crop = "w4efwfew.png", (0.08, 0.23, 0.84, 0.62)
    skin, radius, scale = (70, 75, 90), 0.45, 1.25
    hp_mult, speed_mult = 1.8, 0.85


FACES = [Grinner, Starer, Tyler, Kieran]


def combine(face, role):
    """Every enemy is a friend's face (looks + small stat tweak) on a role (weapon + AI)."""
    return type(face.__name__ + role.__name__, (face, role),
                {"title": f"{face.__name__} the {role.role}"})


# Classes that waves pick from at random: every face with every role.
SPAWN_POOL = [combine(f, r) for f in FACES for r in ROLES]
# Map character -> enemy class, for placing enemies in a LEVEL by hand. Register new types here.
_POOL = {c.__name__: c for c in SPAWN_POOL}
ENEMY_TYPES = {"B": _POOL["GrinnerBrawler"], "A": _POOL["StarerArcher"], "M": _POOL["TylerMage"],
               "K": _POOL["KieranBrawler"]}
