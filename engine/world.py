import math
from . import entities


def cast_ray(world, ox, oy, ang, max_steps=64):
    """DDA grid traversal. Returns (distance, side, tile_id, wall_x 0..1)."""
    dx, dy = math.cos(ang), math.sin(ang)
    mx, my = int(ox), int(oy)
    ddx = abs(1 / dx) if dx else 1e30
    ddy = abs(1 / dy) if dy else 1e30
    sx, sdx = (-1, (ox - mx) * ddx) if dx < 0 else (1, (mx + 1 - ox) * ddx)
    sy, sdy = (-1, (oy - my) * ddy) if dy < 0 else (1, (my + 1 - oy) * ddy)
    side = t = 0
    for _ in range(max_steps):
        if sdx < sdy:
            sdx += ddx; mx += sx; side = 0
        else:
            sdy += ddy; my += sy; side = 1
        t = world.tile(mx, my)
        if t:
            break
    else:
        return 1e30, 0, 0, 0.0
    if side == 0:
        dist = sdx - ddx
        wx = oy + dist * dy
    else:
        dist = sdy - ddy
        wx = ox + dist * dx
    return dist, side, t, wx - math.floor(wx)


class World:
    """Grid map. Digits = wall texture ids, 'P' = player start,
    other letters = enemy spawns (see entities.ENEMY_TYPES)."""

    def __init__(self, rows):
        self.grid, self.enemies, self.start = [], [], (1.5, 1.5)
        for y, row in enumerate(rows):
            line = []
            for x, ch in enumerate(row):
                line.append(int(ch) if ch.isdigit() else 0)
                if ch == "P":
                    self.start = (x + 0.5, y + 0.5)
                elif ch in entities.ENEMY_TYPES:
                    self.enemies.append(entities.ENEMY_TYPES[ch](x + 0.5, y + 0.5))
            self.grid.append(line)

    def tile(self, x, y):
        if 0 <= y < len(self.grid) and 0 <= x < len(self.grid[y]):
            return self.grid[y][x]
        return 1

    def move(self, e, dx, dy):
        r = e.radius
        if dx and not self.tile(int(e.x + dx + math.copysign(r, dx)), int(e.y)):
            e.x += dx
        if dy and not self.tile(int(e.x), int(e.y + dy + math.copysign(r, dy))):
            e.y += dy

    def line_of_sight(self, ax, ay, bx, by):
        d = math.hypot(bx - ax, by - ay)
        return cast_ray(self, ax, ay, math.atan2(by - ay, bx - ax))[0] > d


LEVEL = [
    "1111111111111111",
    "1P.............1",
    "1..............1",
    "1...22....33...1",
    "1...2......3...1",
    "1.......I......1",
    "1..............1",
    "1...2..B...3...1",
    "1...22....33...1",
    "1......I.......1",
    "1..............1",
    "1111111111111111",
]
