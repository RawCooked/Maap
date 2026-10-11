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

## 3 bis. Préparer et placer tes designs
**Comment le design est posé.** Chaque PNG (devant, dos) est étiré sur une **zone d'impression de 30 cm de large**, centrée, dont le haut est à **7 cm sous le col**. Sa hauteur suit les proportions du PNG : en 3000 × 3900 px, il fait 30 × 39 cm. Ce que tu dessines en haut à droite du PNG se retrouve en haut à droite du t-shirt vu de face, donc sur le cœur de la personne.

**Le gabarit.** Lance `APERCU.bat` une fois : il crée `design\GABARIT_zone_impression.png`, en 3000 × 3900 px, avec les repères (centre, zone cœur 10 × 10 cm, poitrine 25 × 12 cm, plein devant/dos 27 × 36 cm, règle en cm). Ouvre-le comme **calque du dessous** dans ton logiciel, dessine par-dessus, puis **masque le gabarit avant d'exporter**. Exporte en PNG transparent.

**L'aperçu.** `APERCU.bat` affiche en une seconde `out\apercu.png` : le t-shirt à plat, devant et dos, avec tes designs placés exactement comme dans la vidéo. `pub3d.py` le refait aussi automatiquement avant chaque rendu.

**La couleur.** Si ton design a un fond uni, ce fond devient la couleur du t-shirt. S'il est transparent, la couleur vient de `"couleur_tshirt"` dans `design\produit.json`, ou de l'option `--color`, sinon le script te la demande. Tu peux écrire un nom (noir, blanc, gris, gris chiné, bleu marine, bleu, rouge, bordeaux, vert, kaki, sable, beige, rose) ou un code `#RRGGBB`.

**Outils gratuits pour dessiner :**
| Outil | Pour quoi |
|---|---|
| **Photopea** (photopea.com, dans le navigateur) | Comme Photoshop : calques, PNG transparent. Ouvre le gabarit, ajoute ton design au-dessus |
| **Canva** / **Kittl** (version gratuite) | Typo et mise en page rapides ; crée un document en 3000 × 3900 px |
| **Inkscape** (logiciel gratuit) | Dessin vectoriel : le design reste net à toutes les tailles |
| **Générateurs de maquettes Printful / Printify** (compte gratuit) | Placent ton design sur leurs vrais t-shirts, avec leurs zones d'impression |

**L'appli qui crée un vêtement 3D à partir d'un patron** : ce sont **CLO3D** et **Marvelous Designer** (payants, avec essai gratuit). Ils servent à concevoir la coupe du vêtement. Pour poser un design sur un t-shirt existant, le gabarit et l'aperçu suffisent.

**Pour l'imprimeur** : la plupart demandent environ **300 dpi**, soit **3543 × 4606 px** pour 30 × 39 cm, en PNG transparent. Garde les mêmes proportions que le gabarit : le placement dans la vidéo reste identique. Demande-lui sa zone maximale et la distance sous le col (souvent 7 à 10 cm), et ajuste si besoin avec `--print-size` et `--print-top`.

## 4. Les trois animations : brouillon d'abord, version lourde ensuite
| Lanceur | Animation |
|---|---|
| `ANIM1_VENT.bat` | Le t-shirt porté par un corps invisible, en plein vent, filmé en 6 plans (contre-plongée, gros plans, dos) |
| `ANIM2_CHUTE.bat` | Le t-shirt flotte, puis tombe et se drape sur un socle ; vue de dessus sur le print |
| `ANIM3_VITRINE.bat` | Le t-shirt porté, sans vent, la caméra en fait le tour complet ; les reflets glissent sur le tissu |

1. **Double-clic** sur le lanceur : simulation du tissu + **brouillon** EEVEE en Full HD (`out\<anim>_brouillon.mp4`). La simulation est **enregistrée** dans `out\work\scene_<anim>.blend`.
2. Si le brouillon te plaît : **`ANIM1_VENT.bat --final`** (ou `ANIM2_CHUTE.bat --final`, `ANIM3_VITRINE.bat --final`). La version lourde (Cycles sur la carte graphique) **rouvre la scène déjà simulée** et ne fait que le rendu.
3. Tant que tu ne changes ni le design, ni la couleur, ni le vent, la simulation n'est jamais refaite. `--resim` force une nouvelle simulation.

