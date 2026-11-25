"""A QR code small enough for the panel, made here with nothing but Python (an imported module may only count on
Pillow, numpy and Python's own library). Byte mode, the lowest error correction, versions 1 to 3 (21 to 29
dots a side): enough for the topic's address. ``matrix(text)`` is rows of True (dark) and False."""
from __future__ import annotations

# version: (size, data codewords, error-correction codewords, alignment pattern centre or None), level L, one block
VERSIONS = {1: (21, 19, 7, None), 2: (25, 34, 10, 18), 3: (29, 55, 15, 22)}


def _mul(x: int, y: int) -> int:
    z = 0
    for i in range(7, -1, -1):
        z = ((z << 1) ^ ((z >> 7) * 0x11D)) & 0xFF
        z ^= ((y >> i) & 1) * x
    return z


def _divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _mul(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _mul(root, 0x02)
    return result


def _remainder(data: list[int], divisor: list[int]) -> list[int]:
    result = [0] * len(divisor)
    for byte in data:
        factor = byte ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _mul(coef, factor)
    return result


def version_for(text: str) -> int | None:
    """The smallest version that holds ``text``, or None if it is too long for the panel."""
    n = len(text.encode("utf-8"))
    for v, (_, data, _, _) in VERSIONS.items():
        if 4 + 8 + 8 * n <= data * 8:
            return v
    return None


def _codewords(text: str, version: int) -> list[int]:
    size, data_len, ec_len, _ = VERSIONS[version]
    raw = text.encode("utf-8")
    bits = [0, 1, 0, 0] + [(len(raw) >> i) & 1 for i in range(7, -1, -1)]
    for byte in raw:
        bits += [(byte >> i) & 1 for i in range(7, -1, -1)]
    bits += [0] * min(4, data_len * 8 - len(bits))
    bits += [0] * (-len(bits) % 8)
    data = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0xEC
    while len(data) < data_len:
        data.append(pad)
        pad ^= 0xEC ^ 0x11
    return data + _remainder(data, _divisor(ec_len))


MASKS = [lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0, lambda x, y: (x + y) % 3 == 0,
         lambda x, y: (x // 3 + y // 2) % 2 == 0, lambda x, y: x * y % 2 + x * y % 3 == 0,
         lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0, lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0]


def _base(version: int):
    """The fixed patterns: (modules, which ones are fixed)."""
    size, _, _, align = VERSIONS[version]
    dots = [[False] * size for _ in range(size)]
    fixed = [[False] * size for _ in range(size)]

    def put(x, y, dark):
        if 0 <= x < size and 0 <= y < size:
            dots[y][x], fixed[y][x] = dark, True

    for i in range(size):                               # timing
        put(6, i, i % 2 == 0), put(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):   # finders, with their light borders
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                d = max(abs(dx), abs(dy))
                put(cx + dx, cy + dy, d not in (2, 4))
    if align:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                put(align + dx, align + dy, max(abs(dx), abs(dy)) != 1)
    for i in range(9):                                  # where the format bits go (filled in later)
        if not fixed[8][i]:
            put(i, 8, False)
        if not fixed[i][8]:
            put(8, i, False)
    for i in range(8):
        put(size - 1 - i, 8, False), put(8, size - 1 - i, False)
    put(8, size - 8, True)                              # the one dark module
    return dots, fixed


def _format(dots, mask: int) -> None:
    size = len(dots)
    data = (1 << 3) | mask                              # level L is 01
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    bits = ((data << 10) | rem) ^ 0x5412
    bit = [(bits >> i) & 1 == 1 for i in range(15)]
    for i in range(6):
        dots[i][8] = bit[i]
    dots[7][8], dots[8][8], dots[8][7] = bit[6], bit[7], bit[8]
    for i in range(9, 15):
        dots[8][14 - i] = bit[i]
    for i in range(8):
        dots[8][size - 1 - i] = bit[i]
    for i in range(8, 15):
        dots[size - 15 + i][8] = bit[i]
    dots[size - 8][8] = True


def _place(dots, fixed, codewords: list[int]) -> None:
    size = len(dots)
    i, total = 0, len(codewords) * 8
    right = size - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(size):
            for j in range(2):
                x = right - j
                y = size - 1 - vert if ((right + 1) & 2) == 0 else vert
                if not fixed[y][x] and i < total:
                    dots[y][x] = (codewords[i >> 3] >> (7 - (i & 7))) & 1 == 1
                    i += 1
        right -= 2


def _penalty(dots) -> int:
    size, score = len(dots), 0
    lines = [row for row in dots] + [[dots[y][x] for y in range(size)] for x in range(size)]
    finder = [True, False, True, True, True, False, True]
    for line in lines:
        run, last = 0, None
        for dot in line:
            run = run + 1 if dot == last else 1
            last = dot
            if run == 5:
                score += 3
            elif run > 5:
                score += 1
        padded = [False] * 4 + list(line) + [False] * 4
        for k in range(len(padded) - 6):
            if padded[k:k + 7] == finder and (not any(padded[max(0, k - 4):k]) or not any(padded[k + 7:k + 11])):
                score += 40
    for y in range(size - 1):
        for x in range(size - 1):
            if dots[y][x] == dots[y][x + 1] == dots[y + 1][x] == dots[y + 1][x + 1]:
                score += 3
    dark = sum(map(sum, dots))
    score += 10 * (abs(dark * 20 - size * size * 10) // (size * size))
    return score


def matrix(text: str, mask: int | None = None) -> list[list[bool]] | None:
    """The code for ``text`` (None if it's too long for a version-3 code), with the mask that scans best."""
    version = version_for(text)
    if version is None:
        return None
    codewords = _codewords(text, version)
    best = None
    for m in ([mask] if mask is not None else range(8)):
        dots, fixed = _base(version)
        _place(dots, fixed, codewords)
        for y in range(len(dots)):
            for x in range(len(dots)):
                if not fixed[y][x] and MASKS[m](x, y):
                    dots[y][x] = not dots[y][x]
        _format(dots, m)
        score = _penalty(dots)
        if best is None or score < best[0]:
            best = (score, dots)
    return best[1]
