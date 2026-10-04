"""Build the browser version with pygbag.

    python tools/build_web.py           # build into build/pygbag/build/web
    python tools/build_web.py --serve   # build, then serve it at http://localhost:8000

Copies the game into build/pygbag and shrinks the photos there first: the originals are
megapixel images, but the game only ever draws them a few dozen pixels big, and the browser
has to download every byte. assets/ itself is never modified.
"""
import os
import shutil
import subprocess
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame as pg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "build", "pygbag")
MAX_SIDE = 512  # plenty for face crops; held weapons are drawn ~110px tall
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def shrink(src, dst):
    img = pg.image.load(src)
    w, h = img.get_size()
    k = MAX_SIDE / max(w, h)
    rgba = pg.Surface((w, h), pg.SRCALPHA, 32)  # also handles paletted GIFs (colorkey -> alpha)
    rgba.blit(img, (0, 0))
    if k < 1:
        rgba = pg.transform.smoothscale(rgba, (max(1, round(w * k)), max(1, round(h * k))))
    # Everything becomes PNG: the browser's pygame can't read webp, and it picks the decoder
    # from the file extension, so non-PNGs also get a .png name (see stage()).
    pg.image.save(rgba, dst, "png")
    if src.lower().endswith(".png") and os.path.getsize(dst) >= os.path.getsize(src):
        shutil.copy(src, dst)  # already a small PNG


def stage():
    shutil.rmtree(STAGE, ignore_errors=True)
    os.makedirs(STAGE)
    shutil.copy(os.path.join(ROOT, "main.py"), STAGE)
    shutil.copytree(os.path.join(ROOT, "engine"), os.path.join(STAGE, "engine"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    before = after = 0
    renamed = {}
    assets = os.path.join(ROOT, "assets")
    for folder, _, files in sorted(os.walk(assets)):
        for f in sorted(files):
            if os.path.splitext(f)[1].lower() not in IMAGE_EXTS:
                continue
            name = os.path.relpath(os.path.join(folder, f), assets).replace(os.sep, "/")  # e.g. boss/verity.png
            new = name if name.lower().endswith(".png") else name + ".png"
            src, dst = os.path.join(assets, name), os.path.join(STAGE, "assets", new)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shrink(src, dst)
            if new != name:
                renamed[name] = new
            before += os.path.getsize(src)
            after += os.path.getsize(dst)
    print(f"assets: {before / 1e6:.1f} MB -> {after / 1e6:.1f} MB")
    # Point the staged code at the renamed files (only quoted paths, e.g. "other/apple.gif").
    used = set()
    for folder, _, files in os.walk(STAGE):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(folder, f)
                code = open(path, encoding="utf-8").read()
                for old, new in renamed.items():
                    if f'"{old}"' in code:
                        code = code.replace(f'"{old}"', f'"{new}"')
                        used.add(old)
                open(path, "w", encoding="utf-8").write(code)
    for old in sorted(set(renamed) - used):
        print(f"note: assets/{old} isn't referenced by name in the code")


def main():
    pg.init()
    stage()
    args = [sys.executable, "-m", "pygbag", "--title", "Doom-ish", "--no_opt"]
    if "--serve" not in sys.argv:
        args.append("--build")
    args.append(STAGE)
    subprocess.run(args, check=True)
    print("built:", os.path.join(STAGE, "build", "web"))


if __name__ == "__main__":
    main()
