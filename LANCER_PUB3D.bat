@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Pub 3D - qualite maximale (1080x1920, Cycles sur la carte graphique) ===
echo   Le temps restant s affiche pendant le calcul. Version rapide (EEVEE) : LANCER_PUB3D.bat --fast
python --version >nul 2>&1 || (echo Python introuvable : installe-le depuis python.org en cochant "Add to PATH". & pause & exit /b 1)
python -m pip install -q --disable-pip-version-check -r requirements.txt
python pub3d.py --front design\devant.png --back design\dos.png --config design\produit.json --out out\pub3d.mp4 %*
echo.
echo Video : out\pub3d.mp4
pause
