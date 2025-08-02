@echo off
cd /d %~dp0

echo ============================
echo 🔧 Compilando VoluMatch...
echo ============================

REM Verificar si PyInstaller está disponible
C:\Users\Cristian\AppData\Local\Programs\Python\Python311\Scripts\pyinstaller.exe --version >nul 2>&1
if errorlevel 1 (
    echo ❌ PyInstaller no está instalado para py -3.11
    echo    Ejecutá: pip install pyinstaller
    pause
    exit /b
)

REM Limpiar compilaciones anteriores
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Compilar con PyInstaller
C:\Users\Cristian\AppData\Local\Programs\Python\Python311\Scripts\pyinstaller.exe ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "VoluMatch" ^
    --icon "..\assets\VoluMatch.ico" ^
    --add-data "ffmpeg.exe;." ^
    --add-data "..\assets\VoluMatch.png;assets" ^
    --add-data "lang.json;." ^
    VolumeNormalizerApp.py

echo ============================
echo ✅ VoluMatch compilado correctamente
echo ➜  EXE creado: dist\VoluMatch.exe
echo ============================
pause
