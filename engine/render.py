import math
import pygame as pg
from .settings import W, VIEW_H, FOV, TEX, WALL_H
from .world import cast_ray


class Renderer:
    def __init__(self, wall_textures):
        self.proj = (W / 2) / math.tan(FOV / 2)
        self.ray_angles = [math.atan((x + 0.5 - W / 2) / self.proj) for x in range(W)]
        self.cols = {}
        for tid, tex in wall_textures.items():
            dark = tex.copy()
            dark.fill((160, 160, 160), special_flags=pg.BLEND_RGB_MULT)
            cols = []
            for t in (tex, dark):  # stack the texture WALL_H times so tall walls tile instead of stretch
                tall = pg.Surface((TEX, TEX * WALL_H))
                for i in range(WALL_H):
                    tall.blit(t, (0, i * TEX))
                cols.append([tall.subsurface((x, 0, 1, TEX * WALL_H)) for x in range(TEX)])
            self.cols[tid] = cols
        # Tall background with the horizon in the middle, shifted by pitch when drawn.
        self.bg = pg.Surface((W, VIEW_H * 3))
        for y in range(VIEW_H * 3 // 2):
            t = max(0.0, 1 - y / (VIEW_H / 2))  # 1 at horizon, 0 from half a screen away
            self.bg.fill((int(40 - 25 * (1 - t)),) * 3, (0, VIEW_H * 3 // 2 - 1 - y, W, 1))  # ceiling
            self.bg.fill((int(75 - 50 * t), int(55 - 35 * t), int(35 - 20 * t)), (0, VIEW_H * 3 // 2 + y, W, 1))  # floor
        self.zbuf = [0.0] * W

    def render(self, screen, world, player):
        self.horizon = VIEW_H // 2 + int(player.pitch)
        screen.blit(self.bg, (0, self.horizon - VIEW_H * 3 // 2))
        px, py, pa = player.x, player.y, player.angle
        for x, ra in enumerate(self.ray_angles):
            dist, side, tid, wx = cast_ray(world, px, py, pa + ra)
            dist = max(dist * math.cos(ra), 1e-3)
            self.zbuf[x] = dist
            if not tid:
                continue
            col = self.cols.get(tid, self.cols[1])[side][min(TEX - 1, int(wx * TEX))]
            unit = self.proj / dist  # pixels per world unit at this distance
            h = max(1, int(unit * WALL_H))
            top = self.horizon - int(unit * (WALL_H - 0.5 - player.z))  # eye height 0.5 + jump
            self.blit_column(screen, col, x, top, h)
        self.draw_sprites(screen, world.enemies + world.items + world.projectiles + world.effects, player)

    def draw_sprites(self, screen, sprites, player):
        px, py, pa = player.x, player.y, player.angle
        visible = []
        for s in sprites:
            dx, dy = s.x - px, s.y - py
            rel = (math.atan2(dy, dx) - pa + math.pi) % (2 * math.pi) - math.pi
            depth = math.hypot(dx, dy) * math.cos(rel)
            if depth > 0.2 and abs(rel) < FOV:
                visible.append((depth, rel, s))
        for depth, rel, s in sorted(visible, key=lambda v: -v[0]):
            size = self.proj / depth * s.scale
            if size < 1:
                continue
            img = s.image
            iw = img.get_width()
            left = W / 2 + math.tan(rel) * self.proj - size / 2
            z = getattr(s, "z", 0.0)  # height of the sprite's bottom above the floor
            top = int(self.horizon + self.proj / depth * (0.5 + player.z - z) - size)
            for x in range(max(0, math.ceil(left)), min(W, math.ceil(left + size))):
                if depth < self.zbuf[x]:
                    sx = max(0, min(iw - 1, int((x - left) / size * iw)))
                    self.blit_column(screen, img.subsurface((sx, 0, 1, img.get_height())), x, top, int(size))

    @staticmethod
    def blit_column(screen, col, x, top, h):
        """Scale a 1px-wide column to height h at (x, top), cropping to the view first
        so huge close-up walls/sprites stay cheap and undistorted."""
        if h < 1:
            return
        vis_top, vis_bot = max(0, top), min(VIEW_H, top + h)
        if vis_bot <= vis_top:
            return
        ch = col.get_height()
        if vis_top == top and vis_bot == top + h:
            screen.blit(pg.transform.scale(col, (1, h)), (x, top))
            return
        t0 = int((vis_top - top) * ch / h)
        t1 = min(ch, max(t0 + 1, math.ceil((vis_bot - top) * ch / h)))
        screen.blit(pg.transform.scale(col.subsurface((0, t0, 1, t1 - t0)), (1, vis_bot - vis_top)), (x, vis_top))
