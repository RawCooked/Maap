"""
tshirt3d.py - t-shirt 3D en tissu simulé, qui flotte au vent, avec TON design imprimé dessus.

Rien à modéliser : le script construit le t-shirt (devant + dos cousus), le suspend par
les épaules, souffle du vent dessus, applique ton design sur la poitrine, éclaire,
fait tourner la caméra et rend une vidéo.

    blender -b -P tshirt3d.py -- --design mon_design.png --out out/tshirt3d.mp4
    blender -b -P tshirt3d.py -- --design d.png --color "#C42636" --preview
    blender -b -P tshirt3d.py -- --design d.png --save-blend out/scene.blend   # pour retoucher à la main

Par défaut le t-shirt est porté par un corps invisible (torse + bras), dans un grand vent, filmé en
six plans (large, contre-plongée, gros plan poitrine, latéral, dos, plan final).

Options (après le "--") :
  --design PNG     design à imprimer (transparent conseillé)
  --back PNG       design au dos (facultatif)
  --color HEX      couleur du tissu (défaut #141418)
  --bg HEX         couleur du fond (défaut #0A0D14)
  --print-size M   largeur du print en mètres (défaut 0.24)
  --print-top CM   distance col → haut du print (défaut 12)
  --turn           la caméra passe du devant au dos
  --hanger         sur un cintre au lieu du corps invisible
  --orbit          simple rotation au lieu des six plans
  --engine eevee   rendu rapide (carte graphique)
  --wind F         force du vent (défaut 1.0 = brise ; 2.0 = tempête)
  --seconds S      durée de la vidéo (défaut 5)
  --res WxH        défaut 1080x1920 (vertical)
  --samples N      échantillons Cycles (défaut 64 ; 16 en preview)
  --preview        540x960, rapide
  --save-blend F   enregistre aussi la scène .blend
Testé avec Blender 4.5 LTS, rendu Cycles CPU (aucune carte graphique requise).
"""
import argparse
import math
import os
import shutil
import subprocess
import sys
import time

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.geometry import delaunay_2d_cdt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_part  # noqa: E402

# ─────────────────────────── arguments ───────────────────────────
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--design")
ap.add_argument("--back")
ap.add_argument("--color", default="#141418")
ap.add_argument("--bg", default="#0A0D14")
ap.add_argument("--print-size", type=float, default=0.24)
ap.add_argument("--print-top", type=float, default=12.0, help="cm entre le col et le haut du print")
ap.add_argument("--turn", action="store_true", help="la caméra passe du devant au dos")
ap.add_argument("--hanger", action="store_true", help="t-shirt sur un cintre au lieu d'un corps invisible")
ap.add_argument("--orbit", action="store_true", help="ancienne caméra : simple rotation au lieu des plans")
ap.add_argument("--exposure", type=float, default=-0.8)
ap.add_argument("--wind", type=float, default=1.0)
ap.add_argument("--seconds", type=float, default=5.0)
ap.add_argument("--res", default="1080x1920")
ap.add_argument("--samples", type=int, default=64)
ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--preview", action="store_true")
ap.add_argument("--out", default="out/tshirt3d.mp4")
ap.add_argument("--save-blend")
ap.add_argument("--engine", choices=["cycles", "eevee"], default="cycles")
ap.add_argument("--sim-only", action="store_true")
ap.add_argument("--mass", type=float, default=0.02)
ap.add_argument("--every", type=int, default=1, help="ne rend qu'une image sur N (tests)")
ap.add_argument("--check", action="store_true", help="vérification : 8 images basse définition, pas de vidéo")
ap.add_argument("--anim", choices=["vent", "chute", "vitrine"], default="vent",
                help="vent : porté, en plein vent, 6 plans ; chute : tombe et se drape sur un socle ; "
                     "vitrine : porté, sans vent, la caméra en fait le tour")
ap.add_argument("--blend", help="enregistre la scène simulée ici (pour un rendu final sans re-simuler)")
ap.add_argument("--render-only", action="store_true",
                help="rend la scène .blend ouverte par Blender (déjà simulée) sans la reconstruire")
A = ap.parse_args(argv)
if A.check:
    A.preview = True
    A.engine = "eevee"
if A.preview:
    A.res, A.samples = "540x960", 16

if A.render_only:
    # blender -b out/work/scene_<anim>.blend -P tshirt3d.py -- --render-only ... : la simulation est
    # déjà sur le disque (blendcache_...), on ne fait que régler le moteur et rendre.
    sc = bpy.context.scene
    render_part.render_animation(sc, A, int(sc["preroll"]), int(sc["total_frames"]))
    sys.exit(0)

FLAT = A.hanger or A.anim == "chute"   # patron plat (cintre, chute) ; sinon gonflé autour du corps invisible

PREROLL = 45  # images de simulation avant le début de la vidéo (le tissu se met en place)


def hex_rgb(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, 1.0)


