@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Animation : 2 - la chute (le t-shirt tombe et se drape sur un socle) ===
echo   Sans option : BROUILLON rapide (EEVEE, Full HD) + simulation enregistree.
echo   Version lourde ensuite : ANIM2_CHUTE.bat --final   (rendu Cycles, sans refaire la simulation)
echo   Musique : mets un MP3 dans le dossier musique\ (musique\chute.mp3 ou n'importe quel .mp3)
python --version >nul 2>&1 || (echo Python introuvable : installe-le depuis python.org en cochant "Add to PATH". & pause & exit /b 1)
python -m pip install -q --disable-pip-version-check -r requirements.txt
python pub3d.py --front design\devant.png --back design\dos.png --config design\produit.json --anim chute %*
pause
