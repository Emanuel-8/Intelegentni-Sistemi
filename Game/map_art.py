"""
map_art.py
─────────────────────────────────────────────────────────────
All arena artwork, generated procedurally (no image files needed).

  build_static_layer(map)  → one opaque 1920×1080 surface with the
                             terrain, decorations, 3D obstacles and
                             lighting baked in (built once per map).
  MapAnimator(map)         → cheap per-frame effects drawn on top:
                             fireflies, embers, arcane motes, neon
                             pulses, animated crystals …

Visual only: nothing here affects collisions or gameplay, so the AI
training environment never needs to call it.
"""

import hashlib
import math
import os
import random

import numpy as np
import pygame

WIDTH, HEIGHT = 1920, 1080
STYLES = ["forest", "quarry", "ruins", "neon"]


# ─────────────────────────────────────────────
#  small helpers
# ─────────────────────────────────────────────
def _clamp(c):
    return max(0, min(255, int(c)))


def shade(color, amount):
    """Lighten (amount > 0) or darken (amount < 0) an RGB colour."""
    return tuple(_clamp(c + amount) for c in color[:3])


def mix(a, b, t):
    return tuple(_clamp(a[i] + (b[i] - a[i]) * t) for i in range(3))


def value_noise(w, h, cell, rng):
    gw, gh = w // cell + 2, h // cell + 2
    g = rng.random((gh, gw), dtype=np.float32)
    xs = np.arange(w, dtype=np.float32) / cell
    ys = np.arange(h, dtype=np.float32) / cell
    x0, y0 = xs.astype(np.int32), ys.astype(np.int32)
    tx, ty = xs - x0, ys - y0
    tx = tx * tx * (3 - 2 * tx)
    ty = ty * ty * (3 - 2 * ty)
    rows0, rows1 = g[y0], g[y0 + 1]
    top = rows0[:, x0] + (rows0[:, x0 + 1] - rows0[:, x0]) * tx[None, :]
    bot = rows1[:, x0] + (rows1[:, x0 + 1] - rows1[:, x0]) * tx[None, :]
    return top + (bot - top) * ty[:, None]


def fbm(w, h, rng, cell=320, octaves=5, gain=0.5):
    total = np.zeros((h, w), dtype=np.float32)
    amp, norm = 1.0, 0.0
    for _ in range(octaves):
        total += value_noise(w, h, max(2, int(cell)), rng) * amp
        norm += amp
        amp *= gain
        cell /= 2
    return total / norm


def ramp(values, stops):
    """Map a 0..1 array to colours with linear interpolation between stops."""
    ts = [s[0] for s in stops]
    out = np.empty(values.shape + (3,), dtype=np.float32)
    for ch in range(3):
        out[..., ch] = np.interp(values, ts, [s[1][ch] for s in stops])
    return out


def array_to_surface(rgb):
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    return pygame.surfarray.make_surface(rgb.transpose(1, 0, 2))