# ─────────────────────────── scène vide ───────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ─────────────────────────── patron du t-shirt ───────────────────────────
# Contour en cm (x vers la droite, z vers le haut), origine au milieu du col.
# Chaque segment : (point de départ, cousu ?)  — non cousu = ouverture (col, manches, bas).
OUTLINE = [
    ((-9.0, 0.0), False),     # col gauche → col droit  (ouverture du col)
    ((9.0, 0.0), True),       # épaule droite
    ((24.0, -4.0), True),     # dessus de manche droite
    ((38.0, -16.0), False),   # ouverture manche droite
    ((31.0, -27.0), True),    # dessous de manche
    ((24.0, -22.0), True),    # côté droit
    ((25.0, -72.0), False),   # bas (ourlet)
    ((-25.0, -72.0), True),   # côté gauche
    ((-24.0, -22.0), True),   # dessous de manche gauche
    ((-31.0, -27.0), False),  # ouverture manche gauche
    ((-38.0, -16.0), True),   # dessus de manche gauche
    ((-24.0, -4.0), True),    # épaule gauche
]
NECK_DIP = 7.0   # profondeur de l'encolure devant (cm)
# finesse du maillage (cm). La vérification (--check) garde celle du rendu final : la masse étant
# donnée par sommet, changer le maillage changerait le comportement du tissu.
H = 1.4 if (A.preview and not A.check) else 1.25


def outline_points():
    """Rééchantillonne le contour ; renvoie [(x, z, cousu)] ."""
    pts = []
    n = len(OUTLINE)
    for i in range(n):
        (x0, z0), sewn = OUTLINE[i]
        (x1, z1), _ = OUTLINE[(i + 1) % n]
        L = math.hypot(x1 - x0, z1 - z0)
        k = max(1, round(L / H))
        for j in range(k):
            t = j / k
            x, z = x0 + (x1 - x0) * t, z0 + (z1 - z0) * t
            if i == 0:  # encolure arrondie
                z -= NECK_DIP * math.sin(math.pi * t) * 0.35
            # un sommet est cousu si l'un des deux segments qui s'y touchent l'est
            prev_sewn = OUTLINE[i - 1][1]
            pts.append((x, z, sewn if j else (sewn or prev_sewn)))
    return pts


def inside(poly, x, z):
    c = False
    n = len(poly)
    for i in range(n):
        (xa, za), (xb, zb) = poly[i], poly[(i + 1) % n]
        if (za > z) != (zb > z) and x < (xb - xa) * (z - za) / (zb - za) + xa:
            c = not c
    return c


def dist_to_poly(poly, x, z):
    best = 1e9
    n = len(poly)
    for i in range(n):
        (xa, za), (xb, zb) = poly[i], poly[(i + 1) % n]
        dx, dz = xb - xa, zb - za
        t = max(0, min(1, ((x - xa) * dx + (z - za) * dz) / (dx * dx + dz * dz + 1e-9)))
        best = min(best, math.hypot(x - xa - t * dx, z - za - t * dz))
    return best


# Corps invisible : (hauteur sous le col, demi-largeur, demi-épaisseur) en mètres
BODY_RINGS = [(0.00, 0.065, 0.055), (-0.035, 0.17, 0.075), (-0.07, 0.215, 0.09), (-0.16, 0.215, 0.095),
              (-0.35, 0.205, 0.09), (-0.55, 0.205, 0.088), (-0.80, 0.21, 0.09), (-0.95, 0.21, 0.09)]
GAP = 0.018   # espace entre le corps et le tissu
# Bras invisibles : (départ x, z), (fin x, z), rayon au départ, rayon à la fin (côté droit, miroir à gauche)
ARM = ((0.19, -0.10), (0.33, -0.215), 0.045, 0.04)


def body_section(z):
    """Demi-largeur et demi-épaisseur du corps à la hauteur z (m, sous le col)."""
    if z >= BODY_RINGS[0][0]:
        return BODY_RINGS[0][1], BODY_RINGS[0][2]
    for (za, wa, da), (zb, wb, db) in zip(BODY_RINGS, BODY_RINGS[1:]):
        if za >= z >= zb:
            t = (za - z) / (za - zb)
            return wa + (wb - wa) * t, da + (db - da) * t
    return BODY_RINGS[-1][1], BODY_RINGS[-1][2]


def body_depth(x, z):
    """Demi-épaisseur du corps invisible (torse + bras) au point (x, z) du patron, en mètres ; 0 si hors du corps."""
    wx, wy = body_section(z)
    best = wy * math.sqrt(1 - (abs(x) / wx) ** 2) if abs(x) < wx else 0.0
    (ax, az), (bx, bz), r0, r1 = ARM
    ax, bx = math.copysign(ax, x), math.copysign(bx, x)
    dx, dz = bx - ax, bz - az
    L2 = dx * dx + dz * dz
    t = ((x - ax) * dx + (z - az) * dz) / L2
    if 0.0 <= t <= 1.0:
        r = math.hypot(x - ax - t * dx, z - az - t * dz)
        R = r0 + (r1 - r0) * t
        if r < R:
            best = max(best, math.sqrt(R * R - r * r))
    return best


