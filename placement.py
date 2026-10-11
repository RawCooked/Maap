#!/usr/bin/env python3
"""
placement.py - voir et préparer le placement des designs AVANT la 3D.

    python placement.py --gabarit
        -> design/GABARIT_zone_impression.png : 3000 x 3900 px = la zone d'impression exacte
           (30 x 39 cm, 100 px par cm). Dessine ton design à cette taille ; les repères sont
           sur un calque à part, à masquer avant l'export.

    python placement.py --front design/devant.png --back design/dos.png --color "#121212"
        -> out/apercu.png : le t-shirt à plat, devant et dos, avec les designs placés exactement
           comme dans la vidéo 3D.

Le placement est le même que celui de tshirt3d.py : zone de --print-size m de large (0,30),
centrée, dont le haut est à --print-top cm sous le col (7). Le PNG est étiré sur cette largeur,
sa hauteur suit ses proportions.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Même patron que tshirt3d/tshirt3d.py (en cm, origine au milieu du col, z vers le haut).
OUTLINE = [(-9.0, 0.0), (9.0, 0.0), (24.0, -4.0), (38.0, -16.0), (31.0, -27.0), (24.0, -22.0),
           (25.0, -72.0), (-25.0, -72.0), (-24.0, -22.0), (-31.0, -27.0), (-38.0, -16.0), (-24.0, -4.0)]
NECK_DIP = 7.0

COLORS = {
    "noir": "#121212", "blanc": "#EEECE6", "gris": "#8A8C90", "gris chiné": "#A7A9AC",
    "bleu marine": "#1C2340", "bleu": "#2B5DA8", "rouge": "#B3262E", "bordeaux": "#5E1A24",
    "vert": "#2F5D3A", "kaki": "#6B6B4A", "sable": "#D2C09C", "beige": "#E3D5BA", "rose": "#E8B4C0",
}

PX_PER_CM_GABARIT = 100


def font(size):
    for p in ("C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def parse_color(c: str) -> tuple[int, int, int]:
    c = COLORS.get(c.strip().lower(), c.strip())
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def outline_cm():
    """Contour avec l'encolure arrondie, comme dans la 3D."""
    pts = []
    for i, (x0, z0) in enumerate(OUTLINE):
        x1, z1 = OUTLINE[(i + 1) % len(OUTLINE)]
        n = 12 if i == 0 else 1
        for j in range(n):
            t = j / n
            x, z = x0 + (x1 - x0) * t, z0 + (z1 - z0) * t
            if i == 0:
                z -= NECK_DIP * math.sin(math.pi * t) * 0.35
            pts.append((x, z))
    return pts


