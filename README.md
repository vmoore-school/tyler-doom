# doom-claude

A Doom-style raycaster built with pygame (no other dependencies). Wave survival against your friends, with a Verity boss every 7 waves.

## Run

```
pip install pygame
python main.py
```

A webcam is optional (used for the status-bar face and the death screens).

## Web version

The game also runs in the browser via [pygbag](https://github.com/pygame-web/pygbag) (Python + pygame compiled to WebAssembly):

```
pip install pygbag
python tools/build_web.py --serve   # build and open http://localhost:8000
```

`tools/build_web.py` copies the game into `build/pygbag`, shrinks the photos there (37 MB -> ~2 MB; `assets/` itself is untouched), and builds `build/pygbag/build/web`, a static site. Click the page once to start (browsers need a click before they allow sound and mouse lock); Esc releases the mouse, Tab pauses. No webcam in the browser, so the face is a placeholder.

To publish on GitHub Pages: Settings -> Pages -> Source: GitHub Actions, then run the "Deploy web build" workflow from the Actions tab.

## Controls

| Key | Action |
|---|---|
| WASD / arrows | Move / turn |
| Mouse | Look (left/right and up/down) |
| Left click | Fire |
| 1 / 2 / 3 | Pistol / Shotgun / Tyler Death Beam (after pressing T) |
| T | Enable the Tyler Death Beam for this round (leaderboard entries for the round won't count) |
| Space | Jump |
| Right click / E (hold) | Grapple |
| Middle click / G | Throw David grenade |
| Z / X / C | Answer Verity's quiz |
| R | Restart after dying |
| Tab / Esc | Pause menu |

## Settings

From the main or pause menu:

- **Display**: windowed or fullscreen (fullscreen keeps the 16:10 picture, with black bars if your screen is a different shape). Not in the browser: use F11 there.
- **Resolution**: the 3D view at *Retro* 320x200, *Medium* (half your window/screen resolution) or *Full* (your window/screen resolution). Higher looks sharper but runs slower; the HUD stays pixel art.

Settings are saved to `settings.json` next to `main.py`.

## Gameplay

- Each wave has one more enemy than the last. Clearing it refills health, ammo and grenades.
- Every enemy is one of your friends' faces with one of three fighting styles. Every attack has a wind-up you can see coming, so you can dodge it:
  - **Brawler** (sword): rushes you, raises the sword, then swings. Back off or sidestep during the wind-up. It's slightly slower than you, so you can kite it.
  - **Archer** (bow): keeps its distance and strafes. A glint means it's about to shoot; the arrow flies straight at where you were, so strafe or jump it.
  - **Mage** (staff): alternates a slow homing orb (sidestep it late) with a rune under your feet (the screen glows purple; step out before it erupts). Teleports away if you get close.
  - Hitting an enemy makes it flinch, which cancels its wind-up.
- Headshots do 2.5x damage.
- Al Gore's Tree of Life spawns each wave and drops golden apples with random power-ups.
- Verity appears every 7 waves and gets stronger each time. If he kills you, he eats your brain; anything else gets a normal death screen.
- The radar (top right) shows which direction enemies are in. Up is the way you're facing; closer enemies show as bigger, brighter dots.

## Code layout

| File | Contents |
|---|---|
| `main.py` | Game loop, input, HUD, waves |
| `engine/menus.py` | Main menu, pause menu, help screens |
| `engine/render.py` | Raycaster for walls and sprites |
| `engine/world.py` | Map (`LEVEL`), collision, pathfinding, spawning |
| `engine/entities.py` | Player, `Enemy` base class, roles (`ROLES`), faces (`FACES`), `SPAWN_POOL` |
| `engine/weapons.py` | `Weapon` base class, guns (`WEAPON_TYPES`) |
| `engine/projectiles.py` | Grenades, explosions, enemy arrows/orbs/runes |
| `engine/pickups.py` | Tree of Life, apples, power-ups |
| `engine/boss.py` | Verity, his attacks and minions, death cutscene |
| `engine/grapple.py` | Grapple hook |
| `engine/webcam.py` | Webcam portrait |
| `engine/assets.py` | Generated textures/sounds and photo loading |
| `engine/settings.py` | Resolution, FOV, sensitivity, etc. |
| `tools/build_web.py` | Browser build (pygbag) |

Waves spawn every face combined with every role. To add a fighting style, subclass `Enemy` (set `weapon`, override `think()` for movement and `perform_attack()` for the attack) and add it to `ROLES`. To add a friend, subclass `Friend` with a photo and crop and add it to `FACES`. To add a gun, subclass `Weapon` and add it to `WEAPON_TYPES`.