def dist_to_sewn(bnd, x, z):
    """Distance (cm) aux coutures (les bords cousus restent à plat)."""
    best = 1e9
    for k in range(len(OUTLINE)):
        if not OUTLINE_SEWN[k]:
            continue
        (xa, za), (xb, zb) = SEG_PTS[k]
        dx, dz = xb - xa, zb - za
        t = max(0, min(1, ((x - xa) * dx + (z - za) * dz) / (dx * dx + dz * dz + 1e-9)))
        best = min(best, math.hypot(x - xa - t * dx, z - za - t * dz))
    return best


OUTLINE_SEWN = [sewn for _, sewn in OUTLINE]
SEG_PTS = [(OUTLINE[k][0], OUTLINE[(k + 1) % len(OUTLINE)][0]) for k in range(len(OUTLINE))]


def build_shirt():
    bnd = outline_points()
    poly = [(x, z) for x, z, _ in bnd]
    pts2d = list(poly)
    # points intérieurs en grille hexagonale
    zz = 2.0
    row = 0
    while zz > -80:
        xx = -45 + (H / 2 if row % 2 else 0)
        while xx < 45:
            if inside(poly, xx, zz) and dist_to_poly(poly, xx, zz) > H * 0.6:
                pts2d.append((xx, zz))
            xx += H
        zz -= H * 0.866
        row += 1
    nb = len(bnd)
    edges = [(i, (i + 1) % nb) for i in range(nb)]
    res = delaunay_2d_cdt([Vector(p) for p in pts2d], edges, [], 1, 1e-5)
    verts2d, _, faces2d = res[0], res[1], res[2]
    # retrouver l'index d'origine de chaque sommet (CDT peut réordonner)
    orig = res[3]
    sewn_of = {}
    for vi, olist in enumerate(orig):
        for o in olist:
            if o < nb:
                sewn_of[vi] = bnd[o][2]
    faces2d = [f for f in faces2d
               if inside(poly, sum(verts2d[i].x for i in f) / len(f), sum(verts2d[i].y for i in f) / len(f))]

    used = sorted({i for f in faces2d for i in f})
    me = bpy.data.meshes.new("Tshirt")
    bm = bmesh.new()
    front, back = {}, {}
    cm = 0.01
    for i in used:
        x, z = verts2d[i].x, verts2d[i].y
        on_border = i in sewn_of
        d = dist_to_poly(poly, x, z)
        if FLAT:
            puff = min(1.0, d / 10.0) ** 0.5 * 0.035      # léger volume, nul au bord
            if on_border:
                puff = 0.004
        else:
            # le tissu épouse le corps invisible (torse + bras), toujours au moins GAP au-dessus,
            # sauf contre les coutures qui restent à plat (le corps est placé sous les coutures)
            ds = dist_to_sewn(bnd, x, z)
            puff = body_depth(x * cm, z * cm) + GAP * min(1.0, ds / 2.5)
        if on_border and sewn_of[i]:
            v = bm.verts.new((x * cm, 0.0, z * cm))
            front[i] = back[i] = v
        else:
            front[i] = bm.verts.new((x * cm, -max(puff, 0.004), z * cm))
            back[i] = bm.verts.new((x * cm, max(puff, 0.004), z * cm))
    uv_layer = bm.loops.layers.uv.new("UVMap")
    side_layer = bm.faces.layers.int.new("side")
    for f in faces2d:
        ff = bm.faces.new([front[i] for i in f])
        ff[side_layer] = 0
        fb = bm.faces.new([back[i] for i in reversed(f)])
        fb[side_layer] = 1
    bm.normal_update()
    # UV : projection plane — devant à gauche de la texture, dos à droite
    for face in bm.faces:
        side = face[side_layer]
        for loop in face.loops:
            x, z = loop.vert.co.x / cm, loop.vert.co.z / cm
            u = (x + 45) / 90
            v = (z + 80) / 85
            loop[uv_layer].uv = ((u if side == 0 else 1 - u) * 0.5 + 0.5 * side, v)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("Tshirt", me)
    scene.collection.objects.link(obj)
    # matériau devant / dos via l'attribut "side"
    attr = me.attributes.get("side")
    for p in me.polygons:
        p.material_index = attr.data[p.index].value if attr else 0
    for p in me.polygons:
        p.use_smooth = True
    # groupe d'épingles : les épaules (le cintre)
    vg = obj.vertex_groups.new(name="pin")
    pins = [v.index for v in me.vertices
            if v.co.z > -0.055 and 0.07 < abs(v.co.x) < 0.20]
    vg.add(pins, 1.0, "REPLACE")
    return obj


shirt = build_shirt()
shirt.location = (0, 0, 1.55)


