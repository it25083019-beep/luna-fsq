"""Turn a flat-white-background sprite render into a cropped, transparent PNG.

Pure standard library so it can run without extra packages. Background is found
by flood-filling near-white pixels from the image border, which keeps white
armour and wings inside the character opaque.

Usage:
    py -3 sprite_alpha.py <in.png> <out.png> [max_size]
"""
from __future__ import annotations

import struct
import sys
import zlib
from collections import deque

WHITE_MIN = 243          # pixel counts as background white at/above this
EDGE_SOFT_MIN = 218      # boundary pixels this light get partial alpha
EDGE_ALPHA = 170
PAD = 10


def read_rgb_png(path: str) -> tuple[int, int, bytearray]:
    raw = open(path, "rb").read()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos = 8
    idat = bytearray()
    width = height = 0
    channels = 3
    while pos < len(raw):
        (length,) = struct.unpack(">I", raw[pos : pos + 4])
        ctype = raw[pos + 4 : pos + 8]
        body = raw[pos + 8 : pos + 8 + length]
        if ctype == b"IHDR":
            width, height, depth, color, _comp, _filt, interlace = struct.unpack(
                ">IIBBBBB", body
            )
            if depth != 8 or interlace != 0 or color not in (2, 6):
                raise ValueError(f"unsupported PNG: depth={depth} color={color}")
            channels = 3 if color == 2 else 4
        elif ctype == b"IDAT":
            idat += body
        elif ctype == b"IEND":
            break
        pos += 12 + length

    data = zlib.decompress(bytes(idat))
    stride = width * channels
    out = bytearray(width * height * 3)
    prev = bytearray(stride)
    src = 0
    for y in range(height):
        ftype = data[src]
        src += 1
        line = bytearray(data[src : src + stride])
        src += stride
        if ftype == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        elif ftype != 0:
            raise ValueError(f"bad filter {ftype}")
        prev = line

        dst = y * width * 3
        if channels == 3:
            out[dst : dst + width * 3] = line
        else:
            for x in range(width):
                s = x * 4
                d = dst + x * 3
                out[d] = line[s]
                out[d + 1] = line[s + 1]
                out[d + 2] = line[s + 2]
    return width, height, out


def build_alpha(width: int, height: int, rgb: bytearray) -> bytearray:
    alpha = bytearray(b"\xff" * (width * height))
    is_white = bytearray(width * height)
    for i in range(width * height):
        p = i * 3
        if rgb[p] >= WHITE_MIN and rgb[p + 1] >= WHITE_MIN and rgb[p + 2] >= WHITE_MIN:
            is_white[i] = 1

    queue = deque()
    seen = bytearray(width * height)
    for x in range(width):
        for i in (x, (height - 1) * width + x):
            if is_white[i] and not seen[i]:
                seen[i] = 1
                queue.append(i)
    for y in range(height):
        for i in (y * width, y * width + width - 1):
            if is_white[i] and not seen[i]:
                seen[i] = 1
                queue.append(i)

    while queue:
        i = queue.popleft()
        alpha[i] = 0
        x = i % width
        y = i // width
        if x > 0 and is_white[i - 1] and not seen[i - 1]:
            seen[i - 1] = 1
            queue.append(i - 1)
        if x < width - 1 and is_white[i + 1] and not seen[i + 1]:
            seen[i + 1] = 1
            queue.append(i + 1)
        if y > 0 and is_white[i - width] and not seen[i - width]:
            seen[i - width] = 1
            queue.append(i - width)
        if y < height - 1 and is_white[i + width] and not seen[i + width]:
            seen[i + width] = 1
            queue.append(i + width)

    soften = []
    for y in range(height):
        row = y * width
        for x in range(width):
            i = row + x
            if not alpha[i]:
                continue
            p = i * 3
            if min(rgb[p], rgb[p + 1], rgb[p + 2]) < EDGE_SOFT_MIN:
                continue
            if (
                (x > 0 and alpha[i - 1] == 0)
                or (x < width - 1 and alpha[i + 1] == 0)
                or (y > 0 and alpha[i - width] == 0)
                or (y < height - 1 and alpha[i + width] == 0)
            ):
                soften.append(i)
    for i in soften:
        alpha[i] = EDGE_ALPHA
    return alpha


def bbox(width: int, height: int, alpha: bytearray) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = width, height, -1, -1
    for y in range(height):
        row = y * width
        for x in range(width):
            if alpha[row + x]:
                if x < x0:
                    x0 = x
                if x > x1:
                    x1 = x
                if y < y0:
                    y0 = y
                if y > y1:
                    y1 = y
    if x1 < 0:
        raise ValueError("empty sprite")
    return (
        max(0, x0 - PAD),
        max(0, y0 - PAD),
        min(width - 1, x1 + PAD),
        min(height - 1, y1 + PAD),
    )


def resample(
    src_w: int,
    src_h: int,
    rgb: bytearray,
    alpha: bytearray,
    box: tuple[int, int, int, int],
    max_size: int,
) -> tuple[int, int, bytearray]:
    x0, y0, x1, y1 = box
    cw, ch = x1 - x0 + 1, y1 - y0 + 1
    scale = min(1.0, max_size / max(cw, ch))
    ow, oh = max(1, round(cw * scale)), max(1, round(ch * scale))
    out = bytearray(ow * oh * 4)
    for oy in range(oh):
        sy0 = y0 + int(oy * ch / oh)
        sy1 = y0 + max(sy0 + 1 - y0, int((oy + 1) * ch / oh))
        for ox in range(ow):
            sx0 = x0 + int(ox * cw / ow)
            sx1 = x0 + max(sx0 + 1 - x0, int((ox + 1) * cw / ow))
            ar = ag = ab = aa = n = 0
            for sy in range(sy0, min(sy1, y1 + 1)):
                base = sy * src_w
                for sx in range(sx0, min(sx1, x1 + 1)):
                    i = base + sx
                    a = alpha[i]
                    p = i * 3
                    ar += rgb[p] * a
                    ag += rgb[p + 1] * a
                    ab += rgb[p + 2] * a
                    aa += a
                    n += 1
            d = (oy * ow + ox) * 4
            if aa:
                out[d] = min(255, ar // aa)
                out[d + 1] = min(255, ag // aa)
                out[d + 2] = min(255, ab // aa)
                out[d + 3] = min(255, aa // max(1, n))
    return ow, oh, out


def write_rgba_png(path: str, width: int, height: int, rgba: bytearray) -> None:
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        raw += rgba[y * stride : (y + 1) * stride]

    def chunk(tag: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + tag
            + body
            + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    open(path, "wb").write(png)


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    max_size = int(sys.argv[3]) if len(sys.argv) > 3 else 512
    w, h, rgb = read_rgb_png(src)
    alpha = build_alpha(w, h, rgb)
    box = bbox(w, h, alpha)
    ow, oh, rgba = resample(w, h, rgb, alpha, box, max_size)
    write_rgba_png(dst, ow, oh, rgba)
    print(f"{dst} {ow}x{oh}")


if __name__ == "__main__":
    main()
