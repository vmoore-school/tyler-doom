"""Main menu, pause menu, settings and help screens. Drawn straight onto the window (not the
low-res game surface) so text stays sharp at any window size: layout is written for a 960x600
canvas and scaled. Keyboard (W/S or arrows, Enter) and mouse both work."""
import os
import sys
import pygame as pg
from .assets import PHOTO_DIR
from .settings import RESOLUTIONS

WEB = sys.platform == "emscripten"

RED, YELLOW, WHITE, GREY = (220, 30, 30), (255, 215, 0), (235, 235, 235), (150, 150, 150)

CONTROLS = [
    ("WASD / arrows", "Move / turn"),
    ("Mouse", "Look around"),
    ("Left click", "Fire"),
    ("1 / 2 / 3 / 4", "Fist / pistol / shotgun (wave 7) / rifle (wave 21)"),
    ("Scroll wheel", "Next / previous unlocked weapon"),
    ("R", "Reload (or restart after dying)"),
    ("T", "Tyler Death Beam on / off. Using it means that round's leaderboard entry won't count"),
    ("Space", "Jump"),
    ("Shift (hold)", "Sprint"),
    ("Ctrl / double-tap a direction", "Slide (Ctrl slides the way you're moving; steer with WASD). In the air: dive"),
    ("Right click / E (hold)", "Grapple"),
    ("Middle click / G / Q", "Throw a David grenade"),
    ("Z / X / C", "Answer Verity's pop quiz"),
    ("Tab / Esc", "Pause (settings are in the pause and main menus)"),
]

HOW_TO_PLAY = [
    "Survive waves of your friends. Each wave has one more enemy than the last. "
    "Clearing a wave refills your health and grenades and reloads your guns. "
    "Ammo is unlimited, but every gun has to reload when its clip runs out.",
    "Every enemy shows its attack before it lands. Dodge it:",
    "  Brawler (sword): raises the sword, then swings. Back off. It's a bit slower than you.",
    "  Archer (bow): glints, then shoots where you are. Strafe or jump the arrow.",
    "  Mage (staff): slow homing orbs (sidestep late) and runes under your feet "
    "(the screen glows purple: move!).",
    "Shooting an enemy makes it flinch and cancels its attack. Headshots do 2.5x damage. "
    "The radar (top right) points to every enemy; bigger dots are closer.",
    "Grapple: hold to throw your hand at a wall or the floor and get pulled to it. "
    "Grab high on a wall to climb.",
    "Al Gore's Tree of Life drops golden apples with random power-ups. "
    "Every 7th wave, Verity arrives, stronger each time.",
    "When you die, enter your name to post your wave and kills to the global leaderboard "
    "(rounds with the Tyler Death Beam don't count).",
]


def wrap(text, font, width):
    """Split text into lines that fit `width`, keeping any leading indent on wrapped lines."""
    indent = text[:len(text) - len(text.lstrip())]
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}" if line else indent + word
        if line and font.size(test)[0] > width:
            lines.append(line)
            line = indent + "  " + word
        else:
            line = test
    return lines + [line] if line else lines