def build_body():
    """Mannequin invisible : un torse elliptique un peu plus petit que le t-shirt (collision seulement)."""
    # (hauteur sous le col, demi-largeur, demi-épaisseur) en mètres
    rings = BODY_RINGS
    n = 32
    bm = bmesh.new()
    loops = []
    for z, wx, wy in rings:
        loops.append([bm.verts.new((wx * math.cos(2 * math.pi * k / n), wy * math.sin(2 * math.pi * k / n), z))
                      for k in range(n)])
    for a, b in zip(loops, loops[1:]):
        for k in range(n):
            bm.faces.new([a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]])
    bm.faces.new(loops[0])
    bm.faces.new(list(reversed(loops[-1])))
    # bras invisibles : tiennent les manches comme sur un mannequin
    (ax_, az_), (bx_, bz_), r0, r1 = ARM
    for sx in (-1, 1):
        start = Vector((sx * ax_, 0, az_))
        end = Vector((sx * bx_, 0, bz_))
        axis = (end - start).normalized()
        side = axis.cross(Vector((0, 1, 0))).normalized()
        up = Vector((0, 1, 0))
        arm = []
        for t, r in ((0.0, r0), (0.5, (r0 + r1) / 2), (1.0, r1)):
            c = start + (end - start) * t
            arm.append([bm.verts.new(c + side * r * math.cos(2 * math.pi * k / 16) + up * r * math.sin(2 * math.pi * k / 16))
                        for k in range(16)])
        for a_, b_ in zip(arm, arm[1:]):
            for k in range(16):
                bm.faces.new([a_[k], a_[(k + 1) % 16], b_[(k + 1) % 16], b_[k]])
        bm.faces.new(list(reversed(arm[0]))); bm.faces.new(arm[-1])
    # faces tournées vers l'extérieur : sinon Blender croit le tissu « dans » le corps et l'éjecte
    # (le t-shirt se roulait en boule sur les épaules dès les premières images)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("Corps")
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("Corps", me)
    scene.collection.objects.link(ob)
    ob.location = shirt.location
    ob.hide_render = True
    col = ob.modifiers.new("Collision", "COLLISION")
    ob.collision.thickness_outer = 0.006
    ob.collision.cloth_friction = 1.5     # assez bas pour que le tissu retombe après une rafale
    ob.collision.damping = 0.6
    return ob


body = None if FLAT else build_body()

if A.anim == "chute":
    # le t-shirt est à plat, devant vers le haut, au-dessus d'un socle ; il tombe quand la gravité arrive
    shirt.rotation_euler = (math.radians(-90), 0, 0)
    shirt.location = (0, 0.36, 1.45)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.22, depth=0.95, vertices=96, location=(0, 0, 0.475))   # étroit : le t-shirt retombe sur les côtés
    socle = bpy.context.object
    for p_ in socle.data.polygons:
        p_.use_smooth = True
    bev = socle.modifiers.new("Arrondi", "BEVEL"); bev.width = 0.012; bev.segments = 4
    socle.modifiers.new("Collision", "COLLISION")
    socle.collision.thickness_outer = 0.006
    socle.collision.cloth_friction = 6.0
    sm = bpy.data.materials.new("Socle"); sm.use_nodes = True
    sb = sm.node_tree.nodes["Principled BSDF"]
    sb.inputs["Base Color"].default_value = (0.03, 0.03, 0.035, 1)
    sb.inputs["Roughness"].default_value = 0.35
    socle.data.materials.append(sm)

