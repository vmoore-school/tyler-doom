import math
import pygame as pg
from .settings import W, VIEW_H, FOV, TEX, WALL_H

MAX_ERR = 2.5   # how far (pixels) wall edges and texture rows may jump where two wall slices meet
FILL_ERR = 4    # the same, for walls taller than the screen (where only the texture can jump, not the edges)
MIN_SLICE = 3   # narrowest wall slice in pixels (unless the face itself is narrower)
SUB = 8         # wall textures are stretched this many times wider, so slices can end between texels
TW = TEX * SUB
KEY = (255, 0, 255)  # transparent colour of keyed sprites


class Renderer:
    """Draws the 3D view into the top `view_h` rows of a surface `w` pixels wide. The default is
    the retro 320-wide view; bigger sizes are the same picture at a higher resolution.
    `k` is the scale relative to the retro view (pitch is stored in retro pixels).

    Walls aren't drawn column by column (far too much Python per frame at high resolutions, and
    especially in the browser). Instead the view is split into spans of columns that see the same
    face of the same block, and each face is drawn as a few slices: across a flat face, 1/depth
    (and so the wall height) changes linearly with screen x, so neighbouring texels whose heights
    barely differ are scaled and blitted together. A far wall is then a handful of blits and a
    face seen head-on is one."""

    def __init__(self, wall_textures, w=W, view_h=VIEW_H):
        self.w, self.view_h = w, view_h
        self.k = w / W
        self.proj = (w / 2) / math.tan(FOV / 2)
        self.base_proj = self.proj / self.k  # projection in retro pixels, for aiming maths
        # Per pixel column: the ray's sideways offset per unit forward (ray = forward + t * right),
        # so the distance along the ray direction is the perpendicular (no fisheye) distance.
        self.ts = [(i + 0.5 - w / 2) / self.proj for i in range(w)]
        # Textures stacked WALL_H times so tall walls tile instead of stretch; [side][mirrored].
        # Mirrored copies are for faces whose texture runs right-to-left on screen.
        self.tex, self.cols = {}, {}
        for tid, tex in wall_textures.items():
            dark = tex.copy()
            dark.fill((160, 160, 160), special_flags=pg.BLEND_RGB_MULT)
            sides = []
            for t in (tex, dark):
                tall = pg.Surface((TEX, TEX * WALL_H))
                for i in range(WALL_H):
                    tall.blit(t, (0, i * TEX))
                # In the display's format (walls are scaled straight into the view), SUB times wider.
                tall = pg.transform.scale(tall, (TW, TEX * WALL_H)).convert()
                sides.append((tall, pg.transform.flip(tall, True, False)))
            self.tex[tid] = sides
            self.cols[tid] = [[[t.subsurface((x, 0, 1, TEX * WALL_H)) for x in range(TW)] for t in pair]
                              for pair in sides]  # single columns: close walls are mostly these
        # Tall background with the horizon in the middle, shifted by pitch when drawn.
        self.bg = pg.Surface((w, view_h * 3))
        for y in range(view_h * 3 // 2):
            t = max(0.0, 1 - y / (view_h / 2))  # 1 at horizon, 0 from half a screen away
            self.bg.fill((int(40 - 25 * (1 - t)),) * 3, (0, view_h * 3 // 2 - 1 - y, w, 1))  # ceiling
            self.bg.fill((int(75 - 50 * t), int(55 - 35 * t), int(35 - 20 * t)), (0, view_h * 3 // 2 + y, w, 1))  # floor
        self.bg = self.bg.convert()  # the display's pixel format: a plain copy per frame, no conversion
        # Wall depth for sprites: (first column, end column, a, b) with 1/depth = a + b * x.
        self.spans = []
        self._keyed = {}  # id(sprite image) -> (image, its keyed copy or itself)

    def render(self, screen, world, player):
        self.horizon = self.view_h // 2 + int(player.pitch * self.k)
        screen.blit(self.bg, (0, self.horizon - self.view_h * 3 // 2))
        self.draw_walls(screen, world, player)
        self.draw_sprites(screen, world.enemies + world.items + world.projectiles + world.effects, player)

    def find_faces(self, world, player):
        """-> [(first column, end column, (tile, side, mx, my) or None)]: runs of pixel columns
        that see the same face of the same block.

        If the rays through two columns hit the same face, so does every ray between them:
        the wedge between the two rays and the face is narrower than a block, so nothing can
        hide in it without blocking one of the two rays. So the view is walked face by face:
        the face's end on screen is worked out from its corners and checked with a ray just
        before it, and only if something nearer cuts in is the boundary bisected for.
        That's two or three rays per face instead of one per column."""
        px, py = player.x, player.y
        ca, sa = math.cos(player.angle), math.sin(player.angle)
        grid, gw, gh = world.grid, len(world.grid[0]), len(world.grid)
        ts, w, half, proj = self.ts, self.w, self.w / 2, self.proj
        mx0, my0 = int(px), int(py)
        fx0, fy0 = px - mx0, py - my0

        def cast(i):
            t = ts[i]
            dx, dy = ca - t * sa, sa + t * ca
            if dx < 0:
                sx, ddx = -1, -1 / dx
                sdx = fx0 * ddx
            elif dx > 0:
                sx, ddx = 1, 1 / dx
                sdx = (1 - fx0) * ddx
            else:
                sx, ddx, sdx = 1, 1e30, 1e30
            if dy < 0:
                sy, ddy = -1, -1 / dy
                sdy = fy0 * ddy
            elif dy > 0:
                sy, ddy = 1, 1 / dy
                sdy = (1 - fy0) * ddy
            else:
                sy, ddy, sdy = 1, 1e30, 1e30
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
                    return tid, side, mx, my
            return None

        def right_end(face):
            """Screen x where the face's right end is (inf if it runs off the right edge)."""
            _, side, mx, my = face
            if side == 0:
                n0 = mx if px < mx else mx + 1
                ends = ((n0, my), (n0, my + 1))
            else:
                n0 = my if py < my else my + 1
                ends = ((mx, n0), (mx + 1, n0))
            (ax, ay), (bx, by) = ends
            ad, ar = (ax - px) * ca + (ay - py) * sa, (ay - py) * ca - (ax - px) * sa  # depth, rightwards
            bd, br = (bx - px) * ca + (by - py) * sa, (by - py) * ca - (bx - px) * sa
            xs = []
            for d, r, od, orr in ((ad, ar, bd, br), (bd, br, ad, ar)):
                if d > 1e-9:
                    xs.append(half + proj * r / d)
                else:  # behind the eye: the face runs off the screen on the side where it passes the eye
                    xs.append(math.inf if orr + (r - orr) * od / (od - d) > 0 else -math.inf)
            return max(xs)

        faces = []  # (first column, face); each run ends where the next begins
        c, face = 0, cast(0)
        while True:
            if not faces or faces[-1][1] != face:
                faces.append((c, face))
            xr = right_end(face) if face else math.inf
            end = w if xr >= w else min(w, max(c + 1, math.floor(xr - 0.5) + 1))  # first column past it
            last = end - 1
            if last > c:
                hit = cast(last)
                if hit != face:  # something cuts in first: bisect for where (c sees face, hi doesn't)
                    lo, hi = c, last
                    while hi - lo > 1:
                        m = (lo + hi) // 2
                        hm = cast(m)
                        if hm == face:
                            lo = m
                        else:
                            hi, hit = m, hm
                    c, face = hi, hit
                    continue
            if end >= w:
                break
            c, face = end, cast(end)
        return [(c, faces[j + 1][0] if j + 1 < len(faces) else w, f) for j, (c, f) in enumerate(faces)]

    def draw_walls(self, screen, world, player):
        px, py, w = player.x, player.y, self.w
        ca, sa = math.cos(player.angle), math.sin(player.angle)
        proj, horizon, view_h, half = self.proj, self.horizon, self.view_h, self.w / 2
        eye = (WALL_H - 0.5 - player.cam_z) / WALL_H  # fraction of the wall above the eye (eye 0.5 + jump/slide)
        full_h = TEX * WALL_H
        hk = proj * WALL_H  # wall height in pixels = hk / depth
        scale = pg.transform.scale
        tex, cols = self.tex, self.cols
        inv_edge = 1 / max(eye, 1 - eye)  # wall edges are at most height * edge from the horizon
        reach = max(horizon, view_h - horizon, 1)  # ... and so are the rows on screen
        spans = self.spans = []
        for c0, c1, face in self.find_faces(world, player):
            if face is None:
                spans.append((c0, c1, 0.0, 0.0))
                continue
            tid, side, mx, my = face
            # The face lies on the grid line  n = n0  (n = x for side 0, y for side 1); the texture
            # runs along the other axis, m, from the block's edge m0.
            if side == 0:
                dn, fwd_n, fwd_m, rt_n, rt_m, dm0 = (mx if px < mx else mx + 1) - px, ca, sa, -sa, ca, my - py
            else:
                dn, fwd_n, fwd_m, rt_n, rt_m, dm0 = (my if py < my else my + 1) - py, sa, ca, ca, -sa, mx - px
            # The ray through screen x (forward + t * right, t = (x - half) / proj) meets the face
            # at depth dn / (fwd_n + t * rt_n), so 1/depth = a + b * x.
            b = rt_n / (proj * dn)
            a = fwd_n / dn - b * half
            spans.append((c0, c1, a, b))
            # The texture coordinate u (in 1/SUB texels) over depth is linear in x too:
            # u = (al + be * x) / (a + b * x).
            us = []
            for x in (c0, c1):
                t = (x - half) / proj
                us.append((dn * (t * fwd_n - rt_n) / (rt_m - t * fwd_m) - dm0) * TW * (a + b * x))
            be = (us[1] - us[0]) / (c1 - c0)
            al = us[0] - be * c0
            ia, ib = a + b * c0, a + b * c1
            mirrored = us[1] / ib < us[0] / ia
            if mirrored:  # use the mirrored texture so u always increases left to right
                al, be = TW * a - al, TW * b - be
            ua = min(max((al + be * c0) / ia, 0.0), TW)
            ub = min(max((al + be * c1) / ib, ua), TW)
            src = tex.get(tid, tex[1])[side][mirrored]
            src_cols = cols.get(tid, cols[1])[side][mirrored]
            # Each slice is drawn at the height of its middle, so where two slices meet, the wall
            # jumps by (their height difference) * |y - horizon| / height at screen row y. Slices
            # are made as wide as keeps that under MAX_ERR pixels on the visible rows: those are
            # within height * edge and reach of the horizon, so the width is
            # MAX_ERR / (height change per pixel) * max(1 / edge, height / reach).
            dh = abs(hk * b)
            k_err = MAX_ERR / dh if dh else 1e9
            step_min = max(k_err * inv_edge, MIN_SLICE)
            k_fill = FILL_ERR / dh * hk / reach if dh else 1e9
            sa_, sb_ = k_fill * a, k_fill * b  # step allowed by height: sa_ + sb_ * x
            ha, hb = hk * a, hk * b * 0.5  # height in the middle of columns xi..xei: ha + hb * (xi + xei)
            x, u, xi = float(c0), ua, c0
            while xi < c1:
                xt = sa_ + sb_ * x
                xt = x + (xt if xt > step_min else step_min)
                ut = ub if xt >= c1 else (al + be * xt) / (a + b * xt)
                ui = int(u)
                if u != ui:  # starting partway into a (sub-)texel: don't cross into the next
                    ue = ut if ut < ui + 1 else ui + 1.0
                elif ut >= ui + 1:  # end on the nearest boundary, so the slice shows whole ones
                    ue = float(int(ut + 0.5))
                else:
                    ue = ut
                if ue >= ub:
                    xe, ue, xei = c1, ub, c1
                else:
                    xe = (al - ue * a) / (ue * b - be)
                    if not x < xe:  # numerical trouble: take the minimum slice
                        xe = min(c1, x + MIN_SLICE)
                        ue = ub if xe >= c1 else (al + be * xe) / (a + b * xe)
                    xei = c1 if xe >= c1 else int(xe + 0.5)
                if xei > xi:
                    s0 = ui if ui < TW else TW - 1
                    s1 = -int(-ue)  # ceil
                    if s1 <= s0:
                        s1 = s0 + 1
                    elif s1 > TW:
                        s1 = TW
                    hm = ha + hb * (xi + xei)
                    hi = int(hm) or 1
                    topi = int(horizon - hm * eye)
                    if topi >= 0 and topi + hi <= view_h:
                        part = src_cols[s0] if s1 - s0 == 1 else src.subsurface((s0, 0, s1 - s0, full_h))
                        scale(part, (xei - xi, hi), screen.subsurface((xi, topi, xei - xi, hi)))
                    else:  # partly off screen (close walls): scale only the visible rows
                        vis_top = topi if topi > 0 else 0
                        vis_bot = topi + hi if topi + hi < view_h else view_h
                        if vis_bot > vis_top:
                            t0 = int((vis_top - topi) * full_h / hi)
                            t1 = min(full_h, max(t0 + 1, math.ceil((vis_bot - topi) * full_h / hi)))
                            scale(src.subsurface((s0, t0, s1 - s0, t1 - t0)), (xei - xi, vis_bot - vis_top),
                                  screen.subsurface((xi, vis_top, xei - xi, vis_bot - vis_top)))
                    xi = xei
                x, u = xe, ue

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
            left = self.w / 2 + math.tan(rel) * self.proj - size / 2
            z = getattr(s, "z", 0.0)  # height of the sprite's bottom above the floor
            top = self.horizon + self.proj / depth * (0.5 + player.cam_z - z) - size
            x0, x1 = max(0, math.ceil(left)), min(self.w, math.ceil(left + size))
            if x1 <= x0 or top >= self.view_h or top + size <= 0:
                continue
            img = self.keyed(s.image)
            for a, b in self.visible_runs(x0, x1, 1 / depth):
                self.blit_scaled(screen, img, left, top, size, size, a, b)

    def keyed(self, img):
        """A colour-keyed copy of a sprite whose transparency is (nearly) all-or-nothing, else the
        sprite itself. Close-up sprites cover a lot of the screen, and blending per-pixel alpha
        costs several times more than skipping key-coloured pixels (in the browser especially)."""
        hit = self._keyed.get(id(img))
        if hit is None or hit[0] is not img:
            visible = pg.mask.from_surface(img, 0).count()
            half = pg.mask.from_surface(img, 127)
            soft = visible - pg.mask.from_surface(img, 254).count()  # partly transparent pixels
            out = img
            if img.get_flags() & pg.SRCALPHA and visible and soft <= visible * 0.15:
                # to_surface needs its target in the same pixel format as setsurface, and some
                # images (in the browser build especially) aren't in its default format: draw into
                # a copy of the sprite itself. If pygame still refuses, just use the sprite as is.
                try:
                    out = half.to_surface(img.copy(), setsurface=img, unsetcolor=KEY).convert()
                    out.set_colorkey(KEY)
                except ValueError:
                    out = img
            if len(self._keyed) > 1000:
                self._keyed.clear()
            hit = self._keyed[id(img)] = (img, out)  # holding img keeps its id from being reused
        return hit[1]

    def visible_runs(self, x0, x1, inv_depth):
        """Runs of columns in [x0, x1) where the wall is farther away than 1/inv_depth."""
        runs = []
        for c0, c1, a, b in self.spans:
            if c1 <= x0 or c0 >= x1:
                continue
            lo, hi = max(c0, x0), min(c1, x1)
            # Columns i (centre i + 0.5) with a + b*(i + 0.5) < inv_depth.
            if b > 0:
                hi = min(hi, math.ceil((inv_depth - a) / b - 0.5))
            elif b < 0:
                lo = max(lo, math.floor((inv_depth - a) / b - 0.5) + 1)
            elif a >= inv_depth:
                continue
            if hi > lo:
                if runs and runs[-1][1] == lo:
                    runs[-1] = (runs[-1][0], hi)
                else:
                    runs.append((lo, hi))
        return runs

    def blit_scaled(self, screen, img, left, top, w, h, x0, x1):
        """Draw `img` scaled to (w, h) at (left, top), but only columns x0..x1 and the rows inside
        the view: just the source pixels that cover that area are scaled, so huge close-up
        sprites stay cheap."""
        iw, ih = img.get_size()
        y0, y1 = max(0, math.ceil(top)), min(self.view_h, math.ceil(top + h))
        if y1 <= y0:
            return
        kx, ky = iw / w, ih / h  # source pixels per screen pixel
        s0 = max(0, int((x0 - left) * kx))
        s1 = min(iw, math.ceil((x1 - left) * kx) + 1)
        r0 = max(0, int((y0 - top) * ky))
        r1 = min(ih, math.ceil((y1 - top) * ky) + 1)
        # Scale that source rectangle to its exact on-screen size, then clip to the area.
        dx0, dy0 = left + s0 / kx, top + r0 / ky
        sw, sh = round((s1 - s0) / kx), round((r1 - r0) / ky)
        if sw < 1 or sh < 1:
            return
        part = pg.transform.scale(img.subsurface((s0, r0, s1 - s0, r1 - r0)), (sw, sh))
        if img.get_colorkey():
            part.set_colorkey(KEY)
        ox, oy = round(dx0), round(dy0)
        screen.blit(part, (x0, y0), (x0 - ox, y0 - oy, x1 - x0, y1 - y0))
