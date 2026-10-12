@echo off
chcp 65001 >nul
cd /d "%~dp0"
if "%~1"=="" (
  echo Glisse ta danse Mixamo ^(.fbx^) sur ce fichier, ou : AJOUTER_POSE_NEUTRE.bat chemin\danse.fbx
  pause & exit /b 1
)
if not exist out mkdir out
python -c "import sys; sys.path.insert(0,'.'); from pub3d import find_blender; print(find_blender(None))" > out\blender_path.txt || (echo Blender introuvable & pause & exit /b 1)
set /p BL=<out\blender_path.txt
"%BL%" -b -P tshirt3d\intro_pose.py -- "%~1" "%~dpn1_intro.fbx" | findstr /C:"[intro_pose]"
echo.
echo Fichier pret : %~dpn1_intro.fbx  ^(a importer dans Marvelous Designer comme avatar^)
pause
