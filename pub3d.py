#!/usr/bin/env python3
"""
pub3d.py - une commande : tes designs → t-shirt 3D au vent (Blender) → pub verticale montée.

    python pub3d.py --front design/3.png --back design/4.png
    python pub3d.py --front design/3.png --back design/4.png --final      # qualité max (Cycles)
    python pub3d.py --front d.png --config produit.json --preview         # test rapide

Étapes :
  1. prépare les designs : si le PNG a un fond uni (ex. noir), il est détouré et
     cette couleur devient celle du tissu ;
  2. lance Blender en arrière-plan (tshirt3d/tshirt3d.py) : simulation + rendu ;
  3. monte la pub avec tshirt_video.py (accroche, cartes, prix, musique) par-dessus la 3D.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent


def find_ffmpeg() -> str:
    exe = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg introuvable. Lance : pip install imageio-ffmpeg")


def find_blender(user_path: str | None) -> str:
    cands = [user_path, os.environ.get("BLENDER"), shutil.which("blender")]
    cands += sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe"), reverse=True)
    cands += ["/Applications/Blender.app/Contents/MacOS/Blender"]
    cands += sorted(glob.glob("/opt/blender/*/blender"), reverse=True)
    for c in cands:
        if c and Path(c).exists():
            return c
    sys.exit("Blender introuvable. Installe Blender 4.5 LTS (blender.org) ou passe --blender CHEMIN")


def prepare_design(src: str, dst: Path) -> tuple[str | None, Path]:
    """Détoure un fond uni. Renvoie (couleur du fond en hex ou None, chemin du PNG prêt)."""
    im = Image.open(src).convert("RGBA")
    a = np.asarray(im).astype(np.float32)
    if a[..., 3].min() < 250:                      # déjà transparent : rien à faire
        im.save(dst)
        return None, dst
    h, w = a.shape[:2]
    k = max(4, min(h, w) // 40)
    m = max(2, min(h, w) // 200)                   # on ignore un éventuel liseré sur le bord
    patches = [a[m:m + k, m:m + k], a[m:m + k, -m - k:-m], a[-m - k:-m, m:m + k], a[-m - k:-m, -m - k:-m]]
    corners = np.concatenate([p[..., :3].reshape(-1, 3) for p in patches])
    bg = np.median(corners, axis=0)
    if (np.sqrt(((corners - bg) ** 2).sum(-1)) < 12).mean() < 0.9:   # fond pas uni : image gardée telle quelle
        im.save(dst)
        return None, dst
    dist = np.sqrt(((a[..., :3] - bg) ** 2).sum(-1))
    alpha = np.clip((dist - 10) / 30, 0, 1)        # 10 → transparent, 40 → opaque, doux entre les deux
    out = a.copy()
    out[..., 3] = alpha * 255
    e = max(m, min(h, w) // 100)                   # bords effacés (liseré d'export)
    out[:e, :, 3] = out[-e:, :, 3] = 0
    out[:, :e, 3] = out[:, -e:, 3] = 0
    Image.fromarray(out.astype(np.uint8), "RGBA").save(dst)
    return "#%02X%02X%02X" % tuple(int(round(c)) for c in bg), dst


def main():
    ap = argparse.ArgumentParser(description="Pub t-shirt 3D automatique")
    ap.add_argument("--front", required=True, help="design devant (PNG)")
    ap.add_argument("--back", help="design dos (PNG)")
    ap.add_argument("--color", help="couleur du tissu (sinon : fond du design, ou #141418)")
    ap.add_argument("--config", help="JSON produit (nom, prix, textes) pour la pub")
    ap.add_argument("--music", help="musique à la place du beat généré")
    ap.add_argument("--print-size", type=float, default=0.30, help="largeur de la zone d'impression (m)")
    ap.add_argument("--print-top", type=float, default=7.0, help="cm entre le col et le haut de la zone")
    ap.add_argument("--wind", type=float, default=1.0)
    ap.add_argument("--blender", help="chemin de blender.exe")
    ap.add_argument("--final", action="store_true", help="Cycles, 1080x1920, 96 échantillons (lent, plus beau)")
    ap.add_argument("--preview", action="store_true", help="540x960, rapide, pour vérifier")
    ap.add_argument("--skip-3d", action="store_true", help="réutilise le rendu 3D existant")
    ap.add_argument("--out", default="out/pub3d.mp4")
    A = ap.parse_args()

    ffmpeg = find_ffmpeg()
    os.environ["FFMPEG"] = ffmpeg
    work = Path("out/work")
    work.mkdir(parents=True, exist_ok=True)

    # 1. designs
    bg_front, front = prepare_design(A.front, work / "front.png")
    back = None
    if A.back:
        _, back = prepare_design(A.back, work / "back.png")
    color = A.color or bg_front or "#141418"
    print(f"[pub3d] tissu {color} ; designs prêts dans {work}")

    # 2. 3D
    clip = work / "tshirt3d.mp4"
    seconds = 15.0
    if not A.skip_3d:
        blender = find_blender(A.blender)
        cmd = [blender, "-b", "-P", str(HERE / "tshirt3d" / "tshirt3d.py"), "--",
               "--design", str(front), "--color", color, "--turn",
               "--print-size", str(A.print_size), "--print-top", str(A.print_top),
               "--wind", str(A.wind), "--seconds", str(seconds), "--out", str(clip)]
        if back:
            cmd += ["--back", str(back)]
        if A.final:
            cmd += ["--engine", "cycles", "--samples", "96"]
        else:
            cmd += ["--engine", "eevee", "--samples", "32"]
        if A.preview:
            cmd += ["--preview"]
        print("[pub3d] Blender :", " ".join(f'"{c}"' if " " in c else c for c in cmd))
        t0 = time.time()
        if clip.exists():
            clip.unlink()
        log_path = work / "blender.log"
        # Blender affiche beaucoup d'avertissements internes sans gravité : ils vont dans
        # out/work/blender.log, seules les lignes de progression s'affichent ici.
        with open(log_path, "w", encoding="utf-8", errors="replace") as log:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace")
            for line in p.stdout:
                log.write(line)
                if line.startswith("[tshirt3d]") or "Traceback" in line or line.startswith("Error:"):
                    print(line, end="", flush=True)
            p.wait()
        if p.returncode != 0 or not clip.exists():
            print("".join(open(log_path, encoding="utf-8", errors="replace").readlines()[-40:]))
            sys.exit(f"[pub3d] Blender a échoué. Journal complet : {log_path}")
        print(f"[pub3d] 3D rendue en {time.time() - t0:.0f} s")

    # 3. montage
    cmd = [sys.executable, str(HERE / "tshirt_video.py"), "--clip3d", str(clip), "--out", A.out]
    if A.config:
        cmd += ["--config", A.config]
    if A.music:
        cmd += ["--music", A.music]
    if A.preview:
        cmd += ["--preview"]
    subprocess.run(cmd, check=True)
    print(f"[pub3d] Terminé -> {A.out}")


if __name__ == "__main__":
    main()
