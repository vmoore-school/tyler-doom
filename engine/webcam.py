"""Doom-style status bar portrait fed by the webcam (pygame.camera).
Falls back to a placeholder if no camera is available."""
import math
import threading
import pygame as pg
import pygame.camera


class WebcamPortrait:
    def __init__(self, size=(30, 30), cam_res=(160, 120)):
        self.size = size
        self.frame = self.big_frame = None
        self.cam = None
        self.running = False
        try:
            pygame.camera.init()
            devices = pygame.camera.list_cameras()
            if devices:
                self.cam = pygame.camera.Camera(devices[0], cam_res)
                self.cam.start()
                self.running = True
                # Grab frames on a thread so a slow camera never stalls the game loop.
                threading.Thread(target=self._capture, daemon=True).start()
        except Exception as e:  # no camera / permission denied / unsupported backend
            print("webcam unavailable:", e)
            self.cam = None

    def _capture(self):
        while self.running:
            try:
                img = self.cam.get_image()
            except Exception:
                break
            w, h = img.get_size()
            side = min(w, h)  # centre square crop, mirrored like a selfie
            crop = img.subsurface(((w - side) // 2, (h - side) // 2, side, side))
            self.frame = pg.transform.flip(pg.transform.smoothscale(crop, self.size), True, False)
            self.big_frame = pg.transform.flip(pg.transform.smoothscale(crop, (120, 120)), True, False)

    def stop(self):
        self.running = False
        if self.cam:
            try:
                self.cam.stop()
            except Exception:
                pass

    def snapshot(self):
        """Larger still of the player's face (or a stand-in head) for the death cutscene."""
        if self.big_frame is not None:
            return self.big_frame.copy()
        s = pg.Surface((120, 120))
        s.fill((40, 30, 30))
        pg.draw.circle(s, (200, 150, 120), (60, 64), 46)
        for x in (44, 76):
            pg.draw.circle(s, (255, 255, 255), (x, 58), 8)
            pg.draw.circle(s, (0, 0, 0), (x, 58), 4)
        pg.draw.arc(s, (120, 40, 40), (40, 70, 40, 22), math.pi, 2 * math.pi, 3)
        return s

    def render(self, health, hurt_flash, dead):
        """Portrait with Doom-ish damage effects: bloodier as health drops."""
        if self.frame is None:
            out = pg.Surface(self.size)
            out.fill((40, 30, 30))
            pg.draw.circle(out, (150, 110, 90), (self.size[0] // 2, self.size[1] // 2), self.size[0] // 3)
            return out
        out = self.frame.copy()
        if dead:
            out.fill((140, 30, 30), special_flags=pg.BLEND_RGB_MULT)
            return out
        red = int((1 - health / 100) * 140 + hurt_flash * 300)
        if red > 0:
            out.fill((min(255, red), 0, 0), special_flags=pg.BLEND_RGB_ADD)
            out.fill((255, max(80, 255 - red), max(80, 255 - red)), special_flags=pg.BLEND_RGB_MULT)
        return out
