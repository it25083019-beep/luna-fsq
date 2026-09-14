# -*- coding: utf-8 -*-
"""Knock white/black studio mattes off fight pose PNGs and keep true RGBA."""
from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / "static" / "rpg" / "fight"
PAD = 12


def is_matte(r: int, g: int, b: int, a: int) -> bool:
    if a < 12:
        return True
    mx, mn = max(r, g, b), min(r, g, b)
    sat = mx - mn
    if mn >= 208 and sat <= 36:
        return True
    if mn >= 188 and sat <= 16 and mx >= 198:
        return True
    if mx <= 16:
        return True
    return False


def flood_matte(im: Image.Image) -> None:
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    q = deque()

    def push(x: int, y: int) -> None:
        if 0 <= x < w and 0 <= y < h and not seen[y * w + x]:
            seen[y * w + x] = 1
            q.append((x, y))

    for x in range(w):
        push(x, 0)
        push(x, h - 1)
    for y in range(h):
        push(0, y)
        push(w - 1, y)

    while q:
        x, y = q.popleft()
        r, g, b, a = px[x, y]
        if not is_matte(r, g, b, a):
            continue
        if a:
            px[x, y] = (r, g, b, 0)
        push(x + 1, y)
        push(x - 1, y)
        push(x, y + 1)
        push(x, y - 1)


def punch_large_white_islands(im: Image.Image, min_size: int = 700) -> int:
    """Studio paper trapped inside a pose (bow, cape, legs) is not border-connected."""
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    punched = 0
    for y0 in range(h):
        for x0 in range(w):
            i0 = y0 * w + x0
            if seen[i0]:
                continue
            r, g, b, a = px[x0, y0]
            if a < 12 or not is_matte(r, g, b, a):
                seen[i0] = 1
                continue
            q = deque([(x0, y0)])
            seen[i0] = 1
            cluster = [(x0, y0)]
            while q:
                x, y = q.popleft()
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if nx < 0 or ny < 0 or nx >= w or ny >= h:
                        continue
                    ni = ny * w + nx
                    if seen[ni]:
                        continue
                    rr, gg, bb, aa = px[nx, ny]
                    if aa < 12 or not is_matte(rr, gg, bb, aa):
                        seen[ni] = 1
                        continue
                    seen[ni] = 1
                    q.append((nx, ny))
                    cluster.append((nx, ny))
            if len(cluster) >= min_size:
                for x, y in cluster:
                    rr, gg, bb, _ = px[x, y]
                    px[x, y] = (rr, gg, bb, 0)
                    punched += 1
    return punched


def zero_clear_rgb(im: Image.Image) -> None:
    w, h = im.size
    px = im.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                px[x, y] = (0, 0, 0, 0)


def eat_white_rim(im: Image.Image, rounds: int = 8, white: int = 224) -> None:
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
                if max(r, g, b) - min(r, g, b) > 28:
                    continue
                edge = False
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if nx < 0 or ny < 0 or nx >= w or ny >= h or px[nx, ny][3] == 0:
                        edge = True
                        break
                if edge:
                    victims.append((x, y))
        if not victims:
            break
        for x, y in victims:
            r, g, b, _ = px[x, y]
            px[x, y] = (r, g, b, 0)


def crop_pad(im: Image.Image) -> Image.Image:
    alpha = im.split()[-1]
    box = alpha.getbbox()
    if not box:
        return im
    x0, y0, x1, y1 = box
    x0 = max(0, x0 - PAD)
    y0 = max(0, y0 - PAD)
    x1 = min(im.size[0], x1 + PAD)
    y1 = min(im.size[1], y1 + PAD)
    return im.crop((x0, y0, x1, y1))


def punch(path: Path) -> None:
    im = Image.open(path).convert("RGBA")
    flood_matte(im)
    islands = punch_large_white_islands(im)
    eat_white_rim(im)
    zero_clear_rgb(im)
    im = crop_pad(im)
    zero_clear_rgb(im)
    im.save(path, format="PNG", optimize=True)
    n_white = n_trans = 0
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 10:
                n_trans += 1
            elif r > 240 and g > 240 and b > 240:
                n_white += 1
    print(
        f"{path.name} {im.size} trans={n_trans} white_opaque={n_white} "
        f"islands={islands} corner={im.getpixel((0, 0))}"
    )


def main() -> None:
    for path in sorted(ROOT.glob("*.png")):
        punch(path)


if __name__ == "__main__":
    main()