# ─────────────────────────── matériau tissu + print ───────────────────────────
def fabric_material(name, design_path, mirror_u=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial"); out.location = (900, 0)
    bsdf = N.new("ShaderNodeBsdfPrincipled"); bsdf.location = (600, 0)
    bsdf.inputs["Roughness"].default_value = 0.85
    bsdf.inputs["Sheen Weight"].default_value = 0.12
    bsdf.inputs["Sheen Roughness"].default_value = 0.5
    L.new(bsdf.outputs[0], out.inputs[0])
    fabric = hex_rgb(A.color)
    # trame du tissu (bump fin)
    tc = N.new("ShaderNodeTexCoord"); tc.location = (-900, -300)
    wave = N.new("ShaderNodeTexWave"); wave.location = (-600, -300)
    wave.inputs["Scale"].default_value = 900
    wave.inputs["Distortion"].default_value = 2
    L.new(tc.outputs["Object"], wave.inputs["Vector"])
    noise = N.new("ShaderNodeTexNoise"); noise.location = (-600, -550)
    noise.inputs["Scale"].default_value = 400
    mixb = N.new("ShaderNodeMath"); mixb.operation = "ADD"; mixb.location = (-350, -400)
    L.new(wave.outputs["Fac"], mixb.inputs[0]); L.new(noise.outputs["Fac"], mixb.inputs[1])
    bump = N.new("ShaderNodeBump"); bump.location = (300, -350)
    bump.inputs["Strength"].default_value = 0.06
    bump.inputs["Distance"].default_value = 0.0005
    L.new(mixb.outputs[0], bump.inputs["Height"])
    L.new(bump.outputs[0], bsdf.inputs["Normal"])
    if not design_path:
        bsdf.inputs["Base Color"].default_value = fabric
        return m
    # print : coordonnées centrées sur la poitrine
    uv = N.new("ShaderNodeUVMap"); uv.location = (-900, 200)
    sep = N.new("ShaderNodeSeparateXYZ"); sep.location = (-700, 200)
    L.new(uv.outputs[0], sep.inputs[0])
    # UV -> cm : x = u_local*90-45 ; z = v*85-80 ; u_local = (u - 0.5*side)/0.5
    img = bpy.data.images.load(os.path.abspath(design_path))
    aspect = img.size[1] / max(1, img.size[0])
    w_cm = A.print_size * 100
    h_cm = w_cm * aspect
    cz = -A.print_top - h_cm / 2
    side = 1 if mirror_u else 0

    def math_node(op, a, b, loc):
        n = N.new("ShaderNodeMath"); n.operation = op; n.location = loc
        for k, val in enumerate((a, b)):
            if isinstance(val, (int, float)):
                n.inputs[k].default_value = val
            else:
                L.new(val, n.inputs[k])
        return n.outputs[0]
    ul = math_node("MULTIPLY", math_node("SUBTRACT", sep.outputs["X"], 0.5 * side, (-500, 300)), 2.0, (-350, 300))
    x_cm = math_node("SUBTRACT", math_node("MULTIPLY", ul, 90.0, (-200, 300)), 45.0, (-50, 300))
    z_cm = math_node("SUBTRACT", math_node("MULTIPLY", sep.outputs["Y"], 85.0, (-200, 150)), 80.0, (-50, 150))
    pu = math_node("ADD", math_node("DIVIDE", x_cm, w_cm, (100, 300)), 0.5, (250, 300))
    pv = math_node("ADD", math_node("DIVIDE", math_node("SUBTRACT", z_cm, cz, (100, 150)), h_cm, (250, 150)), 0.5, (400, 150))
    comb = N.new("ShaderNodeCombineXYZ"); comb.location = (400, 350)
    L.new(pu, comb.inputs[0]); L.new(pv, comb.inputs[1])
    tex = N.new("ShaderNodeTexImage"); tex.location = (100, 0)
    tex.image = img
    tex.extension = "CLIP"
    L.new(comb.outputs[0], tex.inputs["Vector"])
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.location = (350, 0)
    mix.inputs["A"].default_value = fabric
    L.new(tex.outputs["Alpha"], mix.inputs["Factor"])
    L.new(tex.outputs["Color"], mix.inputs["B"])
    L.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    # l'encre est un peu moins rugueuse que le coton
    rough = math_node("SUBTRACT", 0.85, math_node("MULTIPLY", tex.outputs["Alpha"], 0.3, (350, -150)), (450, -150))
    L.new(rough, bsdf.inputs["Roughness"])
    return m


shirt.data.materials.append(fabric_material("Devant", A.design))
shirt.data.materials.append(fabric_material("Dos", A.back, mirror_u=True))

# ─────────────────────────── physique du tissu ───────────────────────────
cloth = shirt.modifiers.new("Cloth", "CLOTH")
s = cloth.settings
s.quality = 8
s.mass = A.mass                  # kg par sommet
s.tension_stiffness = 15
s.compression_stiffness = 15
s.shear_stiffness = 5
s.bending_stiffness = 0.08
s.air_damping = 1.0 if A.hanger else 1.6
s.vertex_group_mass = "" if A.anim == "chute" else "pin"   # la chute n'est tenue par rien
s.use_pressure = A.hanger        # sur cintre : la pression donne du volume ; sinon c'est le corps
s.uniform_pressure_force = 0.6
s.pressure_factor = 1.0
s.shrink_min = 0.0
cs = cloth.collision_settings
# collision du tissu sur lui-même : c'est elle qui faisait passer la simulation de 0,5 à 13 s par image.
# Sur le corps invisible, le torse sépare déjà le devant du dos : inutile. Gardée pour la chute (le tissu
# s'y replie vraiment) et le cintre.
cs.use_self_collision = FLAT
cs.self_distance_min = 0.004
cs.distance_min = 0.006
cs.collision_quality = 3
cs.use_collision = True
total_frames = int(A.seconds * A.fps)
cloth.point_cache.frame_start = 1
cloth.point_cache.frame_end = PREROLL + total_frames
if A.anim == "chute":
    # en apesanteur pendant l'accroche, puis la gravité revient à 2 s : le t-shirt tombe sur le socle
    f_drop = PREROLL + int(2.0 * A.fps * A.seconds / 15.0)
    for f_, g in ((1, 0.0), (f_drop - 1, 0.0), (f_drop, -9.81)):
        scene.gravity = (0.0, 0.0, g)
        scene.keyframe_insert("gravity", frame=f_)
    for fc in scene.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
subd = shirt.modifiers.new("Subdiv", "SUBSURF")
subd.levels = 1
subd.render_levels = 1   # niveau 2 multipliait le maillage par ~30 : le processeur le reconstruisait à chaque image
sol = shirt.modifiers.new("Epaisseur", "SOLIDIFY")
sol.thickness = 0.0025

# vent : un souffle principal qui varie + turbulence
bpy.ops.object.effector_add(type="WIND", location=(-1.6, -1.2, 1.3))
wind = bpy.context.object
WIND_DIR = Vector((0.35, -0.9, 0.2)) if A.hanger else Vector((0.4, 0.9, -0.05))   # légèrement vers le bas : ne soulève pas le bas
wind.rotation_euler = WIND_DIR.to_track_quat("Z", "Y").to_euler()
# le tissu ne réagit qu'au vent qui le frappe de face. Sur cintre il souffle vers la caméra ;
# sur le corps il vient de face : le devant se plaque sur le torse, manches et bas claquent derrière.
wind.field.strength = 0
wind.field.noise = 3.0
wind.field.seed = 7
WIND_BASE = 900 if A.hanger else 700    # 2600 retroussait le t-shirt en boule sur les épaules
if A.anim in ("chute", "vitrine"):
    WIND_BASE = 0                       # pas de vent : le tissu tombe ou reste posé
gusts = ((0.0, 1.0), (0.12, 1.5), (0.22, 0.9), (0.38, 1.7), (0.5, 1.1), (0.62, 1.8), (0.75, 1.0),
         (0.88, 1.6), (1.0, 1.2))
for f, k in [(1, 0.0), (PREROLL - 15, 0.0)] + [(PREROLL + fr * total_frames, k) for fr, k in gusts]:
    wind.field.strength = WIND_BASE * A.wind * k
    wind.field.keyframe_insert("strength", frame=int(f))
bpy.ops.object.effector_add(type="TURBULENCE", location=(0, 0, 1.3))
turb = bpy.context.object
turb.field.strength = 0 if A.anim in ("chute", "vitrine") else 160 * A.wind
turb.field.size = 0.4
turb.field.flow = 0.5

# ─────────────────────────── cintre ───────────────────────────
def build_hanger():
    bpy.ops.mesh.primitive_torus_add(major_radius=0.035, minor_radius=0.004, location=(0, 0.0, 1.62))
    hook = bpy.context.object
    hook.rotation_euler = (math.radians(90), 0, 0)
    bpy.ops.curve.primitive_bezier_curve_add(location=(0, 0, 0))
    bar = bpy.context.object
    bar.data.bevel_depth = 0.005
    sp = bar.data.splines[0]
    sp.bezier_points[0].co = (-0.20, 0, 1.52); sp.bezier_points[0].handle_left = (-0.25, 0, 1.50); sp.bezier_points[0].handle_right = (-0.10, 0, 1.56)
    sp.bezier_points[1].co = (0.20, 0, 1.52); sp.bezier_points[1].handle_left = (0.10, 0, 1.56); sp.bezier_points[1].handle_right = (0.25, 0, 1.50)
    metal = bpy.data.materials.new("Metal"); metal.use_nodes = True
    pb = metal.node_tree.nodes["Principled BSDF"]
    pb.inputs["Metallic"].default_value = 1.0; pb.inputs["Roughness"].default_value = 0.25
    pb.inputs["Base Color"].default_value = (0.7, 0.7, 0.72, 1)
    for o in (hook, bar):
        o.data.materials.append(metal)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.003, depth=0.08, location=(0, 0, 1.585))
    bpy.context.object.data.materials.append(metal)


