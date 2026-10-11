@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Animation : 1 - le vent (porte par un corps invisible, en plein vent, 6 plans) ===
echo   Sans option : BROUILLON rapide (EEVEE, Full HD) + simulation enregistree.
echo   Version lourde ensuite : ANIM1_VENT.bat --final   (rendu Cycles, sans refaire la simulation)
echo   Musique : mets un MP3 dans le dossier musique\ (musique\vent.mp3 ou n'importe quel .mp3)
python --version >nul 2>&1 || (echo Python introuvable : installe-le depuis python.org en cochant "Add to PATH". & pause & exit /b 1)
python -m pip install -q --disable-pip-version-check -r requirements.txt
python pub3d.py --front design\devant.png --back design\dos.png --config design\produit.json --anim vent %*
pause
