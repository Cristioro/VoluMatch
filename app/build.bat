@echo off
setlocal

title 🔧 Compilando VoluMatch...

REM --- CONFIGURACIÓN ---
set PYTHON_ALIAS=py -3.11
set SCRIPT=VolumeNormalizerApp.py
set NAME=VoluMatch
set ICON=volumatch.ico
set FFMPEG=ffmpeg.exe

REM --- BORRAR COMPILACIONES ANTERIORES ---
echo 🧹 Limpiando compilaciones anteriores...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q "%NAME%.spec" 2>nul

REM --- COMPILAR EL .EXE CON PYINSTALLER ---
echo 🚀 Compilando %NAME%.exe con PyInstaller...
%PYTHON_ALIAS% -m PyInstaller ^
  --onefile ^
  --noconsole ^
  --name "%NAME%" ^
  --icon "%ICON%" ^
  --add-binary "%FFMPEG%;." ^
  "%SCRIPT%"

REM --- RESULTADO ---
if exist dist\%NAME%.exe (
    echo ✅ Compilación exitosa: dist\%NAME%.exe
) else (
    echo ❌ Ocurrió un error durante la compilación.
)

pause
endlocal
