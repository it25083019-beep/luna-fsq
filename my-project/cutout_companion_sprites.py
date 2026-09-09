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


def _chroma(r: int, g: int, b: int) -> int:
    return max(r, g, b) - min(r, g, b)


def _eat_neutral_sticker_rim(im: Image.Image, rounds: int = 28, min_luma: int = 155, max_chroma: int = 16) -> int:
    """Remove the grey/white sticker stroke. Leaves warm cream clothes and colored hair."""
    w, h = im.size
    px = im.load()
    eaten = 0
    for _ in range(rounds):
        victims = []
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a == 0:
                    continue
                if min(r, g, b) < min_luma:
                    continue
                if _chroma(r, g, b) > max_chroma:
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
            eaten += 1
    return eaten


def _eat_grey_plate_crumbs(im: Image.Image, rounds: int = 10, max_luma: int = 48, max_chroma: int = 10) -> int:
    """Clear leftover dark-grey plate specks in hair gaps (not navy clothes)."""
    w, h = im.size
    px = im.load()
    eaten = 0
    for _ in range(rounds):
        victims = []
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a == 0:
                    continue
                if max(r, g, b) > max_luma:
                    continue
                if _chroma(r, g, b) > max_chroma:
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
            eaten += 1
    return eaten


def _drop_tiny_specks(im: Image.Image, max_size: int = 80) -> int:
    """Delete tiny leftover islands that are not part of the body."""
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    dropped = 0
    for y0 in range(h):
        for x0 in range(w):
            i0 = y0 * w + x0
            if seen[i0] or px[x0, y0][3] == 0:
                continue
            q = deque([(x0, y0)])
            seen[i0] = 1
            comp = [(x0, y0)]
            large = False
            while q:
                x, y = q.popleft()
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if nx < 0 or ny < 0 or nx >= w or ny >= h:
                        continue
                    ni = ny * w + nx
                    if seen[ni] or px[nx, ny][3] == 0:
                        continue
                    seen[ni] = 1
                    q.append((nx, ny))
                    if large:
                        continue
                    comp.append((nx, ny))
                    if len(comp) > max_size:
                        large = True
                        comp = []
            if not large and comp:
                for x, y in comp:
                    r, g, b, _ = px[x, y]
                    px[x, y] = (r, g, b, 0)
                    dropped += 1
    return dropped


def _punch_enclosed_plate(im: Image.Image, min_size: int = 12, max_size: int = 9000) -> int:
    """Clear leftover black/white plate trapped inside hair loops."""
    w, h = im.size
    px = im.load()

    def is_plate(r, g, b, a) -> bool:
        if a == 0:
            return False
        if _chroma(r, g, b) > 14:
            return False
        return max(r, g, b) <= 60 or min(r, g, b) >= 185

    seen = bytearray(w * h)
    punched = 0
    for y0 in range(h):
        for x0 in range(w):
            i0 = y0 * w + x0
            if seen[i0]:
                continue
            r, g, b, a = px[x0, y0]
            if not is_plate(r, g, b, a):
                seen[i0] = 1
                continue
            q = deque([(x0, y0)])
            seen[i0] = 1
            cells = [(x0, y0)]
            sx = x0
            sy = y0
            while q:
                x, y = q.popleft()
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if nx < 0 or ny < 0 or nx >= w or ny >= h:
                        continue
                    ni = ny * w + nx
                    if seen[ni]:
                        continue
                    rr, gg, bb, aa = px[nx, ny]
                    if is_plate(rr, gg, bb, aa):
                        seen[ni] = 1
                        q.append((nx, ny))
                        cells.append((nx, ny))
                        sx += nx
                        sy += ny
                    else:
                        seen[ni] = 1 if aa == 0 else seen[ni]
            n = len(cells)
            cx = sx / n
            cy = sy / n
            side_hair = cx < w * 0.34 or cx > w * 0.66
            upper = cy < h * 0.62
            small = n < 2200
            if min_size <= n <= max_size and (side_hair or upper or small):
                for x, y in cells:
                    r, g, b, _ = px[x, y]
                    px[x, y] = (r, g, b, 0)
                punched += n
    return punched


def refine_sticker(path: Path) -> str:
    im = Image.open(path).convert("RGBA")
    rim = _eat_neutral_sticker_rim(im)
    crumbs = _eat_grey_plate_crumbs(im)
    holes = _punch_enclosed_plate(im)
    specks = _drop_tiny_specks(im)
    im.save(path, "PNG")
    return f"rim={rim} crumbs={crumbs} holes={holes} specks={specks}"


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