if A.hanger:
    build_hanger()

# ─────────────────────────── studio : fond, lumières, caméra ───────────────────────────
bg = hex_rgb(A.bg)
world = bpy.data.worlds.new("World"); scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = bg
world.node_tree.nodes["Background"].inputs[1].default_value = 1.0

# fond courbe (cyclo)
bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 2.0, 0))
cyclo = bpy.context.object
bm = bmesh.new(); bm.from_mesh(cyclo.data)
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=30, use_grid_fill=True)
for v in bm.verts:
    y = v.co.y
    if y > 0:
        a = min(y / 1.5, 1) * math.pi / 2
        v.co.z = (1 - math.cos(a)) * 1.5 + max(0, y - 1.5) * 2.0
        v.co.y = math.sin(a) * 1.5
bm.to_mesh(cyclo.data); bm.free()
cyclo.location = (0, 0.6, 0)
for p in cyclo.data.polygons:
    p.use_smooth = True
bgm = bpy.data.materials.new("Fond"); bgm.use_nodes = True
pbsdf = bgm.node_tree.nodes["Principled BSDF"]
pbsdf.inputs["Base Color"].default_value = bg
pbsdf.inputs["Roughness"].default_value = 0.9
cyclo.data.materials.append(bgm)


def area(name, loc, energy, size, color=(1, 1, 1), target=(0, 0, 1.25)):
    ld = bpy.data.lights.new(name, "AREA"); ld.energy = energy; ld.size = size; ld.color = color
    lo = bpy.data.objects.new(name, ld); scene.collection.objects.link(lo)
    lo.location = loc
    d = Vector(target) - Vector(loc)
    lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return lo


lights = [area("Key", (-1.4, -1.8, 2.3), 220, 1.6, (1.0, 0.96, 0.92)),
          area("Fill", (1.8, -1.4, 1.2), 50, 2.0, (0.85, 0.9, 1.0))]
