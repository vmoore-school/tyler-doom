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

PHOTO_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")


def load_face(filename, crop, rotate=0, size=(26, 30)):
    """Load a photo, crop (fractions x, y, w, h), and cut out an oval face."""
    img = pg.transform.rotate(pg.image.load(os.path.join(PHOTO_DIR, filename)), rotate)
    w, h = img.get_size()
    rect = pg.Rect(int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h))
    face = pg.transform.smoothscale(img.subsurface(rect), size)
    out = _surf(*size)
    mask = pg.Surface(size)
    mask.fill((0, 0, 0))
    pg.draw.ellipse(mask, (255, 255, 255), (0, 0, *size))
    for y in range(size[1]):
        for x in range(size[0]):
            if mask.get_at((x, y))[0]:
                c = face.get_at((x, y))
                transparent = len(c) > 3 and c[3] < 128
                out.set_at((x, y), KEY if transparent or c[:3] == KEY else c[:3])
    return out


def demon(skin, eye, leg=0, arms="down", horns=True, face=None):
    s = _surf(64, 64)
    dark = tuple(c * 6 // 10 for c in skin)
    pg.draw.rect(s, dark, (22 + leg, 44, 7, 19))
    pg.draw.rect(s, dark, (35 - leg, 44, 7, 19))
    pg.draw.ellipse(s, skin, (18, 22, 28, 26))
    pg.draw.ellipse(s, dark, (24, 28, 16, 12), 2)
    if arms == "down":
        pg.draw.line(s, skin, (21, 27), (12 + leg, 45), 5)
        pg.draw.line(s, skin, (43, 27), (52 - leg, 45), 5)
    else:
        pg.draw.line(s, skin, (21, 27), (12, 8), 5)
        pg.draw.line(s, skin, (43, 27), (52, 8), 5)
        pg.draw.circle(s, (255, 140, 20), (32, 5), 5)
        pg.draw.circle(s, (255, 240, 120), (32, 5), 2)
    if face:
        s.blit(face, (32 - face.get_width() // 2, 0))
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


def enemy_frames(skin, eye, horns=True, face=None):
    pain = tuple(min(255, c + 100) for c in skin)
    pain_face = None
    if face:
        pain_face = face.copy()
        pain_face.fill((120, 0, 0), special_flags=pg.BLEND_RGB_ADD)
        pain_face.set_colorkey(None)
        pain_face = _rekey(pain_face, face)
    return {
        "walk": [demon(skin, eye, 0, horns=horns, face=face), demon(skin, eye, 3, horns=horns, face=face)],
        "attack": demon(skin, eye, arms="up", horns=horns, face=face),
        "pain": demon(pain, (255, 255, 255), horns=horns, face=pain_face),
        "dead": corpse(skin),
    }


# --- weapon sprites (64x48, scaled up when drawn) ------------------------

def _flash(s, pos, r):
    pg.draw.circle(s, (255, 120, 0), pos, r)
    pg.draw.circle(s, (255, 230, 90), pos, r * 2 // 3)
    pg.draw.circle(s, (255, 255, 230), pos, r // 3)


def pistol(firing=False):
    s = _surf(64, 48)
    if firing:
        _flash(s, (32, 9), 9)
    pg.draw.rect(s, (50, 50, 55), (27, 14, 10, 26))
    pg.draw.rect(s, (90, 90, 100), (29, 14, 6, 24))
    pg.draw.rect(s, (30, 30, 30), (31, 12, 2, 3))
    pg.draw.ellipse(s, (205, 150, 115), (22, 32, 20, 18))
    pg.draw.ellipse(s, (170, 120, 90), (22, 32, 20, 18), 2)
    return s


def shotgun(firing=False):
    s = _surf(64, 48)
    if firing:
        _flash(s, (32, 6), 12)
    pg.draw.rect(s, (45, 45, 50), (25, 8, 6, 34))
    pg.draw.rect(s, (45, 45, 50), (33, 8, 6, 34))
    pg.draw.rect(s, (110, 110, 120), (27, 8, 2, 32))
    pg.draw.rect(s, (110, 110, 120), (35, 8, 2, 32))
    pg.draw.rect(s, (110, 65, 30), (22, 26, 20, 10))
    pg.draw.ellipse(s, (205, 150, 115), (14, 30, 16, 16))
    pg.draw.ellipse(s, (205, 150, 115), (36, 34, 18, 16))
    return s


TYLER = ("Tyler photo 1.jpg", (0.25, 0.22, 0.5, 0.48))


def tyler_beam(firing=False):
    s = _surf(64, 48)
    if firing:
        pg.draw.circle(s, (255, 60, 200), (32, 14), 14)
        pg.draw.circle(s, (255, 200, 255), (32, 14), 9)
    pg.draw.polygon(s, (70, 30, 90), [(18, 48), (24, 14), (40, 14), (46, 48)])
    pg.draw.polygon(s, (150, 80, 180), [(18, 48), (24, 14), (40, 14), (46, 48)], 2)
    s.blit(load_face(*TYLER, size=(16, 18)), (24, 20))
    pg.draw.ellipse(s, (205, 150, 115), (8, 34, 16, 14))
    pg.draw.ellipse(s, (205, 150, 115), (40, 34, 16, 14))
    return s


# --- sounds --------------------------------------------------------------

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
