import math
import random
from collections import deque
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
        self.projectiles, self.effects, self.items = [], [], []
        self.flow, self._flow_src = {}, None
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

    def update_flow(self, target):
        """BFS distance field from the target's tile, so enemies can path around walls."""
        src = (int(target.x), int(target.y))
        if src == self._flow_src:
            return
        self._flow_src, self.flow = src, {src: 0}
        q = deque([src])
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) not in self.flow and not self.tile(nx, ny):
                    self.flow[(nx, ny)] = self.flow[(x, y)] + 1
                    q.append((nx, ny))

    def next_step(self, x, y):
        """Centre of the neighbouring tile that is one step closer to the flow target."""
        tx, ty = int(x), int(y)
        best = min(((tx + 1, ty), (tx - 1, ty), (tx, ty + 1), (tx, ty - 1)),
                   key=lambda t: self.flow.get(t, 1e9))
        if self.flow.get(best, 1e9) >= self.flow.get((tx, ty), 1e9):
            return None
        return best[0] + 0.5, best[1] + 0.5

    def free_tiles(self, player, min_dist):
        return [(x + 0.5, y + 0.5) for y, row in enumerate(self.grid) for x, t in enumerate(row)
                if not t and math.hypot(x + 0.5 - player.x, y + 0.5 - player.y) >= min_dist]

    def spawn_tree(self, player):
        """Replace the Tree of Life with a new one somewhere random (apples on the floor stay)."""
        from .pickups import TreeOfLife
        self.items = [i for i in self.items if not isinstance(i, TreeOfLife)]
        self.items.append(TreeOfLife(*random.choice(self.free_tiles(player, 6.0))))

    def spawn_wave(self, count, player, min_dist=8.0):
        """Spawn `count` random enemies on empty tiles away from the player."""
        tiles = self.free_tiles(player, min_dist)
        for x, y in random.sample(tiles, min(count, len(tiles))):
            e = random.choice(entities.SPAWN_POOL)(x, y)
            e.state = "chase"  # wave enemies hunt the player
            self.enemies.append(e)

    def line_of_sight(self, ax, ay, bx, by):
        d = math.hypot(bx - ax, by - ay)
        return cast_ray(self, ax, ay, math.atan2(by - ay, bx - ax))[0] > d


LEVEL = [
    "11111111111111111111111111111111",
    "1P.....1..........1............1",
    "1......1..........1............1",
    "1......1...2..2...1....3333....1",
    "1..............................1",
    "1......1...2..2...1....3..3....1",
    "1......1..........1....3..3....1",
    "1111.1111111..11111....3..3....1",
    "1..............1...............1",
    "1..............1.......3333....1",
    "1...22....22...1...............1",
    "1...2......2...111111..111111111",
    "1..............................1",
    "1...2......2...1...............1",
    "1...22....22...1...33.....33...1",
    "1..............1...3.......3...1",
    "1111111..111111111.............1",
    "1..............1...3.......3...1",
    "1..333.........1...33.....33...1",
    "1..3...........................1",
    "1..3....2222...1...............1",
    "1..............1.......2.......1",
    "1..............1...............1",
    "11111111111111111111111111111111",
]