def dashed_rect(d, box, color, width=3, dash=18):
    x0, y0, x1, y1 = box
    for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
        L = math.hypot(bx - ax, by - ay)
        n = max(1, int(L // (dash * 2)))
        for k in range(n + 1):
            t0, t1 = k * 2 * dash / L, min(1, (k * 2 + 1) * dash / L)
            if t0 >= 1:
                break
            d.line([ax + (bx - ax) * t0, ay + (by - ay) * t0, ax + (bx - ax) * t1, ay + (by - ay) * t1],
                   fill=color, width=width)


# ───────────────────────────── gabarit ─────────────────────────────
def make_gabarit(out: Path, print_size=0.30, height_cm=39.0):
    s = PX_PER_CM_GABARIT
    W, H = int(print_size * 100 * s), int(height_cm * s)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    guide = (0, 170, 255, 255)
    d.rectangle([0, 0, W - 1, H - 1], outline=guide, width=6)
    d.line([W / 2, 0, W / 2, H], fill=(0, 170, 255, 140), width=3)                        # centre
    f, fs = font(70), font(46)
    d.text((30, 20), f"ZONE D'IMPRESSION  {W // s} x {H // s} cm  ({W} x {H} px, 100 px/cm)", font=fs, fill=guide)
    d.text((30, 80), "haut de la zone = 7 cm sous le col", font=fs, fill=guide)
    # cœur : côté gauche de la personne = à droite de l'image quand on regarde le t-shirt de face
    cx0, cy0 = int(W / 2 + 4 * s), int(1 * s)
    heart = (cx0, cy0, cx0 + 10 * s, cy0 + 10 * s)
    dashed_rect(d, heart, (255, 80, 80, 255), 5)
    d.text((heart[0] + 15, heart[3] + 10), "CŒUR 10 x 10 cm", font=fs, fill=(255, 80, 80, 255))
    chest = (int(W / 2 - 12.5 * s), int(2 * s), int(W / 2 + 12.5 * s), int(2 * s + 12 * s))
    dashed_rect(d, chest, (255, 200, 0, 255), 4)
    d.text((chest[0] + 15, chest[3] + 10), "POITRINE / NUQUE 25 x 12 cm", font=fs, fill=(255, 200, 0, 255))
    full = (int(1.5 * s), int(1 * s), W - int(1.5 * s), H - int(2 * s))
    dashed_rect(d, full, (80, 220, 120, 255), 4)
    d.text((full[0] + 15, full[3] - 70), "PLEIN DEVANT / PLEIN DOS 27 x 36 cm", font=fs, fill=(80, 220, 120, 255))
    for cm in range(0, int(height_cm) + 1, 5):                                              # règle
        y = cm * s
        d.line([0, y, 60, y], fill=guide, width=4)
        d.text((70, y - 25), f"{cm} cm", font=fs, fill=guide)
    d.text((W / 2 + 20, H - 140), "CENTRE", font=f, fill=(0, 170, 255, 200))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


# ───────────────────────────── aperçu à plat ─────────────────────────────
def load_design(path):
    return Image.open(path).convert("RGBA") if path else None


def draw_shirt(design, color, s, title, print_size, print_top, mirror=False):
    """Un t-shirt à plat à l'échelle s (px/cm), avec le design posé dans la zone d'impression."""
    pad = 6
    W, H = int((76 + 2 * pad) * s), int((72 + NECK_DIP + 2 * pad + 6) * s)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ox, oy = W / 2, (pad + 6) * s                     # position du milieu du col

    def P(x, z):
        return (ox + x * s, oy - z * s)

    poly = [P(x, z) for x, z in outline_cm()]
    shirt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shirt).polygon(poly, fill=color + (255,))
    mask = shirt.getchannel("A")
    lum = 0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2]
    line = (255, 255, 255, 90) if lum < 128 else (0, 0, 0, 90)
    d = ImageDraw.Draw(shirt)
    d.line(poly + [poly[0]], fill=line, width=max(2, s // 4))
    # encolure : un petit arc pour montrer le col
    d.arc([ox - 9 * s, oy - 3 * s, ox + 9 * s, oy + 0.35 * NECK_DIP * 2 * s], 0, 180, fill=line, width=max(2, s // 5))

    w_cm = print_size * 100
    zone_top = -print_top
    if design is not None:
        dz = design.transpose(Image.FLIP_LEFT_RIGHT) if mirror else design
        h_cm = w_cm * dz.height / dz.width
        dz = dz.resize((int(w_cm * s), int(h_cm * s)), Image.LANCZOS)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        x0, y0 = P(-w_cm / 2, zone_top)
        layer.paste(dz, (int(x0), int(y0)), dz)
        a = Image.composite(layer.getchannel("A"), Image.new("L", (W, H), 0), mask)  # pas d'encre hors du tissu
        layer.putalpha(a)
        shirt.alpha_composite(layer)
    else:
        h_cm = 39
    # zone d'impression en pointillés + cotes
    x0, y0 = P(-w_cm / 2, zone_top)
    x1, y1 = P(w_cm / 2, zone_top - h_cm)
    dashed_rect(d, (x0, y0, x1, y1), (0, 170, 255, 230), max(2, s // 5), dash=max(6, s))
    fs = font(max(12, int(s * 1.6)))
    d.text((x1 + s, y0 + 2 * s), f"{w_cm:.0f} x {h_cm:.0f} cm", font=fs, fill=(0, 170, 255, 255))
    d.line([ox + 20 * s, oy, ox + 20 * s, y0], fill=(0, 170, 255, 200), width=max(1, s // 6))
    d.text((ox + 21 * s, (oy + y0) / 2 - s), f"{print_top:.0f} cm sous le col", font=fs, fill=(0, 170, 255, 255))
    d.text((pad * s, 1 * s), title, font=font(max(16, int(s * 3))), fill=(240, 240, 240, 255))
    return shirt


def make_apercu(front, back, color, out: Path, print_size=0.30, print_top=7.0, s=14):
    col = parse_color(color) if isinstance(color, str) else color
    fd, bd = load_design(front), load_design(back)
    a = draw_shirt(fd, col, s, "DEVANT", print_size, print_top)
    b = draw_shirt(bd, col, s, "DOS (vu de derrière)", print_size, print_top)
    sheet = Image.new("RGB", (a.width + b.width, a.height + 4 * s), (40, 42, 48))
    sheet.paste(a, (0, 0), a)
    sheet.paste(b, (a.width, 0), b)
    d = ImageDraw.Draw(sheet)
    d.text((s, a.height + s), "Aperçu à plat : le design est posé exactement comme dans la vidéo 3D. "
           "Le côté droit de l'image devant = le cœur de la personne.", font=font(max(12, int(s * 1.3))),
           fill=(200, 200, 205))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def main():
    ap = argparse.ArgumentParser(description="Gabarit et aperçu de placement des designs")
    ap.add_argument("--gabarit", action="store_true", help="crée design/GABARIT_zone_impression.png")
    ap.add_argument("--front")
    ap.add_argument("--back")
    ap.add_argument("--color", default="noir", help="nom (noir, blanc, bleu marine…) ou #RRGGBB")
    ap.add_argument("--print-size", type=float, default=0.30)
    ap.add_argument("--print-top", type=float, default=7.0)
    ap.add_argument("--out", default="out/apercu.png")
    A = ap.parse_args()
    if A.gabarit:
        print("Gabarit ->", make_gabarit(Path("design/GABARIT_zone_impression.png"), A.print_size))
    if A.front or A.back:
        print("Aperçu ->", make_apercu(A.front, A.back, A.color, Path(A.out), A.print_size, A.print_top))
    if not (A.gabarit or A.front or A.back):
        ap.print_help()


if __name__ == "__main__":
    main()