lights.append(area("Rim", (0.9, 0.9, 2.0), 260 if A.anim != "chute" else 110, 0.6, (1.0, 0.3, 0.35), (0, 0, 1.4)))      # liseré rouge de la marque
lights.append(area("Rim2", (-1.0, 0.9, 1.6), 140, 0.6, (0.6, 0.75, 1.0), (0, 0, 1.3)))

cam_d = bpy.data.cameras.new("Cam"); cam_d.lens = 50
cam = bpy.data.objects.new("Cam", cam_d); scene.collection.objects.link(cam)
scene.camera = cam
target = bpy.data.objects.new("Cible", None); scene.collection.objects.link(target)
track = cam.constraints.new("TRACK_TO")
track.target = target
track.track_axis = "TRACK_NEGATIVE_Z"
track.up_axis = "UP_Y"
# lumières et fond suivent l'angle de la caméra : le dos est aussi bien éclairé que le devant
rig = bpy.data.objects.new("Rig", None); scene.collection.objects.link(rig)
# (vitrine : lumières fixes, pour que les reflets glissent sur le tissu pendant le tour)
for lo in ([cyclo] if A.anim == "vitrine" else lights + [cyclo]):
    lo.parent = rig          # rig à l'origine, sans rotation : pas d'inverse à corriger
cam_d.dof.use_dof = True
cam_d.dof.focus_object = target
cam_d.dof.aperture_fstop = 2.8

NECK_Z = shirt.location.z          # hauteur du col
f0 = PREROLL + 1
T = A.seconds


def pose_key(frame, az, h, dist, lens, tz, tx=0.0, fstop=2.8):
    """Place la caméra : az = angle autour du t-shirt (0 = face, 180 = dos), h = hauteur au-dessus de
    la cible, dist = distance, tz = hauteur de la cible sous le col, tx = décalage latéral de la cible."""
    a = math.radians(az)
    tgt = Vector((tx * math.cos(a), tx * math.sin(a), NECK_Z - tz))
    target.location = tgt
    cam.location = tgt + Vector((dist * math.sin(a), -dist * math.cos(a), h))
    cam_d.lens = lens
    cam_d.dof.aperture_fstop = fstop
    rig.rotation_euler = (0, 0, a)
    target.keyframe_insert("location", frame=frame)
    cam.keyframe_insert("location", frame=frame)
    cam_d.keyframe_insert("lens", frame=frame)
    cam_d.keyframe_insert("dof.aperture_fstop", frame=frame)
    rig.keyframe_insert("rotation_euler", frame=frame)


def add_shots(shots):
    k = T / 15.0
    for t0, t1, pa, pb in shots:
        fa = f0 + int(round(t0 * k * A.fps))
        fb = max(fa, f0 + int(round(t1 * k * A.fps)) - 1)
        pose_key(fa, *pa)
        pose_key(fb, *pb)


back = 180 if A.turn else 0
if A.orbit or A.anim == "vitrine":
    if A.anim == "vitrine":
        # un tour complet, lent, avec une légère montée et un rapprochement
        n = 9
        for i in range(n):
            fr = i / (n - 1)
            pose_key(int(f0 + fr * (total_frames - 1)), -20 + 360 * fr, 0.05 + 0.25 * fr, 2.3 - 0.5 * fr, 40, 0.36,
                     0, 3.2)
    else:
        for frac, az in ((0.0, -25), (0.58, 12), (0.76, 180), (1.0, 195)) if A.turn else ((0.0, -28), (1.0, 28)):
            pose_key(int(f0 + frac * (total_frames - 1)), az, 0.05, 2.6 - 0.4 * frac, 50, 0.36)
    for ob in (cam, target, rig, cam_d):
        for fc in ob.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
