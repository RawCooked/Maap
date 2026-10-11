"""
render_part.py - réglages de rendu et rendu de l'animation, communs à :
  - tshirt3d.py qui vient de construire et simuler la scène ;
  - tshirt3d.py --render-only, lancé sur une scène déjà simulée (out/work/scene_<anim>.blend),
    pour la version finale sans refaire la simulation.
"""
import os
import shutil
import subprocess
import time

import bpy


def eevee_engine():
    names = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    return "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in names else "BLENDER_EEVEE"


def setup_engine(scene, A):
    W, H = (int(v) for v in A.res.lower().split("x"))
    r = scene.render
    if A.engine == "eevee":
        r.engine = eevee_engine()
        scene.eevee.taa_render_samples = max(16, A.samples)
        scene.eevee.use_shadows = True
        if hasattr(scene.eevee, "use_raytracing") and not A.preview:
            scene.eevee.use_raytracing = True      # reflets et ombres de contact plus propres
    else:
        r.engine = "CYCLES"
        gpu_found = False
        prefs = bpy.context.preferences.addons["cycles"].preferences
        # OptiX/CUDA = NVIDIA, HIP = AMD, Metal = Mac, oneAPI = Intel. On ne garde un type que s'il a
        # vraiment une carte de ce type (sinon Cycles retombe en silence sur le processeur).
        for dev_type in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
            try:
                prefs.compute_device_type = dev_type
                prefs.get_devices()
                if any(d.type == dev_type for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = d.type == dev_type  # carte graphique seule : le processeur la ralentirait
                    scene.cycles.device = "GPU"
                    names = ", ".join(d.name for d in prefs.devices if d.use)
                    print(f"[tshirt3d] rendu GPU ({dev_type}) : {names}", flush=True)
                    gpu_found = True
                    break
            except Exception:
                continue
        scene.cycles.samples = A.samples
        scene.cycles.use_denoising = True
        scene.cycles.max_bounces = 4
        if hasattr(scene.cycles, "denoising_use_gpu"):
            scene.cycles.denoising_use_gpu = True   # débruitage sur la carte graphique
        if not gpu_found:
            print("[tshirt3d] ATTENTION : aucune carte graphique trouvée pour Cycles (pilote AMD ? HIP ?).", flush=True)
            print("[tshirt3d] Bascule automatique sur EEVEE pour éviter un rendu de plusieurs heures.", flush=True)
            r.engine = eevee_engine()
            scene.eevee.taa_render_samples = 64
            if hasattr(scene.eevee, "use_raytracing"):
                scene.eevee.use_raytracing = True
    r.resolution_x, r.resolution_y = W, H
    r.resolution_percentage = 100
    r.fps = A.fps
    r.film_transparent = False
    r.use_persistent_data = True    # garde fond, lumières et textures en mémoire entre les images
    # flou de mouvement : en EEVEE seulement ; en Cycles il multiplie le temps de rendu du tissu
    r.use_motion_blur = r.engine != "CYCLES"
    r.motion_blur_shutter = 0.5
    scene.view_settings.view_transform = "Standard"   # couleurs de marque fidèles
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = A.exposure
    return W, H


def render_animation(scene, A, preroll, total_frames):
    W, H = setup_engine(scene, A)
    out = os.path.abspath(A.out)
    frames_dir = os.path.splitext(out)[0] + "_frames"
    os.makedirs(frames_dir, exist_ok=True)
    r = scene.render
    r.image_settings.file_format = "PNG"
    for old in os.listdir(frames_dir):
        if old.endswith(".png"):
            os.remove(os.path.join(frames_dir, old))
    every = A.every
    if A.check:
        every = max(1, total_frames // 8)
    # toute l'animation en un seul appel : Blender ne recharge pas la scène à chaque image
    scene.frame_start = preroll + 1
    scene.frame_end = preroll + total_frames
    scene.frame_step = every
    r.filepath = os.path.join(frames_dir, "f_")
    n_total = len(range(scene.frame_start, scene.frame_end + 1, every))
    done = [0]
    t0 = [time.time()]

    def _progress(_scene, _depsgraph=None):
        done[0] += 1
        el = time.time() - t0[0]
        per = el / done[0]
        print(f"[tshirt3d] rendu {done[0]}/{n_total}  ({per:.1f} s/image, reste ~{per * (n_total - done[0]) / 60:.0f} min)",
              flush=True)

    bpy.app.handlers.render_write.append(_progress)
    print(f"[tshirt3d] rendu : {r.engine}, {W}x{H}, {n_total} images", flush=True)
    t0[0] = time.time()
    bpy.ops.render.render(animation=True)
    for i, name in enumerate(sorted(n for n in os.listdir(frames_dir) if n.startswith("f_"))):
        os.replace(os.path.join(frames_dir, name), os.path.join(frames_dir, f"{i:04d}.png"))

    ff = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if ff:
        subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", str(A.fps // every or 1), "-i",
                        os.path.join(frames_dir, "%04d.png"), "-c:v", "libx264", "-crf", "17",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], check=True)
        print(f"[tshirt3d] OK -> {out}", flush=True)
    else:
        print(f"[tshirt3d] ffmpeg introuvable : images dans {frames_dir}", flush=True)
