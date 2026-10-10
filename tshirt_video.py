#!/usr/bin/env python3
"""
tshirt_video.py - génère une pub verticale (1080x1920, 15 s) pour vendre un t-shirt.

Rythme "Fireship" : accroche glitch, révélation avec rebond, défilement des couleurs,
cartes gauche/droite qui se relaient, zoom sur le print, prix en "slam", compte à
rebours de stock, bouton d'appel à l'action. Musique + effets sonores synthétisés
(aucun fichier à fournir), ou ta propre musique avec --music.

Dépendances : Python 3.10+, pillow, numpy, ffmpeg dans le PATH.
    pip install pillow numpy
Usage :
    python tshirt_video.py                       # rend out/tshirt_ad.mp4
    python tshirt_video.py --preview             # 540x960, rapide pour tester
    python tshirt_video.py --photo mon_tshirt.png --logo logo.png --music beat.mp3
    python tshirt_video.py --config produit.json # surcharge les textes (voir CONFIG)

--photo : PNG détouré (fond transparent) de ton vrai t-shirt. S'il est donné, il remplace
          le t-shirt dessiné par le code (les couleurs ne défilent alors plus).
--logo  : PNG à imprimer sur la poitrine (sinon l'étoile + serrure du dossier).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# ───────────────────────────── CONFIG (tout se change ici) ─────────────────────────────
CONFIG = {
    "brand": "MA MARQUE",
    "product": "ATLAS TEE",
    "price": 39,
    "old_price": 59,
    "currency": "DT",
    "stock": 23,
    "cta": "COMMANDER",
    "cta_sub": "lien en bio",
    "hook": ["TON PLACARD", "A BESOIN", "DE CELUI-LÀ"],
    "features": [
        ("COTON 240 g", "épais, doux, ne se déforme pas"),
        ("COUPE OVERSIZE", "tombe parfaitement"),
        ("IMPRESSION DURABLE", "50 lavages sans fondre"),
    ],
    "zoom_text": "IMPRIMÉ. PAS COLLÉ.",
    "marquee": "NEW DROP  ·  NEW DROP  ·  ",
    "accent": (255, 61, 78),
    "bg": (10, 13, 20),
    # nom, couleur du tissu
    "colors": [
        ("NOIR", (20, 20, 24)),
        ("BLANC", (236, 234, 228)),
        ("ROUGE", (196, 38, 54)),
        ("SABLE", (210, 192, 156)),
    ],
}

def find_ffmpeg():
    exe = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg introuvable. Lance : pip install imageio-ffmpeg")


FFMPEG = find_ffmpeg()
FPS = 30
DURATION = 15.0
BPM = 120
BEAT = 60.0 / BPM
OUT = Path("out")

# Scènes (secondes)
T_HOOK_END = 2.2
T_REVEAL_END = 6.0
T_FEAT_END = 10.2
T_ZOOM_END = 11.8


# ───────────────────────────── utilitaires d'animation ─────────────────────────────
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, t0, t1):
    return clamp((t - t0) / (t1 - t0))


def lerp(a, b, k):
    return a + (b - a) * k


def ease_out(k):
    return 1 - (1 - k) ** 3


def ease_in_out(k):
    return 3 * k * k - 2 * k**3


def ease_out_back(k, s=1.9):
    k -= 1
    return 1 + (s + 1) * k**3 + s * k**2


def bounce(k):
    n, d = 7.5625, 2.75
    if k < 1 / d:
        return n * k * k
    if k < 2 / d:
        k -= 1.5 / d
        return n * k * k + 0.75
    if k < 2.5 / d:
        k -= 2.25 / d
        return n * k * k + 0.9375
    k -= 2.625 / d
    return n * k * k + 0.984375


def mix(c1, c2, k):
    return tuple(int(lerp(a, b, k)) for a, b in zip(c1, c2))


def luminance(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


# ───────────────────────────── polices ─────────────────────────────
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]
FONT_PATH = next((p for p in FONT_CANDIDATES if Path(p).exists()), None)


@lru_cache(maxsize=256)
def font(size: int):
    size = max(8, int(size))
    if FONT_PATH:
        return ImageFont.truetype(FONT_PATH, size)
    return ImageFont.load_default(size)


# ───────────────────────────── moteur de dessin ─────────────────────────────
class Ctx:
    """Échelle de rendu : on dessine en 1080x1920 logique, on réduit en preview."""

    W, H = 1080, 1920


def text_layer(txt, size, fill, stroke=0, stroke_fill=(0, 0, 0), tracking=0):
    f = font(size)
    if tracking:
        widths = [f.getlength(ch) + tracking for ch in txt]
        w = int(sum(widths)) + stroke * 2 + 8
    else:
        w = int(f.getlength(txt)) + stroke * 2 + 8
    h = int(size * 1.35) + stroke * 2
    im = Image.new("RGBA", (max(w, 1), h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if tracking:
        x = stroke + 4
        for ch, cw in zip(txt, widths):
            d.text((x, stroke), ch, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
            x += cw
    else:
        d.text((stroke + 4, stroke), txt, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
    return im


def paste_center(canvas, sprite, cx, cy, alpha=1.0, scale=1.0, rot=0.0, sx=1.0):
    if alpha <= 0.01 or scale <= 0.01:
        return
    w, h = sprite.size
    nw, nh = max(1, int(w * scale * sx)), max(1, int(h * scale))
    sp = sprite.resize((nw, nh), Image.BILINEAR) if (nw, nh) != (w, h) else sprite
    if abs(rot) > 0.05:
        sp = sp.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 0.999:
        a = sp.getchannel("A").point(lambda v: int(v * alpha))
        sp = sp.copy()
        sp.putalpha(a)
    canvas.paste(sp, (int(cx - sp.width / 2), int(cy - sp.height / 2)), sp)


def draw_text(canvas, txt, cx, cy, size, fill=(255, 255, 255), stroke=0, stroke_fill=(0, 0, 0),
              alpha=1.0, scale=1.0, rot=0.0, tracking=0, sx=1.0, max_w=1000):
    layer = text_layer(txt, size, fill, stroke, stroke_fill, tracking)
    if layer.width > max_w:                       # texte trop long : on réduit pour qu'il tienne
        layer = layer.resize((max_w, max(1, int(layer.height * max_w / layer.width))), Image.LANCZOS)
    paste_center(canvas, layer, cx, cy, alpha, scale, rot, sx)


def glitch_text(canvas, txt, cx, cy, size, amount, **kw):
    """Texte avec séparation RVB + décalages horizontaux, façon glitch."""
    if amount <= 0.02:
        draw_text(canvas, txt, cx, cy, size, **kw)
        return
    off = int(14 * amount)
    for dx, col in ((-off, (255, 40, 80)), (off, (40, 230, 255))):
        draw_text(canvas, txt, cx + dx, cy, size, fill=col, alpha=0.8, **{k: v for k, v in kw.items() if k not in ("fill", "alpha")})
    draw_text(canvas, txt, cx + int(np.random.randint(-6, 7) * amount), cy, size, **kw)


@lru_cache(maxsize=8)
def radial_glow(radius: int, color, strength=1.0):
    n = radius * 2
    yy, xx = np.mgrid[0:n, 0:n]
    d = np.sqrt((xx - radius) ** 2 + (yy - radius) ** 2) / radius
    a = np.clip(1 - d, 0, 1) ** 2.2 * 255 * strength
    arr = np.zeros((n, n, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = a.astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


# ───────────────────────────── logo & t-shirt ─────────────────────────────
def make_logo(size: int, fg) -> Image.Image:
    """Étoile à 8 branches avec une serrure découpée au milieu."""
    S = size * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    half = S * 0.355
    d.rectangle([c - half, c - half, c + half, c + half], fill=fg)
    r = S * 0.5
    d.polygon([(c, c - r), (c + r, c), (c, c + r), (c - r, c)], fill=fg)
    # serrure : cercle + trapèze, découpés
    cut = Image.new("L", (S, S), 0)
    cd = ImageDraw.Draw(cut)
    cr = S * 0.065
    cd.ellipse([c - cr, c - S * 0.04 - cr, c + cr, c - S * 0.04 + cr], fill=255)
    cd.polygon([(c - S * 0.026, c + S * 0.0), (c + S * 0.026, c + S * 0.0),
                (c + S * 0.052, c + S * 0.12), (c - S * 0.052, c + S * 0.12)], fill=255)
    im.putalpha(ImageChops.subtract(im.getchannel("A"), cut))
    return im.resize((size, size), Image.LANCZOS)


def load_logo(path: str | None, size: int, fg) -> Image.Image:
    if path:
        im = Image.open(path).convert("RGBA")
        im.thumbnail((size, size), Image.LANCZOS)
        return im
    return make_logo(size, fg)


SHIRT_PTS = [(30, 12), (40, 9), (50, 14), (60, 9), (70, 12), (95, 28), (86, 43), (74, 37),
             (74, 93), (26, 93), (26, 37), (14, 43), (5, 28)]


def make_shirt(color, logo_path=None, accent=(255, 61, 78), size=760) -> Image.Image:
    """T-shirt dessiné : forme + ombrage numpy + col + logo sur la poitrine."""
    SS = 2
    N = size * SS
    mask = Image.new("L", (N, N), 0)
    pts = [(x / 100 * N, y / 100 * N) for x, y in SHIRT_PTS]
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1.2 * SS))
    m = np.asarray(mask, np.float32) / 255.0

    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32) / N
    shade = 1.0 - 0.18 * np.abs(xx - 0.5) * 2                      # bords plus sombres
    shade *= 1.0 - 0.10 * np.clip((yy - 0.55) * 2, 0, 1)           # bas plus sombre
    folds = 0.035 * np.sin(xx * 38 + yy * 9) * np.clip((yy - 0.3) * 3, 0, 1)
    folds += 0.03 * np.sin(yy * 55 - xx * 6) * np.clip(1 - np.abs(xx - 0.5) * 3, 0, 1)
    shade += folds
    sleeve = ((yy < 0.45) & ((xx < 0.27) | (xx > 0.73))).astype(np.float32)
    shade *= 1.0 - 0.10 * sleeve
    rgb = np.clip(np.array(color, np.float32)[None, None, :] * shade[..., None], 0, 255)

    arr = np.zeros((N, N, 4), np.uint8)
    arr[..., :3] = rgb.astype(np.uint8)
    arr[..., 3] = (m * 255).astype(np.uint8)
    im = Image.fromarray(arr, "RGBA")

    # col
    d = ImageDraw.Draw(im)
    dark = tuple(int(v * 0.55) for v in color)
    d.ellipse([N * 0.395, N * 0.055, N * 0.605, N * 0.2], fill=dark)
    inner = tuple(int(v * 0.35) for v in color)
    d.ellipse([N * 0.42, N * 0.045, N * 0.58, N * 0.16], fill=(0, 0, 0, 0))
    d.arc([N * 0.395, N * 0.055, N * 0.605, N * 0.2], 0, 180, fill=inner, width=int(N * 0.008))

    # logo poitrine
    fg = (22, 24, 32) if luminance(color) > 140 else accent
    logo = load_logo(logo_path, int(N * 0.26), fg)
    im.alpha_composite(logo, (int(N * 0.5 - logo.width / 2), int(N * 0.40)))
    return im.resize((size, size), Image.LANCZOS)


@lru_cache(maxsize=1)
def shirt_shadow():
    im = Image.new("RGBA", (900, 200), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([100, 60, 800, 150], fill=(0, 0, 0, 170))
    return im.filter(ImageFilter.GaussianBlur(26))


# ───────────────────────────── fond, post-traitement ─────────────────────────────
class Background:
    def __init__(self, cfg):
        self.cfg = cfg
        W, H = Ctx.W, Ctx.H
        yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        top = np.array(mix(cfg["bg"], (40, 20, 34), 0.35), np.float32)
        bot = np.array(cfg["bg"], np.float32)
        self.grad = np.broadcast_to(top * (1 - yy) + bot * yy, (H, W, 3)).astype(np.uint8)
        # bandes de texte défilantes
        f = font(210)
        strip_txt = cfg["marquee"] * 6
        self.strip_w = int(f.getlength(strip_txt)) + 40
        strip = Image.new("RGBA", (self.strip_w, 280), (0, 0, 0, 0))
        ImageDraw.Draw(strip).text((20, 10), strip_txt, font=f, fill=(0, 0, 0, 0),
                                   stroke_width=3, stroke_fill=(255, 255, 255, 255))
        a = strip.getchannel("A").point(lambda v: int(v * 0.10))
        strip.putalpha(a)
        self.strip = strip
        self.period = int(f.getlength(cfg["marquee"]))
        rng = np.random.default_rng(7)
        self.noise = [rng.normal(0, 9, (H // 2, W // 2)).astype(np.float32) for _ in range(6)]
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.7)) ** 2)
        self.vig = (1 - np.clip(d - 0.35, 0, 1) * 0.75)[..., None]

    def frame(self, t, beat_pulse, hue_boost=0.0):
        im = Image.fromarray(self.grad, "RGB").convert("RGBA")
        W = Ctx.W
        for i, (y, speed) in enumerate(((260, 140), (560, -180), (1500, 120), (1780, -160))):
            off = int(t * speed) % self.period
            seg = self.strip.crop((off, 0, off + W, 280)) if speed > 0 else \
                self.strip.crop((self.period - off, 0, self.period - off + W, 280))
            im.alpha_composite(seg, (0, y))
        glow = radial_glow(900, self.cfg["accent"], 0.22 + 0.25 * beat_pulse + hue_boost)
        im.paste(glow, (Ctx.W // 2 - 900, Ctx.H // 2 - 900 + 80), glow)
        return im

    def post(self, im, frame_idx, shake=0.0, aberration=0.0, flash=0.0):
        arr = np.asarray(im.convert("RGB"), np.float32)
        arr *= self.vig
        n = self.noise[frame_idx % len(self.noise)]
        n = np.repeat(np.repeat(n, 2, 0), 2, 1)
        arr += n[..., None]
        if aberration > 0.01:
            s = int(10 * aberration)
            arr[..., 0] = np.roll(arr[..., 0], s, axis=1)
            arr[..., 2] = np.roll(arr[..., 2], -s, axis=1)
        if shake > 0.01:
            dx, dy = np.random.randint(-int(shake), int(shake) + 1, 2)
            arr = np.roll(np.roll(arr, dx, axis=1), dy, axis=0)
        if flash > 0.01:
            arr = arr + (255 - arr) * flash
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


# ───────────────────────────── clip 3D (rendu Blender) ─────────────────────────────
class Clip:
    """Lit une vidéo image par image (via ffmpeg), recadrée en 1080x1920. Garde la dernière à la fin."""

    def __init__(self, path):
        cmd = [FFMPEG, "-loglevel", "error", "-i", str(path), "-vf",
               f"scale={Ctx.W}:{Ctx.H}:force_original_aspect_ratio=increase,crop={Ctx.W}:{Ctx.H},fps={FPS}",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        self.last = Image.new("RGB", (Ctx.W, Ctx.H), (0, 0, 0))
        self.n = Ctx.W * Ctx.H * 3

    def next(self):
        buf = self.p.stdout.read(self.n) if self.p else b""
        if len(buf) == self.n:
            self.last = Image.frombytes("RGB", (Ctx.W, Ctx.H), buf)
        return self.last


@lru_cache(maxsize=1)
def top_bottom_shade():
    """Dégradé sombre en haut et en bas pour que les textes restent lisibles sur la 3D."""
    y = np.linspace(0, 1, Ctx.H, dtype=np.float32)
    a = np.clip(1 - y / 0.22, 0, 1) ** 1.5 * 200 + np.clip((y - 0.72) / 0.28, 0, 1) ** 1.3 * 230
    arr = np.zeros((Ctx.H, Ctx.W, 4), np.uint8)
    arr[..., 3] = a.astype(np.uint8)[:, None]
    return Image.fromarray(arr, "RGBA")


# ───────────────────────────── la vidéo ─────────────────────────────
class Ad:
    def __init__(self, cfg, photo=None, logo=None, clip3d=None):
        self.cfg = cfg
        self.clip = Clip(clip3d) if clip3d else None
        self.bg = Background(cfg)
        self.accent = tuple(cfg["accent"])
        self.photo = Image.open(photo).convert("RGBA") if photo else None
        if self.photo:
            self.photo.thumbnail((760, 760), Image.LANCZOS)
        self.sprites = {}
        for name, col in cfg["colors"]:
            self.sprites[name] = self.photo or make_shirt(col, logo, self.accent)
        self.names = [n for n, _ in cfg["colors"]]
        self.logo_path = logo
        self.big_logo = load_logo(logo, 300, self.accent)

    # -- éléments communs -------------------------------------------------
    def shirt(self, im, t, cx, cy, scale, rot=0.0, sx=1.0, color_idx=0, alpha=1.0, shadow=True):
        name = self.names[color_idx % len(self.names)]
        if shadow:
            paste_center(im, shirt_shadow(), cx, cy + 380 * scale, 0.9 * alpha, scale, 0)
        paste_center(im, self.sprites[name], cx, cy, alpha, scale, rot, sx)

    def card(self, im, title, sub, cx, cy, k, side):
        """Carte de fonctionnalité qui glisse depuis le côté (k: 0→1 entrée)."""
        W = 580
        x_off = (1 - ease_out_back(k, 1.2)) * (700 * side)
        card = Image.new("RGBA", (W, 250), (0, 0, 0, 0))
        d = ImageDraw.Draw(card)
        d.rounded_rectangle([0, 0, W - 1, 249], 28, fill=(14, 18, 28, 235),
                            outline=self.accent + (255,), width=4)
        d.rounded_rectangle([0, 0, 22, 249], 12, fill=self.accent + (255,))
        card.alpha_composite(text_layer(title, 44, (255, 255, 255)), (46, 56))
        sl = text_layer(sub, 32, (190, 198, 214))
        if sl.width > W - 70:
            sl = sl.resize((W - 70, int(sl.height * (W - 70) / sl.width)), Image.LANCZOS)
        card.alpha_composite(sl, (48, 145))
        paste_center(im, card, cx + x_off, cy, alpha=clamp(k * 3))

    # -- scènes -----------------------------------------------------------
    def scene_hook(self, im, t):
        lines = self.cfg["hook"]
        step = 0.42
        amount = 0.0
        for i, line in enumerate(lines):
            t0 = 0.15 + i * step
            k = prog(t, t0, t0 + 0.22)
            if k <= 0:
                continue
            pop = ease_out_back(k, 2.6)
            amt = clamp(1 - prog(t, t0, t0 + 0.35)) * 0.9
            col = self.accent if i == len(lines) - 1 else (255, 255, 255)
            glitch_text(im, line, Ctx.W / 2, 700 + i * 220, 104, amt, fill=col, stroke=6,
                        stroke_fill=(0, 0, 0), scale=pop, tracking=2)
        # flèche qui pulse vers le bas
        k = prog(t, 1.5, 1.8)
        if k > 0:
            bob = math.sin(t * 14) * 18
            draw_text(im, "↓", Ctx.W / 2, 1480 + bob, 220, fill=self.accent, alpha=k, stroke=4)

    def scene_reveal(self, im, t):
        k = prog(t, T_HOOK_END, T_HOOK_END + 0.9)
        y = lerp(-500, 980, bounce(k))
        squeeze = 1 + 0.18 * math.sin(clamp(k * 3.2, 0, 3.2) * math.pi) * (1 - k)
        # couleurs qui défilent avec petit pop
        local = t - T_HOOK_END - 1.0
        idx = max(0, int(local / 0.7)) if local > 0 else 0
        pop = 1.0
        if local > 0:
            pop = 1 + 0.12 * math.exp(-((local % 0.7) * 11))
        wobble = math.sin(t * 2.2) * 4 if k >= 1 else 0
        self.shirt(im, t, Ctx.W / 2, y, 1.05 * pop, rot=wobble, sx=squeeze, color_idx=idx)
        # pastilles de couleurs
        cols = self.cfg["colors"]
        for i, (name, col) in enumerate(cols):
            x = Ctx.W / 2 + (i - (len(cols) - 1) / 2) * 120
            kk = ease_out_back(prog(t, T_HOOK_END + 1.0 + i * 0.1, T_HOOK_END + 1.3 + i * 0.1))
            active = i == idx % len(cols)
            r = 38 * kk * (1.25 if active else 1.0)
            if r > 1:
                d = ImageDraw.Draw(im)
                y0 = 1500
                if active:
                    d.ellipse([x - r - 8, y0 - r - 8, x + r + 8, y0 + r + 8], outline=(255, 255, 255), width=5)
                d.ellipse([x - r, y0 - r, x + r, y0 + r], fill=col, outline=(255, 255, 255), width=2)
        if local > 0:
            draw_text(im, self.names[idx % len(self.names)], Ctx.W / 2, 1620, 64, stroke=4, tracking=10,
                      alpha=clamp(local * 4))
        # titre du produit
        kt = ease_out_back(prog(t, T_HOOK_END + 0.6, T_HOOK_END + 1.1))
        draw_text(im, self.cfg["brand"], Ctx.W / 2 - (1 - kt) * 900, 250, 44, fill=self.accent, tracking=14, stroke=2)
        draw_text(im, self.cfg["product"], Ctx.W / 2 + (1 - kt) * 900, 345, 120, stroke=6, tracking=4)

    def scene_features(self, im, t):
        feats = self.cfg["features"]
        span = (T_FEAT_END - T_REVEAL_END) / len(feats)
        i = min(len(feats) - 1, int((t - T_REVEAL_END) / span))
        t0 = T_REVEAL_END + i * span
        side = 1 if i % 2 == 0 else -1           # carte à droite → t-shirt à gauche
        shirt_x_target = Ctx.W / 2 - 230 * side
        prev_x = Ctx.W / 2 if i == 0 else Ctx.W / 2 + 230 * side
        kx = ease_in_out(prog(t, t0, t0 + 0.35))
        sx_ = lerp(prev_x, shirt_x_target, kx)
        tilt = -6 * side * math.sin(kx * math.pi) + math.sin(t * 2) * 2
        self.shirt(im, t, sx_, 1000, 0.82, rot=tilt, color_idx=int((t - T_REVEAL_END) / span))
        title, sub = feats[i]
        ke = prog(t, t0 + 0.1, t0 + 0.55)
        cx = Ctx.W / 2 + 270 * side
        cx = min(max(cx, 300), Ctx.W - 300)
        self.card(im, title, sub, cx, 560 if side > 0 else 1480, ke, side)
        # numéro géant
        draw_text(im, f"0{i + 1}", Ctx.W / 2 - 330 * side if side > 0 else Ctx.W / 2 + 330, 330 if side > 0 else 1700,
                  230, fill=self.accent, alpha=0.9 * ease_out(prog(t, t0, t0 + 0.3)), stroke=0)
        # barre de progression des features
        for j in range(len(feats)):
            on = j <= i
            ImageDraw.Draw(im).rounded_rectangle([Ctx.W / 2 - 150 + j * 108, 120, Ctx.W / 2 - 150 + j * 108 + 90, 132],
                                                 6, fill=self.accent if on else (70, 76, 92))

    def scene_zoom(self, im, t):
        k = ease_in_out(prog(t, T_FEAT_END, T_FEAT_END + 0.5))
        k_out = ease_in_out(prog(t, T_ZOOM_END - 0.35, T_ZOOM_END))
        z = lerp(0.82, 2.7, k) * lerp(1, 0.9, k_out)
        cx = lerp(Ctx.W / 2 - 230, Ctx.W / 2, k)
        cy = lerp(1000, 1000 - 470 * 2.7 / 2 * 0.95, k)
        pulse = 0.5 + 0.5 * math.sin((t - T_FEAT_END) * 9)
        glow = radial_glow(500, self.accent, 0.55 + 0.35 * pulse)
        gx, gy = Ctx.W / 2, 880
        if k > 0.5:
            im.paste(glow, (int(gx - 500), int(gy - 500)), glow)
        self.shirt(im, t, cx, cy, z, shadow=False, color_idx=1)
        kt = ease_out_back(prog(t, T_FEAT_END + 0.35, T_FEAT_END + 0.8))
        draw_text(im, self.cfg["zoom_text"], Ctx.W / 2, 1560, 72, stroke=6, scale=kt, alpha=1 - k_out)

    def scene_price(self, im, t, draw_shirt=True):
        T0 = T_ZOOM_END
        kin = ease_out(prog(t, T0, T0 + 0.5))
        if draw_shirt:
            self.shirt(im, t, Ctx.W / 2, lerp(1400, 560, kin), lerp(0.4, 0.72, kin), rot=math.sin(t * 3) * 3,
                       color_idx=0, shadow=True)
        # ancien prix barré
        cur = self.cfg["currency"]
        ko = ease_out_back(prog(t, T0 + 0.5, T0 + 0.8))
        draw_text(im, f"{self.cfg['old_price']} {cur}", Ctx.W / 2, 1000, 90, fill=(150, 156, 172), scale=ko)
        kline = prog(t, T0 + 0.85, T0 + 1.05)
        if kline > 0:
            w = 330 * kline
            ImageDraw.Draw(im).line([Ctx.W / 2 - w / 2, 1000, Ctx.W / 2 + w / 2, 1000], fill=self.accent, width=10)
        # prix : slam
        kp = prog(t, T0 + 1.05, T0 + 1.35)
        if kp > 0:
            s = lerp(3.2, 1.0, ease_out(kp))
            shake = (1 - kp) * 10
            draw_text(im, f"{self.cfg['price']} {cur}", Ctx.W / 2 + np.random.uniform(-shake, shake), 1150,
                      210, fill=self.accent, stroke=8, scale=s, alpha=clamp(kp * 4))
        # stock qui descend
        ks = prog(t, T0 + 1.6, DURATION - 0.3)
        stock = int(lerp(self.cfg["stock"], self.cfg["stock"] - 4, ks))
        if t > T0 + 1.5:
            blink = 0.65 + 0.35 * math.sin(t * 8)
            draw_text(im, f"PLUS QUE {stock} PIÈCES", Ctx.W / 2, 1300, 58, fill=(255, 210, 90), alpha=blink, stroke=3, tracking=3)
        # bouton CTA
        kb = ease_out_back(prog(t, T0 + 1.9, T0 + 2.3))
        if kb > 0:
            pulse = 1 + 0.05 * math.sin(t * 9)
            btn = Image.new("RGBA", (760, 190), (0, 0, 0, 0))
            d = ImageDraw.Draw(btn)
            d.rounded_rectangle([0, 0, 759, 189], 95, fill=self.accent + (255,))
            btn.alpha_composite(text_layer(self.cfg["cta"], 80, (255, 255, 255), tracking=4),
                                (int(380 - font(80).getlength(self.cfg["cta"]) / 2 - 14), 28))
            btn.alpha_composite(text_layer("▶ " + self.cfg["cta_sub"], 34, (255, 235, 238)), (210, 125))
            paste_center(im, btn, Ctx.W / 2, 1560, scale=kb * pulse)
        # logo en bas
        paste_center(im, self.big_logo, Ctx.W / 2, 1780, alpha=ease_out(prog(t, T0 + 2.2, T0 + 2.6)), scale=0.34)

    # -- flashs / transitions --------------------------------------------
    def fx(self, t):
        """(flash, secousse, aberration) selon les cuts musicaux."""
        cuts = [0.0, T_HOOK_END, T_REVEAL_END, T_FEAT_END, T_ZOOM_END, T_ZOOM_END + 1.05 + 0.3]
        flash = shake = ab = 0.0
        for c in cuts:
            d = t - c
            if 0 <= d < 0.35:
                flash = max(flash, math.exp(-d * 14) * (0.9 if c == T_HOOK_END else 0.45))
                ab = max(ab, math.exp(-d * 9))
            if c == T_ZOOM_END + 1.35 and 0 <= d < 0.3:
                shake = 22 * math.exp(-d * 10)
        kb = (t % BEAT) / BEAT
        ab = max(ab, 0.25 * math.exp(-kb * 6))
        return flash, shake, ab

    def render_frame_3d(self, i, t):
        src = self.clip.next()
        if t < T_HOOK_END:                                     # 3D floutée et sombre derrière l'accroche
            k = ease_in_out(prog(t, T_HOOK_END - 0.5, T_HOOK_END))
            blur = src.filter(ImageFilter.GaussianBlur(14 * (1 - k) + 0.01))
            im = Image.blend(Image.new("RGB", src.size, (0, 0, 0)), blur, 0.35 + 0.65 * k).convert("RGBA")
        elif T_FEAT_END <= t < T_ZOOM_END:                     # zoom dans l'image 3D
            k = ease_in_out(prog(t, T_FEAT_END, T_FEAT_END + 0.6)) * (1 - ease_in_out(prog(t, T_ZOOM_END - 0.3, T_ZOOM_END)))
            z = 1 + 0.45 * k
            w, h = int(Ctx.W / z), int(Ctx.H / z)
            cx, cy = Ctx.W // 2, int(Ctx.H * 0.47)
            box = (cx - w // 2, max(0, cy - h // 2), cx + w // 2, max(0, cy - h // 2) + h)
            im = src.crop(box).resize((Ctx.W, Ctx.H), Image.BILINEAR).convert("RGBA")
        elif t >= T_ZOOM_END:                                  # prix : 3D assombrie
            k = ease_out(prog(t, T_ZOOM_END, T_ZOOM_END + 0.5))
            im = Image.blend(src, src.filter(ImageFilter.GaussianBlur(8)), k)
            im = Image.blend(Image.new("RGB", src.size, (0, 0, 0)), im, 1 - 0.55 * k).convert("RGBA")
        else:
            im = src.convert("RGBA")
        im.alpha_composite(top_bottom_shade())

        if t < T_HOOK_END:
            self.scene_hook(im, t)
        elif t < T_REVEAL_END:
            kt = ease_out_back(prog(t, T_HOOK_END + 0.2, T_HOOK_END + 0.7))
            draw_text(im, self.cfg["brand"], Ctx.W / 2 - (1 - kt) * 900, 150, 44, fill=self.accent, tracking=14, stroke=2)
            draw_text(im, self.cfg["product"], Ctx.W / 2 + (1 - kt) * 900, 250, 104, stroke=6, tracking=2)
            kb = ease_out(prog(t, T_HOOK_END + 1.2, T_HOOK_END + 1.6))
            draw_text(im, self.cfg.get("reveal_sub", "100 % COTON · IMPRIMÉ À LA MAIN"), Ctx.W / 2, 1760 + (1 - kb) * 120,
                      42, fill=(230, 230, 236), alpha=kb, tracking=4, stroke=2)
        elif t < T_FEAT_END:
            feats = self.cfg["features"]
            span = (T_FEAT_END - T_REVEAL_END) / len(feats)
            j = min(len(feats) - 1, int((t - T_REVEAL_END) / span))
            t0 = T_REVEAL_END + j * span
            side = 1 if j % 2 == 0 else -1
            if j > 0:                                          # la carte précédente part de l'autre côté
                ko = prog(t, t0, t0 + 0.3)
                if ko < 1:
                    pt, ps = feats[j - 1]
                    self.card(im, pt, ps, Ctx.W / 2 - 160 * side, 1700, 1 - ko, -side)
            title, sub = feats[j]
            self.card(im, title, sub, Ctx.W / 2 + 160 * side, 1700, prog(t, t0 + 0.08, t0 + 0.5), side)
            draw_text(im, f"0{j + 1}", Ctx.W / 2 - 330 * side, 1470, 150, fill=self.accent,
                      alpha=0.95 * ease_out(prog(t, t0, t0 + 0.3)))
            for q in range(len(feats)):
                ImageDraw.Draw(im).rounded_rectangle([Ctx.W / 2 - 150 + q * 108, 120, Ctx.W / 2 - 150 + q * 108 + 90, 132],
                                                     6, fill=self.accent if q <= j else (70, 76, 92))
        elif t < T_ZOOM_END:
            kt = ease_out_back(prog(t, T_FEAT_END + 0.3, T_FEAT_END + 0.7))
            draw_text(im, self.cfg["zoom_text"], Ctx.W / 2, 1720, 80, stroke=6, scale=kt,
                      alpha=1 - prog(t, T_ZOOM_END - 0.3, T_ZOOM_END))
        else:
            self.scene_price(im, t, draw_shirt=False)
        return im

    def render_frame(self, i):
        t = i / FPS
        beat_pulse = math.exp(-((t % BEAT) / BEAT) * 5)
        if self.clip:
            im = self.render_frame_3d(i, t)
            ImageDraw.Draw(im).rectangle([0, 0, Ctx.W * t / DURATION, 8], fill=self.accent)
            flash, shake, ab = self.fx(t)
            return self.bg.post(im, i, shake=shake, aberration=ab * 0.6, flash=flash * 0.7)
        im = self.bg.frame(t, beat_pulse, hue_boost=0.15 if T_FEAT_END <= t < T_ZOOM_END else 0)
        if t < T_HOOK_END:
            self.scene_hook(im, t)
        elif t < T_REVEAL_END:
            self.scene_reveal(im, t)
        elif t < T_FEAT_END:
            self.scene_features(im, t)
        elif t < T_ZOOM_END:
            self.scene_zoom(im, t)
        else:
            self.scene_price(im, t)
        # barre de progression
        ImageDraw.Draw(im).rectangle([0, 0, Ctx.W * t / DURATION, 8], fill=self.accent)
        flash, shake, ab = self.fx(t)
        return self.bg.post(im, i, shake=shake, aberration=ab, flash=flash)


# ───────────────────────────── audio synthétisé ─────────────────────────────
def synth_audio(path: Path, sr=44100):
    n = int(DURATION * sr)
    out = np.zeros(n, np.float32)
    rng = np.random.default_rng(3)

    def add(start, sig, gain=1.0):
        s = int(start * sr)
        e = min(n, s + len(sig))
        if s < n:
            out[s:e] += sig[: e - s] * gain

    def tt(d):
        return np.arange(int(d * sr)) / sr

    kick_t = tt(0.3)
    kick = np.sin(2 * np.pi * (45 * kick_t + 70 * (1 - np.exp(-kick_t * 25)) / 25 * 25)) * np.exp(-kick_t * 12)
    hat_t = tt(0.06)
    hat = rng.normal(0, 1, len(hat_t)).astype(np.float32) * np.exp(-hat_t * 70)
    snare_t = tt(0.2)
    snare = (rng.normal(0, 1, len(snare_t)) * np.exp(-snare_t * 20) + np.sin(2 * np.pi * 190 * snare_t) * np.exp(-snare_t * 25))
    bass_notes = [55.0, 55.0, 65.41, 49.0]

    beat = 0
    t = 0.0
    while t < DURATION - 0.01:
        add(t, kick, 0.9)
        add(t + BEAT / 2, hat, 0.18)
        if beat % 2 == 1:
            add(t, snare, 0.35)
        bt = tt(BEAT * 0.9)
        f0 = bass_notes[(beat // 4) % 4]
        bass = np.sign(np.sin(2 * np.pi * f0 * bt)) * 0.5 + np.sin(2 * np.pi * f0 * bt) * 0.5
        add(t, bass * np.exp(-bt * 2.5), 0.22)
        if t > T_FEAT_END:                                    # arpège qui monte pour la fin
            at = tt(BEAT / 2)
            add(t + BEAT / 2, np.sin(2 * np.pi * f0 * 4 * at) * np.exp(-at * 9), 0.12)
        t += BEAT
        beat += 1

    def whoosh(start, d=0.45, gain=0.35, up=True):
        w = tt(d)
        noise = rng.normal(0, 1, len(w)).astype(np.float32)
        env = (w / d) ** 2 if up else (1 - w / d) ** 2
        sig = np.convolve(noise, np.ones(40) / 40, mode="same") * env
        add(start, sig, gain)

    for c in (T_HOOK_END, T_REVEAL_END, T_FEAT_END, T_ZOOM_END):
        whoosh(c - 0.4)
    for i in range(3):                                         # cartes
        whoosh(T_REVEAL_END + i * (T_FEAT_END - T_REVEAL_END) / 3, 0.25, 0.2, up=False)
    impact_t = tt(0.8)
    add(T_ZOOM_END + 1.05, np.sin(2 * np.pi * 38 * impact_t) * np.exp(-impact_t * 5) * 1.0 +
        rng.normal(0, 1, len(impact_t)) * np.exp(-impact_t * 18) * 0.5, 0.9)
    ding_t = tt(0.9)
    add(T_ZOOM_END + 1.9, (np.sin(2 * np.pi * 1320 * ding_t) + 0.5 * np.sin(2 * np.pi * 1980 * ding_t)) * np.exp(-ding_t * 5), 0.18)
    add(0.0, np.sin(2 * np.pi * 70 * tt(0.5)) * np.exp(-tt(0.5) * 6), 0.5)

    fade = np.ones(n, np.float32)
    k = int(0.6 * sr)
    fade[-k:] = np.linspace(1, 0, k)
    out = np.tanh(out * 1.4) * fade
    pcm = (out * 0.85 * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


# ───────────────────────────── export ─────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Pub vidéo verticale pour un t-shirt")
    ap.add_argument("--out", default="out/tshirt_ad.mp4")
    ap.add_argument("--config", help="JSON qui surcharge CONFIG")
    ap.add_argument("--photo", help="PNG détouré de ton t-shirt")
    ap.add_argument("--logo", help="PNG du logo à imprimer")
    ap.add_argument("--music", help="musique (mp3/wav) à la place du beat synthétisé")
    ap.add_argument("--preview", action="store_true", help="540x960, plus rapide")
    ap.add_argument("--silent", action="store_true", help="sans audio")
    ap.add_argument("--clip3d", help="vidéo 3D (rendu Blender) utilisée comme image principale")
    args = ap.parse_args()

    cfg = dict(CONFIG)
    if args.config:
        cfg.update(json.loads(Path(args.config).read_text(encoding="utf-8")))
        cfg["features"] = [tuple(f) for f in cfg["features"]]
        cfg["colors"] = [(n, tuple(c)) for n, c in cfg["colors"]]
    np.random.seed(1)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    ad = Ad(cfg, args.photo, args.logo, args.clip3d)

    audio = None
    if not args.silent:
        if args.music:
            audio = args.music
        else:
            audio = str(out.with_suffix(".beat.wav"))
            synth_audio(Path(audio))

    W, H = (540, 960) if args.preview else (Ctx.W, Ctx.H)
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if audio:
        cmd += ["-i", audio, "-map", "0:v", "-map", "1:a", "-af", f"afade=t=out:st={DURATION - 0.6}:d=0.6",
                "-c:a", "aac", "-b:a", "192k", "-t", str(DURATION)]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18" if not args.preview else "26",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    total = int(DURATION * FPS)
    for i in range(total):
        fr = ad.render_frame(i)
        if args.preview:
            fr = fr.resize((W, H), Image.BILINEAR)
        p.stdin.write(fr.tobytes())
        if i % 30 == 0:
            print(f"\r{i / total:4.0%}", end="", flush=True)
    p.stdin.close()
    p.wait()
    print(f"\rOK -> {out}")


if __name__ == "__main__":
    main()