else:
    # Plans (début s, fin s, pose de départ, pose d'arrivée) pour une pub de 15 s, mis à l'échelle si
    # --seconds change. pose = (azimut, hauteur, distance, focale, cible sous le col, décalage cible, f/)
    if A.anim == "chute":
        # col à 1,45 m au départ ; dessus du socle à 0,95 m
        add_shots([
            (0.0, 2.2, (-20, 0.10, 3.0, 40, 0.30, 0, 4), (-12, 0.15, 2.6, 40, 0.30, 0, 4)),        # flotte, travelling avant
            (2.2, 5.0, (25, 0.35, 2.3, 35, 0.45, 0, 2.8), (15, 0.30, 2.1, 35, 0.50, 0, 2.8)),      # la chute
            (5.0, 8.0, (0, 1.20, 0.35, 50, 0.48, 0, 2.2), (8, 1.10, 0.30, 50, 0.48, 0, 2.2)),      # vue du dessus : le print
            (8.0, 10.2, (70, 0.05, 1.6, 35, 0.52, 0, 2.8), (120, 0.08, 1.5, 35, 0.52, 0, 2.8)),    # rasant, les plis
            (10.2, 11.8, (160, 0.30, 1.0, 85, 0.55, 0, 2.0), (172, 0.28, 0.9, 85, 0.55, 0, 2.0)),  # détail du drapé
            (11.8, 15.0, (-30, 1.00, 2.6, 40, 0.75, 0, 4), (-45, 1.10, 2.8, 40, 0.75, 0, 4)),      # final en hauteur
        ])
    else:
        add_shots([
            (0.0, 2.2, (-14, 0.05, 2.9, 40, 0.38, 0, 4), (-6, 0.08, 2.4, 40, 0.38, 0, 4)),          # large, travelling avant
            (2.2, 6.0, (-38, -0.70, 1.75, 30, 0.30, 0, 2.8), (-18, 0.10, 1.6, 30, 0.34, 0, 2.8)),    # contre-plongée, grue
            (6.0, 8.0, (-6, 0.02, 1.05, 85, 0.20, 0.06, 2.0), (8, 0.0, 0.95, 85, 0.20, 0.06, 2.0)),  # gros plan poitrine
            (8.0, 10.2, (70, 0.10, 1.6, 35, 0.36, 0, 2.8), (back - 50 if A.turn else 35, 0.15, 1.5, 35, 0.36, 0, 2.8)),
            (10.2, 11.8, (back, 0.05, 1.55, 50, 0.32, 0, 2.2), (back + 4, 0.03, 1.25, 50, 0.32, 0, 2.2)),  # dos
            (11.8, 15.0, (back + 22, 0.35, 2.3, 40, 0.62, 0, 4), (back + 34, 0.40, 2.6, 40, 0.62, 0, 4)),  # final
        ])
    # coupes franches entre les plans, mouvements doux à l'intérieur
    for ob in (cam, target, rig, cam_d):
        for fc in ob.animation_data.action.fcurves:
            pts = fc.keyframe_points
            for idx, kp in enumerate(pts):
                kp.interpolation = "BEZIER" if idx % 2 == 0 else "CONSTANT"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
    # caméra à l'épaule : petit tremblement
    for fc in cam.animation_data.action.fcurves:
        nz = fc.modifiers.new("NOISE")
        nz.strength = 0.012
        nz.scale = 22
        nz.phase = fc.array_index * 13.7

# ─────────────────────────── simulation, enregistrée avec la scène ───────────────────────────
scene.frame_start = 1
scene.frame_end = PREROLL + total_frames
scene["preroll"] = PREROLL
scene["total_frames"] = total_frames
render_part.setup_engine(scene, A)

if A.save_blend:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(A.save_blend))

n_sim = PREROLL + total_frames
t_sim = time.time()
print(f"[tshirt3d] simulation du tissu ({A.anim}) : {n_sim} images…", flush=True)


def _sim_progress(sc, _dg=None):
    f = sc.frame_current
    if f % 20 == 0 and f > 0:
        el = time.time() - t_sim
        print(f"[tshirt3d]   sim {f}/{n_sim}  ({el / f:.1f} s/image, reste ~{el / f * (n_sim - f) / 60:.0f} min)",
              flush=True)


baked = False
if A.blend:
    # La simulation est « cuite » sur le disque à côté du .blend (dossier blendcache_...). La version
    # finale rouvre ce .blend avec --render-only et ne refait pas la simulation.
    try:
        blend = os.path.abspath(A.blend)
        os.makedirs(os.path.dirname(blend), exist_ok=True)
        cloth.point_cache.use_disk_cache = True
        bpy.ops.wm.save_as_mainfile(filepath=blend)
        bpy.app.handlers.frame_change_post.append(_sim_progress)
        bpy.ops.ptcache.bake_all(bake=True)
        bpy.app.handlers.frame_change_post.remove(_sim_progress)
        bpy.ops.wm.save_mainfile()
        baked = True
        print(f"[tshirt3d] simulation enregistrée avec la scène : {blend}", flush=True)
    except Exception as e:  # on retombe sur la simulation en mémoire
        print(f"[tshirt3d] simulation non enregistrée ({e}) ; la version finale la refera.", flush=True)
        if _sim_progress in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.remove(_sim_progress)
if not baked:
    for f in range(1, n_sim + 1):
        scene.frame_set(f)
        _sim_progress(scene)
print(f"[tshirt3d] simulation terminée en {(time.time() - t_sim) / 60:.1f} min", flush=True)

if A.sim_only:
    dg = bpy.context.evaluated_depsgraph_get()
    for f in range(PREROLL, PREROLL + total_frames + 1, 15):
        scene.frame_set(f)
        me = shirt.evaluated_get(dg).to_mesh()
        ys = [v.co.y for v in me.vertices]; xs = [v.co.x for v in me.vertices]; zs = [v.co.z for v in me.vertices]
        print(f"[sim] f{f} x[{min(xs):.2f},{max(xs):.2f}] y[{min(ys):.2f},{max(ys):.2f}] z[{min(zs):.2f},{max(zs):.2f}]", flush=True)
    sys.exit(0)

render_part.render_animation(scene, A, PREROLL, total_frames)
