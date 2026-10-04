import math
import pygame as pg
from .settings import W, VIEW_H, FOV, TEX, WALL_H
from .world import cast_ray


class Renderer:
    """Draws the 3D view into the top `view_h` rows of a surface `w` pixels wide. The default is
    the retro 320-wide view; bigger sizes are the same picture at a higher resolution.
    `k` is the scale relative to the retro view (pitch is stored in retro pixels)."""

    def __init__(self, wall_textures, w=W, view_h=VIEW_H):
        self.w, self.view_h = w, view_h
        self.k = w / W
        self.proj = (w / 2) / math.tan(FOV / 2)
        self.base_proj = self.proj / self.k  # projection in retro pixels, for aiming maths
        # Walls are drawn in strips `cw` pixels wide: at least 480 across, which is finer than the
        # 64px wall textures need even at full resolution, and keeps the per-strip Python work bounded.
        self.cw = max(1, w // 480)
        self.nrays = math.ceil(w / self.cw)
        self.ray_angles = [math.atan((i * self.cw + self.cw / 2 - w / 2) / self.proj) for i in range(self.nrays)]
        # Per-strip ray direction relative to the view (cos/sin of its angle): the actual ray is
        # this rotated by the player's angle, which saves trig per strip.
        self.ray_cs = [(math.cos(a), math.sin(a)) for a in self.ray_angles]
        self.ray_step = 1 if self.k <= 1 else 4  # full DDA every this many strips (see draw_walls)
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
        self.bg = pg.Surface((w, view_h * 3))
        for y in range(view_h * 3 // 2):
            t = max(0.0, 1 - y / (view_h / 2))  # 1 at horizon, 0 from half a screen away
            self.bg.fill((int(40 - 25 * (1 - t)),) * 3, (0, view_h * 3 // 2 - 1 - y, w, 1))  # ceiling
            self.bg.fill((int(75 - 50 * t), int(55 - 35 * t), int(35 - 20 * t)), (0, view_h * 3 // 2 + y, w, 1))  # floor
        self.zbuf = [0.0] * self.nrays  # wall distance per strip (sprites look up x // cw)

    def render(self, screen, world, player):
        self.horizon = self.view_h // 2 + int(player.pitch * self.k)
        screen.blit(self.bg, (0, self.horizon - self.view_h * 3 // 2))
        self.draw_walls(screen, world, player)
        self.draw_sprites(screen, world.enemies + world.items + world.projectiles + world.effects, player)

    def draw_walls(self, screen, world, player):
        """One wall column per screen column. Rays are DDA-cast through the grid only every
        `ray_step` columns; when the two rays either side of a gap hit the same face of the same
        block, the columns between hit it too, so they're solved directly against that flat face
        instead of re-walking the grid (the hottest loop in the game). Columns are blitted in one batch."""
        px, py = player.x, player.y
        ca, sa = math.cos(player.angle), math.sin(player.angle)
        grid, gw, gh = world.grid, len(world.grid[0]), len(world.grid)
        rays = self.ray_cs
        n = len(rays)
        mx0, my0 = int(px), int(py)

        def cast(x):
            """-> (tile, side, mx, my, distance along the ray, wall_x 0..1) or None."""
            cr, sr = rays[x]
            dx, dy = ca * cr - sa * sr, sa * cr + ca * sr
            ddx = abs(1 / dx) if dx else 1e30
            ddy = abs(1 / dy) if dy else 1e30
            if dx < 0:
                sx, sdx = -1, (px - mx0) * ddx
            else:
                sx, sdx = 1, (mx0 + 1 - px) * ddx
            if dy < 0:
                sy, sdy = -1, (py - my0) * ddy
            else:
                sy, sdy = 1, (my0 + 1 - py) * ddy
            mx, my = mx0, my0
            for _ in range(64):
                if sdx < sdy:
                    sdx += ddx
                    mx += sx
                    side = 0
                else:
                    sdy += ddy
                    my += sy
                    side = 1
                tid = grid[my][mx] if 0 <= mx < gw and 0 <= my < gh else 1
                if tid:
                    if side == 0:
                        dist = sdx - ddx
                        wx = py + dist * dy
                    else:
                        dist = sdy - ddy
                        wx = px + dist * dx
                    return tid, side, mx, my, dist, wx - math.floor(wx)
            return None

        hits = [None] * n
        step = self.ray_step
        anchors = list(range(0, n, step))
        if anchors[-1] != n - 1:
            anchors.append(n - 1)
        for x in anchors:
            hits[x] = cast(x)
        for a, b in zip(anchors, anchors[1:]):
            ha, hb = hits[a], hits[b]
            if ha and hb and ha[:4] == hb[:4]:  # same block, same face
                tid, side, mx, my = ha[:4]
                for x in range(a + 1, b):
                    cr, sr = rays[x]
                    dx, dy = ca * cr - sa * sr, sa * cr + ca * sr
                    if side == 0 and dx:
                        dist = ((mx if dx > 0 else mx + 1) - px) / dx
                        wx = py + dist * dy
                    elif side == 1 and dy:
                        dist = ((my if dy > 0 else my + 1) - py) / dy
                        wx = px + dist * dx
                    else:
                        dist = -1
                    hits[x] = (tid, side, mx, my, dist, wx - math.floor(wx)) if dist > 0 else cast(x)
            else:
                for x in range(a + 1, b):
                    hits[x] = cast(x)

        cols, default_cols = self.cols, self.cols[1]
        proj, horizon, view_h, zbuf, cw = self.proj, self.horizon, self.view_h, self.zbuf, self.cw
        eye_above = WALL_H - 0.5 - player.z  # wall top above the eye (eye height 0.5 + jump)
        scale = pg.transform.scale
        batch = []
        append = batch.append
        for i, hit in enumerate(hits):
            if hit is None:
                zbuf[i] = 1e30
                continue
            x = i * cw
            tid, side, _, _, dist, wx = hit
            dist *= rays[i][0]  # perpendicular distance: no fisheye
            if dist < 1e-3:
                dist = 1e-3
            zbuf[i] = dist
            tx = int(wx * TEX)
            col = cols.get(tid, default_cols)[side][tx if tx < TEX else TEX - 1]
            unit = proj / dist  # pixels per world unit at this distance
            h = int(unit * WALL_H) or 1
            top = horizon - int(unit * eye_above)
            if top >= 0 and top + h <= view_h:
                append((scale(col, (cw, h)), (x, top)))
            else:  # partly off screen (close walls): scale only the visible part
                vis_top, vis_bot = max(0, top), min(view_h, top + h)
                if vis_bot <= vis_top:
                    continue
                ch = col.get_height()
                t0 = int((vis_top - top) * ch / h)
                t1 = min(ch, max(t0 + 1, math.ceil((vis_bot - top) * ch / h)))
                append((scale(col.subsurface((0, t0, 1, t1 - t0)), (cw, vis_bot - vis_top)), (x, vis_top)))
        screen.blits(batch, doreturn=False)

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
            left = self.w / 2 + math.tan(rel) * self.proj - size / 2
            z = getattr(s, "z", 0.0)  # height of the sprite's bottom above the floor
            top = int(self.horizon + self.proj / depth * (0.5 + player.z - z) - size)
            x0, x1 = max(0, math.ceil(left)), min(self.w, math.ceil(left + size))
            if x1 <= x0 or top >= self.view_h or top + int(size) <= 0:
                continue
            # Runs of columns where the sprite is in front of the walls.
            zbuf, cw, runs, start = self.zbuf, self.cw, [], None
            for x in range(x0, x1):
                if depth < zbuf[x // cw]:
                    if start is None:
                        start = x
                elif start is not None:
                    runs.append((start, x))
                    start = None
            if start is not None:
                runs.append((start, x1))
            if not runs:
                continue
            isize = int(size)
            if isize <= self.view_h * 2:
                # Scale the whole sprite once and blit the visible strips of it.
                scaled = pg.transform.scale(img, (isize, isize))
                for a, b in runs:
                    sx = int(a - left)
                    screen.blit(scaled, (a, top), (min(sx, isize - 1), 0, b - a, isize))
            else:  # huge (right in your face): column by column, cropped to the view
                for a, b in runs:
                    for x in range(a, b):
                        sx = max(0, min(iw - 1, int((x - left) / size * iw)))
                        self.blit_column(screen, img.subsurface((sx, 0, 1, img.get_height())), x, top, isize)

    def blit_column(self, screen, col, x, top, h):
        """Scale a 1px-wide column to height h at (x, top), cropping to the view first
        so huge close-up walls/sprites stay cheap and undistorted."""
        if h < 1:
            return
        vis_top, vis_bot = max(0, top), min(self.view_h, top + h)
        if vis_bot <= vis_top:
            return
        ch = col.get_height()
        if vis_top == top and vis_bot == top + h:
            screen.blit(pg.transform.scale(col, (1, h)), (x, top))
            return
        t0 = int((vis_top - top) * ch / h)
        t1 = min(ch, max(t0 + 1, math.ceil((vis_bot - top) * ch / h)))
        screen.blit(pg.transform.scale(col.subsurface((0, t0, 1, t1 - t0)), (1, vis_bot - vis_top)), (x, vis_top))
