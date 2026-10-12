"""
intro_pose.py - ajoute une pose neutre (T-pose) au début d'une danse Mixamo, avec une transition douce.

Pourquoi : dans Marvelous Designer, le t-shirt doit être posé sur l'avatar en pose neutre. Une danse
Mixamo commence directement dans le mouvement : le tissu se coince ou explose au départ.

    blender -b -P tshirt3d/intro_pose.py -- danse.fbx danse_intro.fbx
    blender -b -P tshirt3d/intro_pose.py -- danse.fbx danse_intro.fbx --hold 1.0 --blend 1.0

  --hold S   secondes immobiles en pose neutre au début (défaut 1)
  --blend S  secondes de transition de la pose neutre vers la danse (défaut 1)
Le fichier de sortie (FBX) s'importe dans Marvelous Designer comme avatar, à la place de l'original.
"""
import argparse
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--hold", type=float, default=1.0)
ap.add_argument("--blend", type=float, default=1.0)
ap.add_argument("--fps", type=int, default=30)
A = ap.parse_args(argv)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = A.fps
bpy.ops.import_scene.fbx(filepath=os.path.abspath(A.src))
arms = [o for o in scene.objects if o.type == "ARMATURE"]
if not arms:
    sys.exit("[intro_pose] aucun squelette dans le fichier")
arm = max(arms, key=lambda o: len(o.data.bones))
if not (arm.animation_data and arm.animation_data.action):
    sys.exit("[intro_pose] le squelette n'a pas d'animation (télécharge la danse « With Skin »)")
act = arm.animation_data.action
start, end = (int(round(v)) for v in act.frame_range)
hold = int(round(A.hold * A.fps))
blend = int(round(A.blend * A.fps))
shift = hold + blend - start + 1

# 1) on décale toute la danse pour laisser la place à l'intro
for fc in act.fcurves:
    for kp in fc.keyframe_points:
        kp.co.x += shift
        kp.handle_left.x += shift
        kp.handle_right.x += shift

# 2) pose neutre (= pose de repos du squelette, la T-pose de Mixamo) aux images 1 et hold+1
#    sur les os animés ; la courbe de Bézier fait la transition vers la première pose de la danse
bpy.context.view_layer.objects.active = arm
for pb in arm.pose.bones:
    pb.location = (0, 0, 0)
    pb.rotation_quaternion = (1, 0, 0, 0)
    pb.rotation_euler = (0, 0, 0)
    pb.scale = (1, 1, 1)
animated = {fc.data_path.split('"')[1] for fc in act.fcurves if fc.data_path.startswith("pose.bones")}
root_loc = {}
for fc in act.fcurves:  # la racine garde sa position de départ (pas de saut de hauteur)
    if fc.data_path.endswith(".location"):
        root_loc.setdefault(fc.data_path.split('"')[1], [0.0, 0.0, 0.0])[fc.array_index] = fc.evaluate(start + shift)
for f in (1, hold + 1):
    for name in animated:
        pb = arm.pose.bones[name]
        if name in root_loc:
            pb.location = root_loc[name]
        pb.keyframe_insert("location", frame=f)
        pb.keyframe_insert("rotation_quaternion" if pb.rotation_mode == "QUATERNION" else "rotation_euler", frame=f)
for fc in act.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = "BEZIER"
    fc.update()

scene.frame_start = 1
scene.frame_end = end + shift
for o in scene.objects:
    o.select_set(True)
bpy.ops.export_scene.fbx(filepath=os.path.abspath(A.dst), use_selection=False, bake_anim=True,
                         bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                         add_leaf_bones=False)
print(f"[intro_pose] OK : {A.hold:g} s de pose neutre + {A.blend:g} s de transition, puis la danse -> {A.dst}")