def blur_surface(surf, factor=4):
    w, h = surf.get_size()
    small = pygame.transform.smoothscale(surf, (max(1, w // factor), max(1, h // factor)))
    return pygame.transform.smoothscale(small, (w, h))


_glow_cache = {}


def glow_sprite(color, radius, intensity=1.0):
    """Soft radial glow on black, meant for BLEND_ADD blitting."""
    key = (tuple(color[:3]), int(radius), round(intensity, 2))
    spr = _glow_cache.get(key)
    if spr is None:
        size = int(radius) * 2 + 2
        yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
        c = (size - 1) / 2
        d = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / max(1.0, radius)
        fall = np.clip(1 - d, 0, 1) ** 2 * intensity
        rgb = np.stack([fall * color[i] for i in range(3)], axis=-1)
        spr = array_to_surface(rgb)
        _glow_cache[key] = spr
    return spr


def soft_shadow(size, alpha=90, blur=6):
    """A blurred dark ellipse of the given (w, h) on a transparent surface."""
    w, h = int(size[0]), int(size[1])
    pad = blur * 3
    s = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, alpha), (pad, pad, w, h))
    return blur_surface(s, max(2, blur)), pad


def vignette(strength=170, tint=(0, 0, 0)):
    sw, sh = 192, 108
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
    nx = (xx - sw / 2) / (sw / 2)
    ny = (yy - sh / 2) / (sh / 2)
    d = np.sqrt(nx * nx * 0.9 + ny * ny * 1.1)
    a = np.clip((d - 0.55) / 0.75, 0, 1) ** 1.6 * strength
    s = pygame.Surface((sw, sh), pygame.SRCALPHA)
    s.fill((*tint, 0))
    alpha = pygame.surfarray.pixels_alpha(s)
    alpha[:, :] = a.T.astype(np.uint8)
    del alpha
    return pygame.transform.smoothscale(s, (WIDTH, HEIGHT))


# ─────────────────────────────────────────────
#  GROUND
# ─────────────────────────────────────────────
def _ground_forest(rng, nrng):
    n = fbm(WIDTH, HEIGHT, nrng, 360, 6)
    rgb = ramp(n, [(0.0, (20, 52, 26)), (0.35, (32, 80, 36)), (0.55, (46, 104, 46)),
                   (0.75, (62, 124, 54)), (1.0, (92, 150, 66))])
    # winding dirt path between the two spawns
    xs = np.arange(WIDTH, dtype=np.float32)
    ys = np.arange(HEIGHT, dtype=np.float32)[:, None]
    path_y = HEIGHT * 0.52 + 120 * np.sin(xs / 260.0) + 60 * np.sin(xs / 97.0 + 1.3)
    wobble = fbm(WIDTH, HEIGHT, nrng, 120, 3) * 40
    d = np.abs(ys - path_y[None, :]) - wobble
    m = np.clip(1 - (d - 34) / 22, 0, 1)
    dirt = ramp(fbm(WIDTH, HEIGHT, nrng, 60, 4), [(0, (78, 60, 38)), (0.5, (112, 88, 56)), (1, (146, 118, 76))])
    rgb = rgb * (1 - m[..., None]) + dirt * m[..., None]
    grain = nrng.normal(0, 5, (HEIGHT, WIDTH, 1)).astype(np.float32)
    surf = array_to_surface(rgb + grain)
    path_mask = m

    # grass tufts & flowers
    for _ in range(4200):
        x, y = rng.randint(0, WIDTH - 1), rng.randint(0, HEIGHT - 1)
        if path_mask[y, x] > 0.2:
            continue
        base = surf.get_at((x, y))
        col = shade(base, rng.choice((-26, -18, 22, 32)))
        for k in range(3):
            ang = -math.pi / 2 + rng.uniform(-0.6, 0.6)
            ln = rng.randint(4, 9)
            pygame.draw.line(surf, col, (x + k * 2, y), (x + k * 2 + math.cos(ang) * ln, y + math.sin(ang) * ln), 1)
    for _ in range(70):
        cx, cy = rng.randint(40, WIDTH - 40), rng.randint(40, HEIGHT - 40)
        if path_mask[cy, cx] > 0.1:
            continue
        col = rng.choice([(250, 245, 230), (255, 214, 90), (240, 140, 190), (170, 150, 255)])
        for _ in range(rng.randint(3, 7)):
            fx, fy = cx + rng.randint(-18, 18), cy + rng.randint(-12, 12)
            pygame.draw.circle(surf, col, (fx, fy), 2)
            pygame.draw.circle(surf, (255, 250, 200), (fx, fy), 1)
    # pebbles on the path
    for _ in range(260):
        x, y = rng.randint(0, WIDTH - 1), rng.randint(0, HEIGHT - 1)
        if path_mask[y, x] > 0.6:
            r = rng.randint(2, 4)
            pygame.draw.circle(surf, (70, 60, 48), (x + 1, y + 1), r)
            pygame.draw.circle(surf, (150, 138, 118), (x, y), r)
    return surf


def _ground_quarry(rng, nrng):
    n = fbm(WIDTH, HEIGHT, nrng, 400, 6)
    ys = np.arange(HEIGHT, dtype=np.float32)[:, None]
    strata = np.sin(ys * 0.045 + fbm(WIDTH, HEIGHT, nrng, 300, 3) * 7.0)
    rgb = ramp(n, [(0.0, (104, 50, 22)), (0.35, (150, 80, 36)), (0.6, (186, 112, 52)),
                   (0.85, (214, 146, 78)), (1.0, (232, 172, 104))])
    band = (np.abs(strata) < 0.07).astype(np.float32)[..., None]
    rgb = rgb - band * 26 + (strata[..., None] > 0.9) * 10
    # sunset light from the upper left
    xx = np.arange(WIDTH, dtype=np.float32)[None, :]
    light = np.clip(1.2 - np.sqrt((xx / WIDTH) ** 2 + (ys / HEIGHT) ** 2), 0, 1)[..., None]
    rgb = rgb + light * np.array([40, 18, 0], dtype=np.float32)
    rgb = rgb + nrng.normal(0, 6, (HEIGHT, WIDTH, 1)).astype(np.float32)
    surf = array_to_surface(rgb)

    # cracks
    for _ in range(26):
        x, y = rng.uniform(0, WIDTH), rng.uniform(0, HEIGHT)
        ang = rng.uniform(0, math.pi * 2)
        pts = [(x, y)]
        for _ in range(rng.randint(5, 12)):
            ang += rng.uniform(-0.7, 0.7)
            x += math.cos(ang) * rng.uniform(10, 26)
            y += math.sin(ang) * rng.uniform(10, 26)
            pts.append((x, y))
        pygame.draw.lines(surf, (238, 178, 112), False, [(px + 1, py + 1) for px, py in pts], 1)
        pygame.draw.lines(surf, (88, 44, 22), False, pts, 2)
    # mine-cart rails along the bottom
    rail_y = 1010
    for sx in range(-20, WIDTH + 40, 46):
        pygame.draw.rect(surf, (60, 38, 22), (sx, rail_y - 18, 16, 50), border_radius=3)
        pygame.draw.rect(surf, (104, 70, 40), (sx + 2, rail_y - 16, 12, 46), border_radius=2)
    for ry in (rail_y - 8, rail_y + 18):
        pygame.draw.line(surf, (40, 34, 32), (0, ry + 2), (WIDTH, ry + 2), 5)
        pygame.draw.line(surf, (150, 140, 136), (0, ry), (WIDTH, ry), 4)
        pygame.draw.line(surf, (215, 205, 195), (0, ry - 1), (WIDTH, ry - 1), 1)
    # pebbles and sand drifts
    for _ in range(700):
        x, y = rng.randint(0, WIDTH - 1), rng.randint(0, HEIGHT - 1)
        r = rng.choice((1, 2, 2, 3))
        base = surf.get_at((x, y))
        pygame.draw.circle(surf, shade(base, -40), (x + 1, y + 1), r)
        pygame.draw.circle(surf, shade(base, 25), (x, y), r)
    return surf


def _ground_ruins(rng, nrng):
    n = fbm(WIDTH, HEIGHT, nrng, 300, 5)
    moss = fbm(WIDTH, HEIGHT, nrng, 220, 4)
    rgb = ramp(n, [(0.0, (40, 38, 66)), (0.5, (66, 62, 100)), (1.0, (96, 90, 136))])
    tile = 120
    ys, xs = np.mgrid[0:HEIGHT, 0:WIDTH]
    tx, ty = xs // tile, ys // tile
    # each tile gets its own brightness
    tile_rng = np.random.default_rng(7)
    tint = tile_rng.normal(0, 9, (HEIGHT // tile + 2, WIDTH // tile + 2)).astype(np.float32)
    rgb = rgb + tint[ty, tx][..., None]
    grout = ((xs % tile) < 3) | ((ys % tile) < 3)
    rgb[grout] = rgb[grout] * 0.45
    m = np.clip((moss - 0.55) * 4, 0, 1)[..., None]
    rgb = rgb * (1 - m * 0.5) + np.array([50, 92, 58], dtype=np.float32) * m * 0.5
    rgb = rgb + nrng.normal(0, 5, (HEIGHT, WIDTH, 1)).astype(np.float32)
    surf = array_to_surface(rgb)

    # bevel highlights on tiles, some cracked
    for gx in range(0, WIDTH, tile):
        for gy in range(0, HEIGHT, tile):
            pygame.draw.line(surf, (120, 114, 168), (gx + 3, gy + 3), (gx + tile - 2, gy + 3), 1)
            pygame.draw.line(surf, (120, 114, 168), (gx + 3, gy + 3), (gx + 3, gy + tile - 2), 1)
            if rng.random() < 0.22:
                x, y = gx + rng.randint(15, tile - 15), gy + rng.randint(15, tile - 15)
                pts = [(x, y)]
                for _ in range(rng.randint(3, 6)):
                    x += rng.randint(-22, 22)
                    y += rng.randint(-22, 22)
                    pts.append((max(gx + 4, min(gx + tile - 4, x)), max(gy + 4, min(gy + tile - 4, y))))
                pygame.draw.lines(surf, (28, 26, 44), False, pts, 2)

    # summoning circle in the middle of the arena
    cx, cy = WIDTH // 2, HEIGHT // 2 + 20
    for r, wdt in ((210, 4), (186, 2), (120, 3)):
        pygame.draw.circle(surf, (70, 56, 130), (cx, cy), r, wdt)
    for i in range(24):
        a = i / 24 * math.pi * 2
        x, y = cx + math.cos(a) * 198, cy + math.sin(a) * 198
        _rune(surf, x, y, a, (120, 100, 210), rng)
    for i in range(6):
        a1 = i / 6 * math.pi * 2
        a2 = a1 + math.pi * 2 / 3
        pygame.draw.line(surf, (82, 66, 150), (cx + math.cos(a1) * 120, cy + math.sin(a1) * 120),
                         (cx + math.cos(a2) * 120, cy + math.sin(a2) * 120), 2)
    return surf


def _rune(surf, x, y, ang, color, rng):
    pts = []
    for _ in range(rng.randint(2, 3)):
        a = rng.uniform(0, math.pi * 2)
        pts.append(((x + math.cos(a) * 7), (y + math.sin(a) * 7)))
    pts.append((x, y))
    pygame.draw.lines(surf, color, False, pts, 2)


def _ground_neon(rng, nrng):
    n = fbm(WIDTH, HEIGHT, nrng, 420, 5)
    rgb = ramp(n, [(0.0, (3, 3, 12)), (0.6, (8, 8, 28)), (1.0, (20, 14, 52))])
    rgb = rgb + nrng.normal(0, 2.5, (HEIGHT, WIDTH, 1)).astype(np.float32)
    surf = array_to_surface(rgb)
    grid = pygame.Surface((WIDTH, HEIGHT))
    for gx in range(0, WIDTH + 1, 80):
        major = gx % 320 == 0
        pygame.draw.line(grid, (0, 120, 140) if major else (0, 46, 60), (gx, 0), (gx, HEIGHT), 2 if major else 1)
    for gy in range(0, HEIGHT + 1, 80):
        major = gy % 320 == 0
        pygame.draw.line(grid, (120, 0, 140) if major else (40, 0, 60), (0, gy), (WIDTH, gy), 2 if major else 1)
    surf.blit(blur_surface(grid, 6), (0, 0), special_flags=pygame.BLEND_ADD)
    surf.blit(grid, (0, 0), special_flags=pygame.BLEND_ADD)
    for _ in range(260):
        x, y = rng.randint(0, WIDTH - 1), rng.randint(0, HEIGHT - 1)
        c = rng.choice([(0, 200, 255), (255, 60, 220), (160, 120, 255)])
        surf.set_at((x, y), shade(c, -60))
    return surf


GROUND_BUILDERS = {"forest": _ground_forest, "quarry": _ground_quarry,
                   "ruins": _ground_ruins, "neon": _ground_neon}


# ─────────────────────────────────────────────
#  ARENA BORDERS
# ─────────────────────────────────────────────
def _border(surf, style, rng):
    if style == "forest":
        for _ in range(170):
            side = rng.randint(0, 3)
            t = rng.uniform(0, 1)
            x = t * WIDTH if side < 2 else (rng.uniform(-30, 26) if side == 2 else WIDTH - rng.uniform(-30, 26))
            y = (rng.uniform(-30, 22) if side == 0 else HEIGHT - rng.uniform(-30, 22)) if side < 2 else t * HEIGHT
            r = rng.randint(26, 46)
            pygame.draw.circle(surf, (12, 36, 16), (int(x), int(y)), r + 3)
            pygame.draw.circle(surf, rng.choice([(22, 64, 28), (28, 76, 32), (18, 56, 24)]), (int(x), int(y)), r)
            pygame.draw.circle(surf, (44, 100, 44), (int(x - r * 0.3), int(y - r * 0.3)), int(r * 0.4))
    elif style == "quarry":
        for edge_y, sign in ((0, 1), (HEIGHT, -1)):
            pts = [(0, edge_y)]
            for x in range(0, WIDTH + 40, 40):
                pts.append((x, edge_y + sign * rng.randint(10, 30)))
            pts.append((WIDTH, edge_y))
            pygame.draw.polygon(surf, (70, 34, 16), pts)
            pygame.draw.lines(surf, (220, 150, 86), False, pts[1:-1], 2)
    elif style == "ruins":
        for x in range(0, WIDTH, 64):
            for y, h in ((0, 22), (HEIGHT - 22, 22)):
                c = shade((70, 66, 104), rng.randint(-10, 10))
                pygame.draw.rect(surf, c, (x + 1, y, 62, h))
                pygame.draw.rect(surf, (40, 36, 66), (x + 1, y, 62, h), 2)
        for y in range(0, HEIGHT, 64):
            for x, w in ((0, 22), (WIDTH - 22, 22)):
                c = shade((70, 66, 104), rng.randint(-10, 10))
                pygame.draw.rect(surf, c, (x, y + 1, w, 62))
                pygame.draw.rect(surf, (40, 36, 66), (x, y + 1, w, 62), 2)
    elif style == "neon":
        edge = pygame.Surface((WIDTH, HEIGHT))
        pygame.draw.rect(edge, (0, 200, 255), (6, 6, WIDTH - 12, HEIGHT - 12), 3, border_radius=18)
        pygame.draw.line(edge, (255, 40, 200), (40, HEIGHT - 6), (WIDTH - 40, HEIGHT - 6), 3)
        surf.blit(blur_surface(edge, 8), (0, 0), special_flags=pygame.BLEND_ADD)
        surf.blit(blur_surface(edge, 3), (0, 0), special_flags=pygame.BLEND_ADD)
        surf.blit(edge, (0, 0), special_flags=pygame.BLEND_ADD)


# ─────────────────────────────────────────────
#  DECORATIONS
# ─────────────────────────────────────────────
def _blit_shadow(surf, cx, cy, w, h, alpha=80):
    sh, pad = soft_shadow((w, h), alpha, 5)
    surf.blit(sh, (cx - w // 2 - pad, cy - h // 2 - pad))


def draw_tree(surf, x, y, leaf=(38, 115, 45), size=1.0, rng=None):
    rng = rng or random.Random(x * 31 + y)
    r = int(30 * size)
    _blit_shadow(surf, x + 14, y + 14, r * 2.6, r * 1.6, 95)
    pygame.draw.circle(surf, (64, 42, 22), (x, y), int(8 * size))
    dark, mid, light = shade(leaf, -26), leaf, shade(leaf, 34)
    blobs = [(rng.uniform(-0.55, 0.55) * r, rng.uniform(-0.6, 0.45) * r, rng.uniform(0.5, 0.72) * r)
             for _ in range(7)]
    for bx, by, br in blobs:
        pygame.draw.circle(surf, shade(dark, -10), (int(x + bx), int(y + by)), int(br + 3))
    for bx, by, br in blobs:
        pygame.draw.circle(surf, dark, (int(x + bx), int(y + by)), int(br))
    for bx, by, br in blobs:
        pygame.draw.circle(surf, mid, (int(x + bx - br * 0.15), int(y + by - br * 0.18)), int(br * 0.78))
    for bx, by, br in blobs[:4]:
        pygame.draw.circle(surf, light, (int(x + bx - br * 0.32), int(y + by - br * 0.36)), int(br * 0.36))
    for _ in range(int(10 * size)):
        lx, ly = x + rng.uniform(-r, r) * 0.8, y + rng.uniform(-r, r) * 0.7
        pygame.draw.circle(surf, shade(light, 18), (int(lx), int(ly)), 2)


def draw_rock(surf, x, y, color, edge, size=1.0, rng=None):
    rng = rng or random.Random(x * 17 + y)
    r = 20 * size
    _blit_shadow(surf, x + 8, y + 10, r * 2.4, r * 1.4, 90)
    pts = []
    for i in range(9):
        a = i / 9 * math.pi * 2
        rr = r * rng.uniform(0.75, 1.05)
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr * 0.8))
    pygame.draw.polygon(surf, shade(color, -30), pts)
    top = [(px, py - 5 * size) for px, py in pts]
    pygame.draw.polygon(surf, color, top)
    hi = [(x + (px - x) * 0.55 - 4, y + (py - y) * 0.5 - 8 * size) for px, py in pts[4:8]]
    pygame.draw.polygon(surf, shade(color, 30), hi)
    pygame.draw.polygon(surf, edge, top, 2)


def draw_bush(surf, x, y, color, size=1.0):
    r = int(14 * size)
    _blit_shadow(surf, x + 6, y + 8, r * 3.2, r * 1.6, 75)
    for ox, oy, sc in [(-9, 2, 0.9), (0, -4, 1.1), (10, 2, 0.95), (2, 5, 0.8)]:
        pygame.draw.circle(surf, shade(color, -22), (x + ox, y + oy), int(r * sc) + 2)
    for ox, oy, sc in [(-9, 2, 0.9), (0, -4, 1.1), (10, 2, 0.95), (2, 5, 0.8)]:
        pygame.draw.circle(surf, color, (x + ox - 1, y + oy - 2), int(r * sc))
    pygame.draw.circle(surf, shade(color, 36), (x - 4, y - 8), int(r * 0.45))
    for i in range(3):
        pygame.draw.circle(surf, (220, 60, 70), (x - 8 + i * 8, y - 2 + (i % 2) * 5), 2)


def draw_stump(surf, x, y, size=1.0):
    w, h = int(26 * size), int(16 * size)
    _blit_shadow(surf, x + 5, y + 8, w * 1.4, h * 1.2, 80)
    pygame.draw.ellipse(surf, (70, 48, 26), (x - w // 2, y - h // 2 + 6, w, h))
    pygame.draw.rect(surf, (70, 48, 26), (x - w // 2, y - 2, w, 8))
    pygame.draw.ellipse(surf, (150, 112, 70), (x - w // 2, y - h // 2, w, h))
    for k in range(1, 3):
        pygame.draw.ellipse(surf, (110, 80, 48), (x - w // 2 + k * 4, y - h // 2 + k * 3, w - k * 8, h - k * 6), 1)


def draw_dead_tree(surf, x, y, size=1.0, rng=None):
    rng = rng or random.Random(x * 13 + y)
    _blit_shadow(surf, x + 18, y + 16, 60 * size, 22 * size, 70)

    def branch(px, py, ang, ln, wdt, depth):
        ex, ey = px + math.cos(ang) * ln, py + math.sin(ang) * ln
        pygame.draw.line(surf, (54, 36, 22), (px, py), (ex, ey), max(1, int(wdt)))
        pygame.draw.line(surf, (96, 70, 46), (px - 1, py - 1), (ex - 1, ey - 1), max(1, int(wdt / 3)))
        if depth > 0:
            for da in (-0.5, 0.45):
                branch(ex, ey, ang + da + rng.uniform(-0.2, 0.2), ln * 0.68, wdt * 0.62, depth - 1)

    for k in range(3):
        branch(x, y, -math.pi / 2 + (k - 1) * 0.9 + rng.uniform(-0.2, 0.2), 20 * size, 6 * size, 2)
    pygame.draw.circle(surf, (60, 40, 24), (x, y), int(6 * size))


def draw_column(surf, x, y, size=1.0):
    w, h = int(18 * size), int(40 * size)
    _blit_shadow(surf, x + 10, y + h // 2 + 4, w * 2.6, h * 0.5, 90)
    body = (84, 80, 128)
    pygame.draw.rect(surf, shade(body, -24), (x - w // 2, y - h // 2 + 6, w, h), border_radius=3)
    pygame.draw.rect(surf, body, (x - w // 2, y - h // 2, w, h - 6), border_radius=3)
    for k in range(1, 4):
        fx = x - w // 2 + k * w // 4
        pygame.draw.line(surf, shade(body, -18), (fx, y - h // 2 + 4), (fx, y + h // 2 - 8), 1)
    pygame.draw.line(surf, shade(body, 40), (x - w // 2 + 2, y - h // 2 + 2), (x - w // 2 + 2, y + h // 2 - 8), 2)
    cw = int(w * 1.6)
    pygame.draw.rect(surf, shade(body, 22), (x - cw // 2, y - h // 2 - 8, cw, 10), border_radius=2)
    pygame.draw.rect(surf, (150, 140, 220), (x - cw // 2, y - h // 2 - 8, cw, 10), 1, border_radius=2)


def draw_debris(surf, x, y, size=1.0, rng=None):
    rng = rng or random.Random(x * 7 + y)
    for _ in range(4):
        ox, oy = rng.uniform(-14, 14) * size, rng.uniform(-10, 10) * size
        r = rng.uniform(5, 11) * size
        pts = [(x + ox + math.cos(a) * r * rng.uniform(0.7, 1.1), y + oy + math.sin(a) * r * 0.75)
               for a in [i / 5 * math.pi * 2 for i in range(5)]]
        pygame.draw.polygon(surf, (40, 36, 60), [(px + 3, py + 4) for px, py in pts])
        pygame.draw.polygon(surf, (100, 96, 150), pts)
        pygame.draw.polygon(surf, (160, 150, 215), pts, 1)


def draw_crate(surf, x, y, edge, size=1.0):
    w = int(30 * size)
    _blit_shadow(surf, x + 8, y + 12, w * 1.5, w * 0.7, 110)
    pygame.draw.rect(surf, (16, 16, 34), (x - w // 2, y - w // 2 + 8, w, w), border_radius=4)
    pygame.draw.rect(surf, (30, 30, 58), (x - w // 2, y - w // 2, w, w), border_radius=4)
    pygame.draw.rect(surf, edge, (x - w // 2, y - w // 2, w, w), 2, border_radius=4)
    pygame.draw.line(surf, shade(edge, -60), (x - w // 2 + 4, y), (x + w // 2 - 4, y), 1)


def _draw_decor(surf, style, decor):
    rng = random.Random(99)
    for item in decor:
        kind = item[0]
        if kind == "crystal":
            continue            # animated, drawn every frame
        _, x, y, sz = item
        if kind == "tree":
            draw_tree(surf, x, y, rng.choice([(38, 115, 45), (46, 122, 40), (34, 104, 52)]), sz, rng)
        elif kind == "rock_forest":
            draw_rock(surf, x, y, (96, 104, 92), (140, 156, 120), sz, rng)
        elif kind == "rock_quarry":
            draw_rock(surf, x, y, (150, 104, 66), (210, 160, 104), sz, rng)
        elif kind == "rock_ruins":
            draw_rock(surf, x, y, (90, 86, 140), (150, 140, 215), sz, rng)
        elif kind == "dead_tree":
            draw_dead_tree(surf, x, y, sz, rng)
        elif kind == "bush_forest":
            draw_bush(surf, x, y, (44, 124, 52), sz)
        elif kind == "bush_quarry":
            draw_bush(surf, x, y, (104, 106, 60), sz)
        elif kind == "stump":
            draw_stump(surf, x, y, sz)
        elif kind == "column":
            draw_column(surf, x, y, sz)
        elif kind == "ruin_debris":
            draw_debris(surf, x, y, sz, rng)
        elif kind == "crate_neon":
            draw_crate(surf, x, y, (0, 220, 180), sz)


# ─────────────────────────────────────────────
#  OBSTACLES (pseudo-3D)
# ─────────────────────────────────────────────
RECT_DEPTH = 20
CIRCLE_DEPTH = 18
# (top face, front face) per map style; ruins use each obstacle's own colour
OBSTACLE_PALETTE = {
    "forest": ((112, 118, 104), (66, 70, 60)),
    "quarry": ((154, 94, 58), (96, 52, 28)),
    "neon":   ((16, 16, 44), (8, 8, 24)),
}
BOULDER_COLOR = {"forest": (100, 108, 94), "quarry": (150, 100, 66), "neon": (22, 22, 56)}


def _textured_rect(w, h, base, rng, cell=24, contrast=26):
    nrng = np.random.default_rng(rng.randint(0, 10 ** 6))
    n = fbm(max(2, w), max(2, h), nrng, cell, 3)
    rgb = np.array(base, dtype=np.float32)[None, None, :] + ((n - 0.5) * contrast * 2)[..., None]
    return array_to_surface(rgb)


def _bricks(surf, rect, color, rng, bw=46, bh=20):
    x0, y0, w, h = rect
    row = 0
    for y in range(y0, y0 + h, bh):
        off = (bw // 2) if row % 2 else 0
        for x in range(x0 - off, x0 + w, bw):
            r = pygame.Rect(x, y, bw, bh).clip(pygame.Rect(rect))
            if r.width > 2 and r.height > 2:
                pygame.draw.rect(surf, color, r, 1)
        row += 1


def _draw_rect_obstacle(surf, ob, style, rng):
    x, y, w, h = int(ob.x), int(ob.y), int(ob.w), int(ob.h)
    d = RECT_DEPTH
    sh, pad = soft_shadow((w + 10, h + 6), 120, 7)
    surf.blit(sh, (x + 12 - pad, y + 10 - pad))
    top_rect = (x, y - d, w, h)
    front_rect = (x, y + h - d, w, d)
    top_col, front_col = OBSTACLE_PALETTE.get(style, (shade(ob.color, 16), shade(ob.color, -34)))

    pygame.draw.rect(surf, front_col, (x, y - d + 6, w, h + d - 6), border_radius=8)
    tex = _textured_rect(w, h, top_col, rng, contrast=22 if style != "neon" else 6)
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, w, h), border_radius=8)
    tex = tex.convert_alpha() if pygame.display.get_surface() else tex
    tex.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(tex, top_rect[:2])

    if style == "forest":
        _bricks(surf, front_rect, shade(front_col, -22), rng, 40, 10)
        _bricks(surf, top_rect, shade(top_col, -20), rng)
        for _ in range(max(2, w // 22)):        # moss on top
            mx, my = x + rng.randint(6, w - 6), y - d + rng.randint(3, max(4, h // 3))
            pygame.draw.circle(surf, (64, 128, 56), (mx, my), rng.randint(4, 9))
            pygame.draw.circle(surf, (96, 160, 70), (mx - 2, my - 2), 3)
    elif style == "quarry":
        for k in range(3, d, 5):
            pygame.draw.line(surf, shade(front_col, -18 if k % 2 else 14), (x + 4, y + h - d + k), (x + w - 4, y + h - d + k), 1)
        for _ in range(max(1, w // 120)):
            cx = x + rng.randint(10, max(11, w - 10))
            pygame.draw.lines(surf, shade(top_col, -40), False,
                              [(cx, y - d + 4), (cx + rng.randint(-8, 8), y - d + h // 2), (cx + rng.randint(-10, 10), y - d + h - 4)], 2)
    elif style == "ruins":
        _bricks(surf, front_rect, shade(front_col, -20), rng, 34, 10)
        _bricks(surf, top_rect, shade(top_col, -22), rng, 52, 22)
        glow = pygame.Surface((w, h))
        if w >= h:
            pygame.draw.line(glow, (120, 80, 255), (10, h // 2), (w - 10, h // 2), 3)
        else:
            pygame.draw.line(glow, (120, 80, 255), (w // 2, 10), (w // 2, h - 10), 3)
        surf.blit(blur_surface(glow, 3), (x, y - d), special_flags=pygame.BLEND_ADD)
        surf.blit(glow, (x, y - d), special_flags=pygame.BLEND_ADD)
    elif style == "neon":
        for gx in range(x + 16, x + w, 24):
            pygame.draw.line(surf, (26, 26, 70), (gx, y - d + 4), (gx, y - d + h - 4), 1)
        for gy in range(y - d + 16, y - d + h, 24):
            pygame.draw.line(surf, (26, 26, 70), (x + 4, gy), (x + w - 4, gy), 1)

    # bevel: light top-left edge, dark bottom edge, outline
    pygame.draw.line(surf, shade(top_col, 46), (x + 6, y - d + 1), (x + w - 7, y - d + 1), 2)
    pygame.draw.line(surf, shade(top_col, 30), (x + 1, y - d + 6), (x + 1, y - d + h - 7), 2)
    pygame.draw.line(surf, shade(front_col, -30), (x + 6, y + h - 1), (x + w - 7, y + h - 1), 2)
    pygame.draw.rect(surf, ob.edge if style != "forest" else shade(ob.edge, -30), (x, y - d, w, h), 2, border_radius=8)


def _draw_circle_obstacle(surf, ob, style, rng):
    cx, cy, r = int(ob.x), int(ob.y), int(ob.w)
    d = CIRCLE_DEPTH
    sh, pad = soft_shadow((r * 2 + 16, r * 1.3), 120, 7)
    surf.blit(sh, (cx - r + 4 - pad, cy - r * 0.2 + 10 - pad))
    base = BOULDER_COLOR.get(style, ob.color)
    side = shade(base, -36)
    # cylinder body: the top disc extruded downwards
    pygame.draw.circle(surf, side, (cx, cy), r)
    pygame.draw.rect(surf, side, (cx - r, cy - d, r * 2, d))
    if style == "ruins":
        for k in range(-3, 4):
            fx = cx + int(k * r / 4)
            pygame.draw.line(surf, shade(side, -16), (fx, cy - d + 2), (fx, cy + int(r * 0.7)), 1)
    # top face with radial shading (light from upper-left)
    top_cy = cy - d
    steps = 10
    for i in range(steps):
        t = i / steps
        rr = int(r * (1 - t * 0.85))
        col = mix(shade(base, -6), shade(base, 44), t)
        ox, oy = int(-r * 0.22 * t), int(-r * 0.22 * t)
        pygame.draw.circle(surf, col, (cx + ox, top_cy + oy), rr)
    if style == "forest":
        for _ in range(6):
            a = rng.uniform(math.pi * 0.9, math.pi * 1.9)
            mr = rng.uniform(0.2, 0.7) * r
            pygame.draw.circle(surf, (66, 130, 58), (int(cx + math.cos(a) * mr), int(top_cy + math.sin(a) * mr)), rng.randint(5, 10))
    elif style == "quarry":
        pygame.draw.arc(surf, shade(base, -40), (cx - r * 0.6, top_cy - r * 0.5, r * 1.2, r), 0.3, 2.2, 2)
    elif style == "ruins":
        pygame.draw.circle(surf, (140, 110, 255), (cx, top_cy), int(r * 0.55), 2)
        for i in range(8):
            a = i / 8 * math.pi * 2
            _rune(surf, cx + math.cos(a) * r * 0.75, top_cy + math.sin(a) * r * 0.75, a, (160, 140, 240), rng)
    elif style == "neon":
        pygame.draw.circle(surf, (8, 8, 26), (cx, top_cy), int(r * 0.7))
        pygame.draw.circle(surf, ob.edge, (cx, top_cy), int(r * 0.45), 2)
    pygame.draw.circle(surf, ob.edge if style != "forest" else shade(ob.edge, -30), (cx, top_cy), r, 2)


def _neon_obstacle_glow(obstacles):
    """Additive glow layer for neon edges (reused by the per-frame pulse)."""
    layer = pygame.Surface((WIDTH, HEIGHT))
    for ob in obstacles:
        if ob.shape == "rect":
            pygame.draw.rect(layer, ob.edge, (ob.x, ob.y - RECT_DEPTH, ob.w, ob.h), 4, border_radius=8)
            pygame.draw.line(layer, shade(ob.edge, -80), (ob.x + 8, ob.y + ob.h), (ob.x + ob.w - 8, ob.y + ob.h), 3)
        else:
            pygame.draw.circle(layer, ob.edge, (int(ob.x), int(ob.y - CIRCLE_DEPTH)), int(ob.w), 4)
    return layer


# ─────────────────────────────────────────────
#  PUBLIC: STATIC LAYER
# ─────────────────────────────────────────────
def build_static_layer(game_map, style):
    seed = STYLES.index(style) * 1000 + 17
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    surf = GROUND_BUILDERS[style](rng, nrng)
    if style == "forest":
        # soft sun shafts
        rays = pygame.Surface((WIDTH, HEIGHT))
        for x0, wdt in ((420, 90), (980, 150), (1560, 70)):
            pygame.draw.polygon(rays, (16, 20, 6), [(x0, 0), (x0 + wdt, 0), (x0 + wdt - 420, HEIGHT), (x0 - 420 - wdt, HEIGHT)])
        surf.blit(blur_surface(rays, 16), (0, 0), special_flags=pygame.BLEND_ADD)
    _draw_decor(surf, style, game_map.decor)
    obs = sorted(game_map.obstacles, key=lambda o: o.y + (o.h if o.shape == "rect" else o.w))
    for ob in obs:
        if ob.shape == "rect":
            _draw_rect_obstacle(surf, ob, style, rng)
        else:
            _draw_circle_obstacle(surf, ob, style, rng)
    if style == "neon":
        glow = _neon_obstacle_glow(game_map.obstacles)
        surf.blit(blur_surface(glow, 6), (0, 0), special_flags=pygame.BLEND_ADD)
        surf.blit(glow, (0, 0), special_flags=pygame.BLEND_ADD)
    _border(surf, style, rng)
    tint = {"forest": (0, 10, 0), "quarry": (30, 6, 0), "ruins": (8, 0, 24), "neon": (0, 0, 10)}[style]
    surf.blit(vignette(190 if style in ("ruins", "neon") else 150, tint), (0, 0))
    if pygame.display.get_surface() is not None:
        surf = surf.convert()
    return surf


ART_VERSION = "1"     # bump to force every player's map cache to rebuild


def _cache_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "arena_fighters")


def cached_static_layer(game_map, style):
    """build_static_layer() with an on-disk PNG cache (first launch builds, later launches load).
    The cache key hashes this file and the map layout, so edits invalidate it automatically."""
    h = hashlib.md5(ART_VERSION.encode())
    try:
        with open(__file__, "rb") as f:
            h.update(f.read())
    except OSError:             # frozen .exe builds ship bytecode only
        pass
    h.update(repr([(o.shape, o.x, o.y, o.w, o.h, o.color, o.edge) for o in game_map.obstacles]).encode())
    h.update(repr(game_map.decor).encode())
    path = os.path.join(_cache_dir(), f"{style}_{h.hexdigest()[:12]}.png")
    try:
        if os.path.exists(path):
            surf = pygame.image.load(path)
            return surf.convert() if pygame.display.get_surface() is not None else surf
    except (pygame.error, OSError):
        pass
    surf = build_static_layer(game_map, style)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        for old in os.listdir(os.path.dirname(path)):
            if old.startswith(style + "_") and not old.endswith(".tmp.png"):
                os.remove(os.path.join(os.path.dirname(path), old))
        tmp = path + ".tmp.png"
        pygame.image.save(surf, tmp)
        os.replace(tmp, path)       # atomic: a half-written file is never loaded
    except (pygame.error, OSError):
        pass
    return surf


# ─────────────────────────────────────────────
#  PUBLIC: ANIMATED LAYER
# ─────────────────────────────────────────────
class _Mote:
    __slots__ = ("x", "y", "vx", "vy", "phase", "size", "color", "life")


class MapAnimator:
    """Ambient particles + pulsing lights drawn over the arena each frame."""

    def __init__(self, game_map, style):
        self.style = style
        self.map = game_map
        self.rng = random.Random(5)
        self.motes = [self._spawn(initial=True) for _ in range(self._count())]
        # pulsing lights are pre-rendered at a few brightness levels and cropped
        # to where they actually are, so animating them is a handful of small blits
        self.neon_glows = []        # [(pos, [surface per level])]
        self.rune_glow = None
        self.beam = None
        if style == "neon":
            layer = blur_surface(_neon_obstacle_glow(game_map.obstacles), 4)
            for ob in game_map.obstacles:
                if ob.shape == "rect":
                    r = pygame.Rect(ob.x, ob.y - RECT_DEPTH, ob.w, ob.h + RECT_DEPTH)
                else:
                    r = pygame.Rect(ob.x - ob.w, ob.y - CIRCLE_DEPTH - ob.w, ob.w * 2, ob.w * 2 + CIRCLE_DEPTH)
                r = r.inflate(40, 40).clip(layer.get_rect())
                self.neon_glows.append((r.topleft, _levels(layer.subsurface(r).copy(), 150)))
            self.beam = pygame.transform.scale(glow_sprite((0, 70, 90), 150, 1.0), (WIDTH, 60))
        if style == "ruins":
            g = pygame.Surface((520, 520))
            pygame.draw.circle(g, (60, 30, 150), (260, 260), 210, 10)
            pygame.draw.circle(g, (40, 20, 110), (260, 260), 120, 8)
            self.rune_glow = _levels(blur_surface(g, 8), 255)

    def _count(self):
        return {"forest": 46, "quarry": 60, "ruins": 40, "neon": 34}[self.style]

    def _spawn(self, initial=False):
        m = _Mote()
        rng = self.rng
        m.x = rng.uniform(0, WIDTH)
        m.y = rng.uniform(0, HEIGHT)
        m.phase = rng.uniform(0, math.pi * 2)
        m.life = rng.randint(200, 600)
        if self.style == "forest":
            if rng.random() < 0.7:          # fireflies
                m.vx, m.vy, m.size, m.color = rng.uniform(-0.4, 0.4), rng.uniform(-0.3, 0.3), rng.randint(5, 9), (200, 255, 120)
            else:                           # falling leaves
                m.vx, m.vy, m.size, m.color = rng.uniform(0.3, 1.0), rng.uniform(0.6, 1.2), -1, rng.choice([(120, 170, 60), (190, 160, 60)])
                if not initial:
                    m.y = -10
        elif self.style == "quarry":
            if rng.random() < 0.5:          # embers rising
                m.vx, m.vy, m.size, m.color = rng.uniform(-0.3, 0.3), rng.uniform(-1.2, -0.4), rng.randint(3, 6), (255, 140, 50)
                if not initial:
                    m.y = HEIGHT + 10
            else:                           # drifting dust
                m.vx, m.vy, m.size, m.color = rng.uniform(0.6, 1.6), rng.uniform(-0.1, 0.2), 0, (240, 200, 150)
        elif self.style == "ruins":
            m.vx, m.vy, m.size = rng.uniform(-0.2, 0.2), rng.uniform(-0.7, -0.2), rng.randint(5, 10)
            m.color = rng.choice([(150, 110, 255), (110, 160, 255), (220, 140, 255)])
            if not initial:
                m.y = HEIGHT + 10
        else:
            m.vx, m.vy, m.size = 0.0, rng.uniform(2.0, 5.0), rng.randint(3, 6)
            m.color = rng.choice([(0, 220, 255), (255, 60, 220), (120, 255, 200)])
            if not initial:
                m.y = -20
        return m

    def update(self):
        for i, m in enumerate(self.motes):
            m.phase += 0.05
            m.x += m.vx + (math.sin(m.phase) * 0.35 if self.style in ("forest", "ruins") else 0)
            m.y += m.vy
            m.life -= 1
            if m.life <= 0 or m.x < -30 or m.x > WIDTH + 30 or m.y < -30 or m.y > HEIGHT + 30:
                self.motes[i] = self._spawn()

    def draw_under(self, surface, tick):
        """Effects that belong on the floor (below players)."""
        if self.style == "ruins":
            a = 0.55 + 0.45 * math.sin(tick * 0.04)
            g = self.rune_glow[_level_index(a, len(self.rune_glow))]
            surface.blit(g, (WIDTH // 2 - 260, HEIGHT // 2 + 20 - 260), special_flags=pygame.BLEND_ADD)
        elif self.style == "neon":
            pulse = 0.5 + 0.5 * math.sin(tick * 0.06)
            if pulse > 0.08:
                for pos, levels in self.neon_glows:
                    surface.blit(levels[_level_index(pulse, len(levels))], pos, special_flags=pygame.BLEND_ADD)
            # scan beam sweeping down the arena
            sy = (tick * 4) % (HEIGHT + 300) - 150
            surface.blit(self.beam, (0, sy), special_flags=pygame.BLEND_ADD)
            for item in self.map.decor:
                if item[0] == "crystal":
                    _, x, y, col = item
                    _draw_crystal(surface, x, y, col, tick)

    def draw_over(self, surface, tick):
        """Ambient particles floating above everything."""
        for m in self.motes:
            if m.size == -1:     # leaf
                a = m.phase
                pts = [(m.x + math.cos(a) * 6, m.y + math.sin(a) * 3), (m.x - math.cos(a) * 6, m.y - math.sin(a) * 3),
                       (m.x + math.sin(a) * 2, m.y + math.cos(a) * 2)]
                pygame.draw.polygon(surface, m.color, pts)
            elif m.size == 0:    # dust speck
                surface.fill(m.color, (int(m.x), int(m.y), 2, 2))
            else:
                flick = 0.55 + 0.45 * math.sin(m.phase * 2.3)
                spr = glow_sprite(m.color, m.size, round(flick * 4) / 4)
                surface.blit(spr, (int(m.x) - m.size, int(m.y) - m.size), special_flags=pygame.BLEND_ADD)


GLOW_LEVELS = 8


def _levels(surf, peak):
    """The same glow at GLOW_LEVELS brightnesses (level k = peak·(k+1)/n)."""
    out = []
    for k in range(GLOW_LEVELS):
        g = surf.copy()
        v = int(peak * (k + 1) / GLOW_LEVELS)
        g.fill((v, v, v), special_flags=pygame.BLEND_MULT)
        out.append(g)
    return out


def _level_index(amount, n):
    return max(0, min(n - 1, int(round(amount * n)) - 1))


def _draw_crystal(surface, x, y, color, tick):
    pulse = 0.85 + 0.15 * math.sin(tick * 0.06 + x * 0.01)
    r = int(14 * pulse)
    spr = glow_sprite(color, r * 3, 0.8)
    surface.blit(spr, (x - r * 3, y - r * 3), special_flags=pygame.BLEND_ADD)
    pts = [(x, y - r * 2), (x + r, y), (x, y + r), (x - r, y)]
    pygame.draw.polygon(surface, shade(color, -40), pts)
    pygame.draw.polygon(surface, color, [(x, y - r * 2), (x + r, y), (x, y + r)])
    pygame.draw.polygon(surface, shade(color, 80), pts, 2)
