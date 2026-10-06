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
| 1 / 2 / 3 / 4 | Fist (melee) / Pistol / Shotgun (unlocks at wave 7) / Assault rifle (unlocks at wave 21) |
| Scroll wheel | Next / previous unlocked weapon |
| R | Reload (restart after dying) |
| T | Tyler Death Beam on/off (using it means the round's leaderboard entry won't count) |
| Space | Jump |
| Shift (hold) | Sprint |
| Ctrl / double-tap a direction | Slide (Ctrl slides the way you're moving; steer with WASD). In mid-air it's a dive |
| Right click / E (hold) | Grapple |
| Middle click / G / Q | Throw David grenade |
| Z / X / C | Answer Verity's quiz |
| Tab / Esc | Pause menu |

## Settings

From the main or pause menu:

- **Display**: windowed or fullscreen (fullscreen keeps the 16:10 picture, with black bars if your screen is a different shape). Not in the browser: use F11 there.
- **Resolution**: the 3D view at *Retro* 320x200, *Medium* (half your window/screen resolution) or *Full* (your window/screen resolution; in the browser, the page's own pixel size). Higher looks sharper but runs slower; the HUD stays pixel art.

Settings are saved to `settings.json` next to `main.py`.

## Leaderboard

A global leaderboard ranks runs by the highest wave reached, then kills. When you die after a valid run, the
death screen asks for a name (Enter submits, Esc skips). Rounds where the Tyler Death Beam was enabled (T) aren't
submitted. View it from **Leaderboard** in the main or pause menu.

Scores are stored in a free [Supabase](https://supabase.com) project. To set one up:

1. Create a project, open the **SQL Editor** and run:

   ```sql
   create table public.scores (
     id         bigint generated always as identity primary key,
     name       text not null check (char_length(btrim(name)) between 1 and 12 and name = upper(name)),
     wave       int  not null check (wave between 1 and 500),
     kills      int  not null check (kills >= 0 and kills <= wave * (wave + 5) / 2 + 100),
     created_at timestamptz not null default now()
   );
   create index scores_rank on public.scores (wave desc, kills desc, created_at);
   alter table public.scores enable row level security;
   create policy "anyone can read" on public.scores for select to anon using (true);
   create policy "anyone can add"  on public.scores for insert to anon with check (true);
   -- no update/delete policies: only you (in the dashboard) can edit or remove scores
   ```

2. From **Project Settings -> API**, copy the Project URL and the **anon / publishable** key into
   `engine/leaderboard_config.py`.

The anon key is public by design: it ships inside the web page, and the Row Level Security rules above limit it
to reading scores and adding sane-looking ones. **Never** put the `service_role` / secret key in the game or the repo.
Since the game is open source, someone determined could still post a fake score by hand; delete junk rows from
the Supabase dashboard (Table Editor). Free projects pause after about a week without activity; resume from
the dashboard.

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
| `engine/menus.py` | Main, pause, settings, leaderboard and help screens |
| `engine/leaderboard.py` | Leaderboard client (Supabase REST; uses the page's `fetch` in the browser) |
| `engine/leaderboard_config.py` | Supabase project URL + anon key |
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

Waves spawn every face combined with every role. To add a fighting style, subclass `Enemy` (set `weapon`, override `think()` for movement and `perform_attack()` for the attack) and add it to `ROLES`. To add a friend, subclass `Friend` with a photo and crop and add it to `FACES`. To add a gun, subclass `Weapon` (set `clip`, `reload_time` and `unlock_wave`) and add it to `WEAPON_TYPES`.
