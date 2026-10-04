"""Main menu, pause menu and help screens. Drawn straight onto the window (not the low-res
game surface) so text stays sharp. Keyboard (W/S or arrows, Enter) and mouse both work."""
import sys
import pygame as pg

WEB = sys.platform == "emscripten"

RED, YELLOW, WHITE, GREY = (220, 30, 30), (255, 215, 0), (235, 235, 235), (150, 150, 150)

CONTROLS = [
    ("WASD / arrows", "Move / turn"),
    ("Mouse", "Look around"),
    ("Left click", "Fire"),
    ("1 / 2", "Pistol / shotgun"),
    ("3", "Tyler Death Beam (press T first to enable it)"),
    ("T", "Enable the Tyler Death Beam. Leaderboard entries for that round won't count"),
    ("Space", "Jump"),
    ("Right click / E (hold)", "Grapple"),
    ("Middle click / G", "Throw a David grenade"),
    ("Z / X / C", "Answer Verity's pop quiz"),
    ("Tab / Esc", "Pause"),
    ("R", "Restart after dying"),
]

HOW_TO_PLAY = [
    "Survive waves of your friends. Each wave has one more enemy than the last. "
    "Clearing a wave refills your health, ammo and grenades.",
    "Every enemy shows its attack before it lands, so watch and dodge:",
    "  Brawler (sword): raises the sword, then swings. Back off. It's a bit slower than you.",
    "  Archer (bow): glints, then shoots where you are. Strafe or jump the arrow.",
    "  Mage (staff): slow homing orbs (sidestep late) and runes under your feet "
    "(the screen glows purple: move!).",
    "Shooting an enemy makes it flinch and cancels its attack. Headshots do 2.5x damage.",
    "The radar (top right) points to every enemy. Bigger, brighter dots are closer.",
    "Grapple: hold to throw your hand at a wall or the floor and get pulled to it. "
    "Grab high on a wall to climb.",
    "Al Gore's Tree of Life drops golden apples with random power-ups.",
    "Every 7th wave, Verity arrives, stronger each time.",
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
    def __init__(self, game):
        self.game = game
        self.title_font = pg.font.Font(None, 110)
        self.item_font = pg.font.Font(None, 48)
        self.text_font = pg.font.Font(None, 26)
        self.small_font = pg.font.Font(None, 22)
        self.current = None  # "main", "pause", "help" or None while playing
        self.back_to = None  # where the help screen returns to
        self.sel = 0
        self.page = 0
        self.buttons = []    # (rect, action) of what's on screen, for the mouse

    @property
    def active(self):
        return self.current is not None

    @property
    def title_screen(self):
        """True on the main menu (and its help screen): no game running behind it."""
        return self.current == "main" or (self.current == "help" and self.back_to == "main")

    def open(self, name):
        if name == "help":
            self.back_to, self.page = self.current, 0
        self.current, self.sel = name, 0
        self.game.unlock_mouse()

    def close(self):
        self.current = None
        self.game.lock_mouse()

    def items(self):
        if self.current == "main":
            items = [("PLAY", "play"), ("HELP", "help")]
        elif self.current == "pause":
            items = [("RESUME", "resume"), ("HELP", "help"), ("MAIN MENU", "main")]
        else:
            return []
        return items if WEB else items + [("QUIT", "quit")]  # a web page can't quit

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
            elif ev.key in (pg.K_w, pg.K_UP):
                self.sel = (self.sel - 1) % len(items)
            elif ev.key in (pg.K_s, pg.K_DOWN):
                self.sel = (self.sel + 1) % len(items)
            elif ev.key in (pg.K_RETURN, pg.K_SPACE):
                self.act(items[self.sel][1])
        elif ev.type == pg.MOUSEMOTION:
            for i, (rect, action) in enumerate(self.buttons):
                if rect.collidepoint(ev.pos) and i < len(items):
                    self.sel = i
        elif ev.type == pg.MOUSEBUTTONDOWN and ev.button == 1:
            for rect, action in self.buttons:
                if rect.collidepoint(ev.pos):
                    self.act(action)
                    break

    def act(self, action):
        g = self.game
        if action == "play":
            g.reset()
            self.close()
        elif action == "resume":
            self.close()
        elif action == "help":
            self.open("help")
        elif action == "back":
            self.current, self.sel = self.back_to, 0
        elif action == "main":
            g.reset()
            self.open("main")
        elif action in ("page0", "page1"):
            self.page = int(action[-1])
        elif action == "quit":
            g.quit()

    # --- drawing ---

    def draw(self, win):
        shade = pg.Surface(win.get_size(), pg.SRCALPHA)
        shade.fill((0, 0, 0, 225 if self.current == "help" else 150))
        win.blit(shade, (0, 0))
        self.buttons = []
        if self.current == "help":
            self.draw_help(win)
            return
        cx = win.get_width() // 2
        if self.current == "main":
            self.text(win, self.title_font, "DOOM-ISH", RED, (cx, 150), shadow=True)
            self.text(win, self.text_font, "Wave survival against your friends", GREY, (cx, 215))
            y = 300
        else:
            self.text(win, self.title_font, "PAUSED", RED, (cx, 150), shadow=True)
            self.text(win, self.text_font, f"Wave {self.game.wave}", GREY, (cx, 215))
            y = 270
        for i, (label, action) in enumerate(self.items()):
            selected = i == self.sel
            rect = self.text(win, self.item_font, f"> {label} <" if selected else label,
                             YELLOW if selected else WHITE, (cx, y + i * 55))
            self.buttons.append((rect.inflate(60, 12), action))
        hint = "W/S or mouse to choose, Enter or click to select"
        if self.current == "pause":  # sits above the status bar
            self.text(win, self.small_font, hint + ",  Tab to resume", GREY, (cx, 480))
        else:
            self.text(win, self.small_font, hint, GREY, (cx, win.get_height() - 30))

    def draw_help(self, win):
        w, h = win.get_size()
        self.text(win, self.item_font, "HELP", RED, (w // 2, 38), shadow=True)
        for i, label in enumerate(("CONTROLS", "HOW TO PLAY")):  # tabs
            rect = self.text(win, self.text_font, label, YELLOW if i == self.page else GREY,
                             (w // 2 + (i * 2 - 1) * 110, 82))
            if i == self.page:
                pg.draw.line(win, YELLOW, (rect.left, rect.bottom + 3), (rect.right, rect.bottom + 3), 2)
            self.buttons.append((rect.inflate(30, 16), f"page{i}"))
        y, left = 118, 80
        if self.page == 0:
            for key, what in CONTROLS:
                self.text(win, self.text_font, key, YELLOW, (left, y), anchor="topleft")
                for line in wrap(what, self.text_font, w - 340 - left):
                    self.text(win, self.text_font, line, WHITE, (330, y), anchor="topleft")
                    y += 24
                y += 5
        else:
            for para in HOW_TO_PLAY:
                for line in wrap(para, self.text_font, w - 2 * left):
                    self.text(win, self.text_font, line, WHITE, (left, y), anchor="topleft")
                    y += 23
                y += 7
        rect = self.text(win, self.text_font, "> BACK <", YELLOW, (w // 2, h - 42))
        self.buttons.append((rect.inflate(60, 16), "back"))
        self.text(win, self.small_font, "A/D to switch tabs, Esc to go back", GREY, (w // 2, h - 16))

    @staticmethod
    def text(win, font, s, color, pos, anchor="center", shadow=False):
        img = font.render(s, True, color)
        rect = img.get_rect(**{anchor: pos})
        if shadow:
            win.blit(font.render(s, True, (0, 0, 0)), rect.move(4, 4))
        win.blit(img, rect)
        return rect
