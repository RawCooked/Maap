# T-shirt 3D au vent — automatique

Tu donnes ton design en PNG. Le script construit un t-shirt en vrai tissu simulé dans Blender, l'accroche à un cintre et souffle du vent dessus. Il imprime ton design sur la poitrine, éclaire la scène comme en studio, fait tourner la caméra et sort un MP4. Tu n'ouvres jamais Blender.

## Installation (Windows)
1. Installe **Blender 4.5 LTS** (gratuit) : https://www.blender.org/download/lts/
2. Installe **ffmpeg** et vérifie qu'il est dans le PATH.
3. Lance :
```
"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" -b -P tshirt3d.py -- --design mon_design.png --color "#141418" --out out\tshirt.mp4
```

## Options utiles
| Option | Effet |
|---|---|
| `--design x.png` | design de face (PNG transparent conseillé) |
| `--back x.png` | design au dos |
| `--color "#C42636"` | couleur du tissu |
| `--bg "#0A0D14"` | couleur du fond du studio |
| `--print-size 0.28` | largeur du print en mètres |
| `--wind 1.5` | plus de vent (2 = tempête, 0.5 = brise) |
| `--seconds 6` | durée |
| `--preview` | 540×960 et 16 échantillons, pour tester vite |
| `--engine eevee` | rendu temps réel, 10 à 50 fois plus rapide sur un PC avec carte graphique |
| `--save-blend scene.blend` | enregistre la scène pour la retoucher à la main |
| `--every 10` | ne rend qu'une image sur 10, pour vérifier le mouvement |

## Ce que fait le script
- **Le t-shirt** : un patron (devant et dos) maillé puis cousu par le code, épinglé aux épaules sur un cintre.
- **La physique** : tissu de coton, pression interne pour le volume, collisions du tissu sur lui-même, vent avec rafales et turbulence. Les 45 premières images servent à laisser le tissu se poser et ne sont pas dans la vidéo.
- **Le print** : il est mélangé à la couleur du tissu, garde la trame du coton et brille un peu plus que le tissu, comme une vraie encre.
- **Le studio** : fond arrondi, quatre lumières dont un liseré rouge aux couleurs de la marque, caméra en orbite avec flou de profondeur.
- **Les couleurs** : le rendu reste en mode « Standard » pour garder les vraies couleurs de la marque.
- **La carte graphique** : avec Cycles, le script utilise automatiquement OptiX, CUDA, HIP ou Metal si ta machine en a une.

## Temps de rendu mesurés ici (4 cœurs, sans carte graphique)
- Simulation : environ 1 min 30 pour 5 s de vidéo.
- Rendu Cycles en 540×960 avec 16 échantillons : environ 20 s par image.
- Sur ton PC avec une carte graphique, l'option `--engine eevee` devrait passer sous la seconde par image. Je ne l'ai pas testé : il n'y a pas de carte graphique ici.

## Réglages trouvés en testant
- **La masse se règle par sommet, pas par mètre carré.** À 0,3 kg, le t-shirt pesait des centaines de kilos et ne bougeait pas ; le défaut est maintenant 0,02.
- **Le tissu ne réagit qu'au vent qui le frappe de face.** Un vent de côté glisse dessus sans effet, donc le script le fait souffler vers la caméra.
- **À trop forte puissance, le t-shirt se retourne comme un sac.** La force par défaut évite ça : `--wind 1`.
