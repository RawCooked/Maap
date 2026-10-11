@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Test rapide (540x960, EEVEE) ===
python --version >nul 2>&1 || (echo Python introuvable : installe-le depuis python.org en cochant "Add to PATH". & pause & exit /b 1)
python -m pip install -q --disable-pip-version-check -r requirements.txt
python pub3d.py --front design\devant.png --back design\dos.png --config design\produit.json --preview --out out\pub3d_test.mp4
echo.
echo Video : out\pub3d_test.mp4
pause
