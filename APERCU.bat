@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Apercu du placement (1 seconde, sans Blender) ===
echo   Autre couleur : APERCU.bat --color "bleu marine"   (ou --color #1C2340)
python -m pip install -q --disable-pip-version-check -r requirements.txt
python placement.py --gabarit --front design\devant.png --back design\dos.png --color noir %*
start "" out\apercu.png
