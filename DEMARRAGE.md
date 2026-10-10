# Pub t-shirt 3D : démarrage sur ton PC (Windows)

Ta machine : Ryzen 5 5600G, Radeon RX 6650 XT, 16 Go de RAM. Elle convient, et c'est la carte graphique qui fait tout le travail de rendu.

## 1. À installer une seule fois
1. **Pilote AMD Adrenalin à jour** : https://www.amd.com/fr/support. Il en faut un récent pour que Blender utilise la carte graphique.
2. **Blender 4.5 LTS** : https://www.blender.org/download/lts/. Garde l'emplacement d'installation par défaut, le script le trouvera tout seul.
3. **Python 3.10 ou plus récent** : https://www.python.org/downloads/. **Coche « Add python.exe to PATH »** pendant l'installation.

Pas besoin d'installer ffmpeg : le lanceur l'installe tout seul (`pip install imageio-ffmpeg`).

## 2. Récupérer le projet
Sur GitHub : `RawCooked/Maap`, branche `claude/admiring-volta-tp8yyw`, bouton « Code » puis « Download ZIP ». Décompresse le ZIP, par exemple dans `Documents\Maap`.

## 3. Mettre tes designs
Dans le dossier `design\`, ajoute :
- `devant.png` : ton fichier **3.png** (la fleur) ;
- `dos.png` : ton fichier **4.png** (la spirale).

Le fond uni (#121212) est détouré automatiquement et cette même couleur devient celle du t-shirt.

Ouvre ensuite `design\produit.json` pour changer le nom, le prix et les textes. **Le prix (49 DT) et les textes actuels sont des exemples à remplacer.**

## 4. Lancer
| Fichier | Ce qu'il fait | Durée estimée sur ton PC* |
|---|---|---|
| `TEST_RAPIDE.bat` | 540×960, EEVEE : vérifie que tout marche | ~5 à 10 min |
| `LANCER_PUB3D.bat` | 1080×1920, EEVEE : la vraie pub | ~10 à 20 min |
| `LANCER_PUB3D.bat --final` | 1080×1920, Cycles sur la carte graphique (HIP) : qualité max | ~40 à 90 min |

\* Ce sont des estimations, je n'ai pas pu mesurer sur ta machine. La simulation du tissu tourne sur le processeur (quelques minutes), le rendu sur la carte graphique.

Le résultat sort dans `out\pub3d_test.mp4` ou `out\pub3d.mp4`.

En ligne de commande, tu peux aussi faire :
```
python pub3d.py --front design\devant.png --back design\dos.png --config design\produit.json --music ma_musique.mp3
python pub3d.py ... --skip-3d    # garde la 3D déjà rendue, ne refait que le montage (quelques minutes)
python pub3d.py ... --wind 1.5   # plus de vent
```

## Ce que contient la vidéo (15 s)
| Temps | Scène |
|---|---|
| 0 – 2,2 s | Accroche glitch (« CE T-SHIRT / CACHE UN / MESSAGE ») sur la 3D floutée |
| 2,2 – 6 s | La 3D apparaît : t-shirt au vent, vu de face, avec le nom du produit |
| 6 – 10,2 s | Trois cartes qui alternent gauche/droite, pendant que la caméra fait le tour vers le dos |
| 10,2 – 11,8 s | Zoom sur le dos et la spirale |
| 11,8 – 15 s | Prix barré, nouveau prix, stock, bouton COMMANDER |

## Si ça coince
- **« Blender introuvable »** : ajoute `--blender "C:\chemin\vers\blender.exe"` à la commande.
- **Rendu très lent avec `--final`** : dans Blender, va dans Édition > Préférences > Système > Cycles, choisis HIP et vérifie que la RX 6650 XT est cochée. Sinon, mets à jour le pilote AMD.
- **Le t-shirt bouge trop ou pas assez** : change `--wind` (0,5 à 2).
- **Le print est trop grand ou mal placé** : change `--print-size` (largeur de la zone d'impression en mètres, 0,30 par défaut) et `--print-top` (distance en cm entre le col et le haut de la zone, 7 par défaut).
