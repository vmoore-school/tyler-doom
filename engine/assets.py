"""Procedurally generated textures, sprites and sounds."""
import array
import os
import random
import pygame as pg
from .settings import TEX

KEY = (255, 0, 255)


def _surf(w, h):
    s = pg.Surface((w, h))
    s.fill(KEY)
    s.set_colorkey(KEY)
    return s


def _noise(s, amt, seed):
    rnd = random.Random(seed)
    for y in range(s.get_height()):
        for x in range(s.get_width()):
            r, g, b, _ = s.get_at((x, y))
            d = rnd.randint(-amt, amt)
            s.set_at((x, y), (max(0, min(255, r + d)), max(0, min(255, g + d)), max(0, min(255, b + d))))


# --- wall textures -------------------------------------------------------

def brick():
    s = pg.Surface((TEX, TEX))
    s.fill((55, 50, 45))
    for row in range(TEX // 8):
        off = 8 if row % 2 else 0
        for col in range(-1, TEX // 16 + 1):
            pg.draw.rect(s, (120, 40, 30), (col * 16 + off + 1, row * 8 + 1, 14, 6))
    _noise(s, 12, 1)
    return s


def stone():
    s = pg.Surface((TEX, TEX))
    s.fill((70, 70, 75))
    rnd = random.Random(2)
    for y in range(0, TEX, 16):
        x = -rnd.randint(0, 12)
        while x < TEX:
            w = rnd.randint(14, 26)
            c = rnd.randint(95, 125)
            pg.draw.rect(s, (c, c, c + 5), (x + 1, y + 1, w - 2, 14))
            x += w
    _noise(s, 10, 3)
    return s


def metal():
    s = pg.Surface((TEX, TEX))
    s.fill((60, 75, 70))
    for y in (0, 32):
        pg.draw.rect(s, (85, 105, 95), (2, y + 2, TEX - 4, 28))
        for rx in (6, TEX - 7):
            for ry in (y + 6, y + 26):
                pg.draw.circle(s, (150, 160, 150), (rx, ry), 2)
    _noise(s, 6, 4)
    return s


WALLS = {1: brick, 2: stone, 3: metal}


# --- enemy sprites -------------------------------------------------------

PHOTO_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")  # files are named by subfolder, e.g. "boss/verity.png"


_photos = {}


def _photo(filename, rotate):
    """Load (and rotate) a photo once; several enemy classes share each face."""
    if (filename, rotate) not in _photos:
        _photos[filename, rotate] = pg.transform.rotate(pg.image.load(os.path.join(PHOTO_DIR, filename)), rotate)
    return _photos[filename, rotate]


def load_face(filename, crop=(0, 0, 1, 1), rotate=0, size=(26, 30)):
    """Load a face image and fit it to `size`. Pre-cut faces (transparent background) keep their
    own outline; plain photos are cropped (fractions x, y, w, h) and cut out as an oval."""
    img = _photo(filename, rotate)
    cutout = img.get_flags() & pg.SRCALPHA and img.get_bounding_rect().size != img.get_size()
    if cutout:
        img = img.subsurface(img.get_bounding_rect())
    w, h = img.get_size()
    rect = pg.Rect(int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h))
    face = pg.transform.smoothscale(img.subsurface(rect), size)
    out = _surf(*size)
    mask = pg.Surface(size)
    mask.fill((255, 255, 255) if cutout else (0, 0, 0))
    pg.draw.ellipse(mask, (255, 255, 255), (0, 0, *size))
    for y in range(size[1]):
        for x in range(size[0]):
            if mask.get_at((x, y))[0]:
                c = face.get_at((x, y))
                transparent = len(c) > 3 and c[3] < 128
                out.set_at((x, y), KEY if transparent or c[:3] == KEY else c[:3])
    return out


def _weapon(s, weapon, attacking):
    """Draw a role's weapon on a demon sprite. The attack pose doubles as the wind-up telegraph."""
    wood, steel = (120, 75, 35), (220, 225, 235)
    if weapon == "sword":
        if attacking:  # raised overhead, about to swing
            pg.draw.line(s, steel, (50, 10), (62, 1), 4)
            pg.draw.line(s, (90, 60, 30), (46, 13), (50, 10), 3)
            pg.draw.line(s, (200, 170, 60), (45, 6), (53, 14), 2)
            pg.draw.arc(s, (255, 255, 255), (6, 4, 56, 50), 0.2, 1.4, 2)  # swoosh
        else:
            pg.draw.line(s, steel, (53, 42), (60, 18), 4)
            pg.draw.line(s, (200, 170, 60), (48, 41), (58, 44), 2)
    elif weapon == "bow":
        if attacking:  # drawn and aimed straight at you
            pg.draw.arc(s, wood, (20, 22, 24, 34), -1.3, 1.3, 3)
            pg.draw.line(s, (230, 230, 230), (37, 25), (37, 53))
            pg.draw.circle(s, (255, 255, 255), (32, 39), 3)  # arrowhead glint
            pg.draw.circle(s, (255, 60, 60), (32, 39), 1)
        else:
            pg.draw.arc(s, wood, (2, 26, 14, 30), 1.9, 4.4, 3)
            pg.draw.line(s, (230, 230, 230), (8, 28), (8, 54))
    elif weapon == "staff":
        if attacking:
            pg.draw.circle(s, (150, 40, 255), (32, 5), 6)
            pg.draw.circle(s, (230, 180, 255), (32, 5), 3)
        else:
            pg.draw.line(s, wood, (54, 60), (54, 16), 3)
            pg.draw.circle(s, (150, 40, 255), (54, 13), 4)
            pg.draw.circle(s, (230, 180, 255), (54, 13), 2)


def demon(skin, eye, leg=0, arms="down", horns=True, face=None, weapon=None):
    s = _surf(64, 64)
    dark = tuple(c * 6 // 10 for c in skin)
    pg.draw.rect(s, dark, (22 + leg, 44, 7, 19))
    pg.draw.rect(s, dark, (35 - leg, 44, 7, 19))
    pg.draw.ellipse(s, skin, (18, 22, 28, 26))
    pg.draw.ellipse(s, dark, (24, 28, 16, 12), 2)
    if arms == "down":
        pg.draw.line(s, skin, (21, 27), (12 + leg, 45), 5)
        pg.draw.line(s, skin, (43, 27), (52 - leg, 45), 5)
    elif weapon == "bow":  # arms forward, holding the drawn bow
        pg.draw.line(s, skin, (21, 27), (30, 40), 5)
        pg.draw.line(s, skin, (43, 27), (36, 38), 5)
    else:
        pg.draw.line(s, skin, (21, 27), (12, 8), 5)
        pg.draw.line(s, skin, (43, 27), (52, 8), 5)
        if not weapon:
            pg.draw.circle(s, (255, 140, 20), (32, 5), 5)
            pg.draw.circle(s, (255, 240, 120), (32, 5), 2)
    if face:
        s.blit(face, (32 - face.get_width() // 2, 0))
        _weapon(s, weapon, arms != "down")
        return s
    pg.draw.circle(s, skin, (32, 16), 9)
    if horns:
        pg.draw.polygon(s, (230, 220, 190), [(24, 12), (19, 2), (28, 9)])
        pg.draw.polygon(s, (230, 220, 190), [(40, 12), (45, 2), (36, 9)])
    pg.draw.rect(s, eye, (27, 13, 3, 3))
    pg.draw.rect(s, eye, (34, 13, 3, 3))
    pg.draw.line(s, (40, 0, 0), (28, 21), (36, 21), 2)
    return s


def _rekey(tinted, original):
    """Restore colorkey transparency lost when tinting a keyed surface."""
    out = _surf(*original.get_size())
    out.blit(tinted, (0, 0))
    for y in range(original.get_height()):
        for x in range(original.get_width()):
            if original.get_at((x, y))[:3] == KEY:
                out.set_at((x, y), KEY)
    return out


def corpse(skin):
    s = _surf(64, 64)
    pg.draw.ellipse(s, (120, 0, 0), (8, 52, 48, 11))
    pg.draw.ellipse(s, skin, (16, 50, 30, 10))
    pg.draw.circle(s, skin, (46, 54), 6)
    pg.draw.line(s, (230, 220, 190), (20, 56), (30, 54), 2)
    return s


def enemy_frames(skin, eye, horns=True, face=None, weapon=None):
    pain = tuple(min(255, c + 100) for c in skin)
    pain_face = None
    if face:
        pain_face = face.copy()
        pain_face.fill((120, 0, 0), special_flags=pg.BLEND_RGB_ADD)
        pain_face.set_colorkey(None)
        pain_face = _rekey(pain_face, face)
    return {
        "walk": [demon(skin, eye, 0, horns=horns, face=face, weapon=weapon),
                 demon(skin, eye, 3, horns=horns, face=face, weapon=weapon)],
        "attack": demon(skin, eye, arms="up", horns=horns, face=face, weapon=weapon),
        "pain": demon(pain, (255, 255, 255), horns=horns, face=pain_face, weapon=weapon),
        "dead": corpse(skin),
    }


# --- weapon sprites (photos from assets/, held in the bottom right) -------

def hue_shift(img, degrees, sat=1.0):
    """Rotate every pixel's hue (and scale its saturation), keeping alpha."""
    out = img.copy()
    c = pg.Color(0)
    for y in range(out.get_height()):
        for x in range(out.get_width()):
            px = out.get_at((x, y))
            if px.a == 0:
                continue
            h, s, v, _ = px.hsva
            c.hsva = ((h + degrees) % 360, min(100.0, s * sat), v, 100)
            out.set_at((x, y), (c.r, c.g, c.b, px.a))
    return out


def held_sprite(filename, scale, flip=False):
    """Load a held-item photo, trim the transparent border, scale it, and optionally mirror it."""
    img = pg.image.load(os.path.join(PHOTO_DIR, filename)).convert_alpha()
    img = img.subsurface(img.get_bounding_rect()).copy()
    img = pg.transform.smoothscale(img, (round(img.get_width() * scale), round(img.get_height() * scale)))
    return pg.transform.flip(img, True, False) if flip else img


def muzzle_flash(img, pos, size):
    """Gun sprite with weapons/flash.png behind the muzzle at `pos` (fractions of its
    width/height). The canvas grows up and left to fit the flash, so when it's drawn anchored
    bottom-right the gun stays exactly where the idle frame is."""
    flash = held_sprite("weapons/flash.png", 1.0)
    flash = pg.transform.smoothscale(flash, (size, round(size * flash.get_height() / flash.get_width())))
    fw, fh = flash.get_size()
    cx, cy = pos[0] * img.get_width(), pos[1] * img.get_height() - fh * 0.22  # just past the barrel tip
    pad_l, pad_t = max(0, round(fw / 2 - cx)), max(0, round(fh / 2 - cy))
    out = pg.Surface((img.get_width() + pad_l, img.get_height() + pad_t), pg.SRCALPHA)
    out.blit(flash, (round(cx + pad_l - fw / 2), round(cy + pad_t - fh / 2)))  # behind the gun
    out.blit(img, (pad_l, pad_t))
    return out


TYLER = ("enemies/Tyler_3.png",)


# --- sounds --------------------------------------------------------------

def load_sound(filename, skip=0.0, length=None):
    """A sound file from assets/ (path inside it), minus `skip` seconds of lead-in,
    cut to `length` seconds if given.
    Returns None if the mixer is unavailable or the file can't be read."""
    if not pg.mixer.get_init():
        return None
    try:
        snd = pg.mixer.Sound(os.path.join(PHOTO_DIR, filename))
    except (pg.error, FileNotFoundError) as e:
        print("couldn't load sound", filename, e)
        return None
    if skip or length:
        freq, size, chans = pg.mixer.get_init()
        frame = abs(size) // 8 * chans
        raw = snd.get_raw()
        start = int(skip * freq) * frame
        end = start + int(length * freq) * frame if length else len(raw)
        snd = pg.mixer.Sound(buffer=raw[start:end])
    return snd


def noise_sound(dur, vol, decay, seed=0):
    """Decaying white-noise burst. Returns None if the mixer is unavailable."""
    if not pg.mixer.get_init():
        return None
    rnd = random.Random(seed)
    freq, _, chans = pg.mixer.get_init()
    n = int(freq * dur)
    data = array.array("h")
    for i in range(n):
        v = int(rnd.uniform(-1, 1) * vol * 32767 * (1 - i / n) ** decay)
        data.extend([v] * chans)
    return pg.mixer.Sound(buffer=data)
