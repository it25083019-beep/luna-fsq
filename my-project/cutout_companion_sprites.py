# -*- coding: utf-8 -*-
"""Make companion expression PNGs true RGBA cutouts like Luna (no plate, no sticker rim)."""
from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent / "static" / "live2d"
SKIP = {"luna-expressions"}


def _corners(im: Image.Image):
    w, h = im.size
    px = im.load()
    return [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]


def _avg_rgb(colors):
    n = max(1, len(colors))
    return (
        sum(c[0] for c in colors) / n,
        sum(c[1] for c in colors) / n,
        sum(c[2] for c in colors) / n,
    )


def _near(c, target, tol):
    return abs(c[0] - target[0]) <= tol and abs(c[1] - target[1]) <= tol and abs(c[2] - target[2]) <= tol


def _flood_transparent(im: Image.Image, target, tol: int) -> None:
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    q = deque()

    def push(x, y):
        if 0 <= x < w and 0 <= y < h and not seen[y * w + x]:
            q.append((x, y))
            seen[y * w + x] = 1

    for x in range(w):
        push(x, 0)
        push(x, h - 1)
    for y in range(h):
        push(0, y)
        push(w - 1, y)

    while q:
        x, y = q.popleft()
        r, g, b, a = px[x, y]
        if a == 0:
            continue
        if not _near((r, g, b), target, tol):
            continue
        px[x, y] = (r, g, b, 0)
        push(x + 1, y)
        push(x - 1, y)
        push(x, y + 1)
        push(x, y - 1)


def _eat_white_rim(im: Image.Image, rounds: int = 10, white: int = 232) -> None:
    """Eat the sticker-style white halo that sits against transparent pixels."""
    w, h = im.size
    px = im.load()
    for _ in range(rounds):
        victims = []
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a == 0:
                    continue
                if r < white or g < white or b < white:
                    continue
                edge = False
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if nx < 0 or ny < 0 or nx >= w or ny >= h:
                        edge = True
                        break
                    if px[nx, ny][3] == 0:
                        edge = True
                        break
                if edge:
                    victims.append((x, y))
        if not victims:
            break
        for x, y in victims:
            r, g, b, _ = px[x, y]
            px[x, y] = (r, g, b, 0)


def cutout(path: Path) -> str:
    im = Image.open(path).convert("RGBA")
    corners = _corners(im)
    # Already a cutout like Luna.
    if sum(1 for c in corners if c[3] < 10) >= 3:
        return "skip-already-alpha"
    avg = _avg_rgb(corners)
    if avg[0] < 40 and avg[1] < 40 and avg[2] < 40:
        _flood_transparent(im, (0, 0, 0), tol=28)
        _eat_white_rim(im, rounds=12, white=228)
        kind = "black-plate"
    else:
        _flood_transparent(im, (255, 255, 255), tol=22)
        # grey checker / off-white plates
        _flood_transparent(im, (230, 230, 230), tol=18)
        _eat_white_rim(im, rounds=8, white=240)
        kind = "white-plate"
    im.save(path, "PNG")
    return kind


def main() -> None:
    n = 0
    for folder in sorted(ROOT.iterdir()):
        if not folder.is_dir() or folder.name in SKIP:
            continue
        for png in sorted(folder.glob("*.png")):
            kind = cutout(png)
            n += 1
            print(f"{kind:16} {png.relative_to(ROOT)}")
    print(f"processed {n} files")


if __name__ == "__main__":
    main()
