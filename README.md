# doom-claude

A Doom-style raycaster built with pygame (no other dependencies). Wave survival against your friends, with a Verity boss every 7 waves.

## Run

```
pip install pygame
python main.py
```

A webcam is optional (used for the status-bar face and the death screen).

## Controls

| Key | Action |
|---|---|
| WASD / arrows | Move / turn |
| Mouse | Look (left/right and up/down) |
| Left click | Fire |
| 1 / 2 / 3 | Pistol / Shotgun / Tyler Death Beam |
| Space | Jump |
| Right click / E (hold) | Grapple |
| Middle click / G | Throw David grenade |
| Z / X / C | Answer Verity's quiz |
| P | Skip to the next Verity fight |
| R | Restart after dying |
| Esc | Quit |

## Gameplay

- Each wave has one more enemy than the last. Clearing it refills health, ammo and grenades.
- Headshots do 2.5x damage.
- Al Gore's Tree of Life spawns each wave and drops golden apples with random power-ups.
- Verity appears every 7 waves and gets stronger each time.

## Code layout

| File | Contents |
|---|---|
| `main.py` | Game loop, input, HUD, waves |
| `engine/render.py` | Raycaster for walls and sprites |
| `engine/world.py` | Map (`LEVEL`), collision, pathfinding, spawning |
| `engine/entities.py` | Player, `Enemy` base class, enemy types (`SPAWN_POOL`) |
| `engine/weapons.py` | `Weapon` base class, guns (`WEAPON_TYPES`) |
| `engine/projectiles.py` | Grenades, explosions |
| `engine/pickups.py` | Tree of Life, apples, power-ups |
| `engine/boss.py` | Verity, his attacks and minions, death cutscene |
| `engine/grapple.py` | Grapple hook |
| `engine/webcam.py` | Webcam portrait |
| `engine/assets.py` | Generated textures/sounds and photo loading |
| `engine/settings.py` | Resolution, FOV, sensitivity, etc. |

To add an enemy, subclass `Enemy` (or `Friend` for a photo face) and add it to `SPAWN_POOL`. To add a gun, subclass `Weapon` and add it to `WEAPON_TYPES`.
