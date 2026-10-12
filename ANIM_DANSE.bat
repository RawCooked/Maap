@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Animation : la danse (t-shirt simule dans Marvelous Designer, 6 plans) ===
echo   Utilise le fichier modeles\danse1.abc (exporte depuis Marvelous Designer).
echo   Sans option : BROUILLON rapide. Version lourde ensuite : ANIM_DANSE.bat --final
if not exist "modeles\danse1.abc" (echo Fichier modeles\danse1.abc introuvable : exporte d'abord la danse depuis Marvelous Designer. & pause & exit /b 1)
python --version >nul 2>&1 || (echo Python introuvable : installe-le depuis python.org en cochant "Add to PATH". & pause & exit /b 1)
python -m pip install -q --disable-pip-version-check -r requirements.txt
python pub3d.py --front design\devant.png --back design\dos.png --config design\produit.json --anim vent --garment modeles\danse1.abc %*
pause
