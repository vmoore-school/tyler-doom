import math
import pygame as pg
from .settings import W, VIEW_H, FOV, TEX
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
            h = max(1, int(self.proj / dist))
            top = self.horizon - h // 2
            vis_top, vis_bot = max(0, top), min(VIEW_H, top + h)
            if vis_bot <= vis_top:
                continue
            if h <= VIEW_H:
                screen.blit(pg.transform.scale(col, (1, h)), (x, top))
            else:  # crop the texture to the visible part before scaling
                t0 = int((vis_top - top) * TEX / h)
                t1 = min(TEX, max(t0 + 1, math.ceil((vis_bot - top) * TEX / h)))
                sub = col.subsurface((0, t0, 1, t1 - t0))
                screen.blit(pg.transform.scale(sub, (1, vis_bot - vis_top)), (x, vis_top))
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
            size = min(int(self.proj / depth * s.scale), VIEW_H * 3)
            if size < 1:
                continue
            img = pg.transform.scale(s.image, (size, size))
            cx = W / 2 + math.tan(rel) * self.proj
            left = int(cx - size / 2)
            z = getattr(s, "z", 0.0)  # height of the sprite's bottom above the floor
            top = int(self.horizon + self.proj / depth * (0.5 - z) - size)
            for x in range(max(0, left), min(W, left + size)):
                if depth < self.zbuf[x]:
                    screen.blit(img, (x, top), (x - left, 0, 1, size))
