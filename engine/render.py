import math
import pygame as pg
from .settings import W, H, FOV, TEX
from .world import cast_ray


class Renderer:
    def __init__(self, wall_textures):
        self.proj = (W / 2) / math.tan(FOV / 2)
        self.ray_angles = [math.atan((x + 0.5 - W / 2) / self.proj) for x in range(W)]
        self.cols = {}
        for tid, tex in wall_textures.items():
            dark = tex.copy()
            dark.fill((160, 160, 160), special_flags=pg.BLEND_RGB_MULT)
            self.cols[tid] = [[s.subsurface((x, 0, 1, TEX)) for x in range(TEX)] for s in (tex, dark)]
        self.bg = pg.Surface((W, H))
        for y in range(H // 2):
            t = y / (H / 2)
            self.bg.fill((int(40 - 25 * t),) * 3, (0, y, W, 1))                 # ceiling
            self.bg.fill((int(25 + 50 * t), int(20 + 35 * t), int(15 + 20 * t)), (0, H - 1 - y, W, 1))  # floor
        self.zbuf = [0.0] * W

    def render(self, screen, world, player):
        screen.blit(self.bg, (0, 0))
        px, py, pa = player.x, player.y, player.angle
        for x, ra in enumerate(self.ray_angles):
            dist, side, tid, wx = cast_ray(world, px, py, pa + ra)
            dist = max(dist * math.cos(ra), 1e-3)
            self.zbuf[x] = dist
            if not tid:
                continue
            col = self.cols.get(tid, self.cols[1])[side][min(TEX - 1, int(wx * TEX))]
            h = int(self.proj / dist)
            if h <= H:
                screen.blit(pg.transform.scale(col, (1, h)), (x, (H - h) // 2))
            else:
                th = max(1, int(TEX * H / h))
                sub = col.subsurface((0, (TEX - th) // 2, 1, th))
                screen.blit(pg.transform.scale(sub, (1, H)), (x, 0))
        self.draw_sprites(screen, world.enemies, player)

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
            size = min(int(self.proj / depth * s.scale), H * 3)
            if size < 1:
                continue
            img = pg.transform.scale(s.image, (size, size))
            cx = W / 2 + math.tan(rel) * self.proj
            left = int(cx - size / 2)
            top = int(H / 2 + self.proj / depth / 2 - size)
            for x in range(max(0, left), min(W, left + size)):
                if depth < self.zbuf[x]:
                    screen.blit(img, (x, top), (x - left, 0, 1, size))