**Musique :** mets tes MP3 libres de droits dans `musique\` (`musique\vent.mp3`, `musique\chute.mp3`, `musique\vitrine.mp3`, ou un seul MP3 pour toutes). Sans MP3, un beat est généré.

## 4 bis. Autres lanceurs
| Fichier | Ce qu'il fait | Durée estimée sur ton PC* |
|---|---|---|
| `APERCU.bat` | Aperçu à plat du placement + gabarit, sans Blender | ~1 s |
| `VERIFIER_3D.bat` | **À lancer en premier** : simulation + 8 images dans `out\check.png`, sans vidéo. Envoie l'image à Claude avant le rendu complet | la simulation + ~1 min |
| `TEST_RAPIDE.bat` | 540×960, EEVEE : **seulement pour vérifier le cadrage**. C'est volontairement basse définition, donc pixelisé | ~5 min |
| `LANCER_PUB3D.bat --fast` | 1080×1920, EEVEE : propre, rapide | ~10 à 15 min |
| `LANCER_PUB3D.bat` | 1080×1920, **Cycles sur la carte graphique, 128 échantillons** : la qualité maximale | dépend de la carte graphique : la fenêtre affiche le temps restant |

\* Ce sont des estimations, je n'ai pas pu mesurer sur ta machine. Pendant la simulation puis le rendu, chaque ligne affiche le temps par image et le temps restant (`reste ~XX min`). **Si le temps restant dépasse 2 heures, arrête avec Ctrl+C** et lance plutôt `--fast`.

Si la fenêtre affiche `ATTENTION : aucune carte graphique trouvée pour Cycles`, Blender ne voit pas ta RX 6650 XT. Le script bascule alors tout seul sur EEVEE, pour ne pas rendre pendant une journée sur le processeur. Pour que Cycles marche, mets à jour le pilote AMD Adrenalin, puis vérifie dans Blender > Édition > Préférences > Système > Cycles Render Devices > HIP.

Le résultat sort dans `out\pub3d_test.mp4` ou `out\pub3d.mp4`.

En ligne de commande, tu peux aussi faire :
```
python pub3d.py --front design\devant.png --back design\dos.png --config design\produit.json --music ma_musique.mp3
python pub3d.py ... --skip-3d       # garde la 3D déjà rendue, ne refait que le montage (quelques minutes)
python pub3d.py ... --wind 1.5      # encore plus de vent (0.5 = brise)
python pub3d.py ... --samples 256   # encore plus propre (plus long)
python pub3d.py ... --hanger        # sur un cintre au lieu du corps invisible
```

## Ce que contient la vidéo (15 s)
| Temps | Scène |
|---|---|
| 0 – 2,2 s | Accroche glitch sur la 3D floutée (plan large, travelling avant) |
| 2,2 – 6 s | Contre-plongée qui monte : le t-shirt porté par un corps invisible, en plein vent |
| 6 – 8 s | Gros plan sur la poitrine (le print devant) |
| 8 – 10,2 s | Plan latéral : les manches et le bas claquent, la caméra part vers le dos |
| 10,2 – 11,8 s | Gros plan sur le dos |
| 11,8 – 15 s | Plan final en hauteur : prix, stock, bouton COMMANDER |

## Si ça coince
- **« Blender introuvable »** : ajoute `--blender "C:\chemin\vers\blender.exe"` à la commande.
- **Rendu très lent avec `LANCER_PUB3D.bat`** : dans Blender, va dans Édition > Préférences > Système > Cycles, choisis HIP et vérifie que la RX 6650 XT est cochée. Sinon, mets à jour le pilote AMD.
- **Le t-shirt bouge trop ou pas assez** : change `--wind` (0,5 à 2).
- **Le tissu traverse le corps ou part dans tous les sens** : baisse le vent (`--wind 0.7`), et envoie-moi une image.
- **Le print est trop grand ou mal placé** : change `--print-size` (largeur de la zone d'impression en mètres, 0,30 par défaut) et `--print-top` (distance en cm entre le col et le haut de la zone, 7 par défaut).