class Menus:
    LW, LH = 960, 600  # logical canvas the layout is written for

    def __init__(self, game):
        self.game = game
        self.current = None  # "main", "pause", "help", "settings", "leaderboard" or None while playing
        self.board = None    # leaderboard Request being shown
        self._logo = None    # (scale, surface) cache of the main menu logo
        self._shade = None   # darkens the game behind the menu
        self._text = {}      # rendered text, by (font, text, colour)
        self.back_to = None  # where help / settings return to
        self.sel = 0
        self.page = 0
        self.buttons = []    # (rect, action) of what's on screen, for the mouse
        self.resize((self.LW, self.LH))

    def resize(self, size):
        """Fit the layout to the area the game picture occupies on screen."""
        self.m = size[0] / self.LW
        self._text = {}  # rendered with the old fonts
        font = lambda px: pg.font.Font(None, max(8, round(px * self.m)))
        self.title_font, self.item_font = font(110), font(48)
        self.text_font, self.small_font = font(26), font(22)
        self.option_font = font(36)

    @property
    def active(self):
        return self.current is not None

    @property
    def title_screen(self):
        """True on the main menu (and screens opened from it): no game running behind it."""
        return self.current == "main" or (self.current in ("help", "settings", "leaderboard")
                                          and self.back_to == "main")

    def open(self, name):
        if name in ("help", "settings", "leaderboard"):
            self.back_to, self.page = self.current, 0
        if name == "leaderboard":
            self.board = self.game.leaderboard.fetch_top()
        self.current, self.sel = name, 0
        self.game.unlock_mouse()

    def close(self):
        self.current = None
        self.game.lock_mouse()

    def items(self):
        quit_ = [] if WEB else [("QUIT", "quit")]  # a web page can't quit
        if self.current == "main":
            return [("PLAY", "play"), ("LEADERBOARD", "leaderboard"), ("HELP", "help"), ("SETTINGS", "settings")] + quit_
        if self.current == "pause":
            return [("RESUME", "resume"), ("LEADERBOARD", "leaderboard"), ("HELP", "help"), ("SETTINGS", "settings"),
                    ("MAIN MENU", "main")] + quit_
        if self.current == "settings":
            g, st = self.game, self.game.settings
            items = []
            if not WEB:  # browsers go fullscreen with F11 instead
                items.append((f"DISPLAY: {'FULLSCREEN' if st['fullscreen'] else 'WINDOWED'}", "fullscreen"))
            w, h = g.view_size(st["resolution"])
            items.append((f"RESOLUTION: {st['resolution'].upper()} ({w}x{h})", "resolution"))
            return items + [("BACK", "back")]
        return []

    # --- input ---

    def handle(self, ev):
        items = self.items()
        if ev.type == pg.KEYDOWN:
            back = ev.key in (pg.K_ESCAPE, pg.K_BACKSPACE)
            if self.current == "help":
                if ev.key in (pg.K_a, pg.K_LEFT, pg.K_d, pg.K_RIGHT, pg.K_TAB):
                    self.page = 1 - self.page
                elif back or ev.key in (pg.K_RETURN, pg.K_SPACE):
                    self.act("back")
            elif self.current == "pause" and (back or ev.key == pg.K_TAB):
                self.act("resume")
            elif self.current == "settings" and back:
                self.act("back")
            elif self.current == "leaderboard":
                if ev.key == pg.K_r:
                    self.board = self.game.leaderboard.fetch_top()
                elif back or ev.key in (pg.K_RETURN, pg.K_SPACE):
                    self.act("back")
            elif ev.key in (pg.K_w, pg.K_UP):
                self.sel = (self.sel - 1) % len(items)
            elif ev.key in (pg.K_s, pg.K_DOWN):
                self.sel = (self.sel + 1) % len(items)
            elif ev.key in (pg.K_RETURN, pg.K_SPACE):
                self.act(items[self.sel][1])
            elif self.current == "settings" and ev.key in (pg.K_a, pg.K_LEFT, pg.K_d, pg.K_RIGHT):
                step = -1 if ev.key in (pg.K_a, pg.K_LEFT) else 1
                if items[self.sel][1] != "back":
                    self.act(items[self.sel][1], step)
        elif ev.type in (pg.MOUSEMOTION, pg.MOUSEBUTTONDOWN):
            pos = self.to_menu(ev.pos)
            for i, (rect, action) in enumerate(self.buttons):
                if rect.collidepoint(pos):
                    if ev.type == pg.MOUSEMOTION:
                        self.sel = i if i < len(items) else self.sel
                    elif ev.button == 1:
                        self.act(action)
                        break

    def to_menu(self, pos):
        """Window position -> position on the menu surface (which is offset by any black bars)."""
        r = self.game.content_rect
        return pos[0] - r.x, pos[1] - r.y

    def act(self, action, step=1):
        g = self.game
        if action == "play":
            g.reset()
            self.close()
        elif action == "resume":
            self.close()
        elif action in ("help", "settings", "leaderboard"):
            self.open(action)
        elif action == "back":
            self.current, self.sel = self.back_to, 0
        elif action == "main":
            g.reset()
            self.open("main")
        elif action in ("page0", "page1"):
            self.page = int(action[-1])
        elif action == "fullscreen":
            g.change_setting("fullscreen", not g.settings["fullscreen"])
        elif action == "resolution":
            i = RESOLUTIONS.index(g.settings["resolution"])
            g.change_setting("resolution", RESOLUTIONS[(i + step) % len(RESOLUTIONS)])
        elif action == "quit":
            g.quit()

    # --- drawing (positions are on the 960x600 logical canvas) ---

    def shade_alpha(self):
        """How much the game behind is darkened."""
        return 225 if self.current in ("help", "leaderboard") else 150

    def draw_shade(self, win):
        # A solid surface with whole-surface alpha: much faster to blend than per-pixel alpha.
        if self._shade is None or self._shade.get_size() != win.get_size():
            self._shade = pg.Surface(win.get_size()).convert()
        self._shade.set_alpha(self.shade_alpha())
        win.blit(self._shade, (0, 0))

    def draw(self, win, shade=True):
        if shade:
            self.draw_shade(win)
        self.buttons = []
        if self.current == "help":
            self.draw_help(win)
            return
        if self.current == "leaderboard":
            self.draw_leaderboard(win)
            return
        cx = self.LW // 2
        top = 255  # first menu item
        if self.current == "main":
            logo = self.logo()
            win.blit(logo, logo.get_rect(center=(round(cx * self.m), round(122 * self.m))))
            self.text(win, self.text_font, "Wave survival against your friends", GREY, (cx, 232))
            top = 285
        else:
            heading = {"pause": "PAUSED", "settings": "SETTINGS"}[self.current]
            sub = {"pause": f"Wave {self.game.wave}", "settings": "Enter / click or A/D to change"}[self.current]
            self.text(win, self.title_font, heading, RED, (cx, 130), shadow=True)
            self.text(win, self.text_font, sub, GREY, (cx, 190))
        font = self.item_font if self.current != "settings" else self.option_font
        gap = 50 if len(self.items()) <= 5 else 42
        for i, (label, action) in enumerate(self.items()):
            selected = i == self.sel
            rect = self.text(win, font, f"> {label} <" if selected else label,
                             YELLOW if selected else WHITE, (cx, top + i * gap))
            self.buttons.append((rect.inflate(round(60 * self.m), round(12 * self.m)), action))
        if self.current == "settings":
            note = "Higher resolutions look sharper but run slower (the HUD stays pixel art)"
            self.text(win, self.small_font, note, GREY, (cx, top + len(self.items()) * gap + 10))
        hint = "W/S or mouse to choose, Enter or click to select"
        if self.current == "pause":  # sits above the status bar
            self.text(win, self.small_font, hint + ",  Tab to resume", GREY, (cx, 482))
        else:
            self.text(win, self.small_font, hint, GREY, (cx, self.LH - 30))

    def logo(self):
        """assets/other/logo.png, trimmed and scaled up ~3x with hard pixel edges (it's pixel-sized art)."""
        if self._logo is None or self._logo[0] != self.m:
            img = pg.image.load(os.path.join(PHOTO_DIR, "other/logo.png")).convert_alpha()
            img = img.subsurface(img.get_bounding_rect())
            k = 190 * self.m / img.get_height()  # 190 logical pixels tall
            logo = pg.transform.scale(img, (round(img.get_width() * k), round(img.get_height() * k)))
            logo.set_alpha(255, pg.RLEACCEL)  # skips the transparent parts when drawn
            self._logo = (self.m, logo)
        return self._logo[1]

    def draw_leaderboard(self, win):
        w, h, m = self.LW, self.LH, self.m
        self.text(win, self.item_font, "LEADERBOARD", RED, (w // 2, 45), shadow=True)
        self.text(win, self.small_font, "Highest wave reached, then most kills", GREY, (w // 2, 85))
        req = self.board
        if not self.game.leaderboard.enabled:
            msg = "The leaderboard isn't set up (see engine/leaderboard_config.py)"
        elif req.status == "pending":
            msg = "Loading..."
        elif req.status == "error":
            msg = f"Couldn't load the leaderboard: {req.error}"
        elif not req.result:
            msg = "No scores yet. Be the first!"
        else:
            msg = None
        if msg:
            self.text(win, self.text_font, msg, WHITE, (w // 2, 250))
        else:
            cols = ((250, "#", "midright"), (290, "NAME", "midleft"), (600, "WAVE", "midright"), (720, "KILLS", "midright"))
            for x, label, anchor in cols:
                self.text(win, self.small_font, label, GREY, (x, 130), anchor=anchor)
            for i, row in enumerate(req.result):
                y = 165 + i * 34
                color = YELLOW if i == 0 else WHITE
                values = (f"{i + 1}.", str(row.get("name", "?")).upper(), str(row.get("wave", 0)), str(row.get("kills", 0)))
                for (x, _, anchor), value in zip(cols, values):
                    self.text(win, self.option_font, value, color, (x, y), anchor=anchor)
        rect = self.text(win, self.text_font, "> BACK <", YELLOW, (w // 2, h - 42))
        self.buttons.append((rect.inflate(round(60 * m), round(16 * m)), "back"))
        self.text(win, self.small_font, "R to refresh, Esc to go back", GREY, (w // 2, h - 16))

    def draw_help(self, win):
        w, h, m = self.LW, self.LH, self.m
        self.text(win, self.item_font, "HELP", RED, (w // 2, 38), shadow=True)
        for i, label in enumerate(("CONTROLS", "HOW TO PLAY")):  # tabs
            rect = self.text(win, self.text_font, label, YELLOW if i == self.page else GREY,
                             (w // 2 + (i * 2 - 1) * 110, 82))
            if i == self.page:
                pg.draw.line(win, YELLOW, (rect.left, rect.bottom + 3 * m), (rect.right, rect.bottom + 3 * m),
                             max(1, round(2 * m)))
            self.buttons.append((rect.inflate(round(30 * m), round(16 * m)), f"page{i}"))
        y, left = 118, 80
        if self.page == 0:
            for key, what in CONTROLS:
                self.text(win, self.text_font, key, YELLOW, (left, y), anchor="topleft")
                for line in wrap(what, self.text_font, (w - 340 - left) * m):
                    self.text(win, self.text_font, line, WHITE, (330, y), anchor="topleft")
                    y += 24
                y += 5
        else:
            for para in HOW_TO_PLAY:
                for line in wrap(para, self.text_font, (w - 2 * left) * m):
                    self.text(win, self.text_font, line, WHITE, (left, y), anchor="topleft")
                    y += 23
                y += 5
        rect = self.text(win, self.text_font, "> BACK <", YELLOW, (w // 2, h - 42))
        self.buttons.append((rect.inflate(round(60 * m), round(16 * m)), "back"))
        self.text(win, self.small_font, "A/D to switch tabs, Esc to go back", GREY, (w // 2, h - 16))

    def text(self, win, font, s, color, pos, anchor="center", shadow=False):
        """Draw text at a logical position; returns its rect in window pixels."""
        img = self.render(font, s, color)
        rect = img.get_rect(**{anchor: (round(pos[0] * self.m), round(pos[1] * self.m))})
        if shadow:
            off = max(1, round(4 * self.m))
            win.blit(self.render(font, s, (0, 0, 0)), rect.move(off, off))
        win.blit(img, rect)
        return rect

    def render(self, font, s, color):
        """font.render, remembered (menus redraw the same text every frame), RLE for fast blits."""
        key = (font, s, color)
        img = self._text.get(key)
        if img is None:
            if len(self._text) > 500:
                self._text.clear()
            img = self._text[key] = font.render(s, True, color).convert_alpha()
            img.set_alpha(255, pg.RLEACCEL)
        return img
